# ------------------------------------------------------------------------------------------------------------------
# Task roles: what the application code itself may do. Separate roles for the API and the worker; every statement is
# scoped to a named resource ARN. (The execution role in main.tf is ECS's own role: image pull and log writes.)
# ------------------------------------------------------------------------------------------------------------------

data "aws_iam_policy_document" "api_task" {
  statement {
    sid       = "JobRecords" # create jobs, read status; Update for dedupe-created SUCCEEDED records
    actions   = ["dynamodb:GetItem", "dynamodb:PutItem", "dynamodb:UpdateItem"]
    resources = [aws_dynamodb_table.jobs.arn]
  }
  statement {
    sid       = "EnqueueLightJobs" # light lane only; nothing may submit to the heavy lane yet
    actions   = ["sqs:SendMessage"]
    resources = [aws_sqs_queue.light.arn]
  }
  statement {
    sid       = "ReadResults"
    actions   = ["s3:GetObject"]
    resources = ["${aws_s3_bucket.results.arn}/results/*"]
  }
  statement {
    sid       = "ListResults" # lets HeadObject on a missing key return 404 (not 403), for dedupe lookups
    actions   = ["s3:ListBucket"]
    resources = [aws_s3_bucket.results.arn]
    condition {
      test     = "StringLike"
      variable = "s3:prefix"
      values   = ["results/*"]
    }
  }
}

data "aws_iam_policy_document" "worker_task" {
  statement {
    sid = "ConsumeLightQueue"
    actions = ["sqs:ReceiveMessage", "sqs:DeleteMessage", "sqs:ChangeMessageVisibility",
    "sqs:GetQueueAttributes"]
    resources = [aws_sqs_queue.light.arn]
  }
  statement {
    sid       = "UpdateJobRecords" # read and update existing jobs; workers never create jobs
    actions   = ["dynamodb:GetItem", "dynamodb:UpdateItem"]
    resources = [aws_dynamodb_table.jobs.arn]
  }
  statement {
    sid       = "ReadWriteResults"
    actions   = ["s3:GetObject", "s3:PutObject"]
    resources = ["${aws_s3_bucket.results.arn}/results/*"]
  }
  statement {
    sid       = "ListResults"
    actions   = ["s3:ListBucket"]
    resources = [aws_s3_bucket.results.arn]
    condition {
      test     = "StringLike"
      variable = "s3:prefix"
      values   = ["results/*"]
    }
  }
}

resource "aws_iam_role" "api_task" {
  name               = "${local.name}-api-task"
  assume_role_policy = data.aws_iam_policy_document.ecs_tasks_trust.json
}

resource "aws_iam_role_policy" "api_task" {
  name   = "api"
  role   = aws_iam_role.api_task.id
  policy = data.aws_iam_policy_document.api_task.json
}

resource "aws_iam_role" "worker_task" {
  name               = "${local.name}-worker-task"
  assume_role_policy = data.aws_iam_policy_document.ecs_tasks_trust.json
}

resource "aws_iam_role_policy" "worker_task" {
  name   = "worker"
  role   = aws_iam_role.worker_task.id
  policy = data.aws_iam_policy_document.worker_task.json
}
