"""Asynchronous job model: types, statuses and the job record shared by the API and the worker.

Job lifecycle (ordinary path):  QUEUED -> RUNNING -> SUCCEEDED
                       failure: RUNNING -> QUEUED (retry, error recorded) ... -> FAILED (final attempt)
A job whose result already exists is created directly as SUCCEEDED with cache_hit = true (nothing is queued).

Possible later statuses (not implemented): CANCELLED, EXPIRED.
"""
from __future__ import annotations

import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum


class JobType(str, Enum):
    TEAM_EVALUATION = "TEAM_EVALUATION"   # one four-character team through the ForwardModel
    TEAM_VARIANT = "TEAM_VARIANT"         # replace one slot of a team, evaluate the resulting team
    # reserved, disabled: not runnable in the cloud yet (see docs/account-analysis-audit.md)
    ACCOUNT_ANALYSIS = "ACCOUNT_ANALYSIS"
    WHAT_IF = "WHAT_IF"                   # account-level counterfactual: add a character, recompute the account
    PULL_RANKING = "PULL_RANKING"


ENABLED_TYPES = frozenset({JobType.TEAM_EVALUATION, JobType.TEAM_VARIANT})
LIGHT_TYPES = frozenset({JobType.TEAM_EVALUATION, JobType.TEAM_VARIANT})   # the light queue / light worker lane


class JobStatus(str, Enum):
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def new_job_id() -> str:
    return uuid.uuid4().hex


@dataclass
class Job:
    job_id: str
    job_type: str
    status: str
    created_at: str
    engine_version: str
    app_commit: str
    input_hash: str              # identity of the requested computation (dedupe key)
    input: dict                  # normalized request input (small; no private data)
    result_location: str         # result-store key the worker writes and GET /result reads
    started_at: str | None = None
    completed_at: str | None = None
    attempt_count: int = 0
    status_message: str = ""
    error: dict | None = None    # {"type": ..., "message": ...}; no stack traces
    cache_hit: bool = False      # true when an identical earlier result was reused
    submitted_by: str = ""       # caller identity from the API gateway (IAM principal ARN)
    duration_s: float | None = None
    expires_at: int | None = None  # epoch seconds; DynamoDB TTL
    extra: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "Job":
        known = {k: d[k] for k in cls.__dataclass_fields__ if k in d}
        return cls(**known)

    def public(self) -> dict:
        """What GET /jobs/{id} returns (no caller identity, no internal fields)."""
        d = self.to_dict()
        for k in ("submitted_by", "expires_at", "extra"):
            d.pop(k, None)
        return d
