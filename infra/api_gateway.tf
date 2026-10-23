# ------------------------------------------------------------------------------------------------------------------
# Stable HTTPS entry point:  client --HTTPS--> API Gateway HTTP API --VPC Link--> Cloud Map --> ECS API task :8000
#
# - HTTPS on the default https://<api-id>.execute-api.<region>.amazonaws.com URL (AWS certificate; no domain needed).
# - /jobs routes use AWS_IAM authorization (SigV4-signed requests). /health and /version are public.
# - The protected integration overwrites the x-gtc-caller-arn header with the signed caller's IAM ARN, so the app can
#   record and scope jobs per caller; clients cannot spoof it (the gateway replaces any value they send).
# - ECS registers each API task in Cloud Map as an SRV record (IP + port); the VPC Link integration discovers it.
# - API Gateway cannot start ECS tasks: with desired_count = 0 the gateway returns 503 until a task is running.
# - Both integrations overwrite the backend path with $request.path, so no stage prefix ever reaches the app.
# - HTTP APIs time out integrations at 30 s, which is why no long computation runs behind a request (jobs are async).
# ------------------------------------------------------------------------------------------------------------------

resource "aws_service_discovery_private_dns_namespace" "main" {
  name        = "${local.name}.internal"
  description = "Service discovery for GTC ECS services"
  vpc         = aws_vpc.main.id
}

resource "aws_service_discovery_service" "api" {
  name = "api"
  dns_config {
    namespace_id   = aws_service_discovery_private_dns_namespace.main.id
    routing_policy = "MULTIVALUE"
    dns_records {
      type = "SRV" # carries the port as well as the IP: required for API Gateway's Cloud Map integration
      ttl  = 10
    }
  }
  # No health_check_custom_config block: an empty block is stored by AWS as "none", which made every plan replace
  # this service (the field forces replacement). ECS deregisters a task from Cloud Map when the task stops, and a task
  # failing its container health check is stopped and replaced, so stale instances do not stay registered.
}

# The VPC Link's network interfaces live in the public subnets; they only need to reach the API tasks on 8000.
resource "aws_security_group" "vpc_link" {
  name        = "${local.name}-vpc-link"
  description = "API Gateway VPC Link: outbound to the API tasks only"
  vpc_id      = aws_vpc.main.id
  tags        = { Name = "${local.name}-vpc-link" }
}

resource "aws_vpc_security_group_egress_rule" "vpc_link_to_api" {
  security_group_id            = aws_security_group.vpc_link.id
  description                  = "To API tasks"
  ip_protocol                  = "tcp"
  from_port                    = 8000
  to_port                      = 8000
  referenced_security_group_id = aws_security_group.api.id
}

resource "aws_vpc_security_group_ingress_rule" "api_from_vpc_link" {
  security_group_id            = aws_security_group.api.id
  description                  = "From API Gateway VPC Link only"
  ip_protocol                  = "tcp"
  from_port                    = 8000
  to_port                      = 8000
  referenced_security_group_id = aws_security_group.vpc_link.id
}

resource "aws_apigatewayv2_vpc_link" "main" {
  name               = "${local.name}-vpc-link"
  subnet_ids         = aws_subnet.public[*].id
  security_group_ids = [aws_security_group.vpc_link.id]
}

resource "aws_apigatewayv2_api" "main" {
  name          = "${local.name}-api"
  protocol_type = "HTTP"
  description   = "GTC theorycrafting jobs API (staging)"
}

# Public routes: no caller identity.
resource "aws_apigatewayv2_integration" "public" {
  api_id                 = aws_apigatewayv2_api.main.id
  integration_type       = "HTTP_PROXY"
  integration_method     = "ANY"
  connection_type        = "VPC_LINK"
  connection_id          = aws_apigatewayv2_vpc_link.main.id
  integration_uri        = aws_service_discovery_service.api.arn
  payload_format_version = "1.0"
  timeout_milliseconds   = 10000
  request_parameters = {
    "overwrite:path" = "$request.path" # the backend receives /health, never a stage-prefixed path
  }
}

# Protected routes: the gateway sets the caller header from the SigV4-authenticated identity.
resource "aws_apigatewayv2_integration" "protected" {
  api_id                 = aws_apigatewayv2_api.main.id
  integration_type       = "HTTP_PROXY"
  integration_method     = "ANY"
  connection_type        = "VPC_LINK"
  connection_id          = aws_apigatewayv2_vpc_link.main.id
  integration_uri        = aws_service_discovery_service.api.arn
  payload_format_version = "1.0"
  timeout_milliseconds   = 10000
  request_parameters = {
    "overwrite:path"                    = "$request.path"             # /jobs/team arrives as /jobs/team
    "overwrite:header.x-gtc-caller-arn" = "$context.identity.userArn" # replaces any client-supplied value
  }
}

locals {
  public_routes    = ["GET /health", "GET /version"]
  protected_routes = ["POST /jobs/team", "POST /jobs/team-variant", "GET /jobs/{job_id}", "GET /jobs/{job_id}/result"]
}

resource "aws_apigatewayv2_route" "public" {
  for_each           = toset(local.public_routes)
  api_id             = aws_apigatewayv2_api.main.id
  route_key          = each.value
  authorization_type = "NONE"
  target             = "integrations/${aws_apigatewayv2_integration.public.id}"
}

resource "aws_apigatewayv2_route" "protected" {
  for_each           = toset(local.protected_routes)
  api_id             = aws_apigatewayv2_api.main.id
  route_key          = each.value
  authorization_type = "AWS_IAM"
  target             = "integrations/${aws_apigatewayv2_integration.protected.id}"
}

resource "aws_cloudwatch_log_group" "api_gateway" {
  name              = "/aws/apigateway/${local.name}-api"
  retention_in_days = var.log_retention_days
}

resource "aws_apigatewayv2_stage" "default" {
  api_id      = aws_apigatewayv2_api.main.id
  name        = "$default"
  auto_deploy = true

  default_route_settings {
    throttling_rate_limit  = var.api_throttle_rate
    throttling_burst_limit = var.api_throttle_burst
  }

  access_log_settings {
    destination_arn = aws_cloudwatch_log_group.api_gateway.arn
    format = jsonencode({
      requestId     = "$context.requestId"
      ip            = "$context.identity.sourceIp"
      caller        = "$context.identity.userArn"
      routeKey      = "$context.routeKey"
      status        = "$context.status"
      latencyMs     = "$context.responseLatency"
      integrationMs = "$context.integrationLatency"
      error         = "$context.error.message"
      integrationEr = "$context.integrationErrorMessage"
    })
  }
}
