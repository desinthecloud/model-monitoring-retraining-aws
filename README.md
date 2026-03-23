# Model Monitoring & Automated Retraining Pipeline

An automated MLOps pipeline that extends the [Support Ticket Triage](https://github.com/desinthecloud/support-ticket-ml) system with drift detection, alerting, and automated retraining on AWS SageMaker.

## Overview

A deployed model is not a finished model. This pipeline monitors the Support Ticket Triage endpoint for data drift, triggers retraining when drift is detected, and redeploys the updated model automatically — no manual intervention required.

## Architecture

```
EventBridge (weekly cron)
    │
    ▼
Lambda (monitoring-trigger)
    │
    ▼
SageMaker Processing Job
    │
    ├── Evidently Drift Detection
    │       ├── Dataset drift
    │       ├── Prediction drift
    │       └── Feature drift (text_length, word_count)
    │
    ├── Drift Report → S3
    │
    └── SNS Alert
            │
            ▼ (if drift detected)
    SageMaker Training Job (retraining)
            │
            ▼
    Validate & Deploy → SageMaker Endpoint
```

## Stack

- **AWS SageMaker** — processing jobs and training jobs
- **AWS Lambda** — orchestration layer
- **AWS EventBridge** — weekly scheduled trigger
- **AWS SNS** — drift alerts via email
- **AWS S3** — reference data, captured endpoint data, drift reports, model artifacts
- **Evidently** — drift detection
- **Terraform** — infrastructure as code
- **Python 3.10**

## Project Structure

```
model-monitoring-retraining-aws/
├── data/
│   └── generate_reference.py       # Generates reference dataset and uploads to S3
├── monitoring/
│   └── run_monitoring.py           # Evidently drift detection script
├── retraining/
│   ├── retrain.py                  # SageMaker Training job launcher
│   └── validate_and_deploy.py      # Model validation and endpoint deployment
├── infrastructure/
│   ├── main.tf                     # Lambda, EventBridge, SNS, IAM resources
│   └── variables.tf                # Input variables
├── enable_capture.py               # Enables SageMaker data capture on endpoint
├── lambda_handler.py               # Lambda function handler
└── requirements.txt
```

## Prerequisites

- AWS CLI configured with appropriate permissions
- Terraform installed
- Python 3.10+
- Existing SageMaker endpoint from the Support Ticket Triage project
- S3 bucket with training data and reference data

## Setup

**1. Clone the repo**
```bash
git clone https://github.com/desinthecloud/model-monitoring-retraining-aws.git
cd model-monitoring-retraining-aws
```

**2. Install dependencies**
```bash
pip install -r requirements.txt
```

**3. Generate reference dataset**
```bash
S3_BUCKET=your-bucket-name python data/generate_reference.py
```

**4. Enable data capture on your endpoint**
```bash
python enable_capture.py
```

**5. Deploy infrastructure**
```bash
cd infrastructure
terraform init
terraform apply \
  -var='alert_email=your@email.com' \
  -var='s3_bucket=your-bucket-name'
```

**6. Deploy Lambda function**
```bash
cd ..
zip lambda_handler.zip lambda_handler.py
aws lambda update-function-code \
  --function-name monitoring-trigger \
  --zip-file fileb://lambda_handler.zip
```

**7. Upload monitoring and retraining scripts to S3**
```bash
aws s3 cp monitoring/ s3://your-bucket/monitoring/code/monitoring/ --recursive
aws s3 cp retraining/ s3://your-bucket/monitoring/code/retraining/ --recursive
```

## How It Works

**Drift Detection**

The monitoring script compares recent endpoint traffic against a reference dataset using Evidently. It checks for dataset drift, prediction drift on the label column, and feature drift on text length and word count. If the drift score exceeds the configured threshold (default 0.3), retraining is triggered.

**Retraining**

The retraining job uses the same scikit-learn container and training script as the original model. The retrained model artifact is saved to a separate S3 prefix.

**Validation and Deployment**

After training completes, the validation script evaluates the new model against a held-out test set. If it passes, the model is deployed to the existing endpoint with zero downtime.

**Alerting**

SNS publishes an email alert on every monitoring run — whether drift was detected or the model is healthy. The full drift report is saved as an HTML file in S3.

## Infrastructure Teardown

```bash
cd infrastructure
terraform destroy \
  -var='alert_email=your@email.com' \
  -var='s3_bucket=your-bucket-name'

aws sagemaker delete-endpoint --endpoint-name your-endpoint-name
aws s3 rm s3://your-bucket-name --recursive
aws s3 rb s3://your-bucket-name
```

## Related Projects

- [Support Ticket Triage](https://github.com/desinthecloud/support-ticket-ml) — the base ML system this pipeline monitors and retrains

## Author

**Des (Desiree' Weston)**
[desinthecloud@gmail.com](https://github.com/desinthecloud)
