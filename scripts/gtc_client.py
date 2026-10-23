"""Tiny SigV4 client for the GTC jobs API (API Gateway with AWS_IAM authorization).

Signs requests with your current AWS credentials (e.g. after `aws login`), so no API key exists anywhere.

    python scripts/gtc_client.py URL team "Kamisato Ayaka" Shenhe "Kaedehara Kazuha" Yelan
    python scripts/gtc_client.py URL variant "Kamisato Ayaka" Shenhe "Kaedehara Kazuha" Yelan --replace Yelan --with Furina
    python scripts/gtc_client.py URL status <job_id>
    python scripts/gtc_client.py URL result <job_id>
    python scripts/gtc_client.py URL wait <job_id>          # poll until SUCCEEDED or FAILED, printing each status change
    python scripts/gtc_client.py URL version                # public, unsigned

URL is `terraform output -raw api_url`.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request

REGION = "us-east-2"


def call(url: str, method: str, path: str, body: dict | None = None, sign: bool = True) -> tuple[int, dict]:
    data = json.dumps(body).encode() if body is not None else None
    headers = {"Content-Type": "application/json"} if data else {}
    if sign:
        import boto3
        from botocore.auth import SigV4Auth
        from botocore.awsrequest import AWSRequest

        creds = boto3.Session().get_credentials()
        if creds is None:
            sys.exit("no AWS credentials: run `aws login` first")
        req = AWSRequest(method=method, url=url.rstrip("/") + path, data=data, headers=headers)
        SigV4Auth(creds.get_frozen_credentials(), "execute-api", REGION).add_auth(req)
        headers = dict(req.headers)
    r = urllib.request.Request(url.rstrip("/") + path, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(r, timeout=30) as resp:
            return resp.status, json.loads(resp.read() or b"{}")
    except urllib.error.HTTPError as e:
        raw = e.read()
        try:
            return e.code, json.loads(raw or b"{}")
        except ValueError:
            return e.code, {"raw": raw.decode(errors="replace")[:300]}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("url")
    ap.add_argument("action", choices=["team", "variant", "status", "result", "wait", "version"])
    ap.add_argument("args", nargs="*")
    ap.add_argument("--replace")
    ap.add_argument("--with", dest="with_")
    a = ap.parse_args()
    if a.action == "version":
        out = call(a.url, "GET", "/version", sign=False)
    elif a.action == "team":
        out = call(a.url, "POST", "/jobs/team", {"lineup": a.args})
    elif a.action == "variant":
        out = call(a.url, "POST", "/jobs/team-variant", {"lineup": a.args, "replace": a.replace, "with": a.with_})
    elif a.action == "status":
        out = call(a.url, "GET", f"/jobs/{a.args[0]}")
    elif a.action == "result":
        out = call(a.url, "GET", f"/jobs/{a.args[0]}/result")
    else:
        t0, last = time.time(), None
        while True:
            code, job = call(a.url, "GET", f"/jobs/{a.args[0]}")
            st = job.get("status")
            if st != last:
                print(f"t={time.time() - t0:5.0f}s  HTTP {code}  {st}  {job.get('status_message', '')}")
                last = st
            if st in ("SUCCEEDED", "FAILED") or code >= 400:
                break
            time.sleep(5)
        out = (code, job)
    print(out[0])
    print(json.dumps(out[1], indent=1)[:4000])


if __name__ == "__main__":
    main()
