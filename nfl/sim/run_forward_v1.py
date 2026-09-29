#!/usr/bin/env python3
"""
FWD1 (D211): forward-test harness for the frozen NFL sim v1.

Usage:
  python3 nfl/sim/run_forward_v1.py --week 4 [--pilot] [--as-of 2026-09-28T17:00:00+00:00]

Steps:
  (a) test_freeze_v1 in-process — HALT if it fails
  (b) sheet: build the Hard Rock prop sheet via log_ai_opinions.py
  (c) sim: run nfl/sim/run_week.py for the week, read picks_log.parquet
  (d) fill: match picks_log to sheet, set p_first/tag/reason
  (e) freeze: freeze with --reader-model nfl_sim_v1_156cd057
  (f) anchor sidecar: per-game anchoring metadata
"""

import argparse, json, os, subprocess, sys, tempfile, time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

READER_MODEL = "nfl_sim_v1_156cd057"
SEASON = 2026
ANCHOR_MISS_TOL = 1.0  # margin OR total miss > 1.0 -> unanchored


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--week", type=int, required=True)
    ap.add_argument("--pilot", action="store_true")
    ap.add_argument("--as-of", help="UTC ISO timestamp (pilot only)")
    a = ap.parse_args()

    if a.as_of and not a.pilot:
        sys.exit("HALT: --as-of requires --pilot")

    week = a.week
    pilot = a.pilot
    as_of = a.as_of

    # (a) test_freeze_v1 in-process
    print("(a) Running test_freeze_v1...", flush=True)
    import pytest
    ret = pytest.main(["-q", str(ROOT / "nfl" / "sim" / "tests" / "test_freeze_v1.py")],
                      plugins=[])
    if ret != 0:
        sys.exit(f"HALT: test_freeze_v1 failed (exit {ret})")
    print("    PASS\n", flush=True)

    # (b) sheet: build via log_ai_opinions.py
    print("(b) Building sheet...", flush=True)
    with tempfile.TemporaryDirectory() as td:
        sheet_path = Path(td) / "sheet.csv"
        sheet_cmd = [sys.executable, str(ROOT / "nfl" / "pipeline" / "log_ai_opinions.py"),
                     "sheet", "--week", str(week), "--out", str(sheet_path)]
        r = subprocess.run(sheet_cmd, capture_output=True, text=True, cwd=str(ROOT))
        if r.returncode != 0:
            sys.exit(f"HALT: sheet failed:\n{r.stderr}\n{r.stdout}")
        sheet_df = pd.read_csv(sheet_path)
        print(f"    {len(sheet_df)} lines, two-way {int(sheet_df['two_way'].sum())}\n{r.stdout.strip()}\n",
              flush=True)

        # (c) sim: run run_week.py
        print("(c) Running sim...", flush=True)
        sim_cmd = [sys.executable, str(ROOT / "nfl" / "sim" / "run_week.py"),
                   "--week", str(week)]
        if as_of:
            sim_cmd += ["--as-of", as_of]
        r_sim = subprocess.run(sim_cmd, capture_output=True, text=True, cwd=str(ROOT),
                               timeout=7200)
        if r_sim.returncode != 0:
            sys.exit(f"HALT: run_week.py failed:\n{r_sim.stderr}\n{r_sim.stdout}")
        print(f"    Sim complete.\n", flush=True)

        # Read picks_log and anchoring_log
        sim_out = ROOT / "nfl" / "data" / "sim" / "outputs" / f"week={SEASON}_{week:02d}"
        picks_log = pd.read_parquet(sim_out / "picks_log.parquet")
        print(f"    picks_log: {len(picks_log)} legs, cal_p range "
              f"[{picks_log['cal_p'].min():.3f}, {picks_log['cal_p'].max():.3f}]", flush=True)

        # Read anchoring metadata from the run_week stdout
        # run_week.py prints: "margin X vs Y" — the printed margin is ANCHORED (run_week.py:997)
        # Read game_results from anchoring_log.parquet
        anch_log_path = sim_out / "anchoring_log.parquet"
        anchor_sidecar_rows = []
        if anch_log_path.exists():
            anch_log = pd.read_parquet(anch_log_path)
            # Get the best iteration per game (min total error)
            for gid in anch_log["game_id"].unique():
                g = anch_log[anch_log["game_id"] == gid]
                best = g.loc[(abs(g["err_m"]) + abs(g["err_t"])).idxmin()]
                spread = float(best.get("spread", 0))
                total_line = float(best.get("total_line", 0))
                anch_m = float(best.get("anch_m", best.get("margin", 0)))
                anch_t = float(best.get("anch_t", best.get("total", 0)))
                converged = bool(best.get("converged", False))
                n_iter = int(best.get("iteration", 0)) + 1
                miss_m = abs(anch_m - spread)
                miss_t = abs(anch_t - total_line)
                anchored = miss_m <= ANCHOR_MISS_TOL and miss_t <= ANCHOR_MISS_TOL
                anchor_sidecar_rows.append({
                    "game_id": gid, "spread": spread, "total_line": total_line,
                    "anch_m": anch_m, "anch_t": anch_t,
                    "miss_m": round(miss_m, 2), "miss_t": round(miss_t, 2),
                    "iterations": n_iter, "converged": converged,
                    "anchored": anchored,
                })

        # (d) fill: match picks_log to sheet
        print("(d) Filling opinions...", flush=True)
        filled = sheet_df.copy()
        filled["p_first"] = filled["q_first"].copy()
        filled["tag"] = "no_view"
        filled["reason"] = ""

        # Match two-way prop rows to picks_log
        # picks_log has: player_name, family (market_key mapping), line, cal_p (OVER side)
        # sheet has: player_name, market_key, line, two_way
        # The picks_log 'side' is always 'over'; cal_p is P(over)
        n_matched = 0
        for idx, row in filled.iterrows():
            if not row.get("two_way", False):
                continue
            # Game-line rows (h2h, spreads, totals) -> always no_view
            if row.get("market_key", "") in ("h2h", "spreads", "totals"):
                continue
            # Find matching picks_log row
            pl_match = picks_log[
                (picks_log["player_name"] == row["player_name"]) &
                (picks_log["line"] == row["line"])
            ]
            # Also match on family -> market_key mapping
            if len(pl_match) == 0:
                continue
            if len(pl_match) > 1:
                # Take first match
                pl_match = pl_match.iloc[:1]
            cal_p_over = float(pl_match.iloc[0]["cal_p"])
            tier = str(pl_match.iloc[0].get("tier", ""))
            # The sheet's "first" side: check if it's over or under
            # In the sheet, first side is the one with price_first
            # For player props, first side is typically over
            # cal_p_over is P(over). If sheet's first side is over, p_first = cal_p_over
            # If sheet's first side is under, p_first = 1 - cal_p_over
            # The sheet's market_key tells us: player_X_over -> first side is over
            mk = str(row.get("market_key", ""))
            if "_under" in mk.lower():
                p_first = 1.0 - cal_p_over
            else:
                p_first = cal_p_over
            p_first = np.clip(p_first, 0.02, 0.98)
            filled.at[idx, "p_first"] = round(p_first, 4)
            filled.at[idx, "tag"] = "sim_v1"
            filled.at[idx, "reason"] = f"sim v1 cal_p {tier}"[:160]
            n_matched += 1

        n_two_way = int(filled["two_way"].sum()) if "two_way" in filled else 0
        n_non_game = int(((filled.get("market_key", pd.Series(dtype=str)).isin(
            ["h2h", "spreads", "totals"])) == False).sum()) if "market_key" in filled.columns else 0
        print(f"    Matched {n_matched} / {n_two_way} two-way prop rows "
              f"({100*n_matched/max(n_two_way,1):.1f}%)\n", flush=True)

        # Write filled CSV for freeze
        filled_path = Path(td) / "filled.csv"
        filled.to_csv(filled_path, index=False)

        # (e) freeze
        print("(e) Freezing...", flush=True)
        freeze_cmd = [sys.executable, str(ROOT / "nfl" / "pipeline" / "log_ai_opinions.py"),
                      "freeze", "--week", str(week), "--filled", str(filled_path),
                      "--reader-model", READER_MODEL]
        if pilot:
            freeze_cmd.append("--pilot")
        if as_of:
            freeze_cmd += ["--as-of", as_of]
        r_freeze = subprocess.run(freeze_cmd, capture_output=True, text=True, cwd=str(ROOT))
        if r_freeze.returncode != 0:
            sys.exit(f"HALT: freeze failed:\n{r_freeze.stderr}\n{r_freeze.stdout}")
        print(f"    {r_freeze.stdout.strip()}\n", flush=True)

    # (f) anchor sidecar
    if anchor_sidecar_rows:
        sidecar_df = pd.DataFrame(anchor_sidecar_rows)
        opinions_dir = (ROOT / "nfl" / "data" / "board" /
                        f"week={SEASON}_{week:02d}" / "ai_opinions")
        sidecar_path = opinions_dir / "anchor_sidecar_sim_v1.parquet"
        sidecar_df.to_parquet(sidecar_path, index=False)
        n_unanch = int((~sidecar_df["anchored"]).sum())
        print(f"(f) Anchor sidecar: {len(sidecar_df)} games, "
              f"{n_unanch} unanchored -> {sidecar_path.relative_to(ROOT)}\n", flush=True)
        print(sidecar_df.to_string(index=False))

    print("\nDone.")


if __name__ == "__main__":
    main()
