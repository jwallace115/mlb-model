#!/usr/bin/env python3
"""PM-1c Item 4: full evidence run on real data.

Environment:
  VM: /root/mlb-model-pm1
  RESULTS_ARCHIVE_DIR=/root/pm1_scratch/results_archive
  POSTGAME_OUT_DIR=/root/pm1_scratch/postgame_pm1c
  PICKS_LEDGER_DIR=/root/private/ledger (read-only)

Outputs:
  ~/mlb-model-pm1/_pm1c_evidence/
"""
import hashlib
import json
import math
import os
import sys
from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(os.environ.get("MLB_REPO_ROOT") or
            Path(__file__).resolve().parent.parent.parent)
sys.path.insert(0, str(ROOT / "nfl" / "pipeline"))
sys.path.insert(0, str(ROOT / "shared" / "pipeline"))

RESULTS_DIR = Path(os.environ.get("RESULTS_ARCHIVE_DIR",
                                   "/root/pm1_scratch/results_archive"))
POSTGAME_DIR = Path(os.environ.get("POSTGAME_OUT_DIR",
                                    "/root/pm1_scratch/postgame_pm1c"))
LEDGER_DIR = Path(os.environ.get("PICKS_LEDGER_DIR", "/root/private/ledger"))
EVIDENCE_DIR = ROOT / "_pm1c_evidence"


def main():
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)

    # ── Load PBP slices ──
    pbp_dir = RESULTS_DIR / "nfl" / "pbp" / "season=2026"
    if not pbp_dir.exists():
        print(f"HALT: PBP directory not found: {pbp_dir}", file=sys.stderr)
        sys.exit(1)

    pbp_slices = {}
    for f in sorted(pbp_dir.glob("pbp_*.parquet")):
        df = pd.read_parquet(f)
        gid = str(df["game_id"].iloc[0])
        pbp_slices[gid] = df
    print(f"Loaded {len(pbp_slices)} game PBP slices")

    # ── Load snap counts ──
    snap_files = sorted((RESULTS_DIR / "nfl").glob("snap_counts_2026_*.parquet"))
    snap_counts = pd.read_parquet(snap_files[-1]) if snap_files else None
    if snap_counts is not None:
        print(f"Snap counts: {len(snap_counts)} rows, weeks {sorted(snap_counts.week.unique())}")
    else:
        print("Snap counts: NONE")

    # ── Load ledger ──
    import picks_ledger as pl
    view = pl.view(LEDGER_DIR)
    graded = [r for r in view if r.get("result") and r.get("sport") == "NFL"]
    print(f"Ledger: {len(graded)} graded NFL rows")

    # Record ledger sha before
    ledger_sha_before = hashlib.sha256(
        json.dumps(sorted([r.get("pick_id", "") for r in graded])).encode()
    ).hexdigest()[:16]

    # ── Build verdicts ──
    import build_postgame as bp
    verdicts = bp.build_verdicts(graded, pbp_slices, week_filter=None,
                                 season=2026, snap_counts=snap_counts)

    if verdicts is None or verdicts.empty:
        print("NO VERDICTS — HALT")
        sys.exit(1)

    df = verdicts
    print(f"\n{'='*60}")
    print(f"Total verdict rows: {len(df)}")

    # ── Write verdicts parquet ──
    for week in sorted(df["week"].unique()):
        wdir = POSTGAME_DIR / f"week=2026_{int(week):02d}"
        wdir.mkdir(parents=True, exist_ok=True)
        wv = df[df["week"] == week]
        wv.to_parquet(wdir / "verdicts.parquet", index=False)
        print(f"  week {int(week)}: {len(wv)} rows")

    # ── Save one game sheet ──
    first_gid = list(pbp_slices.keys())[0]
    sheet = bp.build_game_sheet(pbp_slices[first_gid], snap_counts)
    sheet_path = EVIDENCE_DIR / f"game_{first_gid}.json"
    sheet_path.write_text(json.dumps(sheet, indent=2, default=str) + "\n")
    print(f"\nWrote game sheet: {sheet_path.name}")

    # ══════════ JOIN RATES ══════════
    print(f"\n{'='*60}")
    print("JOIN RATES")
    total = len(df)
    has_game = int(df["game_id"].notna().sum())
    prop_rows = df[df["market"].str.startswith("prop:")]
    game_rows = df[df["market"].isin(["spread", "total", "moneyline"])]
    has_actual = int(prop_rows["actual_stat"].notna().sum()) if "actual_stat" in df.columns else 0
    has_tag = int(df["tag"].notna().sum())

    print(f"  game join: {has_game}/{total} = {has_game/total*100:.1f}%")
    print(f"  player join (props with actual_stat): {has_actual}/{len(prop_rows)} = {has_actual/len(prop_rows)*100:.1f}%" if len(prop_rows) else "  no props")
    print(f"  freeze join (has tag): {has_tag}/{total} = {has_tag/total*100:.1f}%")

    # Freeze join by source
    print("\n  FREEZE JOIN BY SOURCE:")
    if "pick_id" in df.columns:
        # Identify ai_opinions-sourced rows vs others
        ai_rows = df[df["owner"].isin(["ai_nfl"])]
        sim_rows = df[df["owner"].isin(["sim_nfl"])]
        other_rows = df[~df["owner"].isin(["ai_nfl", "sim_nfl"])]
        for label, subset in [("ai_nfl", ai_rows), ("sim_nfl", sim_rows), ("other", other_rows)]:
            if subset.empty:
                continue
            n = len(subset)
            has = int(subset["tag"].notna().sum())
            rate = has / n * 100 if n else 0
            print(f"    {label}: {has}/{n} = {rate:.1f}%")
            if rate < 99 and label == "ai_nfl":
                missing = subset[subset["tag"].isna()]
                if len(missing) > 0:
                    print(f"    MISSES ({len(missing)}):")
                    for _, r in missing.head(10).iterrows():
                        print(f"      {r['pick_id']}: {r['market']} {r.get('player_name', '')} week {r.get('week')}")

    # ══════════ W/L MISMATCHES ══════════
    print(f"\n{'='*60}")
    print("W/L MISMATCHES")
    if "wl_mismatch" in df.columns:
        mm = df[df["wl_mismatch"] == True]
        print(f"  Total mismatches: {len(mm)}")
        if len(mm) > 0:
            for _, r in mm.iterrows():
                print(f"  {r['pick_id']}: {r['market']} {r.get('player_name','')} "
                      f"L={r.get('point')} A={r.get('actual_stat')} "
                      f"ledger={r['ledger_result']} computed={r.get('computed_result')}")
    else:
        print("  (no wl_mismatch column)")

    # ══════════ CHAIN IDENTITY ══════════
    print(f"\n{'='*60}")
    print("CHAIN IDENTITY")
    if "chain" in df.columns and "actual_stat" in df.columns:
        chain_rows = df[df["chain"].notna() & df["actual_stat"].notna() & (df["point"].notna())]
        max_resid = 0
        for _, r in chain_rows.iterrows():
            try:
                decomp = json.loads(r["chain"])
                A = float(r["actual_stat"])
                L = float(r["point"])
                if A <= 0 or L <= 0:
                    continue
                bvp = decomp.get("book_vs_prior", 0)
                link_sum = sum(decomp["links"][k]["term"] for k in decomp["links"])
                lnAL = math.log(A / L)
                resid = abs(lnAL - (bvp + link_sum))
                max_resid = max(max_resid, resid)
            except (json.JSONDecodeError, ValueError, KeyError, TypeError):
                continue
        print(f"  max |ln(A/L) - (book_vs_prior + sum terms)|: {max_resid:.6f}")
        print(f"  chain rows: {len(chain_rows)}")

    # ══════════ WHY_CODE_AUTO ══════════
    print(f"\n{'='*60}")
    print("WHY_CODE_AUTO")
    if "why_code_auto" in df.columns:
        print("\n  LOSSES by market x why_code:")
        losses = df[df["ledger_result"] == "L"]
        if not losses.empty:
            for key, n in sorted(losses.groupby(["market", "why_code_auto"]).size().items()):
                print(f"    {key[0]:20s} {key[1]:20s}: {n}")
        print("\n  WINS by market x why_code:")
        wins = df[df["ledger_result"] == "W"]
        if not wins.empty:
            for key, n in sorted(wins.groupby(["market", "why_code_auto"]).size().items()):
                print(f"    {key[0]:20s} {key[1]:20s}: {n}")

        # By conf tier
        if "conf_rank" in df.columns:
            print("\n  WHY_CODE by conf tier (1-20 / 21-100 / 101+):")
            for tier_name, mask in [("1-20", df["conf_rank"] <= 20),
                                     ("21-100", (df["conf_rank"] > 20) & (df["conf_rank"] <= 100)),
                                     ("101+", df["conf_rank"] > 100)]:
                tier = df[mask]
                if tier.empty:
                    print(f"    {tier_name}: no rows")
                    continue
                losses_t = tier[tier["ledger_result"] == "L"]
                if not losses_t.empty:
                    for wc, n in losses_t["why_code_auto"].value_counts().items():
                        print(f"    {tier_name} L {str(wc):20s}: {n}")

    # ══════════ THESIS HELD/FAILED/FLAT ══════════
    print(f"\n{'='*60}")
    print("THESIS VERDICTS")
    if "thesis_held" in df.columns and "thesis_source" in df.columns:
        # Separate price vs game theses
        has_thesis = df[df["thesis"].notna() & (df["thesis"] != "")]
        price_thesis = has_thesis[has_thesis["thesis"].str.contains("price:", na=False)]
        game_thesis = has_thesis[~has_thesis["thesis"].str.contains("price:", na=False)]

        for label, subset in [("PRICE theses", price_thesis), ("GAME (non-price) theses", game_thesis)]:
            print(f"\n  {label}: {len(subset)} rows")
            if subset.empty:
                continue
            for key, n in sorted(subset.groupby(["thesis_held", "ledger_result"]).size().items()):
                print(f"    {str(key[0]):12s} {key[1]}: {n}")

            # Held rate
            graded_thesis = subset[subset["thesis_held"].isin(["held", "failed", "flat"])]
            if len(graded_thesis) > 0:
                held = (graded_thesis["thesis_held"] == "held").sum()
                rate = held / len(graded_thesis) * 100
                print(f"    HELD rate: {held}/{len(graded_thesis)} = {rate:.1f}%")
                if label.startswith("GAME") and len(graded_thesis) < 30:
                    print(f"    *** INSUFFICIENT N ({len(graded_thesis)} < 30)")

    # ══════════ ONE_PLAY_DECIDED + ROLE_SHIFT ══════════
    print(f"\n{'='*60}")
    print("FLAGS")
    if "one_play_decided" in df.columns:
        opd = df[df["one_play_decided"] == True]
        print(f"  one_play_decided: {len(opd)} rows")
        for _, r in opd.head(5).iterrows():
            print(f"    {r.get('pick_id')}: {r['market']} {r.get('player_name','')} "
                  f"A={r.get('actual_stat')} L={r.get('point')} {r['ledger_result']}")

    if "teammates_out" in df.columns:
        has_tm = df[df["teammates_out"].notna()]
        print(f"  teammates_out (non-null): {len(has_tm)} rows")

    if "why_code_auto" in df.columns:
        rs = df[df["why_code_auto"] == "ROLE_SHIFT"]
        print(f"  ROLE_SHIFT count: {len(rs)}")
        unresolved = df[df["why_code_auto"] == "UNRESOLVED"]
        print(f"  UNRESOLVED count: {len(unresolved)}")

    # ══════════ 5 LARGEST |ln(A/L)| LOSSES ══════════
    print(f"\n{'='*60}")
    print("5 LARGEST |ln(A/L)| LOSSES")
    if "actual_stat" in df.columns:
        losses = df[(df["ledger_result"] == "L") &
                    df["actual_stat"].notna() & (df["actual_stat"] > 0) &
                    df["point"].notna() & (df["point"].astype(float) > 0)].copy()
        if not losses.empty:
            losses["_abslog"] = losses.apply(
                lambda r: abs(math.log(float(r["actual_stat"]) / float(r["point"]))),
                axis=1)
            top5 = losses.nlargest(5, "_abslog")
            for _, r in top5.iterrows():
                print(f"  {r.get('pick_id')}: {r['market']} {r.get('player_name','')} "
                      f"A={r.get('actual_stat')} L={r.get('point')} |ln|={r['_abslog']:.3f} "
                      f"why={r.get('why_code_auto')} primary={r.get('primary_link')}")

    # ══════════ NULL CONTROLS ══════════
    print(f"\n{'='*60}")
    print("NULL CONTROLS")

    # Truncation equivalence: weeks <= 3
    early = df[df["week"] <= 3]
    late = df[df["week"] > 3]
    print(f"  Truncation: weeks<=3 = {len(early)} rows, weeks>3 = {len(late)} rows")

    # Ledger sha after (must match before)
    view_after = pl.view(LEDGER_DIR)
    graded_after = [r for r in view_after if r.get("result") and r.get("sport") == "NFL"]
    ledger_sha_after = hashlib.sha256(
        json.dumps(sorted([r.get("pick_id", "") for r in graded_after])).encode()
    ).hexdigest()[:16]
    print(f"  Ledger sha before: {ledger_sha_before}")
    print(f"  Ledger sha after:  {ledger_sha_after}")
    print(f"  Ledger unchanged:  {ledger_sha_before == ledger_sha_after}")

    # ══════════ SAVE EVIDENCE ══════════
    df.to_parquet(EVIDENCE_DIR / "verdicts_all.parquet", index=False)
    # link_sd
    import shutil
    link_sd_src = ROOT / "nfl" / "data" / "postgame" / "link_sd_2025.json"
    if link_sd_src.exists():
        shutil.copy2(link_sd_src, EVIDENCE_DIR / "link_sd_2025.json")

    print(f"\n{'='*60}")
    print(f"Evidence written to {EVIDENCE_DIR}")
    print(f"Files: {sorted(f.name for f in EVIDENCE_DIR.iterdir())}")


if __name__ == "__main__":
    main()
