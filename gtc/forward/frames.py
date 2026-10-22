"""Measured action timing (execution parity): what an action physically does to the timeline, per character, from
gcsim's own logs of OTHER teams' runs (the reference lineups are excluded). gcsim's frame data is the community's
frame counting of the game; the forward model reads it as measured character facts, like its kit files.

Per character and action state:
    queue[next]     frames until the next action can start, per next-action type (attack, charge, skill, burst, dash,
                    jump, high_plunge, low_plunge, swap) - the input lock is not one number
    hitlag          frozen frames applied to the character during the action (melee hits extend the animation)
Per character:
    particle_delay  seconds from the Skill's start to its particles' arrival (travel)
Global:
    swap_cd         seconds between two swaps (gcsim's swap cooldown)
gaps are also kept per Burst segment ("B:" keys: the character has used their Burst since swapping in; "N:" keys: not), since a Burst
state can change a character's attack string (Raiden's Musou Isshin). Transitions the community rotations never play
(a fifth consecutive attack, attacks in a Burst state) come from probe(): single-character gcsim scripts that play
every chain position into every next action - frame data, not a team result.
Medians over every observation. Written to knowledge/forward/frames.json with the sample count per entry.
"""
from __future__ import annotations

import glob
import json
import re
import statistics
from collections import defaultdict
from functools import lru_cache

from gtc import KNOWLEDGE_DIR, ROOT

FRAMES = KNOWLEDGE_DIR / "forward" / "frames.json"
SIMS = ROOT / "data" / "sims"
FPS = 60.0
STATE = {"attack": "normal", "charge": "charge", "skill": "skill", "burst": "burst", "dash": "dash", "jump": "jump",
         "high_plunge": "plunge", "low_plunge": "plunge", "aim": "aim"}
NEXT = ("attack", "charge", "skill", "burst", "dash", "jump", "high_plunge", "low_plunge", "swap")
SWAP_CD = 1.0     # fallback when not measured


def _key(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", name.lower())


def measure(max_files: int | None = None) -> dict:
    from gtc.forward.reference import REFERENCE

    from gtc.forward.hidden import HIDDEN

    # development and hidden validation teams never inform frame data
    refs = {frozenset(_key(m) for m in e["team"]) for e in list(REFERENCE) + list(HIDDEN)}
    queue = defaultdict(lambda: defaultdict(list))
    hitlag = defaultdict(list)
    delay = defaultdict(list)
    swaps = []
    cds = defaultdict(list)       # (char, skill|burst) -> observed cooldowns in frames
    cds_ctx = defaultdict(list)   # (char, skill|burst, own Burst active?) -> observed cooldowns in frames
    sched = defaultdict(list)     # char -> per Skill cast: [(offset s, count), ...] of its own particles
    naca_hits, naca_energy = defaultdict(int), defaultdict(int)
    chain_gap = defaultdict(lambda: defaultdict(list))    # char -> position of the previous attack -> frames to next
    gaps = defaultdict(lambda: defaultdict(list))         # char -> "prev|chain position|next" -> executed-to-executed frames
    files = sorted(glob.glob(str(SIMS / "*.sample.json")))[: max_files or None]
    used = 0
    dash_obs = []                 # (frames between the two previous dashes, frames to this dash, refused before it)
    regen_start = []              # seconds from a dash's start until stamina regeneration begins (gcsim stam_post)
    regen_rate = []
    for p in files:
        try:
            d = json.loads(open(p, encoding="utf-8").read())
        except (OSError, ValueError):
            continue
        order = [c.get("name") for c in d.get("character_details") or []]
        if frozenset(order) in refs:
            continue
        used += 1
        logs = d.get("logs") or []
        stam = [(l["frame"], l["logs"].get("action"), float(l["logs"]["stam_post"])) for l in logs
                if l.get("event") == "action" and str(l.get("msg", "")).startswith("executed")
                and "stam_post" in (l.get("logs") or {})]
        for i, (f0, a0, s0) in enumerate(stam):
            if a0 != "dash":
                continue
            base = None
            for f1, a1, s1 in stam[i + 1:]:
                if a1 in ("dash", "charge", "jump"):
                    break
                dt = (f1 - f0) / FPS
                if base is None:
                    if dt <= 0.7:
                        base = (dt, s1)
                    continue
                gain = s1 - base[1]
                if 2.0 <= dt <= 4.0 and 0 < gain and s1 < 230 and base[1] < 200:
                    regen_start.append(dt - gain / 25.0)
                    if dt >= 3.0:
                        regen_rate.append(gain / (dt - 1.75))
        dh, dref = [], False
        for l in logs:
            m_ = l.get("msg") or ""
            if l.get("event") == "sim" and m_.startswith("could not execute dash"):
                dref = True
            elif l.get("event") == "action" and m_ == "executed swap":
                dh = []
            elif l.get("event") == "action" and m_ == "executed dash":
                if len(dh) >= 2:
                    dash_obs.append((dh[-1] - dh[-2], l["frame"] - dh[-1], dref))
                dh.append(l["frame"])
                dref = False
        last_exec = {}            # char -> (frame, action)
        last_skill = {}
        cast = {}                 # char -> (frame of the last Skill, [(offset, count)])
        run = [None, 0, 0]        # consecutive attacks: char, count, frame of the last one
        prev_ex = None            # (char, action, frame, chain position) of the previous executed action
        active = d.get("initial_character")
        cur = None                # (char, state, frame, frozen)
        last_swap = None
        seg_burst = set()         # characters who used their Burst since they last swapped in
        refused = False           # gcsim refused an action since the last executed one
        swap_blocked = False      # a swap was refused since the last one: the next gap is the cooldown itself
        own_burst = {}            # char -> frame of their last Burst
        for l in logs:
            ev, msg, fr = l.get("event"), l.get("msg") or "", l.get("frame", 0)
            ci = l.get("char_index", -1)
            who = order[ci] if 0 <= ci < len(order) else None
            lg = l.get("logs") or {}
            if ev == "hitlag" and msg.endswith(" started") and who:
                st = lg.get("State")
                if cur:
                    hitlag[(cur[0], cur[1])].append(cur[3])
                cur = [who, st, fr, 0]
                for n in NEXT:
                    if isinstance(lg.get(n), (int, float)):
                        queue[(who, st)][n].append(lg[n])
            elif ev == "hitlag" and msg.startswith("hitlag applied to char") and cur and who == cur[0]:
                cur[3] += lg.get("frozen_frames", 0)
            elif ev == "cooldown" and msg.endswith("cooldown triggered") and who and lg.get("original_cd"):
                cds[(who, lg.get("type"))].append(int(lg["original_cd"]))
                bd = burst_duration(who)
                if bd:
                    inside = who in own_burst and fr - own_burst[who] <= bd * FPS
                    cds_ctx[(who, lg.get("type"), inside)].append(int(lg["original_cd"]))
            if ev == "action" and msg == "executed burst" and who:
                own_burst[who] = fr
            if ev == "sim" and msg.startswith("could not execute"):
                refused = True
            if (ev == "energy" and msg == "draining energy" and prev_ex and prev_ex[0] == who and prev_ex[1] == "burst"
                    and fr - prev_ex[2] < 30):
                # a Burst that drained less than the full cost is a reduced-cost variant (Flins's Thunderous
                # Symphony): its frames are its own ("burst~partial"), not the full Burst's
                if (lg.get("pre_drain") or 0) - (lg.get("post_drain") or 0) < (lg.get("max_energy") or 0) - 1:
                    prev_ex = (prev_ex[0], "burst~partial") + prev_ex[2:]
            if ev == "action" and msg.startswith("executed ") and msg not in ("executed swap", "executed wait") and who:
                act = msg[9:]
                if prev_ex and prev_ex[0] == who and not refused:      # a refused action in between: a cooldown
                    pos = prev_ex[3] if prev_ex[1] == "attack" else 0   # or energy wait, not the transition
                    gaps[who][f"{prev_ex[1]}|{pos}|{act}"].append(fr - prev_ex[2])
                    # per segment as well: with the character's Burst used since swap-in ("B:"), or not ("N:")
                    gaps[who][f"{'B' if prev_ex[4] else 'N'}:{prev_ex[1]}|{pos}|{act}"].append(fr - prev_ex[2])
                if act == "burst":
                    seg_burst.add(who)
                nxt_pos = (run[1] + 1) if (act == "attack" and run[0] == who) else (1 if act == "attack" else 0)
                prev_ex = (who, act, fr, nxt_pos, who in seg_burst)
                refused = False
            elif ev == "action" and msg in ("executed swap", "executed wait"):
                prev_ex = None
                refused = False
                if msg == "executed swap":
                    seg_burst.clear()
            if ev == "action" and msg == "executed attack" and who:
                if run[0] == who and run[1] >= 1:
                    chain_gap[who][run[1]].append(fr - run[2])
                    run = [who, run[1] + 1, fr]
                else:
                    run = [who, 1, fr]
            elif ev == "action" and msg.startswith("executed ") and msg != "executed attack":
                run = [None, 0, 0]
                if msg == "executed skill" and who:
                    last_skill[who] = fr
                    if who in cast and cast[who][1]:
                        sched[who].append(cast[who][1])
                    cast[who] = (fr, [])
            elif ev == "action" and msg == "executed skill" and who:
                last_skill[who] = fr
                if who in cast and cast[who][1]:
                    sched[who].append(cast[who][1])
                cast[who] = (fr, [])
            elif ev == "action" and msg == "executed swap":
                active = order.index(lg.get("target")) if lg.get("target") in order else active
                active = order[active] if isinstance(active, int) else active
                if last_swap is not None and swap_blocked:
                    swaps.append(fr - last_swap)
                last_swap = fr
                swap_blocked = False
            elif ev == "sim" and msg.startswith("could not execute swap"):
                swap_blocked = True
            elif ev == "damage" and who and who == active and lg.get("attack-tag") in (1, 2):
                naca_hits[who] += 1            # a Normal / Charged hit by the active character
            elif ev == "energy" and msg == "adding energy" and lg.get("source") == "na-ca-on-hit" and who:
                naca_energy[who] += lg.get("rec'd", 1)
            elif ev == "energy" and msg == "particle":
                src = str(lg.get("source") or "")
                if src in cast and 0 < fr - cast[src][0] < 1800 and lg.get("char_index", ci) == ci:
                    pass
                if src in cast and 0 < fr - cast[src][0] < 1800 and (not cast[src][1] or cast[src][1][-1][0] != round((fr - cast[src][0]) / FPS, 2)):
                    cast[src][1].append((round((fr - cast[src][0]) / FPS, 2), lg.get("count", 1)))
                if src in last_skill and 0 < fr - last_skill[src] < 600:
                    delay[src].append((fr - last_skill[src]) / FPS)
                    last_skill.pop(src, None)    # first particle event of that Skill
    out = {"provenance": "gcsim sample logs of non-reference teams (frame data), medians", "files": used,
           # swap-to-swap gap when the second swap had to wait (only those gaps are the cooldown; a free gap is
           # just how the rotation was written)
           "swap_cd": round(statistics.median(swaps) / FPS if swaps else SWAP_CD, 3), "swap_cd_samples": len(swaps),
           # stamina regeneration (gcsim logs the stamina after every action): when it starts after a dash begins,
           # and its rate
           "stamina_regen_delay": round(statistics.median(regen_start), 3) if len(regen_start) >= 20 else None,
           "stamina_regen_samples": len(regen_start),
           # dash lockout: after two dashes close together, the next dash waits (gcsim refuses it, stamina left)
           **_dash_rule(dash_obs),
           "characters": {}}
    for (who, st), nxt in queue.items():
        c = out["characters"].setdefault(who, {"states": {}, "particle_delay": None})
        c["states"][st] = {"queue": {n: round(statistics.median(v)) for n, v in nxt.items()},
                           "hitlag": round(statistics.median(hitlag.get((who, st)) or [0])),
                           "n": len(next(iter(nxt.values())))}
    for (who, typ), v in cds.items():
        c = out["characters"].setdefault(who, {"states": {}, "particle_delay": None})
        vals = sorted({round(x / FPS, 2) for x in v if v.count(x) >= max(2, len(v) // 20)}) or [round(statistics.median(v) / FPS, 2)]
        c.setdefault("cooldowns", {})[typ] = vals          # several values: press and hold variants
        # a cooldown that differs while the character's own Burst is active (Bennett's A4 inside his field): kept
        # per context so the generator does not take the reduced value everywhere
        ctx = {}
        for inside in (False, True):
            w = cds_ctx.get((who, typ, inside)) or []
            if len(w) >= 5:
                # the values that dominate the context (>= 30%: a press and a hold variant both qualify; a reduction
                # that only applies after the Burst's field reaches the character, at swap-in, does not)
                ctx["burst" if inside else "out"] = sorted({round(x / FPS, 2) for x in w if w.count(x) >= 0.3 * len(w)})                     or [round(statistics.median(w) / FPS, 2)]
        if len(ctx) == 2 and ctx["burst"] != ctx["out"]:
            c.setdefault("cooldowns_ctx", {})[typ] = ctx
    for who, casts in sched.items():
        casts = [c for c in casts if c]
        if len(casts) < 3:
            continue
        # the k-th particle event after a cast: median offset, mean count (casts with fewer events add 0)
        k_max = max(len(c) for c in casts)
        rows = []
        for k in range(k_max):
            offs = [c[k][0] for c in casts if len(c) > k]
            cnt = sum(c[k][1] for c in casts if len(c) > k) / len(casts)
            if cnt >= 0.05:
                rows.append([round(statistics.median(offs), 2), round(cnt, 3)])
        out["characters"].setdefault(who, {"states": {}, "particle_delay": None})["particle_schedule"] = rows
    for who, pos in chain_gap.items():
        c = out["characters"].setdefault(who, {"states": {}, "particle_delay": None})
        c["attack_chain"] = {str(k): round(statistics.median(v)) for k, v in sorted(pos.items()) if len(v) >= 5}
    for who, g in gaps.items():
        c = out["characters"].setdefault(who, {"states": {}, "particle_delay": None})
        c["gaps"] = {k: round(statistics.median(v)) for k, v in g.items() if len(v) >= 5}
    for who, n in naca_hits.items():
        if n >= 30:
            out["characters"].setdefault(who, {"states": {}, "particle_delay": None})["naca_energy_per_hit"] = \
                round(naca_energy.get(who, 0) / n, 4)
    for who, v in delay.items():
        out["characters"].setdefault(who, {"states": {}, "particle_delay": None})["particle_delay"] = round(statistics.median(v), 3)
    FRAMES.write_text(json.dumps(out, indent=1), encoding="utf-8")
    return out


@lru_cache(maxsize=1)
def table() -> dict:
    return json.loads(FRAMES.read_text(encoding="utf-8")) if FRAMES.exists() else {}


def lock(char: str, action: str, nxt: str) -> float | None:
    """Seconds after `action` starts until `nxt` (an action, or "swap") can start, hitlag included; None when the
    table has no measurement."""
    c = (table().get("characters") or {}).get(_key(char))
    st = (c or {}).get("states", {}).get(STATE.get(action, action))
    if not st:
        return None
    q = st["queue"].get(nxt)
    if q is None:
        return None
    return (q + st.get("hitlag", 0)) / FPS


@lru_cache(maxsize=None)
def burst_duration(char: str) -> float | None:
    """The character's Burst duration from the Amber table (its longest "... Duration" row), or None."""
    from gtc import gamedata
    from gtc.forward import data as D

    name = gamedata.names().character(char) or char
    try:
        t = D.table(name, "burst")
    except Exception:   # noqa: BLE001
        return None
    vals = [v[0] for k, v in t.items() if "Duration" in k and "Extension" not in k and v and isinstance(v[0], (int, float))]
    return float(max(vals)) if vals else None


def hitlag(char: str, action: str) -> float:
    """Median frozen seconds the character's own hits put on them during this action (measured)."""
    c = (table().get("characters") or {}).get(_key(char)) or {}
    st = (c.get("states") or {}).get(STATE.get(action, action)) or {}
    return float(st.get("hitlag", 0) or 0) / FPS


def cooldown(char: str, kind: str, hold: bool = False, own_burst_active: bool | None = None) -> float | None:
    """Measured cooldown of a Skill / Burst; with press and hold variants measured, hold takes the longer one. When
    the cooldown was measured to differ while the character's own Burst is active, that context decides."""
    c = ((table().get("characters") or {}).get(_key(char)) or {})
    ctx = (c.get("cooldowns_ctx") or {}).get(kind)
    if ctx and own_burst_active is not None and not hold:    # a hold variant keeps its overall value (a context
        return min(ctx["burst" if own_burst_active else "out"])   # may have too few hold casts to show it)
    v = (c.get("cooldowns") or {}).get(kind)
    if not v:
        return None
    return max(v) if hold else min(v)


def attack_gap(char: str, position: int) -> float | None:
    """Seconds from an attack to the next attack of the same chain, by the previous attack's position (1 = the first
    of the run); positions past the measured ones use the longest measured position's cycle."""
    ch = (((table().get("characters") or {}).get(_key(char)) or {}).get("attack_chain") or {})
    if not ch:
        return None
    return ch[str(position)] / FPS if str(position) in ch else None


def gap(char: str, action: str, position: int, nxt: str, burst_segment: bool = False) -> float | None:
    """Measured executed-to-executed seconds from `action` (at chain `position` for attacks) to `nxt` by the same
    character: animation, cancel and hitlag together; None when that transition was not observed. In a Burst
    segment the Burst-segment measurement is used when there is one."""
    g = (((table().get("characters") or {}).get(_key(char)) or {}).get("gaps") or {})
    k = f"{action}|{position if action == 'attack' else 0}|{nxt}"
    v = g.get(f"{'B' if burst_segment else 'N'}:{k}")
    if v is None:
        v = g.get(k)
    return None if v is None else v / FPS


PROBE_REPS = 5
PROBE_NEXT = {"normal": ("attack", "dash", "jump", "skill", "charge", "burst"), "burst": ("attack", "dash", "skill", "charge")}


def probe_scripts(name: str) -> dict[str, str]:
    """Single-character gcsim scripts that play every attack-chain position (1-6) into one kind of next action, out
    of and in a Burst segment (each Burst segment: Burst, the string, the next action; ample energy, gcsim waits out
    the cooldowns). One script per (segment, next action), so a kit rule that refuses one transition (a Charged
    Attack that must follow an attack) loses only that script."""
    from gtc.forward.library import source_lineups
    from gtc.forward.trace import house_config

    hc = None
    for lu in source_lineups(name, None) or []:
        hc = house_config(lu)
        if hc:
            break
    if not hc:
        return {}
    text, keys = hc[0], hc[1]
    k = keys.get(name)
    if not k:
        return {}
    head = [l.strip() for l in text.splitlines() if re.match(rf"\s*{k}\s+(char|add)\b", l)]
    head += [f"{k} add stats er=20;", "options swap_delay=12 iteration=1;",
             "target lvl=100 resist=0.1 hp=1000000000 pos=0,2.4 radius=2;",
             "energy every interval=60,61 amount=1;", f"active {k};"]
    out = {}
    for seg, nexts in PROBE_NEXT.items():
        for nxt in nexts:
            body = []
            for n in range(1, 7):
                body += ([f"{k} burst;"] if seg == "burst" else []) + [f"{k} attack:{n};", f"{k} {nxt};", "wait(90);"]
            out[f"{seg}:{nxt}"] = "\n".join(head + body) + "\n"
    # dash spacing: two dashes some frames apart, then a third at once (the dash lockout), then a long rest
    body = []
    for gap in (0, 10, 20, 30, 40, 50, 60):
        body += [f"{k} dash;"] + ([f"wait({gap});"] if gap else []) + [f"{k} dash;", f"{k} dash;", "wait(240);"]
    out["dash"] = "\n".join(head + body) + "\n"
    return out


def probe(names: list[str] | None = None) -> dict:
    """Run the probe scripts (their sample logs land in data/sims with the others; measure() reads them)."""
    from gtc.forward.kitfreeze import ACT_DIR
    from gtc.synergy import run_sample

    names = names or sorted(p.stem for p in ACT_DIR.glob("*.yaml"))
    out = {}
    for n in names:
        scripts = probe_scripts(n)
        if not scripts:
            out[n] = {"error": "no source config"}
            continue
        res = {}
        for tag, s in scripts.items():
            try:
                for r in range(PROBE_REPS):     # repetitions: every transition observed often enough for a median
                    run_sample(s + f"# probe {r}\n", keep=True)
                res[tag] = "ok"
            except Exception as e:   # noqa: BLE001
                res[tag] = f"{type(e).__name__}: {str(e).strip().splitlines()[-1][:100] if str(e).strip() else ''}"
        out[n] = res
    return out


def particle_schedule(char: str) -> list | None:
    return ((table().get("characters") or {}).get(_key(char)) or {}).get("particle_schedule")


def naca_energy(char: str) -> float:
    return float(((table().get("characters") or {}).get(_key(char)) or {}).get("naca_energy_per_hit") or 0.0)


def particle_delay(char: str) -> float | None:
    return ((table().get("characters") or {}).get(_key(char)) or {}).get("particle_delay")


def _dash_rule(obs: list) -> dict:
    """The pair window (largest spacing of two dashes after which a third was refused at least 20 times) and the
    lockout (median wait from the second dash until the refused third one went through)."""
    from collections import Counter

    ref = [o for o in obs if o[2]]
    if len(ref) < 20:
        return {}
    by_pair = Counter(o[0] // 10 * 10 for o in ref)
    window = max(k for k, n in by_pair.items() if n >= 20) + 9
    waits = [o[1] for o in ref if o[0] <= window and o[1] < 150]
    return {"dash_pair_window": round(window / FPS, 3), "dash_lockout": round(statistics.median(waits) / FPS, 3),
            "dash_samples": len(waits)}


def dash_rule() -> tuple[float, float] | None:
    t = table()
    return (t["dash_pair_window"], t["dash_lockout"]) if t.get("dash_lockout") else None


def stamina_regen_delay(default: float) -> float:
    v = table().get("stamina_regen_delay")
    return float(v) if v else default


def swap_cd() -> float:
    return float(table().get("swap_cd") or SWAP_CD)


def is_hold(abil: str) -> bool:
    """A hit that only the hold variant of a Skill produces ("Hold DMG", "Spring Spirit Summoning (Hold)"); one test
    for the generator's cooldown and the gcsim translation, so the two never disagree on tap vs hold."""
    s = abil or ""
    return bool(re.search(r"\bhold\b", s, re.I)) and not re.search(r"press/hold", s, re.I)
