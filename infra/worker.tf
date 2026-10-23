# ------------------------------------------------------------------------------------------------------------------
# Light worker: same image as the API, command `python -m api.worker`. Polls gtc-light-queue, runs one ForwardModel
# team at a time, writes results to S3 and job state to DynamoDB. No inbound traffic at all.
# desired count 0 by default: queued jobs wait (4-day retention) until a worker is started. Scale-out on queue depth
# (Application Auto Scaling + ECS task scale-in protection) is a documented next step, not built in Phase 2.
# ------------------------------------------------------------------------------------------------------------------

resource "aws_security_group" "worker" {
  name        = "${local.name}-worker"
  description = "GTC worker: no inbound; outbound to AWS APIs and ECR"
  vpc_id      = aws_vpc.main.id
  tags        = { Name = "${local.name}-worker" }
}

resource "aws_vpc_security_group_egress_rule" "worker_out" {
  security_group_id = aws_security_group.worker.id
  description       = "ECR, SQS, DynamoDB, S3, CloudWatch Logs"
  ip_protocol       = "-1"
  cidr_ipv4         = "0.0.0.0/0"
}

resource "aws_cloudwatch_log_group" "worker" {
  name              = "/ecs/${local.name}-worker"
  retention_in_days = var.log_retention_days
}

resource "aws_ecs_task_definition" "worker" {
  family                   = "${local.name}-worker"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = var.worker_cpu
  memory                   = var.worker_memory
  execution_role_arn       = aws_iam_role.execution.arn
  task_role_arn            = aws_iam_role.worker_task.arn
  runtime_platform {
    operating_system_family = "LINUX"
    cpu_architecture        = "X86_64"
  }
  container_definitions = jsonencode([{
    name      = "worker"
    image     = "${aws_ecr_repository.api.repository_url}:${var.image_tag}"
    essential = true
    command   = ["python", "-m", "api.worker"]
    environment = [
      { name = "GTC_SEARCH_SECONDS", value = tostring(var.search_seconds) }, # must match the API (dedupe hash)
      { name = "GTC_CACHE_OFFLINE", value = "1" },
      { name = "GTC_BACKEND", value = "aws" },
      { name = "GTC_JOBS_TABLE", value = aws_dynamodb_table.jobs.name },
      { name = "GTC_RESULTS_BUCKET", value = aws_s3_bucket.results.bucket },
      { name = "GTC_LIGHT_QUEUE_URL", value = aws_sqs_queue.light.url },
      { name = "GTC_VISIBILITY_SECONDS", value = tostring(var.light_visibility_seconds) },
      { name = "GTC_HEARTBEAT_SECONDS", value = tostring(var.heartbeat_seconds) },
      { name = "GTC_MAX_RECEIVE", value = tostring(var.max_receive_count) },
      { name = "AWS_DEFAULT_REGION", value = var.region },
    ]
    readonlyRootFilesystem = true
    user                   = "10001"
    stopTimeout            = 120 # SIGTERM -> finish the current job if possible; Fargate's maximum is 120 s
    logConfiguration = {
      logDriver = "awslogs"
      options = {
        awslogs-group         = aws_cloudwatch_log_group.worker.name
        awslogs-region        = var.region
        awslogs-stream-prefix = "worker"
      }
    }
  }])
}

resource "aws_ecs_service" "worker" {
  name            = "${local.name}-worker"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.worker.arn
  desired_count   = var.worker_desired_count
  launch_type     = "FARGATE"

  network_configuration {
    subnets          = aws_subnet.public[*].id
    security_groups  = [aws_security_group.worker.id]
    assign_public_ip = true # outbound only (no NAT gateway); the security group has no inbound rules
  }

  deployment_circuit_breaker {
    enable   = true
    rollback = true
  }

  lifecycle {
    ignore_changes = [task_definition] # CI owns the image version
  }
}
