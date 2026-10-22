"""Model versioning: tunable values live in knowledge/model.yaml, and changes are tracked."""
import ast
from pathlib import Path

import yaml

from gtc import params

ROOT = Path(__file__).resolve().parents[1] / "gtc"
SCORING_MODULES = ["account", "report", "estimate", "knowledge", "teams", "capabilities", "validity", "synergy",
                   "pairmodel", "investment", "sim", "evidence", "derive", "review", "audit", "artifacts", "aoe",
                   "profiles", "kitgen"]
# Module constants that are game facts, data layouts or labels, not tunable judgments.
ALLOWED = {
    "ARTIFACT_MAX_LEVEL", "MAX_QUALITY", "LEVEL_CAPS", "LUNAR_DIRECT_TAGS", "TRANSFORMATIVE", "CATALYZE",
    "NORMAL_ATTACK_TAG", "AMP_AURA", "REACTION_AURAS", "CORE_REACTIONS", "REACTING", "REACTIVE", "TIERS",
    "PARTNER_PRIORITY", "TEMPLATE_FOR", "FLAT_DMG_PROVIDERS", "TEAM_SET_KEYS", "TIER_TEXT", "OTHER",
    "PRYDWEN_TIER_VALUE", "TIER_QUALITY", "EFFORT_ORDER", "ENABLED", "SUSTAIN_ROLES", "_FALLBACK",
    "TUNE_GRID", "STAT_RE", "HELPERS", "GENERATED_EXTRAS", "SNAP",
    "SET_CRIT_BONUS",  # the crit rate a set grants (Blizzard Strayer 40%): a game fact
    "AVG_ROLL",  # one average 5-star substat roll: a game fact
}


def _numeric(node) -> bool:
    if isinstance(node, ast.Constant):
        return isinstance(node.value, (int, float)) and not isinstance(node.value, bool)
    if isinstance(node, ast.UnaryOp):
        return _numeric(node.operand)
    if isinstance(node, (ast.List, ast.Tuple, ast.Set)):
        return any(_numeric(e) for e in node.elts)
    if isinstance(node, ast.Dict):
        return any(_numeric(v) for v in node.values if v is not None)
    return False


def test_no_hand_chosen_numbers_outside_model_yaml():
    """Module-level constants with numbers in scoring code must come from knowledge/model.yaml (params.get)
    or be on the allowlist of game facts. Numbers inside function bodies are not scanned."""
    offenders = []
    for mod in SCORING_MODULES:
        path = ROOT / f"{mod}.py"
        for node in ast.parse(path.read_text(encoding="utf-8")).body:
            targets = node.targets if isinstance(node, ast.Assign) else [node.target] if isinstance(node, ast.AnnAssign) else []
            value = getattr(node, "value", None)
            for t in targets:
                if isinstance(t, ast.Name) and t.id.isupper() and t.id not in ALLOWED and value is not None and _numeric(value):
                    offenders.append(f"{mod}.{t.id}")
    assert not offenders, f"move these to knowledge/model.yaml or allowlist them as game facts: {offenders}"


def test_every_model_value_is_used():
    for key in params.flat():
        section, name = key.split(".", 1)
        text = (ROOT / f"{section}.py").read_text(encoding="utf-8")
        assert f'params.get("{key}")' in text, f"{key} in model.yaml is not read by gtc/{section}.py"


def test_parameter_changes_are_versioned_and_benchmarked():
    from gtc.benchmark import RESULTS_PATH
    assert RESULTS_PATH.exists(), "run `python -m gtc benchmark --record`"
    recorded = yaml.safe_load(RESULTS_PATH.read_text(encoding="utf-8")) or {}
    entry = recorded.get(params.version())
    assert entry, f"model {params.version()} has no recorded benchmark run: `python -m gtc benchmark --record`"
    assert entry["fingerprint"] == params.fingerprint(), (
        "knowledge/model.yaml or scoring.yaml changed since the benchmark was recorded for this version: "
        "bump model_version and run `python -m gtc benchmark --record`")
