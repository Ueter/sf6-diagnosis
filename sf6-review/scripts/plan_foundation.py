"""Create a CloudFormation change set only. Never execute it."""
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
import boto3
from botocore.config import Config
from botocore.exceptions import ClientError


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--vpc-id', required=True)
    p.add_argument('--stack-name', default='Sf6ReviewFoundation')
    p.add_argument('--execution-role-arn')
    args = p.parse_args()
    settings = Config(connect_timeout=5, read_timeout=20, retries={'max_attempts': 2})
    identity = boto3.client('sts', config=settings).get_caller_identity()
    if identity['Account'] != '516035591962':
        raise SystemExit('Wrong AWS account; stopped')
    cf = boto3.client('cloudformation', region_name='ap-northeast-1', config=settings)
    kind = 'UPDATE'
    try:
        cf.describe_stacks(StackName=args.stack_name)
    except ClientError as exc:
        if exc.response['Error']['Code'] == 'ValidationError' and 'does not exist' in exc.response['Error']['Message']:
            kind = 'CREATE'
        else:
            raise
    template = Path(__file__).resolve().parents[1] / 'infra/foundation.json'
    params = {'StackName': args.stack_name,
              'ChangeSetName': 'sf6-foundation-' + datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S%f'),
              'ChangeSetType': kind, 'TemplateBody': template.read_text(),
              'Parameters': [{'ParameterKey': 'VpcId', 'ParameterValue': args.vpc_id}],
              'Capabilities': ['CAPABILITY_IAM'],
              'Tags': [{'Key': 'Project', 'Value': 'sf6-review'}]}
    if args.execution_role_arn:
        params['RoleARN'] = args.execution_role_arn
    response = cf.create_change_set(**params)
    print(json.dumps({'change_set_id': response['Id'], 'type': kind,
                      'executed': False, 'next': 'describe-change-set and review before execute'}, indent=2))


if __name__ == '__main__':
    main()
