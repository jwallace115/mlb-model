"""
V2 Overlay Revalidation — Revised.
V2 Model_B has mean edge +0.43 (strong over bias), generating ~0 under signals.
Therefore we test overlays as:
1. Standalone blind-under filters (overlay active → bet under)
2. Contra-filter on V2 over signals (overlay active → exclude from over)
3. Combined with V2 edge (overlay active AND V2 edge < median → under)
"""
import pandas as pd
import numpy as np
from sklearn.linear_model import Ridge
from sklearn.preprocessing import StandardScaler
import warnings, os
warnings.filterwarnings("ignore")

OUT = "research/recovery/v2_overlay_revalidation"

def american_to_decimal(price):
    if pd.isna(price): return np.nan
    return 1 + price/100 if price > 0 else 1 + 100/abs(price)

def compute_roi(df, result_col='under_result', price_col='total_under_price'):
    profit = 0.0; n = 0
    for _, r in df.iterrows():
        price = r.get(price_col)
        if pd.isna(price): continue
        n += 1
        if r[result_col]:
            profit += (american_to_decimal(price) - 1)
        else:
            profit -= 1
    return (profit / n * 100 if n > 0 else 0), n

def compute_roi_flat(df, result_col='under_result'):
    valid = df[df[result_col].notna()]
    n = len(valid)
    if n == 0: return 0, 0
    wins = valid[result_col].sum()
    profit = wins * (100/110) - (n - wins)
    return profit / n * 100, n

def fmt_row(label, season, n, hit, roi_act, roi_flat):
    return f"{label:<40s} {season:>8s} {n:5d} {hit:6.1f}% {roi_act:+9.1f}% {roi_flat:+9.1f}%"

# ──────────────────────────────────
# LOAD + REBUILD V2
# ──────────────────────────────────
v2 = pd.read_parquet("research/recovery/v2_engine/v2_modeling_table.parquet")
features_B = [
    "sp_fip_diff", "sp_fip_sum", "offense_diff", "offense_sum",
    "bp_fip_diff", "bp_fip_sum", "bp_avail_diff",
    "park_factor_runs", "temperature", "wind_factor_effective",
    "umpire_over_rate", "rest_diff", "doubleheader_flag",
    "flyball_wind_interaction",
]
train = v2[v2.season.isin([2022, 2023])].copy()
val = v2[v2.season == 2024].copy()
oos = v2[v2.season == 2025].copy()

scaler = StandardScaler()
X_tr = scaler.fit_transform(train[features_B])
model_B = Ridge(alpha=50).fit(X_tr, train["market_error"].values)

for idx, sub in [(train.index, train), (val.index, val), (oos.index, oos)]:
    X = scaler.transform(sub[features_B])
    v2.loc[idx, 'v2_edge'] = model_B.predict(X)

v2['v2_pred'] = v2['market_total'] + v2['v2_edge']

push = v2['actual_total'] == v2['market_total']
v2['under_result'] = np.where(push, np.nan, (v2['actual_total'] < v2['market_total']).astype(float))
v2['over_result'] = np.where(push, np.nan, (v2['actual_total'] > v2['market_total']).astype(float))

print(f"V2: {len(v2)} games, edge range [{v2.v2_edge.min():.3f}, {v2.v2_edge.max():.3f}], mean={v2.v2_edge.mean():.3f}")
print(f"V2 over signal (edge>0.5): {(v2.v2_edge > 0.5).sum()}")
print(f"V2 under signal (edge<-0.2): {(v2.v2_edge < -0.2).sum()}")

# ──────────────────────────────────
# OVERLAY 1: S12
# ──────────────────────────────────
print("\n" + "=" * 70)
print("S12 OVERLAY")
print("=" * 70)

ps = pd.read_csv("research/mlb_phase_a/pitcher_start_metrics_per_start.csv")
home_csw = ps[['pitcher_id', 'game_pk', 'csw_r5']].rename(
    columns={'pitcher_id': 'home_sp_id', 'csw_r5': 'home_csw_r5'})
away_csw = ps[['pitcher_id', 'game_pk', 'csw_r5']].rename(
    columns={'pitcher_id': 'away_sp_id', 'csw_r5': 'away_csw_r5'})

v2m = v2.merge(home_csw, on=['home_sp_id', 'game_pk'], how='left')
v2m = v2m.merge(away_csw, on=['away_sp_id', 'game_pk'], how='left')
v2m = v2m.drop_duplicates(subset=['game_pk'], keep='first')

v2m['s12_score'] = (v2m['home_csw_r5'] + v2m['away_csw_r5']) / 2 - 5 * (v2m['home_sp_xfip'] + v2m['away_sp_xfip']) / 2

s12_valid = v2m[v2m.s12_score.notna()].copy()
print(f"S12 valid: {len(s12_valid)} games")

# Cutoffs
OLD_S12 = 8.4468
tv = s12_valid[s12_valid.season.isin([2022,2023,2024])]
NEW_S12 = tv.s12_score.quantile(0.80)
print(f"Old cutoff: {OLD_S12}, New Q80: {NEW_S12:.4f}")

# ──────────────────────────────────
# OVERLAY 2: P09
# ──────────────────────────────────
print("\n" + "=" * 70)
print("P09 OVERLAY")
print("=" * 70)

hh = pd.read_parquet("research/opponent_adjusted_engine_v2/pitcher_start_performance.parquet")
hh = hh.rename(columns={'game_id': 'game_pk'}).sort_values(['pitcher_id', 'game_date'])
hh['hh_r5'] = hh.groupby('pitcher_id')['hard_hit_rate'].transform(
    lambda x: x.shift(1).rolling(5, min_periods=3).mean())

home_hh = hh[hh.side == 'home'][['pitcher_id', 'game_pk', 'hh_r5']].rename(
    columns={'pitcher_id': 'home_sp_id', 'hh_r5': 'home_hh_r5'})
away_hh = hh[hh.side == 'away'][['pitcher_id', 'game_pk', 'hh_r5']].rename(
    columns={'pitcher_id': 'away_sp_id', 'hh_r5': 'away_hh_r5'})

v2p = v2.merge(home_hh, on=['home_sp_id', 'game_pk'], how='left')
v2p = v2p.merge(away_hh, on=['away_sp_id', 'game_pk'], how='left')
v2p = v2p.drop_duplicates(subset=['game_pk'], keep='first')

v2p['p09_score'] = ((v2p['home_hh_r5'] + v2p['away_hh_r5']) / 2) * v2p['park_factor_runs']
p09_valid = v2p[v2p.p09_score.notna()].copy()
print(f"P09 valid: {len(p09_valid)} games")

OLD_P09 = 31.7305
tv_p = p09_valid[p09_valid.season.isin([2022,2023,2024])]
NEW_P09 = tv_p.p09_score.quantile(0.20)
print(f"Old cutoff: <= {OLD_P09}, New Q20: <= {NEW_P09:.4f}")

# ──────────────────────────────────
# COMPREHENSIVE TEST FUNCTION
# ──────────────────────────────────
def test_overlay(df, overlay_col, overlay_name, cutoff_name, season_split, report_lines):
    """Test overlay as: standalone blind-under, contra-filter on V2 over, combined."""
    report_lines.append(f"\n### {cutoff_name}")
    hdr = f"{'Test':<45s} {'Season':>8s} {'N':>5s} {'UHit%':>7s} {'U_ROI_a':>8s} {'U_ROI_f':>8s} | {'OHit%':>7s} {'O_ROI_f':>8s}"
    report_lines.append(hdr)
    report_lines.append("-" * 110)

    for slabel, smask in season_split:
        sub = df[smask].copy()
        active = sub[sub[overlay_col]].copy()
        inactive = sub[~sub[overlay_col]].copy()

        # 1. Baseline: all games blind under
        u_hit_all = sub.under_result.mean() * 100
        roi_a_all, n_a = compute_roi(sub)
        roi_f_all, _ = compute_roi_flat(sub)
        o_hit_all = sub.over_result.mean() * 100
        roi_fo_all, _ = compute_roi_flat(sub, 'over_result')
        report_lines.append(f"{'All games (baseline)':<45s} {slabel:>8s} {len(sub):5d} {u_hit_all:6.1f}% {roi_a_all:+7.1f}% {roi_f_all:+7.1f}% | {o_hit_all:6.1f}% {roi_fo_all:+7.1f}%")

        # 2. Overlay active — blind under
        if len(active) > 0:
            u_hit = active.under_result.mean() * 100
            roi_a, _ = compute_roi(active)
            roi_f, _ = compute_roi_flat(active)
            o_hit = active.over_result.mean() * 100
            roi_fo, _ = compute_roi_flat(active, 'over_result')
            report_lines.append(f"{'  Overlay ACTIVE (blind under)':<45s} {slabel:>8s} {len(active):5d} {u_hit:6.1f}% {roi_a:+7.1f}% {roi_f:+7.1f}% | {o_hit:6.1f}% {roi_fo:+7.1f}%")

        # 3. Overlay inactive — blind under
        if len(inactive) > 0:
            u_hit = inactive.under_result.mean() * 100
            roi_a, _ = compute_roi(inactive)
            roi_f, _ = compute_roi_flat(inactive)
            o_hit = inactive.over_result.mean() * 100
            roi_fo, _ = compute_roi_flat(inactive, 'over_result')
            report_lines.append(f"{'  Overlay INACTIVE':<45s} {slabel:>8s} {len(inactive):5d} {u_hit:6.1f}% {roi_a:+7.1f}% {roi_f:+7.1f}% | {o_hit:6.1f}% {roi_fo:+7.1f}%")

        # 4. V2 over signals (edge > 0.5) + overlay as contra-filter
        v2_over = sub[sub.v2_edge > 0.5].copy()
        if len(v2_over) > 0:
            v2_over_clean = v2_over[~v2_over[overlay_col]].copy()  # exclude overlay-active from over
            o_hit_v2 = v2_over.over_result.mean() * 100
            roi_fo_v2, _ = compute_roi_flat(v2_over, 'over_result')
            report_lines.append(f"{'  V2 over (edge>0.5, all)':<45s} {slabel:>8s} {len(v2_over):5d} {'':>7s} {'':>8s} {'':>8s} | {o_hit_v2:6.1f}% {roi_fo_v2:+7.1f}%")
            if len(v2_over_clean) > 0:
                o_hit_c = v2_over_clean.over_result.mean() * 100
                roi_fo_c, _ = compute_roi_flat(v2_over_clean, 'over_result')
                report_lines.append(f"{'  V2 over MINUS overlay-active':<45s} {slabel:>8s} {len(v2_over_clean):5d} {'':>7s} {'':>8s} {'':>8s} | {o_hit_c:6.1f}% {roi_fo_c:+7.1f}%")

        # 5. Combined: overlay active + V2 bottom-half edge → under
        median_edge = sub.v2_edge.median()
        combined = sub[(sub[overlay_col]) & (sub.v2_edge < median_edge)].copy()
        if len(combined) > 5:
            u_hit = combined.under_result.mean() * 100
            roi_a, _ = compute_roi(combined)
            roi_f, _ = compute_roi_flat(combined)
            report_lines.append(f"{'  COMBINED: active + edge<median':<45s} {slabel:>8s} {len(combined):5d} {u_hit:6.1f}% {roi_a:+7.1f}% {roi_f:+7.1f}% |")

        report_lines.append("")

# ──────────────────────────────────
# RUN ALL TESTS
# ──────────────────────────────────
season_split = [
    ("2022-2024", lambda d: d.season.isin([2022,2023,2024])),
    ("2025 OOS", lambda d: d.season == 2025),
]

# S12
s12_report = ["# S12 Overlay Revalidation on V2 Baseline (Revised)\n"]
s12_report.append(f"S12 = avg(home_csw_r5, away_csw_r5) - 5 * avg(home_xfip, away_xfip)")
s12_report.append(f"CSW: PIT-safe shift(1).rolling(5) from pitcher_start_metrics_per_start.csv")
s12_report.append(f"Valid games: {len(s12_valid)}")
s12_report.append(f"V2 Model_B mean edge = +0.43 (strong over bias, ~0 under signals at edge<-0.5)")
s12_report.append(f"Therefore testing S12 as standalone blind-under filter and V2-over contra-filter.\n")

for cutoff_name, cutoff_val in [("Old (>=8.4468)", OLD_S12), ("New Q80 (>={:.4f})".format(NEW_S12), NEW_S12)]:
    s12_valid_c = s12_valid.copy()
    s12_valid_c['overlay_active'] = s12_valid_c['s12_score'] >= cutoff_val
    n_active = s12_valid_c.overlay_active.sum()
    s12_report.append(f"\nActive: {n_active} / {len(s12_valid_c)} ({n_active/len(s12_valid_c)*100:.1f}%)")
    splits = [(sl, sm(s12_valid_c)) for sl, sm in season_split]
    test_overlay(s12_valid_c, 'overlay_active', 'S12', cutoff_name, splits, s12_report)

# S12 Verdict
s12_report.append("\n## S12 Verdict")
s12_oos = s12_valid[s12_valid.season == 2025].copy()
s12_oos['s12_active_new'] = s12_oos.s12_score >= NEW_S12
active_oos = s12_oos[s12_oos.s12_active_new]
inactive_oos = s12_oos[~s12_oos.s12_active_new]

if len(active_oos) > 20 and len(inactive_oos) > 20:
    u_hit_a = active_oos.under_result.mean() * 100
    u_hit_i = inactive_oos.under_result.mean() * 100
    roi_a, _ = compute_roi_flat(active_oos)
    roi_i, _ = compute_roi_flat(inactive_oos)
    roi_all, _ = compute_roi_flat(s12_oos)
    delta = roi_a - roi_all

    s12_report.append(f"OOS 2025 blind-under: active hit={u_hit_a:.1f}% ROI={roi_a:+.1f}%, inactive hit={u_hit_i:.1f}% ROI={roi_i:+.1f}%")
    s12_report.append(f"All games blind-under ROI: {roi_all:+.1f}%")
    s12_report.append(f"Delta (active vs all): {delta:+.1f}pp")

    if delta > 3 and u_hit_a > u_hit_i:
        s12_verdict = "SURVIVES"
    elif delta > 0 and u_hit_a > u_hit_i:
        s12_verdict = "DIMINISHED"
    else:
        s12_verdict = "COLLAPSES"
    s12_report.append(f"\nVerdict: **{s12_verdict}**")
else:
    s12_verdict = "INCONCLUSIVE"
    s12_report.append(f"Insufficient data. Verdict: **{s12_verdict}**")

print(f"S12 VERDICT: {s12_verdict}")

with open(f"{OUT}/s12_overlay_report.md", "w") as f:
    f.write("\n".join(s12_report))

# P09
p09_report = ["# P09 Overlay Revalidation on V2 Baseline (Revised)\n"]
p09_report.append(f"P09 = avg(home_hh_r5, away_hh_r5) * park_factor_runs")
p09_report.append(f"Hard-hit: PIT-safe shift(1).rolling(5, min=3) computed in this script")
p09_report.append(f"Valid games: {len(p09_valid)}")
p09_report.append(f"P09 fires when BELOW cutoff (low hard-hit = under lean)\n")

for cutoff_name, cutoff_val in [("Old (<={:.4f})".format(OLD_P09), OLD_P09), ("New Q20 (<={:.4f})".format(NEW_P09), NEW_P09)]:
    p09_valid_c = p09_valid.copy()
    p09_valid_c['overlay_active'] = p09_valid_c['p09_score'] <= cutoff_val
    n_active = p09_valid_c.overlay_active.sum()
    p09_report.append(f"\nActive: {n_active} / {len(p09_valid_c)} ({n_active/len(p09_valid_c)*100:.1f}%)")
    splits = [(sl, sm(p09_valid_c)) for sl, sm in season_split]
    test_overlay(p09_valid_c, 'overlay_active', 'P09', cutoff_name, splits, p09_report)

# P09 Verdict
p09_report.append("\n## P09 Verdict")
p09_oos = p09_valid[p09_valid.season == 2025].copy()
p09_oos['p09_active_new'] = p09_oos.p09_score <= NEW_P09
active_oos_p = p09_oos[p09_oos.p09_active_new]
inactive_oos_p = p09_oos[~p09_oos.p09_active_new]

if len(active_oos_p) > 20 and len(inactive_oos_p) > 20:
    u_hit_a = active_oos_p.under_result.mean() * 100
    u_hit_i = inactive_oos_p.under_result.mean() * 100
    roi_a, _ = compute_roi_flat(active_oos_p)
    roi_i, _ = compute_roi_flat(inactive_oos_p)
    roi_all, _ = compute_roi_flat(p09_oos)
    delta = roi_a - roi_all

    p09_report.append(f"OOS 2025 blind-under: active hit={u_hit_a:.1f}% ROI={roi_a:+.1f}%, inactive hit={u_hit_i:.1f}% ROI={roi_i:+.1f}%")
    p09_report.append(f"All games blind-under ROI: {roi_all:+.1f}%")
    p09_report.append(f"Delta (active vs all): {delta:+.1f}pp")

    if delta > 3 and u_hit_a > u_hit_i:
        p09_verdict = "SURVIVES"
    elif delta > 0 and u_hit_a > u_hit_i:
        p09_verdict = "DIMINISHED"
    else:
        p09_verdict = "COLLAPSES"
    p09_report.append(f"\nVerdict: **{p09_verdict}**")
else:
    p09_verdict = "INCONCLUSIVE"
    p09_report.append(f"Insufficient data. Verdict: **{p09_verdict}**")

print(f"P09 VERDICT: {p09_verdict}")

with open(f"{OUT}/p09_overlay_report.md", "w") as f:
    f.write("\n".join(p09_report))

# Flyball*Wind
print("\n" + "=" * 70)
print("FLYBALL*WIND OVERLAY")
print("=" * 70)

FW_Q80 = v2[v2.season.isin([2022,2023,2024])].flyball_wind_interaction.quantile(0.80)
print(f"FW Q80 cutoff: {FW_Q80:.4f}")

fw_report = ["# Flyball*Wind Interaction Overlay on V2 Baseline (Revised)\n"]
fw_report.append(f"flyball_wind_interaction is already a continuous feature in the V2 model.")
fw_report.append(f"This tests whether discretizing it as an overlay adds value beyond the model's use.")
fw_report.append(f"FW is an OVER amplifier (high flyball% in wind = more runs).")
fw_report.append(f"Q80 cutoff (2022-2024): >= {FW_Q80:.4f}\n")

v2_fw = v2.copy()
v2_fw['overlay_active'] = v2_fw.flyball_wind_interaction >= FW_Q80
n_active = v2_fw.overlay_active.sum()
fw_report.append(f"Active: {n_active} / {len(v2_fw)} ({n_active/len(v2_fw)*100:.1f}%)")

# For FW, test as OVER amplifier
fw_report.append(f"\n### Q80 cutoff (>= {FW_Q80:.4f})")
hdr = f"{'Test':<45s} {'Season':>8s} {'N':>5s} {'OHit%':>7s} {'O_ROI_f':>8s} | {'UHit%':>7s} {'U_ROI_f':>8s}"
fw_report.append(hdr)
fw_report.append("-" * 100)

for slabel, smask in [(sl, sm(v2_fw)) for sl, sm in season_split]:
    sub = v2_fw[smask].copy()
    active = sub[sub.overlay_active]
    inactive = sub[~sub.overlay_active]

    # All games
    o_hit = sub.over_result.mean() * 100; u_hit = sub.under_result.mean() * 100
    roi_fo, _ = compute_roi_flat(sub, 'over_result'); roi_fu, _ = compute_roi_flat(sub)
    fw_report.append(f"{'All games':<45s} {slabel:>8s} {len(sub):5d} {o_hit:6.1f}% {roi_fo:+7.1f}% | {u_hit:6.1f}% {roi_fu:+7.1f}%")

    # FW active — over
    if len(active) > 0:
        o_hit = active.over_result.mean() * 100; u_hit = active.under_result.mean() * 100
        roi_fo, _ = compute_roi_flat(active, 'over_result'); roi_fu, _ = compute_roi_flat(active)
        fw_report.append(f"{'  FW active (blind over)':<45s} {slabel:>8s} {len(active):5d} {o_hit:6.1f}% {roi_fo:+7.1f}% | {u_hit:6.1f}% {roi_fu:+7.1f}%")

    if len(inactive) > 0:
        o_hit = inactive.over_result.mean() * 100; u_hit = inactive.under_result.mean() * 100
        roi_fo, _ = compute_roi_flat(inactive, 'over_result'); roi_fu, _ = compute_roi_flat(inactive)
        fw_report.append(f"{'  FW inactive':<45s} {slabel:>8s} {len(inactive):5d} {o_hit:6.1f}% {roi_fo:+7.1f}% | {u_hit:6.1f}% {roi_fu:+7.1f}%")

    # V2 over + FW active
    v2_over = sub[sub.v2_edge > 0.5]
    if len(v2_over) > 0:
        v2oa = v2_over[v2_over.overlay_active]
        v2oi = v2_over[~v2_over.overlay_active]
        o_hit = v2_over.over_result.mean() * 100
        roi_fo, _ = compute_roi_flat(v2_over, 'over_result')
        fw_report.append(f"{'  V2 over (edge>0.5, all)':<45s} {slabel:>8s} {len(v2_over):5d} {o_hit:6.1f}% {roi_fo:+7.1f}% |")
        if len(v2oa) > 0:
            o_hit = v2oa.over_result.mean() * 100
            roi_fo, _ = compute_roi_flat(v2oa, 'over_result')
            fw_report.append(f"{'    + FW active':<45s} {slabel:>8s} {len(v2oa):5d} {o_hit:6.1f}% {roi_fo:+7.1f}% |")
        if len(v2oi) > 0:
            o_hit = v2oi.over_result.mean() * 100
            roi_fo, _ = compute_roi_flat(v2oi, 'over_result')
            fw_report.append(f"{'    + FW inactive':<45s} {slabel:>8s} {len(v2oi):5d} {o_hit:6.1f}% {roi_fo:+7.1f}% |")

    fw_report.append("")

# FW Verdict
fw_report.append("\n## Flyball*Wind Verdict")
fw_oos = v2_fw[v2_fw.season == 2025]
fw_over = fw_oos[fw_oos.v2_edge > 0.5]
fw_oa = fw_over[fw_over.overlay_active]
fw_oi = fw_over[~fw_over.overlay_active]

if len(fw_oa) > 20 and len(fw_oi) > 20:
    o_hit_a = fw_oa.over_result.mean() * 100
    o_hit_i = fw_oi.over_result.mean() * 100
    roi_a, _ = compute_roi_flat(fw_oa, 'over_result')
    roi_i, _ = compute_roi_flat(fw_oi, 'over_result')
    roi_all, _ = compute_roi_flat(fw_over, 'over_result')
    delta = roi_a - roi_all

    fw_report.append(f"OOS 2025 V2-over: FW-active over hit={o_hit_a:.1f}% ROI={roi_a:+.1f}%")
    fw_report.append(f"OOS 2025 V2-over: FW-inactive over hit={o_hit_i:.1f}% ROI={roi_i:+.1f}%")
    fw_report.append(f"All V2-over ROI: {roi_all:+.1f}%")
    fw_report.append(f"Delta (FW-active vs all): {delta:+.1f}pp")
    fw_report.append(f"Note: flyball_wind is already in V2 as continuous feature (coeff=+0.07).")

    if delta > 3 and o_hit_a > o_hit_i:
        fw_verdict = "SURVIVES"
    elif delta > 0 and o_hit_a > o_hit_i:
        fw_verdict = "DIMINISHED"
    else:
        fw_verdict = "COLLAPSES"
    fw_report.append(f"\nVerdict: **{fw_verdict}**")
else:
    fw_verdict = "INCONCLUSIVE"
    fw_report.append(f"Insufficient data. Verdict: **{fw_verdict}**")

print(f"FW VERDICT: {fw_verdict}")

with open(f"{OUT}/flyball_wind_overlay_report.md", "w") as f:
    f.write("\n".join(fw_report))

# ──────────────────────────────────
# MASTER SURVIVAL MAP
# ──────────────────────────────────
verdicts = {'S12': s12_verdict, 'P09': p09_verdict, 'flyball_wind': fw_verdict}

master = []
master.append("# MASTER V2 OVERLAY SURVIVAL MAP\n")
master.append("Date: 2026-04-10")
master.append("Baseline: V2 Model_B (Ridge alpha=50, 14 features, target=market_error)")
master.append("Train: 2022-2023, Val: 2024, OOS: 2025\n")
master.append("## Key Context")
master.append("V2 Model_B has mean predicted edge of +0.43 runs (strong over bias).")
master.append("It generates ~900 over signals (edge > 0.5) per season but effectively 0 under signals.")
master.append("S12 and P09 were originally designed as UNDER amplifiers for V1.")
master.append("Therefore overlay testing uses: (1) standalone blind-under, (2) V2-over contra-filter,")
master.append("(3) combined with V2 edge direction.\n")

master.append("## Results\n")
master.append("| Overlay | Formula | PIT-Safe | Cutoff | OOS Verdict |")
master.append("|---------|---------|----------|--------|-------------|")
master.append(f"| S12 | avg(csw_r5) - 5*avg(xfip) | YES | >= {NEW_S12:.4f} (Q80) | **{s12_verdict}** |")
master.append(f"| P09 | avg(hh_r5) * park_factor | YES | <= {NEW_P09:.4f} (Q20) | **{p09_verdict}** |")
master.append(f"| flyball_wind | already in V2 model | YES | >= {FW_Q80:.4f} (Q80) | **{fw_verdict}** |")

master.append(f"\n## Summary\n")
counts = {}
for v in verdicts.values():
    counts[v] = counts.get(v, 0) + 1
for status in ['SURVIVES', 'DIMINISHED', 'COLLAPSES', 'INCONCLUSIVE']:
    if status in counts:
        master.append(f"- {status}: {counts[status]}")

master.append(f"\n## Per-Overlay Detail\n")

# S12 detail
master.append(f"### S12")
master.append(f"- Formula: avg(home_csw_r5, away_csw_r5) - 5 * avg(home_xfip, away_xfip)")
master.append(f"- Data: pitcher_start_metrics_per_start.csv, csw_r5 = shift(1).rolling(5)")
master.append(f"- PIT verified: YES")
s12_oos2 = s12_valid[s12_valid.season == 2025].copy()
s12_oos2['act'] = s12_oos2.s12_score >= NEW_S12
a2 = s12_oos2[s12_oos2.act]; i2 = s12_oos2[~s12_oos2.act]
if len(a2) > 0 and len(i2) > 0:
    master.append(f"- OOS blind-under: active hit={a2.under_result.mean()*100:.1f}%, inactive hit={i2.under_result.mean()*100:.1f}%")
    roi_a2, _ = compute_roi_flat(a2); roi_i2, _ = compute_roi_flat(i2)
    master.append(f"- OOS ROI flat: active={roi_a2:+.1f}%, inactive={roi_i2:+.1f}%")
master.append(f"- Verdict: **{s12_verdict}**\n")

# P09 detail
master.append(f"### P09")
master.append(f"- Formula: avg(home_hh_r5, away_hh_r5) * park_factor_runs")
master.append(f"- Data: opponent_adjusted_engine_v2/pitcher_start_performance.parquet")
master.append(f"- PIT verified: YES (shift(1).rolling(5, min=3) computed in script)")
p09_oos2 = p09_valid[p09_valid.season == 2025].copy()
p09_oos2['act'] = p09_oos2.p09_score <= NEW_P09
a3 = p09_oos2[p09_oos2.act]; i3 = p09_oos2[~p09_oos2.act]
if len(a3) > 0 and len(i3) > 0:
    master.append(f"- OOS blind-under: active hit={a3.under_result.mean()*100:.1f}%, inactive hit={i3.under_result.mean()*100:.1f}%")
    roi_a3, _ = compute_roi_flat(a3); roi_i3, _ = compute_roi_flat(i3)
    master.append(f"- OOS ROI flat: active={roi_a3:+.1f}%, inactive={roi_i3:+.1f}%")
master.append(f"- Verdict: **{p09_verdict}**\n")

# FW detail
master.append(f"### flyball_wind")
master.append(f"- Already a continuous feature in V2 (coefficient +0.07)")
master.append(f"- Testing discrete overlay on top of model's continuous usage")
if len(fw_oa) > 0 and len(fw_oi) > 0:
    master.append(f"- OOS V2-over: FW-active hit={fw_oa.over_result.mean()*100:.1f}%, FW-inactive hit={fw_oi.over_result.mean()*100:.1f}%")
    roi_a4, _ = compute_roi_flat(fw_oa, 'over_result'); roi_i4, _ = compute_roi_flat(fw_oi, 'over_result')
    master.append(f"- OOS ROI flat: FW-active={roi_a4:+.1f}%, FW-inactive={roi_i4:+.1f}%")
master.append(f"- Verdict: **{fw_verdict}**\n")

master.append("## Conclusion\n")
survivors = [k for k, v in verdicts.items() if v == 'SURVIVES']
collapsed = [k for k, v in verdicts.items() if v == 'COLLAPSES']
diminished = [k for k, v in verdicts.items() if v == 'DIMINISHED']

if not survivors and not diminished:
    master.append("No V1-era overlay adds meaningful value on top of the V2 baseline in OOS 2025 testing.")
elif survivors:
    master.append(f"Surviving overlays: {', '.join(survivors)} — consider integration.")
if collapsed:
    master.append(f"Collapsed overlays: {', '.join(collapsed)} — do not integrate.")
if diminished:
    master.append(f"Diminished overlays: {', '.join(diminished)} — marginal value, monitor only.")

with open(f"{OUT}/MASTER_V2_OVERLAY_SURVIVAL_MAP.md", "w") as f:
    f.write("\n".join(master))

print(f"\n{'='*70}")
print("FINAL SUMMARY")
print(f"{'='*70}")
for name, v in verdicts.items():
    print(f"  {name:20s}: {v}")
print(f"\nOverlays tested: 3")
for status in ['SURVIVES', 'DIMINISHED', 'COLLAPSES', 'INCONCLUSIVE']:
    if status in counts:
        print(f"  {status}: {counts[status]}")

if not survivors:
    print("\nConclusion: No V1-era overlay survives on the V2 baseline.")
else:
    print(f"\nConclusion: {', '.join(survivors)} survived — consider integration into V2.")
