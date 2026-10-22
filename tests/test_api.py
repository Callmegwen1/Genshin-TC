"""API tests (api/main.py): health, request validation, the one-at-a-time rule, and one real evaluation.

The real evaluation uses a 5 s base-search limit so the test stays short; the engine's own default is untouched.
"""
from __future__ import annotations

import pytest

fastapi = pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

from api import main  # noqa: E402

TEAM = ["Kamisato Ayaka", "Shenhe", "Kaedehara Kazuha", "Yelan"]
client = TestClient(main.app)


@pytest.fixture(autouse=True)
def _clean():
    main._cache.clear()
    yield
    main._cache.clear()
    if main._busy.locked():
        main._busy.release()


def _no_engine(monkeypatch):
    def boom(*a, **k):
        raise AssertionError("the engine must not run for this request")
    import gtc.forward.blind as blind
    monkeypatch.setattr(blind, "theorycraft", boom)


def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["supported_characters"] == len(main.SUPPORTED) >= 26


def test_supported_names_match_kit_files_exactly():
    # the names come from the directory listing, so they keep the case Linux needs to open the files
    for name in main.SUPPORTED:
        assert (main.KIT_DIR / f"{name}.yaml").is_file()


def test_unsupported_character_is_422_and_never_reaches_the_engine(monkeypatch):
    _no_engine(monkeypatch)
    r = client.post("/evaluate", json={"lineup": ["Kamisato Ayaka", "Shenhe", "Kaedehara Kazuha", "Diluc"]})
    assert r.status_code == 422
    detail = r.json()["detail"]
    assert detail["unsupported"] == ["Diluc"]
    assert "Yelan" in detail["supported"]


def test_duplicate_and_wrong_length_are_422(monkeypatch):
    _no_engine(monkeypatch)
    assert client.post("/evaluate", json={"lineup": ["Yelan", "Yelan", "Shenhe", "Bennett"]}).status_code == 422
    assert client.post("/evaluate", json={"lineup": ["Yelan", "Shenhe", "Bennett"]}).status_code == 422
    assert client.post("/evaluate", json={"lineup": "Yelan"}).status_code == 422


def test_names_are_case_insensitive_and_canonicalised():
    assert main._canonical(["kamisato ayaka", "SHENHE", "Kaedehara kazuha", " yelan "]) == TEAM


def test_second_evaluation_while_busy_is_429(monkeypatch):
    _no_engine(monkeypatch)
    main._busy.acquire()
    r = client.post("/evaluate", json={"lineup": TEAM})
    assert r.status_code == 429
    assert r.headers["retry-after"] == "60"


def test_cached_result_is_served_even_while_busy(monkeypatch):
    _no_engine(monkeypatch)
    main._cache[tuple(TEAM)] = {"lineup": TEAM, "dps": 1}
    main._busy.acquire()
    r = client.post("/evaluate", json={"lineup": TEAM})
    assert r.status_code == 200 and r.json()["cached"] is True


def test_real_evaluation(monkeypatch):
    from gtc.forward import generator
    monkeypatch.setattr(generator, "SEARCH_SECONDS", 5.0)
    r = client.post("/evaluate", json={"lineup": TEAM})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["cached"] is False
    assert body["dps"] > 5000
    assert set(body["per_character_dps"]) == set(TEAM)
    assert abs(sum(body["damage_share"].values()) - 1) < 0.02
    s = body["search"]
    assert s["time_limit_seconds"] == 5.0
    assert s["ended_by_time_limit"] == (s["limit_hit"] == "time")
    assert not main._busy.locked()
