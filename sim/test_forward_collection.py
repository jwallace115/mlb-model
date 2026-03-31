"""
Phase 7 — Forward Collection End-to-End Test
=============================================
Simulates a complete real-line lifecycle for one game_id:

  Step 1  Open snapshot (7am)    → Layer 2 open_total populated
  Step 2  Noon snapshot (noon)   → Layer 2 noon_total populated
  Step 3  5pm snapshot (5pm)     → Layer 2 five_pm_total populated
  Step 4  Closing snapshot       → Layer 2 close_total populated, CLV computable
  Step 5  rebuild_games_from_real_lines() → Layers 3+4 re-derived with real figures
  Step 6  Show all four layers for this game_id side-by-side

Uses a scratch copy of the parquet files so the production data is not modified.
"""

import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

SIM_DIR  = Path(__file__).resolve().parent
DATA_DIR = SIM_DIR / "data"
TEST_DIR = SIM_DIR / "data" / "_test_scratch"

# ---------------------------------------------------------------------------
# Redirect layer paths to scratch copies before importing phase7_market
# ---------------------------------------------------------------------------
sys.path.insert(0, str(SIM_DIR.parent))

import sim.phase7_market as p7

PROD_FILES = {
    "L1": p7.L1_PATH,
    "L2": p7.L2_PATH,
    "L3": p7.L3_PATH,
    "L4": p7.L4_PATH,
}


def _setup_scratch() -> None:
    TEST_DIR.mkdir(exist_ok=True)
    for key, src in PROD_FILES.items():
        dst = TEST_DIR / src.name
        shutil.copy2(src, dst)

    # Redirect module-level path constants to scratch copies
    p7.L1_PATH = TEST_DIR / p7.L1_PATH.name
    p7.L2_PATH = TEST_DIR / p7.L2_PATH.name
    p7.L3_PATH = TEST_DIR / p7.L3_PATH.name
    p7.L4_PATH = TEST_DIR / p7.L4_PATH.name


def _restore_paths() -> None:
    p7.L1_PATH = PROD_FILES["L1"]
    p7.L2_PATH = PROD_FILES["L2"]
    p7.L3_PATH = PROD_FILES["L3"]
    p7.L4_PATH = PROD_FILES["L4"]
    shutil.rmtree(TEST_DIR, ignore_errors=True)


def _sep(title: str = "") -> None:
    line = f"─" * 76
    if title:
        print(f"\n{line}")
        print(f"  {title}")
        print(line)
    else:
        print(line)


def _show_row(label: str, row: pd.Series) -> None:
    print(f"\n  [{label}]")
    for col, val in row.items():
        print(f"    {col:<36} {val!r}")


def main() -> None:
    print("\n" + "=" * 76)
    print("  PHASE 7 — FORWARD COLLECTION END-TO-END TEST")
    print("=" * 76)
    print("  Using scratch copy of parquet files — production data NOT modified.")

    # -----------------------------------------------------------------------
    # Pick a test game
    # -----------------------------------------------------------------------
    df_l1   = pd.read_parquet(PROD_FILES["L1"])
    # Use a game with strong model lean (abs_edge >= 1.5) for interesting output
    df_dec  = pd.read_parquet(PROD_FILES["L3"])
    strong  = df_dec[df_dec["abs_edge"] >= 1.5].sort_values("abs_edge", ascending=False)
    test_gid = int(strong.iloc[0]["game_id"])
    test_row_l1 = df_l1[df_l1["game_id"] == test_gid].iloc[0]

    print(f"\n  Test game_id : {test_gid}")
    print(f"  {test_row_l1['away_team']} @ {test_row_l1['home_team']}  ({test_row_l1['date']})")
    print(f"  ridge_pred   : {test_row_l1['ridge_pred']:.4f}")
    print(f"  actual_total : {test_row_l1['actual_total']}")

    # Simulate: opening line is slightly different from proxy (realistic)
    open_line  = 8.5
    noon_line  = 8.5
    five_line  = 9.0   # line moves up (public money on over)
    close_line = 9.0   # closes at 9.0
    decision_line = open_line  # model uses opening line as decision line

    print(f"\n  Simulated market lines:")
    print(f"    Open line (7am)   : {open_line}")
    print(f"    Noon line         : {noon_line}")
    print(f"    5pm line          : {five_line}")
    print(f"    Close line        : {close_line}")
    print(f"    Decision line     : {decision_line} (open = decision for this test)")

    # -----------------------------------------------------------------------
    # Step 0: Set up scratch files
    # -----------------------------------------------------------------------
    print(f"\n{'─'*76}")
    print("  Step 0 — Copying production files to scratch directory")
    _setup_scratch()
    print(f"  Scratch dir: {TEST_DIR}")

    # Verify proxy state before
    l2_before = pd.read_parquet(p7.L2_PATH)
    proxy_row  = l2_before[l2_before["game_id"] == test_gid].iloc[0]
    print(f"\n  Layer 2 BEFORE (proxy state):")
    print(f"    decision_line_source : {proxy_row['decision_line_source']!r}")
    print(f"    decision_line        : {proxy_row['decision_line']}")
    print(f"    open_total           : {proxy_row['open_total']!r}")
    print(f"    close_total          : {proxy_row['close_total']!r}")
    print(f"    clv                  : {proxy_row['clv']!r}")

    # -----------------------------------------------------------------------
    # Step 1: Open snapshot (7am)
    # -----------------------------------------------------------------------
    _sep("Step 1 — Open snapshot (7am)")
    ts_open = datetime(2026, 4, 2, 12, 0, 0, tzinfo=timezone.utc)  # 7am ET = 12pm UTC
    p7.append_real_snapshot(
        game_id       = test_gid,
        date          = str(test_row_l1["date"]),
        book          = "draftkings",
        snapshot_time = ts_open,
        total         = open_line,
        over_price    = -110.0,
        under_price   = -110.0,
        snapshot_slot = "open",
        decision_line = decision_line,
    )
    l2 = pd.read_parquet(p7.L2_PATH)
    # There are now 2 rows for this game: the old proxy row + the new real row
    real_rows = l2[(l2["game_id"] == test_gid) & (l2["decision_line_source"] == "real")]
    r = real_rows.iloc[0]
    print(f"  open_total           : {r['open_total']}  ✓" if not pd.isna(r['open_total']) else "  open_total: MISSING ✗")
    print(f"  decision_line_source : {r['decision_line_source']!r}  (should be 'real')")
    print(f"  decision_line        : {r['decision_line']}  (should be {decision_line})")
    print(f"  close_total          : {r['close_total']!r}  (should be NaN)")
    print(f"  clv                  : {r['clv']!r}  (should be NaN — close not yet captured)")
    assert r["decision_line_source"] == "real", "FAIL: decision_line_source not 'real'"
    assert r["decision_line"] == decision_line, "FAIL: decision_line mismatch"
    assert pd.isna(r["close_total"]), "FAIL: close_total should be NaN at open"
    assert pd.isna(r["clv"]), "FAIL: clv should be NaN — no close yet"
    print("  PASS ✓")

    # -----------------------------------------------------------------------
    # Step 2: Noon snapshot
    # -----------------------------------------------------------------------
    _sep("Step 2 — Noon snapshot")
    ts_noon = datetime(2026, 4, 2, 17, 0, 0, tzinfo=timezone.utc)
    p7.append_real_snapshot(
        game_id       = test_gid,
        date          = str(test_row_l1["date"]),
        book          = "draftkings",
        snapshot_time = ts_noon,
        total         = noon_line,
        over_price    = -110.0,
        under_price   = -110.0,
        snapshot_slot = "noon",
        decision_line = decision_line,
    )
    l2 = pd.read_parquet(p7.L2_PATH)
    real_rows = l2[(l2["game_id"] == test_gid) & (l2["decision_line_source"] == "real")]
    r = real_rows.iloc[0]
    print(f"  noon_total           : {r['noon_total']}  (should be {noon_line})")
    assert r["noon_total"] == noon_line, "FAIL: noon_total mismatch"
    print("  PASS ✓")

    # -----------------------------------------------------------------------
    # Step 3: 5pm snapshot
    # -----------------------------------------------------------------------
    _sep("Step 3 — 5pm snapshot (line moved to 9.0)")
    ts_5pm = datetime(2026, 4, 2, 22, 0, 0, tzinfo=timezone.utc)
    p7.append_real_snapshot(
        game_id       = test_gid,
        date          = str(test_row_l1["date"]),
        book          = "draftkings",
        snapshot_time = ts_5pm,
        total         = five_line,
        over_price    = -115.0,
        under_price   = -105.0,
        snapshot_slot = "five_pm",
        decision_line = decision_line,   # decision line stays as open line
    )
    l2 = pd.read_parquet(p7.L2_PATH)
    real_rows = l2[(l2["game_id"] == test_gid) & (l2["decision_line_source"] == "real")]
    r = real_rows.iloc[0]
    print(f"  five_pm_total        : {r['five_pm_total']}  (should be {five_line})")
    print(f"  over_price           : {r['over_price']}  (line moved: -115)")
    assert r["five_pm_total"] == five_line, "FAIL: five_pm_total mismatch"
    print("  PASS ✓")

    # -----------------------------------------------------------------------
    # Step 4: Closing snapshot — CLV should auto-populate
    # -----------------------------------------------------------------------
    _sep("Step 4 — Closing snapshot (CLV should auto-populate)")
    ts_close = datetime(2026, 4, 3, 0, 30, 0, tzinfo=timezone.utc)   # ~8:30pm ET
    p7.append_real_snapshot(
        game_id       = test_gid,
        date          = str(test_row_l1["date"]),
        book          = "draftkings",
        snapshot_time = ts_close,
        total         = close_line,
        over_price    = -115.0,
        under_price   = -105.0,
        snapshot_slot = "close",
        decision_line = decision_line,
    )
    l2 = pd.read_parquet(p7.L2_PATH)
    real_rows = l2[(l2["game_id"] == test_gid) & (l2["decision_line_source"] == "real")]
    r = real_rows.iloc[0]

    expected_raw_clv = close_line - decision_line   # +0.5 (line moved up from 8.5 to 9.0)
    print(f"  close_total          : {r['close_total']}  (should be {close_line})")
    print(f"  clv (raw, Layer 2)   : {r['clv']}  (should be {expected_raw_clv:.2f})")
    print(f"  open_total           : {r['open_total']}")
    print(f"  noon_total           : {r['noon_total']}")
    print(f"  five_pm_total        : {r['five_pm_total']}")
    assert r["close_total"] == close_line, "FAIL: close_total mismatch"
    assert abs(r["clv"] - expected_raw_clv) < 1e-6, f"FAIL: Layer 2 raw CLV should be {expected_raw_clv}"
    print("  PASS ✓")

    # -----------------------------------------------------------------------
    # Step 5: Rebuild Layers 3 & 4
    # -----------------------------------------------------------------------
    _sep("Step 5 — Rebuild Layers 3 & 4 from real lines")
    p7.rebuild_games_from_real_lines([test_gid])

    df_dec_new = pd.read_parquet(p7.L3_PATH)
    df_res_new = pd.read_parquet(p7.L4_PATH)

    dec_real = df_dec_new[
        (df_dec_new["game_id"] == test_gid) &
        (df_dec_new["decision_line_source"] == "real")
    ]
    res_real = df_res_new[
        (df_res_new["game_id"] == test_gid) &
        (df_res_new["decision_line_source"] == "real")
    ]

    assert not dec_real.empty, "FAIL: Layer 3 has no real row for this game_id"
    assert not res_real.empty, "FAIL: Layer 4 has no real row for this game_id"

    d = dec_real.iloc[0]
    r4 = res_real.iloc[0]

    # Verify Layer 3
    print(f"\n  Layer 3 real row:")
    print(f"    decision_line        : {d['decision_line']}  (should be {decision_line})")
    print(f"    decision_line_source : {d['decision_line_source']!r}  (should be 'real')")
    print(f"    decision_time        : {d['decision_time']}")
    print(f"    edge_vs_decision_line: {d['edge_vs_decision_line']:.4f}  "
          f"(ridge {test_row_l1['ridge_pred']:.4f} - dl {decision_line} = "
          f"{test_row_l1['ridge_pred'] - decision_line:.4f})")
    print(f"    bet_side             : {d['bet_side']!r}")
    print(f"    bet_prob             : {d['bet_prob']:.4f}")
    print(f"    confidence_tier      : {d['confidence_tier']!r}")
    assert d["decision_line_source"] == "real", "FAIL"
    assert d["decision_line"] == decision_line, "FAIL"

    # Verify Layer 4 — CLV direction is bet-side-signed
    actual      = float(test_row_l1["actual_total"])
    bet_side    = d["bet_side"]
    if bet_side == "over":
        expected_clv = close_line - decision_line
    else:
        expected_clv = decision_line - close_line

    print(f"\n  Layer 4 real row:")
    print(f"    actual_total         : {r4['actual_total']}")
    print(f"    close_total          : {r4['close_total']}  (should be {close_line})")
    print(f"    result_win_loss      : {r4['result_win_loss']!r}")
    print(f"    roi_unit_result      : {r4['roi_unit_result']:.4f}")
    print(f"    clv                  : {r4['clv']:.4f}  (should be {expected_clv:.4f})")
    print(f"    decision_line_source : {r4['decision_line_source']!r}")
    assert r4["decision_line_source"] == "real", "FAIL"
    assert r4["close_total"] == close_line, "FAIL"
    assert abs(r4["clv"] - expected_clv) < 1e-6, f"FAIL: CLV mismatch (got {r4['clv']}, expected {expected_clv})"
    print("  PASS ✓")

    # -----------------------------------------------------------------------
    # Step 6: Show fully populated row across all four layers
    # -----------------------------------------------------------------------
    _sep("Step 6 — Sample of fully populated real-line row across all four layers")

    df_l1_scratch = pd.read_parquet(p7.L1_PATH)
    df_l2_scratch = pd.read_parquet(p7.L2_PATH)
    df_l3_scratch = pd.read_parquet(p7.L3_PATH)
    df_l4_scratch = pd.read_parquet(p7.L4_PATH)

    l1_row = df_l1_scratch[df_l1_scratch["game_id"] == test_gid].iloc[0]
    l2_row = df_l2_scratch[
        (df_l2_scratch["game_id"] == test_gid) &
        (df_l2_scratch["decision_line_source"] == "real")
    ].iloc[0]
    l3_row = df_l3_scratch[
        (df_l3_scratch["game_id"] == test_gid) &
        (df_l3_scratch["decision_line_source"] == "real")
    ].iloc[0]
    l4_row = df_l4_scratch[
        (df_l4_scratch["game_id"] == test_gid) &
        (df_l4_scratch["decision_line_source"] == "real")
    ].iloc[0]

    _show_row("Layer 1 — model_outputs  [pure model, unchanged]", l1_row)
    _show_row("Layer 2 — market_snapshots  [real line, all slots populated]", l2_row)
    _show_row("Layer 3 — bet_decisions  [real decision_line, recomputed]", l3_row)
    _show_row("Layer 4 — bet_results  [real CLV, real ROI]", l4_row)

    # -----------------------------------------------------------------------
    # Verify proxy rows are untouched
    # -----------------------------------------------------------------------
    _sep("Verify proxy rows are untouched")
    proxy_still = df_l4_scratch[
        (df_l4_scratch["game_id"] == test_gid) &
        (df_l4_scratch["decision_line_source"] == "proxy")
    ]
    # Proxy row still exists (we added a separate real row, not replaced)
    print(f"  Proxy row still present in Layer 4: {'YES' if len(proxy_still) > 0 else 'NO'}")
    print(f"  Total rows for this game_id in Layer 4: "
          f"{len(df_l4_scratch[df_l4_scratch['game_id'] == test_gid])}")
    print(f"  Real row CLV  : {l4_row['clv']:.4f}")
    print(f"  Proxy row CLV : {proxy_still.iloc[0]['clv'] if len(proxy_still) else 'N/A'!r}")

    # -----------------------------------------------------------------------
    # Summary
    # -----------------------------------------------------------------------
    print("\n" + "=" * 76)
    print("  ALL ASSERTIONS PASSED ✓")
    print("=" * 76)
    print(f"  game_id          : {test_gid}")
    print(f"  Ridge pred       : {test_row_l1['ridge_pred']:.4f}")
    print(f"  Open line        : {open_line}  (decision line)")
    print(f"  Close line       : {close_line}")
    print(f"  Bet side         : {l3_row['bet_side']}")
    print(f"  Abs edge vs open : {l3_row['abs_edge']:.4f}")
    print(f"  Confidence tier  : {l3_row['confidence_tier']}")
    print(f"  Actual total     : {l4_row['actual_total']}")
    print(f"  Result           : {l4_row['result_win_loss']}")
    print(f"  CLV (signed)     : {l4_row['clv']:+.4f}  "
          f"({'favorable' if l4_row['clv'] > 0 else 'unfavorable'} line move)")
    print(f"  ROI unit         : {l4_row['roi_unit_result']:+.4f}")
    print()
    print("  Forward collection path is production-ready for Opening Day 2026.")
    print("  Production data unchanged. Scratch files will be cleaned up.")
    print()

    _restore_paths()
    print("  Scratch files removed.")


if __name__ == "__main__":
    main()
