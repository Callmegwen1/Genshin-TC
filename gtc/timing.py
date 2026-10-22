"""Stage timings and work counters for `--timings`. Cheap enough to leave on: a dict increment per event."""
from __future__ import annotations

import time
from collections import Counter, defaultdict
from contextlib import contextmanager

COUNTS: Counter = Counter()
STAGES: dict[str, float] = defaultdict(float)
_ORDER: list[str] = []


def count(name: str, n: int = 1) -> None:
    COUNTS[name] += n


@contextmanager
def stage(name: str):
    start = time.perf_counter()
    try:
        yield
    finally:
        if name not in STAGES:
            _ORDER.append(name)
        STAGES[name] += time.perf_counter() - start


def reset() -> None:
    COUNTS.clear()
    STAGES.clear()
    _ORDER.clear()


def report() -> str:
    lines = ["Stage                              Seconds", "---------------------------------  -------"]
    lines += [f"{name:<34} {STAGES[name]:7.2f}" for name in _ORDER]
    lines += ["", "Counter                            Count", "---------------------------------  -------"]
    lines += [f"{k:<34} {v:7d}" for k, v in sorted(COUNTS.items())]
    hits = [(k[:-4], COUNTS[k], COUNTS.get(k[:-4] + "_miss", 0)) for k in COUNTS if k.endswith("_hit")]
    if hits:
        lines += ["", "Cache                              Hit rate"]
        lines += [f"{k:<34} {h / (h + m):7.0%}" for k, h, m in sorted(hits) if h + m]
    return "\n".join(lines)


_OPEN: dict[str, float] = {}


def start(name: str) -> None:
    _OPEN[name] = time.perf_counter()


def stop(name: str) -> None:
    began = _OPEN.pop(name, None)
    if began is not None:
        if name not in STAGES:
            _ORDER.append(name)
        STAGES[name] += time.perf_counter() - began
