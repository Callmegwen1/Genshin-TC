# GTC on AWS: architecture and decisions

Status (2026-10-23): **Phase 1 is deployed** (synchronous API, paused). **Phase 2 is implemented and planned, NOT
applied**: the Terraform plan and the code are ready; nothing below Phase 1 exists in AWS until the apply is approved.

## The story in one paragraph

I first deployed the ForwardModel as a synchronous API on ECS Fargate. Measuring real workloads showed one team
evaluation takes about 100 s on a 1 vCPU Fargate task, and an account analysis takes minutes to hours. So I redesigned
the cloud layer around asynchronous SQS-backed jobs, separate ECS API and worker roles, persistent DynamoDB/S3 results
with input-hash reuse, IAM (SigV4) authorization at API Gateway, remote Terraform state, CloudWatch alarms, and
OIDC-based CI/CD. The architecture changed because the measured workload changed what was appropriate.

## Phase 1 (deployed, paused)

```
client (one IP) -> internet gateway -> public subnet -> SG :8000 -> ECS Fargate task (FastAPI + engine, synchronous)
GitHub Actions (OIDC) -> ECR -> ECS;  logs -> CloudWatch;  budget alerts
```

## Phase 2 (planned)

```
client (SigV4-signed)
  -> HTTPS  https://<api-id>.execute-api.us-east-2.amazonaws.com        API Gateway HTTP API (throttled)
       /health, /version                public
       /jobs/team, /jobs/team-variant,   AWS_IAM; gateway sets x-gtc-caller-arn from the signed identity
       /jobs/{id}, /jobs/{id}/result
  -> VPC Link -> Cloud Map (SRV record) -> ECS API service (0.25 vCPU / 0.5 GB)
       POST: validate -> hash -> result exists? reuse (cache_hit) : DynamoDB job QUEUED + SQS message {job_id}
       GET:  DynamoDB status / S3 result
  -> SQS gtc-light-queue (visibility 300 s, heartbeat-extended) -> gtc-light-dlq (after 3 receives)
  -> ECS worker service (1 vCPU / 2 GB, desired 0..N, no inbound)
       RUNNING -> ForwardModel r8 (same engine call as the old synchronous route) -> S3 result -> SUCCEEDED
  -> CloudWatch: JSON logs, metric filters, alarms -> SNS email; one dashboard
  SQS gtc-heavy-queue -> gtc-heavy-dlq: provisioned for account analysis, no producer or consumer yet
Terraform state: S3 (versioned, encrypted, native lock file)
```

## Decisions and why

| Decision | Why | Rejected alternative and why |
|---|---|---|
| **ECS Fargate** | The ForwardModel is CPU-heavy, long-running and already containerized; no servers to manage | **Lambda**: functions are capped at 15 minutes and suit short request-style work; account analyses run for hours and need multi-core processes. **EKS**: a Kubernetes control plane and upgrades are not justified for two services |
| **SQS jobs instead of synchronous requests** | API Gateway HTTP APIs time out integrations at 30 s, far below a ~100 s team evaluation; long synchronous requests are fragile regardless of the gateway (client disconnects, deploys, retries); account workloads take minutes to hours; asynchronous jobs give retries, persistence, status tracking and independent worker scaling | Longer synchronous timeouts: an ALB *can* be configured with a long idle timeout, but that only moves the problem: no retries, no status, the work dies with the connection |
| **DynamoDB (jobs) + S3 (results)** | Single-item status lookups, conditional writes for safe worker state transitions, TTL cleanup, no idle cost; results are JSON documents of any size | **RDS**: ~$13+/month idle, patching and backups, and relational queries GTC does not need |
| **Input-hash result reuse** | The engine is deterministic for a given version, data and search settings; identical requests return the stored result instantly and survive restarts and scaling | **Redis/ElastiCache**: an always-on cache for a workload whose results are already durable in S3 |
| **API Gateway HTTP API + VPC Link + Cloud Map** | Stable HTTPS URL without owning a domain (AWS certificate), built-in throttling, IAM authorization, ~$0 idle | **ALB**: ~$16/month plus ~$7/month of public IPv4 always on, and trusted HTTPS needs a custom domain |
| **AWS_IAM (SigV4) authorization** | AWS-native, no homemade secrets; callers sign with their own IAM credentials | A shared API key in Parameter Store: a long-lived static secret that must be rotated and can leak |
| **Public subnets, no NAT gateway** | A NAT gateway is ~$32/month plus data charges. No task accepts internet traffic: the API only from the VPC Link's security group, workers from nothing. Free gateway endpoints keep S3 and DynamoDB traffic on the AWS network | Private subnets + NAT or interface endpoints: the production upgrade, documented, not built |
| **OIDC for GitHub Actions** | No long-lived AWS keys in GitHub; one-hour credentials scoped to one repo and branch | Stored access keys |
| **Remote Terraform state (S3, native locking)** | Infrastructure is not tied to one workstation; versioned state; concurrent runs are blocked | Local state; a DynamoDB lock table (deprecated mechanism) |
| **Separate light and heavy lanes, separate DLQs** | Different runtimes (minutes vs hours), different worker sizes, clearer alarms and IAM boundaries | One shared queue or DLQ |

## Operating facts worth knowing

- **API at zero tasks:** API Gateway cannot start an ECS task. With the API service at desired count 0, the gateway
  returns 503. To demo: start the API service (and a worker), use it, scale back to 0.
- **Workers at zero:** jobs wait in the queue (4-day retention) and the "queue stale" alarm fires after 30 minutes.
- **Heartbeat:** the worker extends its message's visibility every 60 s by 300 s. If an extension fails, the lease is
  treated as lost: the (idempotent) result is still written, but the stale receipt is not used. SQS caps a message's
  invisibility at 12 h after it is received; the worker stops extending at 11.5 h. That bounds the longest supported
  job; the expected 2.5 h account analysis fits.
- **Result identity:** a stored result equals the synchronous engine call for the same input when the search finishes
  before its time limit (verified by `tests/test_jobs_engine.py`). If the limit is reached, how much was searched
  depends on CPU speed; the result records `limit_hit`, and the deduplicated result is whichever run computed first.
- **Authorization progression:** today IAM/SigV4 (CLI and scripts). A browser frontend must not hold AWS credentials,
  so it will use Cognito user pools with a JWT authorizer on the same routes.

## Not built yet

Heavy (account) worker and its data packaging (see `docs/account-analysis-audit.md`), queue-depth autoscaling with
task scale-in protection, private subnets / interface endpoints, custom domain, frontend, WAF, multi-environment.
