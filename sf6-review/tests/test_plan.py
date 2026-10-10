import importlib.util
import unittest
from pathlib import Path
import yaml

root = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('plan_job', root / 'scripts/plan_job.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class PlanTest(unittest.TestCase):
    def test_same_video_has_stable_key(self):
        config = yaml.safe_load((root / 'config.example.yaml').read_text())
        first = module.build_plan(config, 'https://www.youtube.com/live/3BGM_C5DHHs?si=abc', 0, 900)
        second = module.build_plan(config, 'https://youtu.be/3BGM_C5DHHs', 0, 900)
        self.assertEqual(first['job_key'], second['job_key'])
        self.assertFalse(first['analysis_executed'])

    def test_full_archive_has_no_gaps_and_bounded_overlap(self):
        result = module.windows(0, 10684, 900, 5)
        self.assertEqual(result[0]['start_seconds'], 0)
        self.assertEqual(result[-1]['end_seconds'], 10684)
        for prev, cur in zip(result, result[1:]):
            self.assertEqual(prev['end_seconds'] - cur['start_seconds'], 5)
            self.assertGreater(cur['end_seconds'], prev['end_seconds'])

    def test_no_network_or_local_paths_as_source(self):
        for bad in ['https://youtube.com.evil.test/watch?v=3BGM_C5DHHs',
                    'http://www.youtube.com/watch?v=3BGM_C5DHHs',
                    'https://user:pass@youtube.com/watch?v=3BGM_C5DHHs',
                    'https://youtube.com:123/watch?v=3BGM_C5DHHs',
                    'file:///etc/passwd', 'https://youtube.com/playlist?list=abc']:
            with self.assertRaises(ValueError):
                module.normalize_url(bad)

    def test_budget_call_limit_and_range(self):
        config = yaml.safe_load((root / 'config.example.yaml').read_text())
        config['limits']['max_api_calls'] = 1
        with self.assertRaises(ValueError):
            module.build_plan(config, config['source']['url'], 0, 900)
        with self.assertRaises(ValueError):
            module.windows(0, 900, 900, 900)

    def test_friend_population_has_separate_key(self):
        config = yaml.safe_load((root / 'config.example.yaml').read_text())
        general = module.build_plan(config, config['source']['url'], 0, 900)
        config['review']['mode'] = 'friend_focus'
        with self.assertRaises(ValueError):
            module.build_plan(config, config['source']['url'], 0, 900)
        config['review']['focus_opponent_id'] = 'fixture-friend-not-a-real-player'
        friend = module.build_plan(config, config['source']['url'], 0, 900)
        self.assertNotEqual(general['job_key'], friend['job_key'])


if __name__ == '__main__':
    unittest.main()
