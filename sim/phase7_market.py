"""
Phase 7 — Market Integration (Option C: proxy baseline, forward-collection ready)
===================================================================================
Builds four strictly separated data layers:

  Layer 1  sim/data/model_outputs.parquet       — pure sim/model outputs, no market data
  Layer 2  sim/data/market_snapshots.parquet    — timestamped line snapshots by book
  Layer 3  sim/data/bet_decisions.parquet       — what the model would bet at decision time
  Layer 4  sim/data/bet_results.parquet         — actual_total, result, CLV, ROI unit

Historical rows (2024–2025):
  decision_line_source = "proxy"
  decision_line        = PROXY_LINE (8.86 — league season mean)
  close_total          = null
  clv                  = null

  ALL PROXY-BASED RESULTS ARE LABELED APPROXIMATE.
  Real market validation begins with the 2026 season.

Forward collection (2026+):
  Snapshots captured at 7am / noon / 5pm / close by the daily runner.
  CLV computed only when both decision_line and close_total are real lines.

Usage:
  python3 sim/phase7_market.py            # build all layers + run reporting
  python3 sim/phase7_market.py --layers   # build layers only
  python3 sim/phase7_market.py --report   # report only (layers must already exist)
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
REPO_ROOT   = Path(__file__).resolve().parent.parent
SIM_DIR     = Path(__file__).resolve().parent
DATA_DIR    = SIM_DIR / "data"
REPORT_DIR  = SIM_DIR / "reports"
DATA_DIR.mkdir(exist_ok=True)
REPORT_DIR.mkdir(exist_ok=True)

sys.path.insert(0, str(REPO_ROOT))
from config import (
    PROXY_LINE, WATCHLIST_EDGE, BET_EDGE, STRONG_EDGE,
    WATCHLIST_PROB, BET_PROB, STRONG_PROB, WIN_UNIT, JUICE,
)

# ---------------------------------------------------------------------------
# File paths for the four layers
# ---------------------------------------------------------------------------
L1_PATH  = DATA_DIR / "model_outputs.parquet"
L2_PATH  = DATA_DIR / "market_snapshots.parquet"
L3_PATH  = DATA_DIR / "bet_decisions.parquet"
L4_PATH  = DATA_DIR / "bet_results.parquet"
SRC_PATH = DATA_DIR / "phase5_sim_results.parquet"
REPORT_PATH = REPORT_DIR / "phase7_report.txt"

PROXY_SOURCE = "proxy"
REAL_SOURCE  = "real"

EDGE_BUCKETS = [0.0, 0.5, 1.0, 1.5, 2.0, float("inf")]
EDGE_LABELS  = ["0.0–0.5", "0.5–1.0", "1.0–1.5", "1.5–2.0", "2.0+"]
PROB_THRESHOLDS = [0.50, 0.52, 0.53, 0.55, 0.58, 0.60]


# ===========================================================================
# Helpers
# ===========================================================================

def _report(lines: list[str], msg: str) -> None:
    print(msg)
    lines.append(msg)


def _section(lines: list[str], title: str, width: int = 76) -> None:
    _report(lines, "")
    _report(lines, title)
    _report(lines, "=" * width)


def _sub(lines: list[str], title: str, width: int = 76) -> None:
    _report(lines, "")
    _report(lines, title)
    _report(lines, "─" * width)


def _confidence_tier(edge: float, prob: float) -> str:
    """Classify a bet by edge (runs) and P(bet side)."""
    if edge >= STRONG_EDGE and prob >= STRONG_PROB:
        return "STRONG"
    if edge >= BET_EDGE and prob >= BET_PROB:
        return "BET"
    if edge >= WATCHLIST_EDGE and prob >= WATCHLIST_PROB:
        return "WATCHLIST"
    return "NO_PLAY"


def _roi(wins: int, losses: int) -> float:
    total = wins + losses
    if total == 0:
        return float("nan")
    return (wins * WIN_UNIT - losses * 1.0) / total * 100


# ===========================================================================
# Layer 1 — Model outputs
# ===========================================================================

def build_layer1() -> pd.DataFrame:
    """
    Layer 1: pure model outputs — no market data.
    Reads phase5_sim_results.parquet and re-saves with canonical game_id column.
    """
    raw = pd.read_parquet(SRC_PATH)

    # Rename game_pk → game_id for cross-layer consistency
    df = raw.rename(columns={"game_pk": "game_id"})

    # Ensure column order
    cols = [
        "game_id", "date", "season", "home_team", "away_team",
        "ridge_pred", "sim_mean", "sim_sigma",
        "p_over", "p_under",
        "ci_lo", "ci_hi",
        "review_flag", "extreme_flag", "diverge_flag",
        "actual_total",
    ]
    df = df[cols]
    df.to_parquet(L1_PATH, index=False)
    print(f"[Layer 1] Saved {len(df):,} rows → {L1_PATH.name}")
    return df


# ===========================================================================
# Layer 2 — Market snapshots
# ===========================================================================

def build_layer2_proxy(df_model: pd.DataFrame) -> pd.DataFrame:
    """
    Layer 2 (historical proxy): one row per (game_id, book='proxy').
    All line fields null — decision_line = PROXY_LINE.
    Schema is forward-collection-ready; real snapshots can be appended with no
    redesign, just populating the currently-null columns.
    """
    rows = []
    for _, row in df_model.iterrows():
        rows.append({
            "game_id":              row["game_id"],
            "date":                 row["date"],
            "book":                 "proxy",
            # Timestamped snapshot fields — null for proxy rows
            "snapshot_time":        pd.NaT,
            "open_total":           np.nan,
            "noon_total":           np.nan,
            "five_pm_total":        np.nan,
            "close_total":          np.nan,
            "over_price":           np.nan,
            "under_price":          np.nan,
            # Decision line (the proxy value used as the model's reference line)
            "decision_line":        PROXY_LINE,
            "decision_line_source": PROXY_SOURCE,
            # CLV null — requires real decision_line AND real close_total
            "clv":                  np.nan,
        })
    df = pd.DataFrame(rows)
    df["snapshot_time"] = pd.to_datetime(df["snapshot_time"])
    df["date"] = df["date"].astype(str)
    df.to_parquet(L2_PATH, index=False)
    print(f"[Layer 2] Saved {len(df):,} rows → {L2_PATH.name}")
    return df


def append_real_snapshot(
    game_id: int,
    date: str,
    book: str,
    snapshot_time: datetime,
    total: float,
    over_price: float,
    under_price: float,
    snapshot_slot: str,           # "open" | "noon" | "five_pm" | "close"
    decision_line: Optional[float] = None,
) -> None:
    """
    Forward-collection helper — called by the daily runner (run_model.py /
    refresh.py) to append a real market snapshot to Layer 2.

    snapshot_slot controls which denormalized column is filled:
      "open"    → open_total
      "noon"    → noon_total
      "five_pm" → five_pm_total
      "close"   → close_total

    If a row for (game_id, book) already exists, it is updated in place.
    Otherwise a new row is appended.

    CLV is computed only when both decision_line and close_total are present
    on the same row AND decision_line_source == "real".
    """
    if not L2_PATH.exists():
        raise FileNotFoundError(
            "Layer 2 (market_snapshots.parquet) does not exist. "
            "Run build_layer2_proxy() first."
        )
    df = pd.read_parquet(L2_PATH)

    # Normalize snapshot_time to tz-naive UTC so it's compatible with stored dtype
    if isinstance(snapshot_time, datetime) and snapshot_time.tzinfo is not None:
        snapshot_time = snapshot_time.replace(tzinfo=None)

    slot_col = {
        "open":    "open_total",
        "noon":    "noon_total",
        "five_pm": "five_pm_total",
        "close":   "close_total",
    }[snapshot_slot]

    mask = (df["game_id"] == game_id) & (df["book"] == book)

    if mask.any():
        idx = df[mask].index[0]
        df.at[idx, slot_col]              = total
        df.at[idx, "snapshot_time"]       = snapshot_time
        df.at[idx, "over_price"]          = over_price
        df.at[idx, "under_price"]         = under_price
        if decision_line is not None:
            df.at[idx, "decision_line"]        = decision_line
            df.at[idx, "decision_line_source"] = REAL_SOURCE
        # Recompute CLV if we now have both close_total and a real decision_line
        row = df.loc[idx]
        if (
            not pd.isna(row["close_total"])
            and not pd.isna(row["decision_line"])
            and row["decision_line_source"] == REAL_SOURCE
        ):
            # Populated in bet_results; store here as well for convenience
            # CLV direction depends on the bet side; Layer 3 holds bet_side.
            # We store raw (close - decision) here; sign applied in Layer 4.
            df.at[idx, "clv"] = row["close_total"] - row["decision_line"]
    else:
        new_row = {
            "game_id":              game_id,
            "date":                 date,
            "book":                 book,
            "snapshot_time":        snapshot_time,
            "open_total":           np.nan,
            "noon_total":           np.nan,
            "five_pm_total":        np.nan,
            "close_total":          np.nan,
            "over_price":           over_price,
            "under_price":          under_price,
            "decision_line":        decision_line if decision_line else PROXY_LINE,
            "decision_line_source": REAL_SOURCE if decision_line else PROXY_SOURCE,
            "clv":                  np.nan,
        }
        new_row[slot_col] = total
        df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)

    df.to_parquet(L2_PATH, index=False)


# ===========================================================================
# Layer 3 — Bet decisions
# ===========================================================================

def build_layer3(df_model: pd.DataFrame, df_snap: pd.DataFrame) -> pd.DataFrame:
    """
    Layer 3: what the model would bet at decision time.
    One row per game_id (using the model's lean vs the decision_line).

    For proxy rows:
      - decision_time = null (no real decision timestamp)
      - decision_line = PROXY_LINE
      - edge and p_over_vs_decision_line come from phase5 simulation outputs
        (which were already computed vs PROXY_LINE)
      - decision_line_source = "proxy"

    For real rows (2026+):
      - decision_time = snapshot_time from Layer 2
      - decision_line = real morning or opening line
      - p_over_vs_decision_line recomputed from N(ridge_pred, sim_sigma) vs
        real decision_line using the fast vectorized helper
    """
    # Merge on game_id using the earliest snapshot (or proxy row)
    snap = df_snap.drop_duplicates("game_id", keep="first")
    df = df_model.merge(
        snap[["game_id", "snapshot_time", "decision_line", "decision_line_source"]],
        on="game_id", how="left",
    )

    rows = []
    for _, row in df.iterrows():
        dl      = row["decision_line"]
        dl_src  = row["decision_line_source"]
        rp      = row["ridge_pred"]
        sigma   = row["sim_sigma"]

        # Edge = signed (ridge_pred - decision_line); positive = lean OVER
        signed_edge = rp - dl

        if dl_src == PROXY_SOURCE:
            # p_over / p_under from Phase 5 already computed vs PROXY_LINE
            p_over_dl  = row["p_over"]
            p_under_dl = row["p_under"]
        else:
            # Recompute P(over) vs real decision_line via fast simulation
            draws         = np.random.normal(rp, sigma, 10_000)
            p_over_dl     = float((draws > dl).mean())
            p_under_dl    = 1.0 - p_over_dl

        if signed_edge >= 0:
            bet_side = "over"
            bet_prob = p_over_dl
        else:
            bet_side = "under"
            bet_prob = p_under_dl

        abs_edge = abs(signed_edge)
        tier     = _confidence_tier(abs_edge, bet_prob)

        rows.append({
            "game_id":                   int(row["game_id"]),
            "date":                      row["date"],
            "season":                    int(row["season"]),
            "home_team":                 row["home_team"],
            "away_team":                 row["away_team"],
            "decision_time":             row["snapshot_time"],   # NaT for proxy
            "decision_line":             dl,
            "decision_line_source":      dl_src,
            "projected_total":           round(rp, 4),
            "edge_vs_decision_line":     round(signed_edge, 4),
            "abs_edge":                  round(abs_edge, 4),
            "p_over_vs_decision_line":   round(p_over_dl, 4),
            "p_under_vs_decision_line":  round(p_under_dl, 4),
            "bet_side":                  bet_side,
            "bet_prob":                  round(bet_prob, 4),
            "confidence_tier":           tier,
        })

    decisions = pd.DataFrame(rows)
    decisions.to_parquet(L3_PATH, index=False)
    print(f"[Layer 3] Saved {len(decisions):,} rows → {L3_PATH.name}")
    return decisions


# ===========================================================================
# Layer 4 — Bet results
# ===========================================================================

def build_layer4(df_model: pd.DataFrame,
                 df_decisions: pd.DataFrame,
                 df_snap: pd.DataFrame) -> pd.DataFrame:
    """
    Layer 4: per-game actual results, CLV, and ROI unit.

    CLV rules:
      Over bet:  CLV = close_total − decision_line   (positive = line moved our way)
      Under bet: CLV = decision_line − close_total
      If close_total is null (proxy rows): CLV = null, marked unavailable.
      If decision_line_source = "proxy": CLV = null (closing-only backtest caveat).

    ROI:
      Win at -110: +WIN_UNIT units (~+0.9091)
      Loss at -110: -1.0 unit
      Push (actual == decision_line): 0.0 units
    """
    snap = df_snap.drop_duplicates("game_id", keep="first")[
        ["game_id", "close_total", "decision_line_source"]
    ]
    dec = df_decisions[[
        "game_id", "bet_side", "decision_line", "decision_line_source",
        "projected_total", "abs_edge", "bet_prob", "confidence_tier",
    ]]

    # Include date/season/teams from model layer so they survive into results
    base = df_model[["game_id", "actual_total", "date", "season",
                      "home_team", "away_team"]]
    df = base.merge(dec, on="game_id", how="left")
    df = df.merge(snap, on="game_id", how="left", suffixes=("", "_snap"))

    rows = []
    for _, row in df.iterrows():
        actual    = row["actual_total"]
        dl        = row["decision_line"]
        bet_side  = row["bet_side"]
        close     = row["close_total"]    # NaN for proxy rows
        dl_src    = row["decision_line_source"]

        # Win/loss: did the actual land on our bet side vs the decision line?
        if actual > dl:
            result = "W" if bet_side == "over"  else "L"
        elif actual < dl:
            result = "W" if bet_side == "under" else "L"
        else:
            result = "P"  # push

        roi = WIN_UNIT if result == "W" else (-1.0 if result == "L" else 0.0)

        # CLV
        if pd.isna(close) or dl_src == PROXY_SOURCE:
            clv = np.nan
        else:
            clv = (close - dl) if bet_side == "over" else (dl - close)

        rows.append({
            "game_id":              int(row["game_id"]),
            "date":                 row["date"],
            "season":               int(row["season"]),
            "home_team":            row["home_team"],
            "away_team":            row["away_team"],
            "actual_total":         float(actual),
            "decision_line":        dl,
            "decision_line_source": dl_src,
            "bet_side":             bet_side,
            "confidence_tier":      row["confidence_tier"],
            "abs_edge":             row["abs_edge"],
            "bet_prob":             row["bet_prob"],
            "result_win_loss":      result,
            "roi_unit_result":      roi,
            "close_total":          close if not pd.isna(close) else np.nan,
            "clv":                  clv,
        })

    results = pd.DataFrame(rows)
    results.to_parquet(L4_PATH, index=False)
    print(f"[Layer 4] Saved {len(results):,} rows → {L4_PATH.name}")
    return results


# ===========================================================================
# Rebuild Layers 3 & 4 for specific game_ids (real-line forward collection)
# ===========================================================================

def rebuild_games_from_real_lines(game_ids: list[int]) -> None:
    """
    Called by the daily runner after real closing lines are captured in Layer 2.
    Re-derives Layer 3 (bet decisions) and Layer 4 (bet results) for the
    specified game_ids using the real decision_line and close_total.

    All other game_ids (proxy rows) are left unchanged.

    Workflow for forward collection:
      1. append_real_snapshot(..., slot="open")     → morning line stored
      2. append_real_snapshot(..., slot="close")    → closing line stored, CLV computable
      3. rebuild_games_from_real_lines([game_id])   → L3/L4 updated with real figures
    """
    df_model     = pd.read_parquet(L1_PATH)
    df_snap_all  = pd.read_parquet(L2_PATH)
    df_dec_all   = pd.read_parquet(L3_PATH)
    df_res_all   = pd.read_parquet(L4_PATH)

    for gid in game_ids:
        # Layer 1 row for this game
        m_row = df_model[df_model["game_id"] == gid]
        if m_row.empty:
            print(f"[rebuild] WARNING: game_id {gid} not found in Layer 1 — skipping")
            continue
        m = m_row.iloc[0]

        # Layer 2: prefer book with real decision_line; fall back to any row
        snap_rows = df_snap_all[df_snap_all["game_id"] == gid]
        real_rows = snap_rows[snap_rows["decision_line_source"] == REAL_SOURCE]
        snap = (real_rows.iloc[0] if not real_rows.empty else snap_rows.iloc[0])

        rp      = m["ridge_pred"]
        sigma   = m["sim_sigma"]
        dl      = snap["decision_line"]
        dl_src  = snap["decision_line_source"]
        close   = snap["close_total"]
        snap_t  = snap["snapshot_time"]

        # Recompute P(over) vs real decision_line
        draws      = np.random.normal(rp, sigma, 10_000)
        p_over_dl  = float((draws > dl).mean())
        p_under_dl = 1.0 - p_over_dl

        signed_edge = rp - dl
        if signed_edge >= 0:
            bet_side = "over"
            bet_prob = p_over_dl
        else:
            bet_side = "under"
            bet_prob = p_under_dl

        abs_edge = abs(signed_edge)
        tier     = _confidence_tier(abs_edge, bet_prob)

        # Update Layer 3
        new_dec = {
            "game_id":                   gid,
            "date":                      m["date"],
            "season":                    int(m["season"]),
            "home_team":                 m["home_team"],
            "away_team":                 m["away_team"],
            "decision_time":             snap_t,
            "decision_line":             dl,
            "decision_line_source":      dl_src,
            "projected_total":           round(rp, 4),
            "edge_vs_decision_line":     round(signed_edge, 4),
            "abs_edge":                  round(abs_edge, 4),
            "p_over_vs_decision_line":   round(p_over_dl, 4),
            "p_under_vs_decision_line":  round(p_under_dl, 4),
            "bet_side":                  bet_side,
            "bet_prob":                  round(bet_prob, 4),
            "confidence_tier":           tier,
        }
        # Normalize snapshot_time to tz-naive UTC to match stored dtype
        if isinstance(new_dec.get("decision_time"), datetime):
            dt = new_dec["decision_time"]
            if dt.tzinfo is not None:
                new_dec["decision_time"] = dt.replace(tzinfo=None)

        mask3 = df_dec_all["game_id"] == gid
        if mask3.any():
            for k, v in new_dec.items():
                df_dec_all.loc[mask3, k] = v
        else:
            df_dec_all = pd.concat(
                [df_dec_all, pd.DataFrame([new_dec])], ignore_index=True
            )

        # Layer 4 result
        actual = m["actual_total"]
        if actual > dl:
            result = "W" if bet_side == "over" else "L"
        elif actual < dl:
            result = "W" if bet_side == "under" else "L"
        else:
            result = "P"

        roi_unit = WIN_UNIT if result == "W" else (-1.0 if result == "L" else 0.0)

        if pd.isna(close) or dl_src == PROXY_SOURCE:
            clv = np.nan
        else:
            clv = (close - dl) if bet_side == "over" else (dl - close)

        new_res = {
            "game_id":              gid,
            "date":                 m["date"],
            "season":               int(m["season"]),
            "home_team":            m["home_team"],
            "away_team":            m["away_team"],
            "actual_total":         float(actual),
            "decision_line":        dl,
            "decision_line_source": dl_src,
            "bet_side":             bet_side,
            "confidence_tier":      tier,
            "abs_edge":             round(abs_edge, 4),
            "bet_prob":             round(bet_prob, 4),
            "result_win_loss":      result,
            "roi_unit_result":      roi_unit,
            "close_total":          float(close) if not pd.isna(close) else np.nan,
            "clv":                  clv,
        }
        mask4 = df_res_all["game_id"] == gid
        if mask4.any():
            for k, v in new_res.items():
                df_res_all.loc[mask4, k] = v
        else:
            df_res_all = pd.concat(
                [df_res_all, pd.DataFrame([new_res])], ignore_index=True
            )

        print(f"[rebuild] game_id {gid}  dl={dl}  close={close}  "
              f"bet={bet_side}  result={result}  clv={clv!r}")

    df_dec_all.to_parquet(L3_PATH, index=False)
    df_res_all.to_parquet(L4_PATH, index=False)
    print(f"[rebuild] Layer 3 + 4 updated for {len(game_ids)} game(s)")


# ===========================================================================
# Reporting helpers
# ===========================================================================

def _prob_threshold_table(df: pd.DataFrame, season: int,
                           lines: list[str]) -> None:
    sub = df[df["season"] == season]
    header = (
        f"  {'P Thresh':>10}  {'N Bets':>7}  "
        f"{'Win%':>7}  {'Units Won':>10}  {'ROI%':>7}"
    )
    _report(lines, header)
    _report(lines, "  " + "─" * 54)
    for thresh in PROB_THRESHOLDS:
        mask = sub["bet_prob"] >= thresh
        g = sub[mask]
        n   = len(g)
        if n == 0:
            _report(lines, f"  {thresh:>10.2f}  {'–':>7}  {'–':>7}  {'–':>10}  {'–':>7}")
            continue
        wins   = (g["result_win_loss"] == "W").sum()
        losses = (g["result_win_loss"] == "L").sum()
        units  = wins * WIN_UNIT - losses * 1.0
        roi    = _roi(wins, losses)
        _report(lines,
            f"  {thresh:>10.2f}  {n:>7,}  "
            f"{wins/n*100:>6.1f}%  {units:>+10.2f}  {roi:>+6.2f}%"
        )


def _edge_bucket_table(df: pd.DataFrame, season: int,
                       lines: list[str]) -> None:
    sub = df[df["season"] == season]
    header = (
        f"  {'Edge Bucket':>12}  {'N':>6}  {'Win%':>7}  "
        f"{'Units':>8}  {'ROI%':>7}  {'Avg CLV':>9}"
    )
    _report(lines, header)
    _report(lines, "  " + "─" * 62)
    for lo, hi, label in zip(EDGE_BUCKETS[:-1], EDGE_BUCKETS[1:], EDGE_LABELS):
        mask = (sub["abs_edge"] >= lo) & (sub["abs_edge"] < hi)
        g = sub[mask]
        n = len(g)
        if n == 0:
            _report(lines, f"  {label:>12}  {n:>6,}  {'–':>7}  {'–':>8}  {'–':>7}  {'–':>9}")
            continue
        wins   = (g["result_win_loss"] == "W").sum()
        losses = (g["result_win_loss"] == "L").sum()
        units  = wins * WIN_UNIT - losses * 1.0
        roi    = _roi(wins, losses)
        clv_mean = g["clv"].mean()
        clv_str  = f"{clv_mean:+.3f}" if not np.isnan(clv_mean) else "N/A (proxy)"
        _report(lines,
            f"  {label:>12}  {n:>6,}  {wins/n*100:>6.1f}%  "
            f"{units:>+8.2f}  {roi:>+6.2f}%  {clv_str:>9}"
        )


def _roi_simulation(df: pd.DataFrame, season: int,
                    lines: list[str]) -> None:
    """Simulate betting every game where edge ≥ BET_EDGE AND prob ≥ BET_PROB."""
    sub  = df[df["season"] == season]
    mask = (sub["abs_edge"] >= BET_EDGE) & (sub["bet_prob"] >= BET_PROB)
    g    = sub[mask]
    n    = len(g)
    if n == 0:
        _report(lines, "  No bets qualify at this filter.")
        return
    wins    = (g["result_win_loss"] == "W").sum()
    losses  = (g["result_win_loss"] == "L").sum()
    pushes  = (g["result_win_loss"] == "P").sum()
    units   = wins * WIN_UNIT - losses * 1.0
    roi     = _roi(wins, losses)
    clv_mean = g["clv"].mean()
    clv_str  = f"{clv_mean:+.4f}" if not np.isnan(clv_mean) else "N/A (proxy)"
    _report(lines, f"  Filter: abs_edge ≥ {BET_EDGE}  AND  P(bet side) ≥ {BET_PROB}")
    _report(lines, f"  Pricing: {JUICE} (Win unit: {WIN_UNIT:.4f})")
    _report(lines, "")
    _report(lines, f"  Total bets : {n:,}")
    _report(lines, f"  Wins       : {wins:,}  ({wins/n*100:.1f}%)")
    _report(lines, f"  Losses     : {losses:,}  ({losses/n*100:.1f}%)")
    _report(lines, f"  Pushes     : {pushes:,}")
    _report(lines, f"  Units W/L  : {units:+.2f}")
    _report(lines, f"  ROI        : {roi:+.2f}%")
    _report(lines, f"  Avg CLV    : {clv_str}")


def _prob_calibration(df: pd.DataFrame, season: int,
                      lines: list[str]) -> None:
    """Calibration: does P(bet side) predict actual win rate?"""
    sub = df[df["season"] == season].copy()
    if len(sub) == 0:
        _report(lines, "  No data for this season.")
        return
    n_bins = 10
    # Use quantile-based bins so each bin has equal count even if range is narrow
    try:
        sub["prob_bin"] = pd.qcut(sub["bet_prob"], q=n_bins, precision=2, duplicates="drop")
    except ValueError:
        sub["prob_bin"] = pd.cut(sub["bet_prob"], bins=n_bins, precision=2)
    grp = sub.groupby("prob_bin", observed=True)
    header = (
        f"  {'P(bet side) bin':>20}  {'N':>6}  "
        f"{'Model P (mid)':>14}  {'Actual Win%':>12}  {'Diff':>8}"
    )
    _report(lines, header)
    _report(lines, "  " + "─" * 68)
    for name, g in grp:
        n      = len(g)
        mid    = (name.left + name.right) / 2
        wins   = (g["result_win_loss"] == "W").sum()
        actual = wins / n if n > 0 else float("nan")
        diff   = actual - mid
        _report(lines,
            f"  {str(name):>20}  {n:>6,}  {mid:>14.3f}  "
            f"{actual*100:>11.1f}%  {diff:>+7.3f}"
        )


def _confidence_tier_summary(df: pd.DataFrame, season: int,
                              lines: list[str]) -> None:
    sub = df[df["season"] == season]
    header = (
        f"  {'Tier':>12}  {'N':>6}  {'Win%':>7}  "
        f"{'Units':>8}  {'ROI%':>7}"
    )
    _report(lines, header)
    _report(lines, "  " + "─" * 52)
    for tier in ["STRONG", "BET", "WATCHLIST", "NO_PLAY"]:
        g = sub[sub["confidence_tier"] == tier]
        n = len(g)
        if n == 0:
            continue
        wins    = (g["result_win_loss"] == "W").sum()
        losses  = (g["result_win_loss"] == "L").sum()
        units   = wins * WIN_UNIT - losses * 1.0
        roi     = _roi(wins, losses)
        _report(lines,
            f"  {tier:>12}  {n:>6,}  {wins/n*100:>6.1f}%  "
            f"{units:>+8.2f}  {roi:>+6.2f}%"
        )


# ===========================================================================
# Schema display
# ===========================================================================

def _show_schema(label: str, df: pd.DataFrame, n: int = 3) -> None:
    print(f"\n{'─'*76}")
    print(f"  {label}")
    print(f"{'─'*76}")
    print(f"  Shape: {df.shape[0]:,} rows × {df.shape[1]} cols")
    print(f"  Columns:")
    for col in df.columns:
        dtype = str(df[col].dtype)
        null_pct = df[col].isna().mean() * 100
        print(f"    {col:<32} {dtype:<12}  {null_pct:.0f}% null")
    print(f"\n  Sample rows (n={n}):")
    with pd.option_context("display.max_columns", None, "display.width", 120,
                           "display.max_colwidth", 20):
        print(df.head(n).to_string(index=False))


# ===========================================================================
# Main
# ===========================================================================

def build_all_layers() -> tuple[pd.DataFrame, ...]:
    print("\n" + "=" * 76)
    print("  PHASE 7 — Building Four Data Layers")
    print("=" * 76)
    print(f"  Source      : {SRC_PATH.name}")
    print(f"  Proxy line  : {PROXY_LINE} runs (2024–2025 backtest baseline)")
    print(f"  Decision src: '{PROXY_SOURCE}' (historical — not market-validated)")
    print()

    df_model     = build_layer1()
    df_snap      = build_layer2_proxy(df_model)
    df_decisions = build_layer3(df_model, df_snap)
    df_results   = build_layer4(df_model, df_decisions, df_snap)

    return df_model, df_snap, df_decisions, df_results


def run_report(df_model: pd.DataFrame,
               df_snap: pd.DataFrame,
               df_decisions: pd.DataFrame,
               df_results: pd.DataFrame) -> None:

    lines: list[str] = []

    _section(lines, "PHASE 7 — MARKET INTEGRATION REPORT")
    _report(lines, f"  Generated : {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    _report(lines, f"  Source    : {SRC_PATH.name}")
    _report(lines, f"  Seasons   : 2024 (validation) | 2025 (OOS)")
    _report(lines, "")
    _report(lines, "  *** IMPORTANT — PROXY-BASED BACKTEST ***")
    _report(lines, "  All 2024–2025 results use proxy line = 8.86 (league season mean).")
    _report(lines, "  decision_line_source = 'proxy' for all historical rows.")
    _report(lines, "  close_total = null. CLV = null (unavailable for proxy rows).")
    _report(lines, "  Results are APPROXIMATE and NOT market-validated.")
    _report(lines, "  Real market validation begins with the 2026 season.")
    _report(lines, "")
    _report(lines, f"  Thresholds used:")
    _report(lines, f"    WATCHLIST_EDGE={WATCHLIST_EDGE}  BET_EDGE={BET_EDGE}  STRONG_EDGE={STRONG_EDGE}")
    _report(lines, f"    WATCHLIST_PROB={WATCHLIST_PROB}  BET_PROB={BET_PROB}  STRONG_PROB={STRONG_PROB}")
    _report(lines, f"    JUICE={-110}  WIN_UNIT={WIN_UNIT:.4f}")

    # -----------------------------------------------------------------
    # Section 1: Record by probability threshold
    # -----------------------------------------------------------------
    _section(lines, "1. RECORD BY PROBABILITY THRESHOLD (P ≥ threshold on bet side)")
    _report(lines, "   [PROXY-BASED — line = 8.86 league mean, NOT real market totals]")

    for season in [2024, 2025]:
        label = "Validation" if season == 2024 else "OOS"
        _sub(lines, f"  {season} {label}  (n={len(df_results[df_results['season']==season]):,})")
        _prob_threshold_table(df_results, season, lines)

    # Side-by-side summary
    _sub(lines, "  Quick-compare: Win% at key thresholds (2024 validation | 2025 OOS)")
    header = f"  {'P Thresh':>10}  {'2024 N':>8}  {'2024 Win%':>10}  {'2025 N':>8}  {'2025 Win%':>10}"
    _report(lines, header)
    _report(lines, "  " + "─" * 54)
    for thresh in PROB_THRESHOLDS:
        r24 = df_results[(df_results["season"] == 2024) & (df_results["bet_prob"] >= thresh)]
        r25 = df_results[(df_results["season"] == 2025) & (df_results["bet_prob"] >= thresh)]
        w24 = (r24["result_win_loss"] == "W").sum() / max(len(r24), 1) * 100
        w25 = (r25["result_win_loss"] == "W").sum() / max(len(r25), 1) * 100
        _report(lines,
            f"  {thresh:>10.2f}  {len(r24):>8,}  {w24:>9.1f}%  {len(r25):>8,}  {w25:>9.1f}%"
        )

    # -----------------------------------------------------------------
    # Section 2: Edge bucket performance
    # -----------------------------------------------------------------
    _section(lines, "2. EDGE BUCKET PERFORMANCE  (edge = |ridge_pred − proxy_line|)")
    _report(lines, "   [PROXY-BASED — CLV column will be 'N/A (proxy)' until real lines collected]")

    for season in [2024, 2025]:
        label = "Validation" if season == 2024 else "OOS"
        _sub(lines, f"  {season} {label}")
        _edge_bucket_table(df_results, season, lines)

    # -----------------------------------------------------------------
    # Section 3: ROI simulation at -110
    # -----------------------------------------------------------------
    _section(lines,
        f"3. ROI SIMULATION @ -110  (filter: edge ≥ {BET_EDGE} AND P ≥ {BET_PROB})")
    _report(lines, "   [PROXY-BASED — approximate ROI estimate only]")

    for season in [2024, 2025]:
        label = "Validation" if season == 2024 else "OOS"
        _sub(lines, f"  {season} {label}")
        _roi_simulation(df_results, season, lines)

    # -----------------------------------------------------------------
    # Section 4: Calibration vs proxy line
    # -----------------------------------------------------------------
    _section(lines, "4. PROBABILITY CALIBRATION vs PROXY LINE")
    _report(lines, "   [Replaces Phase 5 proxy calibration — same proxy, richer edge/tier view]")
    _report(lines, "   [Real calibration test vs actual market lines begins 2026 season]")

    for season in [2024, 2025]:
        label = "Validation" if season == 2024 else "OOS"
        _sub(lines, f"  {season} {label} — P(bet side) decile calibration")
        _prob_calibration(df_results, season, lines)

    # -----------------------------------------------------------------
    # Section 5: Confidence tier summary
    # -----------------------------------------------------------------
    _section(lines, "5. CONFIDENCE TIER SUMMARY")
    _report(lines, "   STRONG: edge ≥ 1.5 AND P ≥ 0.58")
    _report(lines, "   BET:    edge ≥ 1.0 AND P ≥ 0.55")
    _report(lines, "   WATCHLIST: edge ≥ 0.5 AND P ≥ 0.53")
    _report(lines, "   NO_PLAY: all others")

    for season in [2024, 2025]:
        label = "Validation" if season == 2024 else "OOS"
        _sub(lines, f"  {season} {label}")
        _confidence_tier_summary(df_results, season, lines)

    # -----------------------------------------------------------------
    # Section 6: Data layer inventory
    # -----------------------------------------------------------------
    _section(lines, "6. DATA LAYER INVENTORY")
    for path, label in [
        (L1_PATH, "Layer 1 — model_outputs.parquet"),
        (L2_PATH, "Layer 2 — market_snapshots.parquet"),
        (L3_PATH, "Layer 3 — bet_decisions.parquet"),
        (L4_PATH, "Layer 4 — bet_results.parquet"),
    ]:
        df_tmp = pd.read_parquet(path)
        null_pct = df_tmp.isna().mean().mean() * 100
        _report(lines,
            f"  {label:<42}  {len(df_tmp):>6,} rows  "
            f"{df_tmp.shape[1]} cols  {null_pct:.0f}% avg null"
        )

    _report(lines, "")
    _report(lines, "  Forward-collection hooks ready in append_real_snapshot().")
    _report(lines, "  When real 2026 lines are collected:")
    _report(lines, "    - Populate close_total, over_price, under_price in Layer 2")
    _report(lines, "    - Rerun Layer 3/4 for those game_ids with decision_line_source='real'")
    _report(lines, "    - CLV and validated ROI will auto-populate in Layer 4")

    # -----------------------------------------------------------------
    # Save report
    # -----------------------------------------------------------------
    txt = "\n".join(lines)
    REPORT_PATH.write_text(txt)
    print(f"\n[Report] Saved → {REPORT_PATH}")


# ===========================================================================
# Entry point
# ===========================================================================

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--layers", action="store_true", help="Build layers only, skip report")
    ap.add_argument("--report", action="store_true", help="Run report only (layers must exist)")
    args = ap.parse_args()

    if args.report and not args.layers:
        # Load existing layers
        df_model     = pd.read_parquet(L1_PATH)
        df_snap      = pd.read_parquet(L2_PATH)
        df_decisions = pd.read_parquet(L3_PATH)
        df_results   = pd.read_parquet(L4_PATH)
    else:
        df_model, df_snap, df_decisions, df_results = build_all_layers()

    if not args.layers:
        # Show schemas before report
        print("\n" + "=" * 76)
        print("  LAYER SCHEMAS & SAMPLE ROWS")
        print("=" * 76)
        _show_schema("Layer 1 — model_outputs.parquet  [pure model, no market data]",
                     df_model)
        _show_schema("Layer 2 — market_snapshots.parquet  [proxy rows; null = awaiting real lines]",
                     df_snap)
        _show_schema("Layer 3 — bet_decisions.parquet", df_decisions)
        _show_schema("Layer 4 — bet_results.parquet", df_results)

        print("\n" + "=" * 76)
        print("  PHASE 7 REPORT")
        print("=" * 76)
        run_report(df_model, df_snap, df_decisions, df_results)


if __name__ == "__main__":
    main()
