"""Polite HTTP with an on-disk cache, so repeated runs do not hit the sites again."""
from __future__ import annotations

import hashlib
import os
import time
import urllib.request
from pathlib import Path

from gtc.sources import CACHE_DIR

BROWSER_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36"
TOOL_UA = "genshin-theorycraft-personal/0.1"
_last_request = 0.0


def get(url: str, source: str, max_age_days: float = 7, delay: float = 1.0, browser: bool = True) -> str | None:
    """Return the body of url, from cache if fresh. None on 404. Waits `delay` seconds between live requests."""
    global _last_request
    path = CACHE_DIR / source / (hashlib.sha1(url.encode()).hexdigest()[:16] + ".html")
    if path.exists() and time.time() - path.stat().st_mtime < max_age_days * 86400:
        return path.read_text(encoding="utf-8")
    if os.environ.get("GTC_CACHE_OFFLINE") == "1":
        # the container ships a fixed cache: serve it whatever its age, and never call the network
        if path.exists():
            return path.read_text(encoding="utf-8")
        raise FileNotFoundError(f"GTC_CACHE_OFFLINE=1 and {url} is not in the cache")
    wait = delay - (time.time() - _last_request)
    if wait > 0:
        time.sleep(wait)
    req = urllib.request.Request(url, headers={"User-Agent": BROWSER_UA if browser else TOOL_UA, "Accept-Language": "en-US"})
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            body = resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None
        raise
    finally:
        _last_request = time.time()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")
    return body


def cached_path(url: str, source: str) -> Path:
    return CACHE_DIR / source / (hashlib.sha1(url.encode()).hexdigest()[:16] + ".html")
