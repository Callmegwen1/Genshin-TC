"""Cloud API for the theorycrafting engine (FastAPI).

Async job API (the normal path):
    POST /jobs/team            {"lineup": [4 names]}                          -> 202 job
    POST /jobs/team-variant    {"lineup": [...], "replace": X, "with": Y}     -> 202 job
    GET  /jobs/{job_id}        status, attempts, timestamps, error
    GET  /jobs/{job_id}/result result document once SUCCEEDED
Public:
    GET  /health, GET /version
Legacy / debug only:
    POST /evaluate             synchronous ForwardModel call (~40-100 s). Disabled in AWS (ENABLE_SYNC_EVALUATE=0):
                               API Gateway's 30 s integration timeout cannot carry it and the API task is sized small.

Authorization happens at API Gateway (AWS_IAM / SigV4 on /jobs routes). The gateway overwrites the
x-gtc-caller-arn header with the signed caller's IAM ARN. With REQUIRE_GATEWAY_IDENTITY=1 (set in AWS) the app rejects
/jobs requests that lack it, as defence in depth; jobs are visible only to the principal that submitted them.

Only characters with a hand-written forward-model kit are accepted (422 otherwise), because the engine's fallback for
other characters needs gcsim, which is not in the image.
"""
from __future__ import annotations

import os
import sys
import threading
import time
import uuid
from collections import OrderedDict
from pathlib import Path

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from api import identity  # noqa: E402
from api.engine_adapter import KIT_DIR, UnsupportedCharacter, run_team, supported_characters  # noqa: E402
from api.jobmodel import JobStatus  # noqa: E402
from api.logs import event, get_logger  # noqa: E402
from api.service import JobService, ValidationError  # noqa: E402
from api.stores import from_environment  # noqa: E402
from gtc.forward import FORWARD_VERSION  # noqa: E402

log = get_logger("gtc.api")
CACHE_SIZE = int(os.environ.get("GTC_RESULT_CACHE", "64"))
SYNC_ENABLED = os.environ.get("ENABLE_SYNC_EVALUATE", "1") == "1"
REQUIRE_GATEWAY_IDENTITY = os.environ.get("REQUIRE_GATEWAY_IDENTITY", "0") == "1"
CALLER_HEADER = "x-gtc-caller-arn"

SUPPORTED = supported_characters()
_BY_LOWER = {n.lower(): n for n in SUPPORTED}

backends = from_environment()
jobs = JobService(backends)

app = FastAPI(title="Genshin Theorycrafting Engine API", version=FORWARD_VERSION,
              description="ForwardModel team evaluation as asynchronous jobs (stable subset of the engine).")


class TeamRequest(BaseModel):
    lineup: list[str] = Field(..., min_length=4, max_length=4,
                              examples=[["Kamisato Ayaka", "Shenhe", "Kaedehara Kazuha", "Yelan"]])


class TeamVariantRequest(BaseModel):
    lineup: list[str] = Field(..., min_length=4, max_length=4)
    replace: str = Field(..., min_length=1, max_length=64)
    with_: str = Field(..., alias="with", min_length=1, max_length=64)


EvaluateRequest = TeamRequest   # legacy name


@app.middleware("http")
async def access_log(request: Request, call_next):
    rid = request.headers.get("x-request-id") or uuid.uuid4().hex[:12]
    t0 = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception:
        event(log, "unhandled error", 40, exc_info=True, request_id=rid, path=request.url.path)
        raise
    response.headers["x-request-id"] = rid
    event(log, "request", request_id=rid, method=request.method, path=request.url.path,
          status=response.status_code, ms=round((time.perf_counter() - t0) * 1000),
          client=request.client.host if request.client else None)
    return response


# ------------------------------------------------------------------------------------------- public

@app.get("/health")
def health() -> dict:
    return {"status": "ok", "engine_version": FORWARD_VERSION, "supported_characters": len(SUPPORTED)}


@app.get("/version")
def version() -> dict:
    return {**identity.version_info(), "sync_evaluate_enabled": SYNC_ENABLED}


# ------------------------------------------------------------------------------------------- jobs

def _caller(arn: str | None) -> str:
    if REQUIRE_GATEWAY_IDENTITY and not arn:
        raise HTTPException(401, {"error": "requests must come through the API gateway with IAM authorization"})
    return arn or ""


def _job_response(job, code: int = 202) -> JSONResponse:
    body = job.public()
    body["links"] = {"self": f"/jobs/{job.job_id}", "result": f"/jobs/{job.job_id}/result"}
    return JSONResponse(body, status_code=code)


@app.post("/jobs/team")
def submit_team(req: TeamRequest, x_gtc_caller_arn: str | None = Header(default=None)) -> JSONResponse:
    caller = _caller(x_gtc_caller_arn)
    try:
        job = jobs.submit_team(req.lineup, caller)
    except ValidationError as e:
        event(log, "validation_failed", route="/jobs/team", error=e.detail.get("error"))
        raise HTTPException(422, e.detail)
    return _job_response(job, 200 if job.cache_hit else 202)


@app.post("/jobs/team-variant")
def submit_team_variant(req: TeamVariantRequest, x_gtc_caller_arn: str | None = Header(default=None)) -> JSONResponse:
    caller = _caller(x_gtc_caller_arn)
    try:
        job = jobs.submit_team_variant(req.lineup, req.replace, req.with_, caller)
    except ValidationError as e:
        event(log, "validation_failed", route="/jobs/team-variant", error=e.detail.get("error"))
        raise HTTPException(422, e.detail)
    return _job_response(job, 200 if job.cache_hit else 202)


@app.get("/jobs/{job_id}")
def get_job(job_id: str, x_gtc_caller_arn: str | None = Header(default=None)) -> dict:
    job = jobs.get(job_id, _caller(x_gtc_caller_arn))
    if job is None:
        raise HTTPException(404, {"error": "job not found"})
    return job.public()


@app.get("/jobs/{job_id}/result")
def get_result(job_id: str, x_gtc_caller_arn: str | None = Header(default=None)) -> JSONResponse:
    job = jobs.get(job_id, _caller(x_gtc_caller_arn))
    if job is None:
        raise HTTPException(404, {"error": "job not found"})
    event(log, "result_requested", job_id=job_id, status=job.status)
    if job.status in (JobStatus.QUEUED.value, JobStatus.RUNNING.value):
        return JSONResponse({"job_id": job_id, "status": job.status, "status_message": job.status_message},
                            status_code=202, headers={"Retry-After": "15"})
    if job.status == JobStatus.FAILED.value:
        return JSONResponse({"job_id": job_id, "status": job.status, "error": job.error}, status_code=409)
    doc = _hot_get(job.result_location)
    if doc is None:
        event(log, "result_missing", 40, job_id=job_id, result_location=job.result_location)
        return JSONResponse({"job_id": job_id, "status": job.status, "error": "result document is missing"},
                            status_code=500)
    return JSONResponse({"job_id": job_id, "job_type": job.job_type, "input": job.input, "cache_hit": job.cache_hit,
                         "result": doc})


_hot: "OrderedDict[str, dict]" = OrderedDict()   # small in-process hot cache in front of the result store
_hot_lock = threading.Lock()


def _hot_get(key: str) -> dict | None:
    with _hot_lock:
        if key in _hot:
            _hot.move_to_end(key)
            return _hot[key]
    doc = backends.results.get(key)
    if doc is not None:
        with _hot_lock:
            _hot[key] = doc
            while len(_hot) > CACHE_SIZE:
                _hot.popitem(last=False)
    return doc


# ------------------------------------------------------------------------------------------- legacy / debug

_busy = threading.Lock()
_cache: "OrderedDict[tuple, dict]" = OrderedDict()
_cache_lock = threading.Lock()


def _canonical(lineup: list[str]) -> list[str]:
    try:
        return jobs.team(lineup)
    except ValidationError as e:
        raise HTTPException(422, e.detail)


def _run(lineup: list[str]) -> dict:
    try:
        return run_team(lineup)
    except UnsupportedCharacter as e:
        raise HTTPException(422, {"error": "unsupported character", "unsupported": e.names, "supported": SUPPORTED})


@app.post("/evaluate", deprecated=True)
def evaluate(req: TeamRequest) -> JSONResponse:
    """LEGACY / DEBUG: synchronous evaluation. Use POST /jobs/team."""
    if not SYNC_ENABLED:
        raise HTTPException(404, {"error": "synchronous evaluation is disabled here; use POST /jobs/team"})
    lineup = _canonical(req.lineup)
    key = tuple(lineup)
    with _cache_lock:
        if key in _cache:
            _cache.move_to_end(key)
            return JSONResponse({**_cache[key], "cached": True})
    if not _busy.acquire(blocking=False):
        event(log, "evaluation refused: busy", 30, lineup=lineup)
        return JSONResponse({"error": "another evaluation is running; retry later"}, status_code=429,
                            headers={"Retry-After": "60"})
    t0 = time.perf_counter()
    try:
        event(log, "evaluation started", lineup=lineup)
        out = _run(lineup)
        out["seconds"] = round(time.perf_counter() - t0, 1)
        event(log, "evaluation finished", lineup=lineup, dps=out["dps"], seconds=out["seconds"],
              limit_hit=out["search"]["limit_hit"], candidates=out["search"]["candidates_evaluated"])
    except HTTPException:
        raise
    except Exception as e:  # noqa: BLE001
        event(log, "evaluation failed", 40, exc_info=True, lineup=lineup)
        raise HTTPException(500, {"error": "the engine could not evaluate this lineup", "type": type(e).__name__})
    finally:
        _busy.release()
    with _cache_lock:
        _cache[key] = out
        while len(_cache) > CACHE_SIZE:
            _cache.popitem(last=False)
    return JSONResponse({**out, "cached": False})


# local convenience: GTC_INLINE_WORKER=1 runs a worker thread inside the API process (memory backend demos only)
if os.environ.get("GTC_INLINE_WORKER") == "1" and os.environ.get("GTC_BACKEND", "memory") == "memory":
    from api.worker import Worker

    threading.Thread(target=Worker(backends).run_forever, kwargs={"wait_seconds": 1}, daemon=True).start()
