terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

# ── Variables ─────────────────────────────────────────────────────────────────

variable "aws_region"    { default = "us-east-1" }
variable "project_name"  { default = "bedrock-rag-app" }
variable "supabase_url"  { sensitive = true }
variable "supabase_key"  { sensitive = true }

data "aws_caller_identity" "current" {}

# ── S3 Bucket — document storage ──────────────────────────────────────────────

resource "aws_s3_bucket" "documents" {
  bucket = "${var.project_name}-docs-${data.aws_caller_identity.current.account_id}"
  tags   = { Project = var.project_name, Purpose = "Financial document storage" }
}

resource "aws_s3_bucket_versioning" "documents" {
  bucket = aws_s3_bucket.documents.id
  versioning_configuration { status = "Enabled" }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "documents" {
  bucket = aws_s3_bucket.documents.id
  rule {
    apply_server_side_encryption_by_default { sse_algorithm = "AES256" }
  }
}

resource "aws_s3_bucket_public_access_block" "documents" {
  bucket                  = aws_s3_bucket.documents.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# ── IAM — Lambda execution role ───────────────────────────────────────────────

resource "aws_iam_role" "lambda_role" {
  name = "${var.project_name}-lambda-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action    = "sts:AssumeRole"
      Effect    = "Allow"
      Principal = { Service = "lambda.amazonaws.com" }
    }]
  })
}

resource "aws_iam_policy" "lambda_policy" {
  name = "${var.project_name}-lambda-policy"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        # AWS Bedrock — Titan Embeddings + Claude 3 Haiku
        Sid    = "BedrockAccess"
        Effect = "Allow"
        Action = [
          "bedrock:InvokeModel",
          "bedrock:InvokeModelWithResponseStream"
        ]
        Resource = [
          "arn:aws:bedrock:${var.aws_region}::foundation-model/amazon.titan-embed-text-v2:0",
          "arn:aws:bedrock:${var.aws_region}::foundation-model/anthropic.claude-3-haiku-20240307-v1:0"
        ]
      },
      {
        # S3 — read documents uploaded by users
        Sid    = "S3Access"
        Effect = "Allow"
        Action = ["s3:GetObject", "s3:PutObject", "s3:ListBucket"]
        Resource = [
          aws_s3_bucket.documents.arn,
          "${aws_s3_bucket.documents.arn}/*"
        ]
      },
      {
        # CloudWatch — Lambda logs
        Sid    = "CloudWatchLogs"
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = "arn:aws:logs:${var.aws_region}:${data.aws_caller_identity.current.account_id}:*"
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "lambda_policy" {
  role       = aws_iam_role.lambda_role.name
  policy_arn = aws_iam_policy.lambda_policy.arn
}

# ── Lambda — document ingestion ───────────────────────────────────────────────

resource "aws_lambda_function" "ingest" {
  filename      = "../lambda.zip"
  function_name = "${var.project_name}-ingest"
  role          = aws_iam_role.lambda_role.arn
  handler       = "ingest.handler"
  runtime       = "python3.11"
  timeout       = 300       # 5 minutes — large documents
  memory_size   = 512       # Titan embedding model needs headroom

  environment {
    variables = {
      AWS_REGION   = var.aws_region
      SUPABASE_URL = var.supabase_url
      SUPABASE_KEY = var.supabase_key
    }
  }

  tags = { Project = var.project_name }
}

# ── S3 → Lambda trigger ───────────────────────────────────────────────────────

resource "aws_lambda_permission" "s3_trigger" {
  statement_id  = "AllowS3Invoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.ingest.function_name
  principal     = "s3.amazonaws.com"
  source_arn    = aws_s3_bucket.documents.arn
}

resource "aws_s3_bucket_notification" "trigger" {
  bucket = aws_s3_bucket.documents.id

  lambda_function {
    lambda_function_arn = aws_lambda_function.ingest.arn
    events              = ["s3:ObjectCreated:*"]
    filter_prefix       = "documents/"
  }

  depends_on = [aws_lambda_permission.s3_trigger]
}

# ── CloudWatch — Lambda monitoring ────────────────────────────────────────────

resource "aws_cloudwatch_log_group" "lambda" {
  name              = "/aws/lambda/${var.project_name}-ingest"
  retention_in_days = 7
}

resource "aws_cloudwatch_metric_alarm" "lambda_errors" {
  alarm_name          = "${var.project_name}-lambda-errors"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "Errors"
  namespace           = "AWS/Lambda"
  period              = 300
  statistic           = "Sum"
  threshold           = 3

  dimensions = {
    FunctionName = aws_lambda_function.ingest.function_name
  }

  alarm_description = "Lambda errors > 3 in 5 minutes — document ingestion failing"
}

# ── Outputs ───────────────────────────────────────────────────────────────────

output "s3_bucket_name" {
  value       = aws_s3_bucket.documents.bucket
  description = "S3 bucket for financial document uploads"
}

output "lambda_function_name" {
  value       = aws_lambda_function.ingest.function_name
  description = "Lambda function for document ingestion"
}

output "lambda_arn" {
  value = aws_lambda_function.ingest.arn
}
