# Reliability plan: account advice and pull value

Proposal only; no code has changed for it yet. Resin efficiency is out of scope. The rule it works toward:

```text
Validity ≠ Structure ≠ Archetype ≠ Power ≠ Account Value ≠ Confidence
```

## 1. Where each responsibility lives today

| Responsibility | Where it is | How it decides |
|---|---|---|
| Candidate generation | `teams.fill_template`, `account.candidates`, `report.analyze` | Branch and bound per archetype template, filling slots by role quality |
| Validity | `teams.elements_fit`, `teams.team_is_valid`, `validity.check`, `check_structure`, `check_carry` | Element signature, learned application and on-field rules, then a damage-owner check |
| Structure | `synergy.classify_structure` (measured), `capabilities.predict_structure` and `Neighbours` (predicted), `validity.structure_of` | Damage shares against fixed thresholds |
| Lead and primary damage dealer | `evidence.damage_lead` | Measured or predicted damage owner, if they fit the template's first slot, else the first-slot holder |
| Archetype identity | The template that filled the lineup; `derive.family_of`; `evidence.sims_for` | Whichever template produced the highest-potential assessment of that lineup |
| Display label | `template.label` plus `Assessment.lead` | The template's label |
| Power | `report.assess` → `archetype_tier` × lineup fit (`lineup_fit`, `pair_model_fit`, `synergy_fit`, `anchored_fit`) → `potential_estimate`; `team_power` | Tier of the lead's best lineup times fit against it |
| Account value | `account.Plan`, `best_plan`, `profiles.plan_for` | Exact search maximising weighted risk-adjusted potential |
| Pull value | `account.value_of`, `gain_estimate` | New plan value minus base plan value |
| Confidence | `gtc/estimate.py`, `Assessment.estimate`, `CharacterValue.estimate`, `compare_words` | Measured sd per evidence tier |
| Simulation noise | `evidence.lineup_median`, `lineup_n`; `synergy.lineup_stats` (median, n, sd, trimmed mean) | Median per lineup |
| Reaction attribution | `synergy.Attributor` | Marginal, Shapley, enablement, and logged reaction-bonus values |
| Swap calculator | `gtc/tc/*`, called by `gtc theory` and by `review.theory_swaps` | Formulas for direct, Lunar and Swirl damage only |
| Benchmark | `gtc/benchmark.py`, `knowledge/benchmark.yaml` | Pass/fail per case |

## 2. What is mixed together

1. **One template object is validity, identity, label and power baseline at once.** Its slots generate
   lineups, its signature and learned rules validate them, its label names them, and its simulation pool sets
   the tier and fit baseline. When several templates can fill a lineup, `account.candidates` keeps the one
   with the highest potential. So **the label is chosen by power.** That is how Raiden / Kazuha / Xingqiu /
   Yaoyao becomes "Hyperbloom".
2. **"Lead" means three things.** It is the identity in the label ("Flins hypercarry"), the power baseline
   (tier and fit are measured against the lead's best lineup), and part of validity (`check_structure`). The
   first-slot fallback makes Chevreuse the "lead" of the hand-written Overloaded template.
3. **Validity depends on structure prediction.** `check_structure` rejects a lineup when the predicted damage
   owner cannot hold the carry slot, so a structure mistake rejects a valid team.
4. **`Assessment.potential` is power with risk already subtracted** (expected minus 0.674 sd). It feeds both
   "how strong is this team" and the plan optimiser, so power and confidence are fused in one number.
5. **The planner has one objective, a weighted sum.** It has no notion of a core, a flex slot or "no second
   team". Pull values are plan differences, so they inherit every planner quirk.
6. **Estimate routing ignores distance.** `anchored_fit` tries the pair model first for any unsimulated
   lineup. Distance only changes the reported sd.
7. **The benchmark is pass/fail.** It cannot see magnitudes, gaps or closeness.

## 3. Corrections to the brief

- **Reaction bonuses are no longer split equally.** Since phase 2 they use the per-source values gcsim logs
  on each hit. Equal splitting is only a fallback when that record is missing. Enablement already credits
  aura owners and Dendro-core makers separately from buffs. What remains is in step 9.
- **The pair model is measured best at one member away.** It scores 6.2% median error against 9.2% for the
  swap estimate on the same 29,400 held-out swaps. So "one member → pair-marginal model" should keep the
  ridge pair model, not the older swap estimate. Routing by distance is still right for three or more members.
- **Uncertainty already exists.** Every team, pull and comparison carries an sd, a tier and the 80% rule.
  What is missing: a `comparison` field in the data rather than in text, a tie zone in the planner, and
  routing-specific evidence types.
- **`gtc theory` does reach account advice.** `review.theory_swaps` feeds teammate-swap findings into the
  account report's to-do list. It also costs 7.6 of the profiled seconds. Its guard should move earlier.
- **Submitters are available.** Raw gcsim entries have a `submitter` field; the loader drops it.

## 4. The smallest refactor

Add one record, `TeamEvaluation`, built by an explicit pipeline in a new `gtc/evaluate.py`. It wraps the
existing functions instead of rewriting them. `report.assess` becomes a thin caller, and `Assessment` keeps
its fields and gains an `evaluation`, so reports keep working while consumers move over one at a time.

```python
@dataclass
class TeamEvaluation:
    lineup: tuple[str, ...]
    validity: Validity            # ok, failed_rules[], checked against archetype requirements
    structure: Structure          # type, primary_damage, driver, enablers, damage_shares, source: measured|predicted
    identity: Identity            # archetype_id, reaction_profile {reaction: share}, display_label
    power: Power                  # single_target, aoe, sustain: each an Estimate (value, sd, tier, evidence_type)
    route: str                    # exact_personal | exact_community | one_member | two_member | archetype | rules_only | kit_model
```

Account value, plans and pull values then read `power` and `confidence` separately. The risk adjustment moves
out of `potential` into the planner. Nothing else needs to change shape in the first step.

## 5. Incremental changes and schema changes

| Step | Incremental | Needs a schema change |
|---|---|---|
| 1. Benchmark | Runner, scoring and sensitivity sweep | `benchmark.yaml` v2 (rankings, gaps, confidence, tags); split into `benchmark_calibration.yaml` and `benchmark_locked.yaml` |
| 2. Planner | Lexicographic search in `account.py` | `model.yaml` planner section; `TeamPlan` with `locked_core` and `flex` |
| 3. Validity | Move the damage-owner check out of validity | Capability vectors per character; `required_capabilities` and `forbidden_patterns` per archetype |
| 4. Structure | Retrain on measured lineups | New structure types (`onFieldCarry`, `quickswap`); `Structure` record |
| 5. Identity and labels | New `gtc/identity.py` | `Identity` record; reaction profile per lineup |
| 6. Routing | `anchored_fit` routing by edit distance | `route` and `evidence_type` on estimates |
| 7. Uncertainty | Tie zone in planner and pulls | `comparison` field on value pairs |
| 8. Noise | Submitters, trimmed means, noise-floor rule | `lineup_stats` gains submitters and spread-based outlier marks |
| 9. Attribution | Ownership, enablement and amplification as separate views | Synergy database entries gain `ownership` and `uncertainty` per member (rebuild, about 35 minutes) |
| 10. Provisional kits | Extend `kits_custom` | Provisional kit schema; `evidence_source` |
| 11. Performance | Caching and deduplication | None |
| 12. Theory guard | Capability flags | `supports_swap_theory` per reaction kind |

## 6. Proposal per priority

### Step 1: benchmark redesign

**Format** (YAML, the same fields as your brief):

```yaml
- id: flins_hydro_support_order
  account: {roster: [...], cons: {...}}          # or account_id pointing at a shared roster
  question: pull_value | team_value | plan_contains | lead | label | structure | validity
  candidates: [Columbina, Furina, Yelan]
  expected_ranking: [Columbina, Furina, Yelan]
  confidence: high                               # weights the case: high 3, medium 2, low 1
  expected_gap: {"Columbina>Furina": large, "Furina>Yelan": small}
  reason_tags: [fills-gap, role-redundancy]
  sensitive_to: [account.duplicate_element_factor]   # for adversarial cases
```

**Scoring per case**, each on a 0 to 1 scale, weighted by confidence:
- ranking: Kendall tau between expected and engine ranking
- pairwise: share of expected pairs ordered correctly
- gap sizes: a "small" gap must fall inside the tie zone (P < 0.8); "medium" between 0.8 and 0.95;
  "large" above 0.95
- close calls stay close: expected small gaps must not come out "large"

**Two files.**
- **`benchmark_calibration.yaml`** is the only file tuning may read.
- **`benchmark_locked.yaml`** holds about 30% of cases, chosen before any tuning. Its hash is stored in
  `benchmark_results.yaml`, and a test fails if it changes without an explicit unlock note.

**Adversarial cases.** For every tunable parameter in model.yaml, at least two cases built so the answer
flips if the parameter is absurd:
- **`duplicate_element_factor`:** a second Pyro carry against a Hydro support for a Pyro-heavy account, where
  the right answer depends on the discount.
- **`estimate.risk`:** a well-simulated team just below a thinly evidenced one; the right pick depends on risk.
- **`plan_weights`:** a second team on an eight-character account, where the answer depends on how much the
  second team matters.
- **`teams.unproven_quality`:** a lineup with an unsimulated teammate against a simulated one.
- **Validity percentiles:** the known-invalid list, plus near-valid teams that must pass.

**Sensitivity sweep** (`python -m gtc benchmark --sweep`). Each parameter is run at about five values across
a wide range, with the others fixed. The output is a table of which cases change and how the score moves.

**Acceptance:**
- Every parameter marked important changes at least 3 cases across its sweep.
- An absurd setting (outside the plausible range in model.yaml) lowers the calibration score by at least 15
  points.
- After tuning, the locked validation score is within 5 points of its pre-tuning value or better, and within
  5 points of the calibration score.

### Step 2: small-account planner

**Data model.**

```python
@dataclass
class TeamPlan:
    team: TeamEvaluation
    locked_core: list[str]   # members whose removal costs more than CORE_LOSS (measured or pair-model share)
    flex: list[str]
```

**Constraints** (model.yaml `planner:`):
- `preserve_primary_team: true`
- `minimum_secondary_value`: below it the plan says "No second team worth building yet"
- `max_primary_loss_for_secondary_gain`: a ratio; breaking Team 1 needs secondary gain of at least loss
  times this ratio
- `core_break_multiplier`: taking a core member needs this many times the justification of a flex member
- `allow_no_secondary: true`

**Algorithm (lexicographic):**
1. Best valid Team 1, by expected power with risk.
2. Mark its locked core: members whose removal loses more than a core threshold, judged by measured shares or
   pair-model effects.
3. Best Team 2 from the remaining roster.
4. Try alternatives that take members from Team 1. Accept one only if the account gain beats the threshold:
   flex members at 1x, core members at `core_break_multiplier`.
5. Repeat for Teams 3 and 4, each lexicographically after the ones before.

Content modes call the same planner with their own team count.

**Acceptance tests** (as benchmark cases and unit tests):
- a 6-character account
- an 8-character account (the Flins / Aino case)
- one excellent team plus weak leftovers, which must answer "no second team"
- two naturally independent teams, which must keep both
- a premium support shared between two teams (for example Bennett), where the plan picks the
  higher-value use and the explanation says which team gave him up

### Step 3: team validity

**Archetype requirements** in templates.yaml, with generated defaults learned from simulations:

```yaml
hyperbloom:
  required_capabilities: {dendro_application: 1, hydro_application: 1, hyperbloom_trigger: 1}
  forbidden_patterns: [{elements: [Pyro, Cryo]}]
  optional_capabilities: [healing, grouping, res_shred]
```

**Character capability vectors** in `knowledge/generated/capabilities.yaml`, measured from the synergy
database and overridable by hand:
- on-field damage, field share, application rates per element on and off field
- driver capability (field share with a low damage share)
- triggers per reaction
- buff strength by target (self, active, party)
- healing and shields

Most of these numbers already exist in `capabilities.json`; this step names them and adds thresholds.

**The validity check uses capabilities only.** The damage-owner check moves to structure and identity,
where a failure means "this is not a Hyperbloom team", not "this is not a team".

**Acceptance:**
- every known-invalid case is rejected
- every archetype keeps at least 98% of its own simulated teams, with membership by family as today
- no valid team is rejected because of a structure prediction

### Step 4: structure predictor

**Types:** hypercarry, onFieldCarry, dualCarry, driver, reactionCore, distributedDamage, quickswap.

**Features** per member, from capability vectors and the predicted damage shares (the current neighbour
predictor):
- field share
- damage share
- off-field persistence
- buff target
- application rate
- driver capability
- reaction ownership
- sustain
- rotation dependency, measured as how much damage falls when Energy Recharge is short (step 15 of phase 5)

**Model:** a small decision list, or a multinomial logistic model, fitted on the measured structures of about
3,700 lineups. Measured structures are relabelled with the new types: quickswap means two or more members each
on field at least 25% of the time; onFieldCarry means the carry is on field at least 60% of the time.

**Validation:** hold out 20% of lineups, report a confusion matrix, and list "absurd" confusions separately.
An absurd confusion is a support predicted as the carry when its measured share is under 15%.

**Acceptance:**
- top damage dealer right on at least 90% of held-out lineups (86% today)
- type right on at least 80% (75% today)
- absurd confusions under 1%

### Step 5: identity and labels

**`gtc/identity.py`** builds an `Identity` from the structure and a reaction profile: the share of team damage
by reaction (direct, vaporize, hyperbloom, Lunar-Charged...). That share is measured from the synergy
database for simulated lineups, and predicted from members' reaction ownership otherwise.

**Label priority:**
1. Primary damage structure, for example "Raiden" or "no single carry".
2. Driver or on-field identity.
3. Dominant reaction, if it has at least 35% of damage.
4. An archetype modifier ("Dendro", "taser").

Chevreuse needed for Overloaded does not make her lead: the label comes from the structure, not the slot.

**Acceptance:**
- a misleading-label test list, which includes Raiden / Kazuha / Xingqiu / Yaoyao → "Raiden (Dendro)" and
  Chevreuse Overloaded → "Razor Overloaded" or "Overloaded, no single carry"
- every simulated lineup's label agrees with its measured structure

### Step 6: routing by edit distance

| Distance from the nearest simulated lineup of this archetype | Route | Evidence type |
|---|---|---|
| 0 | Exact simulation (personal over community) | exact |
| 1 | Pair model, with the swap estimate as a cross-check | one_member |
| 2 | Hybrid: pair model plus a role and fulfilment term, fitted on held-out two-member cases | two_member |
| 3 or more | Archetype estimate: the archetype's tier distribution and role quality, with the pair model only as a weak prior | archetype |

The hybrid's weights are fitted on held-out two-member pairs (about 7,000 exist). The archetype route's sd is
measured on lineups whose nearest neighbour is three or more members away.

**Acceptance:**
- each route's sd is measured and ordered: exact < one_member < two_member < archetype
- the two-member route beats the pair model alone on held-out two-member cases
- three-or-more cases are never reported at a tier better than D

### Step 7: uncertainty propagation

- **Estimate fields.** Add `evidence_type` from the route table, and `confidence` (high, medium, low) from
  the sd and tier.
- **Comparisons.** `compare(a, b)` returns `{comparison: better | roughly_equal | worse, p}`. The planner and
  pull tables use it, and the reports print "roughly equal" for ties.
- **Tie-aware planning.** When plans differ by less than the tie zone, prefer the one that keeps the current
  team (stability), and say the alternatives are equivalent.
- **Pull values.** Gain sd already comes from the changed teams; add the route tier of every team involved.

**Acceptance:** every report number has an sd and an evidence type, and no ranking claim is made inside the
tie zone (a test scans report output).

### Step 8: simulation-noise aggregation

- **Lineup stats.** Add submitters, and per-submitter medians, so one submitter cannot dominate. Use the
  trimmed mean when there are five or more submissions.
- **Outliers.** Mark submissions more than 3 robust sds from the median.
- **Normalisation.** Where gear differs, use the gcsim database's own standard tag (already filtered); never
  mix non-standard submissions into a lineup's value.
- **Noise-floor rule.** A pull or plan conclusion inside the noise floor (about 5% for community lineups) is
  reported as a tie unless independent evidence agrees. Independent evidence means the pair model or guide
  rules pointing the same way.
- **Validation:** the popularity-bias check. Before and after, measure the correlation between a lineup's
  submission count and its fit; it should fall to near zero.

**Acceptance:** that correlation is under 0.1, and no recommendation separates options that differ by less
than the noise floor without stated independent evidence.

### Step 9: reaction attribution

- **Three views per member and lineup.** Ownership (damage they trigger), enablement (auras and cores they
  supply), amplification (buffs on reaction damage). All three exist in some form today; this step stores them
  side by side.
- **Vaporize and Melt ownership.** Today the triggering hit owns the amplified damage and the aura owner gets
  enablement. Add a per-lineup uncertainty: when aura contributions are close between two members, the split
  is reported as uncertain.
- **No forced sums.** Explanations stop presenting marginal shares as adding up. Shapley is labelled "fair
  share"; marginal is labelled "what removing them costs".

**Acceptance:** Hyperbloom triggers own most reaction damage; Hydro and Dendro supports show enablement; and
values match hand checks for Hu Tao / Xingqiu, Nahida / Kuki and Neuvillette / Xiangling reverse Vaporize.

### Step 10: provisional kits for new characters

**Schema** in `kits_custom/`, the fields from your brief:
- role, field time, personal damage tier, elemental application
- buff strength and targets, sustain, reaction ownership
- preferred archetypes, team restrictions, dependencies, expected synergies

**How it turns into a team:** the kit is converted to a capability vector (step 3) and into pair-model
priors. A character's main effect is set from their personal damage tier, by the median main effect of
simulated characters of that tier and role.

**Provenance:** `evidence_source: simulation | interpolation | kit-model | rules-only`, printed as
"Provisional / kit-based".

**Supersession:** when simulations exist for a character with a provisional kit, the kit stops being used
(audit-checked).

**Acceptance:**
- a provisional character appears in valid teams, labelled provisional
- once simulated, their results switch source automatically
- the audit flags any kit still used after simulations exist

### Step 11: performance

**Profile** (this session, with profiler overhead):

| What | Profiled time |
|---|---|
| Account report total | 79 s (about 48 s without the profiler) |
| Team search (`fill_template`): 15,724 calls, 13.5 million search steps | 62 s |
| Candidate generation: 93 calls, mostly 56 pull candidates each rebuilding a pool | 43 s |
| Validity: 282,000 distinct checks, team profile and structure prediction | 22 s |
| Theory swaps in the review | 7.6 s |

**Fixes, in order of expected gain:**
1. **Account-level cache of candidate pools.** A pull candidate only adds teams that contain them; the base
   pool is reused, which `value_of` already does. Also memoise `fill_template` by template, roster key and
   `must`.
2. **Precompute per-template slot candidates once per roster.** Each newcomer is inserted instead of
   re-filled.
3. **Validity cache keyed by canonical lineup and template version.** Exists; extend it to the structure and
   team-profile calls under it.
4. **Drop theory swaps from the account report** (step 12 guard).
5. **Parallelise pull candidates** with a process pool, safe because evaluations are pure given caches.

**Instrumentation:** a `--timings` flag that logs, per stage, the elapsed time, lineups evaluated, cache hit
rate and duplicate evaluations.

**Acceptance:** the account report under 20 seconds with identical plan and pull results (a regression test
compares output).

### Step 12: guarding `gtc theory`

- **Capability flags.** `supports_swap_theory: {direct: true, lunar: true, swirl: true, vaporize: false,
  melt: false, hyperbloom: false, ...}`. A swap is supported only when the reaction profile of both teams
  keeps unsupported reactions under 10% of damage.
- **Otherwise** `gtc theory` and `review.theory_swaps` return "Unsupported for this team".

**Acceptance:** no theory number appears for unsupported teams, and the 200-swap validation is re-run on
supported cases only. The target is 90% within 10% there; otherwise the support list shrinks.

## 7. Proposed sequence

I'd make two changes to your order: the theory guard moves first because it is tiny and currently leaks into
account advice, and the `TeamEvaluation` record goes in before step 3.

0. **Theory guard** (step 12): about an hour. It stops misleading numbers now.
1. **Benchmark v2** with calibration and locked sets, the sensitivity sweep and adversarial cases. Everything
   after this is measured against it, so it comes before any engine change.
2. **Small-account planner**, judged on the new benchmark cases.
3. **`TeamEvaluation` record and pipeline** (section 4), wrapping today's functions without changing results.
   A regression test checks the outputs stay identical.
4. **Validity on capabilities**, with the damage-owner check moved out (step 3).
5. **Structure predictor** (step 4).
6. **Identity and labels** (step 5).
7. **Routing by edit distance** (step 6).
8. **Uncertainty fields and tie zone** (step 7).
9. **Noise aggregation and popularity-bias check** (step 8).
10. **Attribution views** (step 9). The synergy rebuild happens here, once.
11. **Provisional kits** (step 10).
12. **Performance** (step 11). Last, so it optimises the final pipeline. If the slowness gets in the way
    earlier, its first fix (account-level caching) can come forward safely.

Each step ends with the full test suite, the benchmark (calibration and locked), the audit, and a model
version bump with a recorded benchmark run.
