import random, math

# ===== 1. PARAMETERS (the fit step overwrites the four marked FIT) =====
P = dict(ERA=1.0, INTL=2.2, FATIGUE=0.96, MOM_DECAY=0.8,   # FIT
         MOM_CAP=0.25, EQ_CAP=1.5,                         # lower caps: less stacking
         NEG_MULT=2.5,       # a flop hurts 2.5x more than a hit helps
         EVD=0.7,            # dampens team-up/event bonus
         MKT2026=0.8,        # today's smaller market (DC only)
         CEIL=2600)          # no film can pass this ($M)
LEGS  = {"bad": 2.2, "ok": 2.6, "good": 2.9, "great": 3.3}
SCORE = {"bad": -1, "ok": 0, "good": 1, "great": 2}

def F(name, leads, base, event=1.0, support=(), tease=()):
    return dict(name=name, leads=list(leads), base=base, event=event,
                support=list(support), tease=list(tease))

# ===== 2. RUBRIC -> INPUTS =====
# Scores: (P pitch, S set piece, V villain, K stakes, G freshness, H homework, R risk)
def derive(sc):
    Pp, S, V, K, G, H, R = sc
    mkt = 1 + .06*(Pp-3.5) + .04*(V-3) + .03*(S-3.5) + .02*(G-3)
    qi  = .20*(K-3) + .12*(S-3) + .10*(G-3) + .08*(Pp-3) - .20*(R-2.5)
    dep = .4 + .15*H
    gate = 1 - .03*max(0, H-2)
    return mkt, qi, dep, gate

def grade(z):
    return "bad" if z < -.7 else "ok" if z < .1 else "good" if z < .8 else "great"

# ===== 3. ENGINE =====
def run_slate(films, scores, init_eq, rng=None, pins=None, det=False, dc=False):
    pins, mom, eq, solos, out = pins or {}, 0.0, dict(init_eq), {}, []
    for f in films:
        mkt, qi, dep, gate = derive(scores[f["name"]])
        q = pins.get(f["name"]) or grade(qi if det else qi + rng.gauss(0, .8))
        L = f["leads"]
        e = sum(eq.get(c, .6) for c in L) / len(L)
        prior = sum(solos.get(c, 0) for c in L) / len(L)
        if det: noise = 1.0
        else:   # heavy tails for unknown leads: breakouts AND busts
            sig = .12 if e >= .7 else .30
            noise = rng.lognormvariate(-sig*sig/2, sig)
        ev = 1 + (f["event"] - 1) * P["EVD"]
        opening = (f["base"] * (1 + mom*dep) * e * mkt * gate * ev
                   * P["FATIGUE"]**prior * P["ERA"] * noise)
        ww = opening * LEGS[q] * P["INTL"] * (P["MKT2026"] if dc else 1)
        ww = min(P["CEIL"], ww)
        legs = "front-loaded" if (q in ("bad","ok") or (f["event"] >= 1.5 and q != "great")) else "leggy"
        s = SCORE[q]
        s_eff = s if s >= 0 else P["NEG_MULT"] * s
        w = 1.5 if f["event"] >= 1.3 else 1.0
        mom = max(-P["MOM_CAP"], min(P["MOM_CAP"], P["MOM_DECAY"]*mom + .1*s_eff*w))
        for c in L:
            eq[c] = min(P["EQ_CAP"], max(.5, eq.get(c, .6) + .05*s_eff))
            if f["event"] < 1.3: solos[c] = solos.get(c, 0) + 1
        for c in f["support"]:
            eq[c] = min(P["EQ_CAP"], max(.5, eq.get(c, .6) + .05 + .06*s_eff))
        for c in f["tease"]:
            eq[c] = min(P["EQ_CAP"], eq.get(c, .6) + .03)
        out.append(dict(name=f["name"], q=q, open=opening, ww=ww, legs=legs, mom=mom,
                        eq={c: round(eq.get(c, .6), 2) for c in L}))
    return out

def medians(films, scores, init_eq, n=500, seed=7, pins=None, dc=False):
    rng = random.Random(seed)
    runs = [run_slate(films, scores, init_eq, rng, pins, dc=dc) for _ in range(n)]
    return [sorted(r[i]["ww"] for r in runs)[n//2] for i in range(len(films))]

# ===== 4. COMPS (grosses from memory: VERIFY on Box Office Mojo) =====
def pack(rows, sc, eq):
    films = [F(n, L, b, e, support=S) for n, L, S, b, e, a in rows]
    return films, {r[0]: s for r, s in zip(rows, sc)}, eq, [r[5] for r in rows]

MCU = [
 ("Iron Man",["Iron Man"],[],45,1.0,585),("The Incredible Hulk",["Hulk"],[],38,1.0,265),
 ("Iron Man 2",["Iron Man"],["Black Widow"],55,1.0,624),("Thor",["Thor"],[],40,1.0,449),
 ("Captain America",["Captain America"],[],40,1.0,371),
 ("The Avengers",["Iron Man","Thor","Captain America","Hulk"],["Black Widow"],70,1.6,1520),
 ("Iron Man 3",["Iron Man"],[],70,1.0,1215),("Thor 2",["Thor"],[],45,1.0,645),
 ("Cap 2",["Captain America"],["Black Widow"],55,1.0,714),("Guardians",["Star-Lord"],[],38,1.0,773),
 ("Avengers 2",["Iron Man","Thor","Captain America","Hulk"],[],75,1.5,1405),
 ("Ant-Man",["Ant-Man"],[],35,1.0,519),
 ("Civil War",["Iron Man","Captain America"],["Spider-Man","Black Panther"],75,1.3,1153),
 ("Doctor Strange",["Doctor Strange"],[],45,1.0,677),("Guardians 2",["Star-Lord"],[],55,1.0,863),
 ("Homecoming",["Spider-Man"],["Iron Man"],50,1.0,880),("Ragnarok",["Thor"],["Hulk"],50,1.0,854),
 ("Black Panther",["Black Panther"],[],45,1.0,1347),
 ("Infinity War",["Iron Man","Thor","Captain America","Star-Lord"],["Black Panther"],80,1.7,2048),
 ("Ant-Man 2",["Ant-Man"],[],40,1.0,623),("Captain Marvel",["Captain Marvel"],[],55,1.0,1128),
 ("Endgame",["Iron Man","Thor","Captain America","Hulk"],["Captain Marvel"],85,1.9,2799),
 ("Far From Home",["Spider-Man"],[],55,1.0,1132)]
MCU_SC = [(4,4,3,3,4,1,2),(3,3,2,2,3,1,3),(3,4,3,3,2,2,2),(3,4,3,3,3,1,2),(3,3,2,3,3,1,3),
 (5,5,3,4,4,3,3),(4,4,3,3,3,2,2),(3,3,2,2,2,2,2),(4,4,3,3,3,2,2),(3,4,2,3,5,1,4),
 (4,4,4,3,3,3,2),(3,3,2,3,4,1,3),(5,4,3,4,3,3,3),(4,5,3,3,4,1,3),(4,4,3,3,3,2,2),
 (4,4,3,3,3,2,2),(4,4,3,3,5,2,3),(4,4,3,4,4,2,3),(5,5,5,4,3,4,3),(3,3,2,3,3,3,2),
 (4,4,3,3,3,3,3),(5,5,5,5,3,5,3),(4,4,4,4,3,3,2)]
MCU_EQ = {"Iron Man":1.0,"Thor":.8,"Captain America":.8,"Hulk":.7,"Black Widow":.7,"Star-Lord":.5,
          "Ant-Man":.5,"Doctor Strange":.5,"Spider-Man":1.0,"Black Panther":.6,"Captain Marvel":.5}

SW = [("Force Awakens",["Rey","Han Solo"],[],90,1.8,2068),("Rogue One",["Jyn"],[],70,1.0,1056),
      ("Last Jedi",["Rey","Luke"],[],90,1.7,1332),("Solo",["Han Solo"],[],55,1.0,393),
      ("Rise of Skywalker",["Rey"],[],85,1.6,1077)]
SW_SC = [(5,5,3,4,3,3,2),(3,4,3,3,4,2,3),(4,4,3,4,3,3,3),(3,3,2,2,3,2,4),(4,5,3,3,2,4,3)]
SW_EQ = {"Rey":.8,"Han Solo":.9,"Luke":.9,"Jyn":.5}

# Third franchise, HELD OUT from fitting. Replace bases with real openings.
FF = [("Fast Five",["Dom","Brian"],[],55,1.0,626),("Fast & Furious 6",["Dom","Brian"],["Hobbs"],60,1.0,789),
      ("Furious 7",["Dom","Brian"],["Hobbs","Shaw"],75,1.3,1515),
      ("Fate of the Furious",["Dom"],["Hobbs","Shaw"],75,1.0,1236),
      ("Hobbs & Shaw",["Hobbs","Shaw"],[],50,1.0,760)]
FF_SC = [(4,4,3,3,3,2,2),(4,4,3,3,3,2,2),(5,4,3,4,3,2,3),(4,4,3,3,3,2,3),(3,3,3,3,4,2,3)]
FF_EQ = {"Dom":.9,"Brian":.8,"Hobbs":.7,"Shaw":.6}

SETS = {"MCU": pack(MCU, MCU_SC, MCU_EQ), "SW": pack(SW, SW_SC, SW_EQ), "FF": pack(FF, FF_SC, FF_EQ)}

# ===== 5. FIT + REPORT =====
def film_errors(key, n=500):
    films, sc, eq, act = SETS[key]
    med = medians(films, sc, eq, n=n)
    return films, med, act

def loss(keys, n=250):
    e = []
    for k in keys:
        _, med, act = film_errors(k, n)
        e += [abs(math.log(m / a)) for m, a in zip(med, act)]
    return sum(e) / len(e)

def fit(keys=("MCU", "SW"), iters=300):
    rng, best = random.Random(0), (9, None)
    for _ in range(iters):
        P.update(FATIGUE=rng.uniform(.9, 1), MOM_DECAY=rng.uniform(.5, .9),
                 INTL=rng.uniform(1.6, 2.6), ERA=rng.uniform(.8, 2.5))
        l = loss(keys)
        if l < best[0]: best = (l, {k: P[k] for k in ("FATIGUE","MOM_DECAY","INTL","ERA")})
    P.update(best[1])
    print("Fitted:", {k: round(v, 3) for k, v in best[1].items()}, f"| log-loss {best[0]:.3f}")

def report(title, key):
    films, med, act = film_errors(key, 2000)
    print(f"\n== {title} ==  model {sum(med):,.0f} vs actual {sum(act):,.0f}")
    errs = []
    for f, m, a in zip(films, med, act):
        errs.append(m / a - 1)
        print(f"{f['name']:26}{m:8.0f}{a:8.0f}{errs[-1]:7.0%}")
    mae = sum(abs(x) for x in errs) / len(errs)
    print(f"Mean abs film error: {mae:.0%}")
    return mae

# ===== 6. DC SLATE (bases x0.68 to sit on the MCU scale) =====
LEAGUE = ["Superman","Batman","Wonder Woman","Flash","Aquaman","Green Lantern"]
TT = ["Nightwing","Raven","Starfire","Beast Boy","Cyborg"]
DC_EQ = {"Superman":1.1,"Batman":1.2,"Wonder Woman":1.0,"Flash":.8,"Aquaman":.8,"Green Lantern":.7,
 "Martian Manhunter":.6,"Green Arrow":.6,"Deathstroke":.6,"Shazam":.6,"Cyborg":.6,"Nightwing":.6,
 "Raven":.5,"Starfire":.5,"Beast Boy":.5,"Orion":.5,"Mister Miracle":.5,"Barda":.5,"Joker":1.2,
 "Lex Luthor":.9,"Sinestro":.6,"Zod":.8,"Reverse Flash":.6,"Ra's al Ghul":.7}
BS = 0.68
DC = [
 F("Superman",["Superman"],80*BS,tease=["Batman"]),
 F("Batman",["Batman"],90*BS,tease=["Joker","Superman"]),
 F("Wonder Woman",["Wonder Woman"],62*BS,tease=["Batman"]),
 F("Superman 2: World's Finest",["Superman","Batman"],70*BS,1.15,support=["Lex Luthor"]),
 F("Green Lantern and Martian Manhunter",["Green Lantern","Martian Manhunter"],40*BS,tease=["Sinestro"]),
 F("Justice League",["Superman","Batman","Wonder Woman","Flash"],70*BS,1.6,support=["Green Lantern","Martian Manhunter"]),
 F("The Flash",["Flash"],52*BS,support=["Batman"]),
 F("Superman 3",["Superman","Wonder Woman"],72*BS,1.1),
 F("Aquaman",["Aquaman"],58*BS),
 F("Batman 2",["Batman"],88*BS,tease=["Deathstroke"]),
 F("Green Arrow vs. Deathstroke",["Green Arrow","Deathstroke"],30*BS,1.05,support=["Batman"]),
 F("JL: Sinestro Corps War",LEAGUE[:3]+["Flash","Green Lantern"],70*BS,1.5,support=["Aquaman","Martian Manhunter","Sinestro"]),
 F("Wonder Woman 2",["Wonder Woman"],62*BS,support=["Superman"]),
 F("Shazam!",["Shazam"],40*BS,support=["Superman"]),
 F("Superman 4",["Superman"],70*BS,support=["Zod"]),
 F("The Flash 2",["Flash"],48*BS,support=["Reverse Flash"]),
 F("New Gods",["Orion","Mister Miracle"],55*BS,1.3,support=["Superman","Batman","Wonder Woman","Flash"]),
 F("Teen Titans",TT,36*BS,support=["Batman"]),
 F("JL: Tower of Babel",LEAGUE,66*BS,1.4,support=["Ra's al Ghul"]),
 F("Batman 3",["Batman"],92*BS,1.15,support=["Joker"]),
 F("Aquaman 2",["Aquaman","Wonder Woman"],56*BS,1.05),
 F("New Gods 2: Apokolips",["Orion","Mister Miracle","Barda"],40*BS),
 F("Green Arrow 2",["Green Arrow","Deathstroke"],30*BS),
 F("Wonder Woman 3",["Wonder Woman"],58*BS,1.1),
 F("Green Lantern: Blackest Night",["Green Lantern"],55*BS,1.3,support=["Sinestro"]),
 F("Superman 5: Doomsday",["Superman"],85*BS,1.5,support=["Lex Luthor"]),
 F("Teen Titans 2",TT+["Green Arrow"],36*BS),
 F("New Gods 3: Fall of New Genesis",["Orion","Mister Miracle","Barda"],55*BS,1.3,
   support=["Green Lantern","Wonder Woman","Martian Manhunter","Flash","Cyborg","Batman"]),
 F("Cyborg",["Cyborg"],38*BS),
 F("JL: Anti-Life (Part 1)",["Batman","Wonder Woman","Flash","Aquaman","Cyborg","Green Lantern"],75*BS,1.7),
 F("JL: Omega (Part 2)",LEAGUE+["Cyborg"],70*BS,1.9,support=["Deathstroke","Mister Miracle","Barda"]),
]
DC_SC_LIST = [(5,4,3,4,4,1,2),(4,4,3,3,3,1,2),(4,4,2,3,4,1,2),(5,4,3,3,5,2,2),(3,3,2,3,4,2,3),
 (5,5,3,4,3,3,3),(4,5,2,3,5,2,2),(4,4,3,3,3,2,2),(3,5,3,3,3,1,3),(3,3,2,3,2,2,2),
 (3,4,4,4,3,4,3),(4,5,4,3,4,3,3),(4,5,3,4,3,2,2),(5,3,2,3,5,1,2),(5,4,4,4,3,2,2),
 (3,4,3,4,2,2,3),(3,5,5,4,4,3,4),(3,3,2,3,4,2,3),(5,3,3,4,3,4,3),(4,4,5,4,3,3,2),
 (3,4,3,2,2,2,2),(4,4,3,3,5,4,3),(3,3,2,4,2,5,3),(3,3,3,4,2,3,3),(4,5,3,4,4,3,3),
 (5,5,3,5,4,2,3),(3,4,2,3,3,3,2),(3,5,4,4,4,5,3),(3,3,2,3,3,4,3),(4,4,5,5,4,5,4),(4,5,5,5,3,5,4)]
assert len(DC) == len(DC_SC_LIST) == 31
DC_S = {f["name"]: s for f, s in zip(DC, DC_SC_LIST)}
CHAPTERS = [("Ch1",6),("Ch2",6),("Ch3",7),("Ch4",12)]

# ===== 7. OUTPUT =====
def walkthrough():
    res = run_slate(DC, DC_S, DC_EQ, det=True, dc=True)
    i, grand = 0, 0
    for ch, k in CHAPTERS:
        sub = 0
        print(f"\n-- {ch} --")
        for r in res[i:i+k]:
            sub += r["ww"]
            print(f"{r['name']:36}{r['q']:>6} open {r['open']:5.0f} WW {r['ww']:6.0f} "
                  f"{r['legs']:13} mom {r['mom']:+.2f} eq {r['eq']}")
        print(f"{ch} subtotal: {sub:,.0f}"); grand += sub; i += k
    print(f"\nWalkthrough total: {grand:,.0f}")
    return res

def monte_carlo(n=5000, pins=None, seed=1, show=True):
    rng = random.Random(seed)
    runs = [run_slate(DC, DC_S, DC_EQ, rng, pins, dc=True) for _ in range(n)]
    tot = sorted(sum(x["ww"] for x in r) for r in runs)
    bil = sum(sum(x["ww"] >= 1000 for x in r) for r in runs) / n
    print(f"TOTAL p10 {tot[n//10]:,.0f} | p50 {tot[n//2]:,.0f} | p90 {tot[9*n//10]:,.0f} | avg $1B films {bil:.1f}")
    top = 0
    if show: print(f"{'Film':36}{'p10':>7}{'p50':>7}{'p90':>7}{'P>=1B':>7}")
    for i, f in enumerate(DC):
        g = sorted(r[i]["ww"] for r in runs)
        top = max(top, g[n//2])
        if show:
            print(f"{f['name']:36}{g[n//10]:7.0f}{g[n//2]:7.0f}{g[9*n//10]:7.0f}{sum(x>=1000 for x in g)/n:7.0%}")
    return tot[n//2], top

def scenarios():
    S = {"a) base": {}, "b) weak Superman": {"Superman": "bad"},
         "c) GL&MM hit": {"Green Lantern and Martian Manhunter": "great"},
         "d) all great": {f["name"]: "great" for f in DC},
         "e) Doomsday + Anti-Life flop": {"Superman 5: Doomsday": "bad", "JL: Anti-Life (Part 1)": "bad"}}
    p50 = {}
    for label, pins in S.items():
        print(f"\n### {label}")
        p50[label] = monte_carlo(n=3000, pins=pins, show=False)[0]
    return p50

def checks(ff_mae, res, base_p50, flop_p50, top_film):
    drop = 1 - flop_p50 / base_p50
    print("\n===== PASS/FAIL BEFORE TRUSTING A DC NUMBER =====")
    print(f"Holdout (Fast & Furious) error < 40%:   {'PASS' if ff_mae < .40 else 'FAIL'} ({ff_mae:.0%})")
    print(f"No film p50 above $2.6B:                {'PASS' if top_film < 2600 else 'FAIL'} ({top_film:,.0f})")
    print(f"Double flop cuts total by more than 7%: {'PASS' if drop > .07 else 'FAIL'} ({drop:.0%})")
    nbad = sum(r["q"] == "bad" for r in res)
    print(f"Expected path has some 'bad' grades:    {'PASS' if nbad else 'FAIL'} ({nbad} of 31)")

if __name__ == "__main__":
    fit(("MCU", "SW"))                       # joint fit, NOT just one scalar
    report("MCU (in-sample)", "MCU")
    report("STAR WARS (in-sample)", "SW")
    ff_mae = report("FAST & FURIOUS (HELD OUT, never fit)", "FF")
    res = walkthrough()
    base_p50, top = monte_carlo()
    sc = scenarios()
    checks(ff_mae, res, base_p50, sc["e) Doomsday + Anti-Life flop"], top)
