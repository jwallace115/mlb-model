"""
Phase 7 — Historical Line Backfill
===================================
Pulls closing totals from The Odds API for every 2024+2025 MLB game.
Populates Layer 2 (market_snapshots.parquet) with real close_total values,
rebuilds Layers 3+4, and reruns the Phase 7 report showing proxy vs real
results side-by-side.

Strategy:
  For each game, compute the optimal snapshot UTC timestamp (one hour before
  first pitch) so the snapshot captures pre-game (closing) odds.
  Unique (date, snap_hour) pairs are deduplicated → one API call per snapshot.
  Every response is cached to disk; re-runs skip already-cached files.

decision_line_source = "closing_only" for all backfilled rows per Phase 7
spec: we only have closing lines, not a distinct opening/decision line.
CLV = 0 and is marked as unavailable (decision_line == close_total by def).

Usage:
  python3 sim/phase7_pull_lines.py              # full run
  python3 sim/phase7_pull_lines.py --plan       # show credit plan, no API calls
  python3 sim/phase7_pull_lines.py --report     # report only (skip pulling)
"""

from __future__ import annotations

import argparse
import json
import os
import ssl
import sys
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent
SIM_DIR   = Path(__file__).resolve().parent
DATA_DIR  = SIM_DIR / "data"
HIST_CACHE_DIR = DATA_DIR / "cache" / "hist_odds"
HIST_CACHE_DIR.mkdir(parents=True, exist_ok=True)

sys.path.insert(0, str(REPO_ROOT))
from config import (
    ODDS_API_KEY, ODDS_API_BASE, ODDS_API_TEAM_MAP,
    PROXY_LINE, WATCHLIST_EDGE, BET_EDGE, STRONG_EDGE,
    WATCHLIST_PROB, BET_PROB, STRONG_PROB, WIN_UNIT, JUICE,
)
import sim.phase7_market as p7

SPORT_KEY       = "baseball_mlb"
REGION          = "us"
MARKET          = "totals"
PREFERRED_BOOKS = ["draftkings", "fanduel"]
SOURCE_LABEL    = "closing_only"   # per Phase 7 spec: no distinct decision/close line

# SSL context (macOS cert workaround)
_SSL_CTX = ssl.create_default_context()
_SSL_CTX.check_hostname = False
_SSL_CTX.verify_mode    = ssl.CERT_NONE


# ===========================================================================
# Snapshot planning
# ===========================================================================

def _snap_utc(game_date: str, game_hour_utc: int) -> tuple[str, int]:
    """
    Return (date_str, snap_hour) for the optimal pre-game snapshot.
    Games starting UTC 0-3 (8pm-11pm ET): pull at 23:00 UTC same local date.
    All others: pull at (game_hour_utc - 1):00 UTC.
    """
    if game_hour_utc in (0, 1, 2, 3):
        return (game_date, 23)
    return (game_date, game_hour_utc - 1)


def build_snapshot_plan(df_games: pd.DataFrame) -> pd.DataFrame:
    """
    For each game compute its optimal snapshot time.
    Returns a DataFrame with one row per game + snap_date + snap_hour columns.
    """
    df = df_games.copy()
    df["snap_date"], df["snap_hour"] = zip(*df.apply(
        lambda r: _snap_utc(r["date"], r["game_hour_utc"]), axis=1
    ))
    return df


def snap_to_iso(snap_date: str, snap_hour: int) -> str:
    return f"{snap_date}T{snap_hour:02d}:00:00Z"


# ===========================================================================
# API pull & caching
# ===========================================================================

def _cache_path(snap_date: str, snap_hour: int) -> Path:
    return HIST_CACHE_DIR / f"{snap_date}_{snap_hour:02d}.json"


def pull_snapshot(snap_date: str, snap_hour: int) -> dict | None:
    """
    Pull one historical snapshot. Checks disk cache first.
    Returns the parsed API response dict, or None on error.
    """
    cp = _cache_path(snap_date, snap_hour)
    if cp.exists():
        with cp.open() as f:
            return json.load(f)

    iso = snap_to_iso(snap_date, snap_hour)
    url = (
        f"{ODDS_API_BASE}/historical/sports/{SPORT_KEY}/odds"
        f"?apiKey={ODDS_API_KEY}&regions={REGION}&markets={MARKET}&date={iso}"
    )
    try:
        with urllib.request.urlopen(url, context=_SSL_CTX) as r:
            hdrs     = dict(r.info())
            body     = json.loads(r.read())
            remaining = int(hdrs.get("X-Requests-Remaining", -1))
            cost      = int(hdrs.get("X-Requests-Last", 10))
        body["_meta"] = {
            "snap_date": snap_date,
            "snap_hour": snap_hour,
            "remaining": remaining,
            "cost":      cost,
        }
        cp.write_text(json.dumps(body))
        return body
    except urllib.error.HTTPError as e:
        print(f"  HTTP {e.code} pulling {iso}: {e.read().decode()[:120]}")
        return None
    except Exception as e:
        print(f"  ERROR pulling {iso}: {e}")
        return None


# ===========================================================================
# Game matching helpers
# ===========================================================================

def _decimal_to_american(dec: float) -> float:
    if dec >= 2.0:
        return (dec - 1) * 100
    return -100 / (dec - 1)


# Invert ODDS_API_TEAM_MAP (full name → abbrev)
_FULL_TO_ABB: dict[str, str] = ODDS_API_TEAM_MAP


def _api_game_key(api_game: dict) -> tuple[str, str, str]:
    """Return (et_date, home_abbrev, away_abbrev) for an API game entry."""
    ct = api_game["commence_time"]               # e.g. "2024-04-15T23:10:00Z"
    dt = datetime.strptime(ct, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    # Convert to ET (approximate: UTC-4 summer, UTC-5 winter; use -4 for MLB season)
    et_hour = (dt.hour - 4) % 24
    if dt.hour < 4:                              # UTC midnight cross: ET date is prior day
        import datetime as _dt
        et_date = (dt - _dt.timedelta(days=1)).strftime("%Y-%m-%d")
    else:
        et_date = dt.strftime("%Y-%m-%d")

    home = _FULL_TO_ABB.get(api_game["home_team"], api_game["home_team"])
    away = _FULL_TO_ABB.get(api_game["away_team"], api_game["away_team"])
    return (et_date, home, away)


def _extract_total(api_game: dict) -> tuple[float, float, float, str] | None:
    """
    Extract (total_line, over_price_american, under_price_american, book_key)
    from an API game, preferring PREFERRED_BOOKS.
    Returns None if no totals market is found.
    """
    bookmakers = api_game.get("bookmakers", [])
    # Build ordered list: preferred books first, then any others
    preferred = [b for b in bookmakers if b["key"] in PREFERRED_BOOKS]
    others    = [b for b in bookmakers if b["key"] not in PREFERRED_BOOKS]
    for bm in preferred + others:
        for mkt in bm.get("markets", []):
            if mkt["key"] != "totals":
                continue
            outcomes = {o["name"]: o for o in mkt["outcomes"]}
            if "Over" not in outcomes or "Under" not in outcomes:
                continue
            over  = outcomes["Over"]
            under = outcomes["Under"]
            line  = float(over.get("point", under.get("point", np.nan)))
            if np.isnan(line):
                continue
            op = _decimal_to_american(float(over["price"]))
            up = _decimal_to_american(float(under["price"]))
            return (line, round(op, 1), round(up, 1), bm["key"])
    return None


# ===========================================================================
# Core matching: game_pk → (total, over_price, under_price, book, snapshot_ts)
# ===========================================================================

def match_games_to_lines(
    df_plan: pd.DataFrame,
    unique_snaps: list[tuple[str, int]],
    all_responses: dict[tuple, dict],
) -> dict[int, dict]:
    """
    For each game_pk, find its total from the closest pre-game snapshot.
    Handles doubleheaders by matching games to distinct commence_times.

    Returns: {game_pk: {total, over_price, under_price, book, snapshot_ts}}
    """
    # Build lookup: (et_date, home_abbrev, away_abbrev) → list of API game dicts
    # (multiple entries for doubleheaders)
    snap_data: dict[tuple[str, int], list[dict]] = {}
    for (sd, sh), resp in all_responses.items():
        if resp is None:
            continue
        snap_data[(sd, sh)] = resp.get("data", [])

    result: dict[int, dict] = {}

    # Group games by (snap_date, snap_hour) so we search the right snapshot
    for (snap_date, snap_hour), grp in df_plan.groupby(["snap_date", "snap_hour"]):
        api_games = snap_data.get((snap_date, snap_hour), [])
        if not api_games:
            continue

        # Build map from (et_date, home, away) → sorted list of api_games by commence_time
        key_to_games: dict[tuple, list[dict]] = {}
        for ag in api_games:
            k = _api_game_key(ag)
            key_to_games.setdefault(k, []).append(ag)
        for k in key_to_games:
            key_to_games[k].sort(key=lambda g: g["commence_time"])

        for _, row in grp.iterrows():
            gpk  = int(row["game_pk"])
            date = row["date"]
            home = row["home_team"]
            away = row["away_team"]
            gnum = int(row.get("game_number", 1))

            key = (date, home, away)
            candidates = key_to_games.get(key, [])

            if not candidates:
                continue  # no match in this snapshot

            # Doubleheaders: game_number 1 → first commence_time, 2 → second
            idx = min(gnum - 1, len(candidates) - 1)
            ag  = candidates[idx]

            info = _extract_total(ag)
            if info is None:
                continue

            total, op, up, book = info
            snap_ts = snap_to_iso(snap_date, snap_hour)
            result[gpk] = {
                "total":          total,
                "over_price":     op,
                "under_price":    up,
                "book":           book,
                "snapshot_ts":    snap_ts,
                "commence_time":  ag["commence_time"],
            }

    return result


# ===========================================================================
# Layer 2 population
# ===========================================================================

def populate_layer2(
    df_plan: pd.DataFrame,
    game_lines: dict[int, dict],
) -> tuple[list[int], list[int]]:
    """
    Write real closing lines into Layer 2 for matched games.
    Returns (matched_pks, unmatched_pks).
    """
    df_l2 = pd.read_parquet(p7.L2_PATH)

    matched   = []
    unmatched = []

    for _, row in df_plan.iterrows():
        gpk = int(row["game_pk"])
        if gpk not in game_lines:
            unmatched.append(gpk)
            continue

        info  = game_lines[gpk]
        total = info["total"]
        op    = info["over_price"]
        up    = info["under_price"]
        book  = info["book"]
        snap_ts = info["snapshot_ts"]

        mask = df_l2["game_id"] == gpk
        if mask.any():
            idx = df_l2[mask].index[0]
            df_l2.at[idx, "book"]                  = book
            df_l2.at[idx, "snapshot_time"]         = pd.NaT  # closing-only, no single ts
            df_l2.at[idx, "open_total"]             = np.nan  # not available
            df_l2.at[idx, "noon_total"]             = np.nan
            df_l2.at[idx, "five_pm_total"]          = np.nan
            df_l2.at[idx, "close_total"]            = total
            df_l2.at[idx, "over_price"]             = op
            df_l2.at[idx, "under_price"]            = up
            df_l2.at[idx, "decision_line"]          = total   # closing-only: decision = close
            df_l2.at[idx, "decision_line_source"]   = SOURCE_LABEL
            df_l2.at[idx, "clv"]                    = 0.0     # decision == close → CLV = 0
        else:
            new_row = {
                "game_id":              gpk,
                "date":                 row["date"],
                "book":                 book,
                "snapshot_time":        pd.NaT,
                "open_total":           np.nan,
                "noon_total":           np.nan,
                "five_pm_total":        np.nan,
                "close_total":          total,
                "over_price":           op,
                "under_price":          up,
                "decision_line":        total,
                "decision_line_source": SOURCE_LABEL,
                "clv":                  0.0,
            }
            df_l2 = pd.concat([df_l2, pd.DataFrame([new_row])], ignore_index=True)

        matched.append(gpk)

    df_l2.to_parquet(p7.L2_PATH, index=False)
    return matched, unmatched


# ===========================================================================
# Coverage report
# ===========================================================================

def coverage_report(
    df_plan: pd.DataFrame,
    matched: list[int],
    unmatched: list[int],
    game_lines: dict[int, dict],
) -> None:
    print("\n" + "=" * 76)
    print("  COVERAGE REPORT")
    print("=" * 76)

    n_total   = len(df_plan)
    n_matched = len(matched)
    n_miss    = len(unmatched)

    print(f"  Total games (2024+2025) : {n_total:,}")
    print(f"  Matched (real line)     : {n_matched:,}  ({n_matched/n_total*100:.1f}%)")
    print(f"  Unmatched (proxy)       : {n_miss:,}  ({n_miss/n_total*100:.1f}%)")
    print()

    # By season
    for season in [2024, 2025]:
        sub = df_plan[df_plan["season"] == season]
        sm  = sub[sub["game_pk"].isin(matched)]
        print(f"  {season}: {len(sm):,}/{len(sub):,} matched  ({len(sm)/len(sub)*100:.1f}%)")

    # Book distribution
    books: dict[str, int] = {}
    for info in game_lines.values():
        b = info["book"]
        books[b] = books.get(b, 0) + 1
    print()
    print("  Book distribution (matched games):")
    for b, cnt in sorted(books.items(), key=lambda x: -x[1]):
        print(f"    {b:<20} {cnt:,}")

    # Systematic gaps — unmatched games by month + team
    if unmatched:
        miss_df = df_plan[df_plan["game_pk"].isin(unmatched)].copy()
        miss_df["month"] = miss_df["date"].str[:7]
        print()
        print("  Unmatched by month:")
        for month, cnt in miss_df["month"].value_counts().sort_index().items():
            print(f"    {month}: {cnt:,}")
        print()
        print("  Unmatched by home team (top 10):")
        for team, cnt in miss_df["home_team"].value_counts().head(10).items():
            print(f"    {team}: {cnt:,}")


# ===========================================================================
# Phase 7 report — proxy vs real side-by-side
# ===========================================================================

def _roi(wins: int, losses: int) -> float:
    total = wins + losses
    if total == 0:
        return float("nan")
    return (wins * WIN_UNIT - losses) / total * 100


def _tier(abs_edge: float, prob: float) -> str:
    if abs_edge >= STRONG_EDGE and prob >= STRONG_PROB:
        return "STRONG"
    if abs_edge >= BET_EDGE and prob >= BET_PROB:
        return "BET"
    if abs_edge >= WATCHLIST_EDGE and prob >= WATCHLIST_PROB:
        return "WATCHLIST"
    return "NO_PLAY"


def _prob_row(df: pd.DataFrame, thresh: float) -> dict:
    g    = df[df["bet_prob"] >= thresh]
    n    = len(g)
    wins = (g["result_win_loss"] == "W").sum()
    loss = (g["result_win_loss"] == "L").sum()
    return {"n": n, "win_pct": wins/n*100 if n else 0,
            "units": wins*WIN_UNIT - loss, "roi": _roi(wins, loss)}


def _edge_row(df: pd.DataFrame, lo: float, hi: float) -> dict:
    mask = (df["abs_edge"] >= lo) & (df["abs_edge"] < hi)
    g    = df[mask]
    n    = len(g)
    wins = (g["result_win_loss"] == "W").sum()
    loss = (g["result_win_loss"] == "L").sum()
    clvs = g["clv"].dropna()
    return {"n": n, "win_pct": wins/n*100 if n else 0,
            "units": wins*WIN_UNIT - loss, "roi": _roi(wins, loss),
            "clv": clvs.mean() if len(clvs) else float("nan")}


EDGE_BUCKETS = [(0.0,0.5,"0.0–0.5"), (0.5,1.0,"0.5–1.0"),
                (1.0,1.5,"1.0–1.5"), (1.5,2.0,"1.5–2.0"),
                (2.0,float("inf"),"2.0+")]

PROB_THRESHOLDS = [0.50, 0.52, 0.53, 0.55, 0.58, 0.60]


def phase7_comparison_report(
    df_real_results: pd.DataFrame,
    df_proxy_results: pd.DataFrame,
    report_lines: list[str],
) -> None:
    def ln(s=""):
        report_lines.append(s)
        print(s)

    def sec(title):
        ln()
        ln(title)
        ln("=" * 76)

    def sub(title):
        ln()
        ln(title)
        ln("─" * 76)

    def hdr(cols, widths):
        ln("  " + "  ".join(f"{c:>{w}}" for c, w in zip(cols, widths)))

    def row(vals, widths, fmts=None):
        parts = []
        for i, (v, w) in enumerate(zip(vals, widths)):
            fmt = fmts[i] if fmts else None
            if fmt:
                s = fmt.format(v) if v == v else "–"  # nan check
            else:
                s = str(v) if v == v else "–"
            parts.append(f"{s:>{w}}")
        ln("  " + "  ".join(parts))

    # -----------------------------------------------------------------
    # Header
    # -----------------------------------------------------------------
    sec("PHASE 7 — PROXY vs REAL MARKET RESULTS")
    ln(f"  Generated : {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    ln()
    ln("  *** PROXY results: decision_line = 8.86 (league mean) — APPROXIMATE UPPER BOUND ***")
    ln("  *** REAL results:  decision_line = closing market line — HONEST MARKET BACKTEST  ***")
    ln()
    ln("  NOTE: REAL results use closing-only lines (decision = close).")
    ln("        CLV = 0 for all historical rows (no opening line available).")
    ln("        True CLV requires real opening lines — available from 2026 forward.")

    for season in [2024, 2025]:
        label = "Validation" if season == 2024 else "OOS"
        proxy = df_proxy_results[df_proxy_results["season"] == season]
        real  = df_real_results[df_real_results["season"] == season]
        n_p   = len(proxy)
        n_r   = len(real)

        # -----------------------------------------------------------------
        # 1. Probability thresholds
        # -----------------------------------------------------------------
        sec(f"1. RECORD BY PROBABILITY THRESHOLD — {season} {label}")
        ln(f"  Proxy n={n_p:,} (all games)   Real n={n_r:,} (games with real closing line)")
        hdr(["P Thresh","Prxy N","Prxy Win%","Prxy ROI","Real N","Real Win%","Real ROI"],
            [10,7,9,8,7,9,8])
        ln("  " + "─" * 64)
        for thresh in PROB_THRESHOLDS:
            p = _prob_row(proxy, thresh)
            r = _prob_row(real,  thresh)
            row([f"{thresh:.2f}",
                 f"{p['n']:,}", f"{p['win_pct']:.1f}%", f"{p['roi']:+.1f}%",
                 f"{r['n']:,}", f"{r['win_pct']:.1f}%", f"{r['roi']:+.1f}%"],
                [10,7,9,8,7,9,8])

        # -----------------------------------------------------------------
        # 2. Edge buckets
        # -----------------------------------------------------------------
        sec(f"2. EDGE BUCKET PERFORMANCE — {season} {label}")
        ln("  CLV = 0 for all real rows (closing-only backtest — no opening line)")
        hdr(["Edge","Prxy N","Prxy Win%","Prxy ROI","Real N","Real Win%","Real ROI","Avg CLV"],
            [8,7,9,8,7,9,8,9])
        ln("  " + "─" * 71)
        for lo, hi, label_bkt in EDGE_BUCKETS:
            p_mask = (proxy["abs_edge"] >= lo) & (proxy["abs_edge"] < hi)
            r_mask = (real["abs_edge"]  >= lo) & (real["abs_edge"]  < hi)
            pg = proxy[p_mask]; rg = real[r_mask]
            pn = len(pg); rn = len(rg)
            pw = (pg["result_win_loss"]=="W").sum(); pl = (pg["result_win_loss"]=="L").sum()
            rw = (rg["result_win_loss"]=="W").sum(); rl = (rg["result_win_loss"]=="L").sum()
            proi = _roi(pw,pl); rroi = _roi(rw,rl)
            rclv = rg["clv"].dropna()
            clv_str = f"{rclv.mean():+.3f}" if len(rclv) else "0.000"
            row([label_bkt,
                 f"{pn:,}", f"{pw/pn*100:.1f}%" if pn else "–", f"{proi:+.1f}%" if pn else "–",
                 f"{rn:,}", f"{rw/rn*100:.1f}%" if rn else "–", f"{rroi:+.1f}%" if rn else "–",
                 clv_str],
                [8,7,9,8,7,9,8,9])

        # -----------------------------------------------------------------
        # 3. ROI simulation
        # -----------------------------------------------------------------
        sec(f"3. ROI SIMULATION @ -110 (edge ≥ {BET_EDGE}, P ≥ {BET_PROB}) — {season} {label}")
        for label_src, df_src in [("PROXY (approx upper bound)", proxy),
                                   ("REAL  (market-honest)", real)]:
            sub(f"  {label_src}")
            flt = df_src[(df_src["abs_edge"] >= BET_EDGE) & (df_src["bet_prob"] >= BET_PROB)]
            n   = len(flt)
            if n == 0:
                ln("  No qualifying games.")
                continue
            wins  = (flt["result_win_loss"]=="W").sum()
            loss  = (flt["result_win_loss"]=="L").sum()
            push  = (flt["result_win_loss"]=="P").sum()
            units = wins*WIN_UNIT - loss
            roi   = _roi(wins, loss)
            ln(f"  Bets    : {n:,}")
            ln(f"  Win%    : {wins/n*100:.1f}%  ({wins}W / {loss}L / {push}P)")
            ln(f"  Units   : {units:+.2f}")
            ln(f"  ROI     : {roi:+.2f}%")

        # -----------------------------------------------------------------
        # 4. Confidence tier summary
        # -----------------------------------------------------------------
        sec(f"4. CONFIDENCE TIER SUMMARY — {season} {label}")
        hdr(["Tier","Prxy N","Prxy Win%","Prxy ROI","Real N","Real Win%","Real ROI"],
            [12,7,9,8,7,9,8])
        ln("  " + "─" * 64)
        for tier in ["STRONG","BET","WATCHLIST","NO_PLAY"]:
            pg = proxy[proxy["confidence_tier"]==tier]
            rg = real[real["confidence_tier"]==tier]
            pn = len(pg); rn = len(rg)
            pw = (pg["result_win_loss"]=="W").sum(); pl = (pg["result_win_loss"]=="L").sum()
            rw = (rg["result_win_loss"]=="W").sum(); rl = (rg["result_win_loss"]=="L").sum()
            proi = _roi(pw,pl); rroi = _roi(rw,rl)
            row([tier,
                 f"{pn:,}", f"{pw/pn*100:.1f}%" if pn else "–", f"{proi:+.1f}%" if pn else "–",
                 f"{rn:,}", f"{rw/rn*100:.1f}%" if rn else "–", f"{rroi:+.1f}%" if rn else "–"],
                [12,7,9,8,7,9,8])

        # -----------------------------------------------------------------
        # 5. Key takeaway
        # -----------------------------------------------------------------
        sec(f"5. COMPRESSION RATIO — {season} {label}")
        p_wins = (proxy["result_win_loss"]=="W").sum()
        r_wins = (real["result_win_loss"]=="W").sum()
        ln(f"  Proxy win% (all games, vs 8.86)   : {p_wins/n_p*100:.2f}%")
        ln(f"  Real  win% (matched, vs close line): {r_wins/n_r*100:.2f}%")
        delta = r_wins/n_r*100 - p_wins/n_p*100
        ln(f"  Delta                              : {delta:+.2f} pp")
        ln()
        ln("  Edge ≥ 1.0 & P ≥ 0.55 subset:")
        pf = proxy[(proxy["abs_edge"]>=1.0)&(proxy["bet_prob"]>=0.55)]
        rf = real [(real ["abs_edge"]>=1.0)&(real ["bet_prob"]>=0.55)]
        pw2 = (pf["result_win_loss"]=="W").sum()
        rw2 = (rf["result_win_loss"]=="W").sum()
        if len(pf):
            ln(f"    Proxy  : {pw2/len(pf)*100:.2f}% win, ROI {_roi(pw2,len(pf)-pw2):+.2f}%")
        if len(rf):
            ln(f"    Real   : {rw2/len(rf)*100:.2f}% win, ROI {_roi(rw2,len(rf)-rw2):+.2f}%")


# ===========================================================================
# Main
# ===========================================================================

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--plan",   action="store_true", help="Show credit plan only")
    ap.add_argument("--report", action="store_true", help="Run comparison report only")
    ap.add_argument("--limit",  type=int, default=0,
                    help="Max API calls this run (for incremental pulls; 0=unlimited)")
    args = ap.parse_args()

    # Load games
    gt = pd.read_parquet(DATA_DIR / "game_table.parquet")
    gt_sub = gt[gt["season"].isin([2024, 2025])].copy()
    df_plan = build_snapshot_plan(gt_sub)

    unique_snaps = df_plan[["snap_date","snap_hour"]].drop_duplicates().values.tolist()
    unique_snaps = [(r[0], int(r[1])) for r in unique_snaps]
    unique_snaps.sort()

    already_cached = [s for s in unique_snaps if _cache_path(s[0], s[1]).exists()]
    to_pull        = [s for s in unique_snaps if not _cache_path(s[0], s[1]).exists()]

    print("\n" + "=" * 76)
    print("  PHASE 7 — HISTORICAL LINE BACKFILL")
    print("=" * 76)
    print(f"  Games (2024+2025)    : {len(df_plan):,}")
    print(f"  Unique snapshots     : {len(unique_snaps):,}")
    print(f"  Already cached       : {len(already_cached):,}")
    print(f"  Need to pull         : {len(to_pull):,}")
    print(f"  Estimated new cost   : {len(to_pull)*10:,} credits")
    print(f"  API key              : {ODDS_API_KEY[:8]}…")

    if args.plan:
        print("\n  [--plan] No API calls made. Exiting.")
        return

    if args.report:
        print("\n  [--report] Skipping pull, going straight to comparison report.")
        to_pull = []

    # -----------------------------------------------------------------------
    # Pull
    # -----------------------------------------------------------------------
    all_responses: dict[tuple, dict] = {}

    # Load cached
    for sd, sh in already_cached:
        cp = _cache_path(sd, sh)
        with cp.open() as f:
            all_responses[(sd, sh)] = json.load(f)

    if to_pull:
        print(f"\n  Pulling {len(to_pull):,} snapshots…  (throttle: 1 req/s)")
        limit = args.limit if args.limit > 0 else len(to_pull)
        pulled = 0
        for i, (sd, sh) in enumerate(to_pull[:limit]):
            resp = pull_snapshot(sd, sh)
            if resp:
                all_responses[(sd, sh)] = resp
                remaining = resp.get("_meta", {}).get("remaining", "?")
                n_games   = len(resp.get("data", []))
                print(f"  [{i+1:04d}/{min(limit,len(to_pull))}] {sd} {sh:02d}:00Z  "
                      f"→ {n_games:2d} games  credits left: {remaining:,}")
                pulled += 1
            time.sleep(1.0)   # stay well under rate limit

        print(f"\n  Pulled {pulled:,} new snapshots.")
        remaining_str = ""
        for resp in all_responses.values():
            if "_meta" in resp:
                remaining_str = str(resp["_meta"].get("remaining", ""))
        if remaining_str:
            print(f"  Credits remaining (last snapshot): {remaining_str}")

    # -----------------------------------------------------------------------
    # Match games → lines
    # -----------------------------------------------------------------------
    print("\n  Matching games to lines…")
    game_lines = match_games_to_lines(df_plan, unique_snaps, all_responses)
    print(f"  Matched {len(game_lines):,} / {len(df_plan):,} games")

    # -----------------------------------------------------------------------
    # Populate Layer 2
    # -----------------------------------------------------------------------
    print("\n  Populating Layer 2 (market_snapshots.parquet)…")
    matched, unmatched = populate_layer2(df_plan, game_lines)
    print(f"  Layer 2 updated: {len(matched):,} real lines written")

    # Coverage report
    coverage_report(df_plan, matched, unmatched, game_lines)

    # -----------------------------------------------------------------------
    # Snapshot proxy baseline BEFORE rebuild overwrites Layer 4 rows
    # -----------------------------------------------------------------------
    PROXY_BASELINE = DATA_DIR / "bet_results_proxy_baseline.parquet"
    current_l4 = pd.read_parquet(p7.L4_PATH)
    proxy_rows  = current_l4[current_l4["decision_line_source"] == "proxy"]
    if len(proxy_rows) > 0:
        proxy_rows.to_parquet(PROXY_BASELINE, index=False)
        print(f"\n  Proxy baseline saved ({len(proxy_rows):,} rows) → {PROXY_BASELINE.name}")
    elif PROXY_BASELINE.exists():
        print(f"\n  Using existing proxy baseline → {PROXY_BASELINE.name}")
    else:
        print("\n  WARNING: no proxy rows found and no baseline file — proxy comparison unavailable")

    # -----------------------------------------------------------------------
    # Rebuild Layers 3 & 4
    # -----------------------------------------------------------------------
    print("\n  Rebuilding Layers 3 & 4 for matched games…")
    p7.rebuild_games_from_real_lines(matched)

    # -----------------------------------------------------------------------
    # Load both proxy and real result frames for comparison report
    # -----------------------------------------------------------------------
    df_results_all = pd.read_parquet(p7.L4_PATH)

    # Real results: rows where decision_line_source == "closing_only"
    df_real  = df_results_all[df_results_all["decision_line_source"] == SOURCE_LABEL].copy()
    # Proxy results: from snapshot taken before rebuild
    df_proxy = pd.read_parquet(PROXY_BASELINE) if PROXY_BASELINE.exists() else pd.DataFrame()

    print(f"\n  Real rows  (closing_only) : {len(df_real):,}")
    print(f"  Proxy rows (baseline)     : {len(df_proxy):,}")

    report_lines: list[str] = []
    phase7_comparison_report(df_real, df_proxy, report_lines)

    # Save report
    report_path = SIM_DIR / "reports" / "phase7_real_vs_proxy.txt"
    report_path.write_text("\n".join(report_lines))
    print(f"\n  Report saved → {report_path}")


if __name__ == "__main__":
    main()
