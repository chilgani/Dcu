import random, math

# ===== 1. PARAMETERS =====
P = dict(ERA=1.0, INTL=2.2, FATIGUE=0.96, MOM_DECAY=0.8,   # fitted
         FAME=1.0,         # fitted: how much starting fame differences matter (1 = as typed)
         BREAKOUT_P=0.08,  # fitted: odds of breakout (and of bust) for unknown leads
         MOM_CAP=0.25, EQ_CAP=1.5, NEG_MULT=2.5, EVD=0.7,
         BASE0=50.0,       # same starting opening for every film; fame/rubric/events differentiate
         DC_SCALE=0.8,     # ONE market knob: today's market vs the 2008-2019 comps (DC only)
         CEIL=2600)
FIT_KEYS = ("ERA", "INTL", "FATIGUE", "MOM_DECAY", "FAME", "BREAKOUT_P")
FIT_RANGE = dict(ERA=(.3, 2.5), INTL=(1.6, 2.8), FATIGUE=(.9, 1.0),
                 MOM_DECAY=(.5, .9), FAME=(.4, 1.5), BREAKOUT_P=(0, .2))
LEGS  = {"bad": 2.2, "ok": 2.6, "good": 2.9, "great": 3.3}
SCORE = {"bad": -1, "ok": 0, "good": 1, "great": 2}

def F(name, leads, event=1.0, support=(), tease=()):
    return dict(name=name, leads=list(leads), event=event,
                support=list(support), tease=list(tease))

# ===== 2. RUBRIC -> INPUTS =====
# Scores: (P pitch, S set piece, V villain, K stakes, G freshness, H homework, R risk)
def derive(sc):
    Pp, S, V, K, G, H, R = sc
    mkt  = 1 + .06*(Pp-3.5) + .04*(V-3) + .03*(S-3.5) + .02*(G-3)
    qi   = .20*(K-3) + .12*(S-3) + .10*(G-3) + .08*(Pp-3) - .20*(R-2.5)
    dep  = .4 + .15*H
    gate = 1 - .03*max(0, H-2)
    return mkt, qi, dep, gate

def grade(z):   # "great" is harder to earn than v2
    return "bad" if z < -.5 else "ok" if z < .25 else "good" if z < 1.0 else "great"

# ===== 3. ENGINE =====
def run_slate(films, scores, init_eq, rng=None, pins=None, det=False, dc=False):
    pins = pins or {}
    d0 = lambda v: max(.3, 1 + P["FAME"]*(v - 1))
    eq = {c: d0(v) for c, v in init_eq.items()}
    dflt = d0(.6)
    mom, solos, out = 0.0, {}, []
    scale = P["DC_SCALE"] if dc else 1.0
    for f in films:
        mkt, qi, dep, gate = derive(scores[f["name"]])
        q = pins.get(f["name"]) or grade(qi if det else qi + rng.gauss(0, .8))
        L = f["leads"]
        e = sum(eq.get(c, dflt) for c in L) / len(L)
        prior = sum(solos.get(c, 0) for c in L) / len(L)
        noise = 1.0
        if not det:
            unk = e < .7
            s = .25 if unk else .12
            noise = rng.lognormvariate(-.5*s*s, s)
            if unk:                              # breakout / bust for little-known leads
                r = rng.random()
                if r < P["BREAKOUT_P"]: noise *= 2.0
                elif r > 1 - P["BREAKOUT_P"]: noise *= 0.6
        ev = 1 + (f["event"] - 1) * P["EVD"]
        opening = (P["BASE0"] * (1 + mom*dep) * e * mkt * gate * ev
                   * P["FATIGUE"]**prior * P["ERA"] * noise * scale)
        ww = min(P["CEIL"], opening * LEGS[q] * P["INTL"])
        legs = "front-loaded" if (q in ("bad", "ok") or (f["event"] >= 1.5 and q != "great")) else "leggy"
        sc_ = SCORE[q]
        s_eff = sc_ if sc_ >= 0 else P["NEG_MULT"] * sc_
        w = 1.5 if f["event"] >= 1.3 else 1.0
        mom = max(-P["MOM_CAP"], min(P["MOM_CAP"], P["MOM_DECAY"]*mom + .1*s_eff*w))
        for c in L:
            eq[c] = min(P["EQ_CAP"], max(.3, eq.get(c, dflt) + .05*s_eff))
            if f["event"] < 1.3: solos[c] = solos.get(c, 0) + 1
        for c in f["support"]:
            eq[c] = min(P["EQ_CAP"], max(.3, eq.get(c, dflt) + .05 + .06*s_eff))
        for c in f["tease"]:
            eq[c] = min(P["EQ_CAP"], eq.get(c, dflt) + .03)
        out.append(dict(name=f["name"], q=q, open=opening, ww=ww, legs=legs, mom=mom,
                        eq={c: round(eq.get(c, dflt), 2) for c in L}))
    return out

def pct(xs, p): return sorted(xs)[int(p * (len(xs) - 1))]

def stats(films, scores, eq, n=300, seed=7, dc=False, pins=None):
    rng = random.Random(seed)
    runs = [run_slate(films, scores, eq, rng, pins, dc=dc) for _ in range(n)]
    res = []
    for i in range(len(films)):
        w = [r[i]["ww"] for r in runs]; o = [r[i]["open"] for r in runs]
        res.append(dict(w10=pct(w, .1), w50=pct(w, .5), w90=pct(w, .9), o50=pct(o, .5)))
    return res, runs

# ===== 4. COMPS: (name, leads, support, event, DOMESTIC OPENING $M, WORLDWIDE $M) =====
# Openings and grosses are from memory -> have Claude Code VERIFY every number on Box Office Mojo.
MCU = [
 ("Iron Man",["Iron Man"],[],1.0,98.6,585),("The Incredible Hulk",["Hulk"],[],1.0,55.4,265),
 ("Iron Man 2",["Iron Man"],["Black Widow"],1.0,128.1,624),("Thor",["Thor"],[],1.0,65.7,449),
 ("Captain America",["Captain America"],[],1.0,65.1,371),
 ("The Avengers",["Iron Man","Thor","Captain America","Hulk"],["Black Widow"],1.6,207.4,1520),
 ("Iron Man 3",["Iron Man"],[],1.0,174.1,1215),("Thor 2",["Thor"],[],1.0,85.7,645),
 ("Cap 2",["Captain America"],["Black Widow"],1.0,95.0,714),("Guardians",["Star-Lord"],[],1.0,94.3,773),
 ("Avengers 2",["Iron Man","Thor","Captain America","Hulk"],[],1.5,191.3,1405),
 ("Ant-Man",["Ant-Man"],[],1.0,57.2,519),
 ("Civil War",["Iron Man","Captain America"],["Spider-Man","Black Panther"],1.3,179.1,1153),
 ("Doctor Strange",["Doctor Strange"],[],1.0,85.1,677),("Guardians 2",["Star-Lord"],[],1.0,146.5,863),
 ("Homecoming",["Spider-Man"],["Iron Man"],1.0,117.0,880),("Ragnarok",["Thor"],["Hulk"],1.0,122.7,854),
 ("Black Panther",["Black Panther"],[],1.0,202.0,1347),
 ("Infinity War",["Iron Man","Thor","Captain America","Star-Lord"],["Black Panther"],1.7,257.7,2048),
 ("Ant-Man 2",["Ant-Man"],[],1.0,75.8,623),("Captain Marvel",["Captain Marvel"],[],1.0,153.4,1128),
 ("Endgame",["Iron Man","Thor","Captain America","Hulk"],["Captain Marvel"],1.9,357.1,2799),
 ("Far From Home",["Spider-Man"],[],1.0,92.6,1132)]
# Score from PRE-RELEASE info only; I have hindsight, so re-score blind if you can.
MCU_SC = [(4,4,3,3,4,1,2),(3,3,2,2,3,1,3),(3,4,3,3,2,2,2),(3,4,3,3,3,1,2),(3,3,2,3,3,1,3),
 (5,5,3,4,4,3,3),(4,4,3,3,3,2,2),(3,3,2,2,2,2,2),(4,4,3,3,3,2,2),(3,4,2,3,5,1,4),
 (4,4,4,3,3,3,2),(3,3,2,3,4,1,3),(5,4,3,4,3,3,3),(4,5,3,3,4,1,3),(4,4,3,3,3,2,2),
 (4,4,3,3,3,2,2),(4,4,3,3,5,2,3),(4,4,3,4,4,2,3),(5,5,5,4,3,4,3),(3,3,2,3,3,3,2),
 (4,4,3,3,3,3,3),(5,5,5,5,3,5,3),(4,4,4,4,3,3,2)]
MCU_EQ = {"Iron Man":1.0,"Thor":.8,"Captain America":.8,"Hulk":.7,"Black Widow":.7,"Star-Lord":.5,
          "Ant-Man":.5,"Doctor Strange":.5,"Spider-Man":1.0,"Black Panther":.6,"Captain Marvel":.5}

SW = [("Force Awakens",["Rey","Han Solo"],[],1.8,247.9,2068),("Rogue One",["Jyn"],[],1.0,155.1,1056),
      ("Last Jedi",["Rey","Luke"],[],1.7,220.0,1332),("Solo",["Han Solo"],[],1.0,84.4,393),
      ("Rise of Skywalker",["Rey"],[],1.6,177.4,1077)]
SW_SC = [(5,5,3,4,3,3,2),(3,4,3,3,4,2,3),(4,4,3,4,3,3,3),(3,3,2,2,3,2,4),(4,5,3,3,2,4,3)]
SW_EQ = {"Rey":.8,"Han Solo":.9,"Luke":.9,"Jyn":.5}

# HELD OUT: never used in fitting
FF = [("Fast Five",["Dom","Brian"],[],1.0,86.2,626),("Fast & Furious 6",["Dom","Brian"],["Hobbs"],1.0,97.4,789),
      ("Furious 7",["Dom","Brian"],["Hobbs","Shaw"],1.3,147.2,1515),
      ("Fate of the Furious",["Dom"],["Hobbs","Shaw"],1.0,98.8,1236),
      ("Hobbs & Shaw",["Hobbs","Shaw"],[],1.0,60.0,760)]
FF_SC = [(4,4,3,3,3,2,2),(4,4,3,3,3,2,2),(5,4,3,4,3,2,3),(4,4,3,3,3,2,3),(3,3,3,3,4,2,3)]
FF_EQ = {"Dom":.9,"Brian":.8,"Hobbs":.7,"Shaw":.6}

def pack(rows, sc, eq):
    films = [F(r[0], r[1], r[3], support=r[2]) for r in rows]
    return dict(films=films, sc={r[0]: s for r, s in zip(rows, sc)}, eq=eq,
                op=[r[4] for r in rows], ww=[r[5] for r in rows])
SETS = {"MCU": pack(MCU, MCU_SC, MCU_EQ), "SW": pack(SW, SW_SC, SW_EQ), "FF": pack(FF, FF_SC, FF_EQ)}

# ===== 5. FIT + REPORT =====
def loss(keys, n=200):
    errs, above, below, N = [], 0, 0, 0
    for k in keys:
        S = SETS[k]
        st, _ = stats(S["films"], S["sc"], S["eq"], n=n)
        for s, aw, ao in zip(st, S["ww"], S["op"]):
            errs += [abs(math.log(s["w50"] / aw)), abs(math.log(s["o50"] / ao))]
            above += aw > s["w90"]; below += aw < s["w10"]; N += 1
    # error + tail calibration: ~10% of actuals should land above p90 and ~10% below p10
    return sum(errs)/len(errs) + 2*(abs(above/N - .1) + abs(below/N - .1))

def fit(keys=("MCU", "SW"), iters=400, seed=0):
    rng, best = random.Random(seed), (9, None)
    for _ in range(iters):
        for k in FIT_KEYS: P[k] = rng.uniform(*FIT_RANGE[k])
        l = loss(keys)
        if l < best[0]: best = (l, {k: P[k] for k in FIT_KEYS})
    P.update(best[1])
    print("Fitted:", {k: round(v, 3) for k, v in best[1].items()}, f"| loss {best[0]:.3f}")

def report(title, key):
    S = SETS[key]
    st, _ = stats(S["films"], S["sc"], S["eq"], n=2000)
    print(f"\n== {title} ==\n{'Film':24}{'open':>7}{'(act)':>7}{'WW':>7}{'(act)':>7}{'err':>6}  in p10-p90")
    errs = []
    for f, s, ao, aw in zip(S["films"], st, S["op"], S["ww"]):
        errs.append(s["w50"]/aw - 1)
        inband = "yes" if s["w10"] <= aw <= s["w90"] else "NO"
        print(f"{f['name']:24}{s['o50']:7.0f}{ao:7.0f}{s['w50']:7.0f}{aw:7.0f}{errs[-1]:6.0%}  {inband}")
    mae = sum(abs(x) for x in errs)/len(errs)
    print(f"Mean abs WW error: {mae:.0%} | model total {sum(s['w50'] for s in st):,.0f} vs actual {sum(S['ww']):,.0f}")
    return mae

# ===== 6. DC SLATE (no hand-typed bases; fame + rubric + events differentiate) =====
LG = ["Superman","Batman","Wonder Woman","Flash","Aquaman","Green Lantern"]
TT = ["Nightwing","Raven","Starfire","Beast Boy","Cyborg"]
DC_EQ = {"Superman":1.1,"Batman":1.2,"Wonder Woman":1.0,"Flash":.8,"Aquaman":.8,"Green Lantern":.7,
 "Martian Manhunter":.6,"Green Arrow":.6,"Deathstroke":.6,"Shazam":.6,"Cyborg":.6,"Nightwing":.6,
 "Raven":.5,"Starfire":.5,"Beast Boy":.5,"Orion":.5,"Mister Miracle":.5,"Barda":.5,"Joker":1.2,
 "Lex Luthor":.9,"Sinestro":.6,"Zod":.8,"Reverse Flash":.6,"Ra's al Ghul":.7}
DC = [
 F("Superman",["Superman"],tease=["Batman"]),
 F("Batman",["Batman"],tease=["Joker","Superman"]),
 F("Wonder Woman",["Wonder Woman"],tease=["Batman"]),
 F("Superman 2: World's Finest",["Superman","Batman"],1.15,support=["Lex Luthor"]),
 F("Green Lantern and Martian Manhunter",["Green Lantern","Martian Manhunter"],tease=["Sinestro"]),
 F("Justice League",["Superman","Batman","Wonder Woman","Flash"],1.6,support=["Green Lantern","Martian Manhunter"]),
 F("The Flash",["Flash"],support=["Batman"]),
 F("Superman 3",["Superman","Wonder Woman"],1.1),
 F("Aquaman",["Aquaman"]),
 F("Batman 2",["Batman"],tease=["Deathstroke"]),
 F("Green Arrow vs. Deathstroke",["Green Arrow","Deathstroke"],1.05,support=["Batman"]),
 F("JL: Sinestro Corps War",LG[:3]+["Flash","Green Lantern"],1.5,support=["Aquaman","Martian Manhunter","Sinestro"]),
 F("Wonder Woman 2",["Wonder Woman"],support=["Superman"]),
 F("Shazam!",["Shazam"],support=["Superman"]),
 F("Superman 4",["Superman"],support=["Zod"]),
 F("The Flash 2",["Flash"],support=["Reverse Flash"]),
 F("New Gods",["Orion","Mister Miracle"],1.3,support=["Superman","Batman","Wonder Woman","Flash"]),
 F("Teen Titans",TT,support=["Batman"]),
 F("JL: Tower of Babel",LG,1.4,support=["Ra's al Ghul"]),
 F("Batman 3",["Batman"],1.15,support=["Joker"]),
 F("Aquaman 2",["Aquaman","Wonder Woman"],1.05),
 F("New Gods 2: Apokolips",["Orion","Mister Miracle","Barda"]),
 F("Green Arrow 2",["Green Arrow","Deathstroke"]),
 F("Wonder Woman 3",["Wonder Woman"],1.1),
 F("Green Lantern: Blackest Night",["Green Lantern"],1.3,support=["Sinestro"]),
 F("Superman 5: Doomsday",["Superman"],1.5,support=["Lex Luthor"]),
 F("Teen Titans 2",TT+["Green Arrow"]),
 F("New Gods 3: Fall of New Genesis",["Orion","Mister Miracle","Barda"],1.3,
   support=["Green Lantern","Wonder Woman","Martian Manhunter","Flash","Cyborg","Batman"]),
 F("Cyborg",["Cyborg"]),
 F("JL: Anti-Life (Part 1)",["Batman","Wonder Woman","Flash","Aquaman","Cyborg","Green Lantern"],1.7),
 F("JL: Omega (Part 2)",LG+["Cyborg"],1.9,support=["Deathstroke","Mister Miracle","Barda"]),
]
DC_SC_LIST = [(5,4,3,4,4,1,2),(4,4,3,3,3,1,2),(4,4,2,3,4,1,2),(5,4,3,3,5,2,2),(3,3,2,3,4,2,3),
 (5,5,3,4,3,3,3),(4,5,2,3,5,2,2),(4,4,3,3,3,2,2),(3,5,3,3,3,1,3),(3,3,2,3,2,2,2),
 (3,4,4,4,3,4,3),(4,5,4,3,4,3,3),(4,5,3,4,3,2,2),(5,3,2,3,5,1,2),(5,4,4,4,3,2,2),
 (3,4,3,4,2,2,3),(3,5,5,4,4,3,4),(3,3,2,3,4,2,3),(5,3,3,4,3,4,3),(4,4,5,4,3,3,2),
 (3,4,3,2,2,2,2),(4,4,3,3,5,4,3),(3,3,2,4,2,5,3),(3,3,3,4,2,3,3),(4,5,3,4,4,3,3),
 (5,5,3,5,4,2,3),(3,4,2,3,3,3,2),(3,5,4,4,4,5,3),(3,3,2,3,3,4,3),(4,4,5,5,4,5,4),(4,5,5,5,3,5,4)]
assert len(DC) == len(DC_SC_LIST) == 31
DC_S = {f["name"]: s for f, s in zip(DC, DC_SC_LIST)}
# v3 rescores: the optimistic films lose a point (so the slate isn't skewed toward "great")
DC_S.update({"Cyborg": (3,3,2,2,3,4,3), "Green Arrow 2": (3,3,2,3,2,5,3),
             "The Flash 2": (3,4,3,3,2,2,3), "Aquaman 2": (3,4,3,2,2,2,3),
             "Batman 2": (3,3,2,3,2,2,3)})
CHAPTERS = [("Ch1",6),("Ch2",6),("Ch3",7),("Ch4",12)]
SUPERMAN_2025 = 615   # real cold-start DC anchor ($M WW), from memory: VERIFY

# ===== 7. OUTPUT =====
def walkthrough():
    res = run_slate(DC, DC_S, DC_EQ, det=True, dc=True)
    i, grand = 0, 0
    for ch, k in CHAPTERS:
        sub = 0; print(f"\n-- {ch} --")
        for r in res[i:i+k]:
            sub += r["ww"]
            print(f"{r['name']:36}{r['q']:>6} open {r['open']:5.0f} WW {r['ww']:6.0f} "
                  f"{r['legs']:13} mom {r['mom']:+.2f} eq {r['eq']}")
        print(f"{ch} subtotal: {sub:,.0f}"); grand += sub; i += k
    print(f"\nWalkthrough total: {grand:,.0f}")

def monte_carlo(n=5000, pins=None, seed=1, show=True):
    _, runs = stats(DC, DC_S, DC_EQ, n=n, seed=seed, dc=True, pins=pins)
    tot = sorted(sum(x["ww"] for x in r) for r in runs)
    bil = sum(sum(x["ww"] >= 1000 for x in r) for r in runs) / n
    print(f"TOTAL p10 {pct(tot,.1):,.0f} | p50 {pct(tot,.5):,.0f} | p90 {pct(tot,.9):,.0f} | avg $1B films {bil:.1f}")
    p50s = []
    if show: print(f"{'Film':36}{'p10':>7}{'p50':>7}{'p90':>7}{'P>=1B':>7}")
    for i, f in enumerate(DC):
        g = [r[i]["ww"] for r in runs]; p50s.append(pct(g, .5))
        if show:
            print(f"{f['name']:36}{pct(g,.1):7.0f}{pct(g,.5):7.0f}{pct(g,.9):7.0f}{sum(x>=1000 for x in g)/len(g):7.0%}")
    return dict(total=pct(tot, .5), p50s=p50s, runs=runs)

def scenarios():
    S = {"a) base": {}, "b) weak Superman": {"Superman": "bad"},
         "c) GL&MM hit": {"Green Lantern and Martian Manhunter": "great"},
         "d) all great": {f["name"]: "great" for f in DC},
         "e) Doomsday + Anti-Life flop": {"Superman 5: Doomsday": "bad", "JL: Anti-Life (Part 1)": "bad"}}
    out = {}
    for label, pins in S.items():
        print(f"\n### {label}"); out[label] = monte_carlo(n=3000, pins=pins, show=False)["total"]
    return out

def checks(ff_mae, mc, flop_total):
    grades = [x["q"] for r in mc["runs"] for x in r]
    bad, great = grades.count("bad")/len(grades), grades.count("great")/len(grades)
    drop = 1 - flop_total / mc["total"]
    s1 = mc["p50s"][0]
    print("\n===== CHECKS BEFORE TRUSTING A DC NUMBER =====")
    print(f"Holdout (Fast & Furious) WW error < 40%:  {'PASS' if ff_mae < .40 else 'FAIL'} ({ff_mae:.0%})")
    print(f"No film p50 above $2.6B:                  {'PASS' if max(mc['p50s']) < 2600 else 'FAIL'} ({max(mc['p50s']):,.0f})")
    print(f"Double flop cuts total by more than 7%:   {'PASS' if drop > .07 else 'FAIL'} ({drop:.0%})  [threshold is arbitrary]")
    print(f"Random-run grades balanced (bad 12-25%, great <= 1.5x bad): "
          f"{'PASS' if .12 <= bad <= .25 and great <= 1.5*bad else 'FAIL'} (bad {bad:.0%}, great {great:.0%})")
    print(f"Superman p50 within 20% of ${SUPERMAN_2025}M:    "
          f"{'PASS' if abs(s1/SUPERMAN_2025 - 1) <= .20 else 'FAIL'} ({s1:,.0f})  <- independent anchor, not fitted")

if __name__ == "__main__":
    fit(("MCU", "SW"))                              # fit on MCU + Star Wars only
    report("MCU (in-sample)", "MCU")
    report("STAR WARS (in-sample)", "SW")
    ff = report("FAST & FURIOUS (HELD OUT)", "FF")
    walkthrough()
    mc = monte_carlo()
    sc = scenarios()
    checks(ff, mc, sc["e) Doomsday + Anti-Life flop"])
