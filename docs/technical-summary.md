# Genshin theorycraft engine: technical summary for architectural review

Written 2026-10-11 from the code as it stands (engine model version 5.0). It describes what exists. Proposals
are deliberately left out; there is a separate proposal in docs/reliability-plan.md. Paths are relative to
the project root. The project is Python 3, about 9,900 lines in `gtc/`, run from the command line.

Contents:
1. Project overview
2. Architecture
3. Knowledge model
4. Knowledge sources and ingestion
5. Team generation
6. Team classification and archetypes
7. Team strength evaluation
8. Personal account evaluation
9. Pull value
10. Multi-team optimisation
11. gcsim and the theory calculator
12. Benchmark and calibration
13. Testing
14. Known open problems
15. What works well
16. Representative examples
17. File map
18. Final state summary

---

## 1. Project overview

**What it does.** It is a personal, deterministic "theorycrafter" for one Genshin Impact account. It imports
the account from HoYoLAB, judges which teams the account can field and how strong they are, and recommends:
- the best four non-overlapping teams
- build fixes (talents, levels, artifacts, weapons, Energy Recharge, set choices), each with an estimated or
  simulated damage gain
- which unowned characters would add the most value if pulled

It knows the whole game, not just the owned roster, through:
- gcsim's public simulation database (community damage simulations)
- Prydwen (tier lists, team pages, build pages)
- Keqing Mains character guides
- Project Amber (game data and talent text)

**No LLM is used anywhere.** A search of `gtc/` for anthropic, openai, llm or gpt finds nothing. All
interpretation of source pages is regex and HTML/JSON parsing.

**Workflow:**

```text
python -m gtc gamedata      game data from Project Amber -> knowledge/generated/game_*.json
python -m gtc sources       gcsim database, Prydwen, Keqing Mains -> data/sources/*.json (cached HTTP)
python -m gtc synergy       our own gcsim runs of ~3,800 community lineups with per-hit logs -> data/sources/synergy.json
python -m gtc derive        capability profiles, generated roles and archetypes, validity rules, pair model,
                            uncertainty measurement -> knowledge/generated/*, data/sources/*
python -m gtc aoe           3-target gcsim runs of 159 lineups -> data/sources/aoe.json
python -m gtc kits          generated calculator kits from gcsim logs -> knowledge/generated/kits_auto.yaml
python -m gtc import        HoYoLAB account -> data/snapshots/<date>.json
python -m gtc inventory F   optional scanner export (GOOD format) adds unequipped weapons and artifacts
python -m gtc account       the main report: plan, content modes, carries, pull values, build to-do list
python -m gtc review        per-team build review with personal gcsim simulations
python -m gtc teams         per-archetype team report
python -m gtc theory ...    swap calculator ("what if X replaces Y")
python -m gtc audit         data consistency check over every character
python -m gtc benchmark     scores the engine on knowledge/benchmark.yaml (--tune, --record)
```

**User-facing outputs** are Markdown reports in `reports/`:
- **account-<date>.md:**
  - the best four teams, each with potential ± sd, evidence tier, today's rating and build progress
  - comparison against the meta
  - plans per content mode
  - main damage dealers and carries that would fit the owned supports
  - top pull candidates with gain ± sd, confidence and kind
  - the ranked to-do list from the review
- **review-<date>.md:** per team:
  - personal simulation numbers and damage share
  - Energy Recharge cost
  - "what each teammate brings", from measured synergy
  - findings with gains, effort and source
- **teams-<date>.md:** the best team per archetype, with evidence and calibration statistics.
- **audit-<date>.md:** characters with contradictions or gaps.

---

## 2. Architecture

### 2.1 Module interaction (main data flow)

```text
HoYoLAB (genshin.py) --> importers/hoyolab.py --> Snapshot (snapshot.py)
GOOD scanner export  --> importers/good.py    -/

sources/{gcsim_db,prydwen,kqm,fetch,names}.py --> data/sources/*.json (raw, cached)
gamedata.py (Project Amber)                   --> knowledge/generated/game_*.json

synergy.py (Attributor over gcsim -sample logs) --> data/sources/synergy.json  (per-lineup attribution and profile)
capabilities.py   --> data/sources/capabilities.json  (per-character averages of measured behaviour)
derive.py         --> knowledge/generated/auto_roles.yaml, auto_templates.yaml, data/sources/family_lineups.json
validity.py       --> knowledge/generated/validity.yaml
pairmodel.py      --> data/sources/pair_effects.json
estimate.py       --> data/sources/uncertainty.json
aoe.py, kitgen.py --> data/sources/aoe.json, knowledge/generated/kits_auto.yaml

knowledge.py loads characters.yaml + templates.yaml + generated files -> Knowledge (characters, templates, scoring)
evidence.py builds Evidence (simulations indexed, Prydwen, Keqing Mains, medians, structures, calibration)

report.analyze(snapshot, kb):
    investment.rate per owned character -> Member(key, element, investment, roles, constellation)
    teams.fill_template per template -> Team candidates
    report.assess(team) -> Assessment (tier, fit, estimate, power, lead, rating)
account.AccountModel: candidates -> best_plan -> value_of (pull) -> profiles.plan_for (content modes)
review.build_review: rule checks + sim.TeamSim personal gcsim runs + teammate swaps (+ tc theory swaps)
account.build_report / review.render / report.render -> reports/*.md
```

### 2.2 Subsystems

**Account ingestion: `gtc/importers/hoyolab.py`.** Not Enka.
- **Fetching.** `genshin.Client(cookies).get_genshin_detailed_characters(uid, return_raw_data=True)`.
  Cookies (LTUID_V2, LTOKEN_V2, LTMID_V2) and the UID come from a git-ignored `.env`.
- **Talents.** HoYoLAB reports talent levels with constellation boosts included. `_talents()` parses each
  unlocked constellation's text ("Increases the Level of X by 3") and subtracts the boost, storing base and
  bonus separately.
- **Artifacts.** Main stat and substats in GOOD keys, with roll counts (`times + 1`).
- **Weapons.** Name, rarity, level, refinement, type and ascension (`promote_level`).
- **Final stats** from `property_map`: hp, atk, def, crit_rate, crit_dmg, energy_recharge,
  elemental_mastery.
- **`importers/good.py`** imports a scanner export (GOOD JSON) to add spare weapons and artifacts
  (`snapshot.has_inventory = True`). `python -m gtc import` carries inventory over from the previous snapshot.

**Character and build representation: `gtc/snapshot.py`.**

```python
Character(id, name, element, rarity, level, constellation, talents: Talents, weapon: Weapon,
          artifacts: list[Artifact], stats: dict)   # key = "Traveler (Cryo)" for Traveler
Talents(normal, skill, burst, normal_bonus, skill_bonus, burst_bonus)   # .effective adds the bonuses
Weapon(name, rarity, level, refinement, type, ascension, location)
Artifact(slot 1-5, set_name, rarity, level, main_stat (GOOD key), main_value, substats=[{key, value, rolls}], location)
Snapshot(uid, source, taken_at, characters, spare_weapons, spare_artifacts, has_inventory)   # .data_level "full"|"basic"
```

**For team logic the engine reduces a character to a `Member`** (`gtc/teams.py`):

```python
Member(key, element, investment: float 0..1, roles: dict[str, int], constellation)
```

**Investment: `gtc/investment.py`.**
- **Formula.** Weighted 0-1 score from `knowledge/scoring.yaml`: level 0.30, talents 0.20, weapon 0.20,
  artifacts 0.30.
- **Level** follows a curve (90 → 1.0, 80 → 0.9...).
- **Talents** count the key talents' effective levels toward a target of 9.
- **Weapon** is its level curve times a rarity factor (5★ 1.0, 4★ 0.85...).
- **Artifacts** are 40% pieces and levels plus 60% substat quality (`gtc/artifacts.py`: useful rolls, see
  section 7).

**Team generation: `gtc/teams.py`** (`fill_template`, `slot_candidates`, `score`, `team_is_valid`,
`elements_fit`). Template-and-slot search with branch and bound; section 5.

**Team scoring has two layers:**
1. **Role score** (`teams.score`): slot quality weighted, investment-scaled, with bonuses. Used to search and
   rank lineups within a template.
2. **Evidence-based assessment** (`report.assess`): archetype tier × lineup fit from simulations or models,
   as an `Estimate` with sd and tier. This is the number shown and planned on. Section 7.

**Archetype detection.** Implicit: a lineup belongs to whichever template's slots it fills; data families
come from `derive.family_of`. Section 6.

**Reaction handling.** Three different places:
- **Attribution** (`synergy.Attributor`): reaction damage, reaction bonuses, enablement, all measured from
  gcsim logs.
- **Classification:** element signatures and data families.
- **The calculator** (`gtc/tc`): direct hits, Lunar and Swirl formulas only.

**Synergy scoring:**
- **Measured** pair and lineup shares (`synergy.SynergyTable`).
- **A fitted ridge model** of pair effects (`gtc/pairmodel.py`).
- **Role slot "value formulas"** in templates.

**Rotation handling.** Rotations are never modelled by the engine itself. They come only from community gcsim
configs, used as-is. The engine edits builds (`sim.render`) and, for the Energy Recharge reality mode, the
Burst statements (`sim.guard_bursts`).

**Energy Recharge logic:**
- **Rule check** (`review.check_member`): ER against the Prydwen or Keqing Mains requirement table for this
  team composition (`Guides.er_target`).
- **Simulation:**
  - `TeamSim.baseline` adds ER in 10% steps until no character waits for a Burst more than 3 s (the
    "potential").
  - `TeamSim.reality` runs without the top-up on a rewritten rotation that waits up to 300 frames for a
    Burst, then skips it.
  - `er_cost` reports the damage lost and the Bursts skipped.
- **Artifact rating.** ER substats only count up to the lowest listed requirement.

**Damage calculations:**
- **Exact game formulas** in `gtc/tc/formulas.py`, checked against gcsim constants in a test:
  - amplifying EM bonus: 2.78·EM/(1400+EM)
  - transformative: 16·EM/(2000+EM)
  - additive (catalyze): 5·EM/(1200+EM)
  - Lunar EM bonus: 6·EM/(2000+EM)
  - RES and DEF multipliers, average crit, reaction level base
- **Where they are used.** In attribution, to recompute each logged hit without each buff, and in the
  calculator. Team strength itself comes from gcsim DPS, never from our own damage model.

**gcsim integration: `gtc/sim.py`** with a downloaded binary (`data/tools/gcsim.exe`, v2.48.8):
- **Config lookup.** `find_config` takes a community config for a lineup from the database.
- **Rendering.** `render` rewrites the character, weapon, set and stat lines to the user's builds; weapon
  level caps use the snapshot's ascension.
- **Running.** `run` caches results by config hash.
- **Single-change variants** (`plan_variants`): talent +1 or to 9, level 90, community-standard artifacts,
  each owned weapon.
- **Attribution logs.** `synergy.run_sample` produces per-hit `-sample` logs.

**Pull value, account planning, recommendations:** `gtc/account.py`, `gtc/profiles.py` and `gtc/review.py`;
sections 9 and 10.

**Data files:**
- **`knowledge/`**, hand-written and versioned:
  - `characters.yaml` (83 entries), `templates.yaml` (13 archetypes)
  - `scoring.yaml`, `sets.yaml`, `kits.yaml`, `kits_custom/`, `my_teams.yaml`
  - `model.yaml` (32 tunable parameters plus profiles), `benchmark.yaml` (46 cases), `benchmark_results.yaml`
- **`knowledge/generated/`:** game data, `auto_roles.yaml` (127 characters), `auto_templates.yaml`
  (23 archetypes), `validity.yaml`, `kits_auto.yaml` (108 characters).
- **`data/sources/`** (git-ignored, personal use):
  - raw source data, including 6,020 gcsim database teams
  - `synergy.json` (3,800 lineups), `capabilities.json`, `pair_effects.json`
  - `family_lineups.json`, `uncertainty.json`, `aoe.json`, `calculator_validation.json`
- **`data/sims/`:** cached gcsim configs and results.

---

## 3. Knowledge model

### 3.1 Characters

**Hand-written** in `knowledge/characters.yaml`: roles as `role → quality 1..5`, key talents,
constellation-gated roles and notes. Example:

```yaml
Ineffa:
  roles: {offfield_app: 4, offfield_dps: 4, shield: 3, buffer_lunar: 4, moonsign: 5, enables_lunar_charged: 5}
  key_talents: [skill, burst]
Kaedehara Kazuha:
  roles: {buffer_anemo: 5, cc: 5}
```

**The role vocabulary** (documented in the file header):
- carriers: `carry_<archetype>`
- off-field: `offfield_app`, `offfield_dps`
- buffers: `buffer_atk`, `buffer_anemo`, `buffer_cryo`, `buffer_general`, `buffer_overloaded`,
  `buffer_lunar`, `em_share`
- utility: `healer`, `shield`, `battery`, `cc`, `def_shred`
- factions and enablers: `moonsign`, `enables_lunar_charged`, `enables_bloom`

**Generated** in `knowledge/generated/auto_roles.yaml` by `derive.build`, each role with its reason:

```yaml
Bennett:
  roles: {buffer_general: 5, carry_vape: 3, healer: 3, support_anemo_carry: 5, support_mono_pyro: 5, ...}
  why:
  - 'buffer_general 5: Prydwen Support T0.5'
  - 'healer 3: talent description'
  - 'carry_vape 3: carries Vaporize (Pyro carry) in 459 gcsim sims'
  - 'support_mono_pyro 5: teams with them perform at quality 5 in Mono Pyro gcsim sims'
```

**Where generated roles come from:**
- **Prydwen categories:**
  - Sub-DPS → `offfield_dps` and `offfield_app` (plus one level with the "high app" tag)
  - Support → `buffer_general` (or `buffer_anemo` for Anemo)
  - tiers map to quality: T0/T0.5 → 5, T1/T1.5 → 4, T2 → 3, T3/T4 → 2, T5 → 1
- **Project Amber talent text, by regex:** `healer`, `shield`, `res_shred`, `def_shred` at quality 3.
- **gcsim data families:**
  - `carry_<family>`, from the carry's best simulated lineup over the family's best, cut at 0.9 / 0.75 /
    0.6 / 0.45 for quality 5 to 2
  - `support_<family>`, from the measured pair share with the family's carries, cut at 0.30 / 0.22 / 0.15 /
    0.08 of team damage, including enablement
- **Unsimulated carries:** characters Prydwen rates as DPS with no standard gcsim teams get
  `carry_unsimulated`, which no template accepts.
- **Factions:** Prydwen synergy tags such as Moonsign or Hexerei become `faction_<tag>` roles at runtime
  (`Evidence.faction_roles`).

**Merge rule** (`knowledge.load`): hand-written wins. For a hand-written character, only the generated
`carry_*` and `support_*` roles plus healer, shield and shred are added. Purely generated characters are
flagged `generated: true`. Hand-written kits in `kits_custom/` with `expected_archetypes` can override roles
for unsimulated characters (`custom_kit: true`).

**Capability profile** (measured, `data/sources/capabilities.json`, via `capabilities.aggregate`): the mean
over every simulated lineup containing the character of:
- `damage_share`, `field_share`
- `apply` (applications per 10 s, keyed like `"Hydro.off"`)
- `triggers` (reactions per 10 s), `heal_per_s`, `team_reaction_share`

The `Capability.onfield` flag means `field_share >= 0.35`.

### 3.2 Archetypes (team templates)

**Hand-written** in `knowledge/templates.yaml`, 13 of them:
- `lunar_charged`, `lunar_charged_offfield`
- `freeze`, `melt`, `national`, `vaporize_pyro`, `international`
- `aggravate`, `hyperbloom`, `nilou_bloom`
- `electro_hypercarry`, `mono_geo`, `overloaded`

A template has four slots (roles, elements, `core`, `min_quality`, `weight`, an optional `value` formula),
plus:
- `ceiling`: archetype strength 0..1, a judgment
- `signature`: element pattern (require, forbid, only)
- `requires`: hard role conditions
- `bonuses`, `pair_bonuses`: soft
- `allowed_elements`, `sustain_penalty`
- `compare`: lead or archetype

Example (trimmed):

```yaml
lunar_charged:
  label: Lunar-Charged (Flins hypercarry)
  signature: {require: [Electro, Hydro]}
  ceiling: 1.0
  slots:
    - {name: Lunar carry, roles: [carry_lunar_charged], elements: [Electro], core: true, weight: 2}
    - name: Hydro applicator
      roles: [offfield_app]
      elements: [Hydro]
      core: true
      min_quality: 3
      weight: 1.5
      value: {base: 2, offfield_app: 0.15, buffer_lunar: 0.4, offfield_dps: 0.1}  # tuned on gcsim: Columbina > C6 Aino > Furina
    - {name: Electro enabler, roles: [enables_lunar_charged, offfield_app], elements: [Electro], ...}
    - {name: Flex support, roles: [buffer_anemo, em_share, shield, healer, buffer_atk, offfield_app, moonsign, buffer_lunar], ...}
  requires: [{role: enables_lunar_charged, at_least: 1}]
  bonuses: [{role: moonsign, at_least: 2, bonus: 8, reason: "Ascendant Gleam with 2+ Moonsign characters"}]
```

**Generated** in `knowledge/generated/auto_templates.yaml`, 23 of them:
- `auto_anemo_carry`, `auto_geo_carry`
- `auto_mono_hydro`, `auto_mono_pyro`, `auto_mono_cryo`, `auto_mono_electro`
- `auto_melt_pyro_carry`, `auto_quicken_dendro_carry`, `auto_burning_pyro_carry`, `auto_burning_dendro_carry`
- `auto_overloaded_electro_carry`, `auto_overloaded_pyro_carry`
- `auto_electro_charged_electro_carry`, `auto_electro_charged_hydro_carry`
- `auto_hyperbloom_electro_carry`, `auto_hyperbloom_dendro_carry`, `auto_hyperbloom_hydro_carry`
- `auto_lunar_charged_hydro_carry`, `auto_freeze_hydro_carry`
- `auto_bloom_hydro_carry`, `auto_bloom_dendro_carry`
- `auto_superconduct_electro_carry`, `auto_superconduct_cryo_carry`

They come from `derive.discover`:
- **Grouping.** Every standard gcsim lineup, one median representative per lineup, is grouped into a
  "family" by its carry and `family_of`.
- **The carry** is the lineup's measured top damage owner (hypercarry or dual carry structure).
- **The family** is named after the carry's reaction with partner elements, in a fixed priority order:

```python
PARTNER_PRIORITY = {"Pyro": [("Hydro","Vaporize"), ("Cryo","Melt"), ("Electro","Overloaded"), ("Dendro","Burning")],
                    "Hydro": [("Pyro","Vaporize"), ("Electro","Electro-Charged"), ("Dendro","Bloom"), ("Cryo","Freeze")],
                    "Cryo": [("Hydro","Freeze"), ("Pyro","Melt"), ("Electro","Superconduct")],
                    "Electro": [("Dendro","Quicken"), ("Hydro","Electro-Charged"), ("Pyro","Overloaded"), ("Cryo","Superconduct")],
                    "Dendro": [("Electro","Quicken"), ("Hydro","Bloom"), ("Pyro","Burning")]}
# Anemo/Geo carry -> "<element> carry"; Moonsign carry with Electro+Hydro -> Lunar-Charged; Moonsign with Dendro+Hydro
# -> Lunar-Bloom; Dendro+Hydro+Electro without Pyro (carry of those elements) -> Hyperbloom; no partner -> "Mono <element>".
```

- **Mapping to hand-written templates.** A family maps onto a hand-written template when
  `TEMPLATE_FOR[(reaction, carry_element)]` exists, for example (Vaporize, Pyro) → `vaporize_pyro`.
  Otherwise it becomes an `auto_` template with generic slots:

```yaml
auto_<slug>: slots: [{carry_<slug>, core, weight 2}, {support_<slug>, weight 1.5}, {support_<slug>},
                     {support_<slug> | healer | shield | buffer_general | buffer_anemo}]
```

- **Lineup lists.** Each family's lineups are saved in `data/sources/family_lineups.json`. They are used to
  rate the archetype (`Evidence.sims_for`) and to learn its validity rules.

### 3.3 Reactions

Reactions are not first-class objects. They appear in five places:
- **Element signatures** on templates (require, forbid, only) and family names.
- **Attribution constants** in `synergy.py`:
  - `TRANSFORMATIVE` coefficients (hyperbloom 3.0, burgeon 3.0, bloom 2.0, overload 2.75, electrocharged 2.0,
    superconduct 1.5, shatter 3.0, burning 0.25, swirl 0.6)
  - `CATALYZE` (aggravate 1.15, spread 1.25)
  - `AMP_AURA` (which aura an amplifying hit consumes)
  - `REACTION_AURAS` and `CORE_REACTIONS`, for enablement
- **Measured per-lineup profiles:** reaction triggers per member and the team's `reaction_share`.
- **Calculator damage kinds:** direct, lunar_charged_direct, lunar_charged_reaction, swirl.
- **`report.engine_factor`:** a swap estimate's damage is scaled down when the swap cuts the application of
  an element the archetype reacts with.

### 3.4 Synergy

There is no explicit synergy graph, and no hard-coded pairs except three things:
- template `pair_bonuses`, which no template currently uses
- one Prydwen-described rule in `kits.yaml` (Ascendant Gleam)
- the archetype ceilings

Synergy is known in four measured ways:
1. **Measured per-lineup attribution** (`data/sources/synergy.json`, 3,800 lineups). For each member: own
   damage share, buff share (marginal), Shapley share, enablement share, and a breakdown by
   `target|kind` (atk%, em, res shred, reaction bonus, enablement...).
2. **Pair table** (`synergy.SynergyTable`): for each carry and teammate, the teammate's mean share of team
   damage alongside that carry, over every simulated lineup.
   - `pair_value` weights lineups by shared teammates: ×10 per shared teammate.
   - It shrinks toward a prior with 2 pseudo-lineups.
   - Unproven pairs get 0.5 × the leaving member's share.
3. **Fitted pair effects** (`gtc/pairmodel.py`, 1,857 pairs):

   ```text
   log(team DPS) = archetype effect + Σ character effects + lead effect + Σ pair effects
   ```

   Ridge regression with λ 0.3 for characters, 1.0 for pairs, 0.01 for archetypes, and pairs needing at least
   2 lineups. Examples: Nahida+Kuki +6.9%, Kuki+Xingqiu +9.3%, Nahida+Thoma +10.2%, Ayaka+Shenhe +13.1%,
   Razor+Kazuha −6.2%.
4. **Teammate quality in generated archetypes** (`teams.carry_mate_quality`): capped by measured share with
   this specific carry. Never simulated together → 2; a single simulated team → at most 4. Healers and
   shields are exempt.

### 3.5 Team legitimacy (validity)

Checked when the team search reaches a full lineup (`teams.team_is_valid`, cached per lineup and template):

1. **Element signature** (`elements_fit`).
2. **Template `requires`** (role counts).
3. **Learned archetype rules** (`validity.check`, from `knowledge/generated/validity.yaml`):
   - `require_apply`: per reacting element, at least half the 5th percentile of the archetype's own simulated
     teams' predicted application
   - `forbid`: elements that never appear in its teams
   - `max_onfield`: the 98th percentile of predicted on-field characters
   - "Own teams" are the family lineups for generated archetypes, and lineups that fill the template with a
     damage owner able to hold the carry slot for hand-written ones.
4. **Structure check** (`validity.check_structure`). The team's damage owner (measured if simulated,
   otherwise predicted) must be able to hold the template's first slot. Then the carry's teammate rules
   apply:
   - **Per carry overall** (`_carries`): teammate elements present in at least 95% of their simulated teams.
     Example: Skirk needs Cryo and Hydro.
   - **Per carry within an archetype:** elements never seen with them. Two or more such teammates reject the
     lineup; one is allowed as a flex.
   - **No single owner predicted:** the carry-slot holder's teammate rule still applies.

Recall is the share of an archetype's own simulated teams accepted. It is 93 to 100% across 32 archetypes; the
lowest are `auto_bloom_dendro_carry` 93% and `auto_burning_dendro_carry` 94%.

### 3.6 Representation summary

| Concept | Form |
|---|---|
| Roles | integer quality 1..5 per role tag |
| Factions | role tags |
| Archetypes | templates with role slots, element signatures and judgment ceilings |
| Validity | element sets and learned numeric thresholds |
| Structure | categorical, from damage-share thresholds: hypercarry ≥ 0.55, dual carry 2nd ≥ 0.25, reaction core ≥ 0.50 reaction share, driver field ≥ 0.40 with damage < 0.25, else distributed |
| Synergy | measured shares, ridge pair effects |
| Strength | gcsim DPS normalised to the meta |
| Uncertainty | Gaussian sd per evidence tier |

---

## 4. Knowledge sources and ingestion

All sources are fetched at preprocessing time (`python -m gtc sources`, `derive`, `synergy`) and cached
(`gtc/sources/fetch.py`; Prydwen needs a browser user agent). At runtime the engine reads only local JSON and
YAML. No LLM touches any of it.

| Source | Module | Extracted | Structured into | Used for |
|---|---|---|---|---|
| gcsim public database (`db.kqm.gg/api/db`, pages of 100) | `sources/gcsim_db.py` | 6,020 teams: members (constellation, weapon, refinement), DPS, targets, tags, config text, submitter | `SimTeam`; `is_standard` = single target, accepted tags {1, 9}, 5★ at C0 and 5★ weapons at R1 | Archetype tiers, lineup fits, families, roles, synergy runs, pair model, uncertainty |
| gcsim binary v2.48.8 | `sim.py`, `synergy.py` | Our own runs: DPS, per-character DPS, failed actions, Burst counts, per-hit logs | `synergy.json`, `aoe.json`, `kits_auto.yaml`, personal sims | Attribution, structure, capabilities, AoE, ER cost, build gains |
| Prydwen (HTML plus RSC payload) | `sources/prydwen.py` | Tier list (category DPS / Sub-DPS / Support, overall tier, 3 Stygian boss ratings, tags such as expert, comfort, driver, CC, assumed constellation); per character: teams with %, constellations, weapons, ER table, main stats, sets, synergy tags (factions), usage stats | `prydwen.json` | Roles (category and tier), primary-carry test, execution penalty, tier fallback, Prydwen fits (tier C), ER targets, set fallback, factions, partner notes |
| Keqing Mains quick guides | `sources/kqm.py` | Example teams (slot lines and descriptions), teammates by slot with notes, talent priority, ER requirement tables, main stats, substat priority tiers, sets, weapons, formulas, pros, cons | `kqm.json` (117 characters) | Review rules (talents, main stats, sets, weapons, ER, crit), artifact weights, "Keqing Mains lists this team" evidence text, teammate notes |
| Project Amber (gi.yatta.moe) | `gamedata.py`, `derive.talent_texts` | Characters, weapons, sets, talent descriptions | `game_*.json`; regex roles | Element, rarity and weapon type; healer, shield and shred roles |
| Hand-written knowledge | `knowledge/*.yaml` | Roles, templates, set rules, Lunar kits, scoring, parameters, benchmark | YAML | Everything above |

**What stays unstructured.** Keqing Mains example team descriptions, teammate notes, pros and cons, and
Prydwen notes stay text. They are shown in reports but never scored. KQM `formulas`, `pros` and `cons` are
parsed but unused by any decision.

**New characters:**
- Re-running `sources` and `derive` adds them automatically once they appear in game data, Prydwen and gcsim.
- Without simulations they get `carry_unsimulated` (if Prydwen calls them DPS) or Prydwen-derived support
  roles. That gives evidence tier E (role rules) or F (cannot evaluate).
- A hand-written kit in `knowledge/kits_custom/` with `expected_archetypes` and `capabilities` places them in
  teams, as tier E.
- `python -m gtc audit` lists every such gap.

---

## 5. Team generation

**Not brute force over all combinations.** It is template-driven role-slot filling with exact branch and bound.

`teams.fill_template(template, roster, kb, limit, lead, rank_by, must)`:
1. **Slot candidates.** For each slot, the roster members with any of the slot's roles at or above
   `min_quality` and an allowed element (`slot_candidates`). Slot quality is the best role quality (non-preferred
   roles × 0.8), or the slot's `value` formula: `base + Σ weight·quality`, capped at 5.
2. **Depth-first assignment of slots in template order** (slot 0 is the carry slot, filled first). Each member is
   used at most once. In generated `auto_` templates a teammate's quality is capped by
   `carry_mate_quality(carry, mate)`.
3. **Bound.** `scale · (acc + Σ best remaining slot quality) + max_extra < Nth best` prunes the branch. A test
   checks this matches full enumeration exactly.
4. **At a full lineup**, in order:
   - template `requires`
   - `elements_fit` (signature)
   - `team_is_valid` (learned rules plus structure check, section 3.5)
   - `score()`: the role score is `100 · ceiling · Σ(weight·quality/5·(floor + (1−floor)·investment)) / Σ weight`,
     plus bonuses (Moonsign 2+: +8; Hexerei 2+: +4 in Lunar templates), minus 5 with no healer or shield
5. **Deduplication.** Each distinct member set keeps its best slot assignment. The top `limit` are returned by
   current or potential role score.

**Callers:**
- `account.candidates(roster)` runs every template (36) with `limit=12`, assesses each team
  (`report.assess`) and deduplicates across templates, keeping the assessment with the highest risk-adjusted
  potential. For pull values it adds `must_include=name`.
- `report.analyze` uses `limit=8` per template.
- `evaluate_lineup` fits a given lineup to the best template.
- `ideal_team` is the best team from the whole universe, for the model fit.

**Discovery of new teams.** Yes, within the role-slot space. Any lineup that fills a template's slots and passes
validity is generated, simulated or not. It is valued by the evidence chain (section 7). It cannot discover a
team shape outside the 36 templates. It does not start from DPS characters explicitly; templates do, through
their first slot. Known teams (gcsim, Keqing Mains, Prydwen) are used as evidence, not as a generation source.

---

## 6. Team classification and archetypes

### 6.1 How a label is decided today

- A lineup's archetype is the template that generated it. When several templates can generate the same member
  set, `account.candidates` keeps the one whose assessment has the highest risk-adjusted potential. **The
  label is therefore chosen by value, not by identity.**
- The display label is `template.label` plus `Assessment.lead`. For example "Lunar-Charged (Flins
  hypercarry)", "Hyperbloom (Electro carry) (from gcsim data)", "Freeze".
- **Lead** (`evidence.damage_lead`):
  1. The measured structure of this exact lineup (from synergy.json) or a predicted one (`validity.structure_of`
     → `capabilities.predict_structure`, neighbour-weighted ×100 per shared teammate).
  2. For hypercarry, dual carry and driver structures: the top damage owner, if they fit the template's first
     slot. Otherwise the first-slot holder.
  3. For reaction-core or distributed structures: `None` if measured; the first-slot holder if predicted.

### 6.2 Per reaction type

| Type | How it is recognised |
|---|---|
| Hyperbloom | `hyperbloom` template (Dendro, Hydro and Electro applicator slots, archetype compare); `auto_hyperbloom_*_carry` families when carry is D/H/E and D+H+E are present without Pyro |
| Aggravate | `aggravate` template; `auto_quicken_dendro_carry`; family "Quicken (Electro carry)" maps to `aggravate` |
| Spread | No separate archetype: Dendro carry with Electro → "Quicken (Dendro carry)" |
| Vaporize | `vaporize_pyro` (Pyro carry), `international` (Hydro carry with Pyro) |
| Melt | `melt` (Cryo carry), `auto_melt_pyro_carry` |
| Freeze | `freeze` (Cryo carry), `auto_freeze_hydro_carry` |
| Overloaded | `overloaded` (hand-written, Chevreuse in the first slot), `auto_overloaded_electro_carry`, `auto_overloaded_pyro_carry` |
| Lunar-Charged | `lunar_charged`, `lunar_charged_offfield`, `auto_lunar_charged_hydro_carry`; families need a Moonsign carry |
| Hypercarry | `electro_hypercarry`; elsewhere a structure type, not an archetype |
| Mono-element | `auto_mono_*`, `mono_geo` |
| Mixed reactions | No representation: a team with two significant reactions gets one archetype |

### 6.3 Known classification problems

- **Raiden / Kazuha / Xingqiu / Yaoyao** is labelled "Hyperbloom (Electro carry) (from gcsim data)". It fills
  the generic hyperbloom slots and passes validity because Yaoyao supplies Dendro. Its value (pair model
  67k, close to the simulated Raiden / Kazuha / Xingqiu / Yelan at 65k) is plausible. But it plays as an
  on-field Raiden team with a little Hyperbloom on the side. The label reflects slot fit, not damage source.
- **Chevreuse / Xiangling / Raiden / Yae** gets "Chevreuse Overloaded" with Chevreuse as lead. The
  hand-written `overloaded` template puts Chevreuse in slot 0 as `buffer_overloaded`, and the lead falls back
  to the slot-0 holder.
- **Clorinde** was labelled a Lunar-Charged carry until the family rule required a Moonsign carry. She tops
  damage next to Ineffa and Columbina, with only 23% of team damage from reactions.
- **Families follow a fixed partner priority.** A Bennett-carried team with Hydro and Electro is "Vaporize"
  regardless of how much Overloaded it does.
- **Generated archetypes are coarse** ("Anemo carry", "Geo carry") and lump different play styles together.
- **No type exists for quickswap, on-field driver teams** (Mizuki and Ifa are drivers by measurement) or
  multi-reaction teams.

---

## 7. Team strength evaluation

### 7.1 The value chain (`report.assess`)

```text
lead      = evidence.damage_lead(team)
tier      = evidence.archetype_tier(template, lead)
            best lineup median DPS among simulations of this archetype attributed to `lead`, over the normalizer
            (average of the top 3 lineup medians in the whole standard database), capped at 100.
            Fallback: Prydwen tier value.
fit       = evidence.lineup_fit(...):
            1. measured: this lineup's median / the lead's best lineup median (standard sims)           -> tier B
            2. Prydwen team percentage when Prydwen lists the exact team                                -> tier C
            3. pair_model_fit: predicted DPS / best lineup median (C one member from a simulation, else D)
            4. synergy_fit: swap estimate from simulated lineups 1-2 members away                       -> tier D
                 fit · (1 − Σ leaving shares + Σ newcomer shares) · engine_factor, gains capped at +10·min(1, n/5)
            5. anchored role-model estimate (calibrated role score), or unanchored                      -> tier E
estimate  = potential_estimate: value = tier × fit / 100, sd by evidence tier (relative errors in quadrature)
            × execution factor (1 − 0.03 × Prydwen "expert (-N)" level)
potential = expected − 0.674 × sd          (risk-adjusted; this is what planning ranks by)
rating    = potential × build% / 100       (build% = role score at current investment / at full investment)
power     = {single_target: estimate,
             aoe: estimate × (AoE ratio / median ratio),
             sustain: 20 × best healer or shield role quality}
```

### 7.2 Measured uncertainty per tier

From `data/sources/uncertainty.json`, written by `estimate.measure`. One sd is the 68th percentile of held-out
absolute errors.

| Tier | Evidence | sd |
|---|---|---|
| A | Personal gcsim run | iteration standard error, about 0.2% |
| B | Community median | 9.8% for one submission; ×1.25/√n for n ≥ 3 |
| C | Pair model one member away | 9.9% |
| C | Prydwen team rating | 4.7 fit points |
| D | Pair model two or more away | 13.8% |
| D | Swap estimate | 14.4% |
| E | Role model | leave-one-out calibration: about 13 points anchored, 16 unanchored |
| F | No data | not estimated |

Coverage on held-out halves is 63 to 73% within 1 sd and 91 to 95% within 2 sd.

### 7.3 Factor status

| Factor | Status | Implementation |
|---|---|---|
| DPS | Implemented well | gcsim community lineups, median per lineup, normalised to the meta |
| Direct-hit and reaction damage | Implemented via gcsim | gcsim does the damage; our formulas are only used in attribution and the calculator |
| Buffs, RES shred | Implemented well (measurement) | Per-hit attribution, marginal and exact Shapley; feeds explanations, teammate ratings and the pair table, not the DPS number |
| Energy Recharge | Partial | Rule checks against guide tables; personal sims top up ER (potential) and report the as-built cost; team potential assumes the community build's ER |
| Rotation feasibility | Partial | Inherited from community configs; personal sims report stalls; no own rotation model |
| Field time | Partial | Measured per lineup; used in validity (`max_onfield`) and structure; not in value |
| Survivability | Weak | Sustain power is role quality × 20; no-sustain penalty of 5 in the role score; heals measured but unused |
| Grouping or crowd control | Weak | `cc` role exists (Kazuha 5), worth 0.1 in some slot formulas only |
| Interruption resistance | Missing | — |
| AoE | Partial | Own 3-target runs, 159 lineups, 85 characters; tight grouping assumption; used in content modes only |
| Support compatibility | Implemented | Learned validity, carry teammate rules, pair model, measured pair shares |
| Artifact assumptions | Defined | Team values assume community-standard builds (C0 5★, R1 5★ weapons); the user's artifacts only change "today" and the review |
| Player-owned builds | Partial | In build progress, rating and personal sims; not in potential, plan or pull values |
| Constellations | Partial | Owned constellation unlocks `constellation_roles` in the role model; tiers and fits are C0 community; pull value assumes C0 |
| Execution difficulty | Weak | Prydwen "expert (-N)" tag gives −3% per level |

---

## 8. Personal account evaluation

**What uses the actual account:**
- **Roster ownership:** which teams can be formed, what the plan can use, which pulls fill gaps. The
  strongest personalisation.
- **Constellations:** owned constellation selects role overrides (`roles_at(c)`), for example 4★ characters
  at their owned constellation. Archetype tier and fit evidence do not change with owned constellation.
- **Investment** (level, talents, weapon, artifacts) gives `Member.investment`, which sets the role score at
  current investment. That produces "Today" (`rating = potential × build%`) and build priorities. The plan
  itself uses potential, meaning full build.
- **Artifacts:** substat quality in useful rolls (`artifacts.rate`), main stats, set completeness and ER, all
  in the review's rule checks.
- **Personal gcsim simulations** (`review.simulate` → `sim.TeamSim`) for the plan's teams: the user's actual
  artifacts, weapons, refinements, talents and levels on the community rotation. They measure:
  - the team's DPS against the community standard
  - damage share
  - each single change's gain: talent, level, standard artifacts, each owned weapon
  - the Energy Recharge cost
  These are tier A numbers in the review and to-do list.
- **Inventory** (scanner import): spare weapons are offered as swaps. With a basic import nothing claims a
  spare item is missing.

**"Unusually strong on this account because of a premium weapon, excellent artifacts and its best supports":
partially, and not in the plan.**
- **What can show it.** The review's personal simulation can show a team dealing more than the community
  standard, as the "Simulated: X% of standard" line. Owned supports matter fully, because only owned
  characters form teams.
- **What cannot.** Team potential, the plan and pull values always use community-standard builds, so premium
  gear never raises a team's potential or changes the plan. Refinements and constellations above standard
  affect only the review sims.

**Duplicate role coverage:**
- Only in pull values (sidegrade detection, section 9).
- Implicitly in the plan, since members cannot repeat.
- Team set duplication (two Viridescent holders) in the review.

**Existing teams.** `knowledge/my_teams.yaml` lists the user's played teams. The team report scores them first
and double-weights them in build priorities.

---

## 9. Pull value

**Before-and-after evaluation.** Yes, literally (`account.value_of(name, roster, base_plan, base_cands)`):

```python
new_roster = roster + [newcomer(name)]                       # C0, investment 1.0, roles_at(0) + faction roles
extra      = candidates(new_roster, must_include=name)        # only new teams containing them
merged     = dedupe(base_cands + extra) by member set         # keep higher risk-adjusted potential
new_plan   = best_plan(merged)                                # exact, weights [1, 1, 0.5, 0.25]
gain       = new_plan.value − base_plan.value                 # Plan.value = Σ w_i · potential_i (risk-adjusted)
```

**Kind assignment** (rules in `value_of`):
- **Joins an existing same-lead, same-archetype team** in the base plan: "fills a gap" if the potential
  improves by at least 15%, else "upgrade". Its explanation names who was replaced and their slot quality.
- **Joins a team whose lead is owned** but whose archetype was missing or weaker: "fills a gap" (no workable
  lineup before, or +15% or more), else "upgrade".
- **Leads its own team and is a primary carry** (Prydwen's best-rated category is DPS, or carry role quality
  ≥ 3 without a rating):
  - if one of the base plan's top two teams has another primary carry of the same element: "sidegrade",
    with gain × `duplicate_element_factor` (0.6). The explanation names the contested supports.
  - otherwise "new archetype".
- **Otherwise:** "new archetype" (enables an archetype).
- **Also reported:** reshuffled teams ("your X team becomes...") and replaced teams.

**Uncertainty** (`account.gain_estimate`):
- expected gain from expected values
- sd = √Σ(w·sd)² over teams that differ between the plans; shared teams cancel
- tier = the weakest among the new plan's changed teams
- confidence = P(gain > 0)
- The top two pulls are compared in words: "likely better" at P ≥ 0.8, otherwise "roughly equivalent".

**What it measures:**

| Question | Answer |
|---|---|
| Generic strength | Only through their team's archetype tier |
| Upgrade over an existing slot | Yes |
| New archetypes and viable teams | Yes |
| Best and second team improvements | Yes, weights 1 and 1 |
| Third and fourth | Weights 0.5 and 0.25 |
| Support competition | Yes, implicitly: the plan cannot reuse members |
| Redundancy | Only same-element carries in the top two |
| Synergy with owned characters | Yes, through owned-only teams and pair effects |
| Constellations and weapons | No: always C0, full build, standard gear; `weapon_note` only says whether the account owns a recommended weapon |
| Account-wide value | Yes, as the plan difference |

**Other outputs:**
- `best_carries_for(roster)` ranks unowned primary carries by the best team they would lead with owned
  supports.
- `viable_carries` lists owned carries whose best team reaches potential 45. Fewer than two produces a
  "Carry gap" warning.

---

## 10. Multi-team and account optimisation

**Non-overlapping plans.** Yes, exactly. `AccountModel.best_plan` is an exact branch-and-bound search over all
candidate assessments for up to four disjoint teams:
- objective: `Σ PLAN_WEIGHTS[k] × potential_k`, weights [1.0, 1.0, 0.5, 0.25], over teams sorted by potential
- bound: remaining weights × the best remaining candidates
- no cap on the candidate pool, after an earlier cap of 120 lost good plans

So Kazuha cannot appear twice. The engine finds the best disjoint combination, which may move Kazuha to the
team where he adds more total value.

**Content modes** (`gtc/profiles.py`, model.yaml `profiles.definitions`) reuse the same candidates with
different objectives:

| Mode | Team weights | Value weights |
|---|---|---|
| Abyss | [1, 1] | 0.5 single target + 0.5 AoE |
| Stygian | [1] | single target only |
| General | [1, 1, 0.5, 0.25] | 0.6 single target + 0.4 AoE |
| Theater | greedy disjoint competent teams | team value ≥ 30, up to 6 teams; score × (0.6 + 0.4 × elements covered / 7) |

**Behaviour issue.** Equal weights on teams one and two mean a small account may weaken its best team to field
a second. In one scenario, eight characters led the plan to move Aino out of Flins' measured best team, taking
it from 78 to 62, to build a 33-potential Bennett team. There is no lexicographic priority, protected core,
or "no second team worth building" outcome.

---

## 11. gcsim and the theory calculator

**Where gcsim is used:**
- **Community database:** all strength evidence.
- **Our own runs:**
  - attribution logs for 3,800 lineups (`synergy.build_database`, 14 threads, about 35 minutes)
  - personal team sims and variants
  - Energy Recharge reality mode
  - AoE runs
  - kit generation logs
  - calculator validation
- **Builds** are rewritten line by line (`sim.render`). Rotations are the community's.

**The theory calculator** (`gtc/tc/`, `python -m gtc theory`, and `review.theory_swaps`) answers "what if X
replaces Y":
1. **Profile** (`tc/profile.from_gcsim`): run the base team's community config. Read each character's
   stat snapshot and per-ability DPS (`source_dps`). Classify every damage source as `direct`,
   `lunar_charged_direct`, `lunar_charged_reaction` or `swirl` (`classify`, using kit `abilities`).
2. **Effects** (`tc/engine.Theory.effects`):
   - from kits: stat, react_bonus, base_bonus, res_shred, extra_hit
   - targets: party, active, self, others
   - optional uptime, constellation and Moonsign conditions
   - Plus `_sets` effects and the `_rules` Ascendant Gleam rule.
3. **Multiplier** (`Theory.multiplier`) per source:
   - direct: stat × (1 + DMG%) × RES × crit
   - Lunar direct: stat × (1 + base) × (1 + Lunar EM + react) × RES × crit
   - Lunar reaction: similar, without stat
   - swirl: (1 + transformative EM + react) × RES
4. **Swap** (`swap`): remove the leaving member's sources and effects, add the candidate's measured sources (from a
   gcsim run of the target team, `measured_candidate`) or kit hits, and rescale every remaining source by
   new multiplier ÷ old multiplier. `engine.application` checks that a Lunar team keeps its Hydro applier.
5. **Kits:**
   - hand-written in `knowledge/kits.yaml`: Flins, Ineffa, Columbina, Aino, Sucrose, Fischl, Furina, Xilonen
     and Lunar sets
   - hand-written in `kits_custom/`
   - generated in `kits_auto.yaml` (108 characters): buffs to teammates and RES shred from one median gcsim
     log each, with median value and uptime as a share of receivers' damage; set buffs the calculator
     already models are excluded
   - hand-written overrides generated, per character

**Supported:** direct damage with ATK/HP/DEF scaling, DMG%, crit, RES; Lunar-Charged direct and reaction; Swirl.

**Missing:**
- **Vaporize and Melt:** amplified hits are classified "direct"; EM and reaction bonuses don't affect them.
- **Hyperbloom, Bloom, Burgeon, Burning, Overloaded, Electro-Charged, Superconduct, Shatter.**
- **Aggravate and Spread.**
- **Any change in reaction frequency or aura availability after a swap,** other than the Lunar applier check.
- **Rotation changes:** the newcomer's own damage is measured, but teammates keep their old rotation.

**Why Lunar works and others don't.**
- **Lunar is fully modelled:** its formulas, contributor weights and bonus sources are written out, and the
  Lunar ecosystem has hand-written kits.
- **Other teams lose most of their value channels:**
  - For Vaporize and Melt, the main channel (the amplification multiplier and who supplies the aura) isn't
    modelled.
  - For Hyperbloom and other transformative reactions, damage depends on cores and triggers, also not
    modelled.
- **Result** (`tc/validate.run_broad`, 200 sampled one-member swaps): 37% within 10% of gcsim against a 90%
  target. The median error is 17% with generated kits and 15% without. A few predictions are off by up to
  ~40×, for example Bennett / Freminet / Furina / Xianyun with Furina → Citlali.

**Where it reaches users.** The original 5 Lunar check cases are fine. `review.theory_swaps` still feeds
teammate-swap findings into the review and the account report's to-do list. The account plan and pull values
do not use the calculator.

---

## 12. Benchmark and calibration

**Parameters** (`knowledge/model.yaml`, model 5.0, 32 values plus profiles):
- **account:** plan_weights, teams_per_template, viable_carry_potential 45, carry_category_min 3,
  duplicate_element_factor 0.6
- **report:** built_threshold, candidates_per_template, max_swap_gain 10, max_swap_distance 2
- **estimate:** risk 0.674
- **teams:** pair_thresholds, unproven_quality 2, single_team_cap 4
- **capabilities:** onfield_share 0.35, neighbour_base 100
- **validity:** min_lineups 8, apply_percentile 0.05, onfield_percentile 0.98, carry_element_share 0.95
- **synergy:** enable_share 0.5, context_base 10, shrink 2, unproven_share 0.5, structure_rules
- **pairmodel:** lambdas, min_pair_lineups
- **investment:** rarity values, roll_quality_share 0.6
- **artifacts:** tier weights, fallback weights, benchmark_rolls 30, flat_factor
- **aoe**, **kitgen**, **sim:** burst_wait_frames 300, iterations 300
- **review:** rule-finding gain estimates
- **profiles**

Separately, `scoring.yaml` holds investment weights, curves, floor, sustain penalty, execution penalty and
faction bonuses.

**Guards** (`tests/test_model.py`):
- An AST scan fails on module-level numeric constants in 19 scoring modules not read from `model.yaml`. Game
  facts are allowlisted; numbers inside function bodies are not scanned.
- Every model.yaml value must be read by its module.
- `benchmark_results.yaml` must hold a run whose fingerprint (a hash of model.yaml and scoring.yaml) matches
  the current version.

**Benchmark** (`knowledge/benchmark.yaml`, 46 cases, `gtc/benchmark.py`). Seven kinds, all pass/fail:

| Kind | Count | What it asks |
|---|---|---|
| best_team | 18 | Does a carry's or archetype's best team include or exclude members |
| no_team | 6 | Known-invalid teams must not form |
| plan_team | 4 | The plan's team for a lead or member includes certain members |
| pull_top | 7 | The top pull is in an accepted set, or within noise of the top (P < 0.8) |
| pull_kind | 2 | A pull's kind, for example Mavuika is a sidegrade for an Arlecchino account |
| better_lineup | 8 | One lineup's expected potential above another |
| carry_gap | 1 | Supports-only account: no viable carry, and a recommended carry built on three owned supports |

**What expected answers represent.** Each case is marked `source: scenario` (the user's own corrections) or
`consensus` (Claude's reading of community theorycrafting). Most are consensus and unreviewed.
- **Changed after the first run** (35 of 46 passed first time):
  - runner fixes
  - an over-specified Skirk case
  - two cases relaxed because gcsim data disagreed: Hu Tao / Yelan / Bennett / Kazuha simulates 75k against
    41k for double Hydro with Zhongli; Xiao / Furina / Bennett / Xianyun is above the Faruzan version
  - five pull cases narrowed to support-only pools
- **Close calls:**
  - `pull_furina_for_neuvillette`: Citlali +8.7, Nahida +8.6, Mavuika +8.5, Furina +8.4 before narrowing;
    it passes on the noise rule
  - `neuvillette_sidegrade_with_neuvillette_like`
  - `flins_aino_over_xingqiu`: 78 measured against 77 estimated

**Tuning** (`--tune`): every combination of `estimate.risk` {0.3, 0.674, 1.0},
`account.duplicate_element_factor` {0.4, 0.6, 0.8} and `teams.unproven_quality` {1, 2, 3} is run over all
cases, then scored leave-one-out. **The result: every one of 27 combinations scores 46/46, and the
cases reacting to the tuned values number zero.** Extreme values (risk 5, duplicate factor 0) also pass, and
only an extreme plan weighting flipped one case.

**Why.** Cases test orderings with large margins (measured meta teams against weak alternatives) or
categorical outcomes ("kind is sidegrade"), not magnitudes. Answers are robust to wide parameter ranges, so
the benchmark constrains logic but no parameter. There is one dataset, with no locked validation split.

**Other calibration that works:**
- the role-model calibration curve (per-archetype exponent and residuals, measured leave-one-out)
- uncertainty measured per tier with coverage checks
- the pair model's penalties chosen by 5-fold cross-validation
- validity percentiles chosen on recall

---

## 13. Testing

77 tests (`pytest`), about 25 to 35 seconds. Most run on the real downloaded data and the user's snapshot;
they skip when data is missing.

| File | Tests | What they validate |
|---|---|---|
| test_engine.py | 11 | Knowledge base valid; Freeze prefers an Anemo buffer in flex; investment lowers current but not potential; missing core slot reported; Lunar needs an enabler and rewards 2 Moonsign; the Abyss pair shares no characters; constellation talent bonus subtracted; Mona beats Xingqiu in Freeze; ideal Ayaka Freeze uses Furina; constellation unlocks roles; pruned search equals full enumeration |
| test_sources.py | 8 | Name matching across sources; standard filter; attribution blocked for pure carries; measured fit standard against standard; calibration learns the curve; Prydwen parsers; KQM example-team matching; expert tag |
| test_review.py | 7 | Stat-priority phrases; HoYoLAB artifact substats and rolls; KQM build sections; ER target reads team composition; config rewrite uses your build; team set checks; GOOD inventory import |
| test_synergy.py | 10 | Kazuha's DMG bonus and shred credited; EM does nothing for plain Cryo hits; pair table by carry; Omen, TTDS and quills credited to providers; Hyperbloom EM share and reaction bonus; Aggravate EM only raises added damage; Shapley additivity, hand check and self-buffs; gcsim alias resolution |
| test_theory.py | 6 | Formulas match gcsim constants; effect conditions; losing a buffer lowers the carry; losing the Hydro applier kills Lunar; source classification; build transplant |
| test_derive.py | 4 | Carry assignment; driver tag; families follow the carry; talent-text roles |
| test_phase1.py | 9 | Recall ≥ 90% and ≥ 70% of archetypes at 98%; Overloaded rejects Anemo and Freeze rejects Dendro; Neuvillette never in Mono Pyro; Hyperbloom not led by an Anemo flex; held-out structure prediction (top dealer ≥ 84%, type ≥ 72%); lineup value is the median; Skirk teammate rule; Raiden-damage team not an Anemo carry; only Moonsign carries lead Lunar |
| test_phase3.py | 5 | Probability and wording; combined tier; custom kit places an unsimulated character; tier sd order and coverage; audit has no unexplained findings |
| test_phase5.py | 6 | Basic import never claims a missing weapon; artifact weights and ER cap; AoE carries above single-target carries; narrow account wins Stygian and loses Theater; burst rewriter; hand-written kits override generated ones |
| test_pairmodel.py | 2 | Recovers a planted pair effect; held-out accuracy on synthetic data |
| test_model.py | 3 | No stray numbers; every parameter used; versioned benchmark run |
| test_scenarios.py | 6 | C6 Aino beats Xingqiu for Flins; Kazuha beats Sucrose for Ayaka Freeze; Columbina fills the gap; Mavuika sidegrade for Arlecchino; supports-only account needs a carry built on owned supports; plan teams share no characters |

Plus the 46 benchmark cases (`python -m gtc benchmark`), which are not part of pytest except the version guard.

**Coverage gaps:**
- **Labels and archetype identity:** no test checks that a label matches how a team plays.
- **Plan quality on small accounts:** no "keep the best team" test. The Aino scenario's plan-level assertion
  was removed.
- **Pull values:** no tests for gain magnitudes or ordering among close candidates. Seven top-pick cases and
  two kind cases.
- **Personal-build effects:** no test that premium gear or constellations change anything, because they don't
  outside the review.
- **End-to-end report snapshots:** no regression test of report output.
- **The calculator outside Lunar:** only measured in a script, not tested.
- **Performance:** no regression test.
- **Parameter sensitivity:** no test that parameters matter.

---

## 14. Known open problems

**A. Incorrect behaviour**
1. **The calculator's unreliable numbers reach the review** and the account to-do list through
   `review.theory_swaps` for non-Lunar teams. On 200 swaps, 37% are within 10%, with extreme outliers.
2. **Small-account plans can sacrifice the best team** for a weak second one (equal weights, no core
   protection).
3. **Misleading labels and leads:** Raiden / Kazuha / Xingqiu / Yaoyao as "Hyperbloom"; Chevreuse as lead
   of Overloaded. Labels are chosen by value across templates.
4. **Some valid teams are rejected:** recall below 98% for 7 of 32 archetypes. Structure prediction feeds
   validity, so a wrong prediction can reject a valid team.

**B. Missing capabilities**
1. **Personal builds don't affect potential, plan or pull values.** Only the review's simulations use them.
2. **Pull value ignores constellations and signature weapons** (always C0, standard gear).
3. **No quickswap or driver team types, no multi-reaction teams, no interruption resistance;** survivability
   is crude.
4. **Calculator reactions:** amplifying, transformative (except Swirl) and catalyze are missing.
5. **New characters** (Nefer, Sandrone, Vesna, Zibai, Lohen) cannot be evaluated without hand-written kits.
   Seven more are judged on role rules only.
6. **Stygian ignores Prydwen's per-boss ratings;** Theater ignores seasonal element rules.
7. **Resin efficiency was never built** (postponed by the user).

**C. Weak heuristics**
1. **Archetype ceilings** (0.8 to 1.0) and many slot value-formula weights are hand-set.
2. **Generated archetypes have generic slots,** and "carry" and "support" quality come from performance ratios
   and share cut points.
3. **Family naming follows a fixed partner priority.**
4. **Structure types use fixed thresholds.** The type is predicted right 75% of the time on held-out lineups,
   the top damage dealer 86%.
5. **Sustain is role quality × 20;** grouping is a minor slot term.
6. **AoE assumes three tightly grouped targets,** so ratios cluster near 3 and differences are modest.
7. **The ER cap uses the lowest listed requirement** (optimistic).
8. **The execution penalty is 3% per Prydwen "expert" level.**

**D. Data-quality problems**
1. **Community gcsim data has odd entries.** Hu Tao / Xingqiu / Yelan / Zhongli has a median of 41k from 3
   submissions, below non-standard Hu Tao teams.
2. **Many lineups have one or two submissions,** so tier B medians are noisy: 9.8% sd for one submission.
3. **Submitters aren't stored,** so one submitter can dominate a lineup. The raw field exists.
4. **Generated kits miss untriggered conditional buffs,** and Kazuha's element bonus appears only for the
   element his representative team swirled.
5. **Unused or text-only source fields:** KQM pros, cons, formulas and teammate notes are parsed but not used
   in decisions.
6. **The ER rewriter changes 5 of 80 community configs by more than 2%** (worst 10%).

**E. Architecture limitations**
1. **A template is generator, validator, label and power baseline at once.**
2. **"Lead" is identity, power baseline and a validity input at once.**
3. **`Assessment.potential` fuses power and risk** (expected − 0.674 sd).
4. **The planner has a single weighted-sum objective.**
5. **The unsimulated-lineup estimate chain is ordered by method, not by distance from simulated data.**
6. **No first-class reaction model;** reactions are spread across signatures, families, attribution constants
   and calculator kinds.
7. **Performance.** The account report takes about 48 s (79 s under the profiler):
   - the team search: 13.5 million search steps over 15,724 calls
   - re-running candidate generation per pull candidate
   - 282,000 distinct validity checks

**F. Testing and calibration limitations**
1. **The benchmark cannot discriminate parameters.** No case reacts to the tuned values, and absurd values
   pass.
2. **Benchmark answers are mostly unreviewed consensus,** and some were adjusted after the first run.
3. **No locked validation set, no ranking or gap scoring, no adversarial cases.**
4. **Few account-level tests,** and no report regression tests.

---

## 15. What works well (worth keeping)

- **Attribution** (`synergy.Attributor`): per-hit recomputation of every logged gcsim hit with the game formulas.
  - exact per-source reaction-bonus values read from gcsim's "[React Bonus]" records
  - aura and Dendro-core tracking for enablement
  - exact Shapley shares
  - weapon-holder and set-holder mapping, and gcsim alias resolution
  - hand checks in tests: Kazuha, Mona's Omen, TTDS, Shenhe's quills, Hyperbloom, Aggravate, Chevreuse
- **Evidence handling:** standard-versus-standard comparisons, medians per lineup, a normalizer from the top 3
  medians, families and attributed-lead pools.
- **The pair model:** 6.5% cross-validated error; it beats swap estimates on 29,400 identical held-out swaps
  and recovers known cores.
- **Measured uncertainty:** sd per evidence tier from held-out errors, with coverage checks; probabilities and
  "roughly equivalent" wording.
- **The exact plan search,** branch and bound with no pool cap, and the disjoint-team guarantee.
- **The before-and-after pull evaluation,** with kinds, explanations and contested supports.
- **Learned validity:** the known-nonsense list is rejected, with recall measured.
- **Personal gcsim simulations:** build-transplant rendering, ER top-up with reported deficit, single-change
  variants, the as-built ER mode.
- **Source ingestion and parsing,** with tests.
- **Parameter versioning:** one file, a fingerprint, the benchmark record, and the scan test.
- **The audit command,** which found the gcsim alias bug that had made Chevreuse measure 6% instead of 48%.

---

## 16. Representative examples

Engine output from model 5.0 on the user's real account and on hypothetical accounts.

**Example 1: the user's best team (good).**
- **Input:** the user's account.
- **Conclusion:** plan team 1 is Flins / Aino / Ineffa / Sucrose, potential 78 ± 5, tier B, today 51, build
  65%.
- **Why:** the lineup is simulated (111k median) against Flins' best lineup Columbina / Flins / Ineffa /
  Jahoda (143k): fit 78; Flins' archetype tier is 100.
- **Subsystems:** `evidence.measured_fit`, `archetype_tier`, `estimate`, `account.best_plan`.
- **Verdict:** good, and matches community consensus (Columbina > Aino).

**Example 2: a pull value (good).**
- **Input:** the user's account; pool of unowned characters.
- **Conclusion:** Columbina +22.2 ± 8.8 (B), 99% confidence, "fills a gap: joins your Flins team replacing
  Aino, potential 78 to 100".
- **Why:** with Columbina the plan's Flins team becomes the measured best Flins lineup, so the before-and-after
  plan difference is large and measured.
- **Subsystem:** `account.value_of`, `gain_estimate`.
- **Verdict:** good. The weakness: the value assumes C0 and ignores whether the user owns her weapon (only a
  note says so).

**Example 3: misleading label (flawed identity, plausible value).**
- **Input:** the user's account, plan team 3.
- **Conclusion:** "Raiden Shogun / Kaedehara Kazuha / Xingqiu / Yaoyao — Hyperbloom (Electro carry) (from
  gcsim data)", potential 48 ± 7 (C).
- **Why:**
  - the lineup fills `auto_hyperbloom_electro_carry`'s generic slots
  - validity passes (Yaoyao supplies Dendro)
  - the pair model predicts 67k, near Raiden / Kazuha / Xingqiu / Yelan's simulated 65k
  - the label comes from the template that scored highest
- **Subsystems:** `teams.fill_template`, `account.candidates` deduplication, `report.pair_model_fit`.
- **Verdict:** the value is plausible, but the identity is wrong: it is a Raiden on-field team with incidental
  Hyperbloom.

**Example 4: small-account plan (flawed).**
- **Input:** hypothetical roster Flins, Ineffa, Aino, Xingqiu, Sucrose, Kazuha, Bennett, Zhongli.
- **Conclusion:** Flins / Xingqiu / Ineffa / Sucrose (62, estimated) plus Bennett / Aino / Kazuha / Zhongli
  (33, Bennett-led Vaporize, role-model estimate). The engine's own best Flins team is Flins / Aino / Ineffa /
  Sucrose (78, measured).
- **Why:** `best_plan` maximises 1·62 + 1·33 = 95 over 78 + nothing. The Bennett team is valid because Bennett
  does carry some simulated Vaporize teams, Xianyun plunge for example.
- **Subsystem:** `account.best_plan`, `PLAN_WEIGHTS`.
- **Verdict:** flawed for the question "what is my best team". A human would keep Aino with Flins and call the
  leftovers not worth building.

**Example 5: attribution bug found by the audit (fixed; shows the measurement layer works).**
- **Input:** Razor / Fischl / Bennett / Chevreuse.
- **Before the fix:** Chevreuse measured 6% of team damage. Her RES shred key "chev-a1-electro" used gcsim's
  alias "chev", which the owner lookup didn't recognise, so the shred was credited to the attacker. 38 aliases
  were affected.
- **After:** 48% (RES shred 20%, DMG bonus 21%, ATK 7.5%). The plan's Razor team became the classic
  Razor / Fischl / Bennett / Chevreuse, 65 ± 5 (B).
- **Subsystems:** `synergy.Attributor._member` and `_char_aliases`; the database rebuild.
- **Verdict:** good after the fix. It shows a systemic risk: one parsing bug silently skewed many values.

---

## 17. File map

```text
Account ingestion:       gtc/importers/hoyolab.py, gtc/importers/good.py, gtc/snapshot.py, gtc/stats.py, scripts/test_hoyolab.py
Game data:               gtc/gamedata.py, knowledge/generated/game_*.json, reaction_level_base.json, gcsim_keys.json
Source ingestion:        gtc/sources/{fetch,gcsim_db,prydwen,kqm,names}.py -> data/sources/*.json
Knowledge model:         gtc/knowledge.py; knowledge/{characters,templates,scoring,sets,kits,my_teams}.yaml; knowledge/kits_custom/
Derived knowledge:       gtc/derive.py (roles, families, auto templates), gtc/capabilities.py, gtc/validity.py
Investment and artifacts: gtc/investment.py, gtc/artifacts.py
Team generation:         gtc/teams.py (fill_template, slot_candidates, score, team_is_valid, carry_mate_quality)
Validity:                gtc/validity.py, gtc/teams.py (team_is_valid, elements_fit), knowledge/generated/validity.yaml
Structure and lead:      gtc/synergy.py (classify_structure), gtc/capabilities.py (Neighbours, predict_structure), gtc/evidence.py (damage_lead)
Archetypes and labels:   knowledge/templates.yaml, knowledge/generated/auto_templates.yaml, gtc/derive.py (family_of), gtc/account.py (candidates dedupe)
Team strength:           gtc/evidence.py (Evidence, archetype_tier, measured_fit, lineup_fit, Calibration), gtc/report.py (assess, anchored_fit, pair_model_fit, synergy_fit, engine_factor, potential_estimate, team_power, Model)
Synergy and attribution: gtc/synergy.py (Attributor, build_database, SynergyTable, validate_swaps)
Pair model:              gtc/pairmodel.py
Uncertainty:             gtc/estimate.py
AoE and content modes:   gtc/aoe.py, gtc/profiles.py
Account plan and pulls:  gtc/account.py (AccountModel, best_plan, value_of, gain_estimate, best_carries_for, build_report)
Review and builds:       gtc/review.py (Guides, check_member, check_team_sets, teammate_swaps, theory_swaps, simulate, synergy_lines)
gcsim integration:       gtc/sim.py (find_config, render, run, TeamSim, guard_bursts, plan_variants)
Theory calculator:       gtc/tc/{__init__,profile,engine,formulas,cli,validate}.py, gtc/kitgen.py, knowledge/kits.yaml, knowledge/generated/kits_auto.yaml
Benchmark and parameters: gtc/benchmark.py, gtc/params.py, knowledge/{benchmark,benchmark_results,model}.yaml, tests/test_model.py
Audit:                   gtc/audit.py
CLI:                     gtc/__main__.py
Docs:                    docs/engine.md, docs/improvement-plan.md, docs/current-gaps.md, docs/reliability-plan.md
```

---

## 18. Final state summary

### A. What the engine actually "understands" today

- **Simulated damage:** how much damage about 3,800 community lineups do under standard assumptions, as
  medians, plus which members own it, who buffs whom and by which stat, and who enables which reactions. All
  measured hit by hit from gcsim logs with exact game formulas.
- **Character behaviour:** each character's average on-field time, application rates, reaction triggers and
  damage share, measured.
- **Pair effects:** which pairs perform better together than apart, from a fitted model with standard errors.
- **Uncertainty:** how wrong each kind of estimate tends to be, measured.
- **Exact optimisation:** the best disjoint four-team plan for a roster under a given scoring, and the
  before-and-after plan difference from adding a character.
- **Personal builds:** what the user's real gear does on community rotations (personal gcsim), including what
  low Energy Recharge costs.

### B. What it only approximates using heuristics

- **Archetype membership and labels** (slot fit, fixed partner priority, best-scoring template).
- **Team structure for unsimulated lineups** (neighbour-weighted shares and thresholds).
- **Strength of unsimulated lineups** (pair model, swap estimates, calibrated role scores).
- **Teammate quality** in generated archetypes (share cut points).
- **Validity thresholds** (learned percentiles), sustain, grouping, AoE (one layout).
- **Sidegrade and redundancy** (same-element primary carry in the top two, ×0.6).
- **Artifact quality weights,** execution penalty and investment score.

### C. What is still effectively hard-coded

- **The 13 hand-written templates,** their slot weights, value formulas and ceilings.
- **Hand-written roles** for 83 characters; the role vocabulary.
- **Family naming:** `PARTNER_PRIORITY`, `TEMPLATE_FOR`, `HELPERS`.
- **Structure thresholds** (0.55 / 0.25 / 0.50 / 0.40 / 0.25).
- **Plan weights** [1, 1, 0.5, 0.25]; the content-mode definitions.
- **Reaction constants** in attribution; the calculator's supported damage kinds.
- **Lunar ecosystem kits,** the Ascendant Gleam rule, set tables.
- **Benchmark expected answers.**

All tunable numbers are in model.yaml and scoring.yaml, but most are judgments that the benchmark cannot
currently constrain.

### D. What still depends on source text or LLM interpretation

- **No LLM.** Source text is interpreted only by regex and parsers:
  - Prydwen categories, tiers and tags become roles
  - Keqing Mains priorities and ER tables drive review rules
  - Project Amber talent text, matched by regex, gives healer, shield and shred roles
- **Keqing Mains example-team descriptions,** teammate notes, pros and cons are shown as text but never
  interpreted. Guide knowledge not expressible as tables (playstyle, conditional advice) is invisible to the
  engine.

### E. The five biggest blockers to behaving like a strong human theorycrafter

1. **Identity is entangled with value.** The engine doesn't separately decide what a team is (structure,
   damage source, reactions) before deciding how good it is. Labels, leads and some validity outcomes are side
   effects of template scoring, so explanations can misdescribe teams even when values are right.
2. **Account advice ignores the user's actual gear and constellations.** Plans and pull values use
   community-standard builds. Premium weapons, refinements, constellations and excellent artifacts appear only
   in the review's simulations, so the engine can't say "this character is unusually strong on your account".
3. **The planner's objective is naive for small accounts.** No protected core, no lexicographic priority for
   the main team, no "no second team worth building", so it can weaken the best team for marginal account
   value.
4. **Calibration has no teeth.** The benchmark can't distinguish parameter settings, has no locked validation
   set, and its answers are mostly unreviewed consensus. Most judgment parameters are untested.
5. **Unsimulated territory degrades quickly.** Two or more members from any simulation, estimates rest on a
   pair model (14% sd) or role rules (13 to 16 points). New characters need hand-written kits. The swap
   calculator, the only formula-level tool, models only direct, Lunar and Swirl damage.
