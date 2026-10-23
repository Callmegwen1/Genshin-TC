"""Slow (about 1-2 minutes): the asynchronous path returns exactly the synchronous ForwardModel result.

Run by the validation workflow, not the deploy gate. Identity is only guaranteed when the search finishes before its
time limit: a time-bounded search depends on CPU speed (see docs/aws-architecture.md, "Result identity").
"""
from __future__ import annotations

import pytest

pytest.importorskip("fastapi")

from api.engine_adapter import run_team  # noqa: E402
from api.service import JobService  # noqa: E402
from api.stores import Backends, MemoryJobRepository, MemoryQueue, MemoryResultStore  # noqa: E402
from api.worker import Worker  # noqa: E402

LINEUP = ["Neuvillette", "Furina", "Kaedehara Kazuha", "Zhongli"]


def test_async_result_is_identical_to_synchronous_call():
    from gtc.forward import generator

    sync = run_team(LINEUP)
    b = Backends(MemoryJobRepository(), MemoryResultStore(), MemoryQueue())
    job = JobService(b).submit_team(LINEUP)
    assert Worker(b).process(b.light_queue.receive()) == "succeeded"
    stored = b.results.get(job.result_location)
    assert sync["search"]["limit_hit"] is None and stored["search"]["limit_hit"] is None, \
        f"search hit its {generator.SEARCH_SECONDS} s limit; identity is not guaranteed"
    extra = {"computed_seconds", "computed_by_job", "engine_identity"}

    def strip(d):   # wall-clock timing is not part of the result
        return {k: ({x: y for x, y in v.items() if x != "base_search_seconds"} if k == "search" else v)
                for k, v in d.items() if k not in extra}
    assert strip(stored) == strip(sync)
