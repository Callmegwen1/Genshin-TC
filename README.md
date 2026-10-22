# Genshin Theorycrafting Engine — AWS Cloud Deployment

**Python · FastAPI · Docker · AWS ECS Fargate · ECR · S3 · IAM (OIDC) · VPC · CloudWatch · Terraform · GitHub Actions**

The underlying theorycrafting engine is under active development. This deployment exposes a stable subset of its
functionality through a cloud-hosted API and focuses on reproducible infrastructure, containerization, automated
deployment, and observability.

The engine predicts a Genshin Impact team's damage per second **from character kits alone**: it builds candidate
rotations, resolves buffs, reactions, field time and energy on a timeline, and scores each rotation with the game's
damage formulas. The API serves the frozen forward model (`fm-2026.10.21-r8`) for the 26 characters that have a
hand-written kit.

## Architecture

```
 developer ── git push ──► GitHub ──► GitHub Actions
                                        │  1. fast tests (204, ~1 min)
                                        │  2. OIDC → short-lived AWS credentials (no stored keys)
                                        │  3. S3 cache ──► docker build ──► ECR (tag = commit SHA)
                                        │  4. new task-definition revision ──► ECS service update
                                        ▼
 ┌──────────────────────────── AWS us-east-2 ─────────────────────────────┐
 │  VPC 10.20.0.0/16                                                      │
 │   public subnet (AZ a)      public subnet (AZ b)      internet gateway │
 │   ┌──────────────────────────────┐                                     │
 │   │ ECS Fargate task (1 vCPU/2GB)│◄── :8000 from one allowed IP only   │
 │   │ FastAPI + engine, non-root,  │    (security group)                 │
 │   │ read-only filesystem         │                                     │
 │   └──────────────┬───────────────┘                                     │
 │                  │ stdout JSON lines (awslogs driver)                  │
 │                  ▼                                                     │
 │           CloudWatch Logs /ecs/gtc-api        AWS Budget → email       │
 └────────────────────────────────────────────────────────────────────────┘
```

| Piece | Choice | Why this over the usual alternative |
|---|---|---|
| Compute | ECS on Fargate | No servers or cluster nodes to patch; far simpler than EKS for one service. |
| Image registry | ECR, immutable tags, scan on push | Same account and IAM as ECS; each tag is one commit forever, so deploys are traceable. |
| Network | Public subnets, public task IP | No NAT Gateway (~$32/mo) or load balancer (~$16/mo) for a demo. Trade-off: the IP changes on each deploy. |
| Access control | Security group: port 8000 from one /32 | The API is CPU-heavy and has no authentication, so only the owner can reach it. |
| CI → AWS auth | GitHub OIDC → IAM role, one repo, one branch | No long-lived AWS keys in GitHub; credentials last one hour. |
| Container permissions | Execution role only, no task role | ECS can pull the image and write logs; the app itself gets no AWS permissions. |
| Game-data cache | Private S3 bucket (encrypted, versioned, TLS only) | Third-party data for personal use stays out of git; CI pulls it at build time. |
| Infrastructure | Terraform | Reviewable plans, reproducible environments, one-command teardown. |
| Logs | stdout JSON → CloudWatch Logs, 14-day retention | Queryable by field in Logs Insights; retention bounds cost. |

## API

| Method | Path | Result |
|---|---|---|
| GET | `/health` | `{"status": "ok", "engine_version": "...", "supported_characters": 26}` |
| POST | `/evaluate` | Predicted DPS, strategy, per-character damage, damage shares, buffs, energy, uncertainty, search report |
| GET | `/docs` | Interactive OpenAPI docs (FastAPI) |

```bash
curl -s -X POST http://<task-ip>:8000/evaluate -H 'content-type: application/json' \
  -d '{"lineup": ["Kamisato Ayaka", "Shenhe", "Kaedehara Kazuha", "Yelan"]}'
```

Behaviour worth knowing:

- **422** for any character without a kit file (the engine's fallback runs gcsim, which is not in the container), for
  duplicates, and for lineups that are not exactly four names. Names are matched case-insensitively.
- **429** when another evaluation is running: one prediction at a time, by design (each takes ~40 s locally and
  ~100 s on a Fargate vCPU). Finished results are cached in memory and served even while busy.
- `search.ended_by_time_limit` says whether the deployment's search limit (`GTC_SEARCH_SECONDS`, 60 s in the cloud,
  120 s engine default) cut the rotation search short. On the teams tested it never did and results matched r8 exactly.

## Run it locally

```bash
python -m venv .venv && .venv/Scripts/pip install -e . -r api/requirements-dev.txt
.venv/Scripts/python -m uvicorn api.main:app --port 8000        # API without Docker
bash scripts/docker_verify.sh                                   # build the image and verify it end to end
python scripts/smoke_api.py http://127.0.0.1:8000               # health, 422, 429, evaluate, cache
```

The container needs the Project Amber cache in `data/sources/cache/amber/` (from `python -m gtc gamedata`, or from the
S3 bucket). `.dockerignore` is an allowlist: only `api/`, `gtc/`, `knowledge/` and that cache enter the build, so the
13 GB simulation archive, account snapshots and `.env` cannot.

## Deploy

Prerequisites: an AWS account (standalone; an organization SCP can block the OIDC provider), the AWS CLI logged in
(`aws login`), Terraform ≥ 1.6, Docker.

```bash
cd infra
cp terraform.tfvars.example terraform.tfvars      # your IP, budget email, GitHub repo
terraform init

# 1. registry and cache bucket first, so the service's first task finds an image
terraform apply -target=aws_ecr_repository.api -target=aws_s3_bucket.cache
aws s3 sync ../data/sources/cache/amber s3://$(terraform output -raw cache_bucket)/amber
aws ecr get-login-password | docker login --username AWS --password-stdin $(terraform output -raw ecr_repository_url | cut -d/ -f1)
docker tag gtc-api:local $(terraform output -raw ecr_repository_url):bootstrap
docker push $(terraform output -raw ecr_repository_url):bootstrap

# 2. everything else
terraform apply
bash ../scripts/ecs_ip.sh                          # the task's current public IP
```

Then in GitHub, under *Settings → Secrets and variables → Actions → Variables*, set `AWS_DEPLOY_ROLE_ARN` and
`CACHE_BUCKET` from `terraform output`. Every push to `main` now tests, builds, pushes and deploys.

**Operate**

```bash
aws logs tail /ecs/gtc-api --follow                                # live logs
terraform apply -var desired_count=0                               # pause compute charges, keep everything
terraform apply -var allowed_cidr=$(curl -s checkip.amazonaws.com)/32   # your home IP changed
terraform destroy                                                  # remove everything
```

## Cost

| Item | Approximate cost |
|---|---|
| Fargate task, 1 vCPU / 2 GB, running 24/7 | ~$1.20/day (~$36/month) |
| Public IPv4 address | ~$3.60/month |
| ECR, S3, CloudWatch Logs at demo volume | cents |
| Budget | $10/month alert at 50 %, 80 %, 100 % actual and 100 % forecast |

For a demo, apply, show it, and `terraform destroy` (or `desired_count=0`).

## Known limitations

- **Ephemeral IP.** Without a load balancer the task's public IP changes on every deployment or restart. Production
  upgrade: an Application Load Balancer (stable DNS name, health checks, TLS with ACM) and optionally Route 53.
- **One request at a time.** A second evaluation gets 429. Scaling upgrade: SQS job queue + workers, or more tasks
  behind the ALB with ECS Service Auto Scaling.
- **No authentication.** Access is limited by source IP only. Upgrade: API keys via API Gateway, or Cognito.
- **In-memory cache.** Results are lost when the task restarts.
- **Local Terraform state.** Fine for one person; upgrade to an S3 backend with locking for a team or CI-run Terraform.
- **CI cannot smoke-test the live task**, because the security group admits only the owner's IP; the workflow
  reports the new IP and the owner runs `scripts/smoke_api.py`.
- **Engine scope.** 26 characters with hand-written kits. The wider engine (account analysis, community-sim
  calibration, pull planning) is local-only and not exposed.

## Tests

- CI runs a fast subset (`tests/ci_fast.txt`): the API, forward model, formulas, reactions and golden regressions,
  204 tests in about a minute on a clean checkout.
- The full suite (415 tests, ~8 minutes) runs locally: `python -m pytest -q`. 48 of its tests need local-only data
  (HoYoLAB snapshots, community simulations) that is deliberately kept out of git.

## The engine (local use)

```
.venv/Scripts/python -m gtc gamedata # refresh every character in the game from Project Amber
.venv/Scripts/python -m gtc sources  # refresh gcsim, Prydwen and Keqing Mains data for every character (cached a week)
.venv/Scripts/python -m gtc synergy  # measure who buffs whom in every simulated lineup (about 40 minutes)
.venv/Scripts/python -m gtc derive   # rebuild role tags and archetypes for the whole game from that data
.venv/Scripts/python -m gtc import   # fetch roster from HoYoLAB into data/snapshots/
.venv/Scripts/python -m gtc teams    # write reports/teams-<date>.md
.venv/Scripts/python -m gtc review   # write reports/review-<date>.md, the account review
.venv/Scripts/python -m gtc account  # best four teams, carry check, what new characters would change, priorities
.venv/Scripts/python -m gtc theory --team "Flins,Ineffa,Columbina,Sucrose" --replace Ineffa --rank   # slot analysis from formulas
.venv/Scripts/python -m gtc.tc.validate   # check the calculator against gcsim
```

HoYoLAB cookie values live in `.env`, which git ignores. How the engine works: [docs/engine.md](docs/engine.md) and
[docs/forward-model.md](docs/forward-model.md). Everything subjective lives in `knowledge/`, never in code
(`characters.yaml`, `templates.yaml`, `scoring.yaml`, `sets.yaml`, `kits.yaml`; new characters go in `kits_custom/`).
