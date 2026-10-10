"""Generate the foundation template; no AWS calls."""
import json
from pathlib import Path


def ref(name):
    return {'Ref': name}


def sub(value):
    return {'Fn::Sub': value}


def arn(name):
    return {'Fn::GetAtt': [name, 'Arn']}


def resource(kind, properties, retain=False):
    out = {'Type': kind, 'Properties': properties}
    if retain:
        out.update(DeletionPolicy='Retain', UpdateReplacePolicy='Retain')
    return out


def build():
    assume = lambda service: {'Version': '2012-10-17', 'Statement': [{
        'Effect': 'Allow', 'Principal': {'Service': service}, 'Action': 'sts:AssumeRole'}]}
    resources = {}
    resources['DataBucket'] = resource('AWS::S3::Bucket', {
        'BucketName': sub('sf6-review-${AWS::AccountId}-${AWS::Region}'),
        'PublicAccessBlockConfiguration': dict(BlockPublicAcls=True, IgnorePublicAcls=True,
                                              BlockPublicPolicy=True, RestrictPublicBuckets=True),
        'OwnershipControls': {'Rules': [{'ObjectOwnership': 'BucketOwnerEnforced'}]},
        'BucketEncryption': {'ServerSideEncryptionConfiguration': [
            {'ServerSideEncryptionByDefault': {'SSEAlgorithm': 'AES256'}}]},
        'VersioningConfiguration': {'Status': 'Enabled'},
        'LifecycleConfiguration': {'Rules': [
            {'Id': prefix, 'Prefix': prefix + '/', 'Status': 'Enabled',
             'ExpirationInDays': days, 'NoncurrentVersionExpiration': {'NoncurrentDays': days},
             'AbortIncompleteMultipartUpload': {'DaysAfterInitiation': 1}}
            for prefix, days in [('raw', 7), ('evidence', 30), ('reports', 365), ('checkpoints', 90)]]},
        'Tags': [{'Key': 'Project', 'Value': 'sf6-review'}]}, True)
    resources['BucketPolicy'] = resource('AWS::S3::BucketPolicy', {
        'Bucket': ref('DataBucket'), 'PolicyDocument': {'Version': '2012-10-17', 'Statement': [{
            'Effect': 'Deny', 'Principal': '*', 'Action': 's3:*',
            'Resource': [arn('DataBucket'), sub('${DataBucket.Arn}/*')],
            'Condition': {'Bool': {'aws:SecureTransport': 'false'}}}]}})
    resources['JobsTable'] = resource('AWS::DynamoDB::Table', {
        'TableName': 'sf6-review-jobs', 'BillingMode': 'PAY_PER_REQUEST',
        'AttributeDefinitions': [{'AttributeName': 'pk', 'AttributeType': 'S'},
                                 {'AttributeName': 'sk', 'AttributeType': 'S'}],
        'KeySchema': [{'AttributeName': 'pk', 'KeyType': 'HASH'},
                      {'AttributeName': 'sk', 'KeyType': 'RANGE'}],
        'TimeToLiveSpecification': {'AttributeName': 'expires_at', 'Enabled': True},
        'PointInTimeRecoverySpecification': {'PointInTimeRecoveryEnabled': True},
        'SSESpecification': {'SSEEnabled': True},
        'Tags': [{'Key': 'Project', 'Value': 'sf6-review'}]}, True)
    resources['ImageRepository'] = resource('AWS::ECR::Repository', {
        'RepositoryName': 'sf6-review-worker', 'ImageTagMutability': 'IMMUTABLE',
        'ImageScanningConfiguration': {'ScanOnPush': True},
        'EncryptionConfiguration': {'EncryptionType': 'AES256'},
        'LifecyclePolicy': {'LifecyclePolicyText': json.dumps({'rules': [{
            'rulePriority': 1, 'description': 'Remove old untagged images only',
            'selection': {'tagStatus': 'untagged', 'countType': 'sinceImagePushed',
                          'countUnit': 'days', 'countNumber': 7},
            'action': {'type': 'expire'}}]})}}, True)
    resources['Cluster'] = resource('AWS::ECS::Cluster', {'ClusterName': 'sf6-review',
        'Tags': [{'Key': 'Project', 'Value': 'sf6-review'}]})
    resources['WorkerLogs'] = resource('AWS::Logs::LogGroup', {
        'LogGroupName': '/sf6-review/worker', 'RetentionInDays': 14}, True)
    resources['WorkerSecurityGroup'] = resource('AWS::EC2::SecurityGroup', {
        'GroupDescription': 'SF6 outbound-only worker; no ingress', 'VpcId': ref('VpcId'),
        'SecurityGroupEgress': [{'IpProtocol': '-1', 'CidrIp': '0.0.0.0/0'}],
        'Tags': [{'Key': 'Project', 'Value': 'sf6-review'}]})
    resources['TaskRole'] = resource('AWS::IAM::Role', {
        'AssumeRolePolicyDocument': assume('ecs-tasks.amazonaws.com'),
        'Policies': [{'PolicyName': 'Sf6ReviewData', 'PolicyDocument': {
            'Version': '2012-10-17', 'Statement': [
                {'Effect': 'Allow', 'Action': ['s3:GetObject', 's3:PutObject', 's3:DeleteObject'],
                 'Resource': sub('${DataBucket.Arn}/*')},
                {'Effect': 'Allow', 'Action': ['s3:ListBucket'], 'Resource': arn('DataBucket')},
                {'Effect': 'Allow', 'Action': ['dynamodb:GetItem', 'dynamodb:PutItem',
                 'dynamodb:UpdateItem', 'dynamodb:Query', 'dynamodb:BatchWriteItem'],
                 'Resource': arn('JobsTable')},
                {'Effect': 'Allow', 'Action': ['ssm:GetParameter', 'ssm:GetParameters'],
                 'Resource': sub('arn:${AWS::Partition}:ssm:${AWS::Region}:${AWS::AccountId}:parameter/sf6-review/*')}
            ]}}], 'Tags': [{'Key': 'Project', 'Value': 'sf6-review'}]})
    resources['ExecutionRole'] = resource('AWS::IAM::Role', {
        'AssumeRolePolicyDocument': assume('ecs-tasks.amazonaws.com'),
        'Policies': [{'PolicyName': 'Sf6ReviewImageAndLogs', 'PolicyDocument': {
            'Version': '2012-10-17', 'Statement': [
                {'Effect': 'Allow', 'Action': ['ecr:GetAuthorizationToken'], 'Resource': '*'},
                {'Effect': 'Allow', 'Action': ['ecr:BatchGetImage', 'ecr:GetDownloadUrlForLayer',
                                              'ecr:BatchCheckLayerAvailability'],
                 'Resource': arn('ImageRepository')},
                {'Effect': 'Allow', 'Action': ['logs:CreateLogStream', 'logs:PutLogEvents'],
                 'Resource': {'Fn::GetAtt': ['WorkerLogs', 'Arn']}}
            ]}}], 'Tags': [{'Key': 'Project', 'Value': 'sf6-review'}]})
    return {'AWSTemplateFormatVersion': '2010-09-09',
        'Description': 'SF6 Review foundation only. No worker tasks or analysis deployed.',
        'Parameters': {'VpcId': {'Type': 'AWS::EC2::VPC::Id',
                                  'Description': 'Existing VPC; no VPC is created'}},
        'Resources': resources,
        'Outputs': {'DataBucket': {'Value': ref('DataBucket')},
                    'JobsTable': {'Value': ref('JobsTable')},
                    'RepositoryUri': {'Value': {'Fn::GetAtt': ['ImageRepository', 'RepositoryUri']}},
                    'ClusterArn': {'Value': arn('Cluster')},
                    'WorkerSecurityGroup': {'Value': ref('WorkerSecurityGroup')},
                    'TaskRoleArn': {'Value': arn('TaskRole')},
                    'ExecutionRoleArn': {'Value': arn('ExecutionRole')}}}


if __name__ == '__main__':
    Path(__file__).with_name('foundation.json').write_text(json.dumps(build(), indent=2) + '\n', encoding='utf-8')
