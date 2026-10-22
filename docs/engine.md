# How the engine works

The engine takes data and ideas from gcsim, Prydwen and Keqing Mains, but the final numbers are
its own. Every number it reports names its source, so you can always tell a measurement from an
estimate.

## The four measures

| Measure | Question | Depends on your account? |
|---|---|---|
| Archetype tier | How strong is this archetype at its best, compared with all others? | No |
| Lineup fit | How close are these four to the best lineup for the same carry? | Only on who you own |
| Build progress | How much of these four's fully built strength do you already have? | Yes, investment only |
| Team rating | Tier x fit x build, minus an execution penalty. Compares any two of your teams. | Yes |

## What each source contributes

| Source | What we take | How |
|---|---|---|
| gcsim database (db.kqm.gg) | Simulated damage for about 6,000 teams | `python -m gtc sources` downloads every entry |
| Prydwen | Tiers per role, Stygian Onslaught tiers, execution tags, relative team damage, constellation and weapon values, Energy Recharge targets | Parses the tier list and each character guide |
| Keqing Mains | Archetype formulas, example teams with alternatives, the reasoning behind them, pros and cons | Parses each quickguide |
| Our model | Estimates for lineups nobody measured, investment, build priorities | The knowledge files plus calibration |

Order of preference for any number: a gcsim measurement under comparable assumptions, then
Prydwen's published figure, then our calibrated estimate.

## Gaps in the sources, and how the engine fills them

**1. gcsim mixes incompatible assumptions.** The same Flins team ranges from about 140k DPS at C0 to
1.4M at C6 R5. Comparing raw entries is meaningless.
*Fill:* a simulation is "standard" only if every 5-star is C0 with any 5-star weapon at R1, single
target, accepted by reviewers. That matches Keqing Mains' and Prydwen's own conventions. If a lineup
was only simulated with other gear, it is compared like-for-like with sims using the exact same
carry build.

**2. gcsim does not record who the carry is.** Many "Ayaka" simulations are Skirk teams with Ayaka
as a support.
*Fill:* a simulation counts for a carry only if no other member is a pure carry. Pure carries are
read from our role tags, or from Prydwen's role categories for characters we have not tagged.

**3. Prydwen tiers only compare characters within a role.** Prydwen says so itself: a T1 On-Field
DPS and a T1 Support are not comparable. Its team percentages are also relative to one character's
best team, so they never compare archetypes.
*Fill:* archetype tier comes from absolute simulated damage, normalised so 100 is the average of
the three strongest standard lineups in the database. Prydwen's tier is the fallback, and the
report flags archetypes where the two disagree by 20 points or more.

**4. Every source rates only a handful of lineups.** Prydwen lists two Flins teams. Your exact
lineup is often missing from all three sources.
*Fill:* our slot model estimates every lineup, then is calibrated against every lineup that was
measured. Calibration has three layers: a global curve, a per-archetype baseline, and a per-carry
correction. The report shows the error at each layer, tested leave-one-out, and lists the biggest
remaining misses so the knowledge files can be corrected.

**5. Sources assume fully built characters.** None of them knows that your Aino is 15% built.
*Fill:* build progress, from your real levels, talents, weapons and artifacts, multiplies into
team rating. That is why a measured better lineup can still rank below a more built one today.

**6. Simulations assume perfect execution and ignore survival.** gcsim never takes damage or
misses a rotation.
*Fill:* Prydwen's "expert (-N)" tag reduces team rating by 3% per level, set in scoring.yaml.
Sustain and caveats from Keqing Mains, such as weak Hydro application, show as notes beside the team.

**7. Keqing Mains has no numbers.**
*Fill:* its example teams are matched against your lineups, including listed alternatives, and the
explanation is quoted as evidence. It never changes a score on its own.

## Known gaps not yet filled

- **Single target only.** About 95% of simulations use one target. AoE archetypes are undervalued.
- **One content mode.** Prydwen's Stygian Onslaught tiers are shown but not scored. Imaginarium
  Theater's element limits and Spiral Abyss's two-team constraint deserve their own scoring.
- **Staleness.** Old simulations may predate buffs or new artifact sets. Entries are not yet
  weighted by date.
- **Lineups nobody simulated.** Personal simulations need a community rotation for the exact four
  characters. Other teams get rule checks only.
- **Newer characters.** Ideal teams only include characters tagged in characters.yaml.

## Game-wide knowledge

The engine knows the whole game, not only one account. `python -m gtc sources` downloads guides for all
120 characters, and `python -m gtc derive` turns them and the gcsim database into two generated files:

- **knowledge/generated/auto_roles.yaml** gives role tags for every character. Off-field damage and
  application come from Prydwen's Damage Support entries and "high app" tag. Buffs come from its Support
  entries. Healing, shields and shred come from talent descriptions (Project Amber). Carry roles come
  from the archetypes below. Each tag records why it was given.
- **knowledge/generated/auto_templates.yaml** holds archetypes discovered in the 4,800 standard
  simulations. Each simulation gets a carry: the one member Prydwen rates purely as On-Field DPS, or the
  only one rated DPS at all. Prydwen's "driver" tag (Ayato) marks someone on-field but not carrying.
  The archetype is the carry's own reaction with its main partner element, such as "Vaporize (Pyro
  carry)", "Anemo carry" or "Mono Hydro". A carry's quality comes from their best team against the
  archetype's best. A teammate's quality comes from how teams with them perform for the same carry.

Archetypes that match a hand-written template feed its carry role, so Skirk becomes a Freeze carry without
anyone writing it. The rest become new templates, marked "from gcsim data" in reports.

Hand-written files always win: a role in characters.yaml or a template in templates.yaml is never
overwritten. Damage dealers with no standard simulations yet (new releases) are tagged `carry_unsimulated`
with their Prydwen tier, so the engine knows them but cannot build their teams.

Run `derive` again after `sources` to pick up new characters and simulations.

## The account review

`python -m gtc review` looks at your own teams plus your three strongest other teams and reports
concrete changes, using only what you own. It works like a theorycrafter going through an account:

**Measured with gcsim.** If anyone has submitted your exact lineup to the gcsim database, the engine
takes that community rotation and rewrites every character's level, constellation, talents, weapon,
sets and stats with yours. It then measures one change at a time:

- each of the two priority talents raised by one level and to 9,
- level 90,
- every weapon you own of the right type that no teammate in the same team holds,
- community-standard artifacts, which shows how much a character's artifacts cost the team.

gcsim waits for a Burst instead of skipping it, so a support who cannot afford their Burst stalls the
whole rotation. The engine adds Energy Recharge in 10% steps until the rotation runs, reports the
amount as that character's shortfall, and uses the fixed build as the baseline for everything else.

When a weapon would come from another character, the review checks whether the guides list that
weapon for them. If they do, the swap is marked as a trade-off between teams.

**Checked against the guides.** For every member:

| Check | Source |
|---|---|
| Talent levels against the priority order | Keqing Mains |
| Level | Keqing Mains priority, investment |
| Weapon recommended, and a better owned option nobody in the team uses | Keqing Mains and Prydwen weapon lists |
| Sands, goblet and circlet main stats | Keqing Mains, then Prydwen, then player usage |
| Set bonus against the recommended options | Keqing Mains, then Prydwen, then player usage |
| Energy Recharge against this team's requirement | Prydwen per-team rows, then Keqing Mains tables matched by teammate, element count or constellation |
| Energy Recharge far above the requirement, with rolls wasted | same |
| CRIT Rate to CRIT DMG balance, counting set bonuses such as Blizzard Strayer | Keqing Mains stat guidance |

For the team: duplicate or missing team-buff sets (knowledge/sets.yaml), and owned teammates that
raise lineup fit, with Keqing Mains' reasoning when it ranks them.

**Ranking.** Every finding carries a gain as a share of team damage, whether it was measured or
estimated, and an effort: free (a swap), resin, or farming. The top list keeps one entry per
character and kind of change, measured results first.

**Inventory.** HoYoLAB only shows equipped gear. Import a scanner export with
`python -m gtc inventory path/to/good.json` and spare weapons and artifacts join the swap
suggestions. Later HoYoLAB imports keep the last inventory.

## Measured synergy

The engine knows what each character actually does for each teammate, typed and measured, from gcsim itself.

gcsim's detailed log records every hit with its full damage calculation and every buff and RES shred active
on it, including who provided it and its value. For each hit, the engine recomputes the damage without each
buff using the game formulas, and credits the difference to the provider:

- **Every buff source is read.** That covers buffs on the hit, pre-damage modifiers such as Mona's Omen,
  weapon buffs credited to their holder (Mona's TTDS), and flat damage such as Shenhe's quills.
- **Stat buffs** count only where they apply. Elemental Mastery raises reaction damage and EM-scaling
  hits, never a plain Cryo hit. A Cryo DMG bonus raises Cryo hits. ATK raises ATK-scaling hits. Crit
  buffs use average crit.
- **RES shred** counts on every hit of that element, reactions included.
- **Lunar reaction and base-damage bonuses** appear in the log only as totals. They are split between
  their known sources from knowledge/kits.yaml.
- **Transformative reactions** (Hyperbloom, Bloom, Burgeon, Swirl, Electro-Charged, Overloaded,
  Superconduct, Shatter, Burning) are logged as one flat figure. The reaction bonus is solved from it,
  using the known multiplier and level base. The triggering character's EM buffs come from their most
  recent hit. Teammates' reaction bonuses are credited at their logged values: gcsim records each
  source's value with the hit ("<ability> [React Bonus]"), so Flower of Paradise Lost, Viridescent
  Venerer or Nilou are credited exactly. Only when that record is missing is the bonus split equally.
- **Vaporize and Melt** hits credit EM and reaction bonuses on the amplified hit. **Aggravate and Spread**
  hits credit EM and reaction bonuses on the added damage only.
- **Lunar-Charged reaction hits** are credited to each contributor by their weighted share, using
  their logged EM and bonuses.

`gtc.synergy.build_database()` does this for the median simulation of every distinct standard lineup
(about 3,800, run in parallel, roughly half an hour). The result, data/sources/synergy.json, gives each
member's own damage share and buff share in each lineup, with a breakdown by buff type and by who received it.

- **Enablement.** Reaction damage is credited to whoever triggers it, which undercounts the character whose
  aura made it possible. The engine follows every element application, keeping who supplied each aura's
  durability as it decays and is consumed:
  - a Vaporize or Melt hit credits its amplified part, 1 - 1/multiplier, to the owners of the aura it consumed
  - a transformative reaction (Overloaded, Electro-Charged, Swirl, Bloom...) credits half its damage to the
    owners of the auras involved
  - Hyperbloom and Burgeon credit half to whoever made the Dendro core: half of that to the character whose
    hit caused the Bloom, half to the owners of the Hydro and Dendro auras
  - Aggravate and Spread credit half of the added damage to whoever made the Quicken aura

  Enablement overlaps with the damage it enables, so it is stored apart from buffs. With it, Xingqiu's value
  with Hu Tao is 42% of team damage (23% own, 2% buffs, 18% enablement), level with Furina's 42% and a little
  below Yelan's 48%.
- **Fair shares.** Removing one buff at a time (marginal values) can double-count when buffs multiply. Each
  direct hit is also recomputed with every subset of teammates' buffs removed, and each teammate gets their
  exact Shapley value: their average marginal contribution over all orderings. These shares add up exactly to
  the hit minus the hit without any teammate buff. Explanations use them; swap estimates keep marginal values,
  which predicted swaps better (9.2% median error against 9.8%).

**Uses:**
- **Pair table.** For each carry and teammate: the teammate's average share of team damage alongside
  that carry, with the types of buffs behind it.
- **Swap estimates.** Used when the pair model cannot judge a lineup (a member it has never seen). A lineup
  one or two members away from a simulated lineup of the same carry and archetype is estimated as that lineup's measured fit x (1 - leaving members' shares + newcomers' shares).
  This comes before any model estimate.
  - A newcomer's share is their measured share with this carry in other teams of the same archetype,
    weighted toward teams sharing more teammates and shrunk toward "no change" when it rests on few teams.
  - A newcomer never simulated with the carry in that archetype counts half the leaving share. Such swaps
    lose about 5% at the median in the data, and about 12% when the leaving member was a major contributor.
  - **Reaction engine.** Reaction damage is credited to whoever triggers it, so an applier's share undercounts
    what they enable. If a change cuts the team's application of an element the archetype reacts with, the
    estimate loses that fraction of the team's reaction damage. Swapping Nahida out of a Hyperbloom team
    costs the Dendro she supplied.
  - **Gains need evidence.** A swap can beat the simulated team by at most 10 points, and only when each
    newcomer has five or more simulated teams with that carry there; proportionally less with fewer.

  On 25,800 held-out one-member swaps the predicted team damage has a median error of 9.0%, against 10.8% for
  assuming the swap changes nothing.
- **Winner's-curse discount.** When teams are chosen, an estimated fit counts 5 points lower than a measured
  one, its typical error. A model estimate with no simulated lineup of the carry within two members counts
  15 points lower. Without it, the plan search systematically picks whichever estimate happens to be
  too high.
- **Teammate ratings for discovered archetypes** come from measured shares instead of team totals.
- **The review shows "What each teammate brings"** for every team.

## The pair model

`gtc/pairmodel.py` fits one model over all 3,760 standard lineups:

```
log(team DPS) = archetype effect + character effects + lead effect + pair effects
```

It uses ridge regression, so pairs seen in few lineups are shrunk toward zero. A pair effect is how much better
two characters do together than their separate effects predict. It needs no carry label: the Hyperbloom core
pairs (Nahida and Kuki +7%, Kuki and Xingqiu +9%), Burgeon (Nahida and Thoma +10%) and Ayaka with Shenhe
(+13%) all come out positive. A character's lead effect is added only when the team is built around them, so a
carry's strength is not credited when they sit in a support slot. Results go to data/sources/pair_effects.json
with standard errors.

**Accuracy, held out:**

| Case | Median error |
|---|---|
| All lineups, 5-fold cross-validation | 6.5% |
| One member from a simulated lineup, same 29,400 swaps as below | 6.2% |
| Two or more members from any simulated lineup | 11.0% |

On the same one-member swaps, the swap estimate below has 9.2% and "nothing changes" has 10.8%. The pair model
is better in every archetype checked, so it is the engine's first estimate for an unsimulated lineup. Its
discount when ranking is 5 points one member from a simulated lineup and 10 points further away. Taser
(Fischl with Beidou) does not come out as a significant pair.

`gtc.synergy.validate_swaps()` checks the swap estimate hold-out style. It predicts each simulated lineup
from a simulated neighbor without using that lineup's own data.

## Team validity and structure

Each simulated lineup also records what every member did: damage share, field time, element applications on
and off field per 10 seconds, reactions triggered and healing. From that:

- **Structure.** Each lineup is classified by where its damage comes from: hypercarry (one member deals at
  least 55%), dual carry (a second member deals at least 25%), reaction core (reactions deal at least half),
  driver (the on-field character deals under 25%), or distributed. The team's lead is its measured damage
  owner, not a guess from role tags. An unsimulated lineup is predicted from the simulated lineups most like
  it: each weighs 100 times more per shared teammate. Held out, this names the top damage dealer correctly
  86% of the time with a per-member share error of about 5 points. The category itself agrees 75% of the
  time, because its thresholds sit inside simulation noise.
- **Capability profiles** (data/sources/capabilities.json) average each character's behaviour over every
  lineup they appear in.
- **Validity rules** (knowledge/generated/validity.yaml), learned from each archetype's own simulated teams
  and checked before any scoring:
  - minimum application of each element the archetype reacts with
  - elements that never appear in its teams
  - the most on-field characters its teams have
  - per carry within the archetype, teammate elements they never have
  - per carry overall, teammate elements present in at least 95% of their teams (Skirk always has Cryo and
    Hydro teammates)
  - the team's damage must come from someone who can hold the archetype's carry slot (Kazuha / Raiden /
    Shenhe / Citlali is Raiden's damage, so it is not an Anemo carry team)

  A simulated lineup counts as one of an archetype's own teams when the archetype's slots can be filled with
  it and its measured damage owner can hold the carry slot. Recall, the share of its own teams an archetype
  still accepts, is printed by `python -m gtc derive`. 25 of 35 archetypes keep at least 98%, and all keep
  at least 90%. The misses are mostly lineups the slot matcher places in archetypes they do not play.
- **Teammates judged against the carry.** Generated archetypes rate a support by how the whole family's
  teams do with them, which says nothing about one carry. In them a teammate's quality is also capped by
  their measured share alongside this carry: quality 2 if never simulated with them, at most 4 from a single
  team. Healers and shields keep their rating. This stopped Raiden and Sara rating 5/5 next to Noelle.
- **Own teams.** An archetype's own simulated teams are the lineups it was discovered from (derive assigns
  each lineup one family by its measured carry), so Mono Pyro learns that Hydro never appears in it.
- **Medians.** A lineup's value is the median of its simulations, not the best submission, which is biased
  upward for popular lineups. Generated archetypes are rated only from the lineups they were discovered from.

## Uncertainty and evidence tiers

Every team value is an estimate with one standard deviation and an evidence tier (`gtc/estimate.py`). Each
tier's sd is measured on held-out cases by `python -m gtc derive`, never chosen by hand: the 68th percentile
of absolute errors on half the cases, with coverage checked on the other half.

| Tier | Evidence | Measured sd | Within 1 sd | Within 2 sd |
|---|---|---|---|---|
| A | Your own gcsim run (iteration noise only, not rotation differences) | about 0.2% | | |
| B | Community simulations of this lineup: one submission | 9.8% | 73% | 93% |
| B | Median of n submissions | 9.8% x 1.25 / sqrt(n) | | |
| C | Pair model one member from a simulated lineup | 9.9% | 69% | 93% |
| C | Prydwen team rating | 4.7 fit points | 70% | 80% |
| D | Pair model further away | 13.8% | 63% | 95% |
| D | One-member swap estimate | 14.4% | 68% | 91% |
| E | Role rules, calibrated: next to a simulated lineup / without one | about 13 / 16 fit points | | |
| F | No data: shown as "cannot evaluate" | | | |

The first draft of the plan put swap estimates (C) above the pair model (D). Measured, the pair model next to a
simulated lineup is the more accurate, so the tiers follow the measurements.

- **A team's potential** is archetype tier x lineup fit. Their relative errors add in quadrature and the team
  takes the weaker tier. When both come from community medians, the shared best lineup cancels and only this
  lineup's own noise remains.
- **Ranking** uses expected potential minus 0.674 sd, an estimate's median miss. This replaced the fixed
  discounts: thin evidence has to clear a higher bar, in proportion to how thin it is.
- **Pull values** show the expected gain, its sd and the weakest tier among the teams that change. Teams in
  both plans cancel. Confidence is the probability the gain is above zero.
- **Comparisons** say "likely better" only when the probability is at least 80%; otherwise "roughly
  equivalent".
- **Personal gains** in the review show their tier A sd from gcsim's iteration statistics.

## The data audit

`python -m gtc audit` checks every character in the game: game data, roles, simulations, whether they own the
damage in any simulated lineup, their Prydwen rating, capability profile and pair-model coverage, and whether
they appear in and lead any valid team. A character in no valid team is traced to the reason, down to the
validity rule's own message. Findings are split into unexplained contradictions, which should be zero, and
explained gaps:

- characters with no simulations, judged from role rules (tier E)
- new characters with no simulations and no kit numbers, which cannot be evaluated (tier F)
- on-field drivers such as Mizuki and Ifa, rated DPS by Prydwen for their field time while others own the damage

**Hand-written kits.** A character without simulations can be placed in teams through
knowledge/kits_custom/: `expected_archetypes` maps an archetype to carry or support with a quality, and
`capabilities` gives their application rates and field time for the validity rules. Their teams are tier E
until simulations exist. The template is knowledge/kits_custom/_TEMPLATE.yaml.

**What the audit found.** gcsim names buffs with short character aliases such as "chev", "xq", "esco", "kaz"
and "zl". 38 of them were not recognised, so those buffs were credited to the character attacking. Chevreuse's
Overloaded RES shred is the clearest case: she measured 6% of her team's damage, and 48% after the fix (RES
shred 20%, Pyro and Electro DMG bonus 21%, ATK 7.5%). Her Overloaded teams moved up accordingly.
Cyno's old "cannot evaluate" problem no longer occurs: he leads valid teams in four archetypes.

## Model versioning and the benchmark

**One parameter file.** Every tunable value lives in knowledge/model.yaml with a `model_version`: plan
weights, the sidegrade factor, the carry bar, the ranking risk, validity percentiles, synergy shrinkage,
pair-model penalties and the review's rough estimates. Each says where it came from: measured,
cross-validated, tuned or a judgment. Game facts such as reaction multipliers stay in code on an explicit
allowlist. Every report states the model version and a fingerprint of model.yaml and scoring.yaml.

**Guards** (tests/test_model.py):
- A scan of the scoring modules fails on any module-level numeric constant that is neither read from
  model.yaml nor on the game-fact allowlist. Numbers inside function bodies are not scanned.
- Every value in model.yaml must be read by its module.
- If model.yaml or scoring.yaml changes, the test fails until the version is bumped and
  `python -m gtc benchmark --record` is run for it.

**The benchmark** (knowledge/benchmark.yaml) holds 46 cases: an account, a question and the answer an expert
would give. The kinds are a carry's best team, teams that must not form, the account plan, the top pull, a
pull's kind, a lineup comparison and a carry gap. Pull cases use the reports' decision rule: an acceptable
answer within noise of the engine's top pick (under 80% that the top is better) counts. Each case names its
source: the user's own corrections, or Claude's reading of community consensus, which should be reviewed.

**Tuning** (`python -m gtc benchmark --tune`) runs every combination of a small grid of parameters over all
cases, then scores each case with the combination that does best on the other cases (leave-one-out), and
reports which cases react to the tuned values at all. Results are recorded per version in
knowledge/benchmark_results.yaml.

## Breadth: artifacts, AoE, content modes, Energy Recharge, kits

**Artifact quality** (gtc/artifacts.py). Each substat counts as its value over one average roll, weighted by
its tier in the character's Keqing Mains substat priority. Energy Recharge counts only up to the lowest
requirement Keqing Mains lists. Quality is useful rolls over a benchmark of 30 for five pieces. The investment
score's artifact part is 40% pieces and levels and 60% roll quality. On the eight characters with personal
simulations, useful rolls and the simulated artifact gap have a rank correlation of -0.83.

**Team power by dimension.** Every assessment carries single target (the potential estimate), AoE and
sustain. `python -m gtc aoe` runs the strongest lineups of each archetype, 159 in all, against one target and
against three grouped targets. A lineup's AoE ratio is three-target damage over single-target damage, with
ratios for 85 characters. AoE power is single-target power times the team's ratio over the median ratio.
Unsimulated lineups use their members' ratios, weighted by damage share. Known AoE carries (Xiangling 3.5,
Nahida 3.4, Raiden 3.4) rank above single-target carries (Eula 2.2, Ayaka 2.7). Sustain is the best healer
or shield quality on the team.

**Content modes** (gtc/profiles.py). The same teams, reweighted:

| Mode | Teams | Weighting |
|---|---|---|
| Spiral Abyss | 2 | half single target, half AoE |
| Stygian Onslaught | 1 | single target |
| General | 4 | the plan weights, single target 0.6 and AoE 0.4 |
| Imaginarium Theater | up to 6 | disjoint competent teams, scaled by element coverage |

The account report has a section per mode. A one-super-carry account beats a broad 4-star account in
Stygian (55 to 47) and loses in Theater (43 to 72).

**Energy Recharge, as built.** Personal simulations still top up Energy Recharge so that no Burst stalls the
rotation (the potential). The reality run uses your builds without the top-up, on a rotation rewritten so
that a Burst not ready within 5 seconds is skipped (gtc.sim.guard_bursts). The review reports the damage lost
and the Bursts skipped, for example "Mona skips 2 of 5 Bursts". On 80 community configs with enough Energy
Recharge, the rewrite causes no gcsim errors and a median change of 0.3%. Five configs still change by more
than 2%, the worst by 10%. On your three teams, reality sits between the stalled run and the potential, as it
should. Weapons use their real level cap when the snapshot knows their ascension.

**Data level.** Snapshots are "full" with a scanner export and "basic" from HoYoLAB alone. With a basic import
no report claims a spare weapon is missing.

**Generated kits** (`python -m gtc kits`, gtc/kitgen.py). Every simulated character's buffs to teammates and
RES shred are read from one representative gcsim log: the stat, its median value, and its uptime over the
receivers' damage. 108 characters are written to knowledge/generated/kits_auto.yaml. Hand-written kits
override them. The calculator does not get better with them; see the gaps report.

## The account plan and character value

`python -m gtc account` answers three questions with one consistent model.

**Best teams you own.** "Available" means owned. Teams are judged at full build (potential = archetype
tier x lineup fit); today's rating and build progress are shown beside it as the cost of getting there.
The plan is the four teams sharing no characters that maximise a weighted sum: the two strongest count
fully (Spiral Abyss halves), the third half, the fourth a quarter. The search is exact.

**One scale for measured and estimated lineups.** An unsimulated lineup is estimated from simulated
lineups of the same carry: their measured fit, scaled on that archetype's own calibrated curve. Closest
lineups first, and the lowest estimate wins, so an untested lineup never outranks a tested one through
the model's optimism. Archetypes also respect their element pattern when teams are formed: an
Electro-Charged team must contain Hydro, a Freeze team cannot contain Pyro.

**Main damage dealers.** A carry counts as real when Prydwen's best rating for them is On-Field DPS and
their best team reaches potential 45. Fewer than two is reported as a carry gap. Separately, the report
ranks unowned carries by the team they would lead with the characters you already own.

**What a new character would change.** Each unowned character joins the account fully built at C0 and
the plan is recomputed. The gain is the change in the plan, and the explanation says why:

| Kind | Meaning |
|---|---|
| fills a gap | Replaces a weak member of a team you play, raising it 15% or more, or completes a team for a carry you own |
| upgrade | Improves a team you play by less than that |
| new archetype | Leads a team that was not in your plan |
| sidegrade | A carry of an element your top two teams already carry. Counted at 60%, with the teammates both carries want |

The report also checks whether you own a weapon the guides recommend for them, quotes Prydwen partner
tags that link them to your characters, and lists characters it cannot evaluate (no simulations and no
kit numbers) instead of skipping them silently. Best carry and best support are listed separately so
neither crowds out the other.

**Upgrade priorities** come from an account review of exactly those four teams in exclusive mode: no
suggestion moves a character between planned teams, and weapon donors outside the plan are free.

**Scenarios.** tests/test_scenarios.py encodes theorycrafter judgments the engine must reproduce: C6
Aino over Xingqiu with Flins, Kazuha over Sucrose with Ayaka, Columbina filling a Barbara-only Hydro
gap, Mavuika as a sidegrade for an Arlecchino account, and a supports-only account needing a carry that
uses its supports.

## The theorycraft calculator

`python -m gtc theory` answers "would this character be better in this slot, and why" from game math,
the way a theorycrafter does a calc.

**Formulas.** gtc/tc/formulas.py holds the damage formulas copied from gcsim's source: direct hits
(motion value, scaling stat, DMG%, DEF, RES, crit), Lunar-Charged reactions and direct Lunar damage
(3x multiplier, 6 EM / (2000 + EM), separate base-damage and reaction bonuses, no DEF, can crit,
60/30/5/5 contributor weights), transformative and amplifying reactions, and the level table.

**Kits as numbers.** knowledge/kits.yaml describes what each character gives the team: stat buffs,
reaction bonuses, base-damage bonuses, RES shred, extra hits, with targets (party, active, self, others),
uptime, and conditions (Ascendant Gleam, Hexerei, constellation, set holder). Values can depend on the
caster's stats, like "6% of Ineffa's ATK as EM". Numbers come from gcsim's character code. Artifact
sets with team effects live under `_sets`.

**How a swap is judged.**

1. A gcsim run gives the team's damage per ability and each character's stats.
2. Every buff and shred is resolved for the old team and for the new team.
3. Each damage source is scaled by the ratio of its multiplier in the new team to the old one.
4. The leaving member's own damage goes. The newcomer's comes from a gcsim team with the same carry
   (builds of shared characters copied from the base team), or from the hits in their kit.
5. Team checks: Ascendant Gleam gained or lost, a Lunar enabler, Hydro and Electro application.

**Accuracy.** `python -m gtc.tc.validate` predicts five real swaps and compares them with full gcsim
runs using identical builds. All land within 7%, most within 3%.

**New characters.** Copy knowledge/kits_custom/_TEMPLATE.yaml, fill in the kit numbers from the
official announcement, then:

```
python -m gtc theory --team "Flins,Ineffa,Columbina,Sucrose" --replace Ineffa --with Nova
python -m gtc theory --team "Flins,Ineffa,Columbina,Sucrose" --replace Ineffa --rank
```

**Limits.** No rotation or energy changes, and buff uptimes are fixed estimates. Characters without
kit numbers count as giving no buffs, so the review only uses the calculator for teams whose every
member has kit numbers (currently the Lunar ecosystem, Furina and Xilonen). Extending coverage means
adding characters to kits.yaml.

## Speed

Reports run in seconds: about 6 for teams, 9 for the review and 65 for the account plan. Two things make that possible:

- **Indexes.** Simulations are indexed by member, and lookups for an archetype and carry are cached.
  Scanning all simulations for every lookup used to dominate the run time.
- **Validity cache.** Each lineup's validity is checked once per archetype, and neighbour predictions use
  precomputed sums over teammate subsets instead of scanning lineups.
- **Branch and bound in team enumeration.** When only the top N lineups are needed, a partial lineup is
  abandoned as soon as its best possible completion cannot reach the current Nth best. The result is
  identical to scoring every lineup, which a test checks against full enumeration.

## Refreshing data

```
python -m gtc gamedata   # character and weapon lists from Project Amber
python -m gtc sources    # gcsim, Prydwen, Keqing Mains for every character, cached for a week
python -m gtc derive     # role tags and archetypes for the whole game, from the sources
python -m gtc import     # your roster
python -m gtc inventory FILE  # optional: spare weapons and artifacts from a scanner
python -m gtc teams      # the team report
python -m gtc review     # the account review
```

gcsim itself is downloaded once into data/tools/ (version pinned in gtc/sim.py). Simulation results
are cached in data/sims/, so a second review of the same builds is instant.

Downloaded source data lives in data/sources/, which git ignores. It is third-party content for
personal use and should not be redistributed.
