terraform {
  required_version = ">= 1.10" # S3 native state locking (use_lockfile)
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0"
    }
  }
  # Remote state: S3 bucket created by infra/bootstrap (versioned, encrypted, private, TLS-only).
  # Locking: native S3 lock file (Terraform >= 1.10); no DynamoDB lock table.
  # The bucket name is account-specific and comes from backend.hcl (git-ignored; see backend.hcl.example):
  #   terraform init -backend-config=backend.hcl
  backend "s3" {
    key          = "gtc/staging/terraform.tfstate"
    region       = "us-east-2"
    encrypt      = true
    use_lockfile = true
  }
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
