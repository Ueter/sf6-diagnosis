import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import yaml

root = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('scan_window', root / 'scripts/scan_window.py')
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


class ScanWindowGateTest(unittest.TestCase):
    def run_main(self, config_path, tmp_path):
        out = tmp_path / 'out.json'
        argv = ['scan_window.py', '--config', str(config_path), '--start', '0', '--end', '900', '--output', str(out)]
        with mock.patch.object(sys, 'argv', argv):
            code = module.main()
        return code

    def test_refuses_when_live_analysis_disabled(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            config_path = write_config(tmp_path, **{'limits.live_analysis_enabled': False})
            self.assertEqual(self.run_main(config_path, tmp_path), 1)

    def test_refuses_when_model_has_no_known_price(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            config = yaml.safe_load((root / 'config.example.yaml').read_text(encoding='utf-8'))
            config['limits']['live_analysis_enabled'] = True
            config['analysis']['model'] = 'some-future-model-not-in-price-table'
            config_path = tmp_path / 'config.yaml'
            config_path.write_text(yaml.safe_dump(config), encoding='utf-8')
            self.assertEqual(self.run_main(config_path, tmp_path), 1)

    def test_refuses_when_estimate_exceeds_remaining_budget(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            config_path = write_config(tmp_path, **{'limits.live_analysis_enabled': True, 'limits.api_budget_usd': 0.0001})
            self.assertEqual(self.run_main(config_path, tmp_path), 1)

    def test_dry_run_never_calls_api_and_reports_estimate(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            config_path = write_config(tmp_path, **{'limits.live_analysis_enabled': True})
            out = tmp_path / 'out.json'
            argv = ['scan_window.py', '--config', str(config_path), '--start', '0', '--end', '900',
                    '--output', str(out), '--dry-run']
            with mock.patch.object(sys, 'argv', argv):
                code = module.main()
            self.assertEqual(code, 0)
            self.assertFalse(out.exists())

    def test_candidates_only_schema_strips_bookkeeping_fields(self):
        full_schema = json.loads((root / 'schemas/match_index.schema.json').read_text(encoding='utf-8'))
        reduced = module.build_candidates_only_schema(full_schema)
        self.assertEqual(set(reduced['properties']), {'candidates'})
        self.assertEqual(reduced['required'], ['candidates'])


if __name__ == '__main__':
    unittest.main()
