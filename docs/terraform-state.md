# Terraform remote state

Since 2026-10-23 the GTC infrastructure state lives in S3, not on one workstation.

| Item | Value |
|---|---|
| State bucket | `gtc-tfstate-<account-id>`, us-east-2, created by `infra/bootstrap/` |
| Main stack state | `gtc/staging/terraform.tfstate` |
| Bootstrap state | `bootstrap/terraform.tfstate` (same bucket) |
| Locking | Native S3 lock file (`use_lockfile = true`, Terraform >= 1.10): a `<key>.tflock` object exists only while an operation runs. No DynamoDB table |
| Protection | Versioning on; SSE-S3 (AES256); all four Block Public Access settings; ACLs disabled (bucket owner enforced); TLS-only bucket policy; `prevent_destroy` on the bucket |
| History | Old state versions kept 90 days, and the 20 most recent are always kept |

## Using it on any machine

```
cd infra
cp backend.hcl.example backend.hcl        # put the account ID in the bucket name
aws login                                 # region us-east-2
terraform init -backend-config=backend.hcl
terraform plan
```

`terraform.tfvars` is not in git (it holds the allowed IP and budget email); copy it or recreate it from
`terraform.tfvars.example`.

## Why the bootstrap module exists

The state bucket has to exist before any backend can use it. `infra/bootstrap/` creates only that bucket. It was applied
once with local state, then its own state was moved into the bucket it created. It never needs to change again.

## Migration record (2026-10-23)

1. Pre-checks: `terraform plan` on `infra/` reported **No changes**; local state serial 37, 28 managed resources.
2. Backups (identical copies, SHA-256 in `SHA256SUMS`):
   - `infra/state-backups/2026-10-23-pre-migration/` (git-ignored)
   - `Documents/GTC terraform state backups/2026-10-23-pre-migration/`
3. `infra/bootstrap`: plan 7 to add; applied; settings verified with the S3 API.
4. Bootstrap state moved into the bucket; its plan: **No changes**.
5. Main stack: `backend "s3"` added to `infra/providers.tf`; `terraform init -migrate-state -backend-config=backend.hcl`.
6. Verification:
   - Remote state readable (`terraform state pull`): the same 33 addresses and identical attributes and outputs as the
     backup. Terraform wrote it as a new snapshot (serial 1, new lineage); content is unchanged.
   - Locking: during one `terraform plan`, a second run with `-lock-timeout=0s` failed with
     "Error acquiring the state lock"; the lock object disappeared when the first run ended.
   - `terraform plan -detailed-exitcode`: exit code 0 (no changes) for both stacks.
7. The empty local `terraform.tfstate` and its `.backup` were moved to
   `infra/state-backups/2026-10-23-post-migration-local-leftovers/`, so no local file can be mistaken for the real state.

## Recovery

- **Bad apply:** restore an earlier object version of `gtc/staging/terraform.tfstate` from the bucket's version history.
- **Stuck lock** (a crashed run left `terraform.tfstate.tflock`): confirm nothing is running, then
  `terraform force-unlock <lock id>`.
- **The pre-migration local backup has a different lineage**, so Terraform will refuse to `state push` it over the
  remote state without `-force`. Use it only for comparison or disaster recovery.
