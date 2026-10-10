import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import yaml

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / 'scripts'))  # detail_match.py imports sibling gemini_common
spec = importlib.util.spec_from_file_location('detail_match', root / 'scripts/detail_match.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def write_config(tmp_path, **overrides):
    config = yaml.safe_load((root / 'config.example.yaml').read_text(encoding='utf-8'))
    config['analysis']['model'] = 'gemini-3.8-flash'
    for key, value in overrides.items():
        section, field = key.split('.')
        config[section][field] = value
    path = tmp_path / 'config.yaml'
    path.write_text(yaml.safe_dump(config), encoding='utf-8')
    return path


class DetailMatchGateTest(unittest.TestCase):
    def run_main(self, config_path, tmp_path, extra_args=None):
        out = tmp_path / 'out.json'
        argv = ['detail_match.py', '--config', str(config_path), '--start', '336', '--end', '435',
                '--match-id', 'match_3', '--opponent-character', 'Sagat', '--player-side', '1P',
                '--output', str(out)] + (extra_args or [])
        with mock.patch.object(sys, 'argv', argv):
            code = module.main()
        return code, out

    def test_refuses_when_live_analysis_disabled(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            config_path = write_config(tmp_path, **{'limits.live_analysis_enabled': False})
            code, out = self.run_main(config_path, tmp_path)
            self.assertEqual(code, 1)
            self.assertFalse(out.exists())

    def test_refuses_when_model_has_no_known_price(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            config = yaml.safe_load((root / 'config.example.yaml').read_text(encoding='utf-8'))
            config['limits']['live_analysis_enabled'] = True
            config['analysis']['model'] = 'some-future-model-not-in-price-table'
            config_path = tmp_path / 'config.yaml'
            config_path.write_text(yaml.safe_dump(config), encoding='utf-8')
            code, out = self.run_main(config_path, tmp_path)
            self.assertEqual(code, 1)

    def test_refuses_when_estimate_exceeds_remaining_budget(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            config_path = write_config(tmp_path, **{'limits.live_analysis_enabled': True, 'limits.api_budget_usd': 0.0001})
            code, out = self.run_main(config_path, tmp_path)
            self.assertEqual(code, 1)

    def test_dry_run_never_calls_api_and_reports_estimate(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            config_path = write_config(tmp_path, **{'limits.live_analysis_enabled': True})
            code, out = self.run_main(config_path, tmp_path, extra_args=['--dry-run'])
            self.assertEqual(code, 0)
            self.assertFalse(out.exists())

    def test_refuses_clip_longer_than_max_detail_clip_seconds(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            config_path = write_config(tmp_path, **{'limits.live_analysis_enabled': True, 'analysis.max_detail_clip_seconds': 10})
            code, out = self.run_main(config_path, tmp_path)
            self.assertEqual(code, 1)
            self.assertFalse(out.exists())

    def test_episode_request_schema_excludes_match_level_bookkeeping(self):
        full_schema = json.loads((root / 'schemas/episodes.schema.json').read_text(encoding='utf-8'))
        reduced = module.build_episode_request_schema(full_schema)
        props = reduced['properties']['episodes']['items']['properties']
        for excluded_field in ['session_id', 'match_id', 'round_id', 'mode', 'opponent_id',
                                'character', 'opponent_character', 'patch', 'player_side']:
            self.assertNotIn(excluded_field, props)
        self.assertIn('round_number', props)
        self.assertIn('kind', props)
        self.assertIn('evidence', props)
        self.assertNotIn('health_unit', props['result']['properties'])
        self.assertNotIn('health_unit', props['result']['required'])

    def test_hydrate_episodes_fills_bookkeeping_and_remaps_previous_episode_id(self):
        raw = [
            {'episode_id': 'a', 'round_number': 1, 'previous_episode_id': None, 'kind': 'neutral_exchange',
             'result': {'success': True, 'dealt': 10, 'received': 0, 'horizon_seconds': 3, 'censored': False}},
            {'episode_id': 'b', 'round_number': 1, 'previous_episode_id': 'a', 'kind': 'damage_sequence',
             'result': {'success': True, 'dealt': 20, 'received': 0, 'horizon_seconds': 3, 'censored': False}},
        ]
        hydrated = module.hydrate_episodes(
            raw, match_id='match_3', mode='ranked_general', opponent_id=None,
            character='Juri', opponent_character='Sagat', patch='2.0401', player_side='1P')
        self.assertEqual(hydrated[0]['episode_id'], 'match_3_ep1')
        self.assertEqual(hydrated[1]['episode_id'], 'match_3_ep2')
        self.assertEqual(hydrated[1]['previous_episode_id'], 'match_3_ep1')
        self.assertIsNone(hydrated[0]['previous_episode_id'])
        for ep in hydrated:
            self.assertEqual(ep['match_id'], 'match_3')
            self.assertEqual(ep['mode'], 'ranked_general')
            self.assertEqual(ep['character'], 'Juri')
            self.assertEqual(ep['opponent_character'], 'Sagat')
            self.assertEqual(ep['player_side'], '1P')
            self.assertEqual(ep['round_id'], 'match_3_r1')
            self.assertNotIn('round_number', ep)
            self.assertEqual(ep['result']['health_unit'], 'percent_max_health')


if __name__ == '__main__':
    unittest.main()
