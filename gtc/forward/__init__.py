"""First-principles forward model (phases FM-0 to FM-10): structured kits and builds → a rotation of damage events →
expected damage per event → team DPS, with buffs, conditions, reactions, field time and energy resolved on a timeline.

    data.py      game numbers from Project Amber: base stats by level, weapon stats, talent scaling tables
    build.py     builds: META_STANDARD (house), CURRENT_ACCOUNT (snapshot), ACCOUNT_CEILING
    trace.py     a rotation from a gcsim run (actions, hit events, energy, field segments), and the gcsim config
                 rendered with house builds for validation
    effects.py   kit effects as timeline effects (trigger, start, duration, amount, condition state)
    model.py     expected damage per event and the ForwardTeamEvaluation
    rotation.py  composed rotations from per-character action libraries; field windows and energy feasibility
    validate.py  forward vs house gcsim vs community, by team

FORWARD MODEL IS NUMERIC POWER. TEAMMECHANICS IS LOGICAL COMPATIBILITY: the reasoner never multiplies DPS, and this
package never decides recommendability. Damage formulas are reused from gtc/tc/formulas.py, reactions from
gtc/reactions.py; nothing is duplicated. Deterministic expected values (crit as an average), no Monte Carlo.
"""

# bumped whenever a change can move forward numbers; recorded with every benchmark result (gtc/forward/results.py)
FORWARD_VERSION = "fm-2026.10.21-r8"
