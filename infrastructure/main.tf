# Arquitetura de Microsserviços para Sistema de Assinatura de Contratos
# Terraform Configuration

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

# =============================================================================
# VARIÁVEIS
# =============================================================================

variable "aws_region" {
  description = "Região AWS"
  type        = string
  default     = "us-east-1"
}

variable "project_name" {
  description = "Nome do projeto"
  type        = string
  default     = "contrato-assinatura"
}

variable "environment" {
  description = "Ambiente (dev, staging, prod)"
  type        = string
  default     = "dev"
}

variable "s3_bucket_name" {
  description = "Nome do bucket S3 para contratos"
  type        = string
  default     = "template-trigger-docusign"
}

variable "manychat_api_key" {
  description = "API Key do ManyChat"
  type        = string
  default     = ""
  sensitive   = true
}

# =============================================================================
# S3 BUCKET PARA CONTRATOS
# =============================================================================

resource "aws_s3_bucket" "contratos" {
  bucket = var.s3_bucket_name

  tags = {
    Name        = "${var.project_name}-contratos"
    Environment = var.environment
    Project     = var.project_name
  }
}

resource "aws_s3_bucket_versioning" "contratos" {
  bucket = aws_s3_bucket.contratos.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "contratos" {
  bucket = aws_s3_bucket.contratos.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

# =============================================================================
# S3 BUCKET PARA RESULTADOS
# =============================================================================

resource "aws_s3_bucket" "resultados" {
  bucket = "${var.project_name}-resultados-${var.environment}"

  tags = {
    Name        = "${var.project_name}-resultados"
    Environment = var.environment
    Project     = var.project_name
  }
}

resource "aws_s3_bucket_versioning" "resultados" {
  bucket = aws_s3_bucket.resultados.id
  versioning_configuration {
    status = "Enabled"
  }
}

# =============================================================================
# SQS QUEUE PARA CONTRATOS
# =============================================================================

resource "aws_sqs_queue" "contrato_queue" {
  name                       = "${var.project_name}-queue-${var.environment}"
  delay_seconds             = 0
  max_message_size          = 262144  # 256KB
  message_retention_seconds = 86400   # 24 horas
  receive_wait_time_seconds = 0
  visibility_timeout_seconds = 300    # 5 minutos

  tags = {
    Name        = "${var.project_name}-queue"
    Environment = var.environment
    Project     = var.project_name
  }
}

# Dead Letter Queue
resource "aws_sqs_queue" "contrato_dlq" {
  name = "${var.project_name}-dlq-${var.environment}"

  tags = {
    Name        = "${var.project_name}-dlq"
    Environment = var.environment
    Project     = var.project_name
  }
}

# =============================================================================
# SNS TOPIC PARA NOTIFICAÇÕES
# =============================================================================

resource "aws_sns_topic" "contrato_notifications" {
  name = "${var.project_name}-notifications-${var.environment}"

  tags = {
    Name        = "${var.project_name}-notifications"
    Environment = var.environment
    Project     = var.project_name
  }
}

# =============================================================================
# IAM ROLE PARA LAMBDA CONTRACT PROCESSOR
# =============================================================================

resource "aws_iam_role" "lambda_contract_processor_role" {
  name = "${var.project_name}-contract-processor-lambda-role-${var.environment}"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
      }
    ]
  })

  tags = {
    Name        = "${var.project_name}-contract-processor-role"
    Environment = var.environment
    Project     = var.project_name
  }
}

# Política IAM para Lambda Contract Processor
resource "aws_iam_role_policy" "lambda_contract_processor_policy" {
  name = "${var.project_name}-contract-processor-policy-${var.environment}"
  role = aws_iam_role.lambda_contract_processor_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = "arn:aws:logs:*:*:*"
      },
      {
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:ListBucket"
        ]
        Resource = [
          aws_s3_bucket.contratos.arn,
          "${aws_s3_bucket.contratos.arn}/*"
        ]
      }
    ]
  })
}

# =============================================================================
# IAM ROLE PARA LAMBDA API
# =============================================================================

resource "aws_iam_role" "lambda_api_role" {
  name = "${var.project_name}-api-lambda-role-${var.environment}"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
      }
    ]
  })

  tags = {
    Name        = "${var.project_name}-api-role"
    Environment = var.environment
    Project     = var.project_name
  }
}

# Política IAM para Lambda API
resource "aws_iam_role_policy" "lambda_api_policy" {
  name = "${var.project_name}-api-policy-${var.environment}"
  role = aws_iam_role.lambda_api_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = "arn:aws:logs:*:*:*"
      },
      {
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:ListBucket"
        ]
        Resource = [
          aws_s3_bucket.contratos.arn,
          "${aws_s3_bucket.contratos.arn}/*",
          aws_s3_bucket.resultados.arn,
          "${aws_s3_bucket.resultados.arn}/*"
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "sqs:SendMessage"
        ]
        Resource = aws_sqs_queue.contrato_queue.arn
      }
    ]
  })
}

# =============================================================================
# IAM ROLE PARA LAMBDA PROCESSADOR
# =============================================================================

resource "aws_iam_role" "lambda_processor_role" {
  name = "${var.project_name}-processor-lambda-role-${var.environment}"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
      }
    ]
  })

  tags = {
    Name        = "${var.project_name}-processor-role"
    Environment = var.environment
    Project     = var.project_name
  }
}

# Política IAM para Lambda Processor
resource "aws_iam_role_policy" "lambda_processor_policy" {
  name = "${var.project_name}-processor-policy-${var.environment}"
  role = aws_iam_role.lambda_processor_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = "arn:aws:logs:*:*:*"
      },
      {
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:PutObject"
        ]
        Resource = [
          aws_s3_bucket.contratos.arn,
          "${aws_s3_bucket.contratos.arn}/*",
          aws_s3_bucket.resultados.arn,
          "${aws_s3_bucket.resultados.arn}/*"
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "sqs:ReceiveMessage",
          "sqs:DeleteMessage",
          "sqs:GetQueueAttributes"
        ]
        Resource = aws_sqs_queue.contrato_queue.arn
      },
      {
        Effect = "Allow"
        Action = [
          "sns:Publish"
        ]
        Resource = aws_sns_topic.contrato_notifications.arn
      }
    ]
  })
}

# =============================================================================
# IAM ROLE PARA LAMBDA WEBHOOK
# =============================================================================

resource "aws_iam_role" "lambda_webhook_role" {
  name = "${var.project_name}-webhook-lambda-role-${var.environment}"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
      }
    ]
  })

  tags = {
    Name        = "${var.project_name}-webhook-role"
    Environment = var.environment
    Project     = var.project_name
  }
}

# Política IAM para Lambda Webhook
resource "aws_iam_role_policy" "lambda_webhook_policy" {
  name = "${var.project_name}-webhook-policy-${var.environment}"
  role = aws_iam_role.lambda_webhook_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = "arn:aws:logs:*:*:*"
      }
    ]
  })
}

# =============================================================================
# LAMBDA FUNCTION - WEBHOOK
# =============================================================================

data "archive_file" "lambda_webhook" {
  type        = "zip"
  source_dir  = "../lambda-webhook"
  output_path = "lambda_webhook.zip"
}

resource "aws_lambda_function" "webhook" {
  filename         = data.archive_file.lambda_webhook.output_path
  function_name    = "${var.project_name}-webhook-${var.environment}"
  role            = aws_iam_role.lambda_webhook_role.arn
  handler         = "lambda_handler.lambda_handler"
  runtime         = "python3.9"
  timeout         = 30
  memory_size     = 256

  environment {
    variables = {
      LOG_LEVEL = "INFO"
    }
  }

  tags = {
    Name        = "${var.project_name}-webhook"
    Environment = var.environment
    Project     = var.project_name
  }
}

# =============================================================================
# API GATEWAY PARA WEBHOOKS DOCUSIGN
# =============================================================================

# Recurso raiz
resource "aws_api_gateway_resource" "webhook_root" {
  rest_api_id = aws_api_gateway_rest_api.docusign_webhook_api.id
  parent_id   = aws_api_gateway_rest_api.docusign_webhook_api.root_resource_id
  path_part   = "webhook"
}

# Método GET para health check
resource "aws_api_gateway_method" "webhook_get" {
  rest_api_id   = aws_api_gateway_rest_api.docusign_webhook_api.id
  resource_id   = aws_api_gateway_rest_api.docusign_webhook_api.root_resource_id
  http_method   = "GET"
  authorization = "NONE"
}

resource "aws_api_gateway_integration" "webhook_get" {
  rest_api_id             = aws_api_gateway_rest_api.docusign_webhook_api.id
  resource_id             = aws_api_gateway_rest_api.docusign_webhook_api.root_resource_id
  http_method             = aws_api_gateway_method.webhook_get.http_method
  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = aws_lambda_function.webhook.invoke_arn
}

resource "aws_api_gateway_method_response" "webhook_get" {
  rest_api_id = aws_api_gateway_rest_api.docusign_webhook_api.id
  resource_id = aws_api_gateway_rest_api.docusign_webhook_api.root_resource_id
  http_method = aws_api_gateway_method.webhook_get.http_method
  status_code = "200"

  response_parameters = {
    "method.response.header.Access-Control-Allow-Origin" = "'*'"
  }
}

# Método POST para webhooks do DocuSign
resource "aws_api_gateway_method" "webhook_post" {
  rest_api_id   = aws_api_gateway_rest_api.docusign_webhook_api.id
  resource_id   = aws_api_gateway_resource.webhook_root.id
  http_method   = "POST"
  authorization = "NONE"
}

resource "aws_api_gateway_integration" "webhook_post" {
  rest_api_id             = aws_api_gateway_rest_api.docusign_webhook_api.id
  resource_id             = aws_api_gateway_resource.webhook_root.id
  http_method             = aws_api_gateway_method.webhook_post.http_method
  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = aws_lambda_function.webhook.invoke_arn
}

resource "aws_api_gateway_method_response" "webhook_post" {
  rest_api_id = aws_api_gateway_rest_api.docusign_webhook_api.id
  resource_id = aws_api_gateway_resource.webhook_root.id
  http_method = aws_api_gateway_method.webhook_post.http_method
  status_code = "200"

  response_parameters = {
    "method.response.header.Access-Control-Allow-Origin" = "'*'"
  }
}

# Deploy da API
resource "aws_api_gateway_deployment" "docusign_webhook_deployment" {
  depends_on = [
    aws_api_gateway_integration.webhook_get,
    aws_api_gateway_integration.webhook_post
  ]

  rest_api_id = aws_api_gateway_rest_api.docusign_webhook_api.id
  stage_name  = var.environment

  lifecycle {
    create_before_destroy = true
  }
}

# Permissão para API Gateway invocar Lambda Webhook
resource "aws_lambda_permission" "allow_api_gateway_invoke_webhook" {
  statement_id  = "AllowAPIGatewayInvokeWebhook"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.webhook.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_api_gateway_rest_api.docusign_webhook_api.execution_arn}/*/*/*"
}

# =============================================================================
# LAMBDA FUNCTION - CONTRACT PROCESSOR
# =============================================================================

data "archive_file" "lambda_contract_processor" {
  type        = "zip"
  source_dir  = "../lambda-contract-processor"
  output_path = "lambda_contract_processor.zip"
}

resource "aws_lambda_function" "contract_processor" {
  filename         = data.archive_file.lambda_contract_processor.output_path
  function_name    = "${var.project_name}-contract-processor-${var.environment}"
  role            = aws_iam_role.lambda_contract_processor_role.arn
  handler         = "lambda_handler.lambda_handler"
  runtime         = "python3.9"
  timeout         = 300
  memory_size     = 512

  environment {
    variables = {
      LOG_LEVEL = "INFO"
      RETURN_URL = "https://www.docusign.com"
    }
  }

  tags = {
    Name        = "${var.project_name}-contract-processor"
    Environment = var.environment
    Project     = var.project_name
  }
}

# =============================================================================
# S3 EVENT NOTIFICATION PARA CONTRACT PROCESSOR LAMBDA
# =============================================================================

resource "aws_s3_bucket_notification" "contract_upload" {
  bucket = aws_s3_bucket.contratos.id

  lambda_function {
    lambda_function_arn = aws_lambda_function.contract_processor.arn
    events              = ["s3:ObjectCreated:*"]
    filter_prefix       = "contratos-gerados/"
    filter_suffix       = ".pdf"
  }

  # Ignorar pasta audit se existir
  lambda_function {
    lambda_function_arn = aws_lambda_function.contract_processor.arn
    events              = ["s3:ObjectCreated:*"]
    filter_prefix       = "contratos-gerados/"
    filter_suffix       = ".pdf"
  }
}

# Permissão para S3 invocar Lambda Contract Processor
resource "aws_lambda_permission" "allow_s3_invoke_contract_processor" {
  statement_id  = "AllowS3InvokeContractProcessor"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.contract_processor.function_name
  principal     = "s3.amazonaws.com"
  source_arn    = aws_s3_bucket.contratos.arn
}


# =============================================================================
# REDSHIFT DEAD LETTER QUEUE
# =============================================================================

resource "aws_sqs_queue_redrive_policy" "contrato_queue" {
  queue_url = aws_sqs_queue.contrato_queue.id

  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.contrato_dlq.arn
    maxReceiveCount     = 3
  })
}

resource "aws_sqs_queue_redrive_allow_policy" "contrato_dlq" {
  queue_url = aws_sqs_queue.contrato_dlq.id

  redrive_allow_policy = jsonencode({
    redrivePermission = "byQueue",
    sourceQueueArns   = [aws_sqs_queue.contrato_queue.arn]
  })
}

# =============================================================================
# OUTPUTS
# =============================================================================

output "s3_bucket_contratos" {
  description = "Bucket S3 para contratos"
  value       = aws_s3_bucket.contratos.bucket
}

output "s3_bucket_resultados" {
  description = "Bucket S3 para resultados"
  value       = aws_s3_bucket.resultados.bucket
}

output "lambda_contract_processor_arn" {
  description = "ARN da Lambda Contract Processor"
  value       = aws_lambda_function.contract_processor.arn
}

output "lambda_webhook_arn" {
  description = "ARN da Lambda Webhook"
  value       = aws_lambda_function.webhook.arn
}

output "api_gateway_webhook_url" {
  description = "URL da API Gateway para webhooks"
  value       = aws_api_gateway_deployment.docusign_webhook_deployment.invoke_url
}

output "webhook_endpoint" {
  description = "Endpoint completo para webhooks do DocuSign"
  value       = "${aws_api_gateway_deployment.docusign_webhook_deployment.invoke_url}/webhook"
}

output "health_check_endpoint" {
  description = "Endpoint de health check"
  value       = aws_api_gateway_deployment.docusign_webhook_deployment.invoke_url
}
