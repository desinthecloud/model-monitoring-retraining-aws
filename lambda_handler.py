import boto3
import os
from datetime import datetime
 
def handler(event, context):
    sm = boto3.client('sagemaker')
    s3_bucket         = os.environ['S3_BUCKET']
    sns_topic_arn     = os.environ['SNS_TOPIC_ARN']
    processing_role   = os.environ['PROCESSING_ROLE']
    drift_threshold   = float(os.environ.get('DRIFT_THRESHOLD', '0.3'))
    job_name = f"model-monitoring-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}"
 
    sm.create_processing_job(
        ProcessingJobName=job_name,
        RoleArn=processing_role,
        ProcessingResources={
            'ClusterConfig': {
                'InstanceCount': 1,
                'InstanceType': 'ml.t3.medium',
                'VolumeSizeInGB': 20
            }
        },
        AppSpecification={
            'ImageUri': '683313688378.dkr.ecr.us-east-1.amazonaws.com/sagemaker-scikit-learn:1.4-2-cpu-py3',
            'ContainerEntrypoint': [
                'bash', '-c',
                'pip install "evidently==0.4.30" && python3 /opt/ml/processing/code/monitoring/run_monitoring.py "$@"',
                '--'
        ],
        'ContainerArguments': [
            '--s3-bucket',           s3_bucket,
            '--sns-topic-arn',       sns_topic_arn,
            '--drift-threshold',     str(drift_threshold),
            '--processing-role-arn', processing_role 
         ]
        },
        ProcessingInputs=[{
            'InputName': 'code',
            'S3Input': {
                'S3Uri': f's3://{s3_bucket}/monitoring/code/',
                'LocalPath': '/opt/ml/processing/code',
                'S3DataType': 'S3Prefix',
                'S3InputMode': 'File'
            }
        }],
        ProcessingOutputConfig={
            'Outputs': [{
                'OutputName': 'reports',
                'S3Output': {
                    'S3Uri': f's3://{s3_bucket}/monitoring/reports/',
                    'LocalPath': '/opt/ml/processing/output',
                    'S3UploadMode': 'EndOfJob'
                }
            }]
        }
    )
 
    print(f'Processing job launched: {job_name}')
    return {'statusCode': 200, 'body': f'Job launched: {job_name}'}


