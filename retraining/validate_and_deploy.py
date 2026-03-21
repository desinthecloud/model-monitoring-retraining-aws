import argparse
import boto3
import tarfile
import joblib
import os
import json
import numpy as np
import pandas as pd
from sklearn.metrics import accuracy_score, f1_score
from datetime import datetime
 
ACCURACY_THRESHOLD = 0.80
F1_THRESHOLD       = 0.78
 
CATEGORIES = ['billing', 'technical', 'account', 'shipping', 'general']
 
VALIDATION_SAMPLES = [
    ('My invoice shows the wrong amount', 'billing'),
    ('App crashes every time I open it', 'technical'),
    ('I cannot log into my account', 'account'),
    ('My package has not arrived', 'shipping'),
    ('I have a general question', 'general'),
    ('Charged twice this month', 'billing'),
    ('Error code appears on screen', 'technical'),
    ('Account is locked', 'account'),
    ('Wrong item was delivered', 'shipping'),
    ('How does this feature work', 'general'),
]
 
def download_model(model_artifact, local_dir='/tmp/model'):
    os.makedirs(local_dir, exist_ok=True)
    s3 = boto3.client('s3', region_name='us-east-1')
    bucket = model_artifact.split('/')[2]
    key    = '/'.join(model_artifact.split('/')[3:])
    local_tar = os.path.join(local_dir, 'model.tar.gz')
    s3.download_file(bucket, key, local_tar)
    with tarfile.open(local_tar, 'r:gz') as tar:
        tar.extractall(local_dir)
    return local_dir
 
def evaluate_model(model_dir):
    model_path = os.path.join(model_dir, 'model.joblib')
    model = joblib.load(model_path)
    texts  = [s[0] for s in VALIDATION_SAMPLES]
    labels = [s[1] for s in VALIDATION_SAMPLES]
    preds  = model.predict(texts)
    acc    = accuracy_score(labels, preds)
    f1     = f1_score(labels, preds, average='weighted', zero_division=0)
    return acc, f1
 
def deploy_model(model_artifact, processing_role, sm):
    model_name = f"support-ticket-retrained-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
    sm.create_model(
        ModelName=model_name,
        PrimaryContainer={
            'Image': '683313688378.dkr.ecr.us-east-1.amazonaws.com/sagemaker-scikit-learn:1.2-1-cpu-py3',
            'ModelDataUrl': model_artifact
        },
        ExecutionRoleArn=processing_role
    )
    config_name = f"{model_name}-config"
    sm.create_endpoint_config(
        EndpointConfigName=config_name,
        ProductionVariants=[{
            'VariantName': 'AllTraffic',
            'ModelName': model_name,
            'InitialInstanceCount': 1,
            'InstanceType': 'ml.t2.medium'
        }]
    )
    sm.update_endpoint(
        EndpointName='support-ticket-endpoint',
        EndpointConfigName=config_name
    )
    return model_name
 
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--s3-bucket', required=True)
    parser.add_argument('--sns-topic-arn', required=True)
    parser.add_argument('--model-artifact', required=True)
    parser.add_argument('--processing-role-arn', required=True)
    args = parser.parse_args()
 
    sns = boto3.client('sns', region_name='us-east-1')
    sm  = boto3.client('sagemaker', region_name='us-east-1')
 
    print('Downloading retrained model for evaluation...')
    model_dir = download_model(args.model_artifact)
 
    print('Evaluating retrained model...')
    acc, f1 = evaluate_model(model_dir)
    print(f'Accuracy: {acc:.4f}  F1: {f1:.4f}')
    print(f'Thresholds - Accuracy: {ACCURACY_THRESHOLD}  F1: {F1_THRESHOLD}')
 
    if acc >= ACCURACY_THRESHOLD and f1 >= F1_THRESHOLD:
        print('Model passed validation. Deploying...')
        model_name = deploy_model(args.model_artifact, args.processing_role_arn, sm)
        sns.publish(
            TopicArn=args.sns_topic_arn,
            Subject='Retrained Model Deployed Successfully',
            Message=(
                f'The retrained model passed validation and has been deployed.\n'
                f'Model name: {model_name}\n'
                f'Accuracy: {acc:.4f}  (threshold: {ACCURACY_THRESHOLD})\n'
                f'F1 score: {f1:.4f}  (threshold: {F1_THRESHOLD})'
            )
        )
    else:
        print('Model failed validation. Keeping current deployed model.')
        sns.publish(
            TopicArn=args.sns_topic_arn,
            Subject='Retrained Model Rejected - Below Threshold',
            Message=(
                f'The retrained model did not meet validation thresholds.\n'
                f'Accuracy: {acc:.4f}  (threshold: {ACCURACY_THRESHOLD})\n'
                f'F1 score: {f1:.4f}  (threshold: {F1_THRESHOLD})\n'
                f'Current deployed model remains unchanged.'
            )
        )
 
if __name__ == '__main__':
    main()


