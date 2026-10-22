"""External sources: gcsim's team database, Prydwen and Keqing Mains.

Each module downloads politely (cached, rate limited), parses into plain JSON under
data/sources/, and never edits the curated knowledge files. data/sources/ is git-ignored
because it is third-party content for personal use.
"""
from gtc import ROOT

SOURCE_DIR = ROOT / "data" / "sources"
CACHE_DIR = SOURCE_DIR / "cache"
