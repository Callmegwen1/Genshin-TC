# Backend contract for the website (model 6.4; implemented in the UI MVP)

This is a proposed, versioned JSON contract between the engine and a future UI. It maps each planned screen to
the engine function that already provides it, says how stable that function is, and lists the fields that are
still missing or should stay internal. Nothing here is built yet.

**Conventions:**
- Every response carries `model_version`.
- Power is on the engine's scale: 100 = the strongest simulated lineup's median DPS.
- Every number is an `Estimate`, never a bare float.
- Characters use the engine's display names, for example "Kaedehara Kazuha" and "Traveler (Anemo)".

## 1. Shared objects

```jsonc
// Estimate: every power, gain and ceiling
{
  "expected": 58.7,
  "sd": 5.8,
  "tier": "B",                          // A own sim, B community sims, C pair model near, D far, E kit / role rules, F none
  "evidence_state": "simulation",       // simulation | interpolation | kit-model | rules-only | none
  "route": "exact_community",           // exact_personal | exact_community | pair_model | provisional_kit | role_rules | none
  "quality": "good",                    // community evidence only: good | unconfirmed | mixed | poor
  "quality_reasons": [],
  "sd_parts": {"team": 0.10, "build": 0.40},   // relative; account numbers only
  "confidence": 0.95,                   // where a comparison is implied (pull gains)
  "coverage": "complete",               // mechanics coverage: complete | partial (cap 80%) | unknown (cap 65%)
  "notes": ["Provisional / kit-based: ..."]
}

// TeamResult: one four-character team
{
  "lineup": ["Neuvillette", "Furina", "Kaedehara Kazuha", "Zhongli"],
  "status": "well_supported",           // invalid | well_supported | unusual
  "status_reasons": [],                 // e.g. "Skirk has a Cryo and Hydro teammate in 95% of their simulated teams"
  "meta": Estimate, "current": Estimate, "ceiling": Estimate,
  "identity": {"label": "Neuvillette hypercarry · Freeze", "primary_actor": "Neuvillette",
               "mechanics": {"freeze": 1.0}, "structure": {"hypercarry": 0.92, "dual_carry": 0.08}},
  "aoe_ratio": 1.04,
  "strengths": ["..."], "problems": ["..."],      // see section 3: to be built from existing signals
  "substitutions": [{"out": "Zhongli", "in": "Kokomi", "comparison": "roughly_equal", "probability": 0.48}]
}

// PullResult: one unowned character added at C0
{
  "character": "Columbina",
  "standing": "Competitive / roughly equal",     // Clear recommendation | Competitive / roughly equal | Lower-value
  "gain": Estimate,                              // literal plan change, never discounted by a label
  "kind": "fills a gap",                         // no change | fills a gap | upgrade | new archetype | sidegrade | luxury
  "decomposition": {"plan_gain": 20.2, "best_team_gain": 20.2, "second_team_gain": 0.0,
                    "new_mechanics": [], "new_viable_teams": 3, "improved": ["Flins"], "displaced": ["Aino"],
                    "support_contention": [], "redundancy": {"role": 0.4, "mechanic": 0.0, "support_demand": 0.0,
                    "team": 0.75, "content_coverage": 0.0}, "redundancy_score": 0.23},
  "resulting_plan": [TeamResult],
  "explanation": ["Joins Flins / Columbina / Ineffa / Sucrose ...", "Plan change: best team +20."],
  "pros": ["..."], "cons": ["..."],              // see section 3
  "weapon_note": "You own a recommended weapon: The Widsith.",
  "provisional": false
}
```

## 2. Endpoints and how ready they are

| Screen | Request | Response | Engine source | Stable? | Missing |
|---|---|---|---|---|---|
| Account | snapshot import (HoYoLAB or scanner) | characters (level, talents, constellation, weapon, artifacts, stats), owned weapons, investment per character | `gtc.snapshot.Snapshot`, `report.analyze` (`an.roster`, `an.investments`) | yes: the snapshot schema has been stable since phase 1 | a public schema document; unowned characters list (`gamedata.load_characters()` minus owned) |
| Team Builder | `{lineup[4], account?}` | TeamResult | `AccountModel.assess_lineup` (any legal team, template or not); `account_power` (meta, current, ceiling, `sd_parts`); `evaluation.identity`, `.structure`, `.coverage`, `.validity` | yes (6.3/6.4) | `strengths` / `problems` and `substitutions` (section 3) |
| Recommended Teams: strongest, overlap allowed | `{account, n}` | `[TeamResult]` sorted by decision value | `AccountModel.candidates` | yes | none |
| Recommended Teams: account plan, no overlap | `{account, mode}` | `{teams: [TeamResult], value, ties: [...], abyss_tradeoffs, locked_core, note}` | `AccountModel.plan` / `best_plan`, `profiles.all_plans`, `near_alternatives` | yes | "why this unit is here" assignment explanations (section 3) |
| Account Improvements | `{account, pool?}` | `[PullResult]` with standing | `AccountModel.value_of` over the pool, `pull_groups` | yes, but gain sds are wide (the honest result: most pulls are competitive) | `pros` / `cons` |
| What-If Pull | `{account, character}` | PullResult, plus best resulting teams | `value_of` (`v.plan`, `v.decomposition`, `v.explanation`), `candidates_with` | yes | `pros` / `cons`; best resulting teams beyond the plan (one call to `candidates_with`) |

## 3. Fields to add before the UI (all derived from existing signals; no new modelling)

- **`strengths` / `problems` for a team.**
  - Problems: typicality findings, mechanics coverage gaps, community quality reasons, provisional notes, constellation-unknown flags, and an unaffordable Burst in current power.
  - Strengths: central mechanics with high centrality, measured buffs to the damage dealer, `well_supported` evidence.
  - Plain sentences, generated from the fields above.
- **`substitutions` for a manual team.** One-member swaps from the owned roster, compared with the team by
  `compare()`, keeping only "better" or "roughly equal" (as `near_alternatives` already does for plan teams).
- **Assignment explanation for plans.** For each premium support in the plan, the best alternative team it could
  join and how much the plan loses if it moves. The data exists in `decompose` (support contention) and
  `best_plan`.
- **`pros` / `cons` for a pull.**
  - Pros: best and second team gains, new mechanics, improved characters, new viable teams.
  - Cons: displaced characters, support contention, redundancy, weak evidence (tier E, coverage unknown, provisional).
  - Taken from `decomposition` and the estimate.

## 4. Internal only (do not expose)

- **Pair-model internals:** pair effects, functional-distance features, the capacity term.
- **Template internals:** template ids, slot fills, fit and archetype tier.
- **`potential`** (the decision value, expected − 0.674 × sd). It is the planner's objective, not a strength. Show
  `expected ± sd` instead.
- **Raw evidence:** `explanation` dicts, `uncertainty.json`, submitter ids, raw gcsim configs (personal-use
  source data).
- **The account's identifiers:** UID and cookies never leave the backend.

## 5. Versioning and stability rules

- `model_version` changes whenever numbers can change. A UI may cache per version.
- Enum values (`status`, `standing`, `kind`, `evidence_state`, `quality`, `tier`) are part of the contract. New
  values may be added; existing ones are not renamed.
- Ties are part of the contract. A response never implies an order inside "Competitive / roughly equal" or among
  `ties`.

## 6. As implemented in the UI MVP (gtc/app/server.py)

| Endpoint | Service function | Notes |
|---|---|---|
| `GET /api/status` | `AppService.status` | Loading stage, pull progress, timings |
| `GET /api/dashboard` | `dashboard` | Plan, strongest current team, Abyss pair, build improvement, pull group, warnings |
| `GET /api/account` | `get_account` | Summary and plan (no UID) |
| `GET /api/characters` | `get_characters` | Catalog, owned and unowned |
| `GET /api/characters/<name>` | `get_character` | Build, investment, build factor, problems, best teams; the pull card for unowned characters |
| `POST /api/team {"lineup", "substitutions"?}` | `evaluate_team` | `{legal, reasons, team: TeamResult + strengths/problems, substitutions, not_owned}` |
| `GET /api/teams?overlap=1` | `recommended_teams` | Strongest individual teams |
| `GET /api/teams?overlap=0` | `recommended_plan` | Plan teams, `allocation`, `ties`, `modes` |
| `GET /api/pulls` | `recommended_pulls` | `groups` keyed by standing, including "Provisional / insufficient evidence" |
| `GET /api/whatif/<name>` | `what_if` | Pull card, `plan_before`, `plan_after`, `teams_added` / `teams_removed`, decomposition fields |

**Changes from the proposal:**
- `TeamResult.status` adds `provisional`.
- `TeamResult.evidence` gains a `badge` (High / Medium / Low): a documented presentation mapping from tier and
  status.
- Pull standing adds the group "Provisional / insufficient evidence". No-change pulls are always Lower-value.
- `Estimate` fields are `{expected, sd, tier}`. Evidence fields live on the team (`evidence.state`, `quality`,
  `coverage`).
- Powers are rounded to whole numbers and gains to one decimal.
- **Allocation rows:** `unit`, `placed_on`, `alternative_team`, `swapped_with`, `team_a {now, with_unit}`,
  `team_b {now, without_unit}`, `gain_on_a`, `loss_on_b`, `net_account_effect`, `net_sd`, `comparison`,
  `probability_chosen_is_better`, `text`.
- **Substitution rows:** `out`, `in`, `kind` (upgrade | alternative | frees a contested support), `lineup`,
  `expected_change`, `probability_better`, `comparison`, `power`, `evidence_state`, `tier`, `provisional`,
  `frees_for`.

## Team `mechanics` (model 6.6, full team payloads only)

From `present.team_mechanics`: `central`, `supplied_functions` (function → members), `missing_functions`,
`synergies` (buff edges: from, to, effect, what, state), `conflicts` (kind, severity harm|caution, members, text,
resolved_by), `opportunity_losses` (member, kind, text), `conditions_satisfied`, `reaction_dependencies`,
`kit_coverage` (reviewed / compiled / derived / missing; compiled = LLM-extracted, checked, not human-reviewed). Representation only: no field here enters power. `recommendability`
reasons may now cite field-time, aura or opportunity-loss problems.
