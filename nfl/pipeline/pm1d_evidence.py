#!/usr/bin/env python3
"""PM-1d Item 4: evidence run + tag-shuffle null control.

Run on VM: /root/mlb-model/venv/bin/python3 nfl/pipeline/pm1d_evidence.py

Outputs to POSTGAME_OUT_DIR / _pm1d_evidence/:
  - verdicts_w*.parquet (every week)
  - game_*.json (one per game)
  - link_sd_2025_v2.json (copy)
  - shuffle_null.json (1,000 held rates)
  - evidence_report.txt (full text)
"""
import hashlib
import json
import math
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(os.environ.get("MLB_REPO_ROOT") or Path(__file__).resolve().parent.parent.parent)
sys.path.insert(0, str(ROOT / "nfl" / "pipeline"))
sys.path.insert(0, str(ROOT / "shared" / "pipeline"))

import build_postgame as bp
import picks_ledger as pl

RESULTS_DIR = Path(os.environ.get("RESULTS_ARCHIVE_DIR") or (ROOT / "data" / "results_archive"))
POSTGAME_DIR = Path(os.environ.get("POSTGAME_OUT_DIR") or (ROOT / "nfl" / "data" / "postgame"))
LEDGER_DIR = Path(os.environ.get("PICKS_LEDGER_DIR") or "/root/private/ledger")
EVIDENCE_DIR = POSTGAME_DIR / "_pm1d_evidence"


def load_all():
    """Load PBP slices, snap counts, ledger."""
    pbp_dir = RESULTS_DIR / "nfl" / "pbp" / "season=2026"
    if not pbp_dir.exists():
        print(f"HALT: PBP directory not found: {pbp_dir}", file=sys.stderr)
        sys.exit(1)

    pbp_slices = {}
    for f in sorted(pbp_dir.glob("pbp_*.parquet")):
        df = pd.read_parquet(f)
        gid = str(df["game_id"].iloc[0])
        pbp_slices[gid] = df

    snap_files = sorted((RESULTS_DIR / "nfl").glob("snap_counts_2026_*.parquet"))
    snap_counts = pd.read_parquet(snap_files[-1]) if snap_files else None

    view = pl.view(LEDGER_DIR) if LEDGER_DIR.exists() else []
    graded = [r for r in view if r.get("result") and r.get("sport") == "NFL"
              and r.get("owner") in ("ai_nfl", "sim_nfl")]

    return pbp_slices, snap_counts, graded


def build_all_verdicts(pbp_slices, snap_counts, graded):
    """Build verdicts for all weeks."""
    bp._link_sd_cache.clear()
    bp._clv_cache.clear()
    verdicts = bp.build_verdicts(graded, pbp_slices, week_filter=None,
                                  snap_counts=snap_counts, season=2026)
    return verdicts


_PRICE_TAGS = {"price_vs_sharp", "line_move"}


def tag_shuffle_null(verdicts, n_shuffles=1000, seed=20261011):
    """Within each market, shuffle tags and recompute thesis held rate.

    PM-1e fix: separate game (non-price) and price (CLV) thesis pools.
    The shuffle null runs ONLY on game theses — both real and shuffled
    rates are computed over the same pool. Price theses get a separate
    held-rate line (no shuffle, since price theses depend on CLV not tags).

    Returns dict with game_held_rate, shuffle stats, price_held_rate,
    tag counts, and power note when one tag dominates.
    """
    if verdicts is None or verdicts.empty:
        return {"error": "no verdicts"}

    # Only rows with a thesis that produced a verdict
    has_thesis = verdicts[
        verdicts["thesis_held"].isin(["held", "failed", "flat"])
    ].copy()

    if len(has_thesis) < 5:
        return {"error": f"only {len(has_thesis)} rows with thesis verdict"}

    # Split into game (non-price) and price pools
    is_price = has_thesis["tag"].isin(_PRICE_TAGS)
    game_pool = has_thesis[~is_price].copy()
    price_pool = has_thesis[is_price].copy()

    # Game-thesis held rate
    game_held_rate = float((game_pool["thesis_held"] == "held").mean()) if len(game_pool) else 0.0

    # Price-thesis held rate (no shuffle — depends on CLV, not tag assignment)
    price_held_rate = float((price_pool["thesis_held"] == "held").mean()) if len(price_pool) else None

    # Tag counts in the game pool
    tag_counts = game_pool["tag"].value_counts().to_dict() if len(game_pool) else {}

    # Power note: warn when one tag is >80% of the pool
    power_note = None
    if len(game_pool) > 0:
        for tag_name, count in tag_counts.items():
            frac = count / len(game_pool)
            if frac > 0.80:
                power_note = (
                    f"{tag_name} is {frac:.0%} of the game pool ({count}/{len(game_pool)}); "
                    f"shuffle has little power to distinguish tag-specific signal"
                )
                break

    # Shuffle null over game pool only
    tag_rows = game_pool[game_pool["thesis_source"] == "tag_map"].copy()
    if len(tag_rows) < 5:
        tag_rows = game_pool.copy()

    rng = np.random.RandomState(seed)
    shuffled_rates = []

    for i in range(n_shuffles):
        shuffled = tag_rows.copy()
        for market in shuffled["market"].unique():
            mask = shuffled["market"] == market
            idx = shuffled.index[mask]
            tags = shuffled.loc[idx, "tag"].values.copy()
            rng.shuffle(tags)
            shuffled.loc[idx, "tag"] = tags

        held_count = 0
        total_count = 0
        for _, row in shuffled.iterrows():
            tag = row.get("tag")
            market = row.get("market", "")
            side = row.get("side", "")
            thesis, _ = bp._thesis_from_tag(tag, market, side)
            if not thesis:
                continue

            chain_str = row.get("chain")
            decomp = None
            if chain_str and isinstance(chain_str, str):
                try:
                    decomp = json.loads(chain_str)
                except (json.JSONDecodeError, TypeError):
                    pass

            link_sd = bp._load_link_sd(ROOT)
            clv_row = None
            verdict, z = bp._check_thesis(thesis, decomp, link_sd, clv_row, market=market)
            if verdict == "held":
                held_count += 1
            if verdict in ("held", "failed", "flat"):
                total_count += 1

        rate = held_count / total_count if total_count > 0 else 0
        shuffled_rates.append(rate)

    arr = np.array(shuffled_rates)
    result = {
        "game_held_rate": round(float(game_held_rate), 4),
        "n_game": int(len(game_pool)),
        "price_held_rate": round(float(price_held_rate), 4) if price_held_rate is not None else None,
        "n_price": int(len(price_pool)),
        "tag_counts": tag_counts,
        "n_tag_rows": int(len(tag_rows)),
        "shuffle_mean": round(float(arr.mean()), 4),
        "shuffle_std": round(float(arr.std()), 4),
        "shuffle_p025": round(float(np.percentile(arr, 2.5)), 4),
        "shuffle_p975": round(float(np.percentile(arr, 97.5)), 4),
        "n_shuffles": n_shuffles,
        "seed": seed,
        "shuffled_rates": [round(float(x), 4) for x in arr.tolist()],
    }
    if power_note:
        result["power_note"] = power_note
    return result


def evidence_report(verdicts, shuffle_result, pbp_slices):
    """Generate the full evidence report text."""
    lines = []
    lines.append("=" * 60)
    lines.append("PM-1d EVIDENCE RUN")
    lines.append(f"Generated: {datetime.now(timezone.utc).isoformat()}")
    lines.append("=" * 60)

    if verdicts is None or verdicts.empty:
        lines.append("NO VERDICTS")
        return "\n".join(lines)

    # PM-1: game count, weeks
    weeks = sorted(verdicts["week"].unique())
    lines.append(f"\n## PM-1: {len(verdicts)} verdict rows, weeks {weeks}")
    lines.append(f"Games: {len(pbp_slices)}")

    # PM-2: counts by owner × market × result
    lines.append("\n## PM-2: Graded rows by owner × market × result")
    for (owner, market, result), count in verdicts.groupby(
            ["owner", "market", "ledger_result"]).size().items():
        lines.append(f"  {owner} / {market} / {result}: {count}")

    # PM-3: why_code_auto distribution
    if "why_code_auto" in verdicts.columns:
        lines.append("\n## PM-3: why_code_auto for LOSSES")
        losses = verdicts[verdicts["ledger_result"] == "L"]
        if len(losses):
            for code, count in losses["why_code_auto"].value_counts().items():
                lines.append(f"  {code}: {count}")
        lines.append("\n## PM-3: why_code_auto for WINS")
        wins = verdicts[verdicts["ledger_result"] == "W"]
        if len(wins):
            for code, count in wins["why_code_auto"].value_counts().items():
                lines.append(f"  {code}: {count}")

    # PM-4: join rates
    total = len(verdicts)
    has_chain = verdicts["chain"].notna().sum() if "chain" in verdicts.columns else 0
    has_actual = verdicts["actual_stat"].notna().sum() if "actual_stat" in verdicts.columns else 0
    unresolved = (verdicts.get("why_code_auto") == "UNRESOLVED").sum() if "why_code_auto" in verdicts.columns else 0
    lines.append(f"\n## PM-4: Join rates")
    lines.append(f"  Total verdicts: {total}")
    lines.append(f"  Has chain decomp: {has_chain} ({100*has_chain/total:.1f}%)")
    lines.append(f"  Has actual_stat: {has_actual} ({100*has_actual/total:.1f}%)")
    lines.append(f"  UNRESOLVED: {unresolved}")

    # PM-5: thesis held/failed/flat × W/L (game and price separately)
    if "thesis_held" in verdicts.columns:
        lines.append("\n## PM-5: Thesis verdicts × W/L")
        for src in sorted(verdicts["thesis_source"].dropna().unique()):
            src_rows = verdicts[verdicts["thesis_source"] == src]
            lines.append(f"\n  thesis_source={src} ({len(src_rows)} rows):")
            for tv in ("held", "failed", "flat", "no_data"):
                tv_rows = src_rows[src_rows["thesis_held"] == tv]
                if len(tv_rows) == 0:
                    continue
                n_w = (tv_rows["ledger_result"] == "W").sum()
                n_l = (tv_rows["ledger_result"] == "L").sum()
                n_p = (tv_rows["ledger_result"] == "P").sum()
                lines.append(f"    {tv}: {len(tv_rows)} (W={n_w} L={n_l} P={n_p})")

        # Game theses only (N >= 30 gate)
        game_thesis = verdicts[verdicts["thesis_source"].isin(["freeze", "tag_map"])]
        game_thesis = game_thesis[game_thesis["thesis_held"].isin(["held", "failed", "flat"])]
        n_game = len(game_thesis)
        if n_game >= 30:
            held_rate = (game_thesis["thesis_held"] == "held").mean()
            lines.append(f"\n  Game-thesis held rate: {held_rate:.1%} (N={n_game})")
        else:
            lines.append(f"\n  Game-thesis: INSUFFICIENT N ({n_game} < 30)")

    # PM-6: tag-shuffle null (PM-1e: separate game/price pools)
    lines.append("\n## PM-6: Tag-shuffle null control")
    if "error" in shuffle_result:
        lines.append(f"  ERROR: {shuffle_result['error']}")
    else:
        lines.append(f"  Game-thesis held rate: {shuffle_result['game_held_rate']} (N={shuffle_result['n_game']})")
        if shuffle_result.get("price_held_rate") is not None:
            lines.append(f"  Price-thesis held rate: {shuffle_result['price_held_rate']} (N={shuffle_result['n_price']}, CLV-based, no shuffle)")
        if shuffle_result.get("tag_counts"):
            lines.append(f"  Tag counts in game pool: {shuffle_result['tag_counts']}")
        if shuffle_result.get("power_note"):
            lines.append(f"  POWER NOTE: {shuffle_result['power_note']}")
        lines.append(f"  Shuffle mean: {shuffle_result['shuffle_mean']}")
        lines.append(f"  Shuffle 95% band: [{shuffle_result['shuffle_p025']}, {shuffle_result['shuffle_p975']}]")
        lines.append(f"  N shuffles: {shuffle_result['n_shuffles']}, seed: {shuffle_result['seed']}")
        if shuffle_result['game_held_rate'] > shuffle_result['shuffle_p975']:
            lines.append("  VERDICT: Game rate ABOVE 95% band — signal present")
        elif shuffle_result['game_held_rate'] < shuffle_result['shuffle_p025']:
            lines.append("  VERDICT: Game rate BELOW 95% band")
        else:
            lines.append("  VERDICT: Game rate WITHIN 95% band — no signal detected")

    # Chain identity max residual
    if "chain" in verdicts.columns:
        max_residual = 0
        for _, row in verdicts.iterrows():
            if not row.get("chain") or not isinstance(row["chain"], str):
                continue
            try:
                d = json.loads(row["chain"])
            except (json.JSONDecodeError, TypeError):
                continue
            if d.get("zero_actual") or "links" not in d:
                continue
            A = d.get("A", 0)
            L = d.get("L", 0)
            if A <= 0 or L <= 0:
                continue
            lhs = math.log(A / L)
            rhs = d.get("book_vs_prior", 0) + sum(
                d["links"][k]["term"] for k in d["links"]
            )
            residual = abs(lhs - rhs)
            max_residual = max(max_residual, residual)
        lines.append(f"\n## Chain identity max residual: {max_residual:.2e} (target <= 1e-9)")

    # ROLE_SHIFT, one_play_decided, UNRESOLVED counts
    if "why_code_auto" in verdicts.columns:
        rs = (verdicts["why_code_auto"] == "ROLE_SHIFT").sum()
        lines.append(f"\n## ROLE_SHIFT count: {rs}")
    if "one_play_decided" in verdicts.columns:
        opd = verdicts["one_play_decided"].sum()
        lines.append(f"## one_play_decided count: {opd}")
    lines.append(f"## UNRESOLVED count: {unresolved}")

    # Mismatches
    if "wl_mismatch" in verdicts.columns:
        mismatches = verdicts[verdicts["wl_mismatch"] == True]
        lines.append(f"\n## W/L mismatches: {len(mismatches)}")
        for _, r in mismatches.iterrows():
            lines.append(f"  {r.get('pick_id')}: {r.get('market')} {r.get('player_name', '')} "
                          f"ledger={r.get('ledger_result')} computed={r.get('computed_result')} "
                          f"A={r.get('actual_stat')} L={r.get('point')}")

    return "\n".join(lines)


def main():
    print("Loading data...")
    pbp_slices, snap_counts, graded = load_all()
    print(f"Loaded {len(pbp_slices)} PBP slices, {len(graded)} graded rows")

    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)

    print("Building verdicts...")
    verdicts = build_all_verdicts(pbp_slices, snap_counts, graded)

    if verdicts is not None and len(verdicts) > 0:
        # Write verdicts per week
        for week in verdicts["week"].unique():
            wv = verdicts[verdicts["week"] == week]
            out = EVIDENCE_DIR / f"verdicts_w{int(week):02d}.parquet"
            wv.to_parquet(out, index=False)
            print(f"  Week {int(week)}: {len(wv)} verdicts → {out.name}")

        # Write one game sheet per game
        for gid, g_pbp in pbp_slices.items():
            sheet = bp.build_game_sheet(g_pbp, snap_counts)
            out = EVIDENCE_DIR / f"game_{gid}.json"
            out.write_text(json.dumps(sheet, indent=2, default=str) + "\n")

        # Copy link_sd_2025_v2.json
        v2_path = ROOT / "nfl" / "data" / "postgame" / "link_sd_2025_v2.json"
        if v2_path.exists():
            import shutil
            shutil.copy2(v2_path, EVIDENCE_DIR / "link_sd_2025_v2.json")

        # Tag-shuffle null
        print("Running tag-shuffle null (1000 shuffles, seed=20261011)...")
        shuffle_result = tag_shuffle_null(verdicts, n_shuffles=1000, seed=20261011)
        (EVIDENCE_DIR / "shuffle_null.json").write_text(
            json.dumps(shuffle_result, indent=2) + "\n")
        print(f"  Real held rate: {shuffle_result.get('real_held_rate')}")
        print(f"  Shuffle 95% band: [{shuffle_result.get('shuffle_p025')}, "
              f"{shuffle_result.get('shuffle_p975')}]")

        # Full report
        report = evidence_report(verdicts, shuffle_result, pbp_slices)
        (EVIDENCE_DIR / "evidence_report.txt").write_text(report + "\n")
        print(report)
    else:
        print("No verdicts produced")

    # Print listing
    print(f"\n{'='*40}")
    print(f"Evidence directory: {EVIDENCE_DIR}")
    for f in sorted(EVIDENCE_DIR.iterdir()):
        print(f"  {f.name} ({f.stat().st_size:,} bytes)")


if __name__ == "__main__":
    main()
