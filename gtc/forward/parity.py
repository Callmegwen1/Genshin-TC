"""Execution parity (diagnosis round): given the SAME ordered actions, do the forward model and gcsim agree on what
happens, when, and whether the rotation is executable?

A generated rotation is played in gcsim action for action (gtc/forward/decompose.to_gcsim: explicit waits for our
idle time, the kit's hold variants). gcsim's sample log is read back event by event:
    executed <action>                the action's start frame
    <state> started (hitlag log)     CanQueueAfter: the earliest next action, per next-action type (input lock)
    hitlag applied to char           frozen frames that extend the acting character's animation
    could not execute <a>; not ready one entry per frame gcsim waited on that action
    executed swap / swap_cd_post     swap animation and the swap cooldown
    executed wait                    explicit waits (our idle time)
    particle / adding energy / draining energy   the energy ledger (element, count, collector on/off field, ER)
For every action after the first, both sides' gap since the previous action is split into:
    lock         input/action lock of the previous action (ours: the kit duration; gcsim: CanQueueAfter)
    swap         character change (ours: the swap delay; gcsim: swap animation + waiting for the swap cooldown)
    cooldown     waiting for a Skill / Burst cooldown
    energy       waiting for Burst energy
    hitlag       frozen frames (gcsim only; the forward model has no hitlag)
    wait         explicit wait (our idle, reproduced as wait() in gcsim)
    unknown      what the categories do not explain
The per-action delta is gcsim's gap minus ours; the cumulative delta is its running sum. The first meaningful
divergence is the first action where the cumulative delta passes 0.5 s, with its dominant category.
Energy: each Burst's availability time (when its owner's energy first reaches the cost) on both sides, and a
ledger of every particle and flat gain. No energy source is inferred: only what each side logs.
"""
from __future__ import annotations

from collections import defaultdict

FPS = 60.0
CATEGORIES = ("lock", "swap", "cooldown", "energy", "stamina", "hitlag", "wait", "unknown")


def _gcsim_events(sample: dict, keys: dict[str, str]) -> dict:
    import re

    inv = {v: k for k, v in keys.items()}
    inv.update({re.sub(r"[^a-z0-9]", "", k.lower()): k for k in keys})      # gcsim logs full keys (kamisatoayaka)
    order = [inv.get(c.get("name"), c.get("name")) for c in sample.get("character_details") or []]
    logs = sample.get("logs") or []
    out = {"actions": [], "blocked": [], "hitlag": [], "starts": [], "energy": [], "swaps": [], "waits": [],
           "order": order}
    for l in logs:
        ev, msg, fr = l.get("event"), l.get("msg") or "", l.get("frame", 0)
        ci = l.get("char_index", -1)
        who = order[ci] if 0 <= ci < len(order) else None
        lg = l.get("logs") or {}
        if ev == "action" and msg.startswith("executed "):
            a = msg[9:]
            if a == "swap":
                out["swaps"].append({"f": fr, "to": inv.get(lg.get("target"), lg.get("target"))})
            elif a == "wait":
                out["waits"].append({"f": fr, "frames": lg.get("f", 0)})
            else:
                out["actions"].append({"f": fr, "char": who, "action": lg.get("action", a)})
        elif ev == "sim" and msg.startswith("could not execute"):
            out["blocked"].append({"f": fr, "action": msg.split()[3].rstrip(";"), "char": who})
        elif ev == "hitlag" and msg.endswith("started"):
            out["starts"].append({"f": fr, "char": who, "state": lg.get("State"), "queue": {k: v for k, v in lg.items()
                                                                                       if isinstance(v, (int, float))}})
        elif ev == "hitlag" and msg.startswith("hitlag applied to char"):
            out["hitlag"].append({"f": fr, "char": who, "frames": lg.get("frozen_frames", 0)})
        elif ev == "energy" and msg in ("particle", "adding energy", "draining energy"):
            out["energy"].append({"f": fr, "char": who, "kind": {"particle": "particle", "adding energy": "flat",
                                                                 "draining energy": "drain"}[msg],
                                  "ele": lg.get("ele"), "count": lg.get("count"), "active": lg.get("is_active"),
                                  "er": lg.get("ER"), "amount": lg.get("amt", lg.get("rec'd")),
                                  "pre": lg.get("pre_recovery", lg.get("pre_drain")),
                                  "post": lg.get("post_recovery", lg.get("post_drain")), "max": lg.get("max_energy"),
                                  "source": lg.get("source")})
    return out


def _gc_energy_at(energy: list, who: str, frame: float) -> float | None:
    v = None
    for e in energy:
        if e["f"] > frame:
            break
        if e["char"] == who and e.get("post") is not None:
            v = e["post"]
    return v


def _gc_max(energy: list, who: str) -> float | None:
    return next((e["max"] for e in energy if e["char"] == who and e.get("max")), None)


def compare(rot, builds: dict, sample: dict | None = None) -> dict:
    """Action-by-action timing comparison of a generated rotation and gcsim playing the same actions."""
    from gtc.forward.decompose import char_keys, to_gcsim
    from gtc.forward.generator import SWAP_DELAY
    from gtc.synergy import run_sample

    keys = char_keys(rot.lineup)
    if sample is None:
        sample = run_sample(to_gcsim(rot, builds, keys), keep=True)
    g = _gcsim_events(sample, keys)
    ours = [a for a in rot.actions]
    theirs = g["actions"]
    n = min(len(ours), len(theirs))
    rows, cum, first = [], 0.0, None
    totals = {"forward": defaultdict(float), "gcsim": defaultdict(float), "delta": defaultdict(float)}
    starts = sorted(g["starts"], key=lambda s: s["f"])
    for i in range(1, n):
        a0, a1 = ours[i - 1], ours[i]
        f0, f1 = theirs[i - 1]["f"], theirs[i]["f"]
        gc_gap = (f1 - f0) / FPS
        our_gap = a1.t - a0.t
        # ours
        o = defaultdict(float)
        if a1.char != a0.char:
            o["swap"] = SWAP_DELAY
        idle = max(0.0, a1.t - (a0.end or a0.t) - o["swap"]) if getattr(a0, "own_duration", False) or not a0.end else             max(0.0, a1.t - (a0.end or a0.t) - o["swap"])         # generator idle (emitted to gcsim as wait())
        o["wait"] = idle
        o["lock"] = max(0.0, our_gap - o["swap"] - idle)            # measured transition lock, hitlag included
        # gcsim
        c = defaultdict(float)
        st = next((s for s in reversed(starts) if s["f"] <= f0 + 1 and s["char"] == a0.char and s["state"] != "swap"), None)
        nxt = "swap" if a1.char != a0.char else a1.action
        if any(f0 <= w["f"] < f1 for w in g["waits"]):
            nxt = "wait"                       # the previous action is followed by an explicit wait first
        if st:
            c["lock"] = st["queue"].get(nxt, st["queue"].get("CanQueueAfter", 0)) / FPS
        c["hitlag"] = sum(h["frames"] for h in g["hitlag"] if f0 <= h["f"] < f1 and h["char"] == a0.char) / FPS
        c["wait"] = sum(w["frames"] for w in g["waits"] if f0 <= w["f"] < f1) / FPS
        if a1.char != a0.char:
            c["swap"] = 12 / FPS + sum(1 for b in g["blocked"] if f0 <= b["f"] < f1 and b["action"] == "swap") / FPS
        blocked = [b for b in g["blocked"] if f0 <= b["f"] < f1 and b["action"] == a1.action]
        if blocked:
            e_now = _gc_energy_at(g["energy"], a1.char, blocked[0]["f"])
            mx = _gc_max(g["energy"], a1.char)
            if a1.action == "burst" and e_now is not None and mx and e_now < mx - 1e-6:
                c["energy"] = len(blocked) / FPS
            elif a1.action in ("charge", "dash"):
                c["stamina"] = len(blocked) / FPS      # a Charged Attack or dash blocked: not enough stamina
            else:
                c["cooldown"] = len(blocked) / FPS     # Skill / Burst cooldown, dash lockout
        c["unknown"] = gc_gap - sum(v for k, v in c.items() if k != "unknown")
        o["unknown"] = 0.0
        delta = gc_gap - our_gap
        cum += delta
        d = {k: round(c[k] - o[k], 3) for k in CATEGORIES}
        d["lock+hitlag"] = round(c["lock"] + c["hitlag"] - o["lock"], 3)    # the forward model folds hitlag into lock
        for k in CATEGORIES:
            totals["forward"][k] += o[k]
            totals["gcsim"][k] += c[k]
            totals["delta"][k] += c[k] - o[k]
        totals["delta"]["lock+hitlag"] += d["lock+hitlag"]
        row = {"i": i, "char": a1.char, "action": a1.action, "t_forward": round(a1.t, 2), "t_gcsim": round(f1 / FPS, 2),
               "delta": round(delta, 3), "cumulative": round(cum, 3), "by_category": d}
        rows.append(row)
        if first is None and abs(cum) > 0.5:
            main = max((k for k in d if k not in ("lock", "hitlag")), key=lambda k: abs(d[k]))
            first = {**row, "dominant": main}
    ledger = energy_ledger(rot, g)
    pred, act = rot.duration, (theirs[n - 1]["f"] / FPS if n else 0.0)
    unexplained = totals["gcsim"]["unknown"]
    return {"actions": n, "matched": len(ours) == len(theirs),
            "predicted_duration": round(pred, 2), "gcsim_duration": round(act, 2),
            "duration_error": round(act / pred - 1, 3) if pred else None,
            "first_divergence": first, "totals": {k: {c: round(v, 2) for c, v in d.items()} for k, d in totals.items()},
            "explicit_waits": round(totals["gcsim"]["wait"], 2), "unexplained": round(unexplained, 2),
            "bursts": ledger["bursts"], "ledger": ledger, "rows": rows}


def _availability(events: list[tuple[float, float]], bursts: list[float], cost: float, start: float) -> list[dict]:
    """For each Burst: when the energy first reached the cost before it, and the margin at the cast."""
    out, energy, i = [], start, 0
    events = sorted(events)
    for k, bt in enumerate(bursts):
        avail = 0.0 if k == 0 and energy >= cost - 1e-6 else None
        while i < len(events) and events[i][0] <= bt:
            energy = min(cost, energy + events[i][1])
            if avail is None and energy >= cost - 1e-6:
                avail = events[i][0]
            i += 1
        out.append({"burst_t": round(bt, 2), "available_t": None if avail is None else round(avail, 2),
                    "margin": round(energy - cost, 2)})
        energy = 0.0
    return out


def _capped(events: list, bursts: list, cost: float) -> float:
    """Energy actually gained (overflow above the cost is lost), replaying the bar from full with Burst resets."""
    energy, got, i = cost, 0.0, 0
    events = sorted(events)
    for bt in list(bursts) + [1e18]:
        while i < len(events) and events[i][0] <= bt:
            add = min(events[i][1], max(0.0, cost - energy))
            got += add
            energy += add
            i += 1
        energy = 0.0
    return got


def energy_ledger(rot, g: dict) -> dict:
    """Both sides' energy events, and each Burst's availability."""
    from gtc.forward import data as D

    ours = [{"t": round(e["t"], 2), "collector": e["char"], "kind": e.get("kind"), "source": e.get("source"),
             "element": e.get("ele"), "count": e.get("count"), "spawn": e.get("spawn"), "on_field": e.get("active"),
             "er": e.get("er"), "energy": round(e.get("amount", 0.0), 2)} for e in rot.energy]
    theirs = [{"t": round(e["f"] / FPS, 2), "collector": e["char"], "kind": e["kind"], "source": e.get("source"),
               "element": e.get("ele"), "count": e.get("count"), "on_field": e.get("active"), "er": e.get("er"),
               "energy": e.get("amount"), "after": e.get("post")} for e in g["energy"]]
    bursts = {}
    for m in rot.lineup:
        cost = D.value(m, "burst", "Energy Cost") or 0.0
        ob = [a.t for a in rot.actions if a.char == m and a.action == "burst"]
        gb = [a["f"] / FPS for a in g["actions"] if a["char"] == m and a["action"] == "burst"]
        oe = [(e["t"], e.get("amount", 0.0)) for e in rot.energy if e["char"] == m]
        ge = [(e["f"] / FPS, (e.get("post") or 0) - (e.get("pre") or 0)) for e in g["energy"]
              if e["char"] == m and e["kind"] != "drain"]
        if not ob and not gb:
            continue
        oa, ga = _availability(oe, ob, cost, cost), _availability(ge, gb, cost, cost)
        diffs = [round(y["available_t"] - x["available_t"], 2) for x, y in zip(oa, ga)
                 if x["available_t"] is not None and y["available_t"] is not None]
        bursts[m] = {"cost": cost, "forward": oa, "gcsim": ga, "availability_delta": diffs,
                     # both capped at the Burst cost (gcsim logs the energy after minus before; overflow is lost)
                     "received_forward": round(_capped(oe, ob, cost), 1), "received_gcsim": round(sum(v for _, v in ge), 1),
                     "received_forward_uncapped": round(sum(v for _, v in oe), 1)}
    return {"bursts": bursts, "forward": ours, "gcsim": theirs}
