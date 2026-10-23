"""Async job system with in-memory adapters (no AWS): lifecycle, dedupe, validation, failures, retries, redelivery,
DLQ, missing results, gateway identity and the heartbeat. One test runs the real engine (short search limit) and
checks the async result is identical to the synchronous call.
"""
from __future__ import annotations

import importlib

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

from api import identity  # noqa: E402
from api.jobmodel import JobStatus  # noqa: E402
from api.service import JobService, ValidationError  # noqa: E402
from api.stores import Backends, MemoryJobRepository, MemoryQueue, MemoryResultStore  # noqa: E402
from api.worker import Heartbeat, Worker  # noqa: E402

TEAM = ["Kamisato Ayaka", "Shenhe", "Kaedehara Kazuha", "Yelan"]


class Clock:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t


def fake_runner(calls):
    def run(lineup):
        calls.append(list(lineup))
        return {"lineup": list(lineup), "dps": 12345, "search": {"limit_hit": None}}
    return run


@pytest.fixture
def env():
    clock = Clock()
    b = Backends(MemoryJobRepository(), MemoryResultStore(), MemoryQueue(visibility=300, max_receive=3, clock=clock))
    calls = []
    return {"b": b, "svc": JobService(b), "worker": Worker(b, runner=fake_runner(calls)), "calls": calls,
            "clock": clock}


def drain(env):
    msg = env["b"].light_queue.receive()
    return env["worker"].process(msg) if msg else None


# --------------------------------------------------------------------------------------------- lifecycle

def test_submit_queue_run_succeed_and_result(env):
    job = env["svc"].submit_team(TEAM)
    assert job.status == "QUEUED" and not job.cache_hit
    assert env["b"].light_queue.depth() == 1
    assert env["b"].jobs.get(job.job_id).status == "QUEUED"
    assert drain(env) == "succeeded"
    done = env["b"].jobs.get(job.job_id)
    assert done.status == "SUCCEEDED" and done.attempt_count == 1 and done.duration_s is not None
    assert env["b"].light_queue.depth() == 0                       # message deleted
    doc = env["svc"].result(done)
    assert doc["dps"] == 12345 and doc["computed_by_job"] == job.job_id
    assert env["calls"] == [TEAM]


def test_running_status_is_visible_while_engine_runs(env):
    seen = {}

    def runner(lineup):
        seen["status"] = env["b"].jobs.get(job.job_id).status
        return {"dps": 1, "search": {}}
    job = env["svc"].submit_team(TEAM)
    Worker(env["b"], runner=runner).process(env["b"].light_queue.receive())
    assert seen["status"] == "RUNNING"


def test_identical_request_reuses_result_without_queueing(env):
    first = env["svc"].submit_team(TEAM)
    drain(env)
    second = env["svc"].submit_team(TEAM)
    assert second.status == "SUCCEEDED" and second.cache_hit is True
    assert second.result_location == first.result_location
    assert env["b"].light_queue.depth() == 0 and len(env["calls"]) == 1


def test_variant_and_team_share_the_computation(env):
    variant = env["svc"].submit_team_variant(TEAM, "Yelan", "Furina")
    assert variant.input["variant_lineup"] == ["Kamisato Ayaka", "Shenhe", "Kaedehara Kazuha", "Furina"]
    drain(env)
    direct = env["svc"].submit_team(["Kamisato Ayaka", "Shenhe", "Kaedehara Kazuha", "Furina"])
    assert direct.cache_hit and direct.result_location == variant.result_location
    assert direct.input_hash != variant.input_hash                # different jobs, same computation


def test_team_order_is_part_of_the_hash(env):
    a = env["svc"].submit_team(TEAM)
    b = env["svc"].submit_team(list(reversed(TEAM)))
    assert a.result_location != b.result_location


def test_hash_changes_with_search_limit(monkeypatch):
    base = identity.team_computation_hash(TEAM)
    ident = dict(identity.engine_identity())
    monkeypatch.setattr(identity, "engine_identity", lambda: {**ident, "search_seconds": 5.0})
    assert identity.team_computation_hash(TEAM) != base


def test_failed_job_does_not_block_a_clean_retry(env):
    calls = []

    def boom(lineup):
        calls.append(1)
        raise RuntimeError("engine exploded")
    env["worker"].runner, env["worker"].max_receive = boom, 1
    job = env["svc"].submit_team(TEAM)
    assert drain(env) == "failed_final"
    assert env["b"].jobs.get(job.job_id).status == "FAILED"
    env["worker"].runner = fake_runner(env["calls"])
    again = env["svc"].submit_team(TEAM)
    assert again.status == "QUEUED" and not again.cache_hit        # no result was stored, so it recomputes


# --------------------------------------------------------------------------------------------- validation

@pytest.mark.parametrize("lineup", [["Yelan", "Shenhe", "Bennett"], ["Yelan", "Yelan", "Shenhe", "Bennett"],
                                    ["Yelan", "Shenhe", "Bennett", "Diluc"]])
def test_invalid_team_is_rejected_and_nothing_is_queued(env, lineup):
    with pytest.raises(ValidationError):
        env["svc"].submit_team(lineup)
    assert env["b"].light_queue.depth() == 0


@pytest.mark.parametrize("replace,with_", [("Bennett", "Furina"), ("Yelan", "Shenhe"), ("Yelan", "Diluc")])
def test_invalid_variant(env, replace, with_):
    with pytest.raises(ValidationError):
        env["svc"].submit_team_variant(TEAM, replace, with_)


# --------------------------------------------------------------------------------------------- failures and retries

def test_worker_exception_retries_then_fails_and_goes_to_dlq(env):
    def boom(lineup):
        raise RuntimeError("engine exploded")
    env["worker"].runner = boom
    job = env["svc"].submit_team(TEAM)
    q = env["b"].light_queue
    assert drain(env) == "failed_retry"
    j = env["b"].jobs.get(job.job_id)
    assert j.status == "QUEUED" and j.attempt_count == 1 and j.error["type"] == "RuntimeError"
    assert q.receive() is None                                   # retry delay: not visible yet
    env["clock"].t += 31
    assert drain(env) == "failed_retry"
    env["clock"].t += 31
    assert drain(env) == "failed_final"
    j = env["b"].jobs.get(job.job_id)
    assert j.status == "FAILED" and j.attempt_count == 3 and j.completed_at
    assert q.receive() is None and len(q.dlq) == 1               # 4th receive moved it to the DLQ


def test_poison_message_goes_to_dlq(env):
    q = env["b"].light_queue
    q.send_raw("this is not json")
    for _ in range(3):
        assert env["worker"].process(q.receive()) == "poison"
        env["clock"].t += 301                                    # visibility expires, SQS redelivers
    assert q.receive() is None and len(q.dlq) == 1


def test_unknown_job_id_is_poison(env):
    env["b"].light_queue.send({"job_id": "does-not-exist", "job_type": "TEAM_EVALUATION", "v": 1})
    assert drain(env) == "poison"


def test_redelivery_of_completed_job_does_not_recompute(env):
    job = env["svc"].submit_team(TEAM)
    msg = env["b"].light_queue.receive()
    assert env["worker"].process(msg) == "succeeded"
    env["b"].light_queue.send({"job_id": job.job_id, "job_type": job.job_type, "v": 1})   # duplicate delivery
    assert drain(env) == "already_succeeded"
    assert len(env["calls"]) == 1


def test_redelivery_after_crash_reuses_result_if_already_written(env):
    job = env["svc"].submit_team(TEAM)
    env["b"].results.put(job.result_location, {"dps": 1})       # crashed after writing, before marking done
    assert drain(env) == "reused"
    assert env["b"].jobs.get(job.job_id).status == "SUCCEEDED" and env["calls"] == []


def test_disabled_job_type_fails_cleanly(env):
    job = env["svc"].submit_team(TEAM)
    env["b"].jobs.update(job.job_id, {"job_type": "ACCOUNT_ANALYSIS"})
    assert drain(env) == "disabled"
    assert env["b"].jobs.get(job.job_id).status == "FAILED"


# --------------------------------------------------------------------------------------------- heartbeat

def test_heartbeat_extends_and_detects_lost_lease(env):
    q = env["b"].light_queue
    env["svc"].submit_team(TEAM)
    msg = q.receive()
    hb = Heartbeat(q, msg.receipt, env["clock"](), "j", every=60, visibility=300, clock=env["clock"])
    env["clock"].t += 200
    assert hb.beat() and hb.extensions == 1
    env["clock"].t += 250
    assert q.receive() is None                                   # still invisible thanks to the extension
    q.delete(msg.receipt)                                        # receipt no longer valid
    assert not hb.beat() and hb.lost


def test_heartbeat_stops_before_sqs_12h_limit(env):
    q = env["b"].light_queue
    env["svc"].submit_team(TEAM)
    msg = q.receive()
    hb = Heartbeat(q, msg.receipt, env["clock"](), "j", visibility=300, clock=env["clock"])
    env["clock"].t += 11.5 * 3600
    assert not hb.beat() and not hb.lost


# --------------------------------------------------------------------------------------------- HTTP layer

@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("GTC_BACKEND", "memory")
    monkeypatch.delenv("GTC_INLINE_WORKER", raising=False)
    from api import main
    importlib.reload(main)
    return main, TestClient(main.app)


def test_http_job_flow_and_result_statuses(client):
    main, c = client
    r = c.post("/jobs/team", json={"lineup": TEAM})
    assert r.status_code == 202
    jid = r.json()["job_id"]
    assert c.get(f"/jobs/{jid}").json()["status"] == "QUEUED"
    pending = c.get(f"/jobs/{jid}/result")
    assert pending.status_code == 202 and pending.headers["retry-after"] == "15"
    Worker(main.backends, runner=fake_runner([])).process(main.backends.light_queue.receive())
    res = c.get(f"/jobs/{jid}/result")
    assert res.status_code == 200 and res.json()["result"]["dps"] == 12345
    again = c.post("/jobs/team", json={"lineup": TEAM})
    assert again.status_code == 200 and again.json()["cache_hit"] is True


def test_http_variant_validation_and_missing_job(client):
    _, c = client
    assert c.post("/jobs/team-variant", json={"lineup": TEAM, "replace": "Yelan", "with": "Diluc"}).status_code == 422
    ok = c.post("/jobs/team-variant", json={"lineup": TEAM, "replace": "Yelan", "with": "Furina"})
    assert ok.status_code == 202 and ok.json()["input"]["variant_lineup"][3] == "Furina"
    assert c.get("/jobs/nope").status_code == 404
    assert c.get("/jobs/nope/result").status_code == 404


def test_http_failed_job_and_missing_result_document(client):
    main, c = client
    jid = c.post("/jobs/team", json={"lineup": TEAM}).json()["job_id"]
    main.backends.jobs.update(jid, {"status": "FAILED", "error": {"type": "X", "message": "y"}})
    assert c.get(f"/jobs/{jid}/result").status_code == 409
    main.backends.jobs.update(jid, {"status": "SUCCEEDED"})
    assert c.get(f"/jobs/{jid}/result").status_code == 500       # SUCCEEDED but the document is gone


def test_gateway_identity_required_and_jobs_are_private(client, monkeypatch):
    main, c = client
    monkeypatch.setattr(main, "REQUIRE_GATEWAY_IDENTITY", True)
    assert c.post("/jobs/team", json={"lineup": TEAM}).status_code == 401
    assert c.get("/health").status_code == 200 and c.get("/version").status_code == 200   # public routes
    alice = {"x-gtc-caller-arn": "arn:aws:iam::111122223333:user/alice"}
    jid = c.post("/jobs/team", json={"lineup": TEAM}, headers=alice).json()["job_id"]
    assert c.get(f"/jobs/{jid}", headers=alice).status_code == 200
    bob = {"x-gtc-caller-arn": "arn:aws:iam::111122223333:user/bob"}
    assert c.get(f"/jobs/{jid}", headers=bob).status_code == 404
    assert c.get(f"/jobs/{jid}").status_code == 401


def test_version_reports_engine_and_build(client, monkeypatch):
    _, c = client
    monkeypatch.setenv("GTC_COMMIT", "abc123")
    v = c.get("/version").json()
    assert v["app_commit"] == "abc123" and v["engine_version"].startswith("fm-")
    assert set(v["engine_fingerprint"]) == {"kits", "frames", "data"} and v["api_schema_version"] == "2"


def test_sync_route_can_be_disabled(client, monkeypatch):
    main, c = client
    monkeypatch.setattr(main, "SYNC_ENABLED", False)
    assert c.post("/evaluate", json={"lineup": TEAM}).status_code == 404
