variable "region" {
  description = "AWS region for every resource."
  type        = string
  default     = "us-east-2"
}

variable "project" {
  description = "Name prefix for resources."
  type        = string
  default     = "gtc"
}

variable "allowed_cidr" {
  description = "Who may call the API on port 8000. Your public IP as a /32, e.g. 203.0.113.7/32."
  type        = string
  validation {
    condition     = can(cidrhost(var.allowed_cidr, 0))
    error_message = "allowed_cidr must be a CIDR block, e.g. 203.0.113.7/32."
  }
}

variable "github_repo" {
  description = "GitHub repository allowed to deploy, as owner/name (e.g. octocat/Genshin-TC). Empty skips the OIDC role."
  type        = string
  default     = ""
}

variable "github_branch" {
  description = "Only workflows running on this branch may assume the deploy role."
  type        = string
  default     = "main"
}

variable "budget_email" {
  description = "Email address for AWS Budget alerts."
  type        = string
}

variable "monthly_budget_usd" {
  description = "Monthly cost budget in USD; alerts at 50%, 80% and 100% actual and 100% forecast."
  type        = number
  default     = 10
}

variable "image_tag" {
  description = "Image tag the Terraform-managed task definition starts from. CI deploys later images itself."
  type        = string
  default     = "bootstrap"
}

variable "desired_count" {
  description = "Running tasks. 1 for the demo; 0 stops compute charges while keeping everything else."
  type        = number
  default     = 1
}

variable "task_cpu" {
  description = "Fargate CPU units (1024 = 1 vCPU)."
  type        = number
  default     = 1024
}

variable "task_memory" {
  description = "Fargate memory in MiB."
  type        = number
  default     = 2048
}

variable "search_seconds" {
  description = "GTC_SEARCH_SECONDS for the container: the forward model's base-search time limit."
  type        = number
  default     = 60
}

variable "log_retention_days" {
  description = "CloudWatch Logs retention."
  type        = number
  default     = 14
}

variable "github_oidc_subject" {
  description = <<-EOT
    Exact "sub" claim of the workflow's OIDC token. Newer GitHub repositories use an immutable format with numeric IDs,
    repo:owner@<owner-id>/name@<repo-id>:ref:refs/heads/main, which survives renames and cannot be claimed by a
    re-created repo with the same name. Empty = the classic repo:owner/name:ref:refs/heads/<branch> format.
  EOT
  type        = string
  default     = ""
}
