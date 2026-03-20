variable "aws_region" {
  default = "us-east-1"
}
 
variable "alert_email" {
  description = "desinthecloud@gmail.com"
  type        = string
}
 
variable "s3_bucket" {
  description = "support-ticket-ml-build-3.17"
  type        = string
}
 
variable "lambda_function_name" {
  default = "monitoring-trigger"
}

