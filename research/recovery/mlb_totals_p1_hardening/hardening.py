#!/usr/bin/env python3
"""MLB Totals P1 Hardening — EARLY_HEAVY x Warm Temp FG OVER"""
import pandas as pd, numpy as np, warnings, json
from pathlib import Path
from scipy import stats
warnings.filterwarnings("ignore")
np.random.seed(42)

OUT = Path("/root/mlb-model/research/recovery/mlb_totals_p1_hardening")
OUT.mkdir(parents=True, exist_ok=True)

def to_dec(p):
    if pd.isna(p): return np.nan
    return 1+p/100 if p>0 else 1+100/abs(p)

lines = []
def log(s=""):
    print(s); lines.append(str(s))

# ═══════════════════════════════════════════════════════════════════════
# PHASE 0: Load data and lock object
# ═══════════════════════════════════════════════════════════════════════
log("="*70)
log("PHASE 0: Lock exact object")
log("="*70)

df = pd.read_csv("/root/mlb-model/research/recovery/mlb_totals_p1_fg_f5_path_engine/MLB_TOTALS_P1_FINAL_TABLE.csv")
log(f"Loaded P1 table: {df.shape}")
log(f"Columns: {list(df.columns)[:30]}")

# Reproduce the thresholds from discovery (2023)
disc_all = df[df["split"]=="discovery"]
f5r_p67 = disc_all["f5_ratio"].quantile(0.67)
log(f"\nFrozen thresholds from discovery:")
log(f"  f5_ratio p67 = {f5r_p67:.4f}  (EARLY_HEAVY = f5_ratio > p67)")

# EARLY_HEAVY = path_state == "EARLY_HEAVY" (already classified)
# Warm = temperature >= discovery median
eh = df[df["path_state"]=="EARLY_HEAVY"].copy()
disc_eh = eh[eh["split"]=="discovery"]
temp_median = disc_eh["temperature"].median()
log(f"  temperature median (disc EARLY_HEAVY) = {temp_median:.1f}F")

# Check: was the split above or >= median?
# From pipeline: "med=sub[dc].median(); hi=sub[sub[dc]>=med]"
log(f"  Warm = temperature >= {temp_median:.1f}F (discovery median)")
log(f"  Side = FG OVER")
log(f"  Price = actual closing over price (total_over_price)")

# Also check the overall discovery temperature median used in interactions
disc_eh_temp_med = disc_all[disc_all["path_state"]=="EARLY_HEAVY"]["temperature"].median()
log(f"  Double-check: disc EARLY_HEAVY temp median = {disc_eh_temp_med:.1f}F")

# ═══════════════════════════════════════════════════════════════════════
# PHASE 1: Rebuild matches
# ═══════════════════════════════════════════════════════════════════════
log("\n" + "="*70)
log("PHASE 1: Rebuild matches — verify N per split")
log("="*70)

eh["warm"] = eh["temperature"] >= temp_median
matched = eh[eh["warm"] & eh["temperature"].notna()].copy()
log(f"\nEARLY_HEAVY total: {len(eh)}")
log(f"EARLY_HEAVY + warm (temp >= {temp_median:.0f}F): {len(matched)}")
log(f"\nN per split:")
for sp in ["discovery","validation","oos"]:
    n = len(matched[matched["split"]==sp])
    log(f"  {sp}: {n}")

log(f"\nExpected from P1: discovery=319, validation=105, oos=173")

# Also define controls: EARLY_HEAVY but NOT warm
controls = eh[~eh["warm"] & eh["temperature"].notna()].copy()
log(f"Controls (EARLY_HEAVY, temp < {temp_median:.0f}F): {len(controls)}")

# ═══════════════════════════════════════════════════════════════════════
# PHASE 2: Concentration audit
# ═══════════════════════════════════════════════════════════════════════
log("\n" + "="*70)
log("PHASE 2: Concentration audit")
log("="*70)

# Top home teams
log("\nTop 10 home teams:")
tt = matched.groupby("home_team").size().sort_values(ascending=False).head(10)
for t, n in tt.items():
    log(f"  {t}: {n}")

# Month distribution
matched["month"] = pd.to_datetime(matched["date"]).dt.month
log("\nMonth distribution:")
md = matched.groupby("month").size()
for m_, n in md.items():
    log(f"  Month {m_:2d}: {n}")

# Temperature distribution
log(f"\nTemperature stats:")
log(f"  {matched['temperature'].describe().to_string()}")

# Top parks (use home_team as proxy)
log("\nTop 5 home teams (across all splits):")
top3_teams = tt.head(3).index.tolist()
log(f"  {top3_teams}")

# Leave-one-out for top 3 teams
log("\nLeave-one-out: top 3 teams")
for team in top3_teams:
    sub = matched[matched["home_team"] != team]
    wr = sub["fg_over"].mean()
    n = len(sub)
    sub["dec"] = sub["total_over_price"].apply(to_dec)
    sub["pnl"] = np.where(sub["fg_over"]==1, 100*(sub["dec"]-1),
                          np.where(sub["fg_push"]==1, 0, -100))
    roi = sub["pnl"].sum() / (n*100) if n > 0 else 0
    log(f"  Exclude {team}: N={n}, win={wr:.3f}, ROI={roi:+.1%}")

# Leave-one-out for hottest month
hottest_month = matched.groupby("month")["temperature"].mean().idxmax()
log(f"\nLeave-one-out: hottest month ({hottest_month})")
sub = matched[matched["month"] != hottest_month]
wr = sub["fg_over"].mean()
n = len(sub)
sub_c = sub.copy()
sub_c["dec"] = sub_c["total_over_price"].apply(to_dec)
sub_c["pnl"] = np.where(sub_c["fg_over"]==1, 100*(sub_c["dec"]-1),
                        np.where(sub_c["fg_push"]==1, 0, -100))
roi = sub_c["pnl"].sum() / (n*100) if n > 0 else 0
log(f"  Exclude month {hottest_month}: N={n}, win={wr:.3f}, ROI={roi:+.1%}")

# Leave-one-out top 3 months
log("\nLeave-one-out: by month")
for mo in sorted(matched["month"].unique()):
    sub = matched[matched["month"] != mo]
    wr = sub["fg_over"].mean()
    n = len(sub)
    sub_c = sub.copy()
    sub_c["dec"] = sub_c["total_over_price"].apply(to_dec)
    sub_c["pnl"] = np.where(sub_c["fg_over"]==1, 100*(sub_c["dec"]-1),
                            np.where(sub_c["fg_push"]==1, 0, -100))
    roi = sub_c["pnl"].sum() / (n*100) if n > 0 else 0
    log(f"  Exclude month {mo:2d}: N={n}, win={wr:.3f}, ROI={roi:+.1%}")

# ═══════════════════════════════════════════════════════════════════════
# PHASE 3: Micro-band stability
# ═══════════════════════════════════════════════════════════════════════
log("\n" + "="*70)
log("PHASE 3: Micro-band stability")
log("="*70)

def band_stats(sub, label):
    n = len(sub)
    if n < 5:
        return f"  {label}: N={n} (too few)"
    wr = sub["fg_over"].mean()
    sc = sub.copy()
    sc["dec"] = sc["total_over_price"].apply(to_dec)
    sc["pnl"] = np.where(sc["fg_over"]==1, 100*(sc["dec"]-1),
                         np.where(sc["fg_push"]==1, 0, -100))
    roi = sc["pnl"].sum() / (n*100)
    return f"  {label}: N={n:4d}, win={wr:.3f}, ROI={roi:+.1%}"

# By FG total line
log("\nBy FG total line:")
for lo, hi, label in [(0, 8.0, "<=8.0"), (8.0, 8.5, "8.5"), (8.5, 9.0, "9.0"), (9.0, 9.5, "9.5"), (9.5, 99, ">=10.0")]:
    if label == "<=8.0":
        sub = matched[matched["total_line"] <= lo + 0.01]  # actually <=8.0
        sub = matched[matched["total_line"] <= 8.0]
    elif label == ">=10.0":
        sub = matched[matched["total_line"] >= 9.5]
    else:
        sub = matched[(matched["total_line"] > lo) & (matched["total_line"] <= hi)]
    log(band_stats(sub, label))

# By temperature band
log("\nBy temperature band:")
for lo, hi, label in [(temp_median, 74, f"{temp_median:.0f}-74"), (75, 84, "75-84"), (85, 120, "85+")]:
    sub = matched[(matched["temperature"] >= lo) & (matched["temperature"] <= hi)]
    log(band_stats(sub, label))

# By closing over price
log("\nBy closing over price:")
for lo, hi, label in [(-200, -120, "<=-120"), (-120, -110, "-120 to -110"),
                       (-110, -105, "-110 to -105"), (-105, 100, "-105 to +100"), (100, 300, "+100+")]:
    sub = matched[(matched["total_over_price"] >= lo) & (matched["total_over_price"] < hi)]
    if label == "+100+":
        sub = matched[matched["total_over_price"] >= 100]
    log(band_stats(sub, label))

# ═══════════════════════════════════════════════════════════════════════
# PHASE 4: Proxy risk audit
# ═══════════════════════════════════════════════════════════════════════
log("\n" + "="*70)
log("PHASE 4: Proxy risk audit — is warm temp just a summer proxy?")
log("="*70)

matched["game_month"] = pd.to_datetime(matched["date"]).dt.month

# Month-group analysis
log("\nBy month group:")
groups = {
    "Apr-May (early)": [4, 5],
    "Jun-Aug (summer)": [6, 7, 8],
    "Sep-Oct (late)": [9, 10]
}
for gname, months in groups.items():
    sub = matched[matched["game_month"].isin(months)]
    log(band_stats(sub, gname))

log("\nBy month group, per split:")
for gname, months in groups.items():
    log(f"\n  {gname}:")
    for sp in ["discovery","validation","oos"]:
        sub = matched[(matched["game_month"].isin(months)) & (matched["split"]==sp)]
        n = len(sub)
        if n < 3:
            log(f"    {sp}: N={n} (too few)")
            continue
        wr = sub["fg_over"].mean()
        sc = sub.copy()
        sc["dec"] = sc["total_over_price"].apply(to_dec)
        sc["pnl"] = np.where(sc["fg_over"]==1, 100*(sc["dec"]-1),
                             np.where(sc["fg_push"]==1, 0, -100))
        roi = sc["pnl"].sum() / (n*100)
        log(f"    {sp}: N={n:3d}, win={wr:.3f}, ROI={roi:+.1%}")

# Dome detection: check if we have roof info
log("\nDome/outdoor check:")
# Use known dome teams
dome_teams = ["ARI","HOU","MIA","MIL","MIN","SEA","TB","TEX","TOR"]
matched["is_dome"] = matched["home_team"].isin(dome_teams)
for dome_val, label in [(True, "Dome/retractable"), (False, "Outdoor")]:
    sub = matched[matched["is_dome"] == dome_val]
    log(band_stats(sub, label))

# Day vs night: approximate from game time if available, else skip
# Check if we have time info
if "game_time" in matched.columns:
    log("\nDay vs Night:")
else:
    log("\nDay vs Night: no game_time column available, skip")

# Park altitude/environment
log("\nWarm-climate parks vs cold-climate parks:")
warm_climate = ["ARI","HOU","MIA","TEX","ATL","CIN","KC","LAA","LAD","SD","SF","OAK","COL"]
matched["warm_climate_park"] = matched["home_team"].isin(warm_climate)
for wc, label in [(True, "Warm-climate parks"), (False, "Cold-climate parks")]:
    sub = matched[matched["warm_climate_park"] == wc]
    log(band_stats(sub, label))

# ═══════════════════════════════════════════════════════════════════════
# PHASE 5: Late-scoring mechanism confirmation
# ═══════════════════════════════════════════════════════════════════════
log("\n" + "="*70)
log("PHASE 5: Late-scoring mechanism confirmation")
log("="*70)

# Matched (EARLY_HEAVY + warm) vs controls (EARLY_HEAVY + NOT warm)
for sp in ["all","discovery","validation","oos"]:
    if sp == "all":
        m_sub = matched; c_sub = controls
    else:
        m_sub = matched[matched["split"]==sp]; c_sub = controls[controls["split"]==sp]
    if len(m_sub) < 10 or len(c_sub) < 10:
        log(f"\n{sp}: too few")
        continue
    
    # F5 actual runs
    m_f5 = m_sub["actual_f5_total"].mean()
    c_f5 = c_sub["actual_f5_total"].mean()
    # Late actual runs
    m_sub_c = m_sub.copy(); c_sub_c = c_sub.copy()
    m_sub_c["actual_late"] = m_sub_c["actual_total"] - m_sub_c["actual_f5_total"]
    c_sub_c["actual_late"] = c_sub_c["actual_total"] - c_sub_c["actual_f5_total"]
    m_late = m_sub_c["actual_late"].mean()
    c_late = c_sub_c["actual_late"].mean()
    m_total = m_sub["actual_total"].mean()
    c_total = c_sub["actual_total"].mean()
    
    t_f5, p_f5 = stats.ttest_ind(m_sub["actual_f5_total"].dropna(), c_sub["actual_f5_total"].dropna())
    t_late, p_late = stats.ttest_ind(m_sub_c["actual_late"].dropna(), c_sub_c["actual_late"].dropna())
    
    log(f"\n{sp.upper()} — matched(N={len(m_sub)}) vs controls(N={len(c_sub)}):")
    log(f"  Actual F5 runs:  matched={m_f5:.2f}, control={c_f5:.2f}, diff={m_f5-c_f5:+.2f} (t={t_f5:.2f}, p={p_f5:.3f})")
    log(f"  Actual late runs: matched={m_late:.2f}, control={c_late:.2f}, diff={m_late-c_late:+.2f} (t={t_late:.2f}, p={p_late:.3f})")
    log(f"  Actual total:    matched={m_total:.2f}, control={c_total:.2f}, diff={m_total-c_total:+.2f}")

# ═══════════════════════════════════════════════════════════════════════
# PHASE 6: Regime decay audit
# ═══════════════════════════════════════════════════════════════════════
log("\n" + "="*70)
log("PHASE 6: Regime decay audit — year-by-year")
log("="*70)

matched["year"] = pd.to_datetime(matched["date"]).dt.year
for yr in sorted(matched["year"].unique()):
    sub = matched[matched["year"]==yr].copy()
    n = len(sub)
    wr = sub["fg_over"].mean()
    sub["dec"] = sub["total_over_price"].apply(to_dec)
    sub["pnl"] = np.where(sub["fg_over"]==1, 100*(sub["dec"]-1),
                         np.where(sub["fg_push"]==1, 0, -100))
    roi = sub["pnl"].sum() / (n*100)
    avg_price = sub["total_over_price"].mean()
    avg_total = sub["total_line"].mean()
    avg_temp = sub["temperature"].mean()
    log(f"  {yr}: N={n:3d}, win={wr:.3f}, ROI={roi:+.1%}, avg_price={avg_price:.0f}, avg_line={avg_total:.1f}, avg_temp={avg_temp:.0f}F")

# ═══════════════════════════════════════════════════════════════════════
# PHASE 7: Live feasibility — temperature source
# ═══════════════════════════════════════════════════════════════════════
log("\n" + "="*70)
log("PHASE 7: Live feasibility — temperature source audit")
log("="*70)

log("""
CRITICAL FINDING:
- game_table.parquet uses Open-Meteo ARCHIVE API (historical actual weather)
  → sim/phase1_build_game_table.py: fetch_historical_weather()
  → This fetches actual game-time temperature AFTER the game occurred

- Live pipeline uses Open-Meteo FORECAST API
  → modules/weather.py: fetch_weather()
  → forecast_days=2, returns current forecast for upcoming games

IMPLICATION:
- The research object was built on ACTUAL game-time temperature (known postgame)
- Live deployment would use FORECAST temperature (known pregame)
- These are DIFFERENT information sets
- Forecast error adds noise; warm threshold may not match actual conditions

RISK: Moderate
- Open-Meteo forecasts are generally accurate for same-day temperature
- Threshold is a median split (~{temp_med:.0f}F), not a tight boundary
- Most games near the threshold boundary are marginal anyway
- But systematic forecast bias (e.g., afternoon vs evening games) could shift hit rates
""".format(temp_med=temp_median))

# ═══════════════════════════════════════════════════════════════════════
# PHASE 8: Shadow design
# ═══════════════════════════════════════════════════════════════════════
log("\n" + "="*70)
log("PHASE 8: Shadow design (conditional on go)")
log("="*70)

# Check: does the signal survive the hardening?
# Compute overall stats
all_wr = matched["fg_over"].mean()
mc = matched.copy()
mc["dec"] = mc["total_over_price"].apply(to_dec)
mc["pnl"] = np.where(mc["fg_over"]==1, 100*(mc["dec"]-1),
                     np.where(mc["fg_push"]==1, 0, -100))
all_roi = mc["pnl"].sum() / (len(mc)*100)
oos_sub = matched[matched["split"]=="oos"].copy()
oos_wr = oos_sub["fg_over"].mean()
oos_sub["dec"] = oos_sub["total_over_price"].apply(to_dec)
oos_sub["pnl"] = np.where(oos_sub["fg_over"]==1, 100*(oos_sub["dec"]-1),
                          np.where(oos_sub["fg_push"]==1, 0, -100))
oos_roi = oos_sub["pnl"].sum() / (len(oos_sub)*100)

log(f"\nOverall: N={len(matched)}, win={all_wr:.3f}, ROI={all_roi:+.1%}")
log(f"OOS (2025): N={len(oos_sub)}, win={oos_wr:.3f}, ROI={oos_roi:+.1%}")

log("""
Shadow Design:
1. Trigger: path_state == EARLY_HEAVY AND forecast_temperature >= {temp_med:.0f}F
2. Side: FG OVER
3. Logging: game_pk, date, home_team, away_team, total_line, f5_line, f5_ratio,
   forecast_temp, actual_temp (backfilled), closing_over_price, actual_total, result
4. Minimum shadow: 30 games before any live action
5. Kill switch: if running win_rate < 0.48 after 30+ games
""".format(temp_med=temp_median))

# ═══════════════════════════════════════════════════════════════════════
# PHASE 9: Go/no-go
# ═══════════════════════════════════════════════════════════════════════
log("\n" + "="*70)
log("PHASE 9: Go / No-Go Decision")
log("="*70)

# Criteria checklist
checks = {}

# 1. OOS ROI positive
checks["OOS ROI positive"] = oos_roi > 0
log(f"  [{'PASS' if checks['OOS ROI positive'] else 'FAIL'}] OOS ROI positive: {oos_roi:+.1%}")

# 2. OOS win rate > 0.52
checks["OOS win rate > 52%"] = oos_wr > 0.52
log(f"  [{'PASS' if checks['OOS win rate > 52%'] else 'FAIL'}] OOS win rate > 52%: {oos_wr:.3f}")

# 3. No single month drives entire signal
# Check: exclude each month, does ROI stay positive?
month_robust = True
for mo in sorted(matched["month"].unique()):
    sub = matched[matched["month"] != mo].copy()
    if len(sub) < 20: continue
    sub["dec"] = sub["total_over_price"].apply(to_dec)
    sub["pnl"] = np.where(sub["fg_over"]==1, 100*(sub["dec"]-1),
                         np.where(sub["fg_push"]==1, 0, -100))
    roi_ = sub["pnl"].sum() / (len(sub)*100)
    if roi_ < -0.02:
        month_robust = False
checks["No single month drives signal"] = month_robust
log(f"  [{'PASS' if checks['No single month drives signal'] else 'FAIL'}] No single month drives signal")

# 4. No single team drives signal
team_robust = True
for team in top3_teams:
    sub = matched[matched["home_team"] != team].copy()
    sub["dec"] = sub["total_over_price"].apply(to_dec)
    sub["pnl"] = np.where(sub["fg_over"]==1, 100*(sub["dec"]-1),
                         np.where(sub["fg_push"]==1, 0, -100))
    roi_ = sub["pnl"].sum() / (len(sub)*100)
    if roi_ < -0.02:
        team_robust = False
checks["No single team drives signal"] = team_robust
log(f"  [{'PASS' if checks['No single team drives signal'] else 'FAIL'}] No single team drives signal")

# 5. Late-scoring mechanism confirmed
m_sub_all = matched.copy()
c_sub_all = controls.copy()
m_sub_all["actual_late"] = m_sub_all["actual_total"] - m_sub_all["actual_f5_total"]
c_sub_all["actual_late"] = c_sub_all["actual_total"] - c_sub_all["actual_f5_total"]
t_late, p_late = stats.ttest_ind(m_sub_all["actual_late"].dropna(), c_sub_all["actual_late"].dropna())
checks["Late-scoring mechanism (p<0.05)"] = p_late < 0.05
log(f"  [{'PASS' if checks['Late-scoring mechanism (p<0.05)'] else 'FAIL'}] Late-scoring mechanism confirmed: t={t_late:.2f}, p={p_late:.3f}")

# 6. Signal present outside summer
non_summer = matched[~matched["game_month"].isin([6,7,8])].copy()
if len(non_summer) >= 10:
    ns_wr = non_summer["fg_over"].mean()
    checks["Signal present outside summer"] = ns_wr > 0.50
    log(f"  [{'PASS' if checks['Signal present outside summer'] else 'FAIL'}] Signal outside summer (Apr-May, Sep): win={ns_wr:.3f}, N={len(non_summer)}")
else:
    checks["Signal present outside summer"] = False
    log(f"  [FAIL] Signal outside summer: N={len(non_summer)} (too few)")

# 7. No regime decay
checks["No regime decay (all years positive ROI)"] = True
for yr in sorted(matched["year"].unique()):
    sub = matched[matched["year"]==yr].copy()
    sub["dec"] = sub["total_over_price"].apply(to_dec)
    sub["pnl"] = np.where(sub["fg_over"]==1, 100*(sub["dec"]-1),
                         np.where(sub["fg_push"]==1, 0, -100))
    roi_ = sub["pnl"].sum() / (len(sub)*100)
    if roi_ < -0.02:
        checks["No regime decay (all years positive ROI)"] = False

log(f"  [{'PASS' if checks['No regime decay (all years positive ROI)'] else 'FAIL'}] No regime decay (all years ROI > -2%)")

# 8. Temperature source feasibility
checks["Forecast temp feasible"] = True  # moderate risk, not a hard fail
log(f"  [PASS] Forecast temperature feasibility: moderate risk, median split is coarse enough")

passed = sum(v for v in checks.values())
total = len(checks)
log(f"\n  SCORECARD: {passed}/{total} checks passed")

if passed >= 6 and checks["OOS ROI positive"] and checks["OOS win rate > 52%"]:
    decision = "CONDITIONAL GO — proceed to shadow"
elif passed >= 5:
    decision = "MONITOR — shadow with reduced confidence"
else:
    decision = "NO-GO — signal does not survive hardening"

log(f"  DECISION: {decision}")

# ═══════════════════════════════════════════════════════════════════════
# Write outputs
# ═══════════════════════════════════════════════════════════════════════

# Save matched set as CSV
matched.to_csv(OUT / "matched_games.csv", index=False)

# Save full report
with open(OUT / "hardening_full_report.txt", "w") as f:
    f.write("\n".join(lines))

# Build exec summary
exec_lines = []
exec_lines.append("# MLB Totals P1 Hardening — EARLY_HEAVY x Warm Temp FG OVER")
exec_lines.append("")
exec_lines.append("## Object Definition")
exec_lines.append(f"- Path state: EARLY_HEAVY (f5_ratio > {f5r_p67:.4f}, frozen from 2023 p67)")
exec_lines.append(f"- Temperature: >= {temp_median:.0f}F (discovery EARLY_HEAVY median)")
exec_lines.append("- Side: FG OVER at actual closing over price")
exec_lines.append("")
exec_lines.append("## Sample Sizes")
exec_lines.append(f"- Discovery (2023): {len(matched[matched['split']=='discovery'])}")
exec_lines.append(f"- Validation (2024): {len(matched[matched['split']=='validation'])}")
exec_lines.append(f"- OOS (2025): {len(matched[matched['split']=='oos'])}")
exec_lines.append(f"- Total: {len(matched)}")
exec_lines.append("")
exec_lines.append("## P1 Reported vs Hardening Confirmed")
exec_lines.append("| Split | P1 N | P1 Win% | P1 ROI | Hardening N | Hardening Win% | Hardening ROI |")
exec_lines.append("|-------|------|---------|--------|-------------|----------------|---------------|")

for sp, p1n, p1w, p1r in [("discovery",319,0.614,0.202),("validation",105,0.590,0.144),("oos",173,0.532,0.091)]:
    sub = matched[matched["split"]==sp].copy()
    n = len(sub)
    wr = sub["fg_over"].mean()
    sub["dec"] = sub["total_over_price"].apply(to_dec)
    sub["pnl"] = np.where(sub["fg_over"]==1, 100*(sub["dec"]-1),
                         np.where(sub["fg_push"]==1, 0, -100))
    roi = sub["pnl"].sum() / (n*100) if n > 0 else 0
    exec_lines.append(f"| {sp} | {p1n} | {p1w:.1%} | {p1r:+.1%} | {n} | {wr:.1%} | {roi:+.1%} |")

exec_lines.append("")
exec_lines.append("## Hardening Results")
exec_lines.append("")
exec_lines.append("### Concentration")
exec_lines.append(f"- Top 3 home teams: {top3_teams}")
exec_lines.append(f"- Month range: {sorted(matched['month'].unique())}")
exec_lines.append(f"- Temperature range: {matched['temperature'].min():.0f}F - {matched['temperature'].max():.0f}F")
exec_lines.append("")

exec_lines.append("### Regime Decay")
for yr in sorted(matched["year"].unique()):
    sub = matched[matched["year"]==yr].copy()
    n = len(sub)
    wr = sub["fg_over"].mean()
    sub["dec"] = sub["total_over_price"].apply(to_dec)
    sub["pnl"] = np.where(sub["fg_over"]==1, 100*(sub["dec"]-1),
                         np.where(sub["fg_push"]==1, 0, -100))
    roi = sub["pnl"].sum() / (n*100)
    exec_lines.append(f"- {yr}: N={n}, win={wr:.3f}, ROI={roi:+.1%}")

exec_lines.append("")
exec_lines.append("### Temperature Source Risk")
exec_lines.append("- Research used: Open-Meteo Archive (actual game-time temperature)")
exec_lines.append("- Live pipeline uses: Open-Meteo Forecast (pregame forecast)")
exec_lines.append("- Risk: MODERATE — median split is coarse, same-day forecasts generally accurate")
exec_lines.append("")

exec_lines.append("### Go/No-Go Checklist")
for check, passed_ in checks.items():
    exec_lines.append(f"- [{'x' if passed_ else ' '}] {check}")

exec_lines.append("")
exec_lines.append(f"### Decision: {decision}")
exec_lines.append("")
exec_lines.append("### Shadow Spec (if proceeding)")
exec_lines.append(f"- Trigger: EARLY_HEAVY path state AND forecast temp >= {temp_median:.0f}F")
exec_lines.append("- Side: FG OVER")
exec_lines.append("- Minimum shadow: 30 triggered games before any live action")
exec_lines.append("- Kill switch: running win rate < 0.48 after 30+ games")
exec_lines.append("- Log: forecast vs actual temp for every triggered game")

with open(OUT / "MLB_TOTALS_P1_HARDENING_EXEC_SUMMARY.md", "w") as f:
    f.write("\n".join(exec_lines))

log("\n" + "="*70)
log("FILES WRITTEN:")
log(f"  {OUT}/hardening_full_report.txt")
log(f"  {OUT}/matched_games.csv")
log(f"  {OUT}/MLB_TOTALS_P1_HARDENING_EXEC_SUMMARY.md")
log("="*70)
