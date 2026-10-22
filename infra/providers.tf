terraform {
  required_version = ">= 1.6"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0"
    }
  }
  # State is local (infra/terraform.tfstate, git-ignored) for this first version: one person, one machine.
  # Upgrade path: an S3 backend with native locking, so CI or a second machine can run Terraform safely.
}

provider "aws" {
  region = var.region
  # every resource gets these tags: easy to find in the console and in Cost Explorer
  default_tags {
    tags = {
      Project   = var.project
      ManagedBy = "terraform"
    }
  }
}
