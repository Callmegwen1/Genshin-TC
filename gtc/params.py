"""The engine's tunable values, from knowledge/model.yaml.

Modules read their constants here at import time:

    PLAN_WEIGHTS = params.get("account.plan_weights")

`apply(overrides)` sets new values on the already imported modules (the benchmark tuner uses it), so a key
"account.plan_weights" maps to the attribute PLAN_WEIGHTS of gtc.account.
"""
from __future__ import annotations

import hashlib
import importlib
from functools import lru_cache

import yaml

from gtc import KNOWLEDGE_DIR

MODEL_PATH = KNOWLEDGE_DIR / "model.yaml"
SCORING_PATH = KNOWLEDGE_DIR / "scoring.yaml"


@lru_cache(maxsize=1)
def load() -> dict:
    return yaml.safe_load(MODEL_PATH.read_text(encoding="utf-8")) or {}


def get(key: str):
    """A value by dotted key, such as "account.plan_weights"."""
    d = load()
    for part in key.split("."):
        if not isinstance(d, dict) or part not in d:
            raise KeyError(f"knowledge/model.yaml has no {key}")
        d = d[part]
    return d


def version() -> str:
    return str(load().get("model_version", "unversioned"))


def fingerprint() -> str:
    """Hash of everything tunable: model.yaml and scoring.yaml. A change needs a version bump and a benchmark run."""
    h = hashlib.sha256()
    for path in (MODEL_PATH, SCORING_PATH):
        h.update(path.read_bytes().replace(b"\r\n", b"\n"))
    return h.hexdigest()[:16]


def flat() -> dict[str, object]:
    """Every value as {"section.name": value}, except the version."""
    return {f"{section}.{name}": v for section, values in load().items() if isinstance(values, dict)
            for name, v in values.items()}


def apply(overrides: dict[str, object]) -> dict[str, object]:
    """Set values on the imported modules; returns the previous values so they can be restored."""
    previous = {}
    for key, value in overrides.items():
        section, name = key.split(".", 1)
        module = importlib.import_module(f"gtc.{section}")
        attr = name.upper()
        if not hasattr(module, attr):
            raise KeyError(f"gtc.{section} has no {attr}")
        previous[key] = getattr(module, attr)
        setattr(module, attr, value)
    return previous
