"""No-network job manifest generator. This does not analyze or enqueue a video."""
import argparse
import hashlib
import json
import re
from pathlib import Path
from urllib.parse import parse_qs, urlparse
import yaml


def normalize_url(raw):
    parsed = urlparse(raw)
    if parsed.scheme != 'https' or parsed.username or parsed.password or parsed.port:
        raise ValueError('HTTPS YouTube URL without credentials or custom port required')
    host = (parsed.hostname or '').lower()
    if host == 'youtu.be':
        video_id = parsed.path.strip('/')
    elif host in {'youtube.com', 'www.youtube.com', 'm.youtube.com'}:
        if parsed.path == '/watch':
            ids = parse_qs(parsed.query).get('v', [])
            video_id = ids[0] if len(ids) == 1 else ''
        elif re.fullmatch(r'/(live|shorts)/[^/]+/?', parsed.path):
            video_id = parsed.path.strip('/').split('/')[1]
        else:
            video_id = ''
    else:
        raise ValueError('Unsupported host')
    if not re.fullmatch(r'[A-Za-z0-9_-]{11}', video_id):
        raise ValueError('Invalid YouTube video ID')
    return video_id, f'https://www.youtube.com/watch?v={video_id}'


def windows(start, end, width, overlap):
    if not (0 <= start < end and 0 <= overlap < width):
        raise ValueError('Invalid time range/window/overlap')
    result = []
    cursor = start
    while cursor < end:
        stop = min(cursor + width, end)
        result.append({'start_seconds': cursor, 'end_seconds': stop})
        if stop == end:
            break
        cursor = stop - overlap
    return result


def build_plan(config, url, start, end):
    video_id, canonical = normalize_url(url)
    source_duration = config['source']['duration_seconds']
    duration = source_duration if end is None else end
    if not 0 <= start < duration <= source_duration <= config['limits']['max_video_seconds']:
        raise ValueError('Range exceeds declared source duration or configured limit')
    a = config['analysis']
    review = config.get('review', {'mode': 'ranked_general'})
    if review['mode'] not in {'ranked_general', 'friend_focus', 'mixed'}:
        raise ValueError('Unsupported review mode')
    if review['mode'] == 'friend_focus' and not review.get('focus_opponent_id'):
        raise ValueError('friend_focus requires an opponent_id; identity must be verified before live execution')
    scan = windows(start, duration, a['scan_window_seconds'], a['overlap_seconds'])
    # Index windows + detail request per selected match + one coaching summary.
    estimated_calls = len(scan) + a['max_detail_matches'] + 1
    if estimated_calls > config['limits']['max_api_calls']:
        raise ValueError('Plan exceeds API call limit')
    identity = json.dumps({'url': canonical, 'start': start, 'end': duration,
                           'analysis': a, 'player': config['player'], 'review': review,
                           'statistics': config.get('statistics', {})}, sort_keys=True)
    return {
        'schema_version': '1.0', 'state': 'PLANNED', 'analysis_executed': False,
        'job_key': hashlib.sha256(identity.encode()).hexdigest(),
        'video_id': video_id, 'source_url': canonical,
        'source_duration_seconds': source_duration,
        'range_seconds': [start, duration], 'scan_windows': scan,
        'baseline_api_calls_before_extra_windows_or_retries': estimated_calls,
        'review': review, 'statistics': config.get('statistics', {}),
        'live_prerequisites': ['verified_player_identity', 'video_model_access',
                               'gemini_api_key', 'pricing_and_budget_preflight'],
        'notes': ['plan only; no AWS resources or API calls created',
                  'scan windows overlap; deduplicate absolute match times',
                  'runtime must count additional detail windows and retries against limits',
                  'API budget is not a hard cap on AWS charges'],
    }


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--config', default='config.example.yaml')
    p.add_argument('--url')
    p.add_argument('--start', type=int, default=0)
    p.add_argument('--end', type=int)
    p.add_argument('--output', required=True)
    args = p.parse_args()
    config = yaml.safe_load(Path(args.config).read_text(encoding='utf-8'))
    plan = build_plan(config, args.url or config['source']['url'], args.start, args.end)
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(plan, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'state': 'PLANNED', 'windows': len(plan['scan_windows']),
                      'analysis_executed': False, 'output': str(out)}))


if __name__ == '__main__':
    main()
