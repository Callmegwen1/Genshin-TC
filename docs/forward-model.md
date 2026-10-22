# Forward model (FM-0 to FM-10)

**Goal:** structured kits → plausible rotation → resolve buffs, conditions and reactions → per-event damage → team
DPS, from first principles.

- **Community gcsim** becomes validation, calibration and rotation-reference data. It no longer defines power.
- **Status:** experimental. Not wired into production power, the planner or pull ranking (`legacy_power` is
  unchanged).
- **Rule:** **forward model is numeric power; TeamMechanics is logical compatibility.**

## FM-0 audit: what existed and is reused

| Need | Existing component | Used as |
|---|---|---|
| Damage formulas: DEF, RES, crit average, EM curves, transformative, Lunar | `gtc/tc/formulas.py` | Reused as is |
| Reaction table (classes, coefficients, auras) | `gtc/reactions.py` | Reused |
| Talent multipliers, scaling tables, energy cost, durations, cooldowns | Amber cache (`kitcompile.amber`) | New reader: `forward/data.py` `table()` / `value()` |
| Base stats by level, ascension stat | Amber `upgrade` + curve endpoints (newly fetched, cached) | `forward/data.py` |
| Weapon base ATK and substat | Amber weapon endpoints (new, cached) | `forward/data.py` |
| Structured effects, conditions, provenance | Schema-3 kits (`gtc/kits.py`), TeamMechanics condition evaluator | Effect definitions; condition states |
| Moonsign Ascendant Gleam rule table | `knowledge/kits.yaml` `_rules` | Universal effect |
| Rotation scripts | Community gcsim configs (`gtc/sim.py` `find_config` / `render`) | Rotation source A |
| Running gcsim | `gtc/sim.py` `run`, `gtc/synergy.py` `run_sample` (local gcsim v2.48.8) | Traces and validation |
| Per-hit logs | gcsim `-sample` (`calc`, `damage`, `action`, `energy` events) | Rotation, hit list, energy; per-hit validation |
| Account stats | Snapshot weapons and artifacts (`gtc/snapshot.py`), GOOD keys (`gtc/stats.py`) | CURRENT_ACCOUNT build |
| Buff attribution | `gtc/synergy.py` Attributor | Not reused (the forward model attributes by removal) |
| Ratio calculator (`gtc/tc/engine.py`) | Swap ratios on a gcsim profile | Kept; superseded for forward power |

**Not available before, now added:**
- hit counts and timing per rotation (from traces);
- an energy model;
- field-time windows;
- timeline buff resolution;
- a party-HP model (Fanfare, Salon);
- Moonsign and Hexerei factions;
- elemental resonance.

## Modules (`gtc/forward/`)

| Module | Role |
|---|---|
| `data.py` | Amber numbers: `character_stats`, `weapon_stats`, `table`, `value`, `talent_kind` |
| `build.py` | META_STANDARD (house), CURRENT_ACCOUNT, ACCOUNT_CEILING; `house_builds` (ER to requirement) |
| `trace.py` | Rotation source A: community script run with house builds, read as actions, hits, energy and field segments |
| `effects.py` | Timeline effects, condition states (met / partial / unmet / unknown), factions, resonance, party HP and Fanfare |
| `energy.py` | Required ER per character; sustainable / marginal / unsustainable / unknown |
| `rotation.py` | Field-time profiles and window fit |
| `model.py` | Per-event expected damage; `ForwardTeamEvaluation`; contributions by removal |
| `validate.py` | Calibration vs locked sets: forward vs gcsim (same rotation, mean) vs community vs legacy |

`knowledge/forward/annotations.yaml` holds the triggers, durations, table-sourced amounts, quotas and
snapshotting the kits do not state as numbers.

## What the trace supplies and what the model computes

**From the trace (rotation source A, a community script run with house builds):**
- who acts when;
- each hit's ability, timing, element, damage type and talent multiplier;
- which hits reacted (aura outcome);
- particles.

**Computed by the forward model:**
- every stat;
- every buff and debuff: trigger, landing time, duration, quota, target, element and type filters, statuses
  persisting after a swap, snapshotting;
- condition states;
- flat additive damage;
- DEF, RES and crit;
- amplifier and catalyze math;
- transformative and Lunar reaction damage (per-contributor states);
- Furina's Fanfare and Salon scaling from party HP;
- energy feasibility;
- field windows.

## Theorycrafting without the team's simulations (rotation steps 1 and 2)

**`library.py`: per-character action libraries, measured as character facts from house-build traces of OTHER teams.**
- Role-aware: a carry is measured from teams where they carry.
- Never from the evaluated lineup.
- Each action records cast duration, hits (offset, multiplier, element, type), Swirl templates, particles, the usual
  follow-up (Kazuha's plunge) and which of Skill or Burst comes first.
- Normal Attacks are keyed by chain position.
- Each character's top three on-field strings are kept.
- Multipliers are checked against Amber: Mona's Skill and Shenhe's hold Skill read one talent level higher in gcsim.

**`generator.py`: the rotation generator.**
- Template: supports set up, then a carry window (the carry's buff openers such as Ayaka's dash, Skill and Burst in
  both orders, and filler strings with Skill recasts), then an optional support refresh (none, mid-window, or right
  after the carry's Burst).
- Supports go in every order; no ordering rule is imposed, and the forward model scores every candidate.
- Scheduling uses ample energy. The build is then required to meet each member's ER requirement + 10% (as for traced
  rotations), and a requirement above 2.6 ER makes the generator reschedule with late or skipped Bursts.
- Swirl and Anemo absorption use a stopgap aura rule (Cryo + Hydro means Frozen, which swirls as Cryo).

**`blind.py`:** `theorycraft(lineup)` returns the engine's answer; `reveal(lineup)` returns the reference afterwards.

**Blind results** (vs gcsim mean on the community rotation, house builds; data/validation/blind_batch.json):

| Team | Blind vs gcsim | Note |
|---|---|---|
| Ayaka / Shenhe / Kazuha / Mona | +1.4% | Development case |
| Ayaka / Shenhe / Kazuha / Furina | −6.2% | |
| Ayaka / Shenhe / Escoffier / Furina | +7.1% | |
| Razor / Fischl / Bennett / Chevreuse | −6.3% | Partly cancelling errors: unresolved Hexerei buffs |
| Neuvillette / Furina / Kazuha / Baizhu | −20% | Neuvillette's passives unresolved |
| Flins / Aino / Ineffa / Sucrose | −63% | Lunar-Charged reactions are not generated yet (reaction model, step 4) |

**No-reference teams:** Ayaka / Shenhe / Escoffier / Mona projects 32,098; with Chiori instead, 22,955.

## Reaction model (rotation step 4)

**What it is (`gtc/forward/reactions.py`):** an explicit gauge-theory aura simulation over a rotation's hits.
- Each hit carries the units it applied. The libraries keep each kit's ICD and gauge, measured from gcsim's
  application events, so a hit inside its ICD neither applies nor reacts.
- **Modelled:**
  - Melt and Vaporize, with direction (×2 / ×1.5) and gauge consumption;
  - Freeze, and Shatter from blunt hits;
  - Swirl of every swirlable aura present, with Frozen swirling as Cryo;
  - Crystallize, Overloaded and Superconduct;
  - Electro-Charged, or Lunar-Charged in teams with the conversion, ticking every 2.2 s.
- **Not modelled yet:** Bloom and cores, Quicken, Burning, reaction ICDs, multiple targets.
- **Wiring:** generated rotations now decide all their reactions with it. The Swirl stopgap is gone.

**Checked against gcsim on traced hits** (our counts vs gcsim's):

| Team | Reaction | Ours | gcsim |
|---|---|---|---|
| Hu Tao | Vaporize | 51 | 51 |
| Razor | Overloaded | 14 | 14 |
| Flins | Lunar-Charged ticks | 48 | 49 |
| Flins | Swirls | 31 | 41 |
| Raiden National | Vaporize | 60 | 70 |
| Raiden National | Overloaded | 30 | 54 |

**Blind (no access to the team's simulations), vs gcsim mean:**

| Team | Error |
|---|---|
| Ayaka / Mona | +8.0% |
| Ayaka / Furina | +8.9% |
| Ayaka / Escoffier / Furina | +7.1% |
| Raiden National | +5.2% |
| Razor Hexerei | +6.6% |
| Neuvillette | −13.5% |
| Flins | −32% |
| Hu Tao | −41% |

**Known gaps:** Shatter is over-produced in Freeze teams; Lunar damage per tick and Swirls are low in the Flins team;
Hu Tao's and Neuvillette's kits are unresolved (text-only amounts).

## Dual-carry plans (rotation step 5)

**What the generator now considers:**
- **Single-carry plans for every on-field damage dealer:** the others support, casting and leaving.
- **Dual plans:** two carries each get their kit's window in turn (Raiden's Musou Isshin 7 s, Razor's Burst 15 s).
- **On-field Burst states end when the character leaves:** Raiden's and Razor's Burst hits are clipped while they are
  off field.
- **No pairing rule:** the forward model scores every plan.

**Raiden / Razor / Bennett / Xingqiu** (no community simulation exists), best plan per carry choice:

| Plan | DPS | 4 cycles take |
|---|---|---|
| Raiden carries | 17,907 | 84 s |
| Razor carries | 16,054 | 81 s |
| Dual, Razor first | 12,618 | 122 s |
| Dual, Raiden first | 11,663 | 139 s |

- **Why the dual plans lose:** giving both their windows stretches each cycle from about 20 s to 30–35 s, past the
  supports' buffs.
- **Context:** the same engine puts Raiden National at 24,753 (+4.3% vs gcsim).

## Prerelease-style theorycrafting (rotation step 6): Lohen

**Character choice:**
- Mitya could not be used: Amber has no entry and Prydwen lists only his name and element. No stats, talents,
  multipliers, passives or energy data exist locally.
- Lohen (Cryo, 5★, polearm) has 0 community simulations and a complete Amber kit.

**How he is built (`knowledge/forward/prerelease/Lohen.yaml`, no gcsim input):**
- Every fact is tagged known / assumed / unknown.
- Multipliers are references to Amber table labels.
- Engine support for any hand-written kit: character states (Masterstroke 13 s, +1.65 s on Burst), state-specific
  attack variants, limited-use specials (Etched ×3 per Masterstroke), timed talent-level bonuses (High Spirits +1
  Skill level for 9 s), and standard ICD (gauge on the 1st of every 3 hits or after 2.5 s).

**Team generation (`gtc/forward/teamgen.py`):**
- Needs are read from the kit: Cryo buffs and shred; a teammate who triggers Cryo reactions (his A4); a Hexerei
  partner; sustain.
- Owned characters are scored on those needs, and a shortlist keeps every top supplier.
- TeamMechanics removes harm, then the rotation generator and forward model rank the shortlist.

**Results** (house builds, generated rotations; data/validation/lohen_prerelease.json): best Lohen / Fischl /
Ineffa / Shenhe, 22,892 DPS.

**Sensitivity:**

| Assumption | Effect |
|---|---|
| Masterstroke attacks Physical instead of Cryo | −15.6% |
| One Etched per Masterstroke instead of three | −1.3% |
| Will to Win (unknown cap) at 50–100 points | +2% to +8% |

**Known gap:** reaction ICD is not modelled, so Superconduct volume in Electro teams (17% of the top team's damage)
is likely overstated.

## Phases A–F: kit language, reactions, action libraries, rotation brain v2, blind benchmark

**A. Mechanical language** (`gtc/forward/engine.py`, `KitMixin`). A kit file declares:
- `resources` with caps;
- `states`, which can be concurrent, can `ends_on_swap`, and can be extended;
- `rules`: on an action, hit or reaction by self, the active character or party members; on a swap; or when a threshold is crossed;
- `ops`: gain, consume, enter, exit, extend, energy, copy, distinct;
- `summons` with ticks, and `procs` with ICD, `hits_cycle` and `scale_trigger`;
- per-state action variants (`burst@symphony`), each with its own `cd` and `energy_cost`;
- `requires_state` and `requires_resource`.

Unknown amounts propagate as `None` and earn no credit. Effects take dynamic conditions (`state_active`, `resource_at_least`), resource-scaled amounts, and triggers at reactions (`reaction:overload`). Nothing in the engine names a character.

**B. Reactions** (`gtc/forward/reactions.py`):
- an aura-gauge simulation over the generated hits: application per ICD group, aura decay, trigger ownership;
- reaction-damage ICD: 2 per 0.5 s per kind;
- Freeze/Shatter, Superconduct, Swirl, EC or Lunar-Charged ticks, Melt/Vaporize, Quicken/Aggravate/Spread, Bloom cores (at most 5, 6 s life), Hyperbloom and Burgeon;
- `summary()`: triggers, rate, owners, aura sources, aura uptime and suppressions;
- `plausibility()`: flags any rate above the community 99th percentile.

**C. Libraries.** `knowledge/forward/actions/<Name>.yaml` holds a frozen kit file for each reference character:
- kit structure (timing, hits, element, ICD, particles) is measured from gcsim on other teams, never the reference team;
- multipliers come from Amber tables;
- a hand-written `causal:` block carries states, resources, rules, summons and procs, with KNOWN/ASSUMED/UNKNOWN facts.

**D. Rotation brain v2** (`gtc/forward/deps.py`):
- an action graph: hard edges put resource builders before the consumer, soft edges put aura appliers before swirl buffers;
- orderings that break a hard edge are pruned;
- each rotation is scored by DPS and reported with its realisation metrics: buff coverage of the carry's damage, field share, state realisation, idle time and energy status;
- rotations that cannot be sustained are deprioritised.

**E. Blind benchmark** (`gtc/forward/benchmark.py`): the engine generates the rotation from kit files alone; the gcsim reference is loaded only afterwards. Results go to `data/validation/forward_benchmark.json`.
- BLIND (the brain) and REPLAY (the calculator on the community rotation) are reported separately.
- Errors tracked: DPS, ranking, cycle length, damage shares, reaction rates, ER and buff coverage.

**F. Reference set** (`gtc/forward/reference.py`): 12 teams covering Freeze, Melt, Vaporize/stance, National, Overloaded/Hexerei, Aggravate/Spread, Hyperbloom, hypercarry/stacks/HP, dual window and Lunar/Moonsign. Generic fixes were made after viewing this set, so it is now a development set, not a held-out one.

Known gaps:
- Flins's energy refund for Thunderous Symphony is not in the kit data, so the Symphony loop is never funded (Lunar −20%).
- The Hyperbloom and dual-window teams pick the wrong driver or field split.
- Aggravate and Spread have no community envelope.

## Phases G–O: realistic builds, gear effects, pipeline, team needs, swaps, uncertainty, validation, shadow, gates

**G. Realistic standard builds** (`gtc/forward/standard.py`). META_STANDARD gives every character the same reasonable investment, not the same stats:
- **Fixed:** level 90, C0, talents 9/9/9.
- **Weapon:** an accessible weapon at a stated refinement (craftable or event R5, gacha 4-stars R3, battle pass R1).
- **Artifacts:** a 4-piece set or a 2+2, three main stats, and a KQM-style substat budget: 20 fixed rolls plus 20 distributable. Each substat holds at most 10 rolls, minus 2 per main-stat piece of the same stat, and CRIT Rate is capped at 100%.
- **Optimiser:** coordinate descent maximises team DPS on the generated rotation. Every scaling stat in the kit is an option.
- **ER is paid from the substat budget**, against a target that is exact for the schedule rather than an average: each member's energy is replayed with the cap at Burst cost, every scheduled Burst must find it full, and bisection finds the lowest ER (×1.05).
- **Favonius:** procs only for wearers, at the R1 cadence, with the particle count scaled by refinement chance. Targets are recomputed for every candidate, because who wears Favonius changes the whole party's particles.
- **ER is a choice made on value:** an ER raise that keeps a Burst on schedule is kept only if team DPS rises, and each member's ER is also tried relaxed.
- **Reveal:** the community rotation gets the same policy, optimised from scratch on its own trace (independent of the blind builds). ER is raised for members whose Bursts slip until the script keeps its shape; a reference that cannot is flagged.
- **The old neutral profile** (`build.meta_standard`) is kept as the calculator baseline.

**H. Gear effects** (`gtc/forward/gear.py`, `knowledge/forward/gear.yaml`). Weapons and sets use the same effect language as passives: static stats, triggered buffs (Skill, Burst, own hits by type, own or party reactions, swirl, swap in/out, periodic), stacks (shared or independent, with ICD), stack levels from several sources, threshold bonuses, stat-scaled amounts, party and enemy targets, and RES shred.
- A sentence-level compiler reads the Amber text.
- Conditions it can resolve are kept: enemy aura (per hit, from the aura simulation), on/off field, weapon type, distinct elements, Moonsign count.
- Anything else (HP thresholds, shields, defeats, chance, unresolved condition words) becomes UNKNOWN: no credit, listed.
- A curated file holds party-, resource- and stack-dependent items; tests check its numbers against the Amber text.
- Unconditional self stats fold into the build, so caster-scaled buffs see them. Identical party effects from two wearers do not stack.
- Buffs on buffs are chained one level (a caster's buffed stat when the effect starts).

**I. Pipeline** (`gtc/forward/pipeline.py`):
- needs → candidate teams → generated rotations → realistic builds → uncertainty → swaps, with no community simulation of the character;
- results go to `data/forward/pipeline/<name>.json` with a fingerprint of every input (kit file, annotations, Amber tables, structured kit);
- `refresh()` reruns only what changed;
- kit files carry `status` (release_status, kit_version) and fact confidence.

**J. Team needs** (`gtc/forward/teamgen.py`):
- **Requires:** reactions, factions, battery (the kit's energy dependency), sustain.
- **Benefits:** kit buffs plus the best party-reaching 4-piece set a teammate could wear.
- **Avoids:** aura interference and wasted buffs as soft flags; field-time and party restrictions as removals.
- Per-need leaders are guaranteed shortlist places. The pair model only breaks ties.

**K. Swaps** (`gtc/forward/swap.py`): both teams are theorycrafted fresh. The delta is split into:
- personal damage lost and gained;
- each effect's contribution lost and gained;
- reaction damage by kind;
- the carry's own change;
- aura uptime and Furina's average Fanfare;
- rotation length, field share and energy;
- an "other" residual.

**L. Uncertainty** (`gtc/forward/uncertainty.py`): sources combined in quadrature, with a High/Medium/Low label and the top drivers. Nothing in it uses distance to gcsim.
- unknown kit mechanics, including the kit file's unknown facts;
- unknown gear;
- per-hit unknowns;
- assumed facts, weighted by damage share;
- provisional data;
- reaction approximation by family;
- uncovered damage;
- rotation quality.

**M. Simulation quality** (`gtc/forward/simquality.py`): each community entry records submitters, comparable build (C0), modernity, validity and duration. Each reveal records whether the rotation kept its shape and whether it was written for constellations it is not run at. The benchmark summary reports both all references and the shape-kept subset.

**N. Shadow mode** (`gtc/forward/shadow.py`): legacy and forward power on the account's production teams and the focus lineups go to `data/validation/shadow_log.json` (no UID). The UI still shows legacy only.

**O. Gates** (`gtc/forward/gates.py`): nine guideline gates go to `data/validation/acceptance_gates.json`. Integration (P–R) waits until all pass.

**Brain fixes made along the way** (generic):
- carry windows no longer overrun their cycle mid filler string;
- the cycle length is searched (Burst cooldowns, support Skill cooldowns, carry state plus setup);
- a "skill_only" plan lets a carry skip a low-value Burst;
- state variants keep independent cooldowns.

**Reference fixes:** amplified hits are compared with gcsim's amplified expected damage (`avg_crit_dmg_react`). This had understated every Melt and Vaporize reference.

CLI: `python -m gtc forward benchmark|pipeline|refresh|swap|shadow|gates [--profile standard|neutral]`.

## Diagnosis round: execution parity (2026-10-19)

**Goal:** given the same rotation, the forward model and gcsim agree on what physically happens, when, and whether the rotation is executable. No production change. Phases P–R are not started.

**Method**
- `gtc/forward/decompose.py`
  - Every candidate plan is generated and scored by the ForwardModel.
  - The serious finalists are converted to gcsim scripts action for action: idle time becomes `wait()`, and hold variants become `skill[hold=1]` when the kit file measured the hold version.
  - Each finalist runs under the same builds.
  - Scores are steady state: damage landing between the second and the last cycle start, over that time, on both sides.
  - Metrics:
    - calculator error: ForwardModel against gcsim on the same rotation;
    - selection regret: best gcsim finalist against the ForwardModel's choice;
    - search regret: reference against the best gcsim finalist.
- `gtc/forward/parity.py`
  - Reads gcsim's sample log event by event: action starts, `CanQueueAfter` per next-action type, hitlag frozen frames, per-frame "not ready" waits, swaps, explicit waits, particles, flat energy and drains.
  - Splits every inter-action gap on both sides into lock, swap, cooldown, energy, stamina, hitlag, wait and unknown.
  - Reports the per-action and cumulative delta, the first divergence over 0.5 s, each Burst's availability time on both sides, and a full energy ledger (source, element, count, spawn, arrival, collector on/off field, ER, energy).
- **Gate 10** (`gates.py`): execution parity, report only, with no threshold yet.

**Timing and resource failure classes found and fixed** (generic):
1. **Swap animation** (0.2 s) was missing.
2. **Swap cooldown** was missing (measured 0.72 s).
3. **Locks are per transition:** the earliest next action depends on what follows. `gtc/forward/frames.py` measures them, with hitlag, from 363 gcsim logs of non-reference teams; the generator uses them instead of one duration per action.
4. **Particle travel** was a fixed 1.0 s; measured values are 1.7–2.4 s, which moves particles to off-field collectors.
5. **Favonius** was periodic same-element particles; it is now elementless particles from the wearer's crit hits, with refinement chance and cooldown.
6. **Hold and press cooldowns:** measured per variant (Shenhe's hold Skill is 15 s, not 10 s).
7. **Stamina:** a party pool of 240 with Amber Charged Attack costs and dash 18. Regeneration is ASSUMED at 25/s after 1.5 s without use; this matches the zero regeneration measured inside continuous charge strings.
8. **Trailing damage:** damage after the last action was counted with no time behind it. Fixed by steady-state scoring.
9. **Hangs:** a refused action in the carry window looped forever (it only appeared once any member could drive). Every branch now acts or lets time pass.

**Runtime**
- An evaluation takes 9 ms (it was 118 ms: kit metadata was re-parsed on every call).
- The plan search is bounded: at most 900 base plans and 120 s.
- The Burst cadence search is per member (every cycle, every second cycle or never; one member at a time from the best 4 plans), never a Cartesian product.
- Optimised builds are kept as warm starts per character and role.
- Rotations outside the leading candidates are lightened to save memory.
- Typical neutral team: 10–40 s. Realistic-build Hyperbloom: 71 s (it was 84 min).

**Open parity classes**
- **Lock + hitlag accounting:** gcsim's queue frames and hitlag overlap in the split. The residual shows as a negative "unknown" that offsets lock + hitlag; their sum is the action-timing class.
- **Favonius proc counts:** off-field wearers proc less in gcsim (Zhongli 2 against 9). The rule is not yet established, so no rule is assumed.
- **Neuvillette:** an 83 s unexplained stretch in his charged attacks; the held charge differs in gcsim.
- **Energy surplus:** total energy received is still high on our side in several teams (Hu Tao's team waits 20.8 s for Xingqiu's Burst in gcsim).
- **Coverage, not model:** Flins's Thunderous Symphony refund is not in the kit data. Generated Lunar rotations cannot be executed in gcsim (322 s of energy waits). Reported as a data-coverage failure.
- **Mona:** bubble pop timing depends on the context.

## Diagnosis round 2: energy, Neuvillette, reaction events (2026-10-19)

**Energy parity.** `parity.energy_ledger` compares both sides capped at the Burst cost. Sources are aligned per collector, so each first divergence names a mechanic. Fixed, generically:
- **Favonius procs only while the wearer is the active character.** gcsim logs: 4,396 of 4,396 procs. The game text does not state it, so this is recorded as gcsim behaviour.
  - Procs are resolved when the hit lands, in time order, so a summon's later ticks are not on-field hits.
  - They are expected value: each eligible hit adds its share of proc probability as particles. The window closes at 95%, and the cooldown runs from the hit where the probability passed 50%. The previous rule (proc at the median hit) over-procced sparse hitters.
- **Normal/Charged hit energy:** gcsim's core restores 1 flat energy on some Normal/Charged hits (`na-ca-on-hit`). The model uses each character's measured expected energy per hit (successes ÷ eligible hits, other teams' logs).
- **Particle schedules:** a Skill's particles follow the character's measured arrival schedule (Hu Tao: 2.35 s and 8.27 s; Mona: 7.15 s). Zhongli has too few non-reference casts to measure, so he keeps the kit's single bundle; this is a coverage limit.

**Neuvillette.** Minimal gcsim cases:
- the charged attack cycles in 3.43 s with 2–3 Sourcewater Droplets absorbed, and 7.15 s with none;
- the Skill spawns 3 droplets and the Burst 3 + 2;
- gcsim marks the charge cancellable after 3 frames but blocks the next action internally.

Kit language now has `duration_by_resource` (an action whose duration depends on a resource it consumes; its own duration overrides measured cancel frames). Neuvillette has a `droplets` resource; the 1-droplet duration is interpolated (assumed). His team went from +75% to +2% duration error.

**Reaction event parity** (`gtc/forward/rxparity.py`): applications aligned per character, producing action and element, compared on aura before/after; reaction counts and owners; Dendro cores; Quicken uptime.

Fixed in `reactions.py`, matching gcsim's logged aura states:
- **Electro on Quicken:** Aggravate does not consume Quicken, and the Electro stays as its own aura beside it, or refreshes Quicken from a coexisting Dendro.
- **Dendro on Quicken:** Spread, and the Dendro coexists or refreshes Quicken from a coexisting Electro.
- **Hydro on Quicken with Electro present:** Bloom, and the Hydro coexists so Electro-Charged runs.
- **EC ownership:** Electro-Charged belongs to whoever created or refreshed the Hydro + Electro coexistence.
- **Dendro cores:** an Electro or Pyro application triggers every core present.

Kit language now has `reaction_procs` (procs on reaction events, applied after the reaction model, two passes). Fischl's A4 is now a rule from the kit text (the active character's Electro-related reactions while Oz is on field, 80% of her ATK) instead of fixed-time hits measured from other teams.

**Open in this area**
- **Hold/press frame data:** locks are measured per state, not per variant (Shenhe's held Skill hit lands after our Burst starts).
- **Oz attack timing** in the Fischl kit.
- **Hydro application counts in the Hyperbloom team**, which limits cores (Hyperbloom 40 against 82).
- **Rain Sword counts on Razor.**
- **Nahida's Tri-Karma first proc timing.**
