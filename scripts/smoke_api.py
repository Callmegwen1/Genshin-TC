"""Smoke test for a running API (local uvicorn, Docker, or the ECS task's public IP). Standard library only.

    python scripts/smoke_api.py http://127.0.0.1:8000

Checks, in order: /health is 200; an unsupported character is 422; two simultaneous /evaluate calls give one 200
and one 429; the 200 has a DPS and reports whether the deployment time limit ended its search. Exit code 0 when
every check passes.
"""
from __future__ import annotations

import json
import sys
import threading
import time
import urllib.error
import urllib.request

TEAM_A = ["Kamisato Ayaka", "Shenhe", "Kaedehara Kazuha", "Yelan"]
TEAM_B = ["Neuvillette", "Furina", "Kaedehara Kazuha", "Zhongli"]


def call(base: str, method: str, path: str, body=None, timeout: float = 600) -> tuple[int, dict]:
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(base.rstrip("/") + path, data=data, method=method,
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"{}")


def main(base: str) -> int:
    ok = True

    def check(name: str, cond: bool, info="") -> None:
        nonlocal ok
        ok &= bool(cond)
        print(f"[{'PASS' if cond else 'FAIL'}] {name} {info}")

    s, b = call(base, "GET", "/health", timeout=10)
    check("GET /health is 200 ok", s == 200 and b.get("status") == "ok", b)

    s, b = call(base, "POST", "/evaluate", {"lineup": ["Kamisato Ayaka", "Shenhe", "Kaedehara Kazuha", "Diluc"]}, 10)
    check("unsupported character is 422", s == 422 and b.get("detail", {}).get("unsupported") == ["Diluc"],
          b.get("detail", {}).get("error"))

    results: dict[str, tuple] = {}

    def run(tag, team):
        t0 = time.time()
        results[tag] = (*call(base, "POST", "/evaluate", {"lineup": team}), round(time.time() - t0, 1))

    first = threading.Thread(target=run, args=("first", TEAM_A))
    first.start()
    time.sleep(2)                       # the first request now holds the evaluation slot
    run("second", TEAM_B)
    s2, b2, t2 = results["second"]
    check("simultaneous second evaluation is 429", s2 == 429, f"({t2} s) {b2}")
    s, _ = call(base, "GET", "/health", timeout=10)
    check("/health answers while an evaluation runs", s == 200)
    first.join()
    s1, b1, t1 = results["first"]
    search = b1.get("search", {})
    check("first evaluation is 200 with a DPS", s1 == 200 and b1.get("dps", 0) > 0,
          f"({t1} s) dps={b1.get('dps')} strategy={b1.get('strategy')!r}")
    check("response states whether the time limit ended the search", "ended_by_time_limit" in search,
          f"limit={search.get('time_limit_seconds')} s, limit_hit={search.get('limit_hit')}, "
          f"candidates={search.get('candidates_evaluated')}")

    s, b = call(base, "POST", "/evaluate", {"lineup": TEAM_A}, 10)
    check("repeat lineup is served from cache", s == 200 and b.get("cached") is True)
    print("ALL PASS" if ok else "SOME CHECKS FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000"))
