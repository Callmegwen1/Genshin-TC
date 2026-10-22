"""Cloud API for the theorycrafting engine: a thin FastAPI wrapper around the forward model's blind theorycraft.

    GET  /health     liveness: {"status": "ok", ...}
    POST /evaluate   {"lineup": ["A", "B", "C", "D"]} -> predicted team DPS from kits alone

Only characters with a hand-written forward-model kit (knowledge/forward/actions/*.yaml) are accepted. Any other
name is rejected with 422 *before* the engine runs, because the engine's fallback for those characters is to run
gcsim (a Windows binary that is not in the container).

One prediction runs at a time (they are CPU-bound, about a minute each); a second concurrent request gets 429.
Finished results are cached in memory, so a repeated lineup answers instantly and is never refused.

Logs are one JSON object per line on stdout. ECS's awslogs driver ships stdout to CloudWatch Logs.
"""
from __future__ import annotations

import json
import logging
import os
import sys
import threading
import time
import uuid
from collections import OrderedDict
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from gtc import KNOWLEDGE_DIR  # noqa: E402
from gtc.forward import FORWARD_VERSION  # noqa: E402

KIT_DIR = KNOWLEDGE_DIR / "forward" / "actions"
CACHE_SIZE = int(os.environ.get("GTC_RESULT_CACHE", "64"))


# ---- logging: JSON lines on stdout ------------------------------------------------------------------------------
class _JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        out = {"ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(record.created)), "level": record.levelname,
               "msg": record.getMessage()}
        out.update(getattr(record, "fields", {}))
        if record.exc_info:
            out["exc"] = self.formatException(record.exc_info)
        return json.dumps(out, default=str)


log = logging.getLogger("gtc.api")
if not log.handlers:
    _h = logging.StreamHandler(sys.stdout)
    _h.setFormatter(_JsonFormatter())
    log.addHandler(_h)
    log.setLevel(logging.INFO)
    log.propagate = False


def _log(msg: str, level: int = logging.INFO, exc_info=False, **fields) -> None:
    log.log(level, msg, extra={"fields": fields}, exc_info=exc_info)


# ---- supported characters ---------------------------------------------------------------------------------------
def supported_characters() -> list[str]:
    """Characters with a hand-written kit file. Read from the directory listing, so the names keep the exact case of
    the files (Linux filesystems are case-sensitive)."""
    return sorted(p.stem for p in KIT_DIR.glob("*.yaml"))


SUPPORTED = supported_characters()
_BY_LOWER = {n.lower(): n for n in SUPPORTED}


class EvaluateRequest(BaseModel):
    lineup: list[str] = Field(..., min_length=4, max_length=4,
                              examples=[["Kamisato Ayaka", "Shenhe", "Kaedehara Kazuha", "Yelan"]])


# ---- concurrency and cache ---------------------------------------------------------------------------------------
_busy = threading.Lock()
_cache: "OrderedDict[tuple, dict]" = OrderedDict()
_cache_lock = threading.Lock()

app = FastAPI(title="Genshin Theorycrafting Engine API", version=FORWARD_VERSION,
              description="Team DPS predicted from character kits by the forward model (stable subset).")


@app.middleware("http")
async def access_log(request: Request, call_next):
    rid = request.headers.get("x-request-id") or uuid.uuid4().hex[:12]
    t0 = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception:
        _log("unhandled error", logging.ERROR, exc_info=True, request_id=rid, path=request.url.path)
        raise
    response.headers["x-request-id"] = rid
    _log("request", request_id=rid, method=request.method, path=request.url.path, status=response.status_code,
         ms=round((time.perf_counter() - t0) * 1000), client=request.client.host if request.client else None)
    return response


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "engine_version": FORWARD_VERSION, "supported_characters": len(SUPPORTED)}


def _canonical(lineup: list[str]) -> list[str]:
    names, unknown = [], []
    for raw in lineup:
        n = _BY_LOWER.get(raw.strip().lower())
        (names.append(n) if n else unknown.append(raw))
    if unknown:
        raise HTTPException(422, {"error": "unsupported character", "unsupported": unknown,
                                  "supported": SUPPORTED})
    if len(set(names)) != len(names):
        raise HTTPException(422, {"error": "a lineup cannot contain the same character twice", "lineup": names})
    return names


def _run(lineup: list[str]) -> dict:
    """Engine call. Imports are lazy so /health answers without loading the engine."""
    from gtc.forward.blind import theorycraft
    from gtc.forward.decompose import _label
    from gtc.forward.library import load_hand

    # defence in depth: never let a name without a kit file reach the gcsim fallback in library.build
    missing = [m for m in lineup if load_hand(m) is None]
    if missing:
        raise HTTPException(422, {"error": "unsupported character", "unsupported": missing, "supported": SUPPORTED})

    r = theorycraft(lineup, profile="neutral")
    ev = r["evaluation"]
    search = r.get("search") or {}
    return {
        "lineup": lineup,
        "engine_version": FORWARD_VERSION,
        "dps": round(ev.dps),
        "total_damage": round(ev.total_damage),
        "rotation_seconds": round(ev.rotation_duration, 2),
        "strategy": _label(r["plan"]),
        "per_character_dps": {k: round(v) for k, v in ev.per_character.items()},
        "damage_share": {k: round(v, 4) for k, v in ev.damage_share.items()},
        "per_reaction": {k: round(v) for k, v in ev.per_reaction.items()},
        "top_buffs": dict(sorted(((k, round(v, 4)) for k, v in ev.buff_contributions.items()),
                                 key=lambda kv: -kv[1])[:10]),
        "field_time": {k: round(v, 2) for k, v in ev.field_time.items()},
        "energy": ev.energy,
        "coverage": round(ev.coverage, 4),
        "uncertainty_relative_sd": round(ev.uncertainty, 4),
        "confidence": ev.confidence,
        "unknown": ev.unknown,
        "assumptions": ev.assumptions,
        "search": {
            "candidates_evaluated": search.get("evaluated"),
            "base_search_seconds": search.get("seconds"),
            "time_limit_seconds": search.get("time_limit_seconds"),
            "limit_hit": search.get("limit_hit"),            # "time", "plans" or null
            "ended_by_time_limit": search.get("limit_hit") == "time",
            "note": search.get("bounded") or None,
        },
    }


@app.post("/evaluate")
def evaluate(req: EvaluateRequest) -> JSONResponse:
    # sync endpoint: FastAPI runs it in a worker thread, so /health stays responsive during a prediction
    lineup = _canonical(req.lineup)
    key = tuple(lineup)
    with _cache_lock:
        if key in _cache:
            _cache.move_to_end(key)
            return JSONResponse({**_cache[key], "cached": True})
    if not _busy.acquire(blocking=False):
        _log("evaluation refused: busy", logging.WARNING, lineup=lineup)
        return JSONResponse({"error": "another evaluation is running; retry later"}, status_code=429,
                            headers={"Retry-After": "60"})
    t0 = time.perf_counter()
    try:
        _log("evaluation started", lineup=lineup)
        out = _run(lineup)
        out["seconds"] = round(time.perf_counter() - t0, 1)
        _log("evaluation finished", lineup=lineup, dps=out["dps"], seconds=out["seconds"],
             limit_hit=out["search"]["limit_hit"], candidates=out["search"]["candidates_evaluated"])
    except HTTPException:
        raise
    except Exception as e:  # noqa: BLE001
        _log("evaluation failed", logging.ERROR, exc_info=True, lineup=lineup)
        raise HTTPException(500, {"error": "the engine could not evaluate this lineup", "type": type(e).__name__})
    finally:
        _busy.release()
    with _cache_lock:
        _cache[key] = out
        while len(_cache) > CACHE_SIZE:
            _cache.popitem(last=False)
    return JSONResponse({**out, "cached": False})
