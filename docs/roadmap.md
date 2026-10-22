# Roadmap

The approved sequence. It runs in order. Each phase ends with:
- pytest, the audit and both benchmark sets
- the original benchmark and the golden diff
- a version bump when behaviour changes

Details of finished phases are in implementation-log.md.

| Phase | Content | State |
|---|---|---|
| 0 | Theory guard | done (5.1) |
| 1 | Golden-output regression harness | done |
| 2 | Safe performance | done |
| 3 | Submitter-aware aggregation | done (5.2) |
| 4 | Benchmark v2: calibration and locked sets, sweeps, decision regret | done |
| 5 | TeamEvaluation; power decoupled from templates | done (5.3) |
| 5.3.1 | Correctness cleanup: swap advice, expected values, simulation precision, reshuffle wording, coverage guard, build heterogeneity | done (5.3.1) |
| 6 | Central reaction facts (`gtc/reactions.py`), capability exposure, lineup measurements, one synergy rebuild | done (5.4) |
| **6.5** | **Provisional Kits Lite** (inserted, see below) | done (5.5) |
| 7 | Structure v2 (probabilistic) | done (5.6) |
| 8 | Identity v2 (multi-label; labels from identity) | done (5.7) |
| 9 | Validity v2 and typicality | done (5.8) |
| 10 | Power and uncertainty separated; `compare()`; sd from functional distance; swap estimator deleted | done (5.9) |
| 11 | Account-specific power (meta, current, ceiling via a calibrated build factor) | done (6.0) |
| 12 | Planner v2 (content utilities, useful-team gate, value over replacement) and pull v2 (decomposed deltas) | done (6.1) |
| 13 | Provisional kits (full): schema v2 with provenance, evidence states, provisional supports, restrictions, stale audit | done (6.2) |
| 13.5 | Power reliability pass (inserted): validity split from generation, damage capacity, ML distance sd, no planner cliff, tie disclosure, sd parts | done (6.3) |
| 13.6 | Reliability validation (inserted): frozen out-of-sample gcsim set, community evidence quality, pull confidence groups, API contract | done (6.4) |
| M1–M5 | Mechanical reasoning layer: kit schema 3 with provenance, 17 reviewed reference kits, central mechanics, TeamMechanics reasoner, advisor use (docs/mechanics.md) | done (6.6) |
| 14 (M6–M8) | Offline LLM kit compiler validated blind against the reviewed reference kits; 103 compiled kits | done (6.7) |
| M9 | Re-test the advisor failure cases with full kit coverage | done (6.7) |
| M10 | Mechanics in the UI: Team Builder mechanics card, kit provenance badges | done (6.7) |
| Review | Human review of reviewed (17) and compiled (103) kits; schema gaps (Stellar reactions, Moonsign, DEF%/HP%) | open |
| FM-0–FM-10 | First-principles forward model (docs/forward-model.md): Amber data, house builds, gcsim-trace rotations, timeline effects, condition states, energy, field windows, per-event damage; validated against gcsim on the same rotation | done (experimental, not in production) |
| A–F | Kit state/resource language, reaction rates (gauge, ICD, envelope), frozen action libraries for 25 reference characters, rotation brain v2 (dependency graph, realisation), blind benchmark (blind vs replay), 12-team reference set | done (experimental) |
| G–O | Realistic builds, gear effects, prerelease pipeline, team needs, causal swaps, knowledge-based uncertainty, sim quality, shadow log, acceptance gates | done (experimental); gates 2, 3, 4, 8 fail |
| P–R | Production integration, derived pull value, build advisor | blocked by the acceptance gates |
| S | Content context | later |
| FM-6 / FM-9 / FM-11–FM-14 | Reaction tiers 2–4 beyond the trace, composed rotations (templates, search), route hierarchy change, prerelease support, advisor integration | next (awaiting go-ahead) |
| 15 | Final performance | planned |
| UI | UI MVP: presentation layer, application service, local website (engine frozen at 6.4) | done |

Not planned: adaptive rotations, generating new simulations, any LLM at run time.

## Phase 6.5: Provisional Kits Lite (inserted 2026-10-16, built in model 5.5)

**Why.** Recent characters have no community simulations and no kit numbers. Today these are Ifa, Lohen, Nefer,
Sandrone, Vesna and Zibai. They are reported as "cannot evaluate" until phase 13, which is many phases away.
Several are top-rated pulls, so the engine says nothing about exactly the characters people ask about.

**Depends on phase 6.** The provisional kit has to describe a character in the same normalised capability schema
that phase 6 establishes. That schema covers field share, damage share, application on and off field, reaction
triggers and ownership, buffs and their targets, shred, healing, shields and energy. A provisional character can
then enter structure, coverage and the pair model's neighbourhood like any other.

**Scope:**
- **Manual, structured kits only.** One YAML file per character under `knowledge/kits_provisional/`, written by
  hand from the official kit text. Each file holds:
  - element and weapon
  - expected role
  - capability values in the phase 6 schema, with ranges where unsure
  - buffs and shred with their targets and conditions
  - an analogue: a simulated character whose measured profile is closest
  - sources
- **Valuation through the analogue.**
  - Team power: the analogue's measured effects, adjusted by the kit's declared differences.
  - Evidence: a new route, `provisional_kit`, at tier E or worse.
  - Uncertainty: a wide sd, at least the pair model's far error and larger when ranges are wide.
  - Coverage: always "unknown", so the confidence cap applies.
- **Plainly provisional in every report.** "Provisional estimate from the kit, no simulations yet", with the
  analogue named. Never presented beside measured numbers as if comparable without that label.
- **Removed automatically.** When community simulations for the character appear, the measured routes take over
  and the provisional kit is ignored for valuation (and flagged for deletion).

**Not in 6.5:**
- No LLM compiler (that is phase 14).
- No generated rotations.
- No calculator use.
- No automatic kit parsing.

**Acceptance:**
1. Each provisional character gets a value with route `provisional_kit`, tier E or worse, coverage "unknown", and
   confidence at or below the unknown cap.
2. Back-test: build provisional kits for 3 characters that do have simulations, hiding their data. Report how far
   the provisional values land from the measured ones; the sd must cover the misses.
3. Golden diff: only pulls and candidates involving provisional characters change.
