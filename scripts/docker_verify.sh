#!/usr/bin/env bash
# Build the API image and verify it end to end (run from the repo root after installing Docker):
#   bash scripts/docker_verify.sh
# 1. build linux/amd64 (the Fargate platform)   2. inspect what entered the image   3. Linux case check
# 4. run the container and the HTTP smoke test  5. print the container's JSON logs
set -euo pipefail
IMAGE=gtc-api:local
docker build --platform linux/amd64 -t "$IMAGE" .

echo "== image size"; docker image ls "$IMAGE" --format '{{.Repository}}:{{.Tag}} {{.Size}}'

echo "== image contents (must be only api, gtc, knowledge, data/sources/cache/amber)"
docker run --rm --entrypoint sh "$IMAGE" -c '
  set -e
  id
  find /app -maxdepth 3 -type d | sort
  echo "files: $(find /app -type f | wc -l)  size: $(du -sh /app | cut -f1)"
  bad=$(find /app \( -name ".env" -o -name "*.pkl" -o -name "*.exe" -o -name "*.sample.json" -o -path "*/snapshots/*" -o -path "*/sims/*" -o -path "*/validation/*" -o -name my_teams.yaml \) | head)
  [ -z "$bad" ] && echo "no private or large data: OK" || { echo "FOUND: $bad"; exit 1; }
  touch /app/x 2>/dev/null && { echo "app user can write /app: FAIL"; exit 1; } || echo "app dir read-only for app user: OK"
'

echo "== Linux filename case: every supported character, opened by its exact name, plus a short evaluation"
docker run --rm -e GTC_SEARCH_SECONDS=3 --entrypoint python "$IMAGE" -c '
from api import main
from gtc.forward.library import load_hand
assert all(load_hand(n) is not None for n in main.SUPPORTED), "a kit file did not open"
print(len(main.SUPPORTED), "kit files open by exact name")
assert load_hand("kamisato ayaka") is None, "case-insensitive filesystem?"
print("lower-case name does not resolve: Linux is case-sensitive, the API canonicalises names")
for i in range(0, 28, 4):
    t = (main.SUPPORTED * 2)[i:i + 4]
    print(t, main._run(list(dict.fromkeys(t)))["dps"])
'

echo "== run and smoke test"
docker rm -f gtc-api >/dev/null 2>&1 || true
docker run -d --name gtc-api -p 8000:8000 --cpus 1 --memory 2g "$IMAGE" >/dev/null
for _ in $(seq 30); do curl -fs localhost:8000/health >/dev/null && break; sleep 1; done
python scripts/smoke_api.py http://127.0.0.1:8000
echo "== health status"; docker inspect --format '{{.State.Health.Status}}' gtc-api
echo "== container logs (JSON lines, what CloudWatch will receive)"; docker logs gtc-api 2>&1 | tail -12
docker rm -f gtc-api >/dev/null
