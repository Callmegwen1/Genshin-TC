output "ecr_repository_url" {
  description = "Push images here."
  value       = aws_ecr_repository.api.repository_url
}

output "cache_bucket" {
  description = "Private bucket holding the Amber cache (aws s3 sync data/sources/cache/amber s3://<bucket>/amber)."
  value       = aws_s3_bucket.cache.bucket
}

output "ecs_cluster" {
  value = aws_ecs_cluster.main.name
}

output "ecs_service" {
  value = aws_ecs_service.api.name
}

output "log_group" {
  description = "CloudWatch log group (aws logs tail <group> --follow)."
  value       = aws_cloudwatch_log_group.api.name
}

output "github_deploy_role_arn" {
  description = "Set as the AWS_DEPLOY_ROLE_ARN variable in the GitHub repository."
  value       = local.github_enabled ? aws_iam_role.github_deploy[0].arn : "(github_repo not set)"
}

output "find_public_ip" {
  description = "The task's public IP changes on every deployment; this prints the current one."
  value       = "bash scripts/ecs_ip.sh"
}

# ---------------------------------------------------------------- Phase 2

output "api_url" {
  description = "Stable HTTPS endpoint (API Gateway). Public: /health, /version. SigV4 (AWS_IAM): /jobs/*."
  value       = aws_apigatewayv2_api.main.api_endpoint
}

output "light_queue_url" {
  value = aws_sqs_queue.light.url
}

output "light_dlq_url" {
  value = aws_sqs_queue.light_dlq.url
}

output "heavy_queue_url" {
  description = "Provisioned, unused: no producer or consumer until ACCOUNT_ANALYSIS is enabled."
  value       = aws_sqs_queue.heavy.url
}

output "jobs_table" {
  value = aws_dynamodb_table.jobs.name
}

output "results_bucket" {
  value = aws_s3_bucket.results.bucket
}

output "worker_service" {
  value = aws_ecs_service.worker.name
}

output "dashboard" {
  value = "https://${var.region}.console.aws.amazon.com/cloudwatch/home?region=${var.region}#dashboards/dashboard/${aws_cloudwatch_dashboard.main.dashboard_name}"
}
