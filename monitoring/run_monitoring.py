import argparse
import json
import os
import boto3
import pandas as pd
import numpy as np
from evidently.report import Report
from evidently.metric_preset import DataDriftPreset, TargetDriftPreset
from evidently.metrics import ColumnDriftMetric
 
def load_reference(s3_bucket):
    s3 = boto3.client('s3', region_name='us-east-1')
    local = '/tmp/reference_data.csv'
    s3.download_file(s3_bucket, 'monitoring/reference/reference_data.csv', local)
    return pd.read_csv(local)
 
def load_current_data(s3_bucket):
    """Load captured endpoint data from S3.
    SageMaker data capture stores jsonl files under data-capture/.
    We parse predictions (output) and input text into a DataFrame.
    """
    s3 = boto3.client('s3', region_name='us-east-1')
    paginator = s3.get_paginator('list_objects_v2')
    pages = paginator.paginate(Bucket=s3_bucket, Prefix='data-capture/')
    rows = []
    for page in pages:
        for obj in page.get('Contents', []):
            key = obj['Key']
            if not key.endswith('.jsonl'):
                continue
            body = s3.get_object(Bucket=s3_bucket, Key=key)['Body'].read().decode()
            for line in body.strip().split('\n'):
                if not line:
                    continue
                try:
                    record = json.loads(line)
                    inp = record.get('captureData', {}).get('endpointInput', {})
                    out = record.get('captureData', {}).get('endpointOutput', {})
                    text = inp.get('data', '')
                    label = out.get('data', '').strip()
                    if text and label:
                        rows.append({'text': text, 'label': label})
                except Exception:
                    continue
    if not rows:
        print('No captured data found. Generating synthetic drift data for demo.')
        return generate_synthetic_current()
    return pd.DataFrame(rows)
 
def generate_synthetic_current():
    """
    For portfolio demo purposes: if there is no real captured data,
    generate data with intentional drift so the pipeline can be tested end-to-end.
    """
    np.random.seed(99)
    cats_drifted = ['billing', 'billing', 'billing', 'technical', 'account']
    rows = []
    for _ in range(200):
        cat = np.random.choice(cats_drifted)
        rows.append({'text': f'Issue with {cat} service', 'label': cat})
    return pd.DataFrame(rows)
 
def add_text_features(df):
    """Add numeric features Evidently can measure for feature drift.""",
    df = df.copy()
    df['text_length'] = df['text'].str.len()
    df['word_count']  = df['text'].str.split().str.len()
    df['label_encoded'] = pd.Categorical(df['label']).codes
    return df
 
def run_drift_checks(reference, current):
    ref = add_text_features(reference)
    cur = add_text_features(current)
    report = Report(metrics=[
        DataDriftPreset(),
        ColumnDriftMetric(column_name='label_encoded'),  # prediction drift
        ColumnDriftMetric(column_name='text_length'),    # feature drift
        ColumnDriftMetric(column_name='word_count'),     # feature drift
    ])
    report.run(reference_data=ref, current_data=cur)
    return report
 
def extract_drift_summary(report):
    result = report.as_dict()
    metrics = result.get('metrics', [])
    summary = {
        'dataset_drift_detected': False,
        'prediction_drift': False,
        'feature_drift': {},
        'drift_score': 0.0
    }
    for m in metrics:
        name = m.get('metric', '')
        res  = m.get('result', {})
        if 'DatasetDriftMetric' in name:
            summary['dataset_drift_detected'] = res.get('dataset_drift', False)
            summary['drift_score'] = res.get('share_of_drifted_columns', 0.0)
        if 'ColumnDriftMetric' in name:
            col = res.get('column_name', '')
            drifted = res.get('drift_detected', False)
            if col == 'label_encoded':
                summary['prediction_drift'] = drifted
            else:
                summary['feature_drift'][col] = drifted
    return summary
 
def save_report(report, s3_bucket):
    local = '/tmp/drift_report.html'
    report.save_html(local)
    s3 = boto3.client('s3', region_name='us-east-1')
    from datetime import datetime
    key = f"monitoring/reports/drift_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.html"
    s3.upload_file(local, s3_bucket, key)
    print(f'Report saved to s3://{s3_bucket}/{key}')
    return key
 
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--s3-bucket', required=True)
    parser.add_argument('--sns-topic-arn', required=True)
    parser.add_argument('--drift-threshold', type=float, default=0.3)
    parser.add_argument('--processing-role-arn', required=True)
    args = parser.parse_args()
 
    print('Loading reference data...')
    reference = load_reference(args.s3_bucket)
    print(f'Reference rows: {len(reference)}')
 
    print('Loading current captured data...')
    current = load_current_data(args.s3_bucket)
    print(f'Current rows: {len(current)}')
 
    print('Running Evidently drift checks...')
    report = run_drift_checks(reference, current)
    summary = extract_drift_summary(report)
    print(f'Drift summary: {json.dumps(summary, indent=2)}')
 
    report_key = save_report(report, args.s3_bucket)
 
    sns = boto3.client('sns', region_name='us-east-1')
    drift_detected = (
        summary['prediction_drift'] or
        summary['dataset_drift_detected'] or
        any(summary['feature_drift'].values()) or
        summary['drift_score'] > args.drift_threshold
    )
 
    if drift_detected:
        print(f'Drift detected (score={summary["drift_score"]:.2f}). Triggering retraining...')
        sns.publish(
            TopicArn=args.sns_topic_arn,
            Subject='Model Drift Detected - Retraining Triggered',
            Message=(
                f'Drift detected in support-ticket model.\n'
                f'Drift score: {summary["drift_score"]:.2f}\n'
                f'Prediction drift: {summary["prediction_drift"]}\n'
                f'Feature drift: {summary["feature_drift"]}\n'
                f'Report: s3://{args.s3_bucket}/{report_key}\n'
                f'Retraining job is starting now.'
            )
        )
        # Trigger retraining
        import subprocess
        subprocess.run([
            'python', '/opt/ml/processing/code/retraining/retrain.py',
            '--s3-bucket', args.s3_bucket,
            '--sns-topic-arn', args.sns_topic_arn,
            '--processing-role-arn', args.processing_role_arn
        ], check=True)
    else:
        print(f'No drift detected (score={summary["drift_score"]:.2f}). Model is healthy.')
        sns.publish(
            TopicArn=args.sns_topic_arn,
            Subject='Model Monitoring: No Drift Detected',
            Message=(
                f'Weekly monitoring complete. Model is healthy.\n'
                f'Drift score: {summary["drift_score"]:.2f}\n'
                f'Report: s3://{args.s3_bucket}/{report_key}'
            )
        )
 
if __name__ == '__main__':
    main()


