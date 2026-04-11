import pandas as pd
import numpy as np

nrfi = pd.read_parquet("research/recovery/nrfi_phase1/nrfi_research_table.parquet")
canon = pd.read_parquet("mlb_sim/data/mlb_odds_closing_canonical.parquet")

nrfi["game_pk"] = nrfi["game_pk"].astype(str)
canon["game_pk"] = canon["game_pk"].astype(str)
canon_dedup = canon.drop_duplicates(subset="game_pk", keep="first")

merged = nrfi.merge(canon_dedup[["game_pk", "home_total_line", "away_total_line"]], on="game_pk", how="inner")
merged = merged.dropna(subset=["home_total_line","away_total_line"])
print("Merged: %d games with team totals" % len(merged))
print("home_total_line dtype:", merged["home_total_line"].dtype)
print("nrfi dtype:", merged["nrfi"].dtype)

merged["tt_min"] = merged[["home_total_line", "away_total_line"]].min(axis=1)
merged["tt_max"] = merged[["home_total_line", "away_total_line"]].max(axis=1)
merged["tt_dispersion"] = merged["tt_max"] - merged["tt_min"]
merged["tt_sum"] = merged["home_total_line"] + merged["away_total_line"]
merged["both_below_4"] = (merged["home_total_line"] <= 4.0) & (merged["away_total_line"] <= 4.0)
merged["one_below_3_5"] = ((merged["home_total_line"] <= 3.5) | (merged["away_total_line"] <= 3.5))

print("\n=== NRFI Rate by Min Team Total ===")
for bucket in sorted(merged["tt_min"].unique()):
    sub = merged[merged["tt_min"].values == bucket]
    if len(sub) >= 30:
        print("  tt_min=%.1f: N=%5d, NRFI=%.3f" % (bucket, len(sub), sub["nrfi"].mean()))

print("\n=== NRFI Rate by Max Team Total ===")
for bucket in sorted(merged["tt_max"].unique()):
    sub = merged[merged["tt_max"].values == bucket]
    if len(sub) >= 30:
        print("  tt_max=%.1f: N=%5d, NRFI=%.3f" % (bucket, len(sub), sub["nrfi"].mean()))

print("\n=== NRFI Rate by TT Dispersion ===")
for bucket in sorted(merged["tt_dispersion"].unique()):
    sub = merged[merged["tt_dispersion"].values == bucket]
    if len(sub) >= 30:
        print("  disp=%.1f: N=%5d, NRFI=%.3f" % (bucket, len(sub), sub["nrfi"].mean()))

print("\n=== NRFI Rate by Both Below 4.0 ===")
for val in [True, False]:
    sub = merged[merged["both_below_4"].values == val]
    print("  both_below_4=%s: N=%5d, NRFI=%.3f" % (val, len(sub), sub["nrfi"].mean()))

print("\n=== NRFI Rate by One Below 3.5 ===")
for val in [True, False]:
    sub = merged[merged["one_below_3_5"].values == val]
    print("  one_below_3_5=%s: N=%5d, NRFI=%.3f" % (val, len(sub), sub["nrfi"].mean()))

print("\n=== NRFI Rate by TT Sum (binned) ===")
for lo, hi in [(5,7),(7,7.5),(7.5,8),(8,8.5),(8.5,9),(9,9.5),(9.5,12)]:
    mask = (merged["tt_sum"].values > lo) & (merged["tt_sum"].values <= hi)
    sub = merged[mask]
    if len(sub) >= 30:
        print("  tt_sum=(%.1f,%.1f]: N=%5d, NRFI=%.3f" % (lo, hi, len(sub), sub["nrfi"].mean()))

# YRFI lines merge
yrfi = pd.read_parquet("research/yrfi/data/yrfi_lines_historical.parquet")
yrfi["game_id"] = yrfi["game_id"].astype(str)
yrfi_dedup = yrfi.drop_duplicates("game_id", keep="first")
yrfi_merged = nrfi.merge(yrfi_dedup[["game_id","yrfi_over_price","nrfi_under_price"]], 
                          left_on="game_pk", right_on="game_id", how="inner")
print("\n=== YRFI Lines matched to NRFI table: %d ===" % len(yrfi_merged))
if len(yrfi_merged) > 0:
    print("  Date range: %s - %s" % (yrfi_merged["date"].min(), yrfi_merged["date"].max()))
    yrfi_merged["nrfi_implied"] = yrfi_merged["nrfi_under_price"].apply(
        lambda x: abs(x)/(abs(x)+100) if x < 0 else 100/(x+100))
    
    print("\n  NRFI Rate by Market Implied Probability Quintile:")
    yrfi_merged["nrfi_q"] = pd.qcut(yrfi_merged["nrfi_implied"], 5, duplicates="drop")
    for b in sorted(yrfi_merged["nrfi_q"].dropna().unique()):
        sub = yrfi_merged[yrfi_merged["nrfi_q"].values == b]
        if len(sub) >= 30:
            actual = sub["nrfi"].mean()
            implied = sub["nrfi_implied"].mean()
            print("    %s: N=%4d, actual_NRFI=%.3f, mkt_implied=%.3f, diff=%+.3f" % (b, len(sub), actual, implied, actual-implied))

# Save preview CSV
merged.to_csv("research/recovery/nrfi_phase1b_data_audit/team_total_nrfi_preview.csv", index=False)
print("\nSaved preview CSV: %d rows" % len(merged))
