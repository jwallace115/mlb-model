#!/usr/bin/env python3
"""
NRFI Phase 1 — Build canonical NRFI research table
Fetches first-inning scores from MLB Stats API for all games in game_table,
joins closing totals and F5 lines, and runs full analysis (Phases 0-8).
"""
import json
import os
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
import requests

PROJECT_ROOT = Path("/root/mlb-model")
OUT_DIR = PROJECT_ROOT / "research" / "recovery" / "nrfi_phase1"
os.makedirs(OUT_DIR, exist_ok=True)

MLB_API = "https://statsapi.mlb.com/api/v1"
CACHE_FILE = OUT_DIR / "first_inning_cache.json"

# ── PHASE 0: Fetch first-inning data ────────────────────────────────────────

def fetch_first_inning_scores(game_pks: list[int]) -> dict:
    """Fetch first-inning runs from MLB API for each game_pk. Returns dict of results."""
    # Load cache
    cache = {}
    if CACHE_FILE.exists():
        cache = json.load(open(CACHE_FILE))
        cache = {int(k): v for k, v in cache.items()}

    needed = [gp for gp in game_pks if gp not in cache]
    print(f"  Cache: {len(cache)} entries, need {len(needed)} more")

    for i, gp in enumerate(needed):
        if i > 0 and i % 100 == 0:
            print(f"    Fetched {i}/{len(needed)}...")
            # Save checkpoint
            with open(CACHE_FILE, "w") as f:
                json.dump({str(k): v for k, v in cache.items()}, f)

        try:
            r = requests.get(f"{MLB_API}/game/{gp}/linescore", timeout=10)
            if r.status_code != 200:
                cache[gp] = {"status": "error", "code": r.status_code}
                time.sleep(0.3)
                continue

            data = r.json()
            innings = data.get("innings", [])
            if not innings:
                cache[gp] = {"status": "no_innings"}
                time.sleep(0.3)
                continue

            inn1 = innings[0]
            away_r = inn1.get("away", {}).get("runs")
            home_r = inn1.get("home", {}).get("runs")

            if away_r is None or home_r is None:
                cache[gp] = {"status": "incomplete"}
            else:
                cache[gp] = {
                    "status": "ok",
                    "away_1st": int(away_r),
                    "home_1st": int(home_r),
                }
        except Exception as e:
            cache[gp] = {"status": "error", "msg": str(e)[:80]}

        time.sleep(0.3)  # Rate limit

    # Final save
    with open(CACHE_FILE, "w") as f:
        json.dump({str(k): v for k, v in cache.items()}, f)

    return cache


def build_canonical_table():
    print("=" * 70)
    print("NRFI PHASE 1 RESEARCH — Building Canonical Table")
    print("=" * 70)

    # Load game_table
    gt = pd.read_parquet(PROJECT_ROOT / "sim" / "data" / "game_table.parquet")
    print(f"\ngame_table: {len(gt)} games, seasons {sorted(gt['season'].unique())}")

    # Also use existing phase1_features for known first-inning data
    p1_existing = pd.read_parquet(PROJECT_ROOT / "research" / "mlb_first_inning" / "phase1_features.parquet")
    existing_fi = {}
    for _, row in p1_existing.iterrows():
        existing_fi[int(row["game_pk"])] = {
            "status": "ok",
            "away_1st": int(row["top1_scored"]),
            "home_1st": int(row["bot1_scored"]),
        }
    print(f"Existing first-inning data from phase1_features: {len(existing_fi)} games")

    # Pre-populate cache with existing data
    cache = {}
    if CACHE_FILE.exists():
        cache = json.load(open(CACHE_FILE))
        cache = {int(k): v for k, v in cache.items()}
    for gp, data in existing_fi.items():
        if gp not in cache:
            cache[gp] = data
    with open(CACHE_FILE, "w") as f:
        json.dump({str(k): v for k, v in cache.items()}, f)

    # Fetch remaining
    all_pks = sorted(gt["game_pk"].unique())
    print(f"\nPHASE 0: Fetching first-inning scores for {len(all_pks)} games...")
    cache = fetch_first_inning_scores(all_pks)

    # Build table
    rows = []
    for _, g in gt.iterrows():
        gp = int(g["game_pk"])
        fi = cache.get(gp)
        if fi is None or fi.get("status") != "ok":
            continue
        rows.append({
            "game_pk": gp,
            "date": g["date"],
            "season": int(g["season"]),
            "home_team": g["home_team"],
            "away_team": g["away_team"],
            "away_1st_runs": fi["away_1st"],
            "home_1st_runs": fi["home_1st"],
            "total_1st_runs": fi["away_1st"] + fi["home_1st"],
            "nrfi": 1 if (fi["away_1st"] == 0 and fi["home_1st"] == 0) else 0,
            "yrfi": 1 if (fi["away_1st"] + fi["home_1st"]) > 0 else 0,
            "actual_total": g.get("actual_total"),
            "actual_f5_total": g.get("actual_f5_total"),
            "home_score": g.get("home_score"),
            "away_score": g.get("away_score"),
            "venue_name": g.get("venue_name"),
            "park_factor_runs": g.get("park_factor_runs"),
            "park_factor_hr": g.get("park_factor_hr"),
            "temperature": g.get("temperature"),
            "wind_speed": g.get("wind_speed"),
            "dome": 1 if g.get("roof_status") in ("closed", "dome") else 0,
        })

    nrfi_df = pd.DataFrame(rows)
    print(f"\nCanonical NRFI table: {len(nrfi_df)} games")
    print(f"  Seasons: {sorted(nrfi_df['season'].unique())}")

    # Join closing totals from canonical odds
    try:
        canon = pd.read_parquet(PROJECT_ROOT / "mlb_sim" / "data" / "mlb_odds_closing_canonical.parquet")
        canon_totals = canon.groupby("game_pk").agg(
            closing_total=("total_line", "first"),
        ).reset_index()
        nrfi_df = nrfi_df.merge(canon_totals, on="game_pk", how="left")
        matched = nrfi_df["closing_total"].notna().sum()
        print(f"  Closing totals matched: {matched}/{len(nrfi_df)}")
    except Exception as e:
        print(f"  Closing totals error: {e}")
        nrfi_df["closing_total"] = np.nan

    # Join F5 lines
    try:
        f5 = pd.read_parquet(PROJECT_ROOT / "mlb_sim_f5" / "data" / "f5_lines_historical.parquet")
        f5_canon = f5[f5["is_canonical"] == True].copy()
        # game_id in F5 might be game_pk
        f5_canon["game_pk"] = f5_canon["game_id"].astype(int)
        f5_totals = f5_canon.groupby("game_pk").agg(
            closing_f5_total=("f5_total", "first"),
        ).reset_index()
        nrfi_df = nrfi_df.merge(f5_totals, on="game_pk", how="left")
        matched_f5 = nrfi_df["closing_f5_total"].notna().sum()
        print(f"  F5 closing totals matched: {matched_f5}/{len(nrfi_df)}")
    except Exception as e:
        print(f"  F5 lines error: {e}")
        nrfi_df["closing_f5_total"] = np.nan

    # Save
    nrfi_df.to_parquet(OUT_DIR / "nrfi_research_table.parquet", index=False)
    nrfi_df.to_csv(OUT_DIR / "NRFI_PHASE1_FINAL_TABLE.csv", index=False)
    print(f"\n  Saved: nrfi_research_table.parquet, NRFI_PHASE1_FINAL_TABLE.csv")

    return nrfi_df


# ── PHASE 2-8: Analysis ─────────────────────────────────────────────────────

def run_analysis(df: pd.DataFrame):
    reports = {}

    # ── PHASE 2: Slate frequency ──
    print("\n" + "=" * 70)
    print("PHASE 2: Slate Frequency Analysis")
    print("=" * 70)

    daily = df.groupby("date").agg(
        games=("game_pk", "count"),
        nrfi_count=("nrfi", "sum"),
        yrfi_count=("yrfi", "sum"),
    ).reset_index()
    daily["nrfi_rate"] = daily["nrfi_count"] / daily["games"]

    p2_lines = []
    p2_lines.append("# Phase 2: Slate Frequency Analysis\n")
    p2_lines.append(f"Total games: {len(df)}")
    p2_lines.append(f"Total slates (days): {len(daily)}")
    p2_lines.append(f"Overall NRFI rate: {df['nrfi'].mean():.4f} ({df['nrfi'].mean()*100:.1f}%)")
    p2_lines.append(f"Overall YRFI rate: {df['yrfi'].mean():.4f} ({df['yrfi'].mean()*100:.1f}%)")
    p2_lines.append(f"\nImplied fair NRFI price (no vig): {-100 / (df['nrfi'].mean()) + 100:+.0f}")
    p2_lines.append(f"Implied fair YRFI price (no vig): {-100 / (df['yrfi'].mean()) + 100:+.0f}")
    p2_lines.append(f"\nGames per day: mean={daily['games'].mean():.1f}, median={daily['games'].median():.0f}")
    p2_lines.append(f"NRFIs per day: mean={daily['nrfi_count'].mean():.1f}, median={daily['nrfi_count'].median():.0f}")
    p2_lines.append(f"\nNRFI rate by season:")
    for season in sorted(df["season"].unique()):
        s = df[df["season"] == season]
        p2_lines.append(f"  {season}: {s['nrfi'].mean():.4f} ({len(s)} games)")

    p2_lines.append(f"\nDaily NRFI rate distribution:")
    for pct in [10, 25, 50, 75, 90]:
        p2_lines.append(f"  P{pct}: {daily['nrfi_rate'].quantile(pct/100):.3f}")

    p2_lines.append(f"\n## Half-inning breakdown")
    p2_lines.append(f"Top-1 clean (away scores 0): {(df['away_1st_runs']==0).mean():.4f}")
    p2_lines.append(f"Bot-1 clean (home scores 0): {(df['home_1st_runs']==0).mean():.4f}")
    p2_lines.append(f"Both clean (NRFI): {df['nrfi'].mean():.4f}")

    p2_text = "\n".join(p2_lines)
    print(p2_text)
    reports["phase2"] = p2_text

    # ── PHASE 3: Market baseline ──
    print("\n" + "=" * 70)
    print("PHASE 3: Market Baseline")
    print("=" * 70)

    p3_lines = []
    p3_lines.append("# Phase 3: Market Baseline\n")
    nrfi_rate = df["nrfi"].mean()
    yrfi_rate = df["yrfi"].mean()
    p3_lines.append(f"Actual NRFI rate: {nrfi_rate:.4f}")
    p3_lines.append(f"Typical market NRFI price: -130 to -150 (implied 56.5%-60.0%)")
    p3_lines.append(f"Typical market YRFI price: +105 to +120 (implied 45.5%-48.8%)")
    p3_lines.append(f"\nActual NRFI: {nrfi_rate*100:.1f}% — market implies ~57-60%")
    if nrfi_rate > 0.56:
        p3_lines.append("Market pricing appears roughly fair to slightly favorable for NRFI")
    elif nrfi_rate > 0.50:
        p3_lines.append("NRFI actual rate is BELOW typical market implied — market overprices NRFI on average")
    else:
        p3_lines.append("NRFI actual rate is well BELOW market implied — significant market overprice")

    p3_lines.append(f"\nActual YRFI: {yrfi_rate*100:.1f}% — market implies ~40-43%")

    # NRFI rate by season for trend
    p3_lines.append(f"\n## Season trend:")
    for season in sorted(df["season"].unique()):
        s = df[df["season"] == season]
        rate = s["nrfi"].mean()
        fair_price = -100 / rate + 100
        p3_lines.append(f"  {season}: NRFI={rate:.4f} fair_price={fair_price:+.0f}")

    p3_text = "\n".join(p3_lines)
    print(p3_text)
    reports["phase3"] = p3_text

    # ── PHASE 4: Full-game total buckets ──
    print("\n" + "=" * 70)
    print("PHASE 4: NRFI Rate by Full-Game Closing Total")
    print("=" * 70)

    p4_lines = []
    p4_lines.append("# Phase 4: NRFI Rate by Full-Game Closing Total\n")

    has_total = df[df["closing_total"].notna()].copy()
    p4_lines.append(f"Games with closing total: {len(has_total)}/{len(df)}")

    if len(has_total) > 500:
        # Create buckets
        total_buckets = has_total.copy()
        total_buckets["total_bucket"] = pd.cut(
            total_buckets["closing_total"],
            bins=[0, 7.0, 7.5, 8.0, 8.5, 9.0, 9.5, 10.0, 10.5, 11.0, 20],
            labels=["<=7.0", "7.5", "8.0", "8.5", "9.0", "9.5", "10.0", "10.5", "11.0", ">11.0"],
        )

        bucket_stats = total_buckets.groupby("total_bucket", observed=False).agg(
            games=("game_pk", "count"),
            nrfi_count=("nrfi", "sum"),
            nrfi_rate=("nrfi", "mean"),
            avg_1st_runs=("total_1st_runs", "mean"),
        ).reset_index()

        p4_lines.append(f"\n{'Total':<8} {'Games':>6} {'NRFI':>6} {'Rate':>8} {'Avg1stR':>8}")
        p4_lines.append("-" * 42)
        for _, row in bucket_stats.iterrows():
            if row["games"] > 0:
                p4_lines.append(f"{row['total_bucket']:<8} {int(row['games']):>6} {int(row['nrfi_count']):>6} "
                              f"{row['nrfi_rate']:>7.1%} {row['avg_1st_runs']:>8.3f}")

        p4_lines.append(f"\n## Key finding:")
        low = total_buckets[total_buckets["closing_total"] <= 8.0]["nrfi"].mean()
        mid = total_buckets[(total_buckets["closing_total"] > 8.0) & (total_buckets["closing_total"] <= 9.5)]["nrfi"].mean()
        high = total_buckets[total_buckets["closing_total"] > 9.5]["nrfi"].mean()
        p4_lines.append(f"  Low totals (<=8.0): NRFI rate = {low:.1%}")
        p4_lines.append(f"  Mid totals (8.5-9.5): NRFI rate = {mid:.1%}")
        p4_lines.append(f"  High totals (>9.5): NRFI rate = {high:.1%}")
    else:
        p4_lines.append("Insufficient games with closing totals for analysis.")

    p4_text = "\n".join(p4_lines)
    print(p4_text)
    reports["phase4"] = p4_text

    # ── PHASE 5: F5 total buckets ──
    print("\n" + "=" * 70)
    print("PHASE 5: NRFI Rate by F5 Closing Total")
    print("=" * 70)

    p5_lines = []
    p5_lines.append("# Phase 5: NRFI Rate by F5 Closing Total\n")

    has_f5 = df[df["closing_f5_total"].notna()].copy()
    p5_lines.append(f"Games with F5 closing total: {len(has_f5)}/{len(df)}")

    if len(has_f5) > 200:
        f5_buckets = has_f5.copy()
        f5_buckets["f5_bucket"] = pd.cut(
            f5_buckets["closing_f5_total"],
            bins=[0, 4.0, 4.5, 5.0, 5.5, 6.0, 6.5, 15],
            labels=["<=4.0", "4.5", "5.0", "5.5", "6.0", "6.5", ">6.5"],
        )

        f5_stats = f5_buckets.groupby("f5_bucket", observed=False).agg(
            games=("game_pk", "count"),
            nrfi_count=("nrfi", "sum"),
            nrfi_rate=("nrfi", "mean"),
            avg_1st_runs=("total_1st_runs", "mean"),
        ).reset_index()

        p5_lines.append(f"\n{'F5 Tot':<8} {'Games':>6} {'NRFI':>6} {'Rate':>8} {'Avg1stR':>8}")
        p5_lines.append("-" * 42)
        for _, row in f5_stats.iterrows():
            if row["games"] > 0:
                p5_lines.append(f"{row['f5_bucket']:<8} {int(row['games']):>6} {int(row['nrfi_count']):>6} "
                              f"{row['nrfi_rate']:>7.1%} {row['avg_1st_runs']:>8.3f}")

        p5_lines.append(f"\n## Key finding:")
        low_f5 = f5_buckets[f5_buckets["closing_f5_total"] <= 4.5]["nrfi"].mean()
        high_f5 = f5_buckets[f5_buckets["closing_f5_total"] > 5.5]["nrfi"].mean()
        p5_lines.append(f"  Low F5 totals (<=4.5): NRFI rate = {low_f5:.1%}")
        p5_lines.append(f"  High F5 totals (>5.5): NRFI rate = {high_f5:.1%}")
    else:
        p5_lines.append("Insufficient games with F5 closing totals for analysis.")

    p5_text = "\n".join(p5_lines)
    print(p5_text)
    reports["phase5"] = p5_text

    # ── PHASE 6: Interaction table (full-game x F5) ──
    print("\n" + "=" * 70)
    print("PHASE 6: Interaction Table (Full-Game Total x F5 Total)")
    print("=" * 70)

    p6_lines = []
    p6_lines.append("# Phase 6: Interaction Table (Full-Game Total x F5 Total)\n")

    has_both = df[(df["closing_total"].notna()) & (df["closing_f5_total"].notna())].copy()
    p6_lines.append(f"Games with both totals: {len(has_both)}/{len(df)}")

    if len(has_both) > 200:
        has_both["fg_bucket"] = pd.cut(
            has_both["closing_total"],
            bins=[0, 8.0, 8.5, 9.0, 9.5, 10.0, 20],
            labels=["<=8.0", "8.5", "9.0", "9.5", "10.0", ">10.0"],
        )
        has_both["f5_bucket"] = pd.cut(
            has_both["closing_f5_total"],
            bins=[0, 4.5, 5.0, 5.5, 15],
            labels=["<=4.5", "5.0", "5.5", ">5.5"],
        )

        interaction = has_both.groupby(["fg_bucket", "f5_bucket"], observed=False).agg(
            n=("game_pk", "count"),
            nrfi_rate=("nrfi", "mean"),
        ).reset_index()

        # Pivot table
        pivot = interaction.pivot(index="fg_bucket", columns="f5_bucket", values="nrfi_rate")
        pivot_n = interaction.pivot(index="fg_bucket", columns="f5_bucket", values="n")

        p6_lines.append(f"\nNRFI Rate by Full-Game Total (rows) x F5 Total (columns):")
        p6_lines.append(f"\n{'':>10}", )
        header = f"{'FG Total':<10}"
        for col in pivot.columns:
            header += f" {col:>10}"
        p6_lines.append(header)
        p6_lines.append("-" * (10 + 11 * len(pivot.columns)))

        for idx in pivot.index:
            line = f"{idx:<10}"
            for col in pivot.columns:
                rate = pivot.loc[idx, col]
                n = pivot_n.loc[idx, col]
                if pd.notna(rate) and n > 10:
                    line += f" {rate:>9.1%}"
                elif pd.notna(rate):
                    line += f" {rate:>8.1%}*"
                else:
                    line += f" {'--':>10}"
            p6_lines.append(line)

        p6_lines.append("\n* = fewer than 10 games in cell")

        # Best pockets
        p6_lines.append(f"\n## Top NRFI pockets (n>=20):")
        good = interaction[(interaction["n"] >= 20)].sort_values("nrfi_rate", ascending=False).head(5)
        for _, row in good.iterrows():
            p6_lines.append(f"  FG={row['fg_bucket']}, F5={row['f5_bucket']}: "
                          f"NRFI={row['nrfi_rate']:.1%} (n={int(row['n'])})")

        p6_lines.append(f"\n## Worst NRFI pockets (n>=20):")
        bad = interaction[(interaction["n"] >= 20)].sort_values("nrfi_rate", ascending=True).head(5)
        for _, row in bad.iterrows():
            p6_lines.append(f"  FG={row['fg_bucket']}, F5={row['f5_bucket']}: "
                          f"NRFI={row['nrfi_rate']:.1%} (n={int(row['n'])})")
    else:
        p6_lines.append("Insufficient games with both totals for interaction analysis.")

    p6_text = "\n".join(p6_lines)
    print(p6_text)
    reports["phase6"] = p6_text

    # ── PHASE 7: Underpriced pocket identification ──
    print("\n" + "=" * 70)
    print("PHASE 7: Underpriced Pocket Identification")
    print("=" * 70)

    p7_lines = []
    p7_lines.append("# Phase 7: Underpriced Pocket Identification\n")

    # Standard market NRFI is priced around -135 (implied ~57.4%)
    market_implied = 0.574
    p7_lines.append(f"Assumed average market NRFI implied probability: {market_implied:.1%}")
    p7_lines.append(f"(Typical -135 line = 57.4% implied)")
    p7_lines.append("")

    if len(has_total) > 500:
        # By full-game total bucket
        p7_lines.append("## By full-game closing total:")
        total_buckets2 = has_total.copy()
        total_buckets2["total_bucket"] = pd.cut(
            total_buckets2["closing_total"],
            bins=[0, 7.5, 8.0, 8.5, 9.0, 9.5, 10.0, 10.5, 20],
            labels=["<=7.5", "8.0", "8.5", "9.0", "9.5", "10.0", "10.5", ">10.5"],
        )
        for bucket in total_buckets2["total_bucket"].cat.categories:
            subset = total_buckets2[total_buckets2["total_bucket"] == bucket]
            if len(subset) < 30:
                continue
            rate = subset["nrfi"].mean()
            edge = rate - market_implied
            fair = -100 / rate + 100 if rate > 0 else 0
            status = "UNDERPRICED" if edge > 0.02 else ("FAIR" if abs(edge) <= 0.02 else "OVERPRICED")
            p7_lines.append(f"  {bucket}: NRFI={rate:.1%}, edge={edge:+.1%}, fair={fair:+.0f} — {status} (n={len(subset)})")

    if len(has_f5) > 200:
        p7_lines.append(f"\n## By F5 closing total:")
        f5_buckets2 = has_f5.copy()
        f5_buckets2["f5_bucket"] = pd.cut(
            f5_buckets2["closing_f5_total"],
            bins=[0, 4.0, 4.5, 5.0, 5.5, 6.0, 15],
            labels=["<=4.0", "4.5", "5.0", "5.5", "6.0", ">6.0"],
        )
        for bucket in f5_buckets2["f5_bucket"].cat.categories:
            subset = f5_buckets2[f5_buckets2["f5_bucket"] == bucket]
            if len(subset) < 20:
                continue
            rate = subset["nrfi"].mean()
            edge = rate - market_implied
            fair = -100 / rate + 100 if rate > 0 else 0
            status = "UNDERPRICED" if edge > 0.02 else ("FAIR" if abs(edge) <= 0.02 else "OVERPRICED")
            p7_lines.append(f"  {bucket}: NRFI={rate:.1%}, edge={edge:+.1%}, fair={fair:+.0f} — {status} (n={len(subset)})")

    # Dome vs outdoor
    p7_lines.append(f"\n## Environment splits:")
    dome = df[df["dome"] == 1]
    outdoor = df[df["dome"] == 0]
    p7_lines.append(f"  Dome: NRFI={dome['nrfi'].mean():.1%} (n={len(dome)})")
    p7_lines.append(f"  Outdoor: NRFI={outdoor['nrfi'].mean():.1%} (n={len(outdoor)})")

    # Temperature splits (outdoor only)
    out_temp = outdoor[outdoor["temperature"].notna()].copy()
    if len(out_temp) > 100:
        cold = out_temp[out_temp["temperature"] < 55]
        mild = out_temp[(out_temp["temperature"] >= 55) & (out_temp["temperature"] < 75)]
        warm = out_temp[out_temp["temperature"] >= 75]
        p7_lines.append(f"\n  Outdoor by temperature:")
        p7_lines.append(f"    Cold (<55F): NRFI={cold['nrfi'].mean():.1%} (n={len(cold)})")
        p7_lines.append(f"    Mild (55-74F): NRFI={mild['nrfi'].mean():.1%} (n={len(mild)})")
        p7_lines.append(f"    Warm (>=75F): NRFI={warm['nrfi'].mean():.1%} (n={len(warm)})")

    p7_text = "\n".join(p7_lines)
    print(p7_text)
    reports["phase7"] = p7_text

    # ── PHASE 8: Top-3 selection framework ──
    print("\n" + "=" * 70)
    print("PHASE 8: Top-3 Selection Framework")
    print("=" * 70)

    p8_lines = []
    p8_lines.append("# Phase 8: Top-3 Selection Framework\n")
    p8_lines.append("## Objective: Identify the best daily NRFI legs for parlay construction\n")

    p8_lines.append("### Signal hierarchy (from existing micro-model research):")
    p8_lines.append("1. **Combined p_yrfi rank** — bottom 10% of slate = strongest NRFI signal")
    p8_lines.append("2. **Full-game closing total** — lower total = higher NRFI rate")
    p8_lines.append("3. **F5 closing total** — provides independent validation")
    p8_lines.append("4. **Dome games** — slightly higher NRFI rate (controlled environment)")
    p8_lines.append("5. **Starter archetype** — CONTACT_RISK exclusion from Phase 8 overlay")
    p8_lines.append("6. **Top-3 lineup stability** — both-changed exclusion from Phase 11")

    # Quantify the value of each filter
    p8_lines.append("\n### Filter value quantification:")

    if len(has_total) > 500:
        low_total = has_total[has_total["closing_total"] <= 8.0]
        high_total = has_total[has_total["closing_total"] >= 10.0]
        p8_lines.append(f"\n  Closing total <=8.0: NRFI={low_total['nrfi'].mean():.1%} (n={len(low_total)})")
        p8_lines.append(f"  Closing total >=10.0: NRFI={high_total['nrfi'].mean():.1%} (n={len(high_total)})")
        lift = low_total['nrfi'].mean() - high_total['nrfi'].mean()
        p8_lines.append(f"  Lift: {lift:+.1%}")

    if len(has_f5) > 200:
        low_f5 = has_f5[has_f5["closing_f5_total"] <= 4.5]
        high_f5 = has_f5[has_f5["closing_f5_total"] >= 5.5]
        if len(low_f5) > 20 and len(high_f5) > 20:
            p8_lines.append(f"\n  F5 total <=4.5: NRFI={low_f5['nrfi'].mean():.1%} (n={len(low_f5)})")
            p8_lines.append(f"  F5 total >=5.5: NRFI={high_f5['nrfi'].mean():.1%} (n={len(high_f5)})")
            lift_f5 = low_f5['nrfi'].mean() - high_f5['nrfi'].mean()
            p8_lines.append(f"  Lift: {lift_f5:+.1%}")

    # Best combined filter
    if len(has_both) > 100:
        best = has_both[(has_both["closing_total"] <= 8.5) & (has_both["closing_f5_total"] <= 5.0)]
        if len(best) > 20:
            p8_lines.append(f"\n  Combined (FG<=8.5 AND F5<=5.0): NRFI={best['nrfi'].mean():.1%} (n={len(best)})")
            p8_lines.append(f"  vs overall: {df['nrfi'].mean():.1%}")
            p8_lines.append(f"  Lift: {best['nrfi'].mean() - df['nrfi'].mean():+.1%}")

    p8_lines.append("\n### Recommended selection criteria for top-3 NRFI legs:")
    p8_lines.append("1. Closing total <= 8.5 (strong prior)")
    p8_lines.append("2. F5 total <= 5.0 (confirms starter quality)")
    p8_lines.append("3. Micro-model p_yrfi in bottom 10% of slate")
    p8_lines.append("4. NOT CONTACT_RISK archetype starter at home")
    p8_lines.append("5. Top-3 lineup stable (not both changed)")
    p8_lines.append("6. Dome or mild temperature preferred (avoid extreme heat)")

    p8_text = "\n".join(p8_lines)
    print(p8_text)
    reports["phase8"] = p8_text

    return reports


def write_exec_summary(df: pd.DataFrame, reports: dict):
    lines = []
    lines.append("# NRFI Phase 1 — Executive Summary")
    lines.append(f"\nGenerated: 2026-04-11")
    lines.append(f"Data: {len(df)} MLB games, {sorted(df['season'].unique())}")
    lines.append("")

    nrfi_rate = df["nrfi"].mean()
    lines.append("## Key Findings\n")
    lines.append(f"1. **Overall NRFI rate: {nrfi_rate:.1%}** across {len(df)} games (2022-2026)")
    lines.append(f"   - Top-1 clean (away 0 in 1st): {(df['away_1st_runs']==0).mean():.1%}")
    lines.append(f"   - Bot-1 clean (home 0 in 1st): {(df['home_1st_runs']==0).mean():.1%}")
    lines.append(f"   - Fair NRFI price (no vig): {-100/nrfi_rate+100:+.0f}")
    lines.append(f"   - Typical market price: -135 (implied 57.4%)")

    has_total = df[df["closing_total"].notna()]
    if len(has_total) > 500:
        low = has_total[has_total["closing_total"] <= 8.0]["nrfi"].mean()
        high = has_total[has_total["closing_total"] >= 10.0]["nrfi"].mean()
        lines.append(f"\n2. **Full-game total is the strongest NRFI filter**")
        lines.append(f"   - Closing total <=8.0: NRFI = {low:.1%}")
        lines.append(f"   - Closing total >=10.0: NRFI = {high:.1%}")
        lines.append(f"   - Spread: {low - high:+.1%}")

    has_f5 = df[df["closing_f5_total"].notna()]
    if len(has_f5) > 200:
        low_f5 = has_f5[has_f5["closing_f5_total"] <= 4.5]["nrfi"].mean()
        high_f5 = has_f5[has_f5["closing_f5_total"] >= 5.5]["nrfi"].mean()
        lines.append(f"\n3. **F5 total provides independent confirmation**")
        lines.append(f"   - F5 <=4.5: NRFI = {low_f5:.1%}")
        lines.append(f"   - F5 >=5.5: NRFI = {high_f5:.1%}")

    has_both = df[(df["closing_total"].notna()) & (df["closing_f5_total"].notna())]
    if len(has_both) > 100:
        best = has_both[(has_both["closing_total"] <= 8.5) & (has_both["closing_f5_total"] <= 5.0)]
        if len(best) > 20:
            lines.append(f"\n4. **Best combined filter (FG<=8.5 AND F5<=5.0): NRFI = {best['nrfi'].mean():.1%}** (n={len(best)})")
            lines.append(f"   - vs baseline {nrfi_rate:.1%} = {best['nrfi'].mean()-nrfi_rate:+.1%} lift")

    lines.append(f"\n5. **Environment effects are modest**")
    dome_rate = df[df["dome"]==1]["nrfi"].mean()
    outdoor_rate = df[df["dome"]==0]["nrfi"].mean()
    lines.append(f"   - Dome: {dome_rate:.1%}, Outdoor: {outdoor_rate:.1%}")

    lines.append(f"\n## Season stability")
    for season in sorted(df["season"].unique()):
        s = df[df["season"] == season]
        lines.append(f"  {season}: NRFI = {s['nrfi'].mean():.1%} ({len(s)} games)")

    lines.append(f"\n## Actionable framework")
    lines.append("Select top-3 NRFI legs daily using:")
    lines.append("1. Closing total <= 8.5")
    lines.append("2. F5 total <= 5.0 (when available)")
    lines.append("3. Micro-model p_yrfi bottom 10%")
    lines.append("4. Exclude CONTACT_RISK archetype starters")
    lines.append("5. Exclude both-top-3-changed lineups")
    lines.append("6. Prefer dome/mild temperature")

    lines.append(f"\n## Files")
    lines.append(f"- `nrfi_research_table.parquet` — {len(df)} rows, canonical NRFI table")
    lines.append(f"- `NRFI_PHASE1_FINAL_TABLE.csv` — same, CSV format")
    lines.append(f"- Phase reports: phase2-phase8 markdown files")

    text = "\n".join(lines)
    with open(OUT_DIR / "NRFI_PHASE1_EXEC_SUMMARY.md", "w") as f:
        f.write(text)
    print("\n" + "=" * 70)
    print(text)
    return text


# ── Main ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    df = build_canonical_table()
    reports = run_analysis(df)

    # Write phase reports
    for phase, text in reports.items():
        with open(OUT_DIR / f"{phase}_report.md", "w") as f:
            f.write(text)

    write_exec_summary(df, reports)
    print("\n\nDONE. All files written to research/recovery/nrfi_phase1/")
