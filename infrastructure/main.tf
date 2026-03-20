provider "aws" {
  region = var.aws_region
}
 
# SNS topic for drift and retraining alerts
resource "aws_sns_topic" "monitoring_alerts" {
  name = "model-monitoring-alerts"
}
 
resource "aws_sns_topic_subscription" "email_alert" {
  topic_arn = aws_sns_topic.monitoring_alerts.arn
  protocol  = "email"
  endpoint  = var.alert_email
}
 
# IAM role for SageMaker Processing job
resource "aws_iam_role" "processing_role" {
  name = "sagemaker-monitoring-role"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "sagemaker.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}
 
resource "aws_iam_role_policy_attachment" "sagemaker_full" {
  role       = aws_iam_role.processing_role.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSageMakerFullAccess"
}
 
resource "aws_iam_role_policy_attachment" "s3_full" {
  role       = aws_iam_role.processing_role.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonS3FullAccess"
}
 
# IAM role for Lambda
resource "aws_iam_role" "lambda_role" {
  name = "monitoring-lambda-role"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "lambda.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}
 
resource "aws_iam_role_policy_attachment" "lambda_sagemaker" {
  role       = aws_iam_role.lambda_role.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSageMakerFullAccess"
}
 
resource "aws_iam_role_policy_attachment" "lambda_logs" {
  role       = aws_iam_role.lambda_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}
 
resource "aws_iam_role_policy_attachment" "lambda_sns" {
  role       = aws_iam_role.lambda_role.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSNSFullAccess"
}
 
# Placeholder Lambda (you will zip and upload the real one in Phase 6)
resource "aws_lambda_function" "monitoring_trigger" {
  function_name = var.lambda_function_name
  role          = aws_iam_role.lambda_role.arn
  runtime       = "python3.11"
  handler       = "lambda_handler.handler"
  filename      = "lambda_placeholder.zip"
  timeout       = 300
  environment {
    variables = {
      S3_BUCKET       = var.s3_bucket
      SNS_TOPIC_ARN   = aws_sns_topic.monitoring_alerts.arn
      PROCESSING_ROLE = aws_iam_role.processing_role.arn
    }
  }
}
 
# EventBridge rule - runs every Monday at 8am UTC
resource "aws_cloudwatch_event_rule" "weekly_monitoring" {
  name                = "weekly-model-monitoring"
  schedule_expression = "cron(0 8 ? * MON *)"
}
 
resource "aws_cloudwatch_event_target" "trigger_lambda" {
  rule      = aws_cloudwatch_event_rule.weekly_monitoring.name
  target_id = "MonitoringLambda"
  arn       = aws_lambda_function.monitoring_trigger.arn
}
 
resource "aws_lambda_permission" "allow_eventbridge" {
  statement_id  = "AllowExecutionFromEventBridge"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.monitoring_trigger.function_name

  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.weekly_monitoring.arn
}
 
output "sns_topic_arn" {
  value = aws_sns_topic.monitoring_alerts.arn
}
 
output "processing_role_arn" {
  value = aws_iam_role.processing_role.arn
}


