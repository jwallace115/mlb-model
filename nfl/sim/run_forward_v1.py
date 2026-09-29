#!/usr/bin/env python3
"""
FWD1 (D211/D215): forward-test harness for the frozen NFL sim v1.

Usage:
  python3 nfl/sim/run_forward_v1.py --week 3 [--pilot] [--as-of ...] [--window-hours 9] [--events pit,cle]
"""

import argparse, json, subprocess, sys, tempfile
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

READER_MODEL = "nfl_sim_v1_156cd057"
SEASON = 2026
ANCHOR_MISS_TOL = 1.0
GAME_MARKETS = ("h2h", "spreads", "totals")
# D215(a): explicit family -> sheet market_key map; unlisted families are not matched
FAMILY_TO_MARKET = {
    "receptions": "player_receptions",
    "rush_attempts": "player_rush_attempts",
}


# ── public helpers (tested directly) ──────────────────────────────────────────

def fill_sheet(sheet_df, picks_log):
    """D215(a): match picks_log to sheet and set p_first / tag / reason.

    Match key: (player_name, market_key derived from family, line).
    picks_log.side: 'over' -> p_first = cal_p; 'under' -> p_first = 1 - cal_p
    (the sheet's first side is always Over for player props).
    More than one match for a key -> raises SystemExit (do not take the first).
    """
    filled = sheet_df.copy()
    filled["p_first"] = filled["q_first"].copy()
    filled["tag"] = "no_view"
    filled["reason"] = ""

    # Build a lookup from picks_log keyed by (player_name, market_key, line)
    pl_lookup = {}
    for _, r in picks_log.iterrows():
        mk = FAMILY_TO_MARKET.get(r["family"])
        if mk is None:
            continue
        key = (r["player_name"], mk, float(r["line"]))
        if key in pl_lookup:
            raise SystemExit(f"HALT: duplicate picks_log key {key}")
        pl_lookup[key] = r

    n_matched = 0
    for idx, row in filled.iterrows():
        if not row.get("two_way", False):
            continue
        mk = str(row.get("market_key", ""))
        if mk in GAME_MARKETS:
            continue
        key = (row["player_name"], mk, float(row["line"]))
        pl_row = pl_lookup.get(key)
        if pl_row is None:
            continue
        cal_p_over = float(pl_row["cal_p"])
        side = str(pl_row.get("side", "over"))
        if side == "under":
            p_first = 1.0 - cal_p_over
        else:
            p_first = cal_p_over
        p_first = float(np.clip(p_first, 0.02, 0.98))
        tier = str(pl_row.get("tier", ""))
        filled.at[idx, "p_first"] = round(p_first, 4)
        filled.at[idx, "tag"] = "sim_v1"
        filled.at[idx, "reason"] = f"sim v1 cal_p {tier}"[:160]
        n_matched += 1

    return filled, n_matched


def anchor_sidecar(anchoring_log_df, lines):
    """D215(b): per-game anchor sidecar from the anchoring log.

    Best iteration = min |err_m| + |err_t| (same rule as run_week).
    Market spread/total come from the run's lines dict, not from defaults.
    Raises KeyError if required columns are missing.
    """
    required = {"game", "iter", "margin", "total", "err_m", "err_t", "converged"}
    missing = required - set(anchoring_log_df.columns)
    if missing:
        raise KeyError(f"anchoring_log missing columns: {missing}")

    rows = []
    for gname in anchoring_log_df["game"].unique():
        g = anchoring_log_df[anchoring_log_df["game"] == gname]
        best = g.loc[(abs(g["err_m"]) + abs(g["err_t"])).idxmin()]
        anch_m = float(best["margin"])
        anch_t = float(best["total"])
        # Market values from lines dict (away@home -> spread, total)
        ln = lines.get(gname, {})
        spread = float(ln.get("spread", anch_m - float(best["err_m"])))
        total_line = float(ln.get("total_line", anch_t - float(best["err_t"])))
        miss_m = abs(anch_m - spread)
        miss_t = abs(anch_t - total_line)
        rows.append({
            "game": gname,
            "spread": spread, "total_line": total_line,
            "anch_m": round(anch_m, 2), "anch_t": round(anch_t, 2),
            "miss_m": round(miss_m, 2), "miss_t": round(miss_t, 2),
            "iterations": int(best["iter"]) + 1,
            "converged": bool(best["converged"]),
            "anchored": miss_m <= ANCHOR_MISS_TOL and miss_t <= ANCHOR_MISS_TOL,
        })
    return pd.DataFrame(rows)


# ── main ──────────────────────────────────────────────────────────────────────

def main(freeze_json_path=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--week", type=int, required=True)
    ap.add_argument("--pilot", action="store_true")
    ap.add_argument("--as-of", help="UTC ISO timestamp (pilot only)")
    ap.add_argument("--window-hours", type=float, help="limit to games kicking within N hours")
    ap.add_argument("--events", help="comma-separated team fragments")
    a = ap.parse_args()

    if a.as_of and not a.pilot:
        sys.exit("HALT: --as-of requires --pilot")

    # (a) test_freeze_v1 in-process
    print("(a) Running test_freeze_v1...", flush=True)
    import pytest
    test_args = ["-q", str(ROOT / "nfl" / "sim" / "tests" / "test_freeze_v1.py")]
    if freeze_json_path:
        # Allow overriding FREEZE_PATH for testing
        import nfl.sim.tests.test_freeze_v1 as ft
        ft.FREEZE_PATH = Path(freeze_json_path)
    ret = pytest.main(test_args, plugins=[])
    if ret != 0:
        sys.exit(f"HALT: test_freeze_v1 failed (exit {ret})")
    print("    PASS\n", flush=True)

    # D215(c): common flags for sheet and freeze
    common_flags = []
    if a.pilot:
        common_flags.append("--pilot")
    if a.as_of:
        common_flags += ["--as-of", a.as_of]
    if a.window_hours:
        common_flags += ["--window-hours", str(a.window_hours)]
    if a.events:
        common_flags += ["--events", a.events]

    # (b) sheet
    print("(b) Building sheet...", flush=True)
    with tempfile.TemporaryDirectory() as td:
        sheet_path = Path(td) / "sheet.csv"
        sheet_cmd = [sys.executable, str(ROOT / "nfl" / "pipeline" / "log_ai_opinions.py"),
                     "sheet", "--week", str(a.week), "--out", str(sheet_path)] + common_flags
        r = subprocess.run(sheet_cmd, capture_output=True, text=True, cwd=str(ROOT))
        if r.returncode != 0:
            sys.exit(f"HALT: sheet failed:\n{r.stderr}\n{r.stdout}")
        sheet_df = pd.read_csv(sheet_path)
        print(f"    {len(sheet_df)} lines\n{r.stdout.strip()}\n", flush=True)

        # (c) sim
        print("(c) Running sim...", flush=True)
        sim_cmd = [sys.executable, str(ROOT / "nfl" / "sim" / "run_week.py"),
                   "--week", str(a.week)]
        if a.as_of:
            sim_cmd += ["--as-of", a.as_of]
        r_sim = subprocess.run(sim_cmd, capture_output=True, text=True, cwd=str(ROOT),
                               timeout=7200)
        if r_sim.returncode != 0:
            sys.exit(f"HALT: run_week.py failed:\n{r_sim.stderr}\n{r_sim.stdout}")
        print(f"    Sim complete.\n{r_sim.stdout[-500:]}\n", flush=True)

        # Read picks_log
        sim_out = ROOT / "nfl" / "data" / "sim" / "outputs" / f"week={SEASON}_{a.week:02d}"
        picks_log = pd.read_parquet(sim_out / "picks_log.parquet")
        print(f"    picks_log: {len(picks_log)} legs", flush=True)

        # (d) fill
        print("(d) Filling opinions...", flush=True)
        filled, n_matched = fill_sheet(sheet_df, picks_log)
        n_two_way = int(filled["two_way"].sum()) if "two_way" in filled else 0
        print(f"    Matched {n_matched} / {n_two_way} two-way prop rows\n", flush=True)

        # Write filled CSV for freeze
        filled_path = Path(td) / "filled.csv"
        filled.to_csv(filled_path, index=False)

        # (e) freeze
        print("(e) Freezing...", flush=True)
        freeze_cmd = [sys.executable, str(ROOT / "nfl" / "pipeline" / "log_ai_opinions.py"),
                      "freeze", "--week", str(a.week), "--filled", str(filled_path),
                      "--reader-model", READER_MODEL] + common_flags
        r_freeze = subprocess.run(freeze_cmd, capture_output=True, text=True, cwd=str(ROOT))
        if r_freeze.returncode != 0:
            sys.exit(f"HALT: freeze failed:\n{r_freeze.stderr}\n{r_freeze.stdout}")
        print(f"    {r_freeze.stdout.strip()}\n", flush=True)

    # (f) anchor sidecar
    anch_log_path = sim_out / "anchoring_log.parquet"
    if anch_log_path.exists():
        anch_log = pd.read_parquet(anch_log_path)
        sidecar_df = anchor_sidecar(anch_log, {})
        opinions_dir = (ROOT / "nfl" / "data" / "board" /
                        f"week={SEASON}_{a.week:02d}" / "ai_opinions")
        sidecar_path = opinions_dir / "anchor_sidecar_sim_v1.parquet"
        sidecar_df.to_parquet(sidecar_path, index=False)
        n_unanch = int((~sidecar_df["anchored"]).sum())
        print(f"(f) Anchor sidecar: {len(sidecar_df)} games, "
              f"{n_unanch} unanchored -> {sidecar_path.relative_to(ROOT)}", flush=True)
        print(sidecar_df.to_string(index=False))

    print("\nDone.")


if __name__ == "__main__":
    main()
