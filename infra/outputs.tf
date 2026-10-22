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
