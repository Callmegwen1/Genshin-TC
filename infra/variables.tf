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
  description = "Only used when enable_direct_access = true: one /32 allowed to reach an API task directly on port 8000 (debug)."
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
  description = "Monthly cost budget in USD; alerts at 50%, 80% and 100% actual and 100% forecast ($10 / $16 / $20 at $20)."
  type        = number
  default     = 20
}

variable "image_tag" {
  description = "Image tag the Terraform-managed task definition starts from. CI deploys later images itself."
  type        = string
  default     = "bootstrap"
}

variable "desired_count" {
  description = "Running API tasks. 1 while demoing; 0 stops API compute charges. API Gateway cannot start a task from 0."
  type        = number
  default     = 1
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

# ---------------------------------------------------------------- Phase 2: async jobs, worker, API Gateway

variable "enable_direct_access" {
  description = "Debug only: also allow allowed_cidr to reach API tasks directly on port 8000, bypassing API Gateway."
  type        = bool
  default     = false
}

variable "api_cpu" {
  description = "API task CPU units. The API no longer computes, so it is small."
  type        = number
  default     = 256
}

variable "api_memory" {
  description = "API task memory in MiB."
  type        = number
  default     = 512
}

variable "worker_cpu" {
  description = "Light worker CPU units (one ForwardModel team at a time, ~100 s on 1 vCPU)."
  type        = number
  default     = 1024
}

variable "worker_memory" {
  description = "Light worker memory in MiB."
  type        = number
  default     = 2048
}

variable "worker_desired_count" {
  description = "Light worker tasks. 0 = no compute cost; queued jobs wait (up to the queue retention) until > 0."
  type        = number
  default     = 0
}

variable "light_visibility_seconds" {
  description = "Light queue visibility timeout. The worker re-extends it every heartbeat_seconds while a job runs."
  type        = number
  default     = 300
}

variable "heavy_visibility_seconds" {
  description = "Heavy queue initial visibility timeout (future account jobs extend it by heartbeat, up to SQS's 12 h cap)."
  type        = number
  default     = 900
}

variable "heartbeat_seconds" {
  description = "How often a worker extends the visibility of the message it is processing."
  type        = number
  default     = 60
}

variable "max_receive_count" {
  description = "Deliveries before SQS moves a message to its dead-letter queue."
  type        = number
  default     = 3
}

variable "result_retention_days" {
  description = "S3 lifecycle expiry for stored results (they are recomputable caches)."
  type        = number
  default     = 90
}

variable "job_record_ttl_days" {
  description = "Informational: the application sets DynamoDB expires_at this many days after creation."
  type        = number
  default     = 30
}

variable "api_throttle_rate" {
  description = "API Gateway steady-state requests per second."
  type        = number
  default     = 5
}

variable "api_throttle_burst" {
  description = "API Gateway burst limit."
  type        = number
  default     = 10
}

variable "alert_email" {
  description = "Email for CloudWatch alarms (SNS). Empty = budget_email. The subscription must be confirmed by email."
  type        = string
  default     = ""
}
