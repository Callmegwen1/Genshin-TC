"""Command line entry point.

    python -m gtc gamedata  refresh the list of every character in the game
    python -m gtc sources   refresh gcsim, Prydwen and Keqing Mains data (cached for a week)
    python -m gtc synergy   measure who buffs whom, hit by hit, in every simulated lineup (about 40 minutes)
    python -m gtc derive    rebuild generated roles and archetypes for every character from the sources
    python -m gtc import    fetch your roster from HoYoLAB and save a snapshot
    python -m gtc inventory FILE  merge unequipped weapons and artifacts from a scanner GOOD export
    python -m gtc teams     analyze the latest snapshot and write a team report
    python -m gtc review    theorycrafter-style review of your teams with concrete changes
    python -m gtc account   best four teams, carry check, which characters would change the account, priorities
    python -m gtc compile packets|compile|validate [--names A,B]   offline kit compiler (gtc/kitcompile.py)
    python -m gtc theory --team "A,B,C,D" --replace B (--with X | --rank)   formula-based slot analysis
"""
from __future__ import annotations

from gtc import params

import argparse
from datetime import datetime

from gtc import REPORT_DIR, SNAPSHOT_DIR, knowledge
from gtc.snapshot import Snapshot, latest_snapshot


def cmd_import(_args) -> None:
    from gtc.importers.hoyolab import import_snapshot

    snap = import_snapshot()
    try:
        previous = Snapshot.load(latest_snapshot(SNAPSHOT_DIR))
    except FileNotFoundError:
        previous = None
    if previous and previous.has_inventory:
        # HoYoLAB cannot see the inventory, so carry over the last scanner import.
        snap.spare_weapons, snap.spare_artifacts, snap.has_inventory = previous.spare_weapons, previous.spare_artifacts, True
        print("Kept spare weapons and artifacts from your last scanner import. Rescan to refresh them.")
    path = SNAPSHOT_DIR / f"{datetime.now():%Y%m%d-%H%M%S}-hoyolab.json"
    snap.save(path)
    print(f"Saved {len(snap.characters)} characters to {path}")


def cmd_gamedata(_args) -> None:
    from gtc import gamedata

    print(f"Saved {gamedata.update()} characters to {gamedata.GAME_CHARACTERS}")


def cmd_sources(_args) -> None:
    from gtc import gamedata
    from gtc.sources import gcsim_db, kqm, prydwen

    names, game = gamedata.names(), gamedata.load_characters()
    kb = knowledge.load()
    try:
        owned = [c.key for c in Snapshot.load(latest_snapshot(SNAPSHOT_DIR)).characters]
    except FileNotFoundError:
        owned = []
    # Every character in the game, so the engine knows the whole game and not only this account.
    characters = sorted(set(game) | {k for k in list(kb.characters) + owned if k in game})

    print("gcsim database: downloading...")
    print(f"  {gcsim_db.download()} entries")
    kept, skipped = gcsim_db.normalize(names, game)
    print(f"  {kept} usable, {skipped} skipped (unknown names or no damage)")
    print(f"Prydwen: tier list and {len(characters)} character pages...")
    p = prydwen.update(characters, names)
    print(f"  tier list {p['version']} updated {p['tier_list_updated']}, {len(p['tiers'])} rated, {len(p['characters'])} guides")
    print(f"Keqing Mains: {len(characters)} quickguides...")
    print(f"  {len(kqm.update(characters, names))} guides found")


def cmd_inventory(args) -> None:
    from gtc import gamedata
    from gtc.importers import good

    snap = Snapshot.load(latest_snapshot(SNAPSHOT_DIR))
    snap = good.merge(snap, args.file, gamedata.names(), gamedata.load_weapons())
    path = SNAPSHOT_DIR / f"{datetime.now():%Y%m%d-%H%M%S}-hoyolab+good.json"
    snap.save(path)
    print(f"Added {len(snap.spare_weapons)} spare weapons and {len(snap.spare_artifacts)} spare artifacts. Saved {path}")


def cmd_synergy(_args) -> None:
    from gtc.synergy import build_database

    print(f"{build_database()} lineups attributed.")


def cmd_derive(_args) -> None:
    from gtc import capabilities, validity
    from gtc.derive import write
    from gtc.report import build_universe
    from gtc.synergy import load_database

    from gtc.synergy import refresh_values

    print(f"Lineup values refreshed (median of per-submitter medians): {refresh_values()} changed.")
    print(f"Measured capability profiles for {capabilities.build()} characters.")
    roles, templates = write(knowledge.load(generated=False))
    print(f"Generated role tags for {roles} characters and {templates} archetypes discovered in gcsim data.")
    kb = knowledge.load()
    universe = {m.key: m for m in build_universe(kb)}
    db = load_database()
    # Validity v2 (phase 9) learns no rejection rules; the carries' usual teammate elements feed typicality.
    carries = validity.learn_carries(db, universe)
    validity.set_carry_rules(carries)
    rules = {"_carries": carries}
    from gtc import pairmodel
    pm = pairmodel.build()
    cv = pm.validation["cross_validation"]["all"]
    print(f"Pair model fitted on {pm.validation['lineups']} lineups: {len(pm.pairs)} pair effects, "
          f"held-out median error {cv['median_error']:.1%}.")
    from gtc import estimate
    u = estimate.measure()
    print("Measured uncertainty (one sd, relative): one community simulation {:.1%}, pair model next to a simulation "
          "{:.1%}, further away {:.1%} (per lineup: functional distance, coverage {}); Prydwen team ratings {:.1f} fit "
          "points.".format(u["B"]["sd_single"], u["pair"]["near"]["sd"], u["pair"]["far"]["sd"],
                           u["distance"]["coverage_model"], u["prydwen"]["sd"]))
    validity.write(rules)
    print(f"Teammate elements learned for {len(carries)} carries (typicality); typicality widens extrapolated sd by "
          f"{u['typicality']['per_finding']:.0%} per finding.")


def cmd_benchmark(args) -> None:
    from gtc import benchmark

    cv = None
    if args.tune:
        cv = benchmark.tune()
        print(f"Tuning over {cv['cases']} cases: current values score {cv['current_score']:.0%}; "
              f"best in-sample {cv['best']} scores {cv['best_score']:.0%}; leave-one-out cross-validated {cv['cv_score']:.0%}. "
              f"Cases that react to the tuned values: {len(cv['sensitive_cases'])}"
              + (f" ({', '.join(cv['sensitive_cases'])})." if cv['sensitive_cases'] else "; the benchmark cannot tell them apart, so the defaults stand."))
    results = benchmark.run()
    print(benchmark.render(results))
    if args.record:
        benchmark.record(results, cv)
        print(f"Recorded for model {params.version()} ({params.fingerprint()}).")


def cmd_kits(_args) -> None:
    from gtc import kitgen

    print(f"Generated calculator kits for {kitgen.build()} characters: {kitgen.KITS_AUTO_PATH}")


def cmd_aoe(_args) -> None:
    from gtc import aoe

    out = aoe.build()
    print(f"Ran {len(out['lineups'])} lineups against three targets; AoE ratios for {len(out['characters'])} characters.")


def cmd_bench(args) -> None:
    import json as _json

    from gtc import bench

    if args.unlock:
        bench.unlock(args.reason or "")
        print(f"Locked set re-pinned at {bench.locked_hash()}; logged in {bench.LOCK_PATH}. Approval reset: the user must review it again.")
        return
    if args.approve:
        bench.approve()
        print("Locked set recorded as approved by the user.")
        return
    ok, msg = bench.check_lock()
    if not ok:
        print("WARNING:", msg)
    extra = {}
    if args.sweep:
        sw = bench.sweep()
        extra["sweep"] = sw
        print(_json.dumps(sw, indent=1))
    if args.tune:
        t = bench.tune()
        extra["tuning"] = t
        print(_json.dumps(t, indent=1))
    results = bench.run()
    print(bench.render(results, details=args.details))
    if args.record:
        bench.record(results, extra)
        print(f"Recorded for model {params.version()}.")


def cmd_golden(args) -> None:
    from gtc import golden

    if args.update:
        diffs = golden.update(args.reason or "")
        print(f"Golden outputs updated ({len(diffs)} changed values); logged in {golden.CHANGES}.")
        return
    diffs = golden.check()
    if diffs:
        print(chr(10).join(diffs[:400]))
        print(f"{len(diffs)} differences from the stored golden outputs.")
        raise SystemExit(1)
    print("Golden outputs unchanged.")


def cmd_audit(_args) -> None:
    from gtc import audit

    audits = audit.run()
    REPORT_DIR.mkdir(exist_ok=True)
    path = REPORT_DIR / f"audit-{datetime.now():%Y%m%d}.md"
    path.write_text(audit.render(audits), encoding="utf-8")
    flagged = [a for a in audits if a.findings]
    print(f"{len(audits)} characters checked, {len(flagged)} with findings. Written to {path}")


def cmd_teams(_args) -> None:
    from gtc.report import analyze, render

    snap = Snapshot.load(latest_snapshot(SNAPSHOT_DIR))
    text = render(analyze(snap, knowledge.load()))
    REPORT_DIR.mkdir(exist_ok=True)
    path = REPORT_DIR / f"teams-{datetime.now():%Y%m%d}.md"
    path.write_text(text, encoding="utf-8")
    print(text)
    print(f"\nReport written to {path}")


def cmd_web(args) -> None:
    from gtc.app.server import serve

    serve(port=args.port, open_browser=args.open)


def cmd_review(_args) -> None:
    from gtc.review import build_review, render

    snap = Snapshot.load(latest_snapshot(SNAPSHOT_DIR))
    text = render(build_review(snap, knowledge.load()))
    REPORT_DIR.mkdir(exist_ok=True)
    path = REPORT_DIR / f"review-{datetime.now():%Y%m%d}.md"
    path.write_text(text, encoding="utf-8")
    print(text)
    print(f"\nReview written to {path}")


def cmd_theory(args) -> None:
    from gtc.tc.cli import run

    team = [x.strip() for x in args.team.split(",")]
    text = run(team, args.replace, args.with_name, args.rank, args.mine, args.kit, args.rotation, not args.gcsim_rules)
    REPORT_DIR.mkdir(exist_ok=True)
    path = REPORT_DIR / f"theory-{datetime.now():%Y%m%d-%H%M%S}.md"
    path.write_text(text, encoding="utf-8")
    print(text)
    print(f"\nWritten to {path}")


def cmd_account(args) -> None:
    import time

    from gtc import timing
    from gtc.account import build_report

    timing.reset()
    began = time.perf_counter()
    snap = Snapshot.load(latest_snapshot(SNAPSHOT_DIR))
    if getattr(args, "calibrate", False):
        from gtc import account_power
        from gtc.account import AccountModel
        from gtc.report import analyze

        kb = knowledge.load()
        an = analyze(snap, kb)
        _, cands = AccountModel(an, kb).plan(an.roster)
        print(f"{account_power.collect_truth(an, cands)} lineups simulated with your builds.")
        r = account_power.calibrate(an, an.evidence)
        print(f"Build factors fitted on {r.get('teams')} teams: held-out median miss {r.get('loo_median_abs', 0):.0%} (log), "
              f"against {r.get('no_model_median_abs', 0):.0%} with no build model.")
    text = build_report(snap, knowledge.load())
    total = time.perf_counter() - began
    REPORT_DIR.mkdir(exist_ok=True)
    path = REPORT_DIR / f"account-{datetime.now():%Y%m%d}.md"
    path.write_text(text, encoding="utf-8")
    if getattr(args, "timings", False):
        print(timing.report())
        print(f"Total: {total:.1f} s")
        print(f"Written to {path}")
        return
    print(text)
    print("")
    print(f"Written to {path}")


def cmd_compile(args) -> None:
    """Offline kit compiler (gtc/kitcompile.py): packets, compile responses, validate against the reviewed kits."""
    from gtc import gamedata, kitcompile as C
    from gtc.kits import reviewed_kits

    names = [n.strip() for n in (args.names or "").split(",") if n.strip()]
    if args.action == "packets":
        if not names:
            names = sorted(set(gamedata.load_characters()) - set(reviewed_kits()))
        paths = C.write_packets(names)
        print(f"Wrote {len(paths)} packets to {C.PACKETS}. Responses go to {C.RESPONSES}.")
    elif args.action == "compile":
        if not names:
            names = sorted(C.slug_names_with_responses() - set(reviewed_kits()))
        ok = 0
        for n in names:
            r = C.compile_response(n)
            ok += r["ok"]
            mark = "OK " if r["ok"] else "REJ"
            print(f"{mark} {n}: {len(r['notes'])} note(s)" + ("" if r["ok"] else " | " + "; ".join(r["errors"][:3])))
        print(f"{ok} of {len(names)} compiled into {C.COMPILED_DIR}.")
    elif args.action == "validate":
        v = C.validate_reference(names or None)
        for n, r in v["rows"].items():
            print(n, "INVALID " + "; ".join(r["errors"][:2]) if not r["ok"] else r["score"])
        print("summary", v["summary"])
        ok, fails = C.accepted(v["summary"])
        print("ACCEPTED for population" if ok else "NOT accepted: " + "; ".join(fails))


def cmd_forward(args) -> None:
    """The forward model (experimental, not in production): blind benchmark, prerelease pipeline, swaps, shadow
    log and acceptance gates."""
    import json as _json

    team = [x.strip() for x in (args.team or "").split(",") if x.strip()]
    if args.action == "benchmark":
        from gtc.forward.benchmark import run

        out = run(profile=args.profile)
        print(_json.dumps(out["summary"], indent=1))
        for r in out["rows"]:
            print(f"  {r['family'][:32]:32} blind {r['blind_error']:+.3f}  replay {r['replay_error']:+.3f}  "
                  f"{r.get('confidence') or ''}")
    elif args.action == "pipeline":
        from gtc.forward.pipeline import analyse

        out = analyse(args.name, profile=args.profile, keep=args.keep)
        print(f"{args.name}: {out['status']['release_status']} {out['status']['kit_version']}, "
              f"{out['status']['community_simulations']} community simulations, {out['seconds']} s")
        for t in out["teams"]:
            print(f"  {t['dps']:>7,}  {' / '.join(t['lineup'])}  share {t['personal_share']:.0%}  {t['confidence']}")
        for s in out["swaps"]:
            print("\n".join("  " + x for x in s["lines"]))
    elif args.action == "refresh":
        from gtc.forward.pipeline import refresh

        print("rerun:", refresh() or "nothing changed")
    elif args.action == "swap":
        from gtc.forward.swap import swap

        out = swap(team, args.out, args.into, profile=args.profile)
        print("\n".join(out["lines"]))
    elif args.action == "shadow":
        from gtc.forward.shadow import run as shadow

        out = shadow(profile=args.profile, focus_only=args.focus_only)
        print({k: v for k, v in out.items() if k not in ("rows",)})
    elif args.action == "gates":
        from gtc.forward.gates import evaluate

        out = evaluate(args.profile)
        for g in out["gates"]:
            mark = "INFO" if g["pass"] is None else ("PASS" if g["pass"] else "FAIL")
            print(f"  {mark}  {g['gate']}. {g['name']}: {g['value']} (target {g['target']})")
        print(out["decision"])


def main() -> None:
    p = argparse.ArgumentParser(prog="gtc")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("gamedata").set_defaults(fn=cmd_gamedata)
    sub.add_parser("sources").set_defaults(fn=cmd_sources)
    sub.add_parser("synergy").set_defaults(fn=cmd_synergy)
    sub.add_parser("derive").set_defaults(fn=cmd_derive)
    sub.add_parser("import").set_defaults(fn=cmd_import)
    inv = sub.add_parser("inventory")
    inv.add_argument("file")
    inv.set_defaults(fn=cmd_inventory)
    sub.add_parser("teams").set_defaults(fn=cmd_teams)
    sub.add_parser("audit").set_defaults(fn=cmd_audit)
    sub.add_parser("aoe").set_defaults(fn=cmd_aoe)
    sub.add_parser("kits").set_defaults(fn=cmd_kits)
    cp = sub.add_parser("compile", help="offline kit compiler: packets | compile | validate")
    cp.add_argument("action", choices=["packets", "compile", "validate"])
    cp.add_argument("--names", default="", help="comma-separated characters (default: all applicable)")
    cp.set_defaults(fn=cmd_compile)
    bn = sub.add_parser("bench")
    bn.add_argument("--details", action="store_true")
    bn.add_argument("--sweep", action="store_true")
    bn.add_argument("--tune", action="store_true")
    bn.add_argument("--record", action="store_true")
    bn.add_argument("--unlock", action="store_true")
    bn.add_argument("--approve", action="store_true")
    bn.add_argument("--reason")
    bn.set_defaults(fn=cmd_bench)
    gd = sub.add_parser("golden")
    gd.add_argument("--check", action="store_true", help="compare with the stored outputs (default)")
    gd.add_argument("--update", action="store_true", help="store the current outputs; needs --reason")
    gd.add_argument("--reason", help="why the outputs changed, logged in tests/golden/CHANGES.md")
    gd.set_defaults(fn=cmd_golden)
    bm = sub.add_parser("benchmark")
    bm.add_argument("--record", action="store_true", help="record the score for the current model version")
    bm.add_argument("--tune", action="store_true", help="fit tunable parameters with leave-one-out cross-validation")
    bm.set_defaults(fn=cmd_benchmark)
    sub.add_parser("review").set_defaults(fn=cmd_review)
    web = sub.add_parser("web", help="local website at http://127.0.0.1:PORT")
    web.add_argument("--port", type=int, default=8765)
    web.add_argument("--open", action="store_true", help="open the browser")
    web.set_defaults(fn=cmd_web)
    acc = sub.add_parser("account")
    acc.add_argument("--timings", action="store_true", help="print stage timings and work counters instead of the report")
    acc.add_argument("--calibrate", action="store_true", help="simulate your builds on every simulated lineup you can field and refit the build factors (phase 11)")
    acc.set_defaults(fn=cmd_account)
    th = sub.add_parser("theory")
    th.add_argument("--team", required=True, help='four names, comma separated: "Flins,Ineffa,Columbina,Sucrose"')
    th.add_argument("--replace", required=True, help="the team member whose slot is being judged")
    th.add_argument("--with", dest="with_name", help="one candidate")
    th.add_argument("--rank", action="store_true", help="rank every candidate the engine knows")
    th.add_argument("--mine", action="store_true", help="start from your own builds instead of community builds")
    th.add_argument("--kit", help="extra kit YAML file, e.g. a new character")
    th.add_argument("--rotation", type=float, default=20.0, help="rotation length in seconds, for kit hits")
    th.add_argument("--gcsim-rules", action="store_true", help="only use effects gcsim implements")
    th.set_defaults(fn=cmd_theory)
    fw = sub.add_parser("forward", help="forward model (experimental): benchmark | pipeline | refresh | swap | shadow | gates")
    fw.add_argument("action", choices=["benchmark", "pipeline", "refresh", "swap", "shadow", "gates"])
    fw.add_argument("--profile", default="standard", choices=["standard", "neutral"])
    fw.add_argument("--name", help="pipeline: the character")
    fw.add_argument("--keep", type=int, default=6, help="pipeline: teams to theorycraft")
    fw.add_argument("--team", help='swap: four names, comma separated')
    fw.add_argument("--out", help="swap: the member leaving")
    fw.add_argument("--into", help="swap: the member joining")
    fw.add_argument("--focus-only", action="store_true", help="shadow: only the reference / focus lineups")
    fw.set_defaults(fn=cmd_forward)
    args = p.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
