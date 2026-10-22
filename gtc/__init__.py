"""gtc: Genshin theorycrafting engine. Deterministic scoring over curated data."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
KNOWLEDGE_DIR = ROOT / "knowledge"
SNAPSHOT_DIR = ROOT / "data" / "snapshots"
REPORT_DIR = ROOT / "reports"
