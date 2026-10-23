"""Job submission and lookup (API side). Validation, dedupe, job creation and enqueueing; no engine work here.

Dedupe: every request is reduced to a computation hash (api/identity.py). If a result for that hash already exists in
the result store, the job is created directly as SUCCEEDED with cache_hit = true and nothing is queued. A failed
earlier job leaves no result, so the same request is simply recomputed.
"""
from __future__ import annotations

import time

from api import identity
from api.engine_adapter import supported_characters
from api.jobmodel import Job, JobStatus, JobType, new_job_id, utc_now
from api.logs import event, get_logger
from api.stores import Backends

log = get_logger("gtc.api")
JOB_TTL_DAYS = 30


class ValidationError(ValueError):
    def __init__(self, detail: dict):
        super().__init__(detail.get("error", "invalid request"))
        self.detail = detail


class JobService:
    def __init__(self, backends: Backends):
        self.b = backends
        self._supported = supported_characters()
        self._by_lower = {n.lower(): n for n in self._supported}

    # ---------------------------------------------------------------- validation
    def canonical_names(self, names: list[str]) -> list[str]:
        out, unknown = [], []
        for raw in names:
            n = self._by_lower.get(str(raw).strip().lower())
            (out.append(n) if n else unknown.append(raw))
        if unknown:
            raise ValidationError({"error": "unsupported character", "unsupported": unknown,
                                   "supported": self._supported})
        return out

    def team(self, lineup: list[str]) -> list[str]:
        if not isinstance(lineup, list) or len(lineup) != 4:
            raise ValidationError({"error": "a team is exactly four character names"})
        names = self.canonical_names(lineup)
        if len(set(names)) != 4:
            raise ValidationError({"error": "a team cannot contain the same character twice", "lineup": names})
        return names

    # ---------------------------------------------------------------- submission
    def submit_team(self, lineup: list[str], caller: str = "") -> Job:
        team = self.team(lineup)
        return self._submit(JobType.TEAM_EVALUATION, {"lineup": team}, team, caller)

    def submit_team_variant(self, lineup: list[str], replace: str, with_: str, caller: str = "") -> Job:
        team = self.team(lineup)
        [out_name] = self.canonical_names([replace])
        [in_name] = self.canonical_names([with_])
        if out_name not in team:
            raise ValidationError({"error": "replace must be a member of the team", "replace": out_name})
        if in_name in team:
            raise ValidationError({"error": "the new character is already in the team", "with": in_name})
        variant = [in_name if m == out_name else m for m in team]   # same slot, same order
        return self._submit(JobType.TEAM_VARIANT, {"lineup": team, "replace": out_name, "with": in_name,
                                                   "variant_lineup": variant}, variant, caller)

    def _submit(self, job_type: JobType, normalized: dict, compute_lineup: list[str], caller: str) -> Job:
        comp = identity.team_computation_hash(compute_lineup)
        key = identity.result_key(comp)
        ver = identity.version_info()
        now = utc_now()
        job = Job(job_id=new_job_id(), job_type=job_type.value, status=JobStatus.QUEUED.value, created_at=now,
                  engine_version=ver["engine_version"], app_commit=ver["app_commit"],
                  input_hash=identity.job_input_hash(job_type.value, normalized, comp), input=normalized,
                  result_location=key, submitted_by=caller, expires_at=int(time.time()) + JOB_TTL_DAYS * 86400,
                  status_message="queued")
        if self.b.results.exists(key):
            job.status, job.cache_hit = JobStatus.SUCCEEDED.value, True
            job.started_at = job.completed_at = now
            job.status_message = "identical result reused"
            self.b.jobs.create(job)
            event(log, "job_reused", job_id=job.job_id, job_type=job.job_type, input_hash=job.input_hash)
            return job
        self.b.jobs.create(job)
        self.b.light_queue.send({"job_id": job.job_id, "job_type": job.job_type, "v": 1})
        event(log, "job_submitted", job_id=job.job_id, job_type=job.job_type, input_hash=job.input_hash,
              engine_version=job.engine_version)
        return job

    # ---------------------------------------------------------------- lookup
    def get(self, job_id: str, caller: str = "") -> Job | None:
        job = self.b.jobs.get(job_id)
        if job is None:
            return None
        if caller and job.submitted_by and job.submitted_by != caller:
            return None     # another principal's job: indistinguishable from "not found"
        return job

    def result(self, job: Job) -> dict | None:
        return self.b.results.get(job.result_location)
