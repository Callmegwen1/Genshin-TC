# ------------------------------------------------------------------------------------------------------------------
# Observability: worker log metrics, alarms to email, ECS service events, one dashboard.
# Alarms within the CloudWatch free allowance (10 alarms, 10 custom metrics, 3 dashboards).
# ------------------------------------------------------------------------------------------------------------------

locals {
  alert_email = var.alert_email != "" ? var.alert_email : var.budget_email
  metric_ns   = "GTC/Jobs"
}

resource "aws_sns_topic" "alerts" {
  name = "${local.name}-alerts"
}

resource "aws_sns_topic_subscription" "alerts_email" {
  topic_arn = aws_sns_topic.alerts.arn
  protocol  = "email"
  endpoint  = local.alert_email # AWS emails a confirmation link; alerts arrive only after it is clicked
}

data "aws_iam_policy_document" "alerts_topic" {
  statement {
    sid       = "AccountOwnerAndCloudWatch"
    actions   = ["sns:Publish"]
    resources = [aws_sns_topic.alerts.arn]
    principals {
      type        = "Service"
      identifiers = ["cloudwatch.amazonaws.com", "events.amazonaws.com"]
    }
    condition {
      test     = "StringEquals"
      variable = "aws:SourceAccount"
      values   = [local.account_id]
    }
  }
}

resource "aws_sns_topic_policy" "alerts" {
  arn    = aws_sns_topic.alerts.arn
  policy = data.aws_iam_policy_document.alerts_topic.json
}

# ---- worker log -> metrics (fields written by api/worker.py)
resource "aws_cloudwatch_log_metric_filter" "jobs_completed" {
  name           = "${local.name}-jobs-completed"
  log_group_name = aws_cloudwatch_log_group.worker.name
  pattern        = "{ $.msg = \"job_completed\" }"
  metric_transformation {
    name      = "JobsCompleted"
    namespace = local.metric_ns
    value     = "1"
  }
}

resource "aws_cloudwatch_log_metric_filter" "job_duration" {
  name           = "${local.name}-job-duration"
  log_group_name = aws_cloudwatch_log_group.worker.name
  pattern        = "{ $.msg = \"job_completed\" && $.cache_hit IS FALSE }"
  metric_transformation {
    name      = "JobDurationSeconds"
    namespace = local.metric_ns
    value     = "$.seconds"
    unit      = "Seconds"
  }
}

resource "aws_cloudwatch_log_metric_filter" "jobs_failed_final" {
  name           = "${local.name}-jobs-failed-final"
  log_group_name = aws_cloudwatch_log_group.worker.name
  pattern        = "{ $.msg = \"job_failed\" && $.final IS TRUE }"
  metric_transformation {
    name      = "JobsFailedFinal"
    namespace = local.metric_ns
    value     = "1"
  }
}

resource "aws_cloudwatch_log_metric_filter" "job_retries" {
  name           = "${local.name}-job-retries"
  log_group_name = aws_cloudwatch_log_group.worker.name
  pattern        = "{ $.msg = \"job_failed\" && $.final IS FALSE }"
  metric_transformation {
    name      = "JobRetries"
    namespace = local.metric_ns
    value     = "1"
  }
}

# ---- alarms
resource "aws_cloudwatch_metric_alarm" "light_dlq" {
  alarm_name          = "${local.name}-light-dlq-not-empty"
  alarm_description   = "A light job (team / team variant) exhausted its retries or was unreadable"
  namespace           = "AWS/SQS"
  metric_name         = "ApproximateNumberOfMessagesVisible"
  dimensions          = { QueueName = aws_sqs_queue.light_dlq.name }
  statistic           = "Maximum"
  period              = 300
  evaluation_periods  = 1
  comparison_operator = "GreaterThanThreshold"
  threshold           = 0
  treat_missing_data  = "notBreaching"
  alarm_actions       = [aws_sns_topic.alerts.arn]
  ok_actions          = [aws_sns_topic.alerts.arn]
}

resource "aws_cloudwatch_metric_alarm" "heavy_dlq" {
  alarm_name          = "${local.name}-heavy-dlq-not-empty"
  alarm_description   = "A heavy (account) job exhausted its retries (lane disabled: should never fire yet)"
  namespace           = "AWS/SQS"
  metric_name         = "ApproximateNumberOfMessagesVisible"
  dimensions          = { QueueName = aws_sqs_queue.heavy_dlq.name }
  statistic           = "Maximum"
  period              = 300
  evaluation_periods  = 1
  comparison_operator = "GreaterThanThreshold"
  threshold           = 0
  treat_missing_data  = "notBreaching"
  alarm_actions       = [aws_sns_topic.alerts.arn]
}

resource "aws_cloudwatch_metric_alarm" "jobs_failed" {
  alarm_name          = "${local.name}-jobs-failed"
  alarm_description   = "A job failed on its final attempt"
  namespace           = local.metric_ns
  metric_name         = "JobsFailedFinal"
  statistic           = "Sum"
  period              = 300
  evaluation_periods  = 1
  comparison_operator = "GreaterThanOrEqualToThreshold"
  threshold           = 1
  treat_missing_data  = "notBreaching"
  alarm_actions       = [aws_sns_topic.alerts.arn]
}

resource "aws_cloudwatch_metric_alarm" "light_queue_age" {
  alarm_name          = "${local.name}-light-queue-stale"
  alarm_description   = "A queued job has waited over 30 minutes (no worker running, or workers stuck)"
  namespace           = "AWS/SQS"
  metric_name         = "ApproximateAgeOfOldestMessage"
  dimensions          = { QueueName = aws_sqs_queue.light.name }
  statistic           = "Maximum"
  period              = 300
  evaluation_periods  = 1
  comparison_operator = "GreaterThanThreshold"
  threshold           = 1800
  treat_missing_data  = "notBreaching"
  alarm_actions       = [aws_sns_topic.alerts.arn]
}

resource "aws_cloudwatch_metric_alarm" "api_5xx" {
  alarm_name          = "${local.name}-api-5xx"
  alarm_description   = "API Gateway returned 5 or more 5xx responses in 5 minutes (includes the 500 returned while no API task runs)"
  namespace           = "AWS/ApiGateway"
  metric_name         = "5xx"
  dimensions          = { ApiId = aws_apigatewayv2_api.main.id, Stage = "$default" }
  statistic           = "Sum"
  period              = 300
  evaluation_periods  = 1
  comparison_operator = "GreaterThanOrEqualToThreshold"
  threshold           = 5
  treat_missing_data  = "notBreaching"
  alarm_actions       = [aws_sns_topic.alerts.arn]
}

# ---- ECS service health: deployment failures and tasks that cannot start -> email
resource "aws_cloudwatch_event_rule" "ecs_unhealthy" {
  name        = "${local.name}-ecs-unhealthy"
  description = "ECS deployment failed or tasks cannot start in the GTC cluster"
  event_pattern = jsonencode({
    source        = ["aws.ecs"]
    "detail-type" = ["ECS Deployment State Change", "ECS Service Action"]
    detail = {
      clusterArn = [aws_ecs_cluster.main.arn]
      eventName  = ["SERVICE_DEPLOYMENT_FAILED", "SERVICE_TASK_START_IMPAIRED", "SERVICE_TASK_PLACEMENT_FAILURE"]
    }
  })
}

resource "aws_cloudwatch_event_target" "ecs_unhealthy" {
  rule      = aws_cloudwatch_event_rule.ecs_unhealthy.name
  target_id = "sns"
  arn       = aws_sns_topic.alerts.arn
}

# ---- one dashboard
resource "aws_cloudwatch_dashboard" "main" {
  dashboard_name = "${local.name}-jobs"
  dashboard_body = jsonencode({
    widgets = [
      {
        type = "metric", x = 0, y = 0, width = 12, height = 6
        properties = {
          title = "Light queue: waiting vs in progress", region = var.region, stat = "Maximum", period = 60
          metrics = [
            ["AWS/SQS", "ApproximateNumberOfMessagesVisible", "QueueName", aws_sqs_queue.light.name, { label = "waiting" }],
            [".", "ApproximateNumberOfMessagesNotVisible", ".", ".", { label = "in progress" }],
          ]
        }
      },
      {
        type = "metric", x = 12, y = 0, width = 12, height = 6
        properties = {
          title = "Oldest queued job (s) and DLQ depth", region = var.region, stat = "Maximum", period = 60
          metrics = [
            ["AWS/SQS", "ApproximateAgeOfOldestMessage", "QueueName", aws_sqs_queue.light.name, { label = "oldest light job (s)" }],
            [".", "ApproximateNumberOfMessagesVisible", ".", aws_sqs_queue.light_dlq.name, { label = "light DLQ", yAxis = "right" }],
            [".", ".", ".", aws_sqs_queue.heavy_dlq.name, { label = "heavy DLQ", yAxis = "right" }],
          ]
        }
      },
      {
        type = "metric", x = 0, y = 6, width = 12, height = 6
        properties = {
          title = "Jobs completed / retried / failed", region = var.region, stat = "Sum", period = 300
          metrics = [
            [local.metric_ns, "JobsCompleted", { label = "completed" }],
            [".", "JobRetries", { label = "retried" }],
            [".", "JobsFailedFinal", { label = "failed (final)" }],
          ]
        }
      },
      {
        type = "metric", x = 12, y = 6, width = 12, height = 6
        properties = {
          title = "Job duration (s), computed jobs only", region = var.region, period = 300
          metrics = [
            [local.metric_ns, "JobDurationSeconds", { stat = "Average", label = "average" }],
            [".", ".", { stat = "Maximum", label = "max" }],
          ]
        }
      },
      {
        type = "metric", x = 0, y = 12, width = 12, height = 6
        properties = {
          title = "API requests and errors", region = var.region, stat = "Sum", period = 300
          metrics = [
            ["AWS/ApiGateway", "Count", "ApiId", aws_apigatewayv2_api.main.id, "Stage", "$default", { label = "requests" }],
            [".", "4xx", ".", ".", ".", ".", { label = "4xx" }],
            [".", "5xx", ".", ".", ".", ".", { label = "5xx" }],
          ]
        }
      },
      {
        type = "metric", x = 12, y = 12, width = 12, height = 6
        properties = {
          title = "ECS CPU %: API and worker", region = var.region, stat = "Average", period = 300
          metrics = [
            ["AWS/ECS", "CPUUtilization", "ClusterName", aws_ecs_cluster.main.name, "ServiceName", aws_ecs_service.api.name, { label = "api" }],
            [".", ".", ".", ".", ".", aws_ecs_service.worker.name, { label = "worker" }],
          ]
        }
      },
    ]
  })
}
