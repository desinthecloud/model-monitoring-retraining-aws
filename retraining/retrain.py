import argparse
import boto3
import os
import json
from datetime import datetime
 
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--s3-bucket', required=True)
    parser.add_argument('--sns-topic-arn', required=True)
    parser.add_argument('--processing-role-arn', required=True)
    args = parser.parse_args()
 
    sm = boto3.client('sagemaker', region_name='us-east-1')
    job_name = f"retrain-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}"
    output_path = f's3://{args.s3_bucket}/retrained-models/'
 
    print(f'Starting retraining job: {job_name}')
 
    sm.create_training_job(
        TrainingJobName=job_name,
        RoleArn=args.processing_role_arn,
        AlgorithmSpecification={
            'TrainingImage': '683313688378.dkr.ecr.us-east-1.amazonaws.com/sagemaker-scikit-learn:1.2-1-cpu-py3',
            'TrainingInputMode': 'File',
        },
        InputDataConfig=[{
            'ChannelName': 'train',
            'DataSource': {
                'S3DataSource': {
                    'S3DataType': 'S3Prefix',
                    'S3Uri': f's3://{args.s3_bucket}/data/',
                    'S3DataDistributionType': 'FullyReplicated'
                }
            }
        }],
        OutputDataConfig={
            'S3OutputPath': output_path
        },
        ResourceConfig={
            'InstanceType': 'ml.m5.large',
            'InstanceCount': 1,
            'VolumeSizeInGB': 20
        },
        StoppingCondition={'MaxRuntimeInSeconds': 3600},
        HyperParameters={
            'sagemaker_program': 'train.py',
            'sagemaker_submit_directory': f's3://{args.s3_bucket}/source/sourcedir.tar.gz',
            'sagemaker_region': 'us-east-1',
            'sagemaker_container_log_level': '20' 

        }
    )
 
    # Wait for training to complete
    print('Waiting for training job to complete...')
    waiter = sm.get_waiter('training_job_completed_or_stopped')
    waiter.wait(TrainingJobName=job_name)
 
    # Check final status
    response = sm.describe_training_job(TrainingJobName=job_name)
    status = response['TrainingJobStatus']
    print(f'Training job {job_name} finished with status: {status}')
 
    if status == 'Completed':
        model_artifact = response['ModelArtifacts']['S3ModelArtifacts']
        print(f'Model artifact: {model_artifact}')
        # Pass artifact path to validation script
        import subprocess
        subprocess.run([
            'python', '/opt/ml/processing/code/retraining/validate_and_deploy.py',
            '--s3-bucket', args.s3_bucket,
            '--sns-topic-arn', args.sns_topic_arn,
            '--model-artifact', model_artifact,
            '--processing-role-arn', args.processing_role_arn
        ], check=True)
    else:
        sns = boto3.client('sns', region_name='us-east-1')
        sns.publish(
            TopicArn=args.sns_topic_arn,
            Subject='Retraining Job Failed',
            Message=f'Training job {job_name} failed with status {status}. No deployment made.'
        )
 
if __name__ == '__main__':
    main()


