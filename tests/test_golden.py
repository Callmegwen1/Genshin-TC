"""Golden-output regression: the engine's conclusions for fixed accounts must not change silently.
Update deliberately with `python -m gtc golden --update --reason "..."`, which logs the change."""
import pytest

from gtc import SNAPSHOT_DIR
from gtc.golden import GOLDEN_DIR

pytestmark = pytest.mark.skipif(not any(GOLDEN_DIR.glob("*.json")) or not any(SNAPSHOT_DIR.glob("*.json")),
                                reason="needs stored golden outputs and a snapshot")


def test_engine_outputs_match_the_golden_files():
    from gtc.golden import check
    diffs = check()
    assert not diffs, "\n".join(diffs[:60]) + f"\n{len(diffs)} differences; if intended, run python -m gtc golden --update --reason ..."
