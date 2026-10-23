"""What exactly produced a result: deployment identity (GET /version) and the computation hash used for dedupe.

The computation hash covers everything that can change a ForwardModel team result:
  - the engine's own fingerprint (gtc.forward.hidden.fingerprint: version, kit actions, frame data),
  - a hash of all packaged data the engine reads (knowledge/ and the Amber game-data cache),
  - search settings (time limit, plan limit) and the build profile,
  - the team itself, in the order given (the engine is not assumed to be order-independent).
Code changes that move numbers bump FORWARD_VERSION by project rule, so the app commit is NOT part of the hash (a
redeploy of identical engine code keeps its cached results).
"""
from __future__ import annotations

import hashlib
import json
import os
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PROFILE = "neutral"
API_SCHEMA_VERSION = "2"
EXCLUDED_DATA = {"my_teams.yaml"}   # personal file, never packaged in the image


def canonical(obj) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def sha256(obj) -> str:
    return hashlib.sha256(canonical(obj).encode()).hexdigest()


@lru_cache(maxsize=1)
def data_fingerprint() -> str:
    """SHA-256 over the packaged engine data: knowledge/ (minus personal files) and the Amber cache."""
    h = hashlib.sha256()
    roots = [ROOT / "knowledge", ROOT / "data" / "sources" / "cache" / "amber"]
    for base in roots:
        if not base.exists():
            continue
        for p in sorted(x for x in base.rglob("*") if x.is_file() and x.name not in EXCLUDED_DATA):
            h.update(p.relative_to(ROOT).as_posix().encode())
            h.update(p.read_bytes())
    return h.hexdigest()


@lru_cache(maxsize=1)
def engine_identity() -> dict:
    from gtc.forward.generator import MAX_PLANS, SEARCH_SECONDS
    from gtc.forward.hidden import fingerprint

    f = fingerprint()
    return {"engine_version": f["version"], "kits_sha256": f["kits_sha256"], "frames_sha256": f["frames_sha256"],
            "data_sha256": data_fingerprint(), "search_seconds": SEARCH_SECONDS, "max_plans": MAX_PLANS,
            "profile": PROFILE}


def team_computation_hash(lineup: list[str]) -> str:
    return sha256({"computation": "TEAM", "lineup": list(lineup), **engine_identity()})


def result_key(computation_hash: str) -> str:
    """results/<engine-version>/<computation-hash>.json"""
    return f"results/{engine_identity()['engine_version']}/{computation_hash}.json"


def job_input_hash(job_type: str, normalized_input: dict, computation_hash: str) -> str:
    return sha256({"job_type": job_type, "input": normalized_input, "computation": computation_hash})


def version_info() -> dict:
    """Safe deployment facts. Build facts come from image build args; nothing secret is read."""
    ident = engine_identity()
    return {
        "app_commit": os.environ.get("GTC_COMMIT", "local"),
        "image_tag": os.environ.get("GTC_IMAGE_TAG", "local"),
        "build_time": os.environ.get("GTC_BUILD_TIME", "unknown"),
        "engine_version": ident["engine_version"],
        "engine_fingerprint": {"kits": ident["kits_sha256"][:12], "frames": ident["frames_sha256"][:12],
                               "data": ident["data_sha256"][:12]},
        "search_seconds": ident["search_seconds"],
        "api_schema_version": API_SCHEMA_VERSION,
    }
