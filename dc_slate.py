import random

# ============ 1. PARAMETERS (calibration adjusts ERA) ============
P = dict(ERA=1.0, INTL=2.2, FATIGUE=0.96, MOM_CAP=0.4, EQ_CAP=2.0, MOM_DECAY=0.8)
LEGS  = {"bad": 2.2, "ok": 2.6, "good": 2.9, "great": 3.3}   # total / opening
SCORE = {"bad": -1, "ok": 0, "good": 1, "great": 2}

def F(name, leads, base, event=1.0, support=(), tease=()):
    return dict(name=name, leads=list(leads), base=base, event=event,
                support=list(support), tease=list(tease))

# ============ 2. PLOT RUBRIC -> MODEL INPUTS ============
# Scores: (P pitch, S set piece, V villain, K stakes, G freshness, H homework, R risk)
def derive(sc):
    Pp, S, V, K, G, H, R = sc
    mkt  = 1 + .06*(Pp-3.5) + .04*(V-3) + .03*(S-3.5) + .02*(G-3)
    qi   = .20*(K-3) + .12*(S-3) + .10*(G-3) + .08*(Pp-3) - .20*(R-2.5)
    dep  = .4 + .15*H                    # reliance on universe momentum
    gate = 1 - .03*max(0, H-2)           # casual penalty for homework
    return mkt, qi, dep, gate

def grade(z):
    return "bad" if z < -.7 else "ok" if z < .1 else "good" if z < .8 else "great"

# ============ 3. ENGINE ============
def run_slate(films, scores, init_eq, rng=None, pins=None, det=False):
    pins, mom, eq, solos, out = pins or {}, 0.0, dict(init_eq), {}, []
    for f in films:
        mkt, qi, dep, gate = derive(scores[f["name"]])
        q = pins.get(f["name"]) or grade(qi if det else qi + rng.gauss(0, .8))
        L = f["leads"]
        e = sum(eq.get(c, .6) for c in L) / len(L)
        prior = sum(solos.get(c, 0) for c in L) / len(L)
        noise = 1 if det else max(.5, rng.gauss(1, .12))
        opening = (f["base"] * (1 + mom*dep) * e * mkt * gate * f["event"]
                   * P["FATIGUE"]**prior * P["ERA"] * noise)
        ww = opening * LEGS[q] * P["INTL"]
        legs = "front-loaded" if (q in ("bad", "ok") or (f["event"] >= 1.5 and q != "great")) else "leggy"
        # --- update universe state ---
        s, w = SCORE[q], (1.5 if f["event"] >= 1.3 else 1.0)
        mom = max(-P["MOM_CAP"], min(P["MOM_CAP"], P["MOM_DECAY"]*mom + .1*s*w))
        for c in L:
            eq[c] = min(P["EQ_CAP"], max(.5, eq.get(c, .6) + .05*s))
            if f["event"] < 1.3: solos[c] = solos.get(c, 0) + 1
        for c in f["support"]:
            eq[c] = min(P["EQ_CAP"], max(.5, eq.get(c, .6) + .05 + .06*s))
        for c in f["tease"]:
            eq[c] = min(P["EQ_CAP"], eq.get(c, .6) + .03)
        out.append(dict(name=f["name"], q=q, open=opening, ww=ww, legs=legs,
                        mom=mom, eq={c: round(eq.get(c, .6), 2) for c in L}))
    return out

def medians(films, scores, init_eq, n=2000, pins=None, seed=7):
    rng = random.Random(seed)
    runs = [run_slate(films, scores, init_eq, rng, pins) for _ in range(n)]
    return [sorted(r[i]["ww"] for r in runs)[n//2] for i in range(len(films))]

# ============ 4. MCU CALIBRATION ============
# (name, leads, support, base, event, actual WW $M) -- VERIFY grosses on Box Office Mojo
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
 ("Far From Home",["Spider-Man"],[],55,1.0,1132),
]
# Score from PRE-RELEASE info only. Rescore anything contaminated by hindsight.
MCU_SC = [(4,4,3,3,4,1,2),(3,3,2,2,3,1,3),(3,4,3,3,2,2,2),(3,4,3,3,3,1,2),(3,3,2,3,3,1,3),
 (5,5,3,4,4,3,3),(4,4,3,3,3,2,2),(3,3,2,2,2,2,2),(4,4,3,3,3,2,2),(3,4,2,3,5,1,4),
 (4,4,4,3,3,3,2),(3,3,2,3,4,1,3),(5,4,3,4,3,3,3),(4,5,3,3,4,1,3),(4,4,3,3,3,2,2),
 (4,4,3,3,3,2,2),(4,4,3,3,5,2,3),(4,4,3,4,4,2,3),(5,5,5,4,3,4,3),(3,3,2,3,3,3,2),
 (4,4,3,3,3,3,3),(5,5,5,5,3,5,3),(4,4,4,4,3,3,2)]
assert len(MCU) == len(MCU_SC)
MCU_EQ = {"Iron Man":1.0,"Thor":.8,"Captain America":.8,"Hulk":.7,"Black Widow":.7,
          "Star-Lord":.5,"Ant-Man":.5,"Doctor Strange":.5,"Spider-Man":1.0,
          "Black Panther":.6,"Captain Marvel":.5}
MCU_F  = [F(n, L, b, e, support=S) for n, L, S, b, e, a in MCU]
MCU_S  = {m[0]: sc for m, sc in zip(MCU, MCU_SC)}
MCU_A  = [m[5] for m in MCU]

def report(title, films, scores, init_eq, actual, scale=None):
    med = medians(films, scores, init_eq)
    if scale is None: scale = sum(actual) / sum(med)
    print(f"\n== {title} ==  model {sum(med)*scale:,.0f} vs actual {sum(actual):,.0f}  (scalar {scale:.2f})")
    errs = []
    for f, m, a in zip(films, med, actual):
        errs.append(m*scale/a - 1)
        print(f"{f['name']:26}{m*scale:8.0f}{a:8.0f}{errs[-1]:7.0%}")
    print(f"Mean abs film error: {sum(abs(x) for x in errs)/len(errs):.0%}")
    return scale

def calibrate():
    P["ERA"] *= report("MCU CALIBRATION", MCU_F, MCU_S, MCU_EQ, MCU_A)
    print(f"Fitted ERA = {P['ERA']:.3f}")

# ============ 5. HOLDOUT (do NOT retune) ============
# Star Wars placeholder: verify grosses, rescore pre-release, adjust bases.
SW = [("Force Awakens",["Rey","Han Solo"],[],90,1.8,2068),("Rogue One",["Jyn"],[],70,1.0,1056),
      ("Last Jedi",["Rey","Luke"],[],90,1.7,1332),("Solo",["Han Solo"],[],55,1.0,393),
      ("Rise of Skywalker",["Rey"],[],85,1.6,1077)]
SW_SC = [(5,5,3,4,3,3,2),(3,4,3,3,4,2,3),(4,4,3,4,3,3,3),(3,3,2,2,3,2,4),(4,5,3,3,2,4,3)]
def holdout():
    f = [F(n, L, b, e, support=S) for n, L, S, b, e, a in SW]
    sc = {x[0]: s for x, s in zip(SW, SW_SC)}
    report("HOLDOUT: STAR WARS (no retuning)", f, sc, {"Rey":.8,"Han Solo":.9,"Luke":.9,"Jyn":.5},
           [x[5] for x in SW], scale=1.0)   # scale fixed at 1.0 on purpose

# ============ 6. DC SLATE ============
LEAGUE = ["Superman","Batman","Wonder Woman","Flash","Aquaman","Green Lantern"]
DC_EQ = {"Superman":1.1,"Batman":1.2,"Wonder Woman":1.0,"Flash":.8,"Aquaman":.8,
 "Green Lantern":.7,"Martian Manhunter":.6,"Green Arrow":.6,"Deathstroke":.6,"Shazam":.6,
 "Cyborg":.6,"Nightwing":.6,"Raven":.5,"Starfire":.5,"Beast Boy":.5,"Orion":.5,
 "Mister Miracle":.5,"Barda":.5,"Joker":1.2,"Lex Luthor":.9,"Sinestro":.6,"Zod":.8,
 "Reverse Flash":.6,"Ra's al Ghul":.7}
TT = ["Nightwing","Raven","Starfire","Beast Boy","Cyborg"]
DC = [
 F("Superman",["Superman"],80,tease=["Batman"]),
 F("Batman",["Batman"],90,tease=["Joker","Superman"]),
 F("Wonder Woman",["Wonder Woman"],62,tease=["Batman"]),
 F("Superman 2: World's Finest",["Superman","Batman"],70,1.15,support=["Lex Luthor"]),
 F("Green Lantern and Martian Manhunter",["Green Lantern","Martian Manhunter"],40,tease=["Sinestro"]),
 F("Justice League",["Superman","Batman","Wonder Woman","Flash"],70,1.6,support=["Green Lantern","Martian Manhunter"]),
 F("The Flash",["Flash"],52,support=["Batman"]),
 F("Superman 3",["Superman","Wonder Woman"],72,1.1),
 F("Aquaman",["Aquaman"],58),
 F("Batman 2",["Batman"],88,tease=["Deathstroke"]),
 F("Green Arrow vs. Deathstroke",["Green Arrow","Deathstroke"],30,1.05,support=["Batman"]),
 F("JL: Sinestro Corps War",LEAGUE[:3]+["Flash","Green Lantern"],70,1.5,support=["Aquaman","Martian Manhunter","Sinestro"]),
 F("Wonder Woman 2",["Wonder Woman"],62,support=["Superman"]),
 F("Shazam!",["Shazam"],40,support=["Superman"]),
 F("Superman 4",["Superman"],70,support=["Zod"]),
 F("The Flash 2",["Flash"],48,support=["Reverse Flash"]),
 F("New Gods",["Orion","Mister Miracle"],55,1.3,support=["Superman","Batman","Wonder Woman","Flash"]),
 F("Teen Titans",TT,36,support=["Batman"]),
 F("JL: Tower of Babel",LEAGUE,66,1.4,support=["Ra's al Ghul"]),
 F("Batman 3",["Batman"],92,1.15,support=["Joker"]),
 F("Aquaman 2",["Aquaman","Wonder Woman"],56,1.05),
 F("New Gods 2: Apokolips",["Orion","Mister Miracle","Barda"],40),
 F("Green Arrow 2",["Green Arrow","Deathstroke"],30),
 F("Wonder Woman 3",["Wonder Woman"],58,1.1),
 F("Green Lantern: Blackest Night",["Green Lantern"],55,1.3,support=["Sinestro"]),
 F("Superman 5: Doomsday",["Superman"],85,1.5,support=["Lex Luthor"]),
 F("Teen Titans 2",TT+["Green Arrow"],36),
 F("New Gods 3: Fall of New Genesis",["Orion","Mister Miracle","Barda"],55,1.3,
   support=["Green Lantern","Wonder Woman","Martian Manhunter","Flash","Cyborg","Batman"]),
 F("Cyborg",["Cyborg"],38),
 F("JL: Anti-Life (Part 1)",["Batman","Wonder Woman","Flash","Aquaman","Cyborg","Green Lantern"],75,1.7),
 F("JL: Omega (Part 2)",LEAGUE+["Cyborg"],70,1.9,support=["Deathstroke","Mister Miracle","Barda"]),
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

# ============ 7. OUTPUT ============
def walkthrough(pins=None):
    """Deterministic expected path: film-by-film, with equity tracking."""
    res = run_slate(DC, DC_S, DC_EQ, det=True, pins=pins)
    i, grand = 0, 0
    for ch, k in CHAPTERS:
        sub = 0
        print(f"\n-- {ch} --")
        for r in res[i:i+k]:
            sub += r["ww"]
            print(f"{r['name']:36}{r['q']:>6} open {r['open']:5.0f}  WW {r['ww']:6.0f}  "
                  f"{r['legs']:13} mom {r['mom']:+.2f}  eq {r['eq']}")
        print(f"{ch} subtotal: {sub:,.0f}"); grand += sub; i += k
    print(f"\nWalkthrough total: {grand:,.0f}  (chapter subtotals re-added: {sum(r['ww'] for r in res):,.0f})")

def monte_carlo(n=5000, pins=None, seed=1, show_films=True):
    rng = random.Random(seed)
    runs = [run_slate(DC, DC_S, DC_EQ, rng, pins) for _ in range(n)]
    tot = sorted(sum(x["ww"] for x in r) for r in runs)
    bil = sum(sum(x["ww"] >= 1000 for x in r) for r in runs) / n
    print(f"TOTAL p10 {tot[n//10]:,.0f} | p50 {tot[n//2]:,.0f} | p90 {tot[9*n//10]:,.0f} | avg $1B films {bil:.1f}")
    if show_films:
        print(f"{'Film':36}{'p10':>7}{'p50':>7}{'p90':>7}{'P>=1B':>7}")
        for i, f in enumerate(DC):
            g = sorted(r[i]["ww"] for r in runs)
            print(f"{f['name']:36}{g[n//10]:7.0f}{g[n//2]:7.0f}{g[9*n//10]:7.0f}{sum(x>=1000 for x in g)/n:7.0%}")
    return tot[n//2]

def scenarios():
    S = {
     "a) base": {},
     "b) weak Superman": {"Superman": "bad"},
     "c) GL&MM hit": {"Green Lantern and Martian Manhunter": "great"},
     "d) all great": {f["name"]: "great" for f in DC},
     "e) Doomsday + Anti-Life flop": {"Superman 5: Doomsday": "bad", "JL: Anti-Life (Part 1)": "bad"},
    }
    for label, pins in S.items():
        print(f"\n### {label}")
        monte_carlo(n=3000, pins=pins, show_films=False)

if __name__ == "__main__":
    calibrate()        # Step 2: fit on MCU
    holdout()          # Step 3: Star Wars, no retuning
    walkthrough()      # Step 4: deterministic film-by-film path + equity
    monte_carlo()      # Step 5: 5,000 slates
    scenarios()        # Step 6: what-if runs
