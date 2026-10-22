# Mechanical reasoning layer (phases M1 to M5)

Pipeline: game facts → structured kits → mechanical reasoning → evidence → power → account optimisation → advisor.

The mechanics layer sits between kits and the advisor. **It never produces or multiplies power.** It is
representation: what each kit supplies, what the team lacks, and which kits help or work against each other. The
advisor reads it to decide what to recommend and how to explain it. Power still comes from the evidence (simulations
and the pair model).

| Module | Role |
|---|---|
| `gtc/kits.py` | Schema 3, validation, reviewed and derived kits |
| `knowledge/kits/*.yaml` | Reviewed kits, one per character (17 today) |
| `gtc/mechanics.py` | Universal mechanics (re-exports `gtc/reactions.py` and `gtc/tc/formulas.py`, and adds the concepts the reasoner needs) |
| `gtc/team_mechanics.py` | `analyse(lineup, central)` returns a `TeamMechanics` |
| `gtc/kit_conditions.py` | Composition conditions, now read from reviewed kits (with `each` semantics) and falling back to the legacy file |
| `gtc/advisor.py` | Recommendability and substitutions read `TeamMechanics` |

## Kit schema (M1)

The full field list is in the `gtc/kits.py` docstring.

- **Behaviour:** field-time demand, on-field damage, off-field persistence, driver, damage ownership, damage element
  and types, application per element and mode, energy, sustain.
- **Scaling.**
- **Effects:** kind, target, affected elements, damage types and reactions, amount, duration, stacking, conditions,
  source.
- **Conditions:** party element count, only these elements (with at least one of each), forbidden elements, required
  reaction, aura, teammate role, reaction trigger count, character state, Hexerei count.
- **Reaction relationships:** owns, enables, requires, aura supplied, aura consumed.
- **Sources and provenance per field:** source, span, confidence, method, reviewed.

"unknown" is a valid value everywhere. `validate()` checks vocabulary, types and provenance. Every character in the
game data has a valid kit:

- **Reviewed:** hand-written from the official kit text. Behaviour judgments carry a "community" citation and medium
  confidence.
- **Derived:** built from the measured capability profile and placement roles. Effects are empty because they cannot
  be derived, so buff reasoning about such a member is "unknown", never "absent".

`tests/test_mechanics.py` cross-checks each reviewed kit's behaviour against the measured profile:
- `on_field_damage` must match exactly;
- field time and damage ownership must be within one level.

## TeamMechanics (M4)

| Field | Meaning |
|---|---|
| `central` | The engine identity's central mechanics, or, without one, reactions that the applied elements produce and that involve a damage dealer's element |
| `supplied_functions` | Function → members: on-field damage, off-field damage, driver, sustain, swirl support, grouping, battery, buffs, debuffs, `<element>` application |
| `missing_functions` | A damage dealer, someone to stay on field, a central mechanic's element; "sustain (soft)" |
| `synergies` | Buff edges where the giver's effect matches the receiver's damage by target, element and type, with effect conditions evaluated. Enabler edges: the auras central mechanics need |
| `conflicts` | **Harm:** two on-field damage dealers (field time); a strongly applied element that removes a central mechanic's auras; a broken `only` condition. **Caution:** a buffer whose buffs reach no damage dealer (a buff on the active character counts if it can snapshot) |
| `conditions_satisfied` / `conditions_failed` | From `kit_conditions.status` |
| `reaction_dependencies` | The kit's `reactions.requires` and the `reaction_required` conditions on its effects, each with whether this lineup can produce it |
| `opportunity_losses` | **Not harm:** a `count` condition below full; an effect whose condition this lineup cannot meet; a shred or buff that reaches only its giver's own damage when the team's other damage is outside it |
| `kit_coverage` | Which members are reviewed, derived or missing |

## Advisor use (M5)

**Recommendability.** Each mechanical problem demotes the team to experimental or adds a caution:

| Problem | Effect on recommendability |
|---|---|
| Broken `only` condition | Always experimental |
| Field-time conflict | Experimental unless this exact team was simulated, then a caution |
| Aura-removal harm | Experimental unless this exact team was simulated, then a caution |
| `count` condition below full | Experimental unless exactly simulated, then a caution. Worded as an opportunity loss: the pair model discounts it with one coefficient per support, which is too coarse to vouch for an unsimulated team |
| Wasted buffs | Caution only |

**Substitutions.** A swap is direct only when the new team keeps all of the following:

- the carry;
- the central mechanics' elements;
- every critical function only the leaving member supplied (on-field damage, central-element application, swirl
  support, sustain);
- no new mechanical harm;
- no newly unmet condition.

The role-based `_functions` heuristic is deleted.

**Explanations.** `team_insights` adds:

- a mechanics strength: who buffs the main damage dealer, and through which kit effects;
- mechanics problems: conflicts and opportunity losses.

The full team payload carries `mechanics`, a `present.team_mechanics` summary.

## Not in scope

- A combat simulator.
- Rotation timing.
- Numeric buff uptime.

Field time is a coarse demand level, not a schedule. Buff amounts are recorded but never summed into power.

## Offline kit compiler (M6 to M8)

`gtc/kitcompile.py`, `python -m gtc compile packets|compile|validate`. The LLM runs at build time only. Nothing in
the engine calls it.

1. **Packets** (`data/compiler/packets/`). Each holds:
   - the extraction rules and the schema;
   - two reviewed example kits, never the target's;
   - the official kit text from the Amber cache: talents and passives, Normal Attack text up to 2500 characters, and
     skill and Burst scaling tables at talent level 10, including Energy Cost;
   - the engine's measured profile.
2. **Fill.** Any LLM writes `data/compiler/responses/<slug>.yaml`.
   - Used here: fresh subagents that read only their packets.
   - Alternative: `fill_with_api` with ANTHROPIC_API_KEY.
3. **Compile.** Each response must pass these checks:
   - **schema validation;**
   - **grounding:** an effect must name a talent from the text, and a numeric amount must appear in the text.
     Otherwise the effect is dropped and listed;
   - **measurement guard:** on_field_damage, field time and damage ownership beyond one level, and application are
     replaced by the measured values. Measured function-critical roles are kept;
   - **generic normalisation:** element-type counts, and free text in element lists;
   - **provenance:** forced to `llm_extracted`, `reviewed: pending`, confidence at most medium.

   Output goes to `knowledge/kits_compiled/`, with every note in the file header.
4. **Validate.** The 17 reviewed kits are compiled blind and scored field by field (`score`, `ACCEPT`). Population
   runs only after the gate passes.

**Kit priority:** reviewed, then compiled, then derived. Compiled kits feed the reasoner (functions, synergies,
conflicts and explanations). **They never feed power:** composition conditions for the pair model come only from
reviewed kits.
