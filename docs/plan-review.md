# Review of the merged reliability plan

A technical review of the merged plan against the code as it stands (model 5.0). Nothing is implemented. Two
facts were checked for this review and change several recommendations:

- **Where values come from.** Of the 328 candidate teams for the user's account:

  | Estimate | Teams | Share |
  |---|---|---|
  | Pair model | 267 | 81% |
  | Community simulation | 32 | 10% |
  | Role rules | 25 | 8% |
  | Swap estimate | 4 | 1% |

- **Power doesn't need the template.** For every simulated team, archetype tier × lineup fit equals the
  team's own median DPS divided by the meta normaliser, to within half a point; checked on 32 teams with
  zero mismatches. The pair model already predicts absolute DPS as well. So a team's potential is
  absolute DPS over the normaliser, and the template only matters for the role-rules estimate.

## Corrections to how the plan describes the code

- **Pull candidates do not rebuild the base pool.** `value_of` reuses the base candidates and only searches
  teams that must contain the newcomer. The actual duplicated work is elsewhere:
  - `best_carries_for` calls `best_team_with`, which re-runs the same must-include search `value_of` already
    ran for that character.
  - `report.analyze` searches every template (limit 8), and then `account.candidates` searches them all again
    (limit 12) for the same roster.
  - The must-include search explores far more than it needs to, because the newcomer is only enforced at the
    leaf. Placing them into each eligible slot first gives identical results with a much smaller search.

  Template, roster and must memoisation inside one run buys little; each combination is already computed once.
- **The current learned validity mostly checks archetype resemblance, not mechanical legitimacy.** `forbid`
  means "never seen in this archetype's simulated teams", and `max_onfield` and the per-carry teammate rules
  are typicality checks. Several "known invalid" benchmark cases are really mislabels. Neuvillette with Diluc,
  Bennett and Xiangling is a working Vaporize team, rejected only as "Mono Pyro". Relaxing validity therefore
  means re-reviewing that list. It's covered below as a dependency.
- **The `forbidden_patterns: [Pyro, Cryo]` example came from my proposal, not the code.** Your objection to it
  is right.
- **Measured reaction signals already cover most of identity.** The synergy database stores, per lineup:
  - reaction triggers per member per 10 s (including vaporize and melt counts)
  - the team's reaction damage share
  - enablement per member
  - aura tracking during attribution, including "frozen" and "quicken"

  What is missing is storing those per reaction type and the per-aura uptime, not measuring them.

## Section by section

| # | Section | Verdict | Reason |
|---|---|---|---|
| 1 | Theory guard first | Keep as written | The guard can use the synergy database's per-lineup trigger profile, since `gtc theory` only runs on simulated community lineups. Unsupported: vaporize or melt triggers, or transformative, catalyze or bloom reactions above a small share. |
| 2 | Safe performance early | Keep but modify | Target the real duplicates listed above, plus a golden-output regression harness. Memoising template, roster and must searches adds little. |
| 3 | Benchmark v2 | Keep but modify | Continuous sensitivity is right, but it measures movement, not correctness. Cases need expected magnitudes or gaps to judge it. Retire parameters before writing adversarial cases for them (see question 7). |
| 4 | `TeamEvaluation` | Keep but modify | Move the power baseline from the template to absolute DPS (question 1). Use an evidence object, not a route string. |
| 5 | Reaction model | Keep but modify | Make it a Python table that replaces the scattered constants, plus measured centrality. No requirement DSL in YAML (question 2). |
| 6 | Capabilities | Keep as written | Mostly exposing `capabilities.json`. Two additions: buff targets come from `kits_auto.yaml`; battery from gcsim's per-character energy statistics. |
| 7 | Validity refactor | Keep but modify | Do it after identity and power are decoupled from templates. Keep the current rules as a typicality score that widens uncertainty, not as rejection. Otherwise nonsense teams come back with optimistic pair-model values. |
| 8 | Structure v2 | Keep but modify | Output class probabilities, not one label. Current type accuracy (75%) is limited by simulation noise near the thresholds. |
| 9 | Identity with hybrids | Keep but modify | Build centrality from signals the data already has instead of counterfactual "does the team collapse" tests (question 5). |
| 10 | Routing with functional distance | Keep but modify | Use functional distance to set the sd of each estimate, learned on held-out swaps, not to choose the route (question 6). |
| 11 | Separating power and risk | Keep as written | The planner can apply the same 0.674 sd adjustment, so outputs stay identical at first. |
| 12 | Submitter aggregation | Keep but modify | Use your robustness tests, not the correlation criterion. Move it earlier: it changes lineup medians, which feed the pair model, tiers and uncertainty, so every later fit should use the new medians. |
| 13 | Account-specific power | Keep but modify | Use a calibrated per-character build factor, with exact personal sims for the top candidates (question 3). Fix one basis for comparing owned teams with pulls. |
| 14 | Planner v2 | Keep but modify | Use content utility functions with a minimum-value gate, inside the existing exact search. The Pareto frontier is for explanation only (question 4). |
| 15 | Functional redundancy | Keep as written | Delete `duplicate_element_factor`. Expect a deliberate behaviour change in sidegrade cases. |
| 16 | Pull decomposition | Keep as written | Cheap: both plans already exist in `value_of`. |
| 17 | Attribution cleanup | Defer | Mostly naming and presentation. It touches the 35-minute rebuild, so batch it with the next rebuild. |
| 18 | Provisional kits and LLM compiler | Keep kits; defer the LLM compiler | The compiler adds a non-deterministic offline step and needs a human review gate. Do it after the provisional kit format is stable and in use. |
| 19 | Order | Keep but modify | See the final sequence. |

## The ten questions

### 1. Is `TeamEvaluation` the right abstraction?

Yes, with one change that matters more than the record itself: **power should not be computed through the
template.**

Today power is tier(template, lead) × fit(template, lead). As shown above, that equals the lineup's own DPS
over the normaliser for simulated teams. The pair model also predicts absolute DPS. Template and lead only
matter for:
- choosing which simulation pool the fit is relative to
- the role-rules estimate, which is 8% of candidates

So `TeamEvaluation.power` should be expected DPS over the normaliser, with sd and evidence. Tier and fit stay
as explanation ("78% of Flins' best lineup").

That removes the main reason template and lead are entangled with power. Once power doesn't depend on the
template, identity can change freely without changing values, which is exactly what steps 5 to 9 need.

Recommended shape:

```python
@dataclass(frozen=True)
class Evidence:
    route: str                  # exact_personal | exact_community | pair_model | role_rules | kit_model
    tier: str                   # A..F
    sd_relative: float
    nearest_simulated: frozenset | None
    member_distance: int
    functional_distance: float  # added in the routing step; 0 until then
    sources: tuple[str, ...]

@dataclass(frozen=True)
class PowerEstimate:
    expected: float             # DPS / meta normaliser x 100
    sd: float
    evidence: Evidence

@dataclass
class TeamEvaluation:
    lineup: frozenset
    generated_by: str           # the template id that produced the candidate: provenance, not identity
    validity: Validity          # ok, reasons; later also a typicality score
    structure: Structure        # class probabilities, primary actor, driver, damage and field shares, measured or predicted
    identity: Identity          # primary actor, systems {mechanic: centrality}, modifiers, display label
    power: dict[str, PowerEstimate]   # "meta"; later "ceiling", "current"; AoE as a per-power ratio
    explanation: dict           # tier, fit, best lineup, Prydwen and KQM evidence lines
```

**Boundary.** `gtc/evaluate.py` owns the pipeline. `report.assess` becomes a wrapper returning `Assessment`
with an `evaluation` field. Content profiles, planner, pulls and benchmark move to reading the evaluation one
at a time.

### 2. Is a first-class reaction model useful, or duplication?

Useful if it **replaces** the scattered constants instead of adding a layer. Today the same knowledge lives in:
- `synergy.TRANSFORMATIVE`, `CATALYZE`, `AMP_AURA`, `REACTION_AURAS`, `CORE_REACTIONS`
- `derive.PARTNER_PRIORITY`, `HELPERS`, `TEMPLATE_FOR`
- template signatures
- the calculator's damage kinds

A `gtc/reactions.py` table can hold all of it:
- class: amplifying, transformative, catalyze, Lunar, control, crystallize
- element pair, aura consumed, coefficient
- calculator support flag, ownership rule

Each existing module then imports from it. The table is game facts, so it belongs in code with tests, not in
an editable YAML.

**What not to build:** a requirements language ("bloom_core_generation") interpreted at runtime.
Requirements are measurable directly: application rates per element from capabilities, plus trigger rates. A
DSL would duplicate the learned application rules.

### 3. AccountCeiling and CurrentPower without exploding gcsim runtime

Use one mechanism for both: **a per-character build factor**, with exact personal simulation only where
it is cheap and decisive.

- **Build factor.** For each owned character, the ratio of their damage output with the account's build to
  their output with the community-standard build. Computed with the existing formulas over the
  character's own damage kinds (scaling stat, DMG%, crit, EM per reaction class). The character's stats
  come from the snapshot; the standard stats come from the community config's build lines, which gcsim
  reports in `character_details` snapshots.
- **Buffers get an output factor too.** Bennett's buff scales with his base ATK (weapon); Furina's with her
  HP; Kazuha's with his EM. Their factor applies to the share of team damage they buff, which the attribution
  already measures per lineup and per buff.
- **Team.** Team current power = meta power × Σ over members of (that member's damage share × their own
  factor), with their buffed shares scaled by the buffer's factor. Shares come from measured attribution, or
  neighbour-predicted shares when the team is unsimulated.
- **Calibration.** The review already runs personal sims with a "community-standard artifacts" variant per
  character. That is a direct measurement of the build factor. Fit and validate the formula factor against
  it, then report the residual as its sd.
  - Today that is about 8 characters. Running the artifacts variant for every owned character in their best
    community lineup is a one-off batch of roughly 40 to 60 sims, cached.
- **Exact sims as override.** For the plan's teams and each pull's best new team (about 4 plus 6 teams),
  run the personal gcsim and use it as tier A. That already happens for the plan in the review.
- **Ceiling** = the same factor with:
  - the best owned weapon per character (from inventory, scored by the same formula, or by personal-sim
    weapon variants for the top teams)
  - standard artifacts
  - the owned constellation

  Constellation effects need evidence. The gcsim database has non-standard sims; a like-for-like
  comparison by constellation for the same lineup, which `measured_fit` already does for builds, gives
  constellation factors where data exists. Elsewhere it is unknown and the factor is 1 with a wider sd.
- **One basis for pulls.** A newly pulled character arrives at C0 with no gear. Compare owned teams at
  **ceiling**, with the newcomer at standard build, which is what "built properly" means. Comparing owned
  teams at current power against a standard-build newcomer would systematically favour pulls.

### 4. Planner objective

Keep the exact branch-and-bound search and replace the objective with a **content utility function over the
ordered team values**, plus a **minimum-value gate**. The search stays exact as long as utility rises with
every team's value: the bound uses the best remaining candidates. Max-min also bounds cleanly.

- **Abyss.** Utility = min(v1, v2) + ε·(v1 + v2). This is max-min with total as tie-break; the 100/55 against
  92/92 case picks 92/92. Teams below `minimum_secondary_value` count zero. Then "one team only" wins when
  the second team is worthless, and the report says "no second team worth building yet".
- **Stygian.** max(v1).
- **General.** The current weights, with the gate.
- **Theater.** The existing breadth search.

On the small-account case, a gate of about 40 (to be set on benchmark cases) means Flins / Aino / Ineffa /
Sucrose at 78 plus nothing beats 62 + 33. Pareto frontiers are worth computing for the first two teams only,
to explain alternatives ("you could have 92/92 instead of 100/55"), not as the objective. Locked core:
explanation only, as you say.

### 5. Representing team identity

Multi-label, from measured signals, each scaled 0 to 1:

| Signal | Captures | Status |
|---|---|---|
| Reaction damage share per reaction type | Hyperbloom, Burgeon, Overloaded, Lunar | Stored per lineup today as a total; needs splitting by type |
| Amplified share: share of the carry's damage on amplified hits | Vaporize, Melt | In the logs; not stored |
| Aura uptime per aura | Freeze (frozen), Quicken | Tracked during attribution; not stored |
| Conditional-buff dependency: share of buffs whose gcsim key needs a reaction | Chevreuse Overloaded (her buff requires Overloaded), Lunar | From kits and buff keys |
| Primary actor, driver | From structure probabilities | Exists in part |

Centrality of a mechanic = the maximum of its normalised signals. The display label comes from the primary
actor, then mechanics above a threshold, and mechanics in a middle band become "incidental". Raiden / Kazuha /
Xingqiu / Yaoyao becomes "Raiden on-field, incidental Hyperbloom", because its Hyperbloom damage share is low.
Freeze is caught by frozen uptime, Vaporize by amplified share, Chevreuse by conditional-buff dependency.

For unsimulated lineups, signals come from members' measured per-character rates, neighbour-weighted, the same
way structure is predicted. A counterfactual "remove the mechanic and see if the team collapses" needs extra
simulations and isn't required for these cases.

### 6. Functional distance

Keep routes by data availability:
- simulated: exact
- every member known to the pair model: pair model
- otherwise: role rules or kit

Use functional distance to set **the sd**, not the route:
- Fit a small regression on the 29,400 held-out one-member swaps, and on held-out two-member cases.
- The target is the absolute log error of the pair model.
- The features are member distance, the capability delta between leaving and joining members (field share,
  application by element, damage share, trigger rates), and whether the newcomer was ever simulated with
  the lineup's primary actor.
- The fitted error becomes the estimate's sd.

Kazuha → Sucrose then gets a tight sd and Kuki → Raiden a wide one, without a hand formula, and it is
validated by coverage like the tier sds today. Introducing a separate "hybrid" route for two-member changes
isn't justified yet. The pair model at two members away (13.8%) plus a learned sd may be enough; measure
before building.

### 7. Parameters to delete rather than tune

| Parameter | Why delete it |
|---|---|
| `account.duplicate_element_factor` | Replaced by measured redundancy and decomposition |
| `report.max_swap_gain`, `report.max_swap_distance`, `synergy.unproven_share`, `synergy.context_base`, `synergy.shrink`, `report.engine_factor` | The swap estimate decides 1% of candidates. Delete it with the routing step, after checking those 4 cases fall to the pair model or role rules. `SynergyTable.pair_value` goes with it; `carry_mate_quality` reads the observations directly. |
| Template `ceiling` values | Unused once power comes from absolute DPS, except in the role-rules estimate, where calibration already absorbs them |
| `estimate.risk` as a team property | It becomes a planner-policy parameter |
| `validity.apply_percentile`, `onfield_percentile`, `carry_element_share`, the per-carry `forbid` rules | Become inputs to a typicality score once validity is mechanical; no longer rejection thresholds |
| `review.estimate` | Rough gains for rule findings; replace by the build-factor formula once it exists |

Keep:
- `teams.pair_thresholds`, `unproven_quality`, `single_team_cap`: search-ordering heuristics only
- `account.viable_carry_potential`: a reporting threshold
- `capabilities.neighbour_base` and the pair-model penalties: cross-validated

### 8. What is overengineered

- **A YAML requirements language for reactions.** Use measured application and trigger rates.
- **A hand formula for functional distance.** Use a learned sd model.
- **A seven-type structure classifier as a hard label.** Use probabilities from continuous features.
- **Pareto frontiers for four teams.** Only the first two teams need them, and only for explanation.
- **Ceiling and current power as separate systems.** One build-factor mechanism serves both.
- **The LLM compiler now.** The provisional kit format doesn't exist yet.
- **Benchmark coverage of every category at once.** Start with plan, pull and identity cases, where answers
  matter most.

### 9. What to do before anything else, beyond the theory guard

A **golden-output regression harness**. Save, for the user's account and every benchmark roster:
- the candidate list with values and evidence
- the plan
- the pull values and kinds
- the labels

Fail on any diff unless the change is marked intended. Every "preserves outputs exactly" claim in the plan
depends on it, starting with the performance work. It takes about half a day and makes every later step
safer.

### 10. The biggest remaining blocker after all of this

**Ground truth outside the community's simulated space.** After every step, the engine is still anchored to
about 3,800 community-simulated lineups under standard builds and fixed rotations. Most candidate values for a
real account (81% today) are model extrapolations. Account-specific adjustment is formula-based and calibrated
on a few dozen personal sims.

Two things a strong human theorycrafter does remain out of reach:
- **Adapting rotations to the account.** Different Energy Recharge, constellations or a missing support
  change how the team should be played; the engine only edits builds inside the community's rotation.
- **Judging off-meta teams nobody has simulated.**

The practical mitigation is targeted simulation: generate and run our own gcsim configs for unsimulated
high-value candidates, by adapting the nearest simulated lineup's rotation. That is a substantial project,
which is why it isn't in the plan.

## Final sequence

Dependencies are noted where an order is forced.

0. **Theory guard.** Uses the synergy database's per-lineup reaction triggers. No dependencies.
1. **Golden-output regression harness.** Everything after relies on it.
2. **Safe performance.** Remove the duplicate searches (`best_team_with` against `value_of`; `analyze`
   against `candidates`), add a must-first search, extend validity caching to its sub-calls, and add timing
   instrumentation. Needs 1 to prove identical outputs. Target: under 20 s.
3. **Submitter-aware aggregation,** with robustness tests. Data layer first: it changes medians, so re-run
   derive (pair model, uncertainty, validity) once here, and later steps fit on the final data. Golden diffs
   are expected and reviewed.
4. **Benchmark v2:** calibration and locked sets, gap and ranking scoring, continuous sensitivity. Cases for
   plan, pull and identity first. Re-review the "known invalid" list into "invalid", "mislabelled" and "weak".
5. **`TeamEvaluation` and power from absolute DPS.** No behaviour change, golden-checked.
   It decouples power from template and lead.
6. **`reactions.py` and capability exposure.** Store per-type reaction shares, amplified share, aura uptimes
   and conditional-buff dependency. This needs one synergy rebuild, so batch step 17's attribution cleanup
   into it.
7. **Structure v2,** with probabilities. Needs 6 for features.
8. **Identity v2:** multi-label, labels from identity. Needs 6 and 7. Label diffs are expected in the golden
   output.
9. **Validity v2:** mechanical rules plus a typicality score that widens sd. Needs 5 and 8: identity and power
   must no longer depend on templates before archetype-shape rejections are lifted. Uses the re-reviewed
   invalid list from 4.
10. **Uncertainty separation and `compare()`,** with risk moved into the planner, outputs identical at first.
    Then the functional-distance sd model, with the swap estimator and its parameters deleted. Needs 6 for
    capability deltas.
11. **Account power:** build factor, calibration batch, exact sims for top candidates, ceiling and current.
    Needs 5 and 10.
12. **Planner v2** (content utilities with the gate), then **pull v2** (decomposition, functional
    redundancy, `duplicate_element_factor` deleted). Needs 10 and 11, with benchmark cases from 4.
13. **Provisional kits** in the new capability format. Needs 6.
14. **Offline LLM kit compiler** with a human review gate. Needs 13 in use.
15. **Final performance and parallelisation pass.**

Each step ends with:
- pytest
- benchmark calibration and locked sets
- the audit
- the golden diff, either empty or every change explained
- a model version bump when parameters or schemas change
