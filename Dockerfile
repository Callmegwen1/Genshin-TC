# Genshin Theorycrafting Engine API: the forward model behind FastAPI, for ECS Fargate (linux/amd64).
FROM python:3.14.4-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    # serve the baked-in Project Amber cache at any age; never call the network at runtime
    GTC_CACHE_OFFLINE=1 \
    # cloud base-search limit (the engine's own default is 120 s); override per task definition
    GTC_SEARCH_SECONDS=60

WORKDIR /app

# dependencies first: this layer is reused until requirements.txt changes
COPY api/requirements.txt api/requirements.txt
RUN pip install -r api/requirements.txt

# code and data are owned by root and read-only for the app user; the engine writes nothing in offline mode
COPY gtc/ gtc/
COPY knowledge/ knowledge/
COPY data/sources/cache/amber/ data/sources/cache/amber/
COPY api/ api/
RUN python -m compileall -q gtc api \
 && test "$(ls data/sources/cache/amber | wc -l)" -gt 300 \
 && useradd --system --uid 10001 --no-create-home --shell /usr/sbin/nologin app

USER 10001
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=4)"]

# one worker: predictions are CPU-bound and the API runs one at a time by design
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1", "--no-access-log"]
