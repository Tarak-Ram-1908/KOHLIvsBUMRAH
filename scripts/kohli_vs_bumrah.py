"""
11 Kohlis vs 11 Bumrahs: ODI Monte Carlo from Cricsheet ball-by-ball data.

Usage:  python -I scripts/kohli_vs_bumrah.py data/odis_json [n_matches]

Rules used everywhere:
  * Men's ODIs only.
  * Per-delivery outcome categories: 0,1,2,3,4,5,6, W, wd, nb.
    - Any delivery with a wide -> 'wd'; with a no-ball -> 'nb' (unless a wicket fell).
    - Any dismissal on the delivery (run-outs included, retirements excluded) -> 'W'.
    - Otherwise the batter's runs off the bat (byes / leg-byes count as a dot).
  * Probabilities are shares of ALL deliveries (legal + wd + nb), so they sum to 1.
  * In the simulation wd / nb add 1 run and are re-bowled; W costs a ball.
"""
import json, os, random, sys
from collections import Counter, defaultdict

KOHLI, BUMRAH = "V Kohli", "JJ Bumrah"
CATS = ["0", "1", "2", "3", "4", "5", "6", "W", "wd", "nb"]
NOT_WICKETS = {"retired hurt", "retired not out"}
NOT_BOWLER_WKTS = {"run out", "retired hurt", "retired not out", "obstructing the field", "timed out"}
LEAGUE_FROM_YEAR = 2008


def classify(d):
    ex = d.get("extras", {})
    if any(w.get("kind") not in NOT_WICKETS for w in d.get("wickets", [])):
        return "W"
    if "wides" in ex:
        return "wd"
    if "noballs" in ex:
        return "nb"
    return str(min(d["runs"]["batter"], 6))


def parse(folder):
    sets = {k: Counter() for k in ("kohli_bat", "bumrah_bowl", "bumrah_bat", "kohli_bowl", "league")}
    bat = {p: dict(runs=0, bf=0, outs=0, inns=set(), hs=defaultdict(int), fours=0, sixes=0, matches=set()) for p in (KOHLI, BUMRAH)}
    bowl = {p: dict(balls=0, runs=0, wkts=0) for p in (KOHLI, BUMRAH)}
    for fn in os.listdir(folder):
        if not fn.endswith(".json"):
            continue
        with open(os.path.join(folder, fn), encoding="utf-8") as fh:
            m = json.load(fh)
        info = m["info"]
        if info.get("gender") != "male":
            continue
        year = int(str(info["dates"][0])[:4])
        for p in (KOHLI, BUMRAH):
            if any(p in pl for pl in info.get("players", {}).values()):
                bat[p]["matches"].add(fn)
        for ii, inn in enumerate(m.get("innings", [])):
            for ov in inn.get("overs", []):
                for d in ov["deliveries"]:
                    c = classify(d)
                    ex = d.get("extras", {})
                    if year >= LEAGUE_FROM_YEAR:
                        sets["league"][c] += 1
                    b, bw = d["batter"], d["bowler"]
                    if b == KOHLI: sets["kohli_bat"][c] += 1
                    if b == BUMRAH: sets["bumrah_bat"][c] += 1
                    if bw == KOHLI: sets["kohli_bowl"][c] += 1
                    if bw == BUMRAH: sets["bumrah_bowl"][c] += 1
                    # career totals for the Statsguru check
                    for p in (KOHLI, BUMRAH):
                        s = bat[p]
                        if b == p:
                            r = d["runs"]["batter"]
                            s["runs"] += r; s["hs"][(fn, ii)] += r; s["inns"].add((fn, ii))
                            if "wides" not in ex: s["bf"] += 1
                            if r == 4 and not d["runs"].get("non_boundary"): s["fours"] += 1
                            if r == 6: s["sixes"] += 1
                        if d.get("non_striker") == p:
                            s["inns"].add((fn, ii)); s["hs"][(fn, ii)] += 0
                        for w in d.get("wickets", []):
                            if w["player_out"] == p and w["kind"] not in NOT_WICKETS:
                                s["outs"] += 1
                        if bw == p:
                            o = bowl[p]
                            if "wides" not in ex and "noballs" not in ex: o["balls"] += 1
                            o["runs"] += d["runs"]["batter"] + ex.get("wides", 0) + ex.get("noballs", 0)
                            o["wkts"] += sum(w["kind"] not in NOT_BOWLER_WKTS for w in d.get("wickets", []))
    return sets, bat, bowl


def probs(counter):
    n = sum(counter.values())
    return {c: counter[c] / n for c in CATS}


def blend_avg(pb, pw, pl=None):
    return {c: (pb[c] + pw[c]) / 2 for c in CATS}


def blend_log5(pb, pw, pl):
    out = {}
    for c in CATS:
        if pb[c] == 0 or pw[c] == 0 or pl[c] == 0:
            out[c] = 0.0; continue
        num = pb[c] * pw[c] / pl[c]
        out[c] = num / (num + (1 - pb[c]) * (1 - pw[c]) / (1 - pl[c]))
    s = sum(out.values())
    return {c: v / s for c, v in out.items()}


def innings(dist, rng, target=None):
    cats, weights = zip(*dist.items())
    runs = wkts = balls = 0
    buf = []
    while balls < 300 and wkts < 10:
        if not buf:
            buf = rng.choices(cats, weights, k=400)
        o = buf.pop()
        if o in ("wd", "nb"):
            runs += 1
        elif o == "W":
            wkts += 1; balls += 1
        else:
            runs += int(o); balls += 1
        if target is not None and runs > target:
            break
    return runs, wkts, balls


def simulate(d_first, d_chase, n, seed=1):
    rng = random.Random(seed)
    w = l = t = 0
    s1 = s2 = 0
    for _ in range(n):
        a, _, _ = innings(d_first, rng)
        b, _, _ = innings(d_chase, rng, target=a)
        s1 += a; s2 += b
        if a > b: w += 1
        elif b > a: l += 1
        else: t += 1
    return dict(kohli_wins=w, bumrah_wins=l, ties=t, avg_kohli=s1 / n, avg_bumrah=s2 / n)


def expected_innings(dist):
    """Analytic per-ball summary: runs/legal ball, balls per wicket, expected all-out-limited total."""
    legal = 1 - dist["wd"] - dist["nb"]
    rpd = sum(int(c) * dist[c] for c in "0123456") + dist["wd"] + dist["nb"]
    rpb = rpd / legal
    bpw = legal / dist["W"] if dist["W"] else float("inf")
    return rpb * 6, bpw


def fmt(dist):
    return "  ".join(f"{c}:{dist[c]*100:5.2f}%" for c in CATS)


def main():
    folder = sys.argv[1]
    n = int(sys.argv[2]) if len(sys.argv) > 2 else 10000
    sets, bat, bowl = parse(folder)

    print("=== Career totals from Cricsheet (compare with Statsguru) ===")
    for p in (KOHLI, BUMRAH):
        s, o = bat[p], bowl[p]
        hs = max(s["hs"].values()) if s["hs"] else 0
        avg = s["runs"] / s["outs"] if s["outs"] else float("nan")
        print(f"{p}: matches {len(s['matches'])}, inns {len(s['inns'])}, runs {s['runs']}, BF {s['bf']}, outs {s['outs']}, "
              f"avg {avg:.2f}, SR {100*s['runs']/max(s['bf'],1):.2f}, HS {hs}, 4s {s['fours']}, 6s {s['sixes']}")
        ov = f"{o['balls']//6}.{o['balls']%6}"
        print(f"{'':{len(p)}}  bowling: balls {o['balls']} ({ov} ov), runs {o['runs']}, wkts {o['wkts']}, "
              f"econ {6*o['runs']/max(o['balls'],1):.2f}")

    P = {k: probs(v) for k, v in sets.items()}
    print("\n=== Per-delivery outcome distributions ===")
    for k in ("kohli_bat", "bumrah_bowl", "bumrah_bat", "kohli_bowl", "league"):
        print(f"{k:12s} n={sum(sets[k].values()):7d}  {fmt(P[k])}")

    results = {}
    for name, fn in (("simple average", blend_avg), ("log5 / odds ratio", blend_log5)):
        kohlis = fn(P["kohli_bat"], P["bumrah_bowl"], P["league"])   # Kohlis batting vs Bumrah bowling
        bumrahs = fn(P["bumrah_bat"], P["kohli_bowl"], P["league"])  # Bumrahs batting vs Kohli bowling
        print(f"\n=== {name} ===")
        print(f"Kohlis bat : {fmt(kohlis)}")
        print(f"Bumrahs bat: {fmt(bumrahs)}")
        for lab, d in (("Kohlis", kohlis), ("Bumrahs", bumrahs)):
            rpo, bpw = expected_innings(d)
            print(f"  {lab}: {rpo:.2f} runs/over, {bpw:.1f} legal balls per wicket")
        r = simulate(kohlis, bumrahs, n)
        results[name] = r
        print(f"  {n} matches -> Kohlis win {r['kohli_wins']}, Bumrahs win {r['bumrah_wins']}, ties {r['ties']}; "
              f"avg scores Kohlis {r['avg_kohli']:.1f}, Bumrahs {r['avg_bumrah']:.1f}")

    # sensitivity: Kohli's bowling wicket count +/- 1 (tiny sample)
    print("\n=== Sensitivity: Kohli bowling wickets +/-1 (dot <-> W) ===")
    for delta in (-1, +1):
        c = Counter(sets["kohli_bowl"]); c["W"] += delta; c["0"] -= delta
        pk = probs(c)
        for name, fn in (("simple average", blend_avg), ("log5 / odds ratio", blend_log5)):
            r = simulate(fn(P["kohli_bat"], P["bumrah_bowl"], P["league"]), fn(P["bumrah_bat"], pk, P["league"]), n, seed=2)
            print(f"  W{delta:+d} {name:18s}: Kohlis {r['kohli_wins']}, Bumrahs {r['bumrah_wins']}, ties {r['ties']}, "
                  f"avg {r['avg_kohli']:.1f} v {r['avg_bumrah']:.1f}")


if __name__ == "__main__":
    main()
