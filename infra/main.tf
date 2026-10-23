# Genshin Theorycrafting Engine API on ECS Fargate.
#
#   GitHub Actions --(OIDC)--> ECR (image) --> ECS Fargate task in a public subnet --> CloudWatch Logs
#                    \--> S3 (Amber cache, read before docker build)
#
# Deliberately absent for v1 (cost and simplicity): NAT Gateway, load balancer, Route 53, autoscaling, database.

data "aws_caller_identity" "current" {}

data "aws_availability_zones" "available" {
  state = "available"
}

locals {
  name       = var.project
  account_id = data.aws_caller_identity.current.account_id
  azs        = slice(data.aws_availability_zones.available.names, 0, 2)
}

# ------------------------------------------------------------------------------------------------------------------
# Network: one VPC, two public subnets in two AZs, an internet gateway. No NAT Gateway (~$32/month): the task gets a
# public IP and reaches ECR, S3 and CloudWatch through the internet gateway.
# ------------------------------------------------------------------------------------------------------------------
resource "aws_vpc" "main" {
  cidr_block           = "10.20.0.0/16"
  enable_dns_support   = true
  enable_dns_hostnames = true
  tags                 = { Name = "${local.name}-vpc" }
}

resource "aws_internet_gateway" "main" {
  vpc_id = aws_vpc.main.id
  tags   = { Name = "${local.name}-igw" }
}

resource "aws_subnet" "public" {
  count                   = length(local.azs)
  vpc_id                  = aws_vpc.main.id
  cidr_block              = cidrsubnet(aws_vpc.main.cidr_block, 8, count.index) # 10.20.0.0/24, 10.20.1.0/24
  availability_zone       = local.azs[count.index]
  map_public_ip_on_launch = false # the ECS service asks for a public IP explicitly
  tags                    = { Name = "${local.name}-public-${local.azs[count.index]}" }
}

resource "aws_route_table" "public" {
  vpc_id = aws_vpc.main.id
  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.main.id
  }
  tags = { Name = "${local.name}-public" }
}

resource "aws_route_table_association" "public" {
  count          = length(aws_subnet.public)
  subnet_id      = aws_subnet.public[count.index].id
  route_table_id = aws_route_table.public.id
}

# Stateful firewall on the API task's network interface. Phase 2: port 8000 only from the API Gateway VPC Link's
# security group (api_gateway.tf). All outbound is allowed so the task can reach ECR, SQS, DynamoDB, S3 and logs.
# (The description below is historical: changing a security group's description forces its replacement.)
resource "aws_security_group" "api" {
  name        = "${local.name}-api"
  description = "GTC API: port 8000 from the allowed CIDR only"
  vpc_id      = aws_vpc.main.id
  tags        = { Name = "${local.name}-api" }
}

resource "aws_vpc_security_group_ingress_rule" "api_8000" {
  count             = var.enable_direct_access ? 1 : 0 # debug only; normal traffic arrives through API Gateway
  security_group_id = aws_security_group.api.id
  description       = "API from the allowed CIDR"
  ip_protocol       = "tcp"
  from_port         = 8000
  to_port           = 8000
  cidr_ipv4         = var.allowed_cidr
}

resource "aws_vpc_security_group_egress_rule" "all_out" {
  security_group_id = aws_security_group.api.id
  description       = "Image pulls (ECR), logs (CloudWatch)"
  ip_protocol       = "-1"
  cidr_ipv4         = "0.0.0.0/0"
}

# ------------------------------------------------------------------------------------------------------------------
# Container registry. Tags are immutable (a tag always means the same image: CI tags with the git commit SHA);
# scan on push; keep the last 10 images.
# ------------------------------------------------------------------------------------------------------------------
resource "aws_ecr_repository" "api" {
  name                 = "${local.name}-api"
  image_tag_mutability = "IMMUTABLE"
  force_delete         = true # terraform destroy also removes the images
  image_scanning_configuration {
    scan_on_push = true
  }
}

resource "aws_ecr_lifecycle_policy" "api" {
  repository = aws_ecr_repository.api.name
  policy = jsonencode({
    rules = [{
      rulePriority = 1
      description  = "keep the last 10 images"
      selection    = { tagStatus = "any", countType = "imageCountMoreThan", countNumber = 10 }
      action       = { type = "expire" }
    }]
  })
}

# ------------------------------------------------------------------------------------------------------------------
# Private S3 bucket for the Project Amber game-data cache (personal-use third-party data: never in git).
# CI downloads it before `docker build`. Objects are uploaded with the CLI, not Terraform, so they stay out of state.
# ------------------------------------------------------------------------------------------------------------------
resource "aws_s3_bucket" "cache" {
  bucket        = "${local.name}-amber-cache-${local.account_id}"
  force_destroy = true
}

resource "aws_s3_bucket_public_access_block" "cache" {
  bucket                  = aws_s3_bucket.cache.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_ownership_controls" "cache" {
  bucket = aws_s3_bucket.cache.id
  rule {
    object_ownership = "BucketOwnerEnforced" # ACLs off; access is decided by IAM only
  }
}

resource "aws_s3_bucket_versioning" "cache" {
  bucket = aws_s3_bucket.cache.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "cache" {
  bucket = aws_s3_bucket.cache.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_policy" "cache_tls_only" {
  bucket = aws_s3_bucket.cache.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Sid       = "DenyInsecureTransport"
      Effect    = "Deny"
      Principal = "*"
      Action    = "s3:*"
      Resource  = [aws_s3_bucket.cache.arn, "${aws_s3_bucket.cache.arn}/*"]
      Condition = { Bool = { "aws:SecureTransport" = "false" } }
    }]
  })
  depends_on = [aws_s3_bucket_public_access_block.cache]
}

# ------------------------------------------------------------------------------------------------------------------
# Logs: the container writes JSON lines to stdout; the awslogs driver ships them here.
# ------------------------------------------------------------------------------------------------------------------
resource "aws_cloudwatch_log_group" "api" {
  name              = "/ecs/${local.name}-api"
  retention_in_days = var.log_retention_days
}

# ------------------------------------------------------------------------------------------------------------------
# IAM. The task EXECUTION role is used by ECS itself (pull the image, create log streams). There is no task role:
# the application calls no AWS APIs, so the container gets no AWS permissions at all.
# ------------------------------------------------------------------------------------------------------------------
data "aws_iam_policy_document" "ecs_tasks_trust" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["ecs-tasks.amazonaws.com"]
    }
    condition { # confused-deputy protection: only ECS acting for this account
      test     = "StringEquals"
      variable = "aws:SourceAccount"
      values   = [local.account_id]
    }
  }
}

resource "aws_iam_role" "execution" {
  name               = "${local.name}-ecs-execution"
  assume_role_policy = data.aws_iam_policy_document.ecs_tasks_trust.json
}

resource "aws_iam_role_policy_attachment" "execution" {
  role       = aws_iam_role.execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

# ------------------------------------------------------------------------------------------------------------------
# ECS: cluster, task definition, service. Fargate = no servers to manage; billed per vCPU-second and GB-second.
# ------------------------------------------------------------------------------------------------------------------
resource "aws_ecs_cluster" "main" {
  name = "${local.name}-cluster"
  setting {
    name  = "containerInsights"
    value = "disabled" # extra CloudWatch metrics cost money; basic CPU/memory metrics are still free
  }
}

resource "aws_ecs_task_definition" "api" {
  family                   = "${local.name}-api"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"    # each task gets its own network interface and security group
  cpu                      = var.api_cpu # Phase 2: the API only validates, queues and reads; workers compute
  memory                   = var.api_memory
  execution_role_arn       = aws_iam_role.execution.arn
  task_role_arn            = aws_iam_role.api_task.arn # the API's own AWS permissions (iam_tasks.tf)
  runtime_platform {
    operating_system_family = "LINUX"
    cpu_architecture        = "X86_64"
  }
  container_definitions = jsonencode([{
    name         = "api"
    image        = "${aws_ecr_repository.api.repository_url}:${var.image_tag}"
    essential    = true
    portMappings = [{ containerPort = 8000, protocol = "tcp" }]
    environment = [
      { name = "GTC_SEARCH_SECONDS", value = tostring(var.search_seconds) }, # part of the dedupe hash: same as worker
      { name = "GTC_CACHE_OFFLINE", value = "1" },
      { name = "GTC_BACKEND", value = "aws" },
      { name = "GTC_JOBS_TABLE", value = aws_dynamodb_table.jobs.name },
      { name = "GTC_RESULTS_BUCKET", value = aws_s3_bucket.results.bucket },
      { name = "GTC_LIGHT_QUEUE_URL", value = aws_sqs_queue.light.url },
      { name = "ENABLE_SYNC_EVALUATE", value = "0" },     # legacy synchronous route off in AWS
      { name = "REQUIRE_GATEWAY_IDENTITY", value = "1" }, # /jobs routes need the gateway-set caller header
      { name = "AWS_DEFAULT_REGION", value = var.region },
    ]
    readonlyRootFilesystem = true # the engine writes nothing in offline mode
    user                   = "10001"
    healthCheck = {
      command     = ["CMD", "python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=4)"]
      interval    = 30
      timeout     = 5
      retries     = 3
      startPeriod = 20
    }
    logConfiguration = {
      logDriver = "awslogs"
      options = {
        awslogs-group         = aws_cloudwatch_log_group.api.name
        awslogs-region        = var.region
        awslogs-stream-prefix = "api"
      }
    }
  }])
}

resource "aws_ecs_service" "api" {
  name            = "${local.name}-api"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.api.arn
  desired_count   = var.desired_count
  launch_type     = "FARGATE"

  network_configuration {
    subnets          = aws_subnet.public[*].id
    security_groups  = [aws_security_group.api.id]
    assign_public_ip = true # no NAT: the public IP is only for outbound (ECR, AWS APIs); inbound comes via VPC Link
  }

  # Cloud Map registration (SRV: IP + port) that API Gateway's VPC Link integration resolves (api_gateway.tf)
  service_registries {
    registry_arn   = aws_service_discovery_service.api.arn
    container_name = "api"
    container_port = 8000
  }

  deployment_circuit_breaker { # a deployment whose tasks keep failing is rolled back automatically
    enable   = true
    rollback = true
  }

  # CI registers new task-definition revisions (new image tags). Terraform must not roll them back on the next apply.
  lifecycle {
    ignore_changes = [task_definition]
  }
}

# ------------------------------------------------------------------------------------------------------------------
# GitHub Actions deploy role via OIDC: GitHub proves the workflow's identity with a signed token, AWS exchanges it for
# short-lived credentials. No AWS keys are stored in GitHub. Trust is limited to one repo and one branch.
# ------------------------------------------------------------------------------------------------------------------
locals {
  github_enabled = var.github_repo != ""
  github_subject = var.github_oidc_subject != "" ? var.github_oidc_subject : "repo:${var.github_repo}:ref:refs/heads/${var.github_branch}"
}

resource "aws_iam_openid_connect_provider" "github" {
  count          = local.github_enabled ? 1 : 0
  url            = "https://token.actions.githubusercontent.com"
  client_id_list = ["sts.amazonaws.com"]
}

data "aws_iam_policy_document" "github_trust" {
  count = local.github_enabled ? 1 : 0
  statement {
    actions = ["sts:AssumeRoleWithWebIdentity"]
    principals {
      type        = "Federated"
      identifiers = [aws_iam_openid_connect_provider.github[0].arn]
    }
    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:aud"
      values   = ["sts.amazonaws.com"]
    }
    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:sub"
      values   = [local.github_subject]
    }
  }
}

data "aws_iam_policy_document" "github_deploy" {
  count = local.github_enabled ? 1 : 0
  statement {
    sid       = "EcrLogin"
    actions   = ["ecr:GetAuthorizationToken"] # account-level action: cannot be scoped to a repository
    resources = ["*"]
  }
  statement {
    sid = "EcrPush"
    actions = ["ecr:BatchCheckLayerAvailability", "ecr:BatchGetImage", "ecr:CompleteLayerUpload",
    "ecr:InitiateLayerUpload", "ecr:PutImage", "ecr:UploadLayerPart", "ecr:DescribeImages"]
    resources = [aws_ecr_repository.api.arn]
  }
  statement {
    sid       = "ReadCache"
    actions   = ["s3:GetObject", "s3:ListBucket"]
    resources = [aws_s3_bucket.cache.arn, "${aws_s3_bucket.cache.arn}/*"]
  }
  statement {
    sid       = "RegisterTaskDefinition" # these two ECS actions do not support resource-level permissions
    actions   = ["ecs:DescribeTaskDefinition", "ecs:RegisterTaskDefinition"]
    resources = ["*"]
  }
  statement {
    sid     = "DeployService"
    actions = ["ecs:UpdateService", "ecs:DescribeServices"]
    # ARNs built from names, not from the service resources: scaling a service (desired_count) then leaves this
    # policy untouched instead of re-rendering it as "known after apply" on every start/stop.
    resources = [for s in ["${local.name}-api", "${local.name}-worker"] :
    "arn:aws:ecs:${var.region}:${local.account_id}:service/${aws_ecs_cluster.main.name}/${s}"]
  }
  statement {
    sid       = "FindTaskIp"
    actions   = ["ecs:ListTasks", "ecs:DescribeTasks", "ec2:DescribeNetworkInterfaces"]
    resources = ["*"]
  }
  statement {
    sid       = "PassTaskRoles" # registering a task definition hands these roles to ECS, and only to ECS
    actions   = ["iam:PassRole"]
    resources = [aws_iam_role.execution.arn, aws_iam_role.api_task.arn, aws_iam_role.worker_task.arn]
    condition {
      test     = "StringEquals"
      variable = "iam:PassedToService"
      values   = ["ecs-tasks.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "github_deploy" {
  count                = local.github_enabled ? 1 : 0
  name                 = "${local.name}-github-deploy"
  assume_role_policy   = data.aws_iam_policy_document.github_trust[0].json
  max_session_duration = 3600
}

resource "aws_iam_role_policy" "github_deploy" {
  count  = local.github_enabled ? 1 : 0
  name   = "deploy"
  role   = aws_iam_role.github_deploy[0].id
  policy = data.aws_iam_policy_document.github_deploy[0].json
}

# ------------------------------------------------------------------------------------------------------------------
# Budget: email at 50%, 80%, 100% of actual monthly cost and when the forecast passes 100%.
# ------------------------------------------------------------------------------------------------------------------
resource "aws_budgets_budget" "monthly" {
  name         = "${local.name}-monthly"
  budget_type  = "COST"
  limit_amount = tostring(var.monthly_budget_usd)
  limit_unit   = "USD"
  time_unit    = "MONTHLY"

  dynamic "notification" {
    for_each = [50, 80, 100]
    content {
      comparison_operator        = "GREATER_THAN"
      threshold                  = notification.value
      threshold_type             = "PERCENTAGE"
      notification_type          = "ACTUAL"
      subscriber_email_addresses = [var.budget_email]
    }
  }
  notification {
    comparison_operator        = "GREATER_THAN"
    threshold                  = 100
    threshold_type             = "PERCENTAGE"
    notification_type          = "FORECASTED"
    subscriber_email_addresses = [var.budget_email]
  }
}
