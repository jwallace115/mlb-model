#!/usr/bin/env python3
"""
Shopping-edge robustness audit (ChatGPT cross-AI review, Q1).

Rebuilds the "best available number vs randomly chosen book" result as a SAVED,
reproducible artifact -- the original figure was computed ad hoc and never
persisted, which is a Check 3 (research-object identity) failure.

Then attacks it four ways:
  A. P&L vs line-improvement-only  (is the t-stat an order statistic?)
  B. Book-count strata            (does best-of-20 carry best-of-6?)
  C. Consensus-distance exclusion (stale-outlier enrichment proxy)
  D. Quote-age exclusion          (stale-BOOK enrichment, via last_update)
  E. Which books hold the best number (survivorship / limit concentration)

NOTE ON SUBSTITUTION: the review asked for exclusion of quotes surviving
<5/15/30/60 SECONDS. That is not computable here -- the archive holds ONE
snapshot per week and the vendor's finest historical grid is 10 minutes.
Quote age at snapshot (snapshot_ts - book last_update) is used instead and is
a different, weaker quantity. Stated, not silently swapped.

Zero API calls. Read-only. Outputs markdown to research/execution_edge/.
"""
import json, glob, sys
from pathlib import Path
from datetime import datetime
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent.parent
SNAP = ROOT / "nfl" / "data" / "cache" / "odds_snapshots"
CANON = ROOT / "nfl" / "data" / "nfl_canonical.parquet"
OUT = ROOT / "research" / "execution_edge" / "shopping_robustness_2026-08-28.md"

TEAM_MAP = {
    'Arizona Cardinals': 'ARI', 'Atlanta Falcons': 'ATL', 'Baltimore Ravens': 'BAL',
    'Buffalo Bills': 'BUF', 'Carolina Panthers': 'CAR', 'Chicago Bears': 'CHI',
    'Cincinnati Bengals': 'CIN', 'Cleveland Browns': 'CLE', 'Dallas Cowboys': 'DAL',
    'Denver Broncos': 'DEN', 'Detroit Lions': 'DET', 'Green Bay Packers': 'GB',
    'Houston Texans': 'HOU', 'Indianapolis Colts': 'IND', 'Jacksonville Jaguars': 'JAX',
    'Kansas City Chiefs': 'KC', 'Las Vegas Raiders': 'LV', 'Los Angeles Chargers': 'LAC',
    'Los Angeles Rams': 'LA', 'Miami Dolphins': 'MIA', 'Minnesota Vikings': 'MIN',
    'New England Patriots': 'NE', 'New Orleans Saints': 'NO', 'New York Giants': 'NYG',
    'New York Jets': 'NYJ', 'Philadelphia Eagles': 'PHI', 'Pittsburgh Steelers': 'PIT',
    'San Francisco 49ers': 'SF', 'Seattle Seahawks': 'SEA', 'Tampa Bay Buccaneers': 'TB',
    'Tennessee Titans': 'TEN', 'Washington Commanders': 'WAS',
    'Washington Football Team': 'WAS',
}

def payout(price):
    if price is None or (isinstance(price, float) and np.isnan(price)):
        return np.nan
    return price / 100.0 if price > 0 else 100.0 / abs(price)

def pnl(side, point, price, total_points):
    if any(v is None or (isinstance(v, float) and np.isnan(v))
           for v in (point, price, total_points)):
        return np.nan
    if total_points == point:
        return 0.0
    won = (total_points > point) if side == "Over" else (total_points < point)
    return payout(price) if won else -1.0

def tstat(x):
    x = np.asarray([v for v in x if v is not None and not np.isnan(v)], dtype=float)
    if len(x) < 3 or x.std(ddof=1) == 0:
        return np.nan, np.nan, len(x)
    return x.mean(), x.mean() / (x.std(ddof=1) / np.sqrt(len(x))), len(x)


def load_rows():
    if not CANON.exists():
        print(f"HARD STOP: {CANON} not found"); sys.exit(1)
    can = pd.read_parquet(CANON)
    can = can.dropna(subset=["total_points"])
    lookup = {}
    for r in can.itertuples():
        lookup[(r.home_team, str(r.date)[:10])] = r.total_points

    files = sorted(glob.glob(str(SNAP / "open_*.json")))
    if not files:
        print(f"HARD STOP: no snapshots in {SNAP}"); sys.exit(1)

    rows = []
    unmatched = 0
    for f in files:
        j = json.load(open(f))
        snap_ts = pd.Timestamp(j["timestamp"])
        for g in j["data"]:
            home = TEAM_MAP.get(g["home_team"])
            if home is None:
                continue
            gdate = str(g["commence_time"])[:10]
            tp = lookup.get((home, gdate))
            if tp is None:   # commence_time UTC can roll a night game to next day
                prev = (pd.Timestamp(gdate) - pd.Timedelta(days=1)).strftime("%Y-%m-%d")
                tp = lookup.get((home, prev))
            if tp is None:
                unmatched += 1
                continue
            quotes = []
            for b in g["bookmakers"]:
                lu = b.get("last_update")
                age = (snap_ts - pd.Timestamp(lu)).total_seconds() if lu else np.nan
                for m in b.get("markets", []):
                    if m.get("key") != "totals":
                        continue
                    o = {x["name"]: x for x in m.get("outcomes", []) if "point" in x}
                    if "Over" not in o or "Under" not in o:
                        continue
                    quotes.append({
                        "book": b["key"], "age": age, "point": float(o["Over"]["point"]),
                        "over_price": o["Over"].get("price"),
                        "under_price": o["Under"].get("price"),
                    })
            if len(quotes) < 2:
                continue
            rows.append({"game": f"{g['id']}", "date": gdate, "snap": snap_ts,
                         "total_points": tp, "quotes": quotes})
    print(f"games with >=2 books: {len(rows)}   unmatched to canonical: {unmatched}")
    return rows


def evaluate(rows, max_consensus_dist=None, exclude_stale_books=False):
    """Returns paired diffs (best - E[random book]) for P&L and for line improvement."""
    dpnl, dline, best_books, nbooks = [], [], [], []
    for r in rows:
        med = float(np.median([q["point"] for q in r["quotes"]]))
        ages = [q["age"] for q in r["quotes"] if not np.isnan(q["age"])]
        med_age = float(np.median(ages)) if ages else np.nan
        for side in ("Over", "Under"):
            pool = r["quotes"]
            if exclude_stale_books and not np.isnan(med_age):
                pool = [q for q in pool if np.isnan(q["age"]) or q["age"] <= med_age]
            if len(pool) < 2:
                continue
            pk = "over_price" if side == "Over" else "under_price"
            # best number for this side: Over wants the LOWEST total, Under the HIGHEST
            cand = sorted(pool, key=lambda q: (q["point"], -(q[pk] or -10000)))
            best = cand[0] if side == "Over" else sorted(
                pool, key=lambda q: (-q["point"], -(q[pk] or -10000)))[0]
            if max_consensus_dist is not None and abs(best["point"] - med) > max_consensus_dist:
                continue
            pb = pnl(side, best["point"], best[pk], r["total_points"])
            pr = [pnl(side, q["point"], q[pk], r["total_points"]) for q in pool]
            pr = [v for v in pr if not np.isnan(v)]
            if np.isnan(pb) or not pr:
                continue
            dpnl.append(pb - float(np.mean(pr)))
            improve = (float(np.mean([q["point"] for q in pool])) - best["point"]) \
                if side == "Over" else (best["point"] - float(np.mean([q["point"] for q in pool])))
            dline.append(improve)
            best_books.append(best["book"])
            nbooks.append(len(pool))
    return dpnl, dline, best_books, nbooks


def main():
    rows = load_rows()
    lines = []
    W = lines.append
    W("# Shopping-Edge Robustness Audit")
    W(f"**Run:** {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}  ")
    W("**Trigger:** ChatGPT cross-AI review, Q1 (stale-quote enrichment).  ")
    W("**Data:** `nfl/data/cache/odds_snapshots/open_*.json`, NFL totals, 2021-2024.  ")
    W("**Prices:** real captured American odds. **API calls:** 0.\n")

    W("## Snapshot character\n")
    lead = [(pd.Timestamp(r["date"], tz="UTC") - r["snap"]).total_seconds() / 86400.0
            for r in rows]
    W(f"- Game-snapshots usable: **{len(rows)}**")
    W(f"- Snapshot lead time before game date: median **{np.median(lead):.1f} days** "
      f"(min {min(lead):.1f}, max {max(lead):.1f})")
    W(f"- Books per game: median **{np.median([len(r['quotes']) for r in rows]):.0f}**, "
      f"range {min(len(r['quotes']) for r in rows)}-{max(len(r['quotes']) for r in rows)}\n")

    W("## A. Headline, rebuilt\n")
    dp, dl, bb, nb = evaluate(rows)
    m, t, n = tstat(dp); ml, tl, _ = tstat(dl)
    W(f"| Metric | Mean | t | N |")
    W(f"|---|---|---|---|")
    W(f"| **P&L per unit (best - E[random book])** | **{m*100:+.2f}%** | {t:.2f} | {n} |")
    W(f"| Line improvement (points) | {ml:+.3f} | {tl:.2f} | {n} |\n")
    W("If the P&L t-stat and the line t-stat are both large, the review's "
      "'it's just an order statistic' objection is only partly right: the order "
      "statistic is real, but it is being converted into money at real prices.\n")

    W("## B. Book-count strata\n")
    W("| Books in pool | Mean P&L diff | t | N |")
    W("|---|---|---|---|")
    nb_a = np.array(nb); dp_a = np.array(dp)
    for lo, hi, lab in [(2, 5, "2-5"), (6, 9, "6-9"), (10, 13, "10-13"), (14, 99, "14+")]:
        sel = dp_a[(nb_a >= lo) & (nb_a <= hi)]
        if len(sel) > 2:
            mm, tt, nn = tstat(sel)
            W(f"| {lab} | {mm*100:+.2f}% | {tt:.2f} | {nn} |")
    W("")
    W("A monotone rise with book count is the order-statistic signature and is "
      "EXPECTED. What matters is whether the low-count strata are still positive, "
      "because that is closer to a realistic account set.\n")

    W("## C. Consensus-distance exclusion (stale-outlier proxy)\n")
    W("| Max |best - median| allowed | Mean P&L diff | t | N |")
    W("|---|---|---|---|")
    for d in [None, 2.0, 1.5, 1.0, 0.5]:
        dpx, _, _, _ = evaluate(rows, max_consensus_dist=d)
        mm, tt, nn = tstat(dpx)
        W(f"| {'no limit' if d is None else f'{d:.1f} pts'} | {mm*100:+.2f}% | {tt:.2f} | {nn} |")
    W("")
    W("**Read this as the review's decisive test.** If the effect collapses as far "
      "outliers are removed, the edge lives in quotes least likely to be executable.\n")

    W("## D. Quote-age exclusion (stale-BOOK proxy)\n")
    dps, _, _, _ = evaluate(rows, exclude_stale_books=True)
    mm, tt, nn = tstat(dps)
    W(f"Restricting each game's pool to books whose `last_update` is at or fresher "
      f"than that game's median: **{mm*100:+.2f}%**, t={tt:.2f}, N={nn}\n")

    W("## E. Which books hold the best number\n")
    vc = pd.Series(bb).value_counts()
    share = (vc / vc.sum() * 100).round(1)
    W("| Book | Times best | Share |")
    W("|---|---|---|")
    for k in vc.index[:12]:
        W(f"| {k} | {vc[k]} | {share[k]}% |")
    W("")
    W(f"Top-3 concentration: **{share.iloc[:3].sum():.1f}%**. High concentration in "
      "soft/offshore books is a monetisability problem, not a statistical one.\n")

    W("## Limits of this audit\n")
    W("- One snapshot per week: sub-minute quote persistence is NOT measurable here, "
      "and the vendor's finest historical grid is 10 minutes. The review's "
      "5/15/30/60-second test cannot be run on any purchasable history.")
    W("- Snapshots are early-week, not at-close. Early week is when dispersion is "
      "widest AND when limits are lowest. That cuts against monetisability.")
    W("- `hardrockbet_fl` is absent from all 22 books here. This result therefore "
      "says nothing about the operator's actual executable account set.")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(lines))
    print(f"\nwrote {OUT}")
    print("\n".join(lines))

if __name__ == "__main__":
    main()
