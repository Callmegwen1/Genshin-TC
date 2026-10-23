# Account analysis: cloud dependency audit

Date: 2026-10-23. Local and read-only. Nothing was uploaded, and no project file was written.

**Method.** Three traced runs, with every write inside the project, every process launch and every network connection
blocked and recorded:
1. `shadow_account()` end to end from its warm cache (20.5 s; 1,252 files read; 0 writes, 0 processes, 0 network).
2. A fresh, uncached `theorycraft()` of Raiden Shogun / Sucrose / Xingqiu / Yaoyao, where Yaoyao has no kit file (89.3 s,
   19,218 DPS; 0 writes, 0 processes, 0 network).
3. `library.build()` for all 43 owned characters without kit files (12.8 s).

Snapshot field use was recorded by instrumenting the snapshot dataclasses during run 1.

## Verdict

Account analysis **cannot run in AWS yet**, for five reasons:

1. **It runs the legacy 6.7 service as its candidate generator.** `AppService` needs the account snapshot plus about
   30 MB of derived and third-party JSON (`data/sources/*.json`), and two of those files are derived from the user's
   own account.
2. **Most of the roster has no kit file.** 43 of 60 owned characters have none. Their action libraries come from
   cached gcsim samples in `data/sims`: 300 files, **511 MB**, for this roster alone.
3. **About 14 characters need gcsim to run.** Their samples are not cached, so the builder writes a config into
   `data/sims` and runs `data/tools/gcsim.exe`, a **Windows binary**. In a Linux container, with a read-only filesystem
   and no gcsim, those characters fail and fall back.
4. **It assumes a writable local disk.** It writes `data/forward/product_cache/`, `data/forward/failed_sources.json`
   and `reports/forward_shadow.*`, and `evaluate_many()` uses 12 local processes.
5. **The code is not committed.** `gtc/forward/product.py` and `gtc/forward/shadow_account.py` exist only in the
   working tree.

**Credentials are not involved.** The analysis path never loads the HoYoLAB importer or `python-dotenv`, and reads only
the `GTC_CACHE_OFFLINE` environment variable. Cookies live in `.env`, used only by `gtc/importers/hoyolab.py` at import
time. The snapshot file contains **no cookies or tokens**, but it does contain the account **UID**, which the analysis
never reads.

## Dependency inventory

| Name | Source | Size | Used by | Why needed | Class |
|---|---|---|---|---|---|
| Account snapshot `data/snapshots/<date>-hoyolab.json` | HoYoLAB importer (`python -m gtc import`) | 108 KB | Legacy `AppService` (roster, builds) | Who you own and how they're built | **RUNTIME_REQUIRED**, but only the sanitized fields below |
| Snapshot `uid`, character `id`, `source`, `taken_at` | Importer | bytes | Nothing in the analysis | Identifiers and metadata | **SHOULD_BE_REMOVED** from the cloud input |
| `.env` HoYoLAB cookies (`LTUID_V2`, `LTOKEN_V2`, `LTMID_V2`, `UID`) | User | < 1 KB | Importer only | Logging in to HoYoLAB | **Never in the cloud**: not in images, git, S3 or SQS |
| Amber game-data cache `data/sources/cache/amber/` | Project Amber API | 6.3 MB (371 files) | ForwardModel (stats, talent tables) | Game numbers | **RUNTIME_REQUIRED** (already in the image) |
| `knowledge/` kits, `kits_compiled`, `forward/`, `generated/`, YAML | Repository | ~1.5 MB | ForwardModel + legacy | Kits, rules, generated roles | **RUNTIME_REQUIRED** (already in the image) |
| `knowledge/my_teams.yaml` | User | < 1 KB | Legacy knowledge loader | "Teams I play" context | **OPTIONAL** (personal preference) |
| `data/sources/gcsim_teams.json` | Derived from the community gcsim database | 5.7 MB | Legacy + library sources | Community lineups and rotations | **RUNTIME_REQUIRED** (legacy and non-kit characters) |
| `data/sources/gcsim_db_raw.json` | Community gcsim database (downloaded) | 34 MB | Library builder (non-kit characters) | Rotation configs to measure | **RUNTIME_REQUIRED** for non-kit characters |
| `data/sources/synergy.json` | Own gcsim runs of ~3,800 lineups | 12.8 MB | Legacy + library sources | Who buffs whom | **RUNTIME_REQUIRED** (legacy) |
| `data/sources/prydwen.json`, `kqm.json` | Third-party sites (parsed) | 0.6 + 1.8 MB | Legacy | Guides and tier context | **LEGACY_ONLY**; personal-use third-party data |
| `data/sources/capabilities.json`, `pair_effects.json`, `family_lineups.json`, `aoe.json`, `uncertainty.json` | Derived (`python -m gtc derive`) | ~0.6 MB | Legacy | Model inputs | **LEGACY_ONLY** |
| `data/sources/account_truth.json`, `account_power.json` | Derived from **your account's** builds (personal gcsim runs, calibration) | 31 KB | Legacy | Build calibration | **LEGACY_ONLY**; private derived data (no UID inside) |
| Raw page caches `data/sources/cache/prydwen`, `cache/kqm` | Third-party HTML | 77 MB | Only when refreshing sources | Parse input | **BUILD_TIME_ONLY**, never in an image |
| gcsim samples `data/sims/*.sample.json` + configs | Local gcsim runs | 511 MB needed for this roster (14 GB total archive) | Library builder for non-kit characters | Measured action libraries | **RUNTIME_REQUIRED** today; **SHOULD_BE_REMOVED** from runtime (see blockers) |
| gcsim binary `data/tools/gcsim.exe` | gcsim v2.48.8 (Windows) | 36 MB | Library builder when a sample is missing | Generates missing samples | **SHOULD_BE_REMOVED** from runtime (Windows-only; runs at analysis time) |
| `data/forward/product_cache/<engine id>/*.json` | Written by `product.forward_team()` | 5 MB (635 teams) | Product layer | Avoid recomputing teams | **OPTIONAL** (replaced by the S3 result store in the cloud) |
| `data/forward/failed_sources.json` | Written by the library builder | KB | Library builder | Skip sources that failed before | **SHOULD_BE_REMOVED** as a mutable local file (move to the image or an object store) |
| `reports/forward_shadow.{json,md}` | Written by `shadow_account()` | 120 KB | Output | The report | **OPTIONAL** (becomes the S3 result) |
| SQLite or other databases | None found | | | | n/a |
| Environment variables | `GTC_CACHE_OFFLINE` only | | Fetch layer | Offline cache | **RUNTIME_REQUIRED** in the container |
| Local processes | `evaluate_many()` ProcessPool (12 workers) | | Product layer | Parallel team evaluation | Works on Linux; size the heavy worker for it |
| Uncommitted code | `gtc/forward/product.py`, `gtc/forward/shadow_account.py`, `tests/test_product.py` | 650 lines | Account path | The shadow product itself | **RUNTIME_REQUIRED**; must be committed first |

Approximate package for a cloud account analysis today:
- **Image additions:** ~55 MB of `data/sources/*.json` plus 511 MB of sims for this roster. Other rosters need other
  samples, up to the 14 GB archive.
- **Still missing:** a Linux gcsim build, for characters whose samples aren't cached.

## Snapshot fields actually consumed

Recorded during the full legacy + forward run:

| Object | Fields read | Fields present but never read |
|---|---|---|
| Snapshot | `characters`, `has_inventory`, `spare_weapons` | `uid`, `source`, `taken_at`, `spare_artifacts` |
| Character | `name`, `element`, `rarity`, `level`, `constellation`, `talents`, `weapon`, `artifacts`, `stats` | `id` |
| Talents | `normal`, `skill`, `burst`, `normal_bonus`, `skill_bonus`, `burst_bonus` | none |
| Weapon | `name`, `rarity`, `level`, `refinement`, `type`, `ascension`, `location` | none |
| Artifact | `level`, `rarity`, `substats` | `slot`, `set_name`, `main_stat`, `main_value`, `location` |

The ForwardModel side uses the `neutral` build profile, so it reads only the roster (who is owned). Builds matter only to
the legacy side.

**Safe account game data:** owned characters, levels, constellations, talents, weapons and refinements, artifact
stats, computed stats.

**Identifiers to drop:** `uid`, character `id`, `source`, `taken_at`. These are not needed and identify the account.

**Authentication material:** none in the snapshot. Cookies stay in `.env` on the user's machine, used only by the importer.

## Sanitized account input (v1)

Formal schema: `api/schemas/account_input.v1.json`. Boundary:

```
HoYoLAB importer (user's machine, has cookies)
  -> sanitized account input v1 (no cookies, no UID, no identifiers)
  -> theorycraft service (cloud)
```

The cloud service never receives HoYoLAB credentials, and never calls HoYoLAB.

| Field | Type | Notes |
|---|---|---|
| `schema_version` | `"gtc.account.v1"` | Constant |
| `roster[]` | list | One entry per owned character |
| `roster[].name` | string | Knowledge key (Traveler as `Traveler (<Element>)`) |
| `roster[].element`, `rarity`, `level`, `constellation` | string / int | |
| `roster[].talents` | `{normal, skill, burst, normal_bonus, skill_bonus, burst_bonus}` | Base levels + constellation bonuses |
| `roster[].weapon` | `{name, rarity, level, refinement, ascension, type}` | No `location`; it's implied by the owner |
| `roster[].artifacts[]` | `{slot, set_name, rarity, level, main_stat, main_value, substats[]}` | Optional; the legacy side reads `level`, `rarity`, `substats` |
| `roster[].stats` | object of GOOD stat keys | Optional; computed panel stats |
| `spare_weapons[]` | weapon objects | Optional; inventory, if a scanner export was merged |
| `profile` | `"neutral"` | Build profile for the ForwardModel |

Explicitly excluded: `uid`, character `id`, `source`, `taken_at`, `location` fields, and any HoYoLAB cookie or token.
A sanitizer belongs on the user's machine at export time, not in the cloud.

## What must change before ACCOUNT_ANALYSIS can be cloud-enabled

These are listed only; they're not designed or implemented in this phase.

1. Commit and test the shadow-product code.
2. Remove runtime gcsim. Either pre-build libraries for every character that lacks a kit file (a build-time step that
   writes kit-like library files into the image), or add kit files.
3. Package the legacy service's JSON inputs (~55 MB) as private build-time data, like the Amber cache, or replace the
   legacy shortlist with a forward-only candidate generator.
4. Replace local writes (`product_cache`, `failed_sources.json`, reports) with the job result store.
5. Accept the sanitized account input v1 instead of reading `data/snapshots/`.
6. Size the heavy worker for `evaluate_many()` (multiple vCPUs), with heartbeat-extended SQS visibility.
