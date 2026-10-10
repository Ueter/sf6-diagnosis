"""Shared helpers for Gemini-calling scripts: never print secret values, never call the API
without an explicit budget/opt-in check. Used by scan_window.py and detail_match.py so the
safety gates can't drift between scripts.
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Published Gemini API prices (checked 2026-10-11, see docs/validation.md). Re-check before
# trusting this for a real budget decision; pricing pages change without this script's knowledge.
# gemini-3.8-flash rate is introductory through 2026-12-31; doubles 2027-01-01.
PRICE_PER_1M_INPUT_USD = {'gemini-2.5-flash': 0.30, 'gemini-3.8-flash': 0.75}
PRICE_PER_1M_OUTPUT_USD = {'gemini-2.5-flash': 2.50, 'gemini-3.8-flash': 3.75}
# Google's documented approximate video tokenization rate at 1fps; scales ~linearly with fps.
# This is an estimate for pre-flight budget checks only, not an authoritative billing figure.
TOKENS_PER_VIDEO_SECOND_AT_1FPS = 263


def load_env(path: Path = None) -> dict:
    path = path or (ROOT / '.env')
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


def load_cost_log(path: Path = None) -> dict:
    path = path or (ROOT / 'data' / 'cost-log.json')
    if path.exists():
        return json.loads(path.read_text(encoding='utf-8'))
    return {'total_usd': 0.0, 'calls': []}


def save_cost_log(log: dict, path: Path = None) -> None:
    path = path or (ROOT / 'data' / 'cost-log.json')
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(log, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def estimate_input_tokens(duration_seconds: float, fps: float, prompt_chars: int) -> int:
    video_tokens = duration_seconds * TOKENS_PER_VIDEO_SECOND_AT_1FPS * max(fps, 1) / 1
    # crude chars->tokens for the text prompt; video dominates the estimate.
    text_tokens = prompt_chars / 4
    return int(video_tokens + text_tokens)


class BudgetGateError(Exception):
    """Raised when a live call must not proceed. `payload` is the full JSON-able error report."""
    def __init__(self, payload: dict):
        super().__init__(payload.get('error'))
        self.payload = payload


def preflight(config: dict, duration_seconds: float, fps: float, prompt_chars: int,
              output_tokens_ceiling: int, cost_log_path: Path = None) -> dict:
    """Runs all the pre-call gates. Returns an estimate report dict on success, raises
    BudgetGateError (never calls the API) on any failure."""
    if not config['limits']['live_analysis_enabled']:
        raise BudgetGateError({'error': 'live_analysis_enabled is false in config; refusing to call the API.'})

    model = config['analysis']['model']
    if not model:
        raise BudgetGateError({'error': 'analysis.model is not set in config.'})

    price_in = PRICE_PER_1M_INPUT_USD.get(model)
    price_out = PRICE_PER_1M_OUTPUT_USD.get(model)
    if price_in is None or price_out is None:
        raise BudgetGateError({'error': f'No known price for model {model}; refusing to estimate cost or call the API.'})

    est_input_tokens = estimate_input_tokens(duration_seconds, fps, prompt_chars)
    est_cost_usd = (est_input_tokens / 1_000_000) * price_in + (output_tokens_ceiling / 1_000_000) * price_out

    cost_log = load_cost_log(cost_log_path)
    budget = config['limits']['api_budget_usd']
    remaining = budget - cost_log['total_usd']
    report = {
        'model': model, 'duration_seconds': duration_seconds, 'fps': fps,
        'estimated_input_tokens': est_input_tokens, 'estimated_output_tokens_ceiling': output_tokens_ceiling,
        'estimated_cost_usd': round(est_cost_usd, 4),
        'budget_usd': budget, 'already_spent_usd': cost_log['total_usd'], 'remaining_budget_usd': round(remaining, 4),
        'price_per_1m_input_usd': price_in, 'price_per_1m_output_usd': price_out,
    }
    if est_cost_usd > remaining:
        raise BudgetGateError({'error': 'Estimated cost exceeds remaining budget; refusing to call the API.', **report})
    return report


def record_actual_cost(script_name: str, model: str, window: dict, usage, cost_log_path: Path = None) -> float:
    price_in = PRICE_PER_1M_INPUT_USD[model]
    price_out = PRICE_PER_1M_OUTPUT_USD[model]
    actual_input = usage.prompt_token_count or 0
    actual_output = usage.candidates_token_count or 0
    actual_cost = (actual_input / 1_000_000) * price_in + (actual_output / 1_000_000) * price_out

    cost_log = load_cost_log(cost_log_path)
    cost_log['total_usd'] += actual_cost
    cost_log['calls'].append({
        'script': script_name, 'model': model, 'window': window,
        'input_tokens': actual_input, 'output_tokens': actual_output, 'cost_usd': round(actual_cost, 4),
    })
    save_cost_log(cost_log, cost_log_path)
    return actual_cost, actual_input, actual_output, cost_log['total_usd']
