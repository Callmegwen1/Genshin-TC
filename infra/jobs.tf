# ------------------------------------------------------------------------------------------------------------------
# Asynchronous jobs: SQS lanes, DynamoDB job records, S3 result documents.
#
#   light lane (enabled):  gtc-light-queue -> gtc-light-dlq   TEAM_EVALUATION, TEAM_VARIANT (~100 s each on 1 vCPU)
#   heavy lane (disabled): gtc-heavy-queue -> gtc-heavy-dlq   future ACCOUNT_ANALYSIS (hours); no producer, no consumer
#
# Messages carry only {job_id, job_type, v}; inputs live in DynamoDB, results in S3.
# Long jobs: the worker extends a message's visibility every heartbeat (ChangeMessageVisibility) instead of relying on
# one huge static timeout, so a crashed worker's job reappears within one visibility window. SQS caps a message's
# total invisibility at 12 hours after receipt; the worker stops extending at 11.5 h (documented limit).
# ------------------------------------------------------------------------------------------------------------------

resource "aws_sqs_queue" "light_dlq" {
  name                      = "${local.name}-light-dlq"
  message_retention_seconds = 1209600 # 14 days to investigate
  sqs_managed_sse_enabled   = true
}

resource "aws_sqs_queue" "light" {
  name                       = "${local.name}-light-queue"
  visibility_timeout_seconds = var.light_visibility_seconds # the worker's lease; extended by heartbeat while running
  receive_wait_time_seconds  = 20                           # long polling: fewer empty receives
  message_retention_seconds  = 345600                       # 4 days: jobs wait while workers are scaled to zero
  sqs_managed_sse_enabled    = true
  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.light_dlq.arn
    maxReceiveCount     = var.max_receive_count
  })
}

resource "aws_sqs_queue_redrive_allow_policy" "light_dlq" {
  queue_url = aws_sqs_queue.light_dlq.id
  redrive_allow_policy = jsonencode({
    redrivePermission = "byQueue"
    sourceQueueArns   = [aws_sqs_queue.light.arn]
  })
}

resource "aws_sqs_queue" "heavy_dlq" {
  name                      = "${local.name}-heavy-dlq"
  message_retention_seconds = 1209600
  sqs_managed_sse_enabled   = true
}

resource "aws_sqs_queue" "heavy" {
  name                       = "${local.name}-heavy-queue"
  visibility_timeout_seconds = var.heavy_visibility_seconds
  receive_wait_time_seconds  = 20
  message_retention_seconds  = 345600
  sqs_managed_sse_enabled    = true
  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.heavy_dlq.arn
    maxReceiveCount     = var.max_receive_count
  })
}

resource "aws_sqs_queue_redrive_allow_policy" "heavy_dlq" {
  queue_url = aws_sqs_queue.heavy_dlq.id
  redrive_allow_policy = jsonencode({
    redrivePermission = "byQueue"
    sourceQueueArns   = [aws_sqs_queue.heavy.arn]
  })
}

# Job records: one item per job, partition key job_id. On-demand billing = no idle cost. Items expire via TTL.
resource "aws_dynamodb_table" "jobs" {
  name         = "${local.name}-jobs"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "job_id"

  attribute {
    name = "job_id"
    type = "S"
  }

  ttl {
    attribute_name = "expires_at"
    enabled        = true
  }

  point_in_time_recovery {
    enabled = false # staging: job records are short-lived; results are recomputable
  }

  server_side_encryption {
    enabled = false # false = DynamoDB's default encryption with an AWS-owned key (data is still encrypted at rest)
  }
}

# Result documents: results/<engine-version>/<computation-hash>.json. A result is a pure function of its key, so
# objects are written once and re-read; they expire after result_retention_days (they can always be recomputed).
resource "aws_s3_bucket" "results" {
  bucket        = "${local.name}-results-${local.account_id}"
  force_destroy = true
}

resource "aws_s3_bucket_public_access_block" "results" {
  bucket                  = aws_s3_bucket.results.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_ownership_controls" "results" {
  bucket = aws_s3_bucket.results.id
  rule {
    object_ownership = "BucketOwnerEnforced"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "results" {
  bucket = aws_s3_bucket.results.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "results" {
  bucket = aws_s3_bucket.results.id
  rule {
    id     = "expire-results"
    status = "Enabled"
    filter {
      prefix = "results/"
    }
    expiration {
      days = var.result_retention_days
    }
    abort_incomplete_multipart_upload {
      days_after_initiation = 1
    }
  }
}

resource "aws_s3_bucket_policy" "results_tls_only" {
  bucket = aws_s3_bucket.results.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Sid       = "DenyInsecureTransport"
      Effect    = "Deny"
      Principal = "*"
      Action    = "s3:*"
      Resource  = [aws_s3_bucket.results.arn, "${aws_s3_bucket.results.arn}/*"]
      Condition = { Bool = { "aws:SecureTransport" = "false" } }
    }]
  })
  depends_on = [aws_s3_bucket_public_access_block.results]
}

# Free gateway endpoints: S3 and DynamoDB traffic from tasks stays on the AWS network instead of the internet gateway.
# (Interface endpoints for SQS/ECR/Logs cost ~$7/month each per AZ and are the documented production upgrade.)
resource "aws_vpc_endpoint" "s3" {
  vpc_id            = aws_vpc.main.id
  service_name      = "com.amazonaws.${var.region}.s3"
  vpc_endpoint_type = "Gateway"
  route_table_ids   = [aws_route_table.public.id]
  tags              = { Name = "${local.name}-s3" }
}

resource "aws_vpc_endpoint" "dynamodb" {
  vpc_id            = aws_vpc.main.id
  service_name      = "com.amazonaws.${var.region}.dynamodb"
  vpc_endpoint_type = "Gateway"
  route_table_ids   = [aws_route_table.public.id]
  tags              = { Name = "${local.name}-dynamodb" }
}
