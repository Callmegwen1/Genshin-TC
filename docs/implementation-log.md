# Implementation log: reliability roadmap

The roadmap is the approved plan in docs/plan-review.md, refined by the user's final decision set.

## 2026-10-11: phases 0 to 2 done; phase 3 not started

Engine model 5.1. Results:
- 82 tests pass
- the audit is clean
- benchmark 46 of 46
- golden outputs unchanged except one approved tie-break update

### Phase 0: theory calculator guard

The theory calculator now refuses to give a number outside the teams it is validated on (`gtc/theory_guard.py`).
The guard sorts each team's damage by channel, using gcsim's source names: "(vaporize)", "(melt)",
"(aggravate)" and "(spread)" suffixes, and reaction sources such as overload or hyperbloom. It also uses the
calculator's own Lunar classification of kit abilities.

A swap is answered only when all of these hold:
- unsupported reactions are at most 5% of damage, before and after
- Lunar-Charged is at least 60% of damage, before and after
- the swap does not replace the team's lead
- for a candidate with no simulated team, their element adds no unmodelled reaction

Both `gtc theory` and `review.theory_swaps` use the guard. Unsupported teams get an explicit "Unsupported for
this team: <reason>". Measured validation:

| Set | Cases | Result |
|---|---|---|
| Accepted by the guard (`tc.validate.run_guarded`, two seeds plus hand checks) | 20 of 290 | 19 of 20 within 10% (95%), median error 2.9% |
| Refused by the guard | 270 | 37% within 10% |
| Broad sample (`run_broad`, 200 swaps, all families, unguarded) | 200 | 33 to 37% within 10% |

**What validation showed that the plan assumed otherwise.** "Direct damage, Lunar, Swirl" are not reliably
supported. Swaps with only those channels were within 10% just 30 to 39% of the time, because the swapped
team usually plays a different rotation. Only Lunar-heavy teams where the lead stays pass. The supported set
was shrunk accordingly, as the roadmap required. A threshold of 50% Lunar gave exactly 90% (27 of 30), so 60%
was chosen for margin.

### Phase 1: golden-output regression harness

- **Tool.** `gtc/golden.py` and `python -m gtc golden --check | --update --reason "..."`.
- **Coverage:** 38 accounts, the user's snapshot plus 37 distinct benchmark rosters. Recorded for each:
  - candidate teams (lineup, template, label, lead, expected value, sd, tier, fit source, ranking value)
  - plan and plan value
  - plans per content mode
  - viable carries
  - carries for owned supports
  - pull values (gain, expected, sd, tier, kind, best team)
- **Storage.** `tests/golden/`, with deterministic JSON and values rounded to 0.1. `tests/test_golden.py`
  fails on any difference.
- **Updates** require a reason and are logged in `tests/golden/CHANGES.md` with the full diff.

**Approved update (1): deterministic tie-breaks.** The harness found that exact ties (equal team, plan, carry
or pull values) were ordered by Python's per-process hash seed, so two runs of the same code could disagree.
Lyney against Varka at 47.3 was the case caught. Ties now break by lineup or name. 9 values changed, all
between options of equal value. Outputs are identical under hash seeds 1 to 8.

### Phase 2: safe performance

`python -m gtc account --timings` prints stage times, work counters and cache hit rates.

| | Before phase 0 | Start of phase 2 | After phase 2 |
|---|---|---|---|
| Account report | about 48 s | 26 s | 15 s |
| Team report pass (analyze) | n/a | 10.5 s | 2.9 s |
| Pull values | n/a | 11.3 s | 8.5 s |
| Carries for owned supports | n/a | 2.6 s | 0.2 s |
| Search steps | 13.6 M | 13.6 M | 1.65 M |
| Validity checks (uncached) | 282 k | 286 k | 182 k |

Most of the drop from 48 s to 26 s came from phase 0, which stopped the calculator running in the review. The
golden outputs are unchanged.

Changes:
1. **One pruned search per template in the team report pass.** `report.analyze` ran a full enumeration per
   template, twice, keeping the top 8. It now runs one exact pruned top-8 search, reused. The pruned search is
   exact and keeps tie order.
2. **Must-include searches place the character first.** They now put the required character into each
   eligible slot first and search around them, merging the results. Ties keep the plain search's order: each
   lineup carries the position where the unrestricted search would first reach it. The first version broke ties
   alphabetically and changed 122 golden values, so it was redone to be exact.
3. **Shared must-include candidates.** `AccountModel.candidates_with` is used by both pull values and carries
   for owned supports.
4. **Team-profile cache** under validity.

### Files changed

- **New:**
  - `gtc/theory_guard.py`, `gtc/golden.py`, `gtc/timing.py`
  - `tests/test_theory_guard.py`, `tests/test_golden.py`, `tests/golden/*` (38 files plus CHANGES.md)
  - `docs/implementation-log.md`
- **Changed:**
  - `gtc/tc/cli.py`, `gtc/tc/validate.py`, `gtc/review.py` (theory guard)
  - `gtc/teams.py` (search refactor, counters), `gtc/report.py` (single search per template, tie-breaks)
  - `gtc/account.py` (tie-breaks, shared candidates, stage timings), `gtc/capabilities.py` (profile cache,
    counters)
  - `gtc/__main__.py` (`golden` command, `account --timings`)
  - `knowledge/model.yaml` (version 5.1, `theory_guard` section), `knowledge/benchmark_results.yaml`
- **Data:** `data/sources/calculator_validation.json`, `calculator_validation_guarded.json`,
  `calculator_validation_lunar.json`.

### Where the code contradicted the roadmap

1. **The calculator's valid scope is narrower than "direct, Lunar, Swirl".** Only Lunar-heavy swaps that keep
   the lead validate. Rotation changes, not missing reaction formulas, are the main error source elsewhere.
2. **The review's gate leaked.** The review had only a "every member has a kit" gate, which phase 5's
   generated kits (108 characters) made almost always true.
3. **Most profiled time wasn't where expected.** It was full enumeration in the team report pass and
   leaf-only must-include checks, more than repeated pull pools.
4. **Outputs depended on the hash seed.** Tie order did, before the golden harness existed.
5. **Candidate pre-selection is order-sensitive.** It uses a coarse role score with a top-12 cutoff that falls
   inside large ties. Which lineups get assessed therefore depends on search order. Behaviour is now pinned
   but still arbitrary at the boundary, which is relevant to phases 5 and 10.
6. **The assessment cache key ignores constellations.** `AccountModel._assessed` is keyed by template and
   members only, so in one engine shared across rosters (benchmark, golden) the same lineup with different
   constellations reuses one assessment. The user's real report is unaffected. Fix it when `TeamEvaluation`
   lands in phase 5.

## 2026-10-11: phase 3 done (model 5.2)

Lineup values are now robust to who submitted the simulations.

- **Submitters kept.** `SimTeam.submitter` is re-normalised from the raw database; all 6,020 records have one.
- **One central rule.** `gcsim_db.aggregate` and `lineup_values()` collapse each submitter's runs to their
  median; the lineup's value is the median of those. "migrated" and blank count as one unknown submitter.
  `n_submitters` is the number of independent votes.
- **Every consumer uses it:**
  - `Evidence`, applying the shared rule to its own simulations
  - `pairmodel.lineup_data`
  - `estimate.measure_community`, now submitter against submitter
  - `derive.discover`
  - the synergy database's stored values, via `synergy.refresh_values()` in `derive`, with no simulation reruns
  - future database builds (`value_stats`)
- **Robustness tests** (`tests/test_aggregation.py`):
  - the same run re-submitted 50 times changes nothing
  - one submitter flooding high runs moves the value at most to the next submitter's value
  - removing the most prolific submitter moves it under 3%
  - an outlier at 100× moves it under 3%
  - unknown submitters are one vote
  - the sd shrinks with independent submitters

**Effect on the data.** 94 of 3,800 lineup values changed, 20 by more than 5% and 2 by more than 15%. All are
lineups where one person had re-submitted. Skirk / Escoffier / Furina / Yelan dropped 14%, for example. The
meta normaliser's top three are essentially unchanged.

**Refit.** `derive` was re-run:

| Measure | Before | After |
|---|---|---|
| Pair model held-out error | 6.4% | 6.4% |
| One community vote's sd | 9.8% (between submissions) | 9.9% (between independent submitters, 151 cases) |
| Validity recall | unchanged | unchanged |

The community coverage check now has only 4 lineups with four or more independent submitters; the threshold
was lowered from six. That is too few to mean much, and is stated as such.

**Golden update (2), approved.** Across 38 accounts:
- 1 plan changed: two pair-model estimates at 50.3 against 50.2 swapped after the refit.
- 2 top pulls changed and 9 pull kinds changed.
- Pull gains moved by a median of 0.1; 48 of 364 moved by more than 1 point. The largest follow the re-valued
  lineups: Yelan for a Skirk account went from 28.0 to 15.1, and Xilonen for a Neuvillette account from 46.8
  to 39.8.
- The user's own plan and top pull are unchanged.
- The 5,983 raw differences are mostly list positions shifting; the semantic summary is above.

**Bug found and fixed.** `Evidence` had first read the global database cache instead of its own simulations,
which a test caught.

**Checks:**
- 89 tests pass
- the audit is clean
- benchmark 46 of 46, recorded for 5.2
- account report 18.6 s

**Files:**
- `gtc/sources/gcsim_db.py`, `gtc/evidence.py`, `gtc/pairmodel.py`, `gtc/estimate.py`, `gtc/derive.py`,
  `gtc/synergy.py`, `gtc/__main__.py`
- `tests/test_aggregation.py`
- `knowledge/model.yaml` (5.2), `knowledge/benchmark_results.yaml`, `tests/golden/*`
- regenerated data in `data/sources/` and `knowledge/generated/`
- a backup of the old records at `data/sources/gcsim_teams.before-phase3.json`

## 2026-10-16: phase 4 done, benchmark v2

The old pass/fail suite (`knowledge/benchmark.yaml`, `python -m gtc benchmark`) stays as a regression suite: still
46 of 46. The new graded benchmark is `python -m gtc bench` (`gtc/bench.py`).

**Two case sets:**
- **Calibration** (`knowledge/benchmark_calibration.yaml`, 34 cases) is the only set tuning reads.
- **Locked** (`knowledge/benchmark_locked.yaml`, 15 cases) is pinned by hash in
  `knowledge/benchmark_locked.lock.json`. A test fails on any change without
  `python -m gtc bench --unlock --reason "..."`, which logs the change and resets approval.

**The locked set is not yet approved by the user.** Its scores are labelled provisional until
`python -m gtc bench --approve`. Before review I unlocked it once to fix two badly posed cases and annotate a
third; the reasons are logged in the lock file.

**Question types:**
- pull ranking (pairs with expected gap class, Kendall ranking, gain ranges)
- team ranking
- plan
- validity (classification: invalid, valid but misclassified, valid but weak)
- identity (primary actor, structure, label, central or incidental mechanics)
- carries (who counts as a viable main damage dealer)
- content modes

**Scoring.** Each case's assertions score 0 to 1, and cases are weighted by confidence (high 3, medium 2, low
1).
- **Pairs** score half for the right order and half for the right gap class. Gap class comes from the engine's
  own probability that one option beats the other: under 80% is small, 80 to 95% medium, above 95% large.
- **Close calls** (expected small) must stay small.
- **Assertions needing later phases** (no second team, mechanic centrality, the new structure types) are
  counted as pending, not as passes or failures.
- **Summaries:** pairwise order accuracy, close calls kept close, and validity as a classifier.

**Scores at model 5.2:**

| Set | Score | Notes |
|---|---|---|
| Calibration | 84.7% over 34 cases, 6 pending | pairwise order 0.90, close calls kept close 0.92 |
| Locked (provisional) | 80.4% over 15 cases, 1 pending | |

Calibration by question:

| Question | Score |
|---|---|
| Team ranking | 0.94 |
| Plan | 0.90 |
| Identity | 0.83 |
| Pull ranking | 0.77 |
| Validity | 0.67 |

The validity score is the gap phase 9 must close: all 3 mechanically invalid teams are correctly rejected,
but all 3 valid-yet-misclassified teams are rejected too.

**Re-review of the old "known invalid" cases:**

| Old case | Classification | Engine today |
|---|---|---|
| Neuvillette in Mono Pyro (with Diluc, Bennett, Xiangling) | valid but misclassified: a Vaporize team | rejected (wrong) |
| Kazuha / Raiden / Shenhe / Citlali as Anemo carry | valid but misclassified: a Raiden team | rejected (wrong) |
| Clorinde leading Lunar-Charged | valid but misclassified: a Clorinde team | forms as Clorinde Electro-Charged (right) |
| Skirk / Chiori / Lan Yan / Zhongli | valid but weak | rejected (wrong) |
| Mizuki leading Hyperbloom | valid but misclassified: Mizuki is a driver | forms; lead not Mizuki (right) |
| Ayaka / Bennett / Xiangling / Mona as Freeze | valid but misclassified: not Freeze | rejected (wrong) |
| Razor with Kazuha in Overloaded | valid but weak | forms (right) |

New genuinely invalid cases, all correctly rejected:
- Hyperbloom without Electro
- Freeze without Hydro
- Vaporize without Hydro
- Aggravate without Dendro

**Which parameters survive** (decided before writing adversarial cases):

| Parameter | Decision |
|---|---|
| `estimate.risk` | keep; becomes planner policy (phase 10) |
| `account.plan_weights` | keep until planner v2's content utilities (phase 12) |
| `teams.unproven_quality`, `teams.single_team_cap` | keep as search-ordering heuristics |
| `account.viable_carry_potential` | keep as a reporting threshold |
| `account.duplicate_element_factor` | delete in phase 12; swept, but no adversarial cases |

The swap-estimator and validity-percentile parameters are scheduled for deletion or conversion (phases 9 and
10) and were not swept. Validity percentiles act at learning time.

**Continuous sensitivity sweep** (`--sweep`; stored in `knowledge/bench_results.yaml` and
`data/sources/bench_sweep.json`). Every swept parameter moves the engine's outputs. Scores react less:

| Parameter | Absurd value | Outputs moved | Calibration score | Other effect |
|---|---|---|---|---|
| `estimate.risk` | 5 | 39% mean change, 7 cases | about unchanged | decision regret 4.3% to 8.0% |
| `account.plan_weights` | [1, 0, 0, 0] | 29% mean change, 7 cases | -1.4 points | |
| `teams.unproven_quality`, `single_team_cap` | various | 1 to 3 outputs | at most 0.6 points | |
| `account.viable_carry_potential` | 30 | | +0.6 points | changes 1 case (the carry case) |
| `account.duplicate_element_factor` | 0 | | +0.6 points | changes 1 case |

**Decision regret** is a new measured-data check for the ranking risk:
- **Setup.** Half of each archetype family's simulated lineups are hidden behind their held-out pair-model
  predictions; the other half are read as noisy measurements.
- **Choice and scoring.** The engine picks by expected value minus risk × sd, and regret is how much worse the
  pick truly is than the best.
- **Scale.** 29 families, 40 random splits.

| Risk | 0 | 0.3 | 0.674 (current) | 1 | 2 | 3 | 5 |
|---|---|---|---|---|---|---|---|
| Regret | 4.2% | 4.3% | 4.3% | 4.4% | 4.7% | 5.3% | 8.0% |

The current value is within 0.1 point of the minimum. Predictions and single measurements carry similar
uncertainty (about 10% each), so there is little winner's curse to correct.

**Tuning** (`--tune`) searches risk × plan weights on calibration only, scored leave-one-out:

| Measure | Score |
|---|---|
| Best in-sample (equal team weights) | 85.3% |
| Current | 84.7% |
| Leave-one-out | 84.7% |
| Locked at the tuned or the current setting | 80.4% |

The in-sample gain comes from one case and does not generalise, so the defaults stand. The locked score is
stable under tuning.

**Acceptance:**
- **Each important parameter affects some cases:** met.
- **Locked performance stable after tuning:** met.
- **Absurd values meaningfully degrade the score:** met for the risk, through decision regret. Only partly met
  on expert cases: they judge expected values, and policy parameters such as risk and plan weights move them
  little. That is the current limit of opinion-based cases. Planner v2 (phase 12) brings plan cases whose
  answers depend on the objective.

**Checks:**
- 96 tests pass, including `tests/test_bench.py`: scoring rules, the pinned lock, and tuning reading only the
  calibration set
- golden outputs unchanged (no engine behaviour changed)
- the audit is clean

**Files:**
- `gtc/bench.py`, `gtc/__main__.py` (`bench` command)
- `knowledge/benchmark_calibration.yaml`, `benchmark_locked.yaml`, `benchmark_locked.lock.json`,
  `bench_results.yaml`
- `tests/test_bench.py`

**User action needed:** review the 15 locked cases in `knowledge/benchmark_locked.yaml`, especially
`locked_xiao_close_call`, which gcsim data contradicts, then run `python -m gtc bench --approve`, or ask for
changes first.

### Locked set review (user, 2026-10-16)

The user reviewed all 15 locked cases and the set is approved (hash c2c6d50d3fd3700f). Changes from the review:
- Skirk pull: Escoffier > Furina (medium), Escoffier > Xilonen (large). Skirk teams have no Anemo for VV, so
  Escoffier's Cryo/Hydro shred is the main gain; Furina's Hydro is replaceable. My pre-review flip was wrong.
- Hyperbloom pull: Kuki > Escoffier widened to large (Escoffier is a Freeze unit, zero value in Hyperbloom).
- Columbina vs Aino team: gap narrowed to medium.
- Xiao close call kept: the gcsim entry favouring Bennett appears to run a Vaporize Xiao.

Locked score with the approved answers: 72.6%. Engine errors this exposes, for later phases:
- Escoffier valued at 2.9 against Furina's 62.5 on a Skirk account without Hydro: the engine cannot form a Skirk
  team without a Hydro member and does not value shred (phases 5, 6, 12).
- Escoffier valued at 35.2 on a Hyperbloom account with no Cryo carry (phases 9, 12).
- Xiao: Bennett team ranked clearly ahead, following the single gcsim entry (phase 10 uncertainty).
- Ayaka / Bennett / Xiangling / Mona: the user rates it off-meta, so rejection is acceptable; the case now only
  asserts it is never identified as Freeze. Nahida / Kuki / Xingqiu / Yelan called hypercarry (phase 7).

## 2026-10-16: phase 5 done (model 5.3)

Every candidate team now goes through one pipeline, `gtc/evaluate.py`, which returns a `TeamEvaluation`:
- lineup and `generated_by` (the template, now provenance only)
- validity and identity (still from the template until phases 8 and 9)
- structure, measured or predicted
- power per context (`single_target`, `aoe`), each a `PowerEstimate` with a `Basis`: route, tier, relative sd,
  nearest simulated lineup and member distance
- sustain, kept apart from power
- explanation: tier, fit and the template's own estimate

`report.assess` wraps it, and `Assessment.evaluation` holds the record.

**Power no longer depends on the template.** `lineup_power` looks at the four characters only:
1. **exact_community.** A lineup with standard community simulations gets its own median over the normaliser
   (tier B), whatever template produced it. Before this, 81 of 141 such evaluations in the golden accounts were
   valued another way. Some measured teams were rated 0 because the template's carry pool did not contain them,
   for example Neuvillette / Furina / Kazuha / Fischl (measured 58.7) and Nahida / Kuki / Xingqiu / Yelan
   (measured 54.3).
2. **pair_model.** For a lineup whose members have all been simulated, power is predicted DPS over the
   normaliser. The tier is C one member from a simulated lineup and D further away. The lead effect comes from
   the structure, and the sd from the pair model's held-out error alone. The old sd also compounded the
   archetype's best lineup noise, which does not belong in an absolute number.
3. **role_rules.** Otherwise the template's role rules apply. This is the only route where the template still
   sets the number. It never reached a plan in the golden accounts.

**Checks:**
- Template dependence: of 107 lineups that several templates generate, 84 used to get different powers; now 0.
- Execution difficulty now reads from the structure's damage owner.
- Ties between templates go to the template whose own estimate fits best, which keeps labels stable.

**Pair model without its archetype term.** The archetype term was the last way a template entered power.
Cross-validated, it bought almost nothing:
- one member from a simulated lineup: median error 6.42% with it, 6.48% without
- further away: 10.9% with it, 11.6% without

That check gave the archetype term each lineup's true archetype, which real use never has. The measured sds
after the refit are 10.1% (near) and 12.8% (far). `pairmodel.lambda_family` is deleted.

**New coverage rule.** `pairmodel.carry_like_share: 0.5`. Two characters who are their team's damage owner in at
least half their lineups, and were never simulated together, are outside the pair model. The model would add
both carries' effects as if both could hold the field; Mualani next to Neuvillette showed up as an "upgrade".
The rule applies to the old pair-model fit too.

**Also fixed:** the assessment cache key now includes constellations. This changed nothing in the golden outputs.

**Verification:**
- 101 tests pass, including `tests/test_evaluation.py`: template independence, exact route, distances, no
  archetype term, record fields.
- Audit clean.
- Golden update 3 approved with reason: 6 plans, 8 top pulls and 62 pull kinds changed, mostly close calls
  within their sd. The user's top pull is unchanged; their Ayaka team now takes Citlali instead of Rosaria.
- Account report 19 s, against 15 s, because tier and fit are still computed for explanations (phase 15).

| Benchmark | Before (5.2) | After (5.3) |
|---|---|---|
| Calibration | 84.7% | 81.2% |
| Locked (approved) | 75.3% | 74.0% |
| Old benchmark | 46 of 46 | 45 of 46 |
| Decision regret | 4.3% | 4.4% |

**Regressions, all explained:**
- **Hu Tao / Xingqiu / Yelan / Zhongli now uses its own data:** a 41k median, 29.1 on the scale. Two of the three
  submitters run Hu Tao on Deathmatch at about 41k; the third uses Ballad of the Fjords at 69k. This flips
  "vape beats mono" (old benchmark and calibration) and lowers Yelan's value for Hu Tao accounts. It is a
  data-standardisation problem the old engine hid by never reading this measurement. Fix with weapon-aware
  standardisation (phase 11's build factor) and spread-aware sd (phase 10). With n = 3, the sd is 5.7% although
  the submitters disagree by 70%.
- **Flins with Aino against Furina** (both measured) is now read as a medium gap, not a close call
  (P = 0.80, at the boundary), because the sd no longer double counts.
- **Locked Skirk pull:** Escoffier vs Xilonen moved from 0.5 to 0 (4.0 vs 7.9). It is the same known Skirk
  problem (phases 5 to 12).

**Known limits now visible:**
- **Pair-model extrapolation to teams with no damage dealer.** Ineffa / Sucrose / Xingqiu / Yaoyao gets 61.8
  (tier D) because Ineffa's character effect carries her Lunar teams' strength. None reaches a plan; phase 9's
  typicality should widen these.
- **Characters with almost no data.** Varka has 1 simulated lineup, yet gets a tier C sd near his only lineup
  and is top pull in several rosters. The sd should grow with each member's evidence (phase 10).
- **Carry-less support teams.** The planner still takes one as a second team on small accounts. Phase 12 adds
  the minimum secondary value.

Backups: data/sources/pair_effects.before-phase5.json and uncertainty.before-phase5.json.

## 2026-10-16: model 5.3.1, correctness cleanup (before phase 6)

No expected power changed: 0 of the 1,089 matched candidate teams in the golden accounts moved. Changes by item:

**1. Swap advice now uses the team evaluation.**
- **Cause of the Kazuha to Keqing "+42%".** `teammate_swaps` compared lineup fits, and fit is relative to the
  lead's best simulated lineup. The swap changed the lead, so the two fits had different denominators: Raiden /
  Kazuha / Xingqiu / Yaoyao had fit 60 against Raiden's best, and with Keqing it had fit 85 against Keqing's best.
- **What the evaluation says.** Expected power falls from 47.3 to 39.3, about -17%.
- **New rule (`review.swap_verdict`).** Both lineups must have a reliable route (exact community or pair model).
  The gain is compared on expected power. The swap is shown only if the gain is at least
  `review.swap_min_gain` (4%) and it is at least `review.swap_min_confidence` (80%) likely to be better, after
  the coverage cap. Anything else gets no number.
- **Calculator swaps** (still Lunar-only) are now suppressed when the evaluation expects the swapped team to be
  weaker.
- **Result.** The Keqing advice is gone from the account and review reports.

**2. User-facing numbers are expected values.**
- `Assessment.expected_power` is the display number; `decision_utility` (= potential, expected - 0.674 sd) is for
  plans and rankings only.
- Fixed in the account report: the "potential X to Y" phrases in pull text, the main damage dealers, the carries
  list, the best carry and best support lines, the "Today" column (`today_power`) and the against-meta ratio
  (now 75% on expected values, previously 72% on decision values).
- Mode scores stay decision scores and are labelled as such.
- The team and review reports now print team rating as `today_power`.

**3. Personal simulations.** "+184% ± 1.1% (A)" is now "+184% (A)", with a note that (A) runs are precise as
simulations but leave out rotation and model uncertainty. The iteration noise is kept as
`Finding.simulation_precision`.

**4. Reshuffle wording.**
- A one-slot change reads "replacing X".
- When a newcomer displaces two or more members, the text says adding them makes the plan reorganise the team,
  old lineup to new.
- Every other team the optimizer moved is listed, old to new, and dropped teams are listed too.

**5. Mechanics coverage guard (`gtc/coverage.py`, temporary).**
- **Mechanics data.** Each character's important mechanics are the buff kinds worth at least 3% of team damage
  on average, from per-hit attribution.
- **When coverage is partial.** Pair-model lineups are "partial" when such a mechanic has no fitted pair effect
  with the team's damage dealers. They are also partial when the pair was never simulated alongside an element
  the lineup adds; that is how Chevreuse + Lyney with Citlali is caught.
- **Exact community lineups** are always complete. Role rules count as unknown.
- **Effect.** Pull confidence is the statistical confidence capped at 80% (partial) or 65% (unknown); reports show
  both. It does not change values, plans or rankings.

**6. Build heterogeneity.**
- **Data.** Community records now keep each member's artifact sets and talents, re-normalised from the stored raw
  download with no new data. `LineupValue.by_build` holds the median and submitter count per build, where a build
  is (constellation, weapon, refinement, main set) per member.
- **Value unchanged.** The value is still the median of submitter medians.
- **New sd (`estimate.exact_rel_sd`).** Within-build noise shrinks with submitters. The disagreement between
  build medians, less what within-build noise explains, is added in full.
- **Scale.** 545 of 3,800 lineups mix builds; in the golden accounts 22 candidates got a wider sd.
- **Hu Tao / Xingqiu / Yelan / Zhongli.** Its builds are Ballad 69k vs Deathmatch 41k and 40k: 29.1 ± 2.1 became
  29.1 ± 8.5 (between-build 28.5%). "Vape beats mono" still fails on expected values, but P(better) moved from
  0.13 (confidently wrong) to 0.31. No tuning to restore the old answer.
- **Reports** mark "mixed builds".

**7. Carry ranking diagnostic** (no logic change beyond item 5):
- **Mavuika, 81 ± 6 (B).** Measured Mavuika / Sucrose / Bennett / Citlali, 2 submitters whose builds agree (129k
  and 118k). The pair model agrees (79.8). Healthy.
- **Gaming, 75 ± 20 (B), mixed builds.** Measured with C6 Gaming. The two submissions differ only in Rosaria's
  Favonius refinement yet read 132k and 89k, so the gap is a rotation or config difference, not the build. The
  pair model says 61. The between-build sd now carries this, and Gaming's decision score falls from 72 to 62, out
  of the top 3 (Arlecchino 67 enters).
- **Lyney, 71 ± 7 (C).** Pair model one member from Bennett / Chevreuse / Lyney / Yae (measured 68). It reaches 71
  through Chevreuse + Lyney (+15%), a pair effect learned in Overloaded teams. Chevreuse's buff needs an all Pyro
  and Electro party, and Citlali breaks it. This is a real modelling error. The coverage guard now flags it as
  partial; it stays a phase 9 item (explicit kit composition restrictions).

**8. Roadmap.** Phase 6.5 "Provisional Kits Lite" is inserted after phase 6, in docs/roadmap.md. It is not built.

**Verification:**
- 110 tests pass (new: tests/test_cleanup_531.py). Audit clean.
- Calibration 81.2% (unchanged). Locked 75.3% (from 74.0%: the Xiao close call now has a wide sd from mixed
  builds). Original benchmark 45 of 46 (Hu Tao vape). Decision regret 4.41%.
- Golden update 4: 1 top pull (a close call) and 4 pull kinds changed through the wider sds; no plan changed.
- Account report 20 s.

Backup: data/sources/gcsim_teams.before-5.3.1.json.

## 2026-10-16: phase 6 done (model 5.4)

**1. Central reaction facts (`gtc/reactions.py`).**
- **The table.** One `Reaction` entry per reaction: class, element pair, auras consumed, gcsim coefficient,
  ownership rule (trigger, core creator, contributors, none), calculator support, theory-guard channel, and
  the family name a team takes.
- **What it replaced.** The derived views replace synergy's TRANSFORMATIVE, CATALYZE, AMP_AURA, REACTION_AURAS and
  CORE_REACTIONS; the theory guard's source names, supported channels and unsupported pairs; derive's helper
  elements and its reaction names per element pair (the partner order stays in derive as a judgment); report's
  reacting elements; and the calculator's Lunar multipliers.
- **Checks.** `tests/test_reactions.py` pins every view to its previous literal. Golden was unchanged after the
  refactor, checked before the rebuild.

**2. Lineup measurements (`Attributor.measure_lineup`), stored in every profile:**
- reaction damage share per reaction type, Swirl grouped
- amplified-hit share (Vaporize, Melt) and catalyzed-hit share (Aggravate, Spread)
- aura uptime on the main target, Frozen and Quicken included, and the share of damage dealt while each aura was
  on. Measured from gcsim's before and after aura state at every application: present at both ends counts as on
  throughout; present after but gone before the next application is assumed to expire halfway.
- conditional buffs: every gcsim mod rejected at least once, with its owner, the share of eligible hits it
  applied to, and the share of team damage on those hits
- per member: reactions they triggered, by type; the amplified share and off-field share of their own damage;
  particles; and energy given to teammates

Examples:
- Ayaka / Shenhe / Kazuha / Mona: Frozen up 34%, 54% of damage dealt into Frozen, with no Freeze damage at all.
- Hu Tao / Xingqiu / Yelan / Zhongli: 56% of Hu Tao's own damage is Vaporized, 18% of the team's.
- Nahida / Kuki / Xingqiu / Yelan: Quicken up 27%.

`reaction_share` now counts Lunar-Bloom and Lunar-Crystallize; before, only transformative reactions and
Lunar-Charged counted.

**3. Attribution cleanup**, batched into the rebuild:
- **Separate fields.** Database entries keep `own` (ownership), `buffs_marginal` (each buff removed alone),
  `buffs_shapley` (the fair split, which sums exactly), `enable_reaction` (reactions their auras or cores made
  possible) and `enable_amp` (the amplified part of Vaporize and Melt on their aura, now a separate contribution
  kind).
- **Migration.** `synergy.load_database` migrates older entries, so readers only use the new names.
- **Review text** now names amplification separately.
- **Overlap.** Marginal and Shapley differ visibly when buffs overlap: Columbina 0.15 vs 0.074 in Flins /
  Ineffa / Columbina / Sucrose.

**4. Capabilities.** `Capability` adds continuous fields:
- reaction ownership by type
- amplified and off-field shares (off-field persistence)
- particles and energy to the team (battery)
- shield rate
- marginal and Shapley buffs, reaction enablement and amplification
- buff effects by kind (shred, element bonuses) and the share landing on the top dealer (buff targets)
- conditional-buff activity and dependency

`driver_like` is a categorical helper, and `vector()` gives the flat feature set for phases 7 and 8. The coverage
guard now reads buff effects from capabilities instead of recomputing them. `TeamEvaluation.explanation`
carries the lineup's measured profile.

**5. The one synergy rebuild** (about 35 minutes; 3,800 lineups, 12 configs gcsim can no longer run, as before;
held-out swap check 9.0%). gcsim draws a new random seed per sample, so re-sampling moves measurements:
- **Sample total damage:** median change 1.6%.
- **Member damage shares:** median change 0.4 points.
- **Structure type:** changed for 166 of 3,788 lineups (4.4%), all near the hard thresholds. The user's Flins /
  Aino / Ineffa / Sucrose went from hypercarry to dual carry. This is the brittleness phase 7 replaces with
  probabilities.

**After derive:**
- pair model 6.4% CV (was 6.5%)
- uncertainty: near 9.8%, far 12.9%
- validity recall at least 93%
- lineup values unchanged

**Verification:**
- 119 tests pass (new: test_reactions, test_measurements). Audit clean.
- Calibration 82.2% (from 81.2%: pull ranking 72% to 80%, team ranking 81% to 75%). The Ayaka close call now sits
  exactly at P = 0.80.
- Locked 75.3% (unchanged). Original benchmark 45 of 46 (Hu Tao vape). Decision regret 3.9% (was 4.4%).
- Golden update 5: 116 of 1,051 teams moved by more than 0.5 (median 0.1). 1 plan changed, a 40.8 vs 40.7 tie
  on the Furina-for-Neuvillette roster. 2 top pulls swapped their top two, 23 pull kinds and 17 labels changed.
  The user's plan and top pull are unchanged.
- Account report 23 s.

**Known limit.** Conditional-mod owners come from the existing key-to-owner mapping, which falls back to the
attacker. Blizzard Strayer's `cryo-res` in Ayaka teams is credited to Kazuha. Fix in the identity work (phase 8)
before reading conditional dependency per member.

Backups: data/backup-before-phase6/ (synergy database, capabilities, families, pair model, uncertainty,
knowledge/generated).

## 2026-10-16: phase 6.5 done (model 5.5), Provisional Kits Lite

Characters with no community simulations can now get a clearly labelled, low-confidence value instead of
"cannot evaluate".

**Who it covers.**
- Of the six characters reported as unevaluable, five have no simulations at all: Lohen, Nefer, Sandrone, Vesna
  and Zibai. They now have hand-written kits in `knowledge/kits_provisional/`.
- **Ifa** had 6 standard simulated lineups. He was unevaluable only because derive's tagging never placed him in
  an archetype, and its reason text wrongly said "no standard gcsim teams yet". The text is fixed (it now says
  "in only N standard lineups"). Ifa is placed by hand in `characters.yaml` and valued from his own data: tier
  B where simulated, the pair model elsewhere. Yumemizuki Mizuki carries the same mislabel; her placement was
  left unchanged.

**The kits.** Each holds:
- role, element and weapon
- an analogue: a simulated character with the closest measured role (Lohen Ganyu, Nefer Nahida, Sandrone Eula,
  Vesna Xiao, Zibai Navia)
- expected archetypes (placement)
- capability ranges in the phase 6 fields (the midpoint is used)
- mechanics paraphrased from the official kit text in the Project Amber cache: reaction conversions, buffs and
  their conditions
- sources

Kits are read with `kits_custom`, but kept out of the calculator.

**The `provisional_kit` route (`gtc/provisional.py`).** It only runs when the pair model cannot predict the
lineup, so simulations replace it automatically.
- **Anchor.** The character's best-team power comes from their Prydwen DPS tier. The mapping,
  log(best-team power) = a + b x tier value, is fitted on the 45 simulated carries with a tier. Its
  leave-one-out miss is 18.9%; a T0 carry anchors at 92.
- **Team fraction:**
  - A Prydwen-listed team gets its listed percentage.
  - A team within two members of a listed team gets the listed percentage times the pair model's ratio of the
    two lineups, with the analogue standing in for the character. The ratio is capped at 1: Prydwen lists the
    strongest teams.
  - Anything further gets no number. Before this rule existed, a nonsense team (Sandrone with Shenhe, Chiori and
    Zhongli, no Electro for her Stellar-Conduct) inherited a listed team's value.
- **Tier E,** sd never below the measured back-test sd, coverage always unknown (confidence capped at 65%).
- **When the route declines a team,** the evaluation gives no number. It never falls back to template role
  rules.

**Back-test** (`provisional.measure`, recomputed by derive):
- Setup: Skirk, Neuvillette, Mavuika and Arlecchino are valued as if unsimulated, with the analogue a kit would
  name (Ganyu, Mualani, Arlecchino, Hu Tao) and the anchor refitted without them.
- Results: 471 measured lineups. The sd is 19.1% (68.3rd percentile); 68% of misses fall within 1 sd, 90% within
  2 sd. The tails are heavy, as in the other tiers.
- Bias by character (median log error): Mavuika +0.02, Skirk -0.12, Neuvillette -0.08, Arlecchino +0.31. With Hu
  Tao as her analogue, Arlecchino's weaker teams come out rated too high.

**Reports.**
- Every provisional number reads "Provisional: no simulations of this character yet ..." with its anchor, how the
  team was placed, and its uncertainty. Team tables show "E, provisional".
- Characters whose possible teams on the account are all too far from Prydwen's teams are listed as "Provisional
  kits, but no estimate for your account". They are never shown as "no change".
- The audit notes provisional kits, and flags them as stale once the character is simulated.

**User's account.**
- Sandrone enters the pull list 4th: +13.1 ± 7.6, tier E, provisional, confidence 65% (96% statistical). Her team
  is Sandrone / Yae Miko / Rosaria / Zhongli, near Prydwen's Yae team.
- Sandrone also enters the carries-for-supports list at 62 (Fischl / Yae Miko / Zhongli).
- Lohen is valued (best team 59) but does not beat the current four.
- Nefer, Vesna and Zibai cannot be estimated for this account: no buildable team is near their listed teams.

**Verification:**
- 126 tests pass (new: tests/test_provisional.py). Audit clean.
- Calibration 82.2% and locked 75.3%, both unchanged (no case involves these characters). Original benchmark 45 of
  46.
- Golden update 6: only pull lists and carries-for-supports lists gained provisional characters (7 carry lists
  changed, 5 account pulls added). No existing value, plan or pull changed.

**Known limits:**
- **Analogue choice.** It matters for unlisted teams (the Arlecchino bias).
- **Anchor.** The anchor assumes a tier means the same strength across releases; power creep would bias recent
  T0s low. Back-test misses are slightly heavier-tailed than normal.
- **Provisional supports.** These are not supported yet; Ifa did not need one.
- **Teammates without simulations.** Six supports in these teams have no simulations either (Odette, Linnea,
  Illuga, Vodyanitsa, Alyosha, Cryo Traveler). So many of Prydwen's own teams count only through their listed
  percentage, and unlisted variants involving them get no number.

## 2026-10-17: phase 7 done (model 5.6), Structure v2

Structure is now a distribution, not one label (`gtc/structure.py`). The old rules (hypercarry at 55%, dual carry
at 25% each, ...) stay as the vocabulary, but shares are uncertain, so they are drawn many times from their
measured error and each draw is classified:
- **Simulated lineups:** the noise of one gcsim sample, measured in the phase 6 rebuild against its predecessor
  (log damage share 3.1%, field share 0.1 points). They keep their measured label; the probabilities show how
  close to a threshold they sit.
- **Predicted lineups:** the held-out error of the neighbour prediction (log damage share 30%, field share 4.5
  points, reaction share 3.2 points). The noise scale is chosen on held-out log likelihood on one half of the
  lineups and scored on the other.

**Output** (TeamEvaluation.structure):
- probabilities over hypercarry / dual_carry / reaction_core / driver / distributed
- patterns: on_field_carry (top dealer on field at least 60%) and quickswap (two or more members on field at least
  25%)
- primary actor probabilities
- the most probable type and its owners, for older readers
- expected damage and field shares, reaction share
- measured or predicted provenance

**Held-out quality** (1,873 lineups, the half not used to choose the scale):

| Measure | Single label (5.5) | Distribution (5.6) |
|---|---|---|
| Type log loss | 1.76 | 0.60 |
| Brier score | 0.51 | 0.32 |
| Calibration error | n/a | 2.9% |
| Most probable type correct | 74.6% | 77.7% |
| Top damage dealer correct | 86% | 86% |
| Absurd confusions (all lineups) | 0.93% | 0.93% |

Probabilities track outcomes: stated 85% is right 87% of the time, 97% is right 97%.

**Targets.** Two hard-accuracy targets are not met; this is honestly limited by data:
- **Type at 80%:** 77.7%. Neither sharpening the shares nor a carry-likeness feature helped (best +1.4 points;
  carry-likeness hurt), and the neighbour weighting (10 to 1000) made no difference.
- **Top dealer at 90%:** 86% overall, 93.7% where the measured leader is ahead by at least 10 points (79% of
  lineups). The rest are near-ties, and the primary-actor probabilities now say so.
- **Absurd confusions under 1%:** met, 0.93% over all lineups.

**Used by:**
- **Validity.** Its damage-owner check for unsimulated teams is probabilistic: a team is rejected only when a
  damage owner who cannot hold the carry slot is more likely than not (`structure.validity_reject: 0.5`). At 0.9,
  teams got wrong identities such as "your Sucrose team" for Sucrose / Xingqiu / Mavuika / Kazuha. The check is an
  identity check, and phase 9 moves it out of validity. Example: Bennett / Kazuha / Nahida / Xingqiu was accepted
  as Kazuha's Anemo-carry team because one point estimate sat 1.7 points under the dual-carry line. Xingqiu is the
  78% likely top dealer, so it is now rejected.
- **Labels.** Templates producing the same lineup prefer the one whose lead is the most probable damage dealer.
- **Benchmark.** Structure assertions score the probability of the expected structure. on_field_carry and
  quickswap are no longer pending.
- **Pair model.** Its lead effect goes to the most probable carry. A probability-weighted lead effect was tested:
  calibration 80.4% against 81.6% without it (locked 79.5% against 78.1%). The choice follows the calibration set
  only, so it was not adopted.

**Performance.** Structure estimates run for every lineup the team search checks, about 131,000 per report. The
work done:
- 81 us each: a fixed shared bank of draws, counting instead of 11 means, and 200 draws (held-out metrics within
  0.5 points of 400)
- provisional kits cached, where the files had been re-read 957 times
- the community database parsed once instead of 42 times

The account report takes 35 s, against 23 s in 5.5; the rest is for phase 15.

**Verification:**
- 131 tests pass (new: tests/test_structure.py). Audit clean.
- Calibration 81.6% (from 82.2%), locked 78.0% (from 75.3%: Nahida / Kuki / Xingqiu / Yelan now gets 52% for
  reaction core), original benchmark 45 of 46.
- Golden updates 7 and 8: 4 plans (3 near ties; the Hyperbloom-trigger roster drops the mislabelled Kazuha team,
  30.9 to 24.7), 3 top pulls, 27 pull kinds and 54 labels. The user's plan and top pull are unchanged.

## 2026-10-17: phase 8 done (model 5.7), Identity v2

What a team is now comes from measurements, not from the template that generated it (`gtc/identity.py`).
Templates keep `generated_by` and their own label and lead as provenance only.

**Identity record** (TeamEvaluation.identity):
- **Primary actor:** the most probable top damage dealer, when the team is at least 50% likely built around a
  carry.
- **Driver, structure and carry probability.**
- **Systems** (multi-label): every mechanic with a centrality from 0 to 1, plus the full signal vector behind it.
- **Central** (at least 0.5) and **incidental** (0.15 to 0.5) mechanics.
- **Owners** of each central mechanic.
- **The label.**

**Signals** per mechanic, each normalised by a scale in `identity.scales`, aggregated by their maximum (v1):
- reaction damage share
- the carry's amplified-hit share and the team's amplified share
- catalyzed share
- damage dealt while an aura is on the target (Frozen for Freeze, Quicken)
- buffs that need the reaction (new fact table `reactions.REACTION_CONDITIONED_BUFFS`: Chevreuse to Overloaded,
  Nilou to Bloom)
- trigger rate

Examples:
- Freeze is central for Ayaka / Shenhe / Kazuha / Mona with no Freeze damage: 54% of damage is dealt into Frozen.
- Vaporize is central for Hu Tao teams through Hu Tao's 56% amplified hits, though only 18% of team damage is
  amplified.

**Unsimulated lineups.** Their signals are averaged over simulated lineups that:
- share at least two members,
- can perform the mechanic,
- and use no outside character for its elements.

Without that last rule, Raiden / Kazuha / Xingqiu / Yaoyao inherited Quicken from Raiden teams whose Dendro is
Nahida. With no such neighbour, the members' own measured reaction ownership is the fallback. Raiden / Kazuha /
Xingqiu / Yaoyao now reads "Raiden Shogun hypercarry · incidental Hyperbloom, Swirl", the roadmap's example.

**Ownership:**
- Lunar reactions belong to the Moonsign members (kit data and Prydwen faction tags). Clorinde / Columbina /
  Ineffa / Kazuha reads "Clorinde dual carry · Lunar-Charged from Columbina and Ineffa", which is the user's own
  description.
- Amplifying reactions belong to whoever's hits are amplified.
- Other reactions belong to whoever triggers at least 25% of their damage.

**Used by:**
- **Every displayed team label.** The account report's column is renamed Identity.
- **The team's lead in account logic**, where identity names one. Benchmark scores are identical with the template
  lead and with the primary actor (both 81.6% / 79.4%), so the roadmap principle decided.
- **The benchmark.** Central and incidental assertions are scored, so no identity assertion is pending any more.
  "Not identified as X" means X is central and belongs to the team's carry. "Label avoids X" looks at what the label
  claims, not at its "incidental" part.

**Data conflicts left as measured:**
- Hu Tao / Xingqiu / Yelan / Zhongli: Yelan is the measured top dealer (the Deathmatch builds); the label says
  "Yelan dual carry · Vaporize from Hu Tao".
- The Mizuki team measures as a dual carry (Ineffa, Columbina), not a driver.

**Verification:**
- 138 tests pass (new: tests/test_identity.py). Audit clean.
- Calibration 81.6% (unchanged, now with 1 pending assertion instead of 6). Locked 79.4% (from 78.0%, 0 pending).
  Original benchmark 45 of 46.
- Golden update 9: every label changed to the identity format and 6 pull kinds moved. No power value, plan or top
  pull changed.
- Account report 30 s (35 s after phase 7). Moonsign membership and element lookups are cached; uncached they had
  cost 75 s.

## 2026-10-17: phase 9 done (model 5.8), Validity v2 and typicality

Validity now answers only "does this composition mechanically function?" (`gtc/validity.py`). The answer is what
the templates enforce while generating candidates:
- every slot filled by a character who can do that job
- the template's required roles
- its element pattern: the elements the mechanic needs (Dendro for Aggravate, Hydro and Electro for
  Electro-Charged). Chevreuse's all Pyro and Electro kit restriction is part of her template's pattern.

Nothing else rejects a team.

**What was removed from rejection:**
- **Learned per-archetype rules.** Elements never seen in its simulated teams, maximum on-field characters, and
  application minimums. The rules are deleted; their template-free part became typicality.
- **The carry teammate rule** (elements present in 95% of a carry's teams). Its data stays and feeds typicality.
- **The damage-owner check.** A predicted carry who cannot hold the template's first slot is now identity's
  business (phase 8), and its probability threshold is deleted.
- **The team search's validity hook and its cache.** `structure.validity_reject`, `validity.apply_percentile` and
  the per-archetype rule learning in derive are gone. `validity.yaml` keeps only the carries' teammate elements.

**Typicality (`gtc/typicality.py`).** Template-free findings:
- the primary actor lacks their usual teammate elements
- a teammate element the primary actor was never simulated with
- more predicted on-field characters than 98% of simulated teams have

Each finding multiplies the sd of an extrapolated estimate (pair model, role rules, provisional kit) by
1 + 0.84 per finding. A lineup with its own community simulations keeps its measured sd.

The 0.84 is measured: on simulated lineups, the held-out pair-model error is 18.0% with a finding and 9.8% without.
The sample with findings is small (17 against 3,741), because the data is overwhelmingly typical.

Findings and the sd factor are stored in `TeamEvaluation.validity`, and the basis is flagged "atypical".

**Acceptance:**
- **Invalid teams rejected.** All four mechanically invalid test teams are still rejected: Hyperbloom without
  Electro, Freeze without Hydro, Vaporize without Hydro, Aggravate without Dendro.
- **Functional teams survive.** Every previously mislabelled but functional team survives with a correct identity:
  - "Neuvillette dual carry · Vaporize"
  - "Raiden Shogun hypercarry · incidental Swirl, Superconduct"
  - Clorinde with Lunar supports
  - Mizuki Hyperbloom
  - Skirk / Chiori / Lan Yan / Zhongli, which forms and is rated far below Skirk's real team (38 against 93)
- **Predicted carries.** No team is rejected because its predicted carry differs from the template's first slot;
  that check no longer exists.
- **Measured teams are not penalised.** Typicality never touches a team with its own simulations (tested on
  Skirk / Chiori / Yelan / Zhongli, simulated at 64k).

**Skirk.** A hard "Hydro and Cryo teammates only" rule was considered, from the user's statement that Skirk is
"locked to hydro and cryo teammates", and rejected on the data. 10 of her 139 simulated lineups have other
teammates and work:
- Skirk / Escoffier / Navia / Xilonen: 85k
- Skirk / Chiori / Yelan / Zhongli: 64k
- her best: about 131k

So it is a team-building preference, which power and typicality express (Skirk with Bennett, Kazuha and Shenhe: two
findings, sd x2.67). It is not a mechanical failure.

**Benchmarks:**
- **Calibration 87.7%** (from 81.6%); validity 100%, 3 of 3 invalid rejected, 3 of 3 functional kept.
- **Locked 79.4%** (validity 100%).
- **Original benchmark 45 of 46.** Its `no_team` cases tested whether a template could form a lineup, which no
  longer means anything. They now pass only if the lineup's identity agrees with the template's reading of it (its
  primary actor is the template's own lead). "No Skirk team without Hydro" became a comparison with her real team.

**Golden update 10.** Candidate teams in these accounts grew from 1,021 to 1,369; no existing power moved. 11 plans
changed, mostly where previously rejected teams are now available:
- the small Flins account keeps Aino in Flins's team: 90.5 to 96.6
- rosters that had no plan now have one

10 top pulls and 44 pull kinds changed. The user's plan and top pull are unchanged. The account report is 21 s
(30 s before; the search no longer checks learned rules at every leaf).

## 2026-10-17: phase 10 done (model 5.9), power and uncertainty separated

**Decision policy (`gtc/decision.py`).**
- Expected power and its sd are separate. The policy is the only place they meet:
  - `utility(estimate)` = expected - `decision.risk` x sd (0.674, unchanged and moved from `estimate.risk`) is what
    plans and rankings maximise.
  - `compare(a, b)` returns better, roughly_equal or worse, with P(a > b).
- `Estimate.low` and `estimate.compare_words` are deleted; reports, profiles and the benchmark read the policy.

**Calibrated tie zone (`decision.calibrate_tie`).** Over 10,335 held-out comparisons inside archetype families, the
stated probabilities hold up:

| Stated probability | Claims right |
|---|---|
| 0.5 to 0.6 | 54% |
| 0.6 to 0.7 | 65% |
| 0.7 to 0.8 | 72% |
| 0.8 to 0.9 | 85% |
| 0.9 to 1.0 | 97% |

- The edge is the smallest probability whose own band is right at least 80% of the time
  (`decision.claim_accuracy`): 0.80. Inside it nothing is ranked.
- The account report names pulls that are roughly equal to each other. Groups are not transitive: each member is
  compared with the group's first.

**Functional distance (`gtc/distance.py`).** The pair model's sd is fitted per lineup. Features:
- members changed
- capability deltas (damage, field time, application, reaction ownership) between the newcomers and the leavers
- a newcomer never simulated with the nearest lineup's carry
- data scarcity of the least simulated member

The fit is held out (5-fold), with non-negative effects only. Field-time and reaction deltas came out negative,
which is noise, and were dropped. What drives the sd: +8.5 points of mean error per member changed, plus scarcity.
A member with one simulated lineup adds about 12 points of sd.

Coverage on the other half:
- overall: 72% within 1 sd and 94% within 2, against 70% and 93% for the flat near/far sd
- two members away: 68% and 100%, against 50% and 82% (22 lineups)
- held-out log likelihood +0.059 per lineup

The estimator is still chosen by data availability (exact simulation, pair model, role rules, kit); distance only
sets the sd. Effect: Varka (1 simulated lineup) gets a wide sd and drops from the top of 5 test rosters' pull lists,
the problem noted in phase 5.

**Swap estimator deleted.**
- **Code removed:** `report.synergy_fit` and `engine_factor`; `SynergyTable.pair_value` and `member_value`;
  `synergy.validate_swaps`; `estimate.measure_swaps`, the "swap" tier and its fallback.
- **Parameters removed:** `report.max_swap_gain`, `report.max_swap_distance`, `synergy.context_base`,
  `synergy.shrink`, `synergy.unproven_share`.
- **Where its teams went:** the 7 candidates it still valued (4 with Iansan or Kachina, which the pair model cannot
  predict; 3 Neuvillette + Diluc, held off the pair model by the coverage rule) now take the calibrated role model,
  tier E. The largest move is -5.8; none is in any plan.

**Verification:**
- 146 tests pass (new: tests/test_decision.py). Audit clean.
- Calibration 87.2% (from 87.7%), locked 79.4% (unchanged), original benchmark 45 of 46. Decision regret 3.9%.
- Golden update 11: 2 plans, 7 top pulls (mostly Varka leaving the top) and 9 pull kinds changed. The user's plan
  and top pull are unchanged.
- Account report 21 s.

## 2026-10-17: phase 11 done (model 6.0), account-specific power

Every team now has three numbers (`gtc/account_power.py`):
- **MetaPower:** the team at community standard. This is the expected power of the earlier phases.
- **CurrentPower:** the team as the account has it today.
- **AccountCeiling:** the team properly built from what the account owns.

**One build mechanism** serves current power:
- **Per-character factors.** Own factor f = exp(sum gamma_k x (investment_k - 1)) over level, talents, weapon and
  artifacts. Buff factor h = f^rho.
- **Per-character offsets,** ridge-penalised: the calibrated per-character build factor.
- **Propagation to the team** through measured shares:
  F = sum_m own_m x f_m x prod_s (1 - b_sm x (1 - h_s)).
- **Measured shares** come from the exact lineup's per-hit attribution (marginal buff shares scaled to Shapley so
  overlapping buffs are not counted twice). Otherwise predicted shares and capability-average buffs are used.
- **Double counting guard.** A support's factor only rescales the part of a carry's damage its buffs make; it is
  never added as a share. Tested.

**Calibration on exact personal simulations** (`python -m gtc account --calibrate`):
- **The truth.** Every candidate lineup with a standard community config was simulated twice on the same rotation:
  the community build, and the account's real builds with Bursts skipped when they cannot be afforded. That gave 48
  teams; one gcsim run that hung is now skipped, and results are saved team by team.
- **The fit.** gamma: level 2.0, weapon 1.5, artifacts 1.0, talents 0 (talents are entangled with the others).
  rho 1.5. Offsets for Ganyu (-0.25), Xiangling (-0.25) and Kazuha (+0.25), with the ridge penalty 8 chosen by
  leaving one team out.
- **Held out, team by team:**

| Approach | Median log miss | Roughly |
|---|---|---|
| No build model | 1.18 | off by 3.3x |
| Investment model | 0.28 | |
| Investment model + offsets | 0.26 | off by about 29% |

- **The sd** is 0.40 (log); 69% of teams fall within 1 sd and 85% within 2. Part of the remaining error is rotation
  behaviour (skipped Bursts).
- **Exact simulations override the model** for the 48 lineups that have one, which include the plan teams.

**What it shows.** The account is far below standard today: the median team deals 31% of the standard build's
damage, and Razor's team 9%. The simulation is right: Razor is level 50 with talents 1/1/1 and a level-1 Waster
Greatsword. Flins has talents 1/1/7 and two artifacts; Ineffa talents 1/1/1 and no artifacts.

**Ceiling:**
- **Constellations.**
  - Measured from same-lineup comparisons in the community database: the median ratio where only that character
    differs from standard, with at least 2 comparisons. 76 character x constellation pairs are measured, e.g.
    Bennett C5 1.00 (n 52), Hu Tao C1 1.13, Flins C1 1.33, Arlecchino C2 1.62.
  - Otherwise "constellation effect unknown": a neutral factor with sd `account_power.unknown_constellation_sd`
    (15%), shown in the report and never presented as "no effect". The account's Razor C3, Chevreuse C3, Ayaka C1
    and Mona C1 are unknown.
- **Weapons.** The first version shifted the ceiling by the fitted weapon-rarity effect, and that put the Ayaka team
  at 25 against a meta of 42. That effect was calibrated against the account's under-levelled weapons, and the
  community standard itself mixes 4- and 5-star weapons, so a 4-star at level 90 is not known to fall short. A
  weapon below 5 stars now widens the sd (`account_power.weapon_sd`, by the member's damage share) instead.

**Basis for plans and pulls.**
- **The account report** compares teams on AccountCeiling: owned characters properly built at their real
  constellations, a newcomer at C0 with the best owned weapon of their type. Never half-built owned characters
  against fully built pulls.
- **Benchmark and golden scenarios** describe fully built rosters and stay on MetaPower. This is an explicit switch,
  `AccountModel(account_basis=...)`, and the "against meta" plan uses its own meta-basis model.
- **The account report's team table** shows Ceiling, Meta and Current with their sds, built = current / ceiling, and
  flags unknown constellation effects.
- **The user's plan and top pull are unchanged.**

**Verification:**
- 151 tests pass (new: tests/test_account_power.py). Audit clean.
- Calibration 87.2% and locked 79.4%, both unchanged (meta basis). Original benchmark 45 of 46.
- Golden outputs unchanged (meta basis).
- Account report 20 s.

## 2026-10-17: phase 12 done (model 6.1), planner v2 and pull value v2

**Content utilities** (`gtc/profiles.py`). All of them keep the exact non-overlapping search.
- **Spiral Abyss** (`objective: balanced`): two disjoint teams maximising min(v1, v2) + 0.1 x (v1 + v2), so a
  balanced 92 / 92 beats 100 / 55. A second team below `minimum_secondary_value` (30) does not count, and the plan
  then says "No second team worth building yet."
- **Stygian:** the best single team.
- **General:** the weighted four-team search, counting only teams at `useful_value` (30) or more.
- **Theater:** the breadth logic, unchanged.
- **Explanations only:** the two-team Pareto frontier ("max primary" against "balanced") and the locked core of
  the best team (members whose removal costs at least `profiles.core_loss`, 15%). For the user's account the core
  is Ineffa (-22%), Flins (-20%) and Sucrose (-17%); Aino's slot can be swapped.

**Account plan.**
- **Useful-team gate.** A team below `account.min_useful_value` (30, judgment) is not a plan team.
- **Value over replacement.** A gate alone was not enough: two leftover lineups at 34 and 30 still beat one
  Neuvillette team at 55 under weights 1 / 1. Plan teams now earn value only above `account.replacement_value`.
  - The sweep (calibration only) was flat at 85.8% from 10 to 35, 86.3% at 35 and 78% at 40.
  - 20 was chosen as the middle of that range; 35 was a fragile edge.
  - `Plan.power` keeps the raw weighted power for the "against meta" ratio.
- **`account.duplicate_element_factor` is deleted** (and its sweep entries); both new parameters are in the
  sensitivity sweep.

**Pull value v2** (`gtc/account.py`).
- **The gain** is the literal change in plan value when the character joins. No label discounts it (tested).
- **The decomposition** (`AccountModel.decompose`, also in the golden output):
  - plan, best-team, second-team and expected gains
  - new mechanics (of the character's own team only) and new viable teams
  - owned characters improved and displaced
  - support contention: teammates taken from another plan team than the one the pull joins
  - functional redundancy over five overlaps: roles, mechanics, support demand, team members, and content
    coverage (a same-element carry; element alone never makes a sidegrade)
  - best owned weapon rarity
- **Kinds describe observed impact:**
  - no change
  - fills a gap: joins a team and lifts it by `account.fill_lift` (15%), or completes one
  - upgrade
  - new archetype
  - sidegrade: leads a team that displaces owned characters and shares its mechanics, or a same-element carry
    competing for the same supports
  - luxury: only the plan's lower teams improve
- **The "Why" column** is built from these deltas. The account report explains the method and shows the abyss
  trade-offs and the locked core.

**Changes** (golden: 6 plans, 3 top pulls, 123 kinds; 0 lineups changed power, 0 labels changed):
- **Plans.** Leftover support lineups no longer pad or split plans. Examples: the Flins account now fields one team
  instead of adding Bennett / Kazuha / Xingqiu / Zhongli, and a supports-only account (best lineup 27.7) has no
  plan team at all.
- **Top pulls.** On one-team accounts a second carry now beats a support upgrade, because the second team was
  leftovers: Mavuika over Columbina for flins_aino_over_xingqiu and yoimiya_hydro, and Varka for
  no_neuvillette_mono_pyro.
- **The user's account.** The top pull is still Columbina (+22.0 ± 13.1, fills a gap). The kinds are now
  descriptive: Mavuika and Lyney are new archetypes (Melt); Durin is a sidegrade of the Razor Overloaded team.

**Verification:**
- 157 tests pass (new: tests/test_planner_v2.py). Audit clean.
- **Calibration 85.8%** (6.0: 87.2%):
  - one_excellent_team_and_leftovers' "no second team" assertion is now scored instead of pending. The account plan
    passes, but the abyss profile still pairs Furina / Kazuha / Lisa / Noelle (34.9) with a Neuvillette team.
    That is a team-power limit: a legitimate Raiden second team scores 32-37, so no threshold separates them.
  - six_character_account: with the Bennett / Xiangling leftover team gone, Ayaka takes Xiangling over Mona
    (40.4 against 40.1, a tie in team power).
- **Locked 80.7%** (6.0: 79.4%); every locked plan case passes.
- **Original benchmark 44 of 46.** Still failing: vape_beats_mono_pyro_hutao (team power). Newly failing:
  plan_raiden_and_nahida. The consensus plan's Raiden / Bennett / Xiangling / Zhongli scores 29.6, just under the
  useful gate, so the plan fields Raiden in the hyperbloom team. Raiden hyperbloom is a real team; the gap is
  within one point.
- Account report 20 s.

## 2026-10-17: phase 13 done (model 6.2), provisional kits (full)

**Kit schema v2** (`gtc/kit_schema.py`, validated by the audit and a test). Each kit in
`knowledge/kits_provisional/` declares, in the normalised capability and reaction vocabulary:
- role (carry, sub_dps, support), element, weapon, analogue
- field behaviour and share
- personal damage tier and share
- application per element, on and off field
- buffs with kind, target, condition and the kit text
- sustain (heal and shield levels)
- reactions owned, enabled and converted (e.g. superconduct to Stellar-Conduct)
- preferred systems (reaction keys)
- machine-checked restrictions (`needs_element`, `needs_count`)
- synergies (explanation only)
- placement (archetypes or roles)

**Provenance.** Every described field carries a source id, a confidence and a method (`manual` today; phase 14's
compiler will write `llm_extracted`). The capability loader reads the midpoints of the ranges. A categorical heal
level is not turned into HP per second, so it stays unknown (0).

**Kits.** The five carry kits (Lohen, Nefer, Sandrone, Vesna, Zibai) are migrated. Seven new support kits come
from the official text: Alyosha (Fischl), Iansan (Bennett), Illuga (Gorou), Kachina (Albedo), Linnea (Zhongli),
Odette (Rosaria) and Vodyanitsa (Sangonomiya Kokomi). Every character outside the pair model now has a kit.

**Evidence states.** Every estimate reports one of four states (`Basis.evidence_state`):
- simulation (exact routes)
- interpolation (pair model)
- kit-model (provisional kit)
- rules-only (template role rules)

They appear in the account team table and the golden output. Provisional numbers read "Provisional / kit-based: no
simulations of <names> yet", with how they were valued.

**The provisional route** (`gtc/provisional.py`), first match wins:
0. **Restrictions.** A broken kit restriction gives no number, with the kit's reason. Example: "Sandrone needs an
   Electro or Anemo teammate: her damage rides on Stellar-Conduct or Stellar Swirl". Two provisional carries in
   one team also get no number.
1. **Same-page ratio.** A simulated carry's Prydwen page lists the lineup and simulated lineups of theirs.
   Percentages on one page share a scale, so power = measured lineup x (listed % / listed %), taking the median.
   Example: Mavuika / Citlali / Iansan / Bennett 94, scaled from two simulated Mavuika teams.
2. **Provisional carry.** The phase 6.5 anchor and fraction, now with every provisional member replaced by their
   analogue. A listed team is compared against only when all its other members are simulated.
   - The first version allowed analogues inside the reference team. That rated Sandrone / Yae Miko / Alyosha /
     Zhongli as good as Prydwen's best Sandrone team, and Sandrone reached +38 on the user's account.
   - With the rule she is +18.3 ± 20.4, valued from the fully simulated Qiqi variant.
3. **Provisional supports only.** Each provisional member is replaced by their analogue, and that lineup is valued
   by the measured routes.
- **Uncertainty.** Tier E. The sd is never below the pair model's far sd or the path's back-tested miss. Coverage
  is unknown, so confidence is capped at 65%.

**Back-tests** (`provisional.measure`, written to uncertainty.json):

| Path | Hidden characters | Lineups | sd (log) | Within 2 sd |
|---|---|---|---|---|
| Carry (unchanged) | Skirk, Neuvillette, Mavuika, Arlecchino | 471 | 0.191 | 90% |
| Same-page ratio | Citlali, Xilonen, Escoffier, Furina, Chevreuse | 20 | 0.098 | 100% |
| Analogue stand-in | same five supports | 2,091 | 0.239 | 99% |

The analogue stand-in is biased low: median miss from -6% (Chevreuse) to -27% (Escoffier). Premium supports
are better than their closest simulated analogue. Five supports are too few to calibrate a correction, so it is
reported and covered by the sd, not corrected.

**Superseded automatically.** The route only runs for characters the pair model does not know (tested with a
patched pair model). The audit now reports, per kit:
- schema errors
- "stale" once the character is in the pair model
- "still in use although N simulated lineups now exist; run derive" when simulations exist but the pair model has
  not been rebuilt (tested)

**Changes** (golden: 0 plans, 0 top pulls; no measured team power changed):
- 35 candidates with provisional members changed. In the user's account scenario they displace 28 low-ranked
  measured candidates from the capped list.
- Pulls on that roster move by 0.3 or less, because its plans can now use the owned provisional supports.
- Three Diluc / Neuvillette lineups move 0.1 in decision score: the functional-distance scale now includes the
  seven kit capability profiles.
- In the user's account report, Columbina is still the top pull. Sandrone (+18.3, E, provisional) joins the
  roughly-equal group behind it. Nefer, Vesna and Zibai still get no estimate: none of the account's teams is near
  their listed teams.
- tests/test_engine.py's "ideal Ayaka freeze uses Furina" now leaves out provisional characters. With them,
  Vodyanitsa (valued as Kokomi) takes the slot on kit-model evidence.

**Verification:**
- 166 tests pass (new: tests/test_kit_schema.py). Audit clean: 12 kits, schema 2, no findings.
- Calibration 85.8% and locked 80.7%, unchanged. Original benchmark 44 of 46, unchanged.
- Account report 21 s.

**Known limits:**
- **Pages with no simulated reference.** Every Cyno team on Prydwen's page includes Odette, so the same-page ratio
  has nothing to scale from. Cyno / Yae Miko / Odette / Alyosha falls to the analogue path at 27, far below
  Prydwen's view.
- **Analogue bias** (above).

## 2026-10-17: model 6.3, power reliability pass (inserted before phase 14)

Goal: make the numbers behind team choice, plans and pulls more reliable without new architecture. Every change
below was kept only if held-out evidence supported it, or it is labelled as semantics only.

**1. Typicality math (verified, no bug).** `sd_factor(n) = 1 + per_finding x n` widens the sd (x1.81 for one
finding, x2.61 for two). "x0.84 per finding" in the capabilities summary was a wording error. Exact simulations are
never widened. A test checks monotonic widening, and that a measured lineup keeps its sd.

**2. Mechanical validity is separate from candidate generation** (semantics).
- `validity.mechanical`: only illegality rejects (not four distinct known characters, two Travelers).
- Templates only decide what the generator searches; "cannot perform Hyperbloom" stays a generation fact.
- `AccountModel.assess_lineup(names, roster)` evaluates any legal team:
  - a template-generated assessment when one exists
  - otherwise a "manual" team with four open slots, valued from the lineup alone (no role-rules number)
  - returns `invalid`, `well_supported` or `unusual`, with reasons
- The benchmark's `lineup()` uses it, as the future Team Builder will.

**3. Community build heterogeneity (investigated, no change).**
- **Hu Tao / Xingqiu / Yelan / Zhongli** has three standard submissions with three build keys:
  - Ballad of the Fjords, Zhongli on Archaic Petra: 68.9k
  - two near-identical Deathmatch configs (only Zhongli's artifact set differs): 41.4k and 40.4k
  - the measured structure of those submissions makes Yelan, not Hu Tao, the damage owner, which suggests a weak Hu
    Tao rotation
  - the median is 41.4k; the between-build term (0.285) gives 29.1 ± 8.5
- **Held-out test** (leave one standard submission out, 703 predictions in 180 lineups):
  - none of four aggregation rules predicts better: submitter median, build-vote median, coarse-build-vote median,
    log-mean (median miss 5.1% to 5.2%)
  - judged against the prediction interval, the current sd is calibrated or conservative in every group, mixed
    builds included (84% within 1 sd, 98% within 2)
- The evidence layer already separates within-build and between-build disagreement (`Basis.between_build_sd`), and
  more submitters do not shrink the between-build term.
- `compare()` calls vape against mono-Pyro roughly equal (P 0.32), so the engine makes no confident wrong claim.
  The original benchmark case compares point values only.

**4. False-positive leftover teams.**
- **Furina / Kazuha / Lisa / Noelle** (36.7, pair model, one member from the Neuvillette team) is not a support-only
  team. Noelle is a measured on-field damage dealer (34% of damage, 58% field time), and her simulated Furina teams
  reach 46 to 59.
- **The pair model is calibrated for carry swaps,** with both the true and the runtime-predicted lead: 1,179 held-out
  lineups whose nearest simulation lost its damage owner, 70% within 1 sd and 94% within 2. Its structure names
  Furina as the damage owner (0.91), which affects only the label.
- **The real false positives are lineups nobody carries** (Citlali / Xilonen / Furina / Bennett at 42.8). The
  additive model puts most of a carry's value in the shared intercept.
- **Fix: damage capacity in the pair model.** One jointly fitted term, coef x log(sum of members' average damage
  shares).
  - Cross-validated: median error 6.48% to 6.42%, mean 8.38% to 8.34%; the overprediction of low-capacity lineups
    falls from +5.1% to +3.7%; the coefficient is stable (0.30 to 0.36 across folds; 0.344 fitted).
  - The joint refit compensates through support effects, so the suspect lineups move little (Escoffier / Citlali /
    Furina / Kazuha stays about 50). Inside the simulated range the data cannot call them wrong; a measured no-carry
    team, Yelan / Xingqiu / Zhongli / Kazuha, really reaches 36.4.
- **New typicality finding `low_capacity`:** capacity below the 2nd percentile of simulated lineups (0.52). It marks a
  lineup as extrapolating outside the data, widens its sd (measured x1.81 per finding), and makes it "unusual".

**5. Low-data extrapolation.**
- **No shrinkage.** Held-out bias is about 0 for low-data lineups (least-simulated member with 6 to 20 lineups:
  -1%) and for unseen-with-carry ones, so shrinking expected values is not supported and they are unchanged.
- **Their sd was too narrow:** 63% and 85% within 1 and 2 sd.
- **The functional-distance sd model is now fitted by maximum likelihood** (log-linear, non-negative effects)
  instead of least squares on mean absolute error.
  - held-out log likelihood 1.699 to 1.704
  - low-data coverage 68% and 90%
  - overall 75% and 95%
- **Coverage-flagged groups cannot be held out cleanly,** because coverage is computed from the same data. They keep
  the confidence cap.

**6. Near ties.** `compare()` calls Ayaka with Xiangling against Mona roughly equal (P 0.46). The planner still has
to choose. The account report now lists "Choices the evidence cannot separate": per plan team, the closest one-member
alternative that `compare()` calls roughly equal, with the probability, phrased as a lean rather than a verdict.
Underlying values are untouched.

**7. Useful-team gate removed.**
- **Comparison** (calibration decides; locked is validation only):
  - A, gate 30 plus replacement 20: 86.7%
  - B, replacement only, max(0, value - R), at R = 15, 20 or 25: 86.4%. The difference is one gap-size class on a
    correctly ordered pair (Columbina over Furina at P 0.92 instead of above 0.95).
  - Locked: identical.
- **B is chosen.** It has no cliff (29.6 no longer counts for nothing while 30.0 counts in full), and it removes a
  parameter. A smooth weighting (C) adds nothing, since max(0, v - R) is already continuous.
- **The mode utilities use the same rule.** For the Abyss, 30 is kept only for the "No second team worth building
  yet." note, not inside the objective.

**8. Redundancy stays explanation only.** The pull order is the literal gain alone (tested); kind and redundancy feed
only `_kind` and `_explain`.

**9. Account-power uncertainty** (semantics).
- Current already includes the build model's held-out miss (0.40); Ceiling includes constellation and weapon sds.
  Both now expose `sd_parts`, and the report shows them, e.g. "24 ± 10 (team ±13%, build ±40%)".
- The exact-personal-simulation sd (5%) moved from code to `model.yaml` as a judgment.

**10. Benchmark batch.** Eight calibration cases, Claude's reading of consensus, to be reviewed:
- a close call that must stay close
- support allocation across two hydro carries
- a completing support against a redundant carry
- two weird-but-legal teams and one illegal team
- a support-only lineup that must be flagged and weaker
- a provisional team that must be kit-model

The validity scorer gains `legal` and `support`. 7 of 8 pass; Yelan against Mualani is a tie (P 0.53) where the case
expects a medium lean.

**Changes** (golden: 6 plans, 2 top pulls, 48 kinds; 339 lineups moved more than 0.5, median 0.2; no
exact-community value changed):
- **Power:** low-capacity pair-model lineups drop (up to -5); high-capacity Flins teams rise (up to +2.7).
- **Pair-model sd:** +4% at the median, +72% at the 90th percentile (low-data and low-capacity lineups).
- **Plans:** second teams between 20 and 30 count again.
  - The six-character Ayaka account takes Mona.
  - plan_raiden_and_nahida returns to Raiden national plus hyperbloom (original benchmark now passes it).
- **Kinds:** mavuika_sidegrade_for_arlecchino now labels Mavuika a new archetype. Her plan replaces the leftover
  team without taking Arlecchino's supports. The original benchmark case (the user's earlier correction) fails on
  the label only; she is still not a top-two pick.
- **The user's account:** Columbina is still the top pull (+22.0, B). Mavuika (E: a reshuffled fourth team uses
  Iansan's kit) and Sandrone (E, kit-based) are in the roughly-equal group behind her.

**Verification:**
- 174 tests pass (new: tests/test_reliability_63.py). Audit clean.
- Calibration 89.8% over 42 cases; on the original 34, 87.8% (6.2: 85.8%). Locked 80.7% (unchanged). Original
  benchmark 44 of 46.
- Account report 19 s; review report written.

**Remaining power-model errors:**
- Lineups nobody carries but inside the simulated capacity range: no simulations of such lineups exist to correct
  them.
- Community data quality: the Hu Tao vape submissions disagree by 66%, and the Hu Tao vaporize identity case fails
  because the pooled submissions make Yelan the damage owner.
- Abyss splitting: under min(v1', v2') a 55 team plus nothing loses to 35 plus 30, which is the Abyss objective
  working as specified.

## 2026-10-17: model 6.4, reliability validation pass (final narrow pass before productization)

**Frozen out-of-sample validation** (`gtc/validation.py`, files in data/validation/v64/; report.md has every row).
- **Freeze.** Before any simulation, 35 lineups and every prediction (expected, sd, route, nearest lineup, member
  and functional distance, structure, primary actor, coverage, typicality, capacity, pair effects) were frozen with
  hashes: model 6.3, model.yaml fe59c212, pair_effects.json 3921cce8, uncertainty.json 935cd643, lineups 17fe0d8d.
  Selection rules and seed are in select64.py.
- **The set:**
  - A, carry-less / support-heavy (11): suspected-bad and plausibly-fine teams (distributed, reaction cores)
  - B, optimizer leftovers (7)
  - C, normal controls (6)
  - D, unusual but valid (5)
  - M, community-simulated method controls (6)
- **Simulation.** A lineup without a community config is built from its nearest simulated lineup's accepted
  config, with the fourth member swapped (their build and actions taken from their own best standard config).
  - Harness 1 broke on multi-line statements and stalled on unaffordable Bursts.
  - Harness 2 is statement-level, skips neighbours whose script tests the leaving character, and guards every
    Burst.
  - A run that spends over 25% of the fight waiting on failed actions is unreliable (8 of 35, mostly leftovers).
- **Frozen-model results** (21 reliable A to D rows, support-swap method bias -0.23 log): median absolute log error
  0.21, 57% within 1 sd, 81% within 2.
  - Distributed and reaction-core carry-less teams are at control level.
  - Pure-buffer lineups appeared 2.8x overpredicted.
- **Tested and rejected: a no-number guard below the simulated damage-capacity range.**
  - It removed 207 golden candidates, including plausible Nilou bloom and Xiangling national variants.
  - Held out, the pair model predicts the 75 simulated low-capacity lineups fine (p68 17.5%).
  - A post-hoc harness control showed why: carry-removed swaps of community-simulated low-capacity lineups land at
    41% of their community value (log -0.89, 23 reliable runs, spread 0.65). The apparent pure-buffer
    overprediction was mostly the harness leaving the carry's field time idle.
- **With swap-type corrections:**
  - Carry-removed rows cannot resolve errors under about 2x.
  - Support-swap rows show modest optimism: controls +0.18, unusual-valid +0.37 median, 90% within 2 sd overall.
  - The one clear miss is Furina / Kaveh / Xilonen / Mizuki (+0.97, z 2.6).
- **Fix candidates for carry-less valuation,** fitted on training data only: a capacity hinge, log of the best
  member's share, a no-damage-dealer indicator. None changed cross-validated error, and the hinge and indicator
  coefficients had the wrong sign; none moved the validation misses. Expected values are unchanged; the 6.3
  `low_capacity` finding keeps widening those sds.

**Community evidence quality** (`estimate.community_quality`, `Basis.quality`).
- Labels: good, unconfirmed (one submitter), mixed, poor.
- Inputs: submitter disagreement, between-build sd, and unusual damage ownership (a usual carry present but someone
  else owning the damage).
- Held out, the labels do not predict larger errors than the sd already allows (p68 good 8.6%, mixed 9.9%), so they
  affect presentation and the support status only. A "poor" exact lineup is "unusual", not "well supported".
- **Hu Tao / Xingqiu / Yelan / Zhongli is poor:** submitters disagree by 69%, three builds disagree, and Yelan owns
  the damage although Hu Tao usually carries. Its thresholds are in `model.yaml` (`estimate:`).

**Pulls.**
- **Confidence groups** (`account.pull_groups`): clear recommendation, competitive / roughly equal, or lower-value,
  each candidate compared with the leader only, through `compare()` with the coverage cap. Tested: no claim inside
  the tie zone, no assumed transitivity, a clear leader surfaces when there is one.
- **The account report** shows a Standing column and names the strongest evidence among the competitive pulls.
- **Mavuika** stays "new archetype" (observed change). A separate line reports "Functional redundancy: moderate
  (another on-field carry of an element your top teams already carry)". The original benchmark expectation was
  updated with the reason.

**Locked pull-ranking misses by root cause** (6 imperfect assertions of 7):
- 3 statistically indistinguishable: right direction, smaller gap than expected.
- 1 team power, an unmodelled shred interaction: Escoffier against Furina for Skirk without Anemo.
- 1 team power, a carry-less team valued 35 at capacity 0.54: Escoffier's gain in the hyperbloom case. The
  expectation there is partly debatable, since the account already has a measured Nahida team.
- Gain sds are honest: held out, lineups sharing three members have uncorrelated errors (-0.03), so plan-delta sds
  are not overstated.

**Consensus cases reviewed.**
- 7 are obvious, or correctly encode "roughly equal".
- completing_support_beats_redundant_carry is ambiguous and is now encoded as a low-confidence small-gap lean, with
  the reason.

**Backend contract:** docs/api-contract.md.

**Verification:**
- 182 tests pass (new: tests/test_validation_64.py). Audit clean.
- Calibration 90.2% over 42 cases. The original 34 are 87.8%, unchanged; the 42-case rise from 89.8% is the
  re-encoded ambiguous case.
- Locked 80.7% (unchanged). Original benchmark 45 of 46: the Mavuika expectation was updated; Hu Tao vape is still a
  miss, now shown as poor evidence.
- Golden: evidence_quality field only; no power, plan, pull or kind changed.
- Account report 20 s.

## 2026-10-17: UI MVP (engine frozen at model 6.4)

**UI-0, presentation layer** (`gtc/app/present.py`). Derived from engine outputs; never a score.
- **Team strengths and problems.** Built from identity and centrality, structure, measured conditional buffs, AoE
  ratio, sustain, evidence route and community quality, provisional flags, mechanics coverage, typicality findings,
  execution tags, the current-against-ceiling gap with the least-invested members, and unknown constellations.
- **Substitutions.** One-member swaps from the owned roster: a lineup-power pre-screen, then a full evaluation,
  judged by `compare()`: upgrade, roughly equal, or frees a contested support. They carry their evidence state.
- **Support allocation.** For each plan member, the counterfactual swap with a member of another plan team. It is
  reported when the unit is individually stronger on the other team but the account plan loses with the swap,
  using the plan value and `gain_estimate`, with a tie flag.
- **Pull pros and cons.** Read off the decomposition, the weapon note and the estimate; the gain is never touched.

**UI-1, application service** (`gtc/app/service.py`).
- `AppService` caches the account analysis (about 3.5 s).
- It computes pull values (about 18 s), allocation explanations and the meta plan in a background thread under one
  engine lock.
- Functions: account, characters, team evaluation (any legal team), recommended teams (overlap on and off),
  recommended pulls in confidence groups, what-if, dashboard.
- `gtc/app/server.py`: a standard-library JSON API on 127.0.0.1. `python -m gtc web` starts it.

**UI-2, frontend** (`web/`): plain HTML, CSS and JavaScript modules, no build step. Pages: Dashboard, Team Builder,
Recommended Teams (overlap toggle), Best Pulls, What-If, Characters. Evidence badges are always visible.

**Product fixes found through the UI** (no engine change):
- the lineup-count wording on pull cards
- no-change pulls moved out of "competitive"
- substitutions badged Provisional when kit-based

**Verification:** 189 tests pass (new: tests/test_app.py). Golden outputs are unchanged. docs/ui.md has the
run commands, times and the product issues log; docs/api-contract.md has the implemented endpoints.

## Next: product iteration from real use (log issues; fix by user impact)

## 2026-10-17: model 6.5, advisor layer (driven by UI failures)

**Separate recommendability from power** (`gtc/advisor.py`). Each team gets one of four levels. Recommendability
never changes power.

| Level | Meaning |
|---|---|
| established | simulated by independent submitters who agree, or a guide lists the exact lineup |
| credible | its own simulations, or interpolated next to one with no typicality finding, coverage not unknown, kit conditions met |
| experimental | far interpolation, a typicality finding, coverage unknown, an unmet kit condition, poor community data, or an unlisted provisional kit |
| unsupported | no simulation or interpolation behind the number |

- Partial mechanics coverage is a caution, not a demotion.
- Pair-level guide notes are never full-team proof; only an exactly listed lineup counts.

**The advisor pool** decides what plans, recommended teams and pulls use:
- established and credible teams
- an experimental team only when its core has no credible team, or `compare()` says it beats the best credible team
  of that core
- never an unsupported team

The raw-model plan and values are still computed and shown separately.

**Substitutions** (`substitution_kind`):
- **direct:** keeps the carry, the elements the central mechanics need, any function only the leaving member
  provided (Anemo support, sustain), and the kit conditions, and the result is recommendable.
- **rebuild:** "alternative team style", a different credible team.
- **experimental:** hidden.

On the user's Ayaka / Shenhe / Mona / Kazuha:
- Kazuha to Sucrose and Kazuha to Lan Yan are direct alternatives.
- Mona to Citlali is a rebuild ("Freeze needs Hydro").
- Kazuha to Ineffa is hidden.

**Recommended Teams, overlap on:** one card per core (primary actor, else the owners of the central mechanics, else
the structure owners), with variants underneath, plus a visible "High model value, not recommended" list.

**Pulls:**
- The headline team is the best recommendable team.
- A higher-modelled experimental lineup is shown separately.
- `plan_changes` names the plan slot each gain comes from. Escoffier: "Best team: unchanged (78) ... Team 4: 42 ->
  54 (Kamisato Ayaka / Shenhe / Escoffier / Mona)".

**Kit conditions** (a measured power-model fix; `knowledge/kit_conditions.yaml`, `gtc/kit_conditions.py`, pair-model
terms):
- **The problem:** held out, lineups breaking a support's party condition were overpredicted (+3.0%, 234 lineups;
  every one of Escoffier, Chevreuse, Nilou and Gorou had the same sign).
- **The fix:** one fitted effect per condition. Cross-validated median error 6.41% to 6.25%, unmet bias to +0.6%.
  Escoffier -0.167 and Chevreuse -0.141, stable across folds; Nilou and Gorou near zero.

**Ayaka against Razor** (raw-power diagnostic, no change):
- **Razor / Fischl / Bennett / Chevreuse 64.8:** 3 recent submissions, one submitter, 60 to 68, with the new Hexerei
  buffs.
- **Ayaka / Shenhe / Mona / Kazuha 43.5:** 2 legacy (migrated) submissions, 47.1 and 40.0.
- **Ayaka's newer teams reach 67 to 77** (with Escoffier, Furina, Mavuika).
- **Conclusion:** the model reports its sources faithfully. The classic Freeze data is old. Community quality now
  says "only legacy submissions (migrated from the old database)".

**Verification:**
- 198 tests pass (new: tests/test_advisor.py). Audit clean.
- Calibration 89.2%; the drop from 90.2% is the six-character Ayaka plan's Mona against Xiangling near tie flipping
  (P about 0.5, disclosed).
- Locked 80.7%. Original benchmark 45 of 46.
- Golden: 93 unmet-condition candidates moved (median -2.5) and 40 others by at most 1.6. Top pulls: Furina passes
  Escoffier on rosters with no other Hydro member.

## 2026-10-18: model 6.6, mechanical reasoning layer (M1 to M5)

Pipeline: game facts → structured kits → mechanical reasoning → evidence → power → account optimisation → advisor.
Design: docs/mechanics.md. **The mechanics layer never produces or multiplies power.**

**M1 schema** (`gtc/kits.py`, schema 3):
- Covers behaviour, scaling, effects (with target, filters and conditions), composition conditions, reaction
  relationships, and provenance per field. "unknown" is valid.
- `validate()` covers every character: 17 reviewed kits plus derived kits from measured profiles (effects unknown).
  Game-data weapon spellings are aliased.

**M2 central mechanics** (`gtc/mechanics.py`):
- **Reused:** the reaction table and formulas.
- **Added:** reaction categories, aura states, aura consumption, field-time demand, buff applicability,
  `reaction_of` (channels) and `conditioned_buffs()`.
- **Deleted:** the hand-kept `reactions.REACTION_CONDITIONED_BUFFS`, now derived from the kits'
  `reactions.requires` (identical mapping, so identity is unchanged).

**M3 reference kits** (`knowledge/kits/`): Ayaka, Shenhe, Mona, Kazuha, Sucrose, Raiden, Razor, Escoffier, Chiori,
Chevreuse, Ineffa, Citlali, Bennett, Xingqiu, Furina, Fischl and Nilou.
- **Sources:** facts from the official kit text, reviewed by Claude; human review is pending.
- **Agreement with the measured profiles:** `on_field_damage` agrees for all 17; other behaviour fields are within
  one level.
- **The `each` clause is live:** Chevreuse and Nilou need at least one of each listed element.

**M4 reasoner** (`gtc/team_mechanics.py`): `TeamMechanics` with:
- functions supplied and missing;
- buff and enabler synergies;
- conflicts: field time, aura, broken condition (harm); wasted buffs (caution);
- conditions, reaction dependencies, opportunity losses and kit coverage.

**M5 advisor:**
- **Recommendability:** mechanical harm the evidence does not answer makes a team experimental: field-time
  competition, aura removal by a strong non-carry applier, or a broken `only` condition. A `count` condition below
  full is worded as an opportunity loss and still demotes an unsimulated team.
- **Substitutions:** read critical functions from the kits. The role-based `_functions` is deleted.
- **Explanations and API:** `team_insights` has mechanics strengths and problems; the full team payload carries
  `mechanics`.

**Results on the account:**
- **Raiden / Razor / Bennett / Xingqiu:** experimental (field time; power 45 unchanged).
- **Ayaka Freeze substitutions:**
  - Direct: Kazuha → Sucrose, Kazuha → Lan Yan, Shenhe → Rosaria, Shenhe → Citlali.
  - Rebuild: Mona → Citlali (Freeze needs Hydro); Kazuha → Chiori (only swirl support); Mona → Xiangling (Hydro lost,
    and Pyro removes the Freeze auras).
  - Kazuha → Ineffa is not direct: it loses the only swirl support and removes the Cryo and Hydro auras.
- **Escoffier pairings:** Ayaka / Shenhe / Chiori / Escoffier is experimental (opportunity loss 3/4, power 45).
  Ayaka / Shenhe / Mona / Escoffier is credible and clean (all three buff Ayaka, power 54).
- **Recommendability:** 14 candidate teams newly experimental from mechanics alone: Raiden or Yoimiya with another
  on-field dealer, and Xingqiu or Xiangling in Quicken teams. 3 of them stay in the advisor pool through the existing
  experimental admission.

**Fixed during the phase:** a derived "unknown" was read as true and made Iansan an on-field dealer. Aura removal by
the on-field carry itself is now only a caution.

**Verification:**
- 217 tests pass (new: tests/test_mechanics.py, 19 tests). Audit clean.
- Calibration 89.2%, locked 80.7%, original 45/46: unchanged.
- Golden: only all-Pyro Chevreuse lineups moved, because they now fail her "at least one Electro" clause:
  - Diluc / Bennett / Chevreuse / Xiangling 37.6 → 32.7;
  - Arlecchino / Bennett / Chevreuse / Xiangling 50.5 → 43.8;
  - Arlecchino's Abyss pick and Columbina's pull gain follow.
- No training lineup changed flag, so the pair model was not refitted.

## 2026-10-18: model 6.7, offline kit compiler and roster population (M6 to M9)

**M6, compiler** (`gtc/kitcompile.py`, `python -m gtc compile`; design in docs/mechanics.md):
- **Packets:** official text, scaling tables at talent level 10, measurements, two example kits.
- **Fill:** the LLM runs offline. Fresh subagents read only their packets; `fill_with_api` is an alternative.
- **Checks:** schema; grounding (unnamed talent or ungrounded number means the effect is dropped); the measurement
  guard (behaviour and critical roles); generic normalisation; provenance forced to llm_extracted, pending.

**M7, blind validation against the 17 reviewed kits** (data/compiler/runs/):
- **Run 1 (development).** Valid 16/17, effect recall 0.96, raw precision 0.52, composition conditions 0.63, burst
  cost 0. Diagnosis:
  - 40 of 41 unmatched effects were true kit statements the reviewed kits omit by design (heals, shields, cooldowns,
    Hexerei passives). One was a misreading: Bennett's field "imbues characters with Pyro" taken as an infusion.
  - Condition mismatches came from my own instruction, which put reactions in top-level conditions.
  - Energy cost was not in the packets.
- **Generic fixes:**
  - clarified instructions (composition-only top-level conditions, an integer `full`, `requires` semantics,
    infusion versus applying an element);
  - added scaling tables;
  - replaced raw effect precision with buff precision in the gate. Raw precision is still reported. This revision
    came after seeing run 1 and is disclosed in the code.
- **Run 2 (reported).** Valid 17/17; burst cost 1.00; buff recall 0.97; buff precision 0.98; composition
  conditions 1.00; numeric amounts 1.00; behaviour within one level 1.00; on_field_damage 1.00, with only 3
  measurement overrides. Raw effect recall 0.94, raw precision 0.62. **Accepted.**

**M8, population:**
- 103 compiled kits (433 effects), all valid after checks.
- **Truncation bug:** 18 kits were re-extracted after Normal Attack text was found truncated at 600 characters
  (Arlecchino, Neuvillette, Lyney and others). The cap is now 2500.
- **Check notes:** 41 in total:
  - 11 on_field_damage overrides by measurement;
  - 23 measured critical roles restored (9 swirl support; Lan Yan's compiled kit had omitted it);
  - 4 element-type counts normalised;
  - 2 free-text element lists cleaned.
- **Schema addition:** `party_element_types` (Lynette, Yun Jin).
- **Burst cost unknown** for Mavuika and Skirk: their Bursts use other resources.
- **Every character now has a reviewed or compiled kit.** Derived kits remain the fallback.

**M9, re-test on the account:**

| Case | Result |
|---|---|
| Raiden + Razor | Experimental; no longer in Recommended Teams |
| Ayaka substitutions | Direct: Kazuha → Sucrose, Kazuha → Lan Yan, Shenhe → Rosaria, Shenhe → Citlali. Rebuild: Mona → Citlali, Mona → Xiangling, Mona → Ganyu, Kazuha → Chiori |
| Escoffier + Chiori | Experimental (opportunity loss, 45) |
| Escoffier + Mona | Credible (54) |
| Escoffier pull headline | Ayaka / Shenhe / Escoffier / Mona |

Compiled kits changed no recommendability level (checked with them switched off and on); they add functions,
synergies and explanations.

**Advisor rule:** teams with mechanical harm the evidence does not answer (field time, aura removal, a broken `only`
condition) are never admitted to the advisor pool on modelled power. Pool 227 → 223.

**Verification:**
- 226 tests pass (new: tests/test_kitcompile.py and mechanics additions). Audit clean.
- Calibration 89.2%, locked 80.7%, original 45/46. Golden unchanged.
- Compiled kits never feed power: conditions come only from reviewed kits.

**Pending:** human review of the 17 reviewed and 103 compiled kits. Known schema gaps:
- Stellar reactions (Stellar-Conduct, Stellar Swirl, Stellar Glimmer) have no reaction keys;
- Moonsign has no condition type;
- there are no DEF% or HP% effect kinds.

**M10, UI** (same model 6.7):
- The Team Builder shows a Mechanics card (docs/ui.md): functions, missing, reaction needs, buff edges, conflicts,
  unused potential, and kit badges (reviewed / compiled / derived).
- `kit_coverage` now separates compiled kits from reviewed ones. It previously counted them as reviewed.
- Rendered from the live API for three teams.
- 227 tests pass.

## 2026-10-18: forward model, first stop point (FM-0 to FM-5, FM-7, FM-8, FM-10; experimental)

Design and audit: docs/forward-model.md.

**Status:** not wired into production. Golden files, benchmarks and the model version (6.7) are unchanged.

**Validation (forward vs gcsim's crit-averaged damage on the same traced rotation, house builds):**

| Set | Team | Forward vs gcsim |
|---|---|---|
| Calibration | Ayaka / Shenhe / Kazuha / Mona | −1.2% |
| Calibration | Ayaka / Shenhe / Kazuha / Furina | +1.3% |
| Calibration | Flins / Aino / Ineffa / Sucrose | −1.7% |
| Locked | Ayaka / Shenhe / Escoffier / Furina | −2.1% |
| Locked | Raiden National | +9.2% (+0.9% vs the gcsim mean) |
| Locked | Razor Hexerei | −25% |
| Locked | Neuvillette | −19% |
| Locked | Hu Tao Vaporize | −33% |

The large locked misses are core mechanics with unresolved amounts or triggers (FM-4: no credit):
- Hexerei passives (Razor team);
- Past Draconic Glories (Neuvillette);
- Hu Tao's HP-to-ATK conversion.

They were not annotated, because that would tune on the locked set.

**Fixes found by per-hit diffs against gcsim:**
- a positional-argument bug in the trace;
- Omen as an enemy debuff, applied for the bubble's life;
- effects start when the ability lands;
- statuses persist after a swap, with snapshots only for Kazuha's Burst;
- per-element instances (Kazuha's A4 on Cryo and Hydro);
- Salon multipliers from talent tables, ×(1 + 0.1 per member above 50% HP);
- Cryo resonance from the first Cryo hit;
- Lunar direct hits recognised;
- Ascendant Gleam;
- the house ER target set to 1.1 × the requirement (the bare requirement stalls).

**Tests:** 238 pass (new: tests/test_forward.py, 11 tests).

## 2026-10-18: forward model phases A–F (experimental; production stays at model 6.7)

- **A:** kit language in `gtc/forward/engine.py`:
  - resources, thresholds, concurrent states, rules, ops, summons, procs;
  - state variants with their own CD and energy cost;
  - dynamic effect conditions; reaction-triggered effects.
- **B:** a gauge-based reaction simulator with reaction ICD, plus a summary and a plausibility envelope.
- **C:** 25 frozen kit files with causal blocks.
- **D:** dependency graph and realisation metrics.
- **E:** blind benchmark.
- **F:** 12-team reference set.

**Blind accuracy** (the engine generates the rotation; gcsim is revealed only afterwards):
- median absolute error 12.7%;
- 9 of 12 teams within 15%;
- pairwise ranking agreement 74%.

**Replay accuracy:** median absolute error 13.0%.

**Worst teams:**
- Lunar −19.6%: the Flins energy refund is not in the kit data.
- National −18.4%: Raiden's ER is over-estimated and reaction rates are about half the reference.
- Freeze + HP +16.3%.

The reference set was used while making generic fixes, so it is a development set.

**Fixes:**
- procs keyed on the source action (Rain Swords on Musou NAs);
- concurrent states;
- variant cooldowns independent of the base action;
- every member is a driver candidate when the team has no on-field dealer;
- dual plans only pair real on-field dealers;
- the duplicate Chevreuse annotation removed;
- `test_library_measures_character_facts` now uses the measured path.

**Checks:**
- **Tests:** 256 pass.
- **Audit:** 0 findings.
- **bench and benchmark:** recorded for model 6.7, unchanged, all PASS.
- **Golden:** no changes.

## 2026-10-18: forward model phases G–O (experimental; production unchanged at model 6.7)

**What was added:**
- **G:** realistic standard builds chosen by the forward model, with ER paid from the substat budget against exact per-window targets, and kept only where it pays.
- **H:** a gear effect compiler plus a curated file (test-checked against Amber).
- **I:** the prerelease pipeline, with fingerprint-driven refresh.
- **J:** gear-aware team needs (requires / benefits / avoids); the pair model only breaks ties.
- **K:** causal swap analysis.
- **L:** uncertainty from model knowledge.
- **M:** a simulation-quality record.
- **N:** shadow log.
- **O:** acceptance gates.

**Fixes found by validation:**
- Amplified hits now use gcsim's amplified expected damage (the Melt and Vaporize references had been understated).
- A conditional stat no longer folds into the static build (Blizzard Strayer).
- The Emblem cap is read from its own sentence.
- Buffs on buffs are chained one level (Shenhe's Quill).
- Cryo resonance and enemy-aura conditions are evaluated per hit from the aura simulation.
- Reference ER is iterated until the community script keeps its shape (National: a 618 s stall became 106.5 s).
- Carry windows no longer overrun their cycle.
- The cycle length is searched, and a skill-only plan was added.

**Benchmark, 12 teams, every reference keeping its shape:**

| Profile | Blind median | Replay median | Pairwise ranking | Within 15% |
|---|---|---|---|---|
| Neutral | 11.6% | 5.7% | 78.8% | 10 of 12 |
| Standard (realistic) | 19.0% | 4.5% | 78.8% | 6 of 12 |

Standard blind failures beyond 30%:
- Vaporize −36%: the brain still Bursts with Hu Tao.
- Lunar −36%: Flins's energy refund is unknown.
- Aggravate −33%.
- Hyperbloom −30%.
- Dual window −30%.

**Gates (standard):** 1, 5, 6 and 7 pass; 2, 3, 4 and 8 fail (Lunar idles 18 s); 9 is pending the shadow log.
- Decision: do not switch power; stop before P.
- Lohen pipeline: 6 teams, best Lohen / Fischl / Furina / Shenhe at 35.3k, mostly Low confidence (Lohen's unknown accrual mechanics).
- Runtime: about 2–5 min per team with realistic builds; the pipeline took 1.8 h, because swaps re-optimise builds.

**Tests:** 271. New: test_gear (8), test_phases_gn (7). test_generator's Raiden/Razor assertion was changed to its invariant (dual loses, a single carry is chosen); the 15% margin was calibrated on the overrunning generator.

## 2026-10-19: diagnosis round (execution parity; production unchanged at model 6.7)

**Added**
- Failure decomposition: calculator error, selection regret, search regret.
- A generated-rotation → gcsim converter.
- An action-by-action parity comparator with classified delays and an energy ledger.
- Measured frame data (`knowledge/forward/frames.json`: per-transition locks, hitlag, particle travel, cooldowns per variant, swap cooldown) and a stamina model.
- Steady-state scoring over cycles 2–5 of 6.
- A bounded strategy search: explicit drivers, and Burst cadence chosen by marginal value per member.
- Runtime bounds and caching; gate 10 (parity, report only).

**12-team decomposition** (neutral builds):
- Duration error 1–9% on 9 teams.
- Vaporize +14%: energy waits.
- Neuvillette +75%: held-charge timing unknown.
- Lunar +281%: Flins energy, a data-coverage failure.

**Tests:** 271 pass. Three assertions were updated to the intended behaviour:
- Favonius returns (cooldown, chance).
- Any member may drive.
- The period is searched (no fixed value).

## 2026-10-19: diagnosis round 2 (energy, Neuvillette, reaction events, transition timing; production unchanged)

**Fixes**
- Favonius: procs while the wearer is active, resolved at landing time, expected value.
- Measured Normal/Charged-hit flat energy.
- Measured particle schedules.
- Neuvillette Sourcewater Droplets (`duration_by_resource`).
- Reaction procs (Fischl's A4 from the kit text).
- Quicken coexistence (Aggravate, Spread, Hydro on Quicken), EC ownership, every Dendro core triggering.
- Measured executed-to-executed transition gaps (by chain position); unobserved transitions are never faster than the measured queue lock or the kit duration.

**12-team decomposition** (neutral)

| Measure | Value |
|---|---|
| Median duration error | 3.5% |
| 90th percentile duration error | 14.2% |
| Median same-rotation calculator error | 10.5% |
| Teams within 5% / 10% / 15% | 3 / 5 / 8 |
| Ranking agreement, forward vs gcsim (same rotations) | 70% |

**Tests:** 271 pass. Two assertions updated:
- Quicken coexistence (two Quicken events).
- Swap rounding tolerance.

## 2026-10-20: validation layer, calculator parity and search round 1 (production unchanged)

**Validation layer**
- `gtc/forward/results.py`: multi-label failure taxonomy with MODEL / DATA_COVERAGE / MIXED verdicts, a SQLite store of every decomposition with cohort metadata and model version, and residual analysis (cohorts, correlations, label Pareto).
- `knowledge/forward/coverage.yaml`: data-coverage gaps and measured assumptions.
- `tests/test_metamorphic.py` (126 metamorphic tests).
- `gtc/forward/sensitivity.py` (one-variable sweeps with anomaly flags).
- Shadow log stored per version.

**Calculator and execution parity.** Each item below is a generic mechanic, measured in gcsim logs of non-reference teams; no correction multipliers.
- **gcsim translation:**
  - The generator records the transition it used (`Action.earliest`), so the gcsim script carries only real idle.
  - The swap cooldown runs from the swap's completion.
  - Tap or hold is decided by one shared test (`frames.is_hold`).
- **Procs on actions** (`event: action`, `delay`, `sustained`): Rain Swords and Exquisite Throw fire on the Normal Attack action. An ICD that expires mid-attack fires right then (modal spacing 1.00 s).
- **Damage-free applications** become zero-damage hits. Xingqiu's Rain Screen orbitals are a summon (first at 0.9 s, then every 2.25 s).
- **Frame probe** (`frames.probe`): single-character scripts for transitions the community rotations never play.
  - Gaps are kept per Burst segment (`B:`), and per reduced-cost Burst variant (`burst~partial`).
  - Gaps that contain a refused action are excluded.
- **State variants:**
  - `uses_per_state` caps a variant; once spent, the base action returns.
  - `ends_on_swap` states.
  - `infuse` states make Normal/Charged/Plunge hits Physical outside the infusion (Hu Tao).
  - `action_rules.unavailable_after` (Fischl's Skill while the Burst's Oz is out).
- **Summon groups** (one Oz from Skill or Burst) and named ICD groups.
- **Kit data:**
  - Flins: Thunderous Symphony once per window, lost on swap; Manifest Flame ends on swap.
  - Chevreuse: the press shot is Press DMG. Overcharged Ball is listed as a coverage gap.

**12-team decomposition (neutral builds, r5)**

| Measure | r3 | r5 |
|---|---|---|
| Same-rotation calculator error (median) | 10.5% | 3.4% |
| Duration error (median) | 3.5% | 0.9% |
| Ranking agreement | 0.758 | 0.833 |

Lunar improved from +262% to +2%, Hu Tao from +30% to +3%, and Overloaded from +22% to +2%.

**Search round 1** (calculator frozen)
- **Structural profile** (`gtc/forward/structure.py`): reference vs generated rotations, both as gcsim executed them. Idle is now taken from gcsim's refused-action frames and explicit waits.
- **Support policy, level 2** (wait / defer / recast): a support whose Skill is not ready is visited inside the carry window instead of waited for.
- **Search alignment:** the decomposition now runs the same stages as the blind search (Burst cadence, then policy).

## 2026-10-20 (later): calculator fixes from search, strategy language v1, expressiveness (production unchanged)

**Calculator bugs that stronger search exposed.** Each was fixed at its first event-level divergence.

| Team | r6 | After | Cause |
|---|---|---|---|
| Melt | +19% | +3% | Bennett's Skill cooldown measured per context (own Burst field, 1 s field tick) |
| Overloaded | +15% | −5% | Same cooldown context; attack gaps kept per Burst segment (`N:` / `B:`) |
| Hyperbloom | −16% | −8% | See below |
| Aggravate | −17% | −8% | Sesshou Sakura as a summon (several instances, level by instance count) |

Hyperbloom had several causes:
- A positional `HitTemplate` call put the source string into `scale_trigger`, so every table-linked proc hit was scaled by its trigger's multiplier.
- The scaling stat now comes from the table row's text, and rows with several terms (ATK + EM) are summed.
- A measured dash lockout.
- The Bloom gauge sides were swapped (Dendro on Hydro is 2×, Hydro on Dendro is 0.5×).
- Dendro on Electro-Charged forms Quicken first, then Blooms with the rest.

Later additions:
- The Normal Attack chain wraps by the length of the Amber string.
- Missing chain positions are filled from the Amber tables.
- State `lead`: Raiden's Musou runs from the end of the Burst animation.

**Search and strategy language**
- Plans add `protect_state` (the driver keeps a state that a swap would end) and `family` ("quickswap": no long driver).
- Cycle families are reported: SHORT, STANDARD, LONG, ALTERNATING, DUAL_WINDOW, QUICKSWAP.
- Level-2 search combines cycle length × support policy × state protection over diverse seeds: the two best support orders of every driver × opening × refresh. Level 3 tries attack strings on the best plan of every driver and opening.
- The decomposition searches with per-plan builds (as the blind search does).
- The scored rotation is always scheduled with its scored build. Members whose Bursts come late get +0.2 ER, the same rule the reference's builds use.

**Validation**
- `gtc/forward/expressive.py` projects each reference onto the strategy language and plays the projection in gcsim: EXPRESSIBLE ≥ 95%, PARTIAL ≥ 85%, else NOT. Missing capabilities come from the remaining structural deltas.
- `results.taxonomy`: CALCULATOR / TRANSLATION / STRATEGY_EXPRESSIVENESS / ROTATION_SEARCH / ROTATION_SELECTION / DATA_COVERAGE.
- Structure profile: damage per action and support recasts per minute. Idle is taken from gcsim logs.
- State realisation now measures against each state's nominal end, so a swap that ends a state early counts as a loss.

**National, the scheduler control:** the engine's best generated strategy scores 24.8k in gcsim against the community reference's 23.7k. Musou realisation is 95%.

## 2026-10-21: r8, engine frozen, first hidden validation (production unchanged)

**r8 (development set, 12 teams)**

| Measure | Value |
|---|---|
| Median calculator error | 5.1% (worst: National −12%) |
| Median search regret | −5.1% |
| Teams within 5% / 15% of the reference | 9 / 10 |
| Median selection regret | 0.4% |
| Generated strategy beats the reference (gcsim) | 8 teams (7 for the selected strategy) |

Fixes in this round:
- Hitlag extends the character's own states.
- Shrine of Maya shortens the Tri-Karma interval (`icd_reduce`).
- A Swirl uses up the Anemo hit's durability.
- Fanfare resets at each Burst cast.
- A re-cast cancels the previous cast's lingering hits.
- Random energy drops are scheduled at their slowest interval.
- New `event` support policy.
- Runtime: the per-team search went from 229 s to 64 s by splitting schedule and finalize, caching, precomputing proc lists, and memoising identical schedules.

The engine was frozen at fm-2026.10.21-r8.

**Hidden set** (`gtc/forward/hidden.py`): 17 teams that were neither development teams nor kit sources, with no logs used for frame data. They are excluded from all measurement.
- Predictions frozen 02:55 (kits `e63fecc4…`, frames `64e44681…`).
- Revealed 02:59, with the engine unchanged since the freeze.
- The first result is `data/validation/hidden_first_result.json`, never overwritten.

| Measure | Development | Hidden (15 valid teams) |
|---|---|---|
| Median calculator error | 5.1% | 3.4% |
| Median search regret | −5.1% | +1.6% |
| Teams with search regret ≤5% / ≤10% / ≤15% | 9 / 9 / 10 of 12 | 9 / 13 / 15 of 15 |
| Median blind error | 8.1% | 11.4% |
| Median selection regret | 0.4% | 1.5% |

- **Excluded:** two Overloaded references are invalid under the neutral house builds. They reach 10–12% of their community-recorded DPS, against 27–54% for every other team. They are left out of the aggregates above.
- **Calculator outliers:** Lunar (Razor) −29%, Hyperbloom / Quicken +18%.
- **Selection misses:** Hu Tao + Furina and direct hypercarry, both above 12%.
