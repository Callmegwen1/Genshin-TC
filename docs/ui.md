# Account Advisor: the local website (UI MVP)

## Run it

```
cd genshin-theorycraft
.venv\Scripts\python -m gtc web          # http://127.0.0.1:8765
.venv\Scripts\python -m gtc web --open   # also opens the browser
.venv\Scripts\python -m gtc web --port 9000
```

The server binds to 127.0.0.1 only. Your account data, UID and cookies never leave the machine, and the UID is
not part of any API response. The site uses the latest snapshot in `data/snapshots`; import a fresh one with
`python -m gtc import` first.

## Architecture

| Layer | Files | Role |
|---|---|---|
| Engine (frozen) | `gtc/*.py` | Team power, plans, pulls. Unchanged by the UI phase. |
| Presentation | `gtc/app/present.py` | UI-0: strengths and problems, substitutions, support-allocation explanations, pull pros and cons. Derived from engine outputs; never a score. |
| Service | `gtc/app/service.py` | UI-1: the stable application API (`AppService`). It caches the account analysis and computes pull values, the meta plan and allocation explanations in a background thread. |
| HTTP | `gtc/app/server.py` | A JSON API and the static files, standard library only (`http.server`). |
| Frontend | `web/` | Plain HTML, CSS and JavaScript modules with a hash router. No build step and no dependencies. |

**Why this stack.**
- The repository had no frontend. A local personal tool does not need a framework or a bundler.
- The standard-library server adds no packages to the Python environment.
- Plain JavaScript modules run in any current browser as they are.
- If the UI grows, the JSON contract stays the same, and a framework can replace `web/` without touching the backend.

## Pages

- **Dashboard (`#/`).** The account plan with ceilings and the comparison with the strongest plan in the game.
  Also: the strongest team on current builds, the Abyss pair, the highest-impact build improvement (the plan team
  with the largest gap between ceiling and current, and its least-invested member), the pull group, and evidence
  warnings.
- **Team Builder (`#/builder?team=a,b,c,d`).** Four slots; any characters, owned or not.
  - Ceiling, Current and Meta, each with its sd.
  - Evidence badges, always visible: confidence, Simulated / Interpolated / Provisional, Unusual, and community
    data quality.
  - How the team works (primary actor, structure, mechanics, damage shares, sustain), strengths and problems.
  - Substitutions from your roster (upgrade / roughly equal / frees a contested support), with a "Try" link.
- **Recommended Teams (`#/teams`).** The "Allow character overlap" toggle.
  - On: the strongest individual teams.
  - Off: the account plan, why each character sits where it does (counterfactual swaps with the net effect on the
    account and a tie flag), choices the evidence cannot separate, and plans by content mode.
- **Best Pulls (`#/pulls`).** Groups, not ranks: Clear recommendation, Competitive / roughly equal, Lower-value,
  Provisional / insufficient evidence. Each card shows the gain ± sd, the probability the gain is real, the kind,
  the evidence, the best team and the main reason.
- **What-If (`#/whatif/<name>`).** Pull value; plan before and after; best new team; pros and cons; what improves;
  what gets displaced; support contention; functional redundancy.
- **Characters (`#/characters`, `#/character/<name>`).** A filterable catalog, owned and unowned. Owned
  characters show build investment, the calibrated build factor, build problems, artifacts, stats and best teams.

## Live data and placeholders

Everything shown is live engine output on your real account. There are no mock values. Simplifications for the MVP:
- **Character page "useful upgrades"** are basic: level, talents, weapon level and missing artifacts. There is no
  artifact optimizer.
- **"CurrentPower contribution"** is shown as the character's calibrated build factor (own damage relative to a
  community-standard build), not as a per-team share.
- **Substitutions** are only offered for teams whose members you all own.

## Response times (your account, this machine)

| Call | Time |
|---|---|
| Server start to usable (analysis, plan, candidates) | 3.4 to 3.9 s |
| Background: 62 pull values / allocation explanations / meta plan | 17 to 19 s / 0.9 s / 0.9 s |
| Dashboard | 0.2 s |
| Team Builder evaluation with substitutions | 0.2 to 0.4 s |
| Recommended teams (either mode) | under 0.05 s |
| What-If (cached / computed on demand) | under 0.01 s / about 0.3 s |

## Product issues log

Fixed during the MVP:
1. **"Opens 138 new teams worth building"** counted every lineup above the replacement level, not distinct teams.
   It now says "Fits N lineups that clear the replacement level".
2. **A no-change pull (Wriothesley, +0.0) appeared as "competitive"**, because unknown mechanics coverage keeps
   `compare()` from ruling it out. No-change pulls now go to Lower-value.
3. **Substitutions now carry their evidence state.** Alyosha valued as Fischl, through his provisional kit, is
   badged Provisional.

Open, by user impact:
1. **Most pulls on this account fall in one competitive group** (gain sds of 7 to 28). That is honest, but it is
   less directive than a ranking. "Strongest evidence" is the tie-breaker the UI offers.
2. **The strongest team on current builds is a provisional team** (Iansan's kit). It is badged Low confidence /
   Provisional; the dashboard may want to prefer well-supported teams there.
3. **Allocation explanations include near-ties** (net +2.1, roughly equal). They are marked "roughly equal"; a later
   pass could hide ties by default.

## Mechanics panel (M10, model 6.7)

The Team Builder shows a **Mechanics** card under Strengths and Problems (`web/ui.js` `mechanicsPanel`, from the team
payload's `mechanics`):
- **Who does what:** each function and its members.
- **Missing functions:** soft ones in grey.
- **Reactions the kits need:** green when this team can trigger them.
- **Buffs that reach a damage dealer:** giver → receiver, with the kit effects.
- **Conflicts:** harm or caution, with what would resolve them.
- **Unused potential:** opportunity losses.
- **Kit badges:** green = reviewed, blue = compiled (LLM-extracted, review pending), amber = derived (measurements
  only).

The card says plainly that it never changes the power numbers. Substitution help text names what a direct swap
keeps, as read from the kits.
