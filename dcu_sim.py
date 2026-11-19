#!/usr/bin/env python3
"""DC film slate simulator.

Each film is scored on seven 1-5 axes. Those scores drive marketability,
a quality distribution, how much the film rides on franchise momentum, and
how much casual audiences are put off by required "homework". A slate is run
in release order; each film's quality feeds momentum and character equity for
the films that follow. Monte Carlo over many slates gives box-office ranges.

Usage:
    python3 dcu_sim.py                       # 10k runs, summary table
    python3 dcu_sim.py --runs 2000 --seed 7
    python3 dcu_sim.py --pin "Superman=bad"  # force a film's quality
    python3 dcu_sim.py --sensitivity         # what each film's quality is worth to the slate
"""
import argparse
import random
import statistics

# ---------------------------------------------------------------- tunables
ERA = 1.0          # whole-market multiplier (theatrical climate)
INTL = 2.3         # worldwide / domestic ratio
FATIGUE = 0.96     # opening multiplier per prior solo outing of the leads
MOM_CAP = 0.5      # momentum clamp (+/-)
EQ_CAP = 1.4       # character equity ceiling
LEGS = {"bad": 2.3, "ok": 2.7, "good": 3.1, "great": 3.6}   # domestic total / opening
SCORE = {"bad": -2, "ok": 0, "good": 1, "great": 2}          # word-of-mouth signal
QUALITIES = ("bad", "ok", "good", "great")

# starting brand equity per character (unknown characters default to 0.6)
INIT_EQUITY = {
    "Superman": 1.0, "Batman": 1.0, "Wonder Woman": 0.85, "Flash": 0.7,
    "Aquaman": 0.7, "Green Lantern": 0.6, "Martian Manhunter": 0.5,
    "Shazam": 0.6, "Green Arrow": 0.55, "Cyborg": 0.5, "Teen Titans": 0.55,
    "New Gods": 0.5,
}

# P, S, V, K, G, H, R  (pitch, set piece, villain, stakes, freshness, homework, risk)
SCORES = {
 "Superman": (5,4,3,4,4,1,2), "Batman": (4,4,3,3,3,1,2),
 "Wonder Woman": (4,4,2,3,4,1,2), "Superman 2: World's Finest": (5,4,3,3,5,2,2),
 "Green Lantern and Martian Manhunter": (3,3,2,3,4,2,3), "Justice League": (5,5,3,4,3,3,3),
 "The Flash": (4,5,2,3,5,2,2), "Superman 3": (4,4,3,3,3,2,2), "Aquaman": (3,5,3,3,3,1,3),
 "Batman 2": (3,3,2,3,2,2,2), "Green Arrow vs. Deathstroke": (3,4,4,4,3,4,3),
 "JL: Sinestro Corps War": (4,5,4,3,4,3,3), "Wonder Woman 2": (4,5,3,4,3,2,2),
 "Shazam!": (5,3,2,3,5,1,2), "Superman 4": (5,4,4,4,3,2,2), "The Flash 2": (3,4,3,4,2,2,3),
 "New Gods": (3,5,5,4,4,3,4), "Teen Titans": (3,3,2,3,4,2,3),
 "JL: Tower of Babel": (5,3,3,4,3,4,3), "Batman 3": (4,4,5,4,3,3,2),
 "Aquaman 2": (3,4,3,2,2,2,2), "New Gods 2: Apokolips": (4,4,3,3,5,4,3),
 "Green Arrow 2": (3,3,2,4,2,5,3), "Wonder Woman 3": (3,3,3,4,2,3,3),
 "Green Lantern: Blackest Night": (4,5,3,4,4,3,3), "Superman 5: Doomsday": (5,5,3,5,4,2,3),
 "Teen Titans 2": (3,4,2,3,3,3,2), "New Gods 3: Fall of New Genesis": (3,5,4,4,4,5,3),
 "Cyborg": (3,3,2,3,3,4,3), "JL: Anti-Life (Part 1)": (4,4,5,5,4,5,4),
 "JL: Omega (Part 2)": (4,5,5,5,3,5,4),
}

SM, BM, WW, FL, AQ = "Superman", "Batman", "Wonder Woman", "Flash", "Aquaman"
GL, MM, SH, GA, CY = "Green Lantern", "Martian Manhunter", "Shazam", "Green Arrow", "Cyborg"
TT, NG = "Teen Titans", "New Gods"
JL_CORE = [SM, BM, WW, FL, GL]
JL_BENCH = [MM, AQ, CY, SH, NG, GA, TT]


def F(name, base, leads, support=(), tease=(), event=1.0):
    """base = domestic opening ($M) at equity 1.0, neutral momentum.
    event >= 1.3 marks a team-up: doesn't count as a solo outing, and its
    quality swings momentum 1.5x as hard."""
    assert name in SCORES, name
    return {"name": name, "base": base, "leads": list(leads),
            "support": list(support), "tease": list(tease), "event": event}


FILMS = [  # release order
    F("Superman", 100, [SM], tease=[BM, WW]),
    F("Batman", 95, [BM], tease=[SM]),
    F("Wonder Woman", 75, [WW], tease=[AQ]),
    F("Superman 2: World's Finest", 105, [SM, BM], [WW], [FL], 1.15),
    F("Green Lantern and Martian Manhunter", 60, [GL, MM], tease=[FL]),
    F("Justice League", 110, [SM, BM, WW], [FL, GL, MM, AQ], [CY, SH], 1.4),
    F("The Flash", 65, [FL], [BM], [TT]),
    F("Superman 3", 95, [SM], tease=[SH]),
    F("Aquaman", 60, [AQ], tease=[CY]),
    F("Batman 2", 90, [BM], [GA], [TT]),
    F("Green Arrow vs. Deathstroke", 50, [GA], [BM], [TT]),
    F("JL: Sinestro Corps War", 100, [GL, SM, WW], [MM, FL, AQ], [NG], 1.35),
    F("Wonder Woman 2", 75, [WW], tease=[NG]),
    F("Shazam!", 55, [SH], [SM], [TT]),
    F("Superman 4", 95, [SM], [SH]),
    F("The Flash 2", 65, [FL], [CY]),
    F("New Gods", 50, [NG], [SM], [CY]),
    F("Teen Titans", 50, [TT], [BM, CY]),
    F("JL: Tower of Babel", 105, [BM, SM, WW], [FL, GL, MM, AQ, CY, SH], event=1.4),
    F("Batman 3", 90, [BM], [GA, TT]),
    F("Aquaman 2", 60, [AQ]),
    F("New Gods 2: Apokolips", 50, [NG], tease=[CY]),
    F("Green Arrow 2", 45, [GA]),
    F("Wonder Woman 3", 75, [WW], [NG]),
    F("Green Lantern: Blackest Night", 70, [GL], [MM, SM]),
    F("Superman 5: Doomsday", 105, [SM], [BM, WW], event=1.15),
    F("Teen Titans 2", 50, [TT], [CY]),
    F("New Gods 3: Fall of New Genesis", 50, [NG], [WW], [CY]),
    F("Cyborg", 50, [CY], [TT, FL]),
    F("JL: Anti-Life (Part 1)", 115, JL_CORE, JL_BENCH, event=1.5),
    F("JL: Omega (Part 2)", 120, JL_CORE, JL_BENCH, event=1.6),
]
assert {f["name"] for f in FILMS} == set(SCORES)


def derive(name):
    P, S, V, K, G, H, R = SCORES[name]
    mkt  = 1 + .06*(P-3.5) + .04*(V-3) + .03*(S-3.5) + .02*(G-3)   # marketability
    qi   = .20*(K-3) + .12*(S-3) + .10*(G-3) + .08*(P-3) - .20*(R-2.5)  # quality index
    dep  = .4 + .15*H                      # how much the film rides on momentum
    gate = 1 - .03*max(0, H-2)             # casuals skip homework-heavy films
    return mkt, qi, dep, gate


def draw_quality(qi, rng):
    z = qi + rng.gauss(0, .8)              # plot-driven, with luck
    return "bad" if z < -.7 else "ok" if z < .1 else "good" if z < .8 else "great"


def run_slate(films, rng, pins=None):
    pins = pins or {}
    mom, eq_map, solos, out = 0.0, dict(INIT_EQUITY), {}, []
    for f in films:
        mkt, qi, dep, gate = derive(f["name"])
        # Always consume the draw so pinned and unpinned runs share the same
        # random stream (common random numbers -> clean A/B comparisons).
        drawn = draw_quality(qi, rng)
        q = pins.get(f["name"]) or drawn
        L = f["leads"]
        eq = sum(eq_map.get(c, 0.6) for c in L) / len(L)
        prior = sum(solos.get(c, 0) for c in L) / len(L)
        opening = (f["base"] * (1 + mom*dep) * eq * mkt * gate * f["event"]
                   * FATIGUE ** prior * ERA * max(.5, rng.gauss(1, .12)))
        ww = opening * LEGS[q] * INTL
        out.append((f["name"], q, ww))
        s = SCORE[q]
        w = 1.5 if f["event"] >= 1.3 else 1.0
        mom = max(-MOM_CAP, min(MOM_CAP, 0.8*mom + 0.1*s*w))
        for c in L:
            eq_map[c] = min(EQ_CAP, max(.5, eq_map.get(c, .6) + 0.05*s))
            if f["event"] < 1.3:
                solos[c] = solos.get(c, 0) + 1
        for c in f["support"]:
            eq_map[c] = min(EQ_CAP, max(.5, eq_map.get(c, .6) + 0.05 + 0.06*s))
        for c in f["tease"]:
            eq_map[c] = min(EQ_CAP, eq_map.get(c, .6) + 0.03)
    return out


def monte_carlo(runs, seed, pins=None, films=FILMS):
    rng = random.Random(seed)
    grosses = {f["name"]: [] for f in films}
    quals = {f["name"]: dict.fromkeys(QUALITIES, 0) for f in films}
    totals = []
    for _ in range(runs):
        res = run_slate(films, rng, pins)
        totals.append(sum(ww for _, _, ww in res))
        for name, q, ww in res:
            grosses[name].append(ww)
            quals[name][q] += 1
    return grosses, quals, totals


def pct(xs, p):
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(p * len(xs)))]


def report(runs, seed, pins):
    grosses, quals, totals = monte_carlo(runs, seed, pins)
    print(f"{runs} runs, seed {seed}" + (f", pins {pins}" if pins else ""))
    print(f"{'#':>2} {'Film':<38}{'P10':>7}{'Median':>8}{'P90':>7}"
          f"   bad   ok good great")
    for i, f in enumerate(FILMS, 1):
        n, g, qd = f["name"], grosses[f["name"]], quals[f["name"]]
        dist = " ".join(f"{100*qd[q]/runs:4.0f}%" for q in QUALITIES)
        print(f"{i:>2} {n:<38}{pct(g,.1):>7.0f}{statistics.median(g):>8.0f}"
              f"{pct(g,.9):>7.0f}  {dist}")
    print(f"\nSlate total ($M WW): P10 {pct(totals,.1):,.0f}  "
          f"median {statistics.median(totals):,.0f}  P90 {pct(totals,.9):,.0f}")


def sensitivity(runs, seed):
    """Slate-total swing between a film landing 'great' vs 'bad', using
    common random numbers so the only difference is that one outcome."""
    print(f"Slate value of each film's quality ({runs} paired runs, $M WW)")
    print(f"{'Film':<38}{'own film':>10}{'rest of slate':>15}")
    rows = []
    for f in FILMS:
        n = f["name"]
        g_hi, _, t_hi = monte_carlo(runs, seed, {n: "great"})
        g_lo, _, t_lo = monte_carlo(runs, seed, {n: "bad"})
        own = statistics.mean(g_hi[n]) - statistics.mean(g_lo[n])
        rest = statistics.mean(t_hi) - statistics.mean(t_lo) - own
        rows.append((own + rest, n, own, rest))
    for _, n, own, rest in sorted(rows, reverse=True):
        print(f"{n:<38}{own:>10,.0f}{rest:>15,.0f}")


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--runs", type=int, default=10000)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--pin", action="append", default=[],
                    metavar="FILM=QUALITY", help="force a film's quality; repeatable")
    ap.add_argument("--sensitivity", action="store_true")
    a = ap.parse_args()
    pins = {}
    for p in a.pin:
        name, _, q = p.rpartition("=")
        if name not in SCORES or q not in QUALITIES:
            ap.error(f"bad --pin {p!r}: film must be in the slate, quality one of {QUALITIES}")
        pins[name] = q
    if a.sensitivity:
        sensitivity(min(a.runs, 2000), a.seed)
    else:
        report(a.runs, a.seed, pins)


if __name__ == "__main__":
    main()
