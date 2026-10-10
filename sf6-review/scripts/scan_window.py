"""Scan-stage: ask Gemini for match CANDIDATES in one time window of a public YouTube video.

This is step 3/4 of CLAUDE.md's handoff: explore 0-900s, identify match boundaries and the
player's own matches as *candidates* that a human must cross-check, not confirmed facts.

Safety gates (see docs/design.md section 4-5 and config.example.yaml):
- Refuses to call the API unless limits.live_analysis_enabled is true in config.
- Refuses to call the API if the estimated cost of this call would exceed the remaining budget.
- Never asserts damage/fight outcomes beyond what the model reports with evidence timestamps.
- Output candidates carry observed/inferred/unknown classification; this script does not upgrade them.

Never logs the API key. Writes raw + parsed output under data/ (gitignored) for manual review.
"""
import argparse
import json
import re
import sys
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]

# Published Gemini API price (checked 2026-10-11, see docs/validation.md). Re-check before trusting
# this for a real budget decision; pricing pages change without this script's knowledge.
# gemini-3.8-flash rate is introductory through 2026-12-31; doubles 2027-01-01.
PRICE_PER_1M_INPUT_USD = {'gemini-2.5-flash': 0.30, 'gemini-3.8-flash': 0.75}
PRICE_PER_1M_OUTPUT_USD = {'gemini-2.5-flash': 2.50, 'gemini-3.8-flash': 3.75}
# Google's documented approximate video tokenization rate at 1fps; scales ~linearly with fps.
# This is an estimate for pre-flight budget checks only, not an authoritative billing figure.
TOKENS_PER_VIDEO_SECOND_AT_1FPS = 263


def load_env(path: Path) -> dict:
    env = {}
    if not path.exists():
        return env
    for line in path.read_text(encoding='utf-8').splitlines():
        s = line.strip()
        if not s or s.startswith('#') or '=' not in s:
            continue
        k, v = s.split('=', 1)
        env[k.strip()] = v.strip()
    return env


def load_cost_log(path: Path) -> dict:
    if path.exists():
        return json.loads(path.read_text(encoding='utf-8'))
    return {'total_usd': 0.0, 'calls': []}


def save_cost_log(path: Path, log: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(log, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def estimate_input_tokens(duration_seconds: float, fps: float, prompt_chars: int) -> int:
    video_tokens = duration_seconds * TOKENS_PER_VIDEO_SECOND_AT_1FPS * max(fps, 1) / 1
    # crude chars->tokens for the text prompt; video dominates the estimate.
    text_tokens = prompt_chars / 4
    return int(video_tokens + text_tokens)


SCAN_PROMPT_TEMPLATE = """あなたはStreet Fighter 6の配信映像を確認するアシスタントです。以下の区間（{start}秒〜{end}秒、動画の絶対時刻）を見て、試合の候補を列挙してください。

厳守事項:
- これは探索段階であり、技の成否やダメージ量などの精密判定は行わない。
- 対象プレイヤーの表示名は「{player_name}」。この名前が画面に見えた場合のみplayer_display_name_seenに記載する。キャラクターが{player_character}だから本人、と断定しない。名前が見えない/低画質/同キャラ対戦などで本人かどうか不明な場合はnullまたはunknownとし、verify_timestampsにその旨の確認すべき時刻を入れる。
- Battle Hub・カスタムルームとランクマッチを画面表示から判断し、区別できない場合はmode_guessをunknownにする。
- 各試合候補について、開始・終了の絶対秒（この動画全体に対する絶対時刻）、両者のキャラクター、本人のサイド（1P/2P）、ラウンド結果（win/loss/incomplete/unknown）を可能な範囲で記載する。
- 確認が必要な時刻（本人確認、結果確認など）をverify_timestampsに列挙する。
- classificationは、画面に明確に表示されている事実はobserved、推測はinferred、判断できないものはunknownとする。
- confidenceは0から1の数値で、根拠の強さを表す。
- 区間の境界をまたいで試合が始まっている/終わっていない場合は、見えた範囲をそのまま記載し、round_resultをincompleteにする。
- 見つからなければ空配列を返す。架空の試合を作らない。

出力は指定されたJSON Schemaの形式で、candidatesのみを埋めてください。"""


def build_candidates_only_schema(full_schema: dict) -> dict:
    """The model only needs to produce `candidates`; job_key/video_id/window are filled in locally
    so bookkeeping fields are never at the mercy of the model echoing them back correctly."""
    return {
        '$schema': full_schema['$schema'],
        'type': 'object',
        'additionalProperties': False,
        'required': ['candidates'],
        'properties': {'candidates': full_schema['properties']['candidates']},
    }


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--config', default='config.yaml')
    p.add_argument('--start', type=int, required=True)
    p.add_argument('--end', type=int, required=True)
    p.add_argument('--output', required=True)
    p.add_argument('--dry-run', action='store_true', help='Build the request and print the cost estimate, but never call the API.')
    args = p.parse_args()

    config = yaml.safe_load((ROOT / args.config).read_text(encoding='utf-8'))
    env = load_env(ROOT / '.env')

    if not config['limits']['live_analysis_enabled']:
        print(json.dumps({'error': 'live_analysis_enabled is false in config; refusing to call the API.'}))
        return 1

    model = config['analysis']['model']
    if not model:
        print(json.dumps({'error': 'analysis.model is not set in config.'}))
        return 1

    fps = config['analysis']['scan_fps']
    duration = args.end - args.start
    prompt = SCAN_PROMPT_TEMPLATE.format(
        start=args.start, end=args.end,
        player_name=config['player']['name'] or 'unknown',
        player_character=config['player']['character'],
    )

    est_input_tokens = estimate_input_tokens(duration, fps, len(prompt))
    est_output_tokens = 4000  # rough ceiling for a 15-minute window's worth of candidates
    price_in = PRICE_PER_1M_INPUT_USD.get(model)
    price_out = PRICE_PER_1M_OUTPUT_USD.get(model)
    if price_in is None or price_out is None:
        print(json.dumps({'error': f'No known price for model {model}; refusing to estimate cost or call the API.'}))
        return 1
    est_cost_usd = (est_input_tokens / 1_000_000) * price_in + (est_output_tokens / 1_000_000) * price_out

    cost_log_path = ROOT / 'data' / 'cost-log.json'
    cost_log = load_cost_log(cost_log_path)
    budget = config['limits']['api_budget_usd']
    remaining = budget - cost_log['total_usd']
    estimate_report = {
        'model': model, 'duration_seconds': duration, 'fps': fps,
        'estimated_input_tokens': est_input_tokens, 'estimated_output_tokens_ceiling': est_output_tokens,
        'estimated_cost_usd': round(est_cost_usd, 4),
        'budget_usd': budget, 'already_spent_usd': cost_log['total_usd'], 'remaining_budget_usd': round(remaining, 4),
    }

    if est_cost_usd > remaining:
        print(json.dumps({'error': 'Estimated cost exceeds remaining budget; refusing to call the API.', **estimate_report}, ensure_ascii=False, indent=2))
        return 1

    if args.dry_run:
        print(json.dumps({'dry_run': True, **estimate_report}, ensure_ascii=False, indent=2))
        return 0

    if not env.get('GEMINI_API_KEY'):
        print(json.dumps({'error': 'GEMINI_API_KEY not set in .env.'}))
        return 1

    from google import genai
    from google.genai import types

    client = genai.Client(api_key=env['GEMINI_API_KEY'])
    full_schema = json.loads((ROOT / 'schemas/match_index.schema.json').read_text(encoding='utf-8'))
    request_schema = build_candidates_only_schema(full_schema)

    video_part = types.Part(
        file_data=types.FileData(file_uri=config['source']['url']),
        video_metadata=types.VideoMetadata(start_offset=f'{args.start}s', end_offset=f'{args.end}s', fps=fps),
    )
    response = client.models.generate_content(
        model=model,
        contents=[prompt, video_part],
        config=types.GenerateContentConfig(response_mime_type='application/json', response_json_schema=request_schema),
    )

    usage = response.usage_metadata
    actual_input = usage.prompt_token_count or 0
    actual_output = usage.candidates_token_count or 0
    actual_cost = (actual_input / 1_000_000) * price_in + (actual_output / 1_000_000) * price_out

    parsed = json.loads(response.text)
    video_id_match = re.search(r'v=([A-Za-z0-9_-]{11})', config['source']['url'])
    result = {
        'schema_version': '1.0',
        'job_key': f"scan-{video_id_match.group(1)}-{args.start}-{args.end}",
        'video_id': video_id_match.group(1),
        'window': {'start_seconds': args.start, 'end_seconds': args.end, 'fps': fps},
        'candidates': parsed.get('candidates', []),
    }

    validator = Draft202012Validator(full_schema)
    errors = sorted(validator.iter_errors(result), key=str)
    schema_valid = not errors

    cost_log['total_usd'] += actual_cost
    cost_log['calls'].append({
        'script': 'scan_window.py', 'model': model, 'window': result['window'],
        'input_tokens': actual_input, 'output_tokens': actual_output, 'cost_usd': round(actual_cost, 4),
    })
    save_cost_log(cost_log_path, cost_log)

    out_path = ROOT / args.output
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

    print(json.dumps({
        'output': str(out_path), 'candidates_found': len(result['candidates']),
        'schema_valid': schema_valid,
        'schema_errors': [e.message for e in errors][:5],
        'actual_input_tokens': actual_input, 'actual_output_tokens': actual_output,
        'actual_cost_usd': round(actual_cost, 4),
        'cumulative_cost_usd': round(cost_log['total_usd'], 4), 'budget_usd': budget,
    }, ensure_ascii=False, indent=2))
    return 0 if schema_valid else 2


if __name__ == '__main__':
    raise SystemExit(main())
