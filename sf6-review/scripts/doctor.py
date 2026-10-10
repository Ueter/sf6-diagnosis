"""Environment check. Optional STS identity check never reads secret values."""
import argparse
import importlib.metadata
import json
import os
import shutil
import subprocess
import sys


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--check-aws', action='store_true')
    args = p.parse_args()
    result = {'python': sys.version.split()[0], 'dependencies': {}, 'tools': {},
              'gemini_key_present': bool(os.getenv('GEMINI_API_KEY')),
              'model_configured': bool(os.getenv('GEMINI_MODEL')),
              'aws_check': 'not_requested', 'analysis_implemented': False}
    missing = []
    for name in ['boto3', 'google-genai', 'PyYAML', 'jsonschema', 'yt-dlp']:
        try:
            result['dependencies'][name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            missing.append(name)
    for name in ['ffmpeg', 'ffprobe', 'node']:
        path = shutil.which(name)
        result['tools'][name] = path is not None
        if name in {'ffmpeg', 'ffprobe'} and not path:
            missing.append(name)
    if args.check_aws:
        import boto3
        from botocore.config import Config
        try:
            client = boto3.client('sts', region_name='ap-northeast-1',
                                  config=Config(connect_timeout=5, read_timeout=5,
                                                retries={'max_attempts': 0}))
            identity = client.get_caller_identity()
            result['aws_check'] = 'expected_account' if identity['Account'] == '516035591962' else 'wrong_account'
            if result['aws_check'] == 'wrong_account':
                missing.append('correct_aws_account')
        except Exception as exc:
            result['aws_check'] = 'unavailable'
            result['aws_error_type'] = type(exc).__name__
            missing.append('aws_credentials_or_connectivity')
    result['missing'] = missing
    result['local_environment_ready'] = not missing
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 1 if missing else 0


if __name__ == '__main__':
    raise SystemExit(main())
