"""Detail-stage: ask Gemini for per-episode data (wakeup/anti-air/damage sequences etc.) within
ONE already-identified match clip. This is step 4 of CLAUDE.md's handoff.

Match-level bookkeeping (match_id, round grouping, mode, character, patch, player_side) is filled
in locally after the call, never trusted to the model's echo, same philosophy as scan_window.py.
Each episode keeps observed/inferred/unknown classification and evidence timestamps; this script
does not upgrade or invent anything beyond what the model reports.

Usage example (match_3 from the 0-900s scan, Juri vs Sagat, 336-435s):
  python scripts/detail_match.py --start 336 --end 435 --match-id match_3 \
      --opponent-character Sagat --player-side 1P --output data/detail-match_3.json
"""
import argparse
import json
import re
import sys
import uuid
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator

import gemini_common as gc

ROOT = gc.ROOT

DETAIL_PROMPT_TEMPLATE = """あなたはStreet Fighter 6の1試合（{start}秒〜{end}秒、動画の絶対時刻）を詳しく確認するアシスタントです。対象プレイヤー「{player_name}」（{player_side}側、{player_character}使用）の視点で、この試合を「機会（episode）」単位に分解してください。

機会の種類（kind）:
- wakeup_attack: 自分が起き攻め側（相手の起き上がりに攻める）
- wakeup_defend: 自分が起き上がり側（相手の起き攻めを受ける）
- anti_air_opportunity: 相手の飛び込みに対して自分が対空できる機会
- drive_impact_opportunity: ドライブインパクトが絡む攻防
- neutral_exchange: 上記に当てはまらない通常の間合い・差し合い
- unknown: 種類を判断できない

厳守事項:
- 一連のコンボ（複数ヒット）はdamage_sequenceという1つのkindの機会としてまとめ、各ヒットを別々の機会にしない（damage_sequenceも選択肢に含めてよい。一撃も複数ヒットのコンボも1機会として扱う）。
- resultのdealt/receivedは、画面のHPバーから読み取れた体力減少を「相手/自分の最大体力に対する%」で記録する。読み取れない場合はnullにする。測定誤差が大きい場合はmeasurement_error_percentに概算を入れる。
- horizon_secondsは3または5のどちらか（機会の開始から何秒後の体力を見たか）。
- 区間の終端で機会が完結しなかった場合はresult.censoredをtrueにする。
- evidenceには根拠となった画面の絶対秒とobservation（見えたものの説明）を最低1つ入れる。
- classificationは、画面に明確に表示されている事実はobserved、見えていないが行動から推測できるものはinferred、判断できないものはunknown。確定反撃やシミー意図など読み取れない内容はinferredまたはunknownにし、断定しない。
- confidenceは0から1の数値。
- previous_episode_idで直前の機会とのつながりを示す（なければnull）。
- round_numberは1〜3のラウンド番号（画面表示から分かる範囲で）。分からなければ1にし confidenceを下げる。
- 架空の機会を作らない。見つからなければ空配列を返す。

出力は指定されたJSON Schemaの形式で、episodesのみを埋めてください。"""


def build_episode_request_schema(full_schema: dict) -> dict:
    """Model only fills per-episode behavior; match-level bookkeeping fields are injected locally.
    health_unit is a const the model unreliably echoes verbatim, so it is dropped here and
    injected locally in hydrate_episodes instead, same as the match-level fields."""
    episode_item = full_schema['properties']['episodes']['items']
    excluded = {'session_id', 'match_id', 'round_id', 'mode', 'opponent_id', 'character',
                'opponent_character', 'patch', 'player_side'}
    properties = {k: v for k, v in episode_item['properties'].items() if k not in excluded}
    result_schema = dict(properties['result'])
    result_properties = {k: v for k, v in result_schema['properties'].items() if k != 'health_unit'}
    result_required = [f for f in result_schema['required'] if f != 'health_unit']
    properties['result'] = {**result_schema, 'properties': result_properties, 'required': result_required}
    properties['round_number'] = {'type': 'integer', 'minimum': 1, 'maximum': 3}
    required = [f for f in episode_item['required'] if f not in excluded] + ['round_number']
    return {
        '$schema': full_schema['$schema'],
        'type': 'object',
        'additionalProperties': False,
        'required': ['episodes'],
        'properties': {
            'episodes': {
                'type': 'array',
                'items': {'type': 'object', 'additionalProperties': False,
                          'required': required, 'properties': properties},
            }
        },
    }


def hydrate_episodes(raw_episodes: list, *, match_id: str, mode: str, opponent_id,
                      character: str, opponent_character, patch, player_side: str) -> list:
    """Fill in match-level fields locally, assign globally-unique episode_ids, and remap
    previous_episode_id references so they still point at the right episode after renaming."""
    id_map = {}
    for i, ep in enumerate(raw_episodes):
        local_id = ep.get('episode_id') or f'local_{i}'
        id_map[local_id] = f'{match_id}_ep{i + 1}'

    hydrated = []
    for i, ep in enumerate(raw_episodes):
        local_id = ep.get('episode_id') or f'local_{i}'
        round_number = ep.pop('round_number', 1)
        prev_local = ep.get('previous_episode_id')
        result = dict(ep.get('result') or {})
        result['health_unit'] = 'percent_max_health'
        hydrated.append({
            **ep,
            'result': result,
            'episode_id': id_map[local_id],
            'session_id': match_id,
            'match_id': match_id,
            'round_id': f'{match_id}_r{round_number}',
            'mode': mode,
            'opponent_id': opponent_id,
            'character': character,
            'opponent_character': opponent_character,
            'patch': patch,
            'player_side': player_side,
            'previous_episode_id': id_map.get(prev_local) if prev_local else None,
        })
    return hydrated


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--config', default='config.yaml')
    p.add_argument('--start', type=int, required=True)
    p.add_argument('--end', type=int, required=True)
    p.add_argument('--match-id', required=True, help='Identifier for this match, e.g. match_3 from the scan output.')
    p.add_argument('--opponent-character', required=True)
    p.add_argument('--player-side', required=True, choices=['1P', '2P', 'unknown'])
    p.add_argument('--output', required=True)
    p.add_argument('--dry-run', action='store_true')
    args = p.parse_args()

    config = yaml.safe_load((ROOT / args.config).read_text(encoding='utf-8'))
    env = gc.load_env()

    fps = config['analysis']['detail_fps']
    duration = args.end - args.start
    max_clip = config['analysis']['max_detail_clip_seconds']
    if duration > max_clip:
        print(json.dumps({'error': f'Clip duration {duration}s exceeds max_detail_clip_seconds ({max_clip}s). Split the match into sub-clips.'}))
        return 1

    prompt = DETAIL_PROMPT_TEMPLATE.format(
        start=args.start, end=args.end,
        player_name=config['player']['name'] or 'unknown',
        player_side=args.player_side,
        player_character=config['player']['character'],
    )

    try:
        estimate = gc.preflight(config, duration, fps, len(prompt), output_tokens_ceiling=8000)
    except gc.BudgetGateError as exc:
        print(json.dumps(exc.payload, ensure_ascii=False, indent=2))
        return 1

    if args.dry_run:
        print(json.dumps({'dry_run': True, **estimate}, ensure_ascii=False, indent=2))
        return 0

    if not env.get('GEMINI_API_KEY'):
        print(json.dumps({'error': 'GEMINI_API_KEY not set in .env.'}))
        return 1

    from google import genai
    from google.genai import types

    client = genai.Client(api_key=env['GEMINI_API_KEY'])
    full_schema = json.loads((ROOT / 'schemas/episodes.schema.json').read_text(encoding='utf-8'))
    request_schema = build_episode_request_schema(full_schema)

    video_part = types.Part(
        file_data=types.FileData(file_uri=config['source']['url']),
        video_metadata=types.VideoMetadata(start_offset=f'{args.start}s', end_offset=f'{args.end}s', fps=fps),
    )
    response = client.models.generate_content(
        model=config['analysis']['model'],
        contents=[prompt, video_part],
        config=types.GenerateContentConfig(response_mime_type='application/json', response_json_schema=request_schema),
    )

    parsed = json.loads(response.text)
    video_id_match = re.search(r'v=([A-Za-z0-9_-]{11})', config['source']['url'])
    mode = config['review']['mode']
    episodes = hydrate_episodes(
        parsed.get('episodes', []), match_id=args.match_id, mode=mode,
        opponent_id=config['review'].get('focus_opponent_id') or None,
        character=config['player']['character'], opponent_character=args.opponent_character,
        patch=config['analysis']['game_patch'], player_side=args.player_side,
    )

    result = {
        'schema_version': '1.0',
        'job_id': f'detail-{uuid.uuid4().hex[:12]}',
        'video_id': video_id_match.group(1),
        'sampling': {'method': 'pilot', 'seed': None, 'eligible_matches': 1, 'analyzed_matches': 1},
        'coverage': {
            'analyzed_seconds': duration, 'opportunity_detection_validated': False,
            'manual_validation_matches': 0, 'missingness_notes': [],
        },
        'episodes': episodes,
    }

    validator = Draft202012Validator(full_schema)
    errors = sorted(validator.iter_errors(result), key=str)
    schema_valid = not errors

    window = {'start_seconds': args.start, 'end_seconds': args.end, 'fps': fps, 'match_id': args.match_id}
    actual_cost, actual_input, actual_output, cumulative = gc.record_actual_cost(
        'detail_match.py', config['analysis']['model'], window, response.usage_metadata)

    out_path = ROOT / args.output
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

    kind_counts = {}
    for ep in episodes:
        kind_counts[ep['kind']] = kind_counts.get(ep['kind'], 0) + 1

    print(json.dumps({
        'output': str(out_path), 'episodes_found': len(episodes), 'kind_counts': kind_counts,
        'schema_valid': schema_valid, 'schema_errors': [e.message for e in errors][:5],
        'actual_input_tokens': actual_input, 'actual_output_tokens': actual_output,
        'actual_cost_usd': round(actual_cost, 4),
        'cumulative_cost_usd': round(cumulative, 4), 'budget_usd': config['limits']['api_budget_usd'],
    }, ensure_ascii=False, indent=2))
    return 0 if schema_valid else 2


if __name__ == '__main__':
    raise SystemExit(main())
