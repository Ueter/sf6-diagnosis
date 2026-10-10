import json
import unittest
from pathlib import Path
from google.genai import types
from jsonschema import Draft202012Validator, ValidationError
import yaml

root = Path(__file__).resolve().parents[1]


class ContractTest(unittest.TestCase):
    def test_video_sdk_supports_clip_parameters(self):
        # SDK construction only: this never sends a video/API request.
        part = types.Part(file_data=types.FileData(file_uri='https://www.youtube.com/watch?v=3BGM_C5DHHs'),
                          video_metadata=types.VideoMetadata(start_offset='0s', end_offset='900s', fps=5))
        self.assertEqual(part.video_metadata.fps, 5)
        self.assertEqual(part.video_metadata.end_offset, '900s')

    def test_episode_contract_is_valid_and_requires_quality_fields(self):
        schema = json.loads((root / 'schemas/episodes.schema.json').read_text(encoding='utf-8'))
        Draft202012Validator.check_schema(schema)
        validator = Draft202012Validator(schema)
        with self.assertRaises(ValidationError):
            validator.validate({'schema_version': '1.0', 'episodes': []})

    def test_config_has_separate_population_and_no_live_run(self):
        config = yaml.safe_load((root / 'config.example.yaml').read_text(encoding='utf-8'))
        self.assertEqual(config['review']['mode'], 'ranked_general')
        self.assertFalse(config['limits']['live_analysis_enabled'])
        self.assertEqual(config['statistics']['sampling'], 'uniform_random_matches')

    def test_no_runtime_or_existing_business_resources_in_foundation(self):
        template = json.loads((root / 'infra/foundation.json').read_text(encoding='utf-8'))
        kinds = [v['Type'] for v in template['Resources'].values()]
        self.assertNotIn('AWS::EC2::Instance', kinds)
        self.assertNotIn('AWS::ECS::Service', kinds)
        self.assertNotIn('AWS::ECS::TaskDefinition', kinds)
        self.assertNotIn('AWS::EC2::NatGateway', kinds)
        serialized = json.dumps(template)
        self.assertNotIn('indeed-ai-assistant', serialized)
        self.assertNotIn('GEMINI_API_KEY', serialized)


if __name__ == '__main__':
    unittest.main()
