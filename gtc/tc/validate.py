"""Check the calculator against gcsim: predict a swap from one simulated team, then simulate the
resulting team with identical builds for every shared character, and compare."""
from __future__ import annotations

from dataclasses import dataclass

from gtc.tc import profile_for
from gtc.tc.engine import Theory, load_kits, measured_candidate, swap

CASES = [
    (["Flins", "Ineffa", "Columbina", "Sucrose"], "Columbina", "Aino"),
    (["Flins", "Ineffa", "Columbina", "Sucrose"], "Ineffa", "Fischl"),
    (["Flins", "Ineffa", "Columbina", "Sucrose"], "Columbina", "Furina"),
    (["Flins", "Ineffa", "Aino", "Sucrose"], "Aino", "Columbina"),
    (["Flins", "Ineffa", "Aino", "Sucrose"], "Ineffa", "Fischl"),
]


@dataclass
class Check:
    base: list[str]
    out: str
    into: str
    predicted: float
    actual: float

    @property
    def error(self) -> float:
        return self.predicted / self.actual - 1


def run_checks(cases=CASES) -> list[Check]:
    kits = load_kits()
    theory = Theory(kits, beyond_gcsim=False)
    out = []
    for base, leaving, joining in cases:
        b = profile_for(base, kits=kits)
        if not b:
            continue
        base_p, base_text, base_keys = b
        target = [joining if m == leaving else m for m in base]
        t = profile_for(target, kits=kits, base=base_p, base_text=base_text, base_keys=base_keys)
        if not t:
            continue
        target_p = t[0]
        res = swap(theory, base_p, leaving, measured_candidate(joining, target_p), target_p)
        out.append(Check(base, leaving, joining, res.after, target_p.dps))
    return out


if __name__ == "__main__":
    for c in run_checks():
        print(f"{' / '.join(c.base)}: {c.out} -> {c.into}: predicted {c.predicted / 1000:.1f}k, gcsim {c.actual / 1000:.1f}k ({c.error:+.1%})")


def sample_swaps(n: int = 200, seed: int = 13) -> list[tuple[list[str], str, str]]:
    """One-member swaps between simulated lineups, across all archetype families: (base, leaving, joining)."""
    import random

    from gtc.synergy import load_database

    lineups = [frozenset(e["lineup"]) for e in load_database().values() if "lineup" in e and len(e["lineup"]) == 4]
    by_three: dict[frozenset, list[frozenset]] = {}
    for L in lineups:
        for m in L:
            by_three.setdefault(L - {m}, []).append(L)
    pairs = []
    for core, group in by_three.items():
        for a in group:
            for b in group:
                if a != b:
                    (out,), (into,) = tuple(a - core), tuple(b - core)
                    pairs.append((sorted(a), out, into))
    random.Random(seed).shuffle(pairs)
    return pairs[:n]


def run_broad(n: int = 200, workers: int = 8) -> dict:
    """The plan's check for generated kits: predicted against simulated DPS on sampled one-member swaps, with
    generated kits and with hand-written kits only. The newcomer's own damage is measured in the target
    simulation, so the check is about how the swap changes everyone else's damage (buffs and RES shred)."""
    from concurrent.futures import ThreadPoolExecutor

    kits_all, kits_hand = load_kits(), load_kits(generated=False)
    th_all, th_hand = Theory(kits_all, beyond_gcsim=False), Theory(kits_hand, beyond_gcsim=False)

    def one(case):
        base, leaving, joining = case
        try:
            b = profile_for(base, kits=kits_all)
            if not b:
                return None
            base_p, base_text, base_keys = b
            target = [joining if m == leaving else m for m in base]
            t = profile_for(target, kits=kits_all, base=base_p, base_text=base_text, base_keys=base_keys)
            if not t:
                return None
            target_p = t[0]
            cand = measured_candidate(joining, target_p)
            with_gen = swap(th_all, base_p, leaving, cand, target_p).after
            hand = swap(th_hand, base_p, leaving, cand, target_p).after
            from gtc.theory_guard import check_swap, coverage
            ok = check_swap(base_p, target_p, leaving=leaving).supported
            return (base, leaving, joining, with_gen, hand, target_p.dps,
                    coverage(base_p).unsupported_share, coverage(target_p).unsupported_share, ok)
        except Exception:
            return None

    with ThreadPoolExecutor(max_workers=workers) as pool:
        rows = [r for r in pool.map(one, sample_swaps(n)) if r]
    supported = [r for r in rows if r[8]]  # cases the guard lets through
    err_sup = sorted(abs(r[3] / r[5] - 1) for r in supported)
    err_gen = sorted(abs(r[3] / r[5] - 1) for r in rows)
    err_hand = sorted(abs(r[4] / r[5] - 1) for r in rows)
    return {"cases": len(rows),
            "generated": {"within_10pct": sum(e <= 0.10 for e in err_gen) / len(rows), "median_error": err_gen[len(err_gen) // 2]},
            "hand_only": {"within_10pct": sum(e <= 0.10 for e in err_hand) / len(rows), "median_error": err_hand[len(err_hand) // 2]},
            "supported": {"cases": len(supported),
                          "within_10pct": (sum(e <= 0.10 for e in err_sup) / len(err_sup)) if err_sup else None,
                          "median_error": err_sup[len(err_sup) // 2] if err_sup else None},
            "rows": rows}


MOONSIGN = {"Flins", "Ineffa", "Columbina", "Lauma", "Aino", "Nefer", "Zibai", "Illuga", "Linnea"}


def run_guarded(n_lunar: int = 150, workers: int = 1, seeds: tuple[int, ...] = (21, 5)) -> dict:
    """The calculator's accuracy where the theory guard lets it answer: the five hand checks plus sampled
    one-member swaps of teams with a Moonsign member (where Lunar teams are), each kept only if the guard
    accepts both the base and the swapped team."""
    from concurrent.futures import ThreadPoolExecutor

    from gtc.theory_guard import check_swap

    kits = load_kits()
    th = Theory(kits, beyond_gcsim=False)
    # One worker by default: parallel runs of the same config race on the result cache and make runs differ.
    seen, cases = set(), []
    for seed in seeds:
        for c in [c for c in sample_swaps(20000, seed=seed) if MOONSIGN & set(c[0])][:n_lunar] + list(CASES):
            key = (tuple(c[0]), c[1], c[2])
            if key not in seen:
                seen.add(key)
                cases.append(c)

    def one(case):
        base, leaving, joining = case
        try:
            b = profile_for(base, kits=kits)
            if not b:
                return None
            base_p, base_text, base_keys = b
            t = profile_for([joining if m == leaving else m for m in base], kits=kits, base=base_p, base_text=base_text, base_keys=base_keys)
            if not t:
                return None
            target_p = t[0]
            ok = check_swap(base_p, target_p, leaving=leaving).supported
            pred = swap(th, base_p, leaving, measured_candidate(joining, target_p), target_p).after
            return base, leaving, joining, pred / target_p.dps - 1, ok
        except Exception:
            return None

    with ThreadPoolExecutor(max_workers=workers) as pool:
        rows = [r for r in pool.map(one, cases) if r]
    accepted = [r for r in rows if r[4]]
    errs = sorted(abs(r[3]) for r in accepted)
    return {"cases": len(rows), "accepted": len(accepted),
            "within_10pct": (sum(e <= 0.10 for e in errs) / len(errs)) if errs else None,
            "median_error": errs[len(errs) // 2] if errs else None,
            "refused_within_10pct": (sum(abs(r[3]) <= 0.10 for r in rows if not r[4]) / max(1, len(rows) - len(accepted))),
            "rows": rows}
