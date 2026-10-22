# Improvement plan

Fifteen known problems, each with an implementation approach, data model changes and a validation test.
The guiding split is five separate questions, each answered by its own layer:

| Layer | Question | Module |
|---|---|---|
| Validity | Can this composition function at all? | `gtc/validity.py` (new) |
| Archetype and structure | What kind of team is this, and where does its damage come from? | `gtc/structure.py` (new) |
| Power | How strong is it under standard conditions? | `gtc/evidence.py`, `gtc/synergy.py` |
| Account fit | How much does it improve this account? | `gtc/account.py` |
| Confidence | How far can this number be trusted? | `gtc/estimate.py` (new) |

One principle runs through all of it. **Wherever gcsim's per-hit logs can measure something, measure it
instead of hand-tagging it.** The synergy database already parses every hit of 3,800 simulated lineups:
who applied which element, who triggered which reaction, field time, damage share, and every buff with
its value. Several fixes below come from those logs at little extra cost.

---

## Shared foundation: a measured capability profile per character

Problems 1, 2, 3, 7 and 9 all need to know what a character actually does in combat. Today that comes
from hand-set role tags. The proposal is a capability profile measured from the logs.

**Data model:** `data/sources/capabilities.json`, one entry per character, aggregated over every
simulated lineup they appear in:

```yaml
Kuki Shinobu:
  field_time_share: 0.06        # share of rotation time on field
  application:                  # element applications per 10 s, off-field and on-field
    Electro: {off_field: 4.1, on_field: 0.3}
  triggers:                     # reactions this character triggers per 10 s
    hyperbloom: 3.8
  damage_share: 0.55            # median share of team damage when present
  buffs_given: {em: 0.0}        # from the synergy attribution
  heals: true                   # healing events observed
  shields: false
  evidence: {lineups: 41}
```

**Source:** gcsim sample logs. The "application" events, the reaction "triggered" events, the
`field_time` statistic and the `heal` and `shield` events are all already in the logs we parse. This
adds one aggregation pass to `gtc/synergy.py` and needs no new simulations.

**Hand-written overrides** stay possible, in `knowledge/capabilities.yaml`, for characters with no
simulations. Every override is marked as unmeasured.

---

## 1. Invalid team generation

**Approach.** Split teams into a validity stage and a strength stage. Every archetype declares hard
requirements as capability thresholds. A lineup that fails them is rejected before scoring, so it can
never compete in the plan.

**Data model.** Archetype templates gain a `requires` block over measured capabilities, and archetype
discovery derives these thresholds automatically. For each discovered family, the requirement is set at
the 10th percentile of what the family's own simulated lineups provide.

```yaml
hyperbloom:
  requires:
    - {capability: application.Dendro.off_field, team_total: ">= 3"}
    - {capability: application.Hydro, team_total: ">= 3"}
    - {capability: triggers.hyperbloom, any_member: ">= 1"}
  forbids:
    - {element: Pyro, unless: "triggers.burgeon"}   # archetype-specific exclusions
```

**Why measured, not hand-tagged.** Kuki's "electroApplication: 0.9" would be my guess. Measured
off-field Electro applications per 10 seconds are a fact from simulations, and they stay correct when a
character is buffed.

**Validation:**
- **Recall:** at least 98% of the community-simulated lineups in each family must pass their own
  family's validity check. Anything lower means the thresholds are too strict.
- **Rejection:** a hand-written list of known-invalid teams must all fail. It starts from the cases
  you found: Neuvillette in Mono Pyro, Mizuki leading Hyperbloom, Razor with Kazuha in Overloaded,
  Skirk with Chiori and Lan Yan.
- **Regression:** your account's plan and the scenario tests must contain no team on that list.

## 2. Fragile carry guessing

**Approach.** Classify teams by damage structure, measured from simulated damage shares, instead of
forcing a single carry.

| Structure | Rule, from measured damage shares |
|---|---|
| Hypercarry | one member deals at least 55% |
| Dual carry | two members each deal at least 25% |
| Reaction core | reactions deal at least 50% of team damage |
| Driver | the on-field member has the most field time but under 25% of damage |
| Distributed | none of the above |

The thresholds live in the central config (problem 12).

**Data model.** The synergy database gains `structure`, `reaction_damage_share` and per-member
`field_time_share` for each lineup. A team's evaluation keys on its structure. A hypercarry team is
judged against its carry's other teams; a reaction-core team is judged against other teams with the
same core (problem 3).

**Unsimulated lineups** get a predicted structure from members' capability profiles, and the
prediction carries lower confidence.

**Validation:**
- **Structure prediction:** predict structure from capabilities for held-out simulated lineups and
  compare it with the measured structure. Target at least 90% agreement.
- **Tier stability:** archetype tiers must stop changing when a carry label changes. Today relabeling
  one team's carry can move its tier by 20 points or more.

## 3. Missing non-carry teams

**Approach.** Replace the carry-to-teammate table with a fitted model of character and pair effects,
estimated over all 3,800 standard lineups at once:

```
log(team DPS) = family effect + Σ character effects + Σ pair effects + noise
```

This is ridge regression: least squares with shrinkage toward zero, so pairs seen only a few times
don't get extreme values. A pair effect is how much better a pair does together than its two members
do separately, which is exactly "Nahida + Kuki = Hyperbloom core," with nobody labeled the carry.

**Data model:** `data/sources/pair_effects.json`, holding the effect for each character and each pair
within each family, plus standard errors.

**Why a fitted model instead of averages.** Raw pair averages are confounded. Pairs that appear
alongside strong third members look better than they are. The regression separates the pair from the
rest of the team. As a side effect, it also predicts lineups two or more members away from any
simulation, which is problem 4.

**Validation:**
- **Hold-out accuracy:** 5-fold cross-validation over lineups, measuring median error in DPS against
  today's 4.9 points for one-member swaps and 13 points for larger changes. The target is under 8
  points for two-member changes.
- **Coverage:** Hyperbloom, taser and Burgeon cores must appear with non-zero, significant effects.

## 4. Large lineup changes

**Approach.** Every number becomes an estimate with uncertainty. Ranking becomes probabilistic.

**Data model:** a new type in `gtc/estimate.py`.

```python
@dataclass
class Estimate:
    value: float
    sd: float            # one standard deviation
    tier: str            # A to F, see problem 8
    sources: list[str]
```

Each evidence tier's standard deviation is measured from hold-out residuals, never chosen by hand:

| Evidence | Typical sd, measured |
|---|---|
| Personal simulation, several runs | about 1 to 2 points |
| Community lineup, aggregated | about 4 points (the noise floor) |
| One-member synergy swap | about 6 points |
| Pair-effect model (problem 3) | measured after fitting |
| Calibrated model only | about 16 points |

**Ranking.** For two teams, P(A > B) = Φ((A − B) / √(sd_A² + sd_B²)), where Φ is the standard normal
distribution. Reports say "A is likely better" only when P is above 0.8. Below that, the two are shown
as roughly equivalent. The plan search optimizes expected value minus a risk term, which replaces the
fixed 5-point estimate discount.

**Validation:** check calibration on held-out lineups. About 68% of true values should fall within
±1 sd, and about 95% within ±2 sd. If coverage is off, the tier sds get corrected.

## 5. Simulation noise

**Approach.** Aggregate repeated simulations of the same lineup instead of trusting one.

**A bias to fix now.** Several places in the code use the best simulation of a lineup. Taking the
maximum of noisy measurements is biased upward, more so for popular lineups with many submissions,
which inflates exactly the teams the community likes. Switch to the median, or a 20% trimmed mean when
there are five or more simulations.

**Data model.** Each lineup record stores `dps_median`, `dps_sd`, `n_sims` and `submitters`. The sd
feeds problem 4.

**Decision rule.** No recommendation separates two options whose difference is smaller than the
combined noise, unless independent evidence such as guides or synergy points the same way.

**Validation:**
- **Hold-out comparison:** prediction error with median aggregation against max aggregation.
- **Popularity bias:** the correlation between how many simulations a lineup has and its measured
  fit should drop. It's positive today.

## 6. Marginal synergy does not compose

**Approach.** Use exact Shapley values per hit, computed directly from the formulas, with no sampling.

Each hit has at most four providers: the attacker and three teammates. Recomputing the hit with every
subset of providers' buffs removed takes 2⁴ = 16 formula evaluations, which is cheap. Each provider's
Shapley value is their average marginal contribution over all orderings. Shares then sum exactly to the
difference between the fully buffed hit and the unbuffed hit, with overlaps split fairly.

**Data model.** Store both views per lineup and member: `marginal` (what removing them alone costs) and
`shapley` (their fair share of a sum that adds up exactly). Explanations use Shapley. Swap estimates
keep using marginal values, which answer the swap question directly.

**Validation:**
- **Additivity:** across all lineups, Shapley shares must sum to the buffed-minus-unbuffed total
  within floating-point error.
- **Hand check:** on a hand-built two-buff example, compare with a hand calculation.
- **Swap accuracy:** check whether Shapley or marginal values predict swaps better on the hold-out set.

## 7. Reaction value split equally

Two separate problems hide here.

**Bonus values.** gcsim logs which reaction-bonus sources are active, but not their values. The fix is
to read the values from gcsim's source code once. There are about 20 sources, including Viridescent
Venerer, Crimson Witch, Thundering Fury, Flower of Paradise Lost, Nilou, Mona C1 and Lauma. They go in
`knowledge/reaction_bonuses.yaml` as value formulas, the same format as kits.yaml. With known values,
splits become exact. An unknown source makes the split explicitly uncertain instead of equal.

**Enablement is the bigger gap.** Xingqiu with Hu Tao currently shows 22% own damage and almost nothing
else. In reality his Hydro aura is what makes every Vaporize possible. The logs record who applied each
aura and which hit consumed it. The amplified portion of each hit, multiplier minus 1, can be credited
to the aura's applier as "reaction enablement." The same goes for transformative reactions:
Hyperbloom needs a Dendro core, which needs Hydro and Dendro applications.

**Data model.** Contributions gain a kind, `enablement`, alongside the buff kinds.

**Validation:**
- **Hand checks:** Xingqiu's value with Hu Tao should rise to a level comparable with Furina's. Yelan's
  and Xingqiu's Vaporize values should be ordered as Keqing Mains orders them.
- **Hold-out:** the one-member swap error, 4.9 points today, should drop for Vaporize and Melt families,
  where enablement matters most.

## 8. Characters without simulations

**Approach.** Make the evidence tier explicit everywhere, add a manual kit path for new releases, and add
a data audit.

| Tier | Evidence |
|---|---|
| A | Personal simulation of this exact lineup |
| B | Community simulation of this exact lineup |
| C | One-member synergy swap from a simulated lineup |
| D | Pair-effect model or kit formula estimate |
| E | Rules only: roles, guides, tier lists |
| F | Insufficient data. Shown as "cannot evaluate," never silently guessed |

**Data model.** Every Estimate carries its tier. Pull values report the lowest tier among their
supporting estimates. New characters can be described in `knowledge/kits_custom/` with
`expected_archetypes`, `capabilities` and `effects`, and come out as tier D at best until simulations exist.

**Audit:** `python -m gtc audit`. For every character in the game it checks game data, roles,
simulations, carry assignment, and whether they can appear in any valid team. It lists contradictions,
for example "Cyno: has a carry role but appears in zero candidate teams," with the reason. Cyno's
actual bug will show up there.

**Validation:**
- **Clean audit:** zero unexplained anomalies.
- **Tier spot checks:** spot-check that each tier's measured sd from problem 4 is ordered A < B < C < D.

## 9. Formula calculator coverage

**Approach.** The effect format already exists in kits.yaml. What's missing is the data, and the logs
can supply most of it automatically:

- **Buff effects:** every buff key in the logs has a stat, a value and an uptime, measured as the share
  of the receiver's hits where it was active. A generated `knowledge/generated/kits_auto.yaml` would
  cover every simulated character's team buffs.
- **Own damage:** talent multipliers come from Project Amber's datamined tables, which we already
  download. Hits per rotation come from the logs.
- **Hand-written kits** remain for unreleased characters and override generated ones.

**Validation:** extend `python -m gtc.tc.validate` from 5 Lunar swaps to a sample of 200 one-member swaps
across all families, comparing calculator predictions with full simulations. The target is within 10% for
90% of swaps.

## 10. Single target only

**Approach.** Report team power by dimension.

- **Single target:** the existing number.
- **AoE:** run our own gcsim simulations of the top lineups per family against 3 targets, which only
  needs a change to each config's target lines. Then measure each lineup's AoE ratio, 3-target DPS
  divided by single-target DPS. Unsimulated lineups use their members' measured ratios.
- **Rules-based fallback:** tags like `large_aoe`, `grouping` and `single_target_locked`, mined from
  Prydwen tags and Keqing Mains pros and cons, for characters without multi-target data.

**Data model.** Assessments gain `power: {single_target, aoe, sustain}`, each an Estimate.

**Validation:**
- **Ordering:** AoE ratios should order known AoE carries (Xiangling, Nahida, Raiden) above known
  single-target carries (Ayaka burst aside, Tartaglia, Eula), matching Keqing Mains' statements.
- **Consistency:** compare against the 270 multi-target simulations already in the database.

## 11. Content modes

**Approach.** Content profiles reweight the account plan without changing team power.

```yaml
profiles:
  abyss:      {teams: 2, weights: {single_target: 0.5, aoe: 0.5}}
  stygian:    {teams: 1, weights: {single_target: 1.0}, boss_tiers: prydwen.stygian}
  theater:    {teams: breadth, element_coverage: 0.4, duplicate_role_penalty: 0.3}
  general:    {teams: 4, weights: {single_target: 0.6, aoe: 0.4}}
```

**Theater needs a different objective,** not just different weights. It's the number of distinct
characters across elements that can field competent teams, not the best four teams. That's a coverage
optimization with its own search.

**Validation:** add per-profile scenarios to the test suite. For example, an account with one
super-carry and a narrow roster should rank high in Stygian and low in Theater.

## 12. Hand-chosen constants

**Approach:**
1. **Move every tunable value into one versioned file,** `knowledge/model.yaml`, with
   `model_version`. That includes the plan weights, sidegrade factor, carry bar, estimate penalty, ESTIMATE
   table, thresholds and anchoring rules. A test scans the code for numeric literals in scoring logic.
2. **Build a benchmark** in `knowledge/benchmark.yaml`: accounts, a question, and the expected expert
   answer as an ordering or a set of acceptable answers. Start from the six scenarios and grow it to
   40 or more cases, including ones you write.
3. **Tune only against the benchmark,** with leave-one-out cross-validation, so 40 cases don't simply
   get memorized.
4. **Record the model version** in every report.

**Validation:**
- **Benchmark score with cross-validation,** reported per model version.
- **Reproducibility:** no constant changes without a version bump, and no version bump without a
  benchmark run.

## 13. Artifact quality

**Approach.** Rate artifacts by useful rolls:

- **Stat weights per character** come from the Keqing Mains substat priority already parsed, plus
  scaling stat and Energy Recharge target.
- **Useful rolls** = Σ over substats of (value ÷ one average roll) × weight. Energy Recharge only counts
  up to the team's requirement.
- **Normalize** against a well-built benchmark of about 30 useful rolls across 5 pieces, which can be
  tuned.
- **Where a personal simulation exists,** its "standard artifacts" variant measures the real gap. It
  overrides the rule and calibrates it.

**Data model.** Investment's artifact component becomes `artifacts: {useful_rolls, quality, saturation}`.

**Validation:** for characters with personal simulations, compare useful rolls with the simulated
artifact gap. Target a rank correlation of at least 0.7.

## 14. Account data levels

**Approach.** Snapshots carry `data_level: basic | full`, and every recommendation that depends on
inventory carries a confidence note. Most of this exists already through `has_inventory`; what's left
is plumbing it into Estimate.

**Validation:** with a basic import, reports must never claim that a spare weapon or artifact swap
doesn't exist.

## 15. Assumed ascension and Energy Recharge top-up

**Approach.** Run two simulation modes:

- **Potential:** today's behavior, with Energy Recharge normalized.
- **Reality:** no top-up. To keep gcsim from stalling on an unaffordable burst, rotation lines are
  rewritten so a burst that isn't ready is skipped:
  `X burst;` becomes `if .X.burst.ready { X burst; }`. The gap between the two modes, in damage and in
  bursts skipped, is reported as the cost of the Energy Recharge shortfall.

Ascension comes from the snapshot where the data has it. HoYoLAB gives weapon ascension; a scanner
export gives character ascension.

**Validation:**
- **Rewriter safety:** the rewriter must leave every community config's DPS unchanged when Energy
  Recharge is sufficient, tested over the 3,800 configs.
- **Ordering:** reality-mode DPS must sit between the raw stalled run and the potential run.

---

## Order of work

| Phase | Problems | Why first |
|---|---|---|
| 1. Measure capabilities and structure | Foundation, 1, 2, 5 (median fix) | Valid, correctly classified teams come first. Precision on nonsense teams is useless. |
| 2. Fair values | 7 (enablement and bonus values), 3 (pair model), 6 | Correct credit for appliers and cores, and predictions for larger lineup changes |
| 3. Confidence | 4, 8 (tiers and audit) | Every number honest about its uncertainty |
| 4. Calibration infrastructure | 12 | Benchmark and versioning, so later tuning is measured, not guessed. The benchmark starts in phase 1 and grows. |
| 5. Breadth | 10, 11, 13, 9, 15, 14 | Content profiles, AoE, artifacts, generated kits, reality mode |

**Regression gate for every phase:**
- **Tests:** the full test suite, including scenarios, passes.
- **Hold-out metrics:** swap error, calibration coverage and the structure agreement rate don't get worse.
- **Golden reports:** a fixed set of accounts gets compared before and after, and every change in their
  plans or top pulls is explained.

## Status

**Phase 1 is done (2026-10-10).** What it delivered, against its targets:

| Check | Target | Result |
|---|---|---|
| Archetypes keeping their own simulated teams | 98% each | 25 of 35 at 98% or more, all at 90% or more |
| Known invalid teams rejected | all | Neuvillette in Mono Pyro, Kazuha / Raiden / Shenhe / Citlali as Anemo carry, Skirk without Cryo and Hydro teammates, Razor with Geo in Overloaded |
| Structure prediction on held-out lineups | 90% | top damage dealer 86%, category 75% |
| Swap estimate, held out | no worse | 9.0% median error, against 10.8% for "no change" |

**Below target, and why:**
- **Recall.** The misses are mostly lineups the slot matcher places in archetypes they do not play, such as
  Mualani Vaporize teams fitting the Freeze slots. Rejecting those is correct; a stricter membership test
  would raise the number without changing behaviour.
- **Structure category.** Its thresholds (55% for a hypercarry) sit inside the 5% simulation noise, so
  near-threshold teams flip. The top damage dealer, which decides the team's lead, is the more useful figure.

**Phase 2 is done (2026-10-10).** Against its targets:

| Check | Target | Result |
|---|---|---|
| Reaction-bonus split | exact values | read from gcsim's per-hit "[React Bonus]" records, no hand table needed |
| Xingqiu with Hu Tao | close to Furina | 42% against Furina's 42% (enablement 18%) |
| Yelan and Xingqiu for Vaporize | Keqing Mains order | Yelan 48%, Xingqiu 42% |
| Shapley additivity | exact | tested; shares sum to buffed minus unbuffed |
| Pair model, held out | under 8 points for two-member changes | 11.0% DPS error two or more away; 6.2% one away |
| Hyperbloom, Burgeon cores | significant | yes (z 2.5 to 3.3) |
| Taser core | significant | no: Fischl with Beidou is -3.5%, not significant |
| Swap error in Vaporize and Melt | drops with enablement | no: enablement does not improve swap predictions |

**Decisions from the validation:**
- **The pair model replaced the swap estimate** as the first estimate for unsimulated lineups. It beat it in
  every archetype on identical held-out swaps.
- **Enablement and Shapley values feed explanations and teammate ratings, not swap estimates.** Neither
  improved swap predictions.
- **The pair model has separate lead effects.** Without them, Mavuika's strength as a carry was credited when
  she filled a support slot.

**Phase 3 is done (2026-10-10).** Against its targets:

| Check | Target | Result |
|---|---|---|
| Coverage of measured sds | about 68% within 1 sd, 95% within 2 sd | 63 to 73% and 91 to 95% per tier |
| Tier sds ordered | A < B < C < D | yes, after ordering tiers by measurement: swaps moved below the pair model |
| Clean audit | zero unexplained anomalies | zero, with 14 explained gaps |
| Cyno | explained | no longer a problem: leads valid teams in four archetypes |
| Chevreuse at 6% | explained | an alias bug: 38 gcsim short names were unrecognised; now 48% |

**What changed:**
- **Estimates.** Every team value carries an sd and a tier, ranking uses expected minus 0.674 sd instead of
  fixed discounts, pull values show confidence, and comparisons say "likely better" only at 80% or more.
- **Audit.** `python -m gtc audit`, which found the alias bug.
- **Hand-written kits** in knowledge/kits_custom/ can place unsimulated characters in teams, as tier E.

**Phase 4 is done (2026-10-10), with one target not met.**

| Check | Target | Result |
|---|---|---|
| Tunable values in one versioned file | all | 32 values in knowledge/model.yaml, model 4.0; a scan test guards it |
| Model version in every report | all | account, review, team report and audit |
| No change without a version bump and a benchmark run | enforced | test fails on a fingerprint mismatch |
| Benchmark | 40 or more cases | 46 |
| Benchmark score, cross-validated | reported per version | 100%, but see below |

**The benchmark does not yet discriminate.** Every one of 27 tried combinations of the ranking risk, the
sidegrade factor and the unproven-teammate quality passes all 46 cases, and so do extreme values (a risk of 5,
no sidegrade discount). The parameters do reach the engine, since a risk of 5 drops team potentials from 74 to
50, but the cases are orderings that hold across wide ranges. Tuning therefore changed nothing, and the 100%
says the engine gets these orderings right, not that its parameters are well chosen. It needs cases whose
answer depends on magnitudes: close calls between two pulls, when a sidegrade is still worth it, how much a
weak fourth teammate costs. Cases written by the user are the most valuable here.

**Benchmark cases changed after the first run** (35 of 46 passed at first):
- **Fixed in the runner:** archetype questions now ask that archetype directly, and plan questions can name
  a member. National's top damage dealer is Xiangling, so "Raiden's team" was the right question, not
  "Raiden-led".
- **Over-specified case fixed:** Skirk with one off-element flex teammate is fine. The invalid case is two
  of them, which another case covers.
- **Relaxed because gcsim data disagrees with the expected answer:**
  - Hu Tao / Yelan / Bennett / Kazuha simulates 75k against 41k for double Hydro with Zhongli.
  - Xiao / Furina / Bennett / Xianyun simulates above the Faruzan version.
- **Pull questions narrowed** to support-only pools where the question was which support completes a team.
  With carries in the pool, the engine rightly values a whole new team on a small roster.
- **Engine fixed:** a carry's teammate needs now also apply when no single damage owner is predicted (Skirk
  with Chiori, Kazuha and Lan Yan). One teammate of an element never seen with a carry is allowed as a flex
  slot, so Skirk / Furina / Escoffier / Zhongli forms again.

**Phase 5 is done (2026-10-10), model 5.0, with two targets not met.**

| Item | Target | Result |
|---|---|---|
| 14. Data levels | no false "you don't own it" with a basic import | met, tested |
| 13. Artifact quality | rank correlation 0.7 with simulated gaps | -0.83 on 8 characters |
| 10. AoE ordering | AoE carries above single-target carries | met |
| 10. AoE consistency | agree with the community's multi-target sims | not checkable: 3 overlapping lineups, set up differently |
| 11. Content modes | narrow super-carry account wins Stygian, loses Theater | met, tested |
| 15. Rewriter safety | unchanged DPS when Energy Recharge suffices | no errors, median 0.3%, but 5 of 80 configs off by more than 2% |
| 15. Ordering | stalled < reality < potential | met on all three teams |
| 9. Calculator | within 10% on 90% of 200 swaps | 37%; generated kits do not help (median error 17% against 15%) |

See docs/current-gaps.md for every open problem across the engine.

**Still open, for later phases:**
- **Razor / Kazuha / Bennett / Fischl** is resolved: with Chevreuse credited correctly, the plan takes Razor /
  Fischl / Bennett / Chevreuse.
- **Bennett as a carry.** Bennett deals most of the damage in a few simulated teams (Xianyun plunge, an
  on-field Lunar team), so the engine accepts Bennett-led teams when a roster has nothing better.

