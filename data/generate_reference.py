import pandas as pd
import numpy as np
import boto3
import json
import os
 
np.random.seed(42)
 
CATEGORIES = ['billing', 'technical', 'account', 'shipping', 'general']
 
TEMPLATES = {
    'billing':   'Thank you for reaching out about your billing inquiry...',
    'technical': 'I understand you are experiencing a technical issue...',
    'account':   'I can help you with your account...',
    'shipping':  'I can see your shipping concern...',
    'general':   'Thank you for contacting support...'
}
 
SAMPLES = {
    'billing':   ['I was charged twice', 'Unexpected charge on my statement',
                  'Wrong amount billed', 'Invoice shows wrong total'],
    'technical': ['App keeps crashing', 'Cannot load the page',
                  'Feature not working', 'Error message on screen'],
    'account':   ['Cannot log in', 'Forgot my password',
                  'Account locked out', 'Cannot access my profile'],
    'shipping':  ['Order not arrived', 'Wrong item delivered',
                  'Package damaged', 'Tracking not updating'],
    'general':   ['General question', 'Need information',
                  'How do I use this', 'Looking for help']
}
 
def generate_reference(n=500):
    rows = []
    for _ in range(n):
        cat = np.random.choice(CATEGORIES)
        base = np.random.choice(SAMPLES[cat])
        suffix = np.random.choice([' please help', ' urgent', '', ' asap', ''])
        rows.append({'text': base + suffix, 'label': cat})
    return pd.DataFrame(rows)
 
if __name__ == '__main__':
    bucket = os.environ.get('S3_BUCKET', 'support-ticket-ml-build-3.17')
    df = generate_reference(500)
    local_path = '/tmp/reference_data.csv'
    df.to_csv(local_path, index=False)
    print(f'Generated {len(df)} reference rows')
    print(df['label'].value_counts())
    s3 = boto3.client('s3')
    s3.upload_file(local_path, bucket, 'monitoring/reference/reference_data.csv')
    print(f'Uploaded to s3://{bucket}/monitoring/reference/reference_data.csv')


