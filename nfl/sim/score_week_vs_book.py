#!/usr/bin/env python3
"""Score one week's sim probabilities against the book's de-vigged probabilities, on outcomes.

WRITTEN 2026-09-20 ~16:05Z, BEFORE the first Week 2 kickoff (17:00Z), so that what is measured
and how is fixed before any outcome exists. It reads; it tunes nothing; it gates nothing.

Inputs
  nfl/data/sim/outputs/week=<S>_<WW>/grades.parquet     (grade_week.py: hit / miss / void ...)
  nfl/data/board/week=<S>_<WW>/nfl_prop_candidates_*.parquet  (newest; two-way Hard Rock rows,
        q_over = proportional de-vig of the SAME row)
  placed legs: rows with tier == 'placed' in grades.parquet, i.e. grade_week.py was run with
        --extra nfl/data/board/week=<S>_<WW>/placed_legs_<slate>.parquet (export_placed_legs.py)

Universe: two-way receptions / rush-attempts rows where the sim priced the book's exact line and
the leg graded hit or miss. One row per (player, family, line); P(over) on all three sides.

PRE-REGISTERED (2026-09-20, Week 2):
  P1. Brier(book q_over) < Brier(sim cal_p) on the universe.
  P2. Among rows with |cal_p - q_over| > 0.20, the outcome sides with the book more often than
      with the sim ("sides with the sim" = over hit when cal_p > q_over, or miss when cal_p < q).
  Neither can validate anything at one week. They can embarrass the sim.

Usage: python3 nfl/sim/score_week_vs_book.py --season 2026 --week 2 [--out report.md]
"""
import argparse, re, sys, unicodedata
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent.parent
FAMILY = {"player_receptions": "receptions", "player_rush_attempts": "rush_attempts"}
DIVERGE = 0.20
EPS = 1e-6


def norm_name(s):
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode().lower()
    s = re.sub(r"[^a-z ]", "", s)
    s = re.sub(r"\b(jr|sr|ii|iii|iv)\b", "", s)
    return " ".join(s.split())


def brier(p, y):
    return float(np.mean((np.asarray(p, float) - np.asarray(y, float)) ** 2))


def logloss(p, y):
    p = np.clip(np.asarray(p, float), EPS, 1 - EPS)
    y = np.asarray(y, float)
    return float(-np.mean(y * np.log(p) + (1 - y) * np.log(1 - p)))


def build_universe(grades, cand):
    g = grades[(grades["side"] == "over") & grades["grade"].isin(["hit", "miss"])
               & (grades["tier"] != "placed")].copy()      # placed legs are scored separately
    g["k"] = g["player_name"].map(norm_name)
    g["y"] = (g["grade"] == "hit").astype(int)
    c = cand[cand["two_way"] & cand["market_key"].isin(FAMILY)].copy()
    c["family"] = c["market_key"].map(FAMILY)
    c["k"] = c["player_name"].map(norm_name)
    keep = ["k", "family", "line", "q_over", "team", "position", "eligible", "pull_timestamp"]
    u = c[keep].merge(g[["k", "family", "line", "sim_p", "cal_p", "tier", "game_id", "y", "grade"]],
                      on=["k", "family", "line"], how="inner")
    dup = u.duplicated(["k", "family", "line"], keep=False)
    if dup.any():
        raise ValueError(f"ambiguous join: {u.loc[dup, ['k', 'family', 'line']].values.tolist()[:5]}")
    return u, len(c), len(g)


def cluster_boot_diff(u, col_a, col_b, n_boot=2000, seed=20260920):
    """Brier(col_a) - Brier(col_b), resampling GAMES (legs in a game are not independent)."""
    rng = np.random.default_rng(seed)
    games = u["game_id"].unique()
    by = {gid: u[u["game_id"] == gid] for gid in games}
    out = []
    for _ in range(n_boot):
        s = pd.concat([by[gid] for gid in rng.choice(games, len(games), replace=True)])
        out.append(brier(s[col_a], s["y"]) - brier(s[col_b], s["y"]))
    return float(np.percentile(out, 2.5)), float(np.percentile(out, 97.5))


def score_table(u):
    rows = []
    for name, col in [("book q_over", "q_over"), ("sim cal_p", "cal_p"), ("sim raw sim_p", "sim_p")]:
        rows.append({"source": name, "n": len(u), "mean_p": round(float(u[col].mean()), 3),
                     "over_rate": round(float(u["y"].mean()), 3),
                     "brier": round(brier(u[col], u["y"]), 4),
                     "logloss": round(logloss(u[col], u["y"]), 4)})
    rows.append({"source": "coin 0.5", "n": len(u), "mean_p": 0.5,
                 "over_rate": round(float(u["y"].mean()), 3), "brier": 0.25,
                 "logloss": round(float(np.log(2)), 4)})
    return pd.DataFrame(rows)


def divergent(u, thr=DIVERGE):
    d = u[(u["cal_p"] - u["q_over"]).abs() > thr].copy()
    d["sim_says_over"] = d["cal_p"] > d["q_over"]
    d["sided_with_sim"] = np.where(d["sim_says_over"], d["y"] == 1, d["y"] == 0)
    return d


def placed_legs(grades, cand):
    """Placed legs come from grade_week's --extra rows (tier == 'placed'), so every family the
    grader knows gets a W/L, whether or not the sim priced it."""
    if "tier" not in grades.columns:
        return pd.DataFrame()
    t = grades[grades["tier"] == "placed"].copy()
    if t.empty:
        return t
    t["k"] = t["player_name"].map(norm_name)
    sim = grades[(grades["tier"] != "placed") & (grades["side"] == "over")].copy()
    sim["k"] = sim["player_name"].map(norm_name)
    t = t.merge(sim[["k", "family", "line", "cal_p"]].rename(columns={"cal_p": "cal_over"}),
                on=["k", "family", "line"], how="left")
    c = cand[cand["two_way"]].copy()
    c["k"] = c["player_name"].map(norm_name)
    c["family"] = c["market_key"].str.replace("player_", "", regex=False)
    t = t.merge(c[["k", "family", "line", "q_over"]], on=["k", "family", "line"], how="left")
    over = t["side"].str.lower() == "over"
    t["q_pick"] = t["q_over"].where(over, 1 - t["q_over"])
    t["cal_pick"] = t["cal_over"].where(over, 1 - t["cal_over"])
    return t[["ticket", "player_name", "family", "side", "line", "book_price", "q_pick", "cal_pick",
              "grade", "grade_reason"]]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--season", type=int, default=2026)
    ap.add_argument("--week", type=int, required=True)
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    wk = f"week={a.season}_{a.week:02d}"
    gpath = ROOT / "nfl" / "data" / "sim" / "outputs" / wk / "grades.parquet"
    cands = sorted((ROOT / "nfl" / "data" / "board" / wk).glob("nfl_prop_candidates_*.parquet"))
    if not gpath.exists():
        sys.exit(f"HALT: {gpath} missing - run grade_week.py --season {a.season} --week {a.week} first")
    if not cands:
        sys.exit(f"HALT: no candidates parquet under nfl/data/board/{wk}")
    grades = pd.read_parquet(gpath)
    cand = pd.read_parquet(cands[-1])
    u, n_cand, n_graded = build_universe(grades, cand)

    L = [f"# Sim vs book on outcomes - {a.season} week {a.week}", "",
         f"grades: `{gpath.relative_to(ROOT)}` ({len(grades)} legs; "
         f"{grades['grade'].value_counts().to_dict()})",
         f"candidates: `{cands[-1].relative_to(ROOT)}` ({n_cand} two-way rec/rush rows)",
         f"universe (sim priced the book's exact line AND graded hit/miss): **{len(u)}** rows, "
         f"{u['k'].nunique()} players, {u['game_id'].nunique()} games", "",
         "**One week. This is a log, not evidence. Nothing is tuned on it.**", ""]
    if len(u) == 0:
        L.append("No gradable rows yet (games not in PBP).")
    else:
        L += ["## All rows", "", score_table(u).to_markdown(index=False), ""]
        lo, hi = cluster_boot_diff(u, "cal_p", "q_over")
        d_b = brier(u["cal_p"], u["y"]) - brier(u["q_over"], u["y"])
        L += [f"Brier(sim cal_p) - Brier(book) = **{d_b:+.4f}** (game-cluster bootstrap 95%: "
              f"{lo:+.4f} .. {hi:+.4f}). P1 (book better) {'HELD' if d_b > 0 else 'DID NOT HOLD'}; "
              f"{'interval excludes 0' if lo > 0 or hi < 0 else 'interval includes 0 - not distinguishable'}.", ""]
        for col in ["family", "tier", "game_id"]:
            t = u.groupby(col).apply(lambda s: pd.Series({
                "n": len(s), "over_rate": round(s["y"].mean(), 3),
                "brier_book": round(brier(s["q_over"], s["y"]), 4),
                "brier_sim": round(brier(s["cal_p"], s["y"]), 4)})).reset_index()
            L += [f"## By {col}", "", t.to_markdown(index=False), ""]
        d = divergent(u)
        L += [f"## Rows where |cal_p - q_over| > {DIVERGE}", ""]
        if len(d):
            ws, n = int(d["sided_with_sim"].sum()), len(d)
            L += [f"{n} rows: outcome sided with the SIM on {ws}, with the BOOK on {n - ws}. "
                  f"P2 (book more often) {'HELD' if n - ws > ws else 'DID NOT HOLD'}.", "",
                  d[["k", "team", "family", "line", "q_over", "cal_p", "y", "sided_with_sim"]]
                  .round(3).to_markdown(index=False), ""]
        else:
            L.append("none graded yet")
    p = placed_legs(grades, cand)
    if len(p):
        by = p.groupby("ticket")["grade"].agg(lambda g: g.value_counts().to_dict())
        L += ["## Placed tickets", ""] + [f"- {k}: {v}" for k, v in by.items()] + [""]
        L += ["## Placed legs (the sim had no say in these)", "",
              p.round(3).to_markdown(index=False), "",
              "Legs with no q/cal are families or lines the sim does not price (5J item 3)."]
    text = "\n".join(L) + "\n"
    print(text)
    if a.out:
        Path(a.out).write_text(text)


if __name__ == "__main__":
    main()
