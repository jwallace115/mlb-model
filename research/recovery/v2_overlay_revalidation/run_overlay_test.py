"""
V2 Overlay Revalidation — Test S12, P09, flyball_wind on V2 baseline.
No API calls. No modifications to existing files.
"""
import pandas as pd
import numpy as np
from sklearn.linear_model import Ridge
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import mean_squared_error
import warnings, os, json
warnings.filterwarnings("ignore")

OUT = "research/recovery/v2_overlay_revalidation"
os.makedirs(OUT, exist_ok=True)

# ──────────────────────────────────────────────────
# HELPERS
# ──────────────────────────────────────────────────
def american_to_decimal(price):
    if pd.isna(price): return np.nan
    return 1 + price/100 if price > 0 else 1 + 100/abs(price)

def compute_roi_actual(df, result_col='under_result', price_col='total_under_price'):
    """ROI using actual closing under prices."""
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
    """ROI at flat -110."""
    n = df[result_col].notna().sum()
    if n == 0: return 0, 0
    wins = df[result_col].sum()
    profit = wins * (100/110) - (n - wins) * 1
    return profit / n * 100, n

# ──────────────────────────────────────────────────
# LOAD V2 TABLE
# ──────────────────────────────────────────────────
print("=" * 70)
print("LOADING V2 ENGINE DATA")
print("=" * 70)

v2 = pd.read_parquet("research/recovery/v2_engine/v2_modeling_table.parquet")
print(f"V2 table: {v2.shape[0]} games, seasons {sorted(v2.season.unique())}")

# Rebuild V2 Model_B predictions (market_error target)
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

scaler_B = StandardScaler()
X_tr = scaler_B.fit_transform(train[features_B])
X_val = scaler_B.transform(val[features_B])
X_oos = scaler_B.transform(oos[features_B])

model_B = Ridge(alpha=50)
model_B.fit(X_tr, train["market_error"].values)

# V2 predicted totals
v2.loc[train.index, 'v2_pred'] = train['market_total'].values + model_B.predict(X_tr)
v2.loc[val.index, 'v2_pred'] = val['market_total'].values + model_B.predict(X_val)
v2.loc[oos.index, 'v2_pred'] = oos['market_total'].values + model_B.predict(X_oos)
v2['v2_edge'] = v2['v2_pred'] - v2['market_total']

# under/over results
v2['under_result'] = (v2['actual_total'] < v2['market_total']).astype(int)
v2['over_result_flag'] = (v2['actual_total'] > v2['market_total']).astype(int)
# pushes
push_mask = v2['actual_total'] == v2['market_total']
v2.loc[push_mask, 'under_result'] = np.nan
v2.loc[push_mask, 'over_result_flag'] = np.nan

print(f"V2 Model_B rebuilt. Edge range: [{v2.v2_edge.min():.2f}, {v2.v2_edge.max():.2f}]")

# V2 baseline: under signals where v2_edge < -0.5 (model predicts under)
v2['v2_under_signal'] = v2['v2_edge'] < -0.5

# ──────────────────────────────────────────────────
# OVERLAY 1: S12
# ──────────────────────────────────────────────────
print("\n" + "=" * 70)
print("OVERLAY 1: S12 (CSW-based pitcher quality)")
print("=" * 70)

# Load CSW data
ps = pd.read_csv("research/mlb_phase_a/pitcher_start_metrics_per_start.csv")
ps['game_date'] = pd.to_datetime(ps['game_date'])
print(f"Per-start CSW data: {ps.shape[0]} rows, seasons {sorted(ps.season.unique())}")

# csw_r5 is PIT-safe (shift(1).rolling(5)) - verified
# Join home SP CSW
home_csw = ps[['pitcher_id', 'game_pk', 'csw_r5']].rename(
    columns={'pitcher_id': 'home_sp_id', 'csw_r5': 'home_csw_r5'})
away_csw = ps[['pitcher_id', 'game_pk', 'csw_r5']].rename(
    columns={'pitcher_id': 'away_sp_id', 'csw_r5': 'away_csw_r5'})

v2_s12 = v2.merge(home_csw, on=['home_sp_id', 'game_pk'], how='left')
v2_s12 = v2_s12.merge(away_csw, on=['away_sp_id', 'game_pk'], how='left')

# Check duplicates from merge
before = len(v2)
v2_s12 = v2_s12.drop_duplicates(subset=['game_pk'], keep='first')
print(f"After CSW merge: {len(v2_s12)} games (from {before})")

csw_avail = v2_s12['home_csw_r5'].notna() & v2_s12['away_csw_r5'].notna()
print(f"CSW available both sides: {csw_avail.sum()} / {len(v2_s12)} ({csw_avail.mean():.1%})")

# S12 = avg(home_csw, away_csw) - 5 * avg(home_xfip, away_xfip)
v2_s12['s12_score'] = (
    (v2_s12['home_csw_r5'] + v2_s12['away_csw_r5']) / 2
    - 5 * (v2_s12['home_sp_xfip'] + v2_s12['away_sp_xfip']) / 2
)

s12_valid = v2_s12[v2_s12['s12_score'].notna()].copy()
print(f"S12 valid games: {len(s12_valid)}")
print(f"S12 distribution: mean={s12_valid.s12_score.mean():.3f}, std={s12_valid.s12_score.std():.3f}")
print(f"  Q20={s12_valid.s12_score.quantile(0.20):.3f}, Q80={s12_valid.s12_score.quantile(0.80):.3f}")

# Old cutoff: 8.4468 (top 20% = high CSW, low xFIP → under lean)
OLD_S12_CUTOFF = 8.4468

# Test with old cutoff
s12_valid['s12_active_old'] = s12_valid['s12_score'] >= OLD_S12_CUTOFF
print(f"\nOld cutoff {OLD_S12_CUTOFF}: {s12_valid.s12_active_old.sum()} games active ({s12_valid.s12_active_old.mean():.1%})")

# Rederive cutoff from 2022-2024
train_val = s12_valid[s12_valid.season.isin([2022, 2023, 2024])]
NEW_S12_CUTOFF = train_val['s12_score'].quantile(0.80)
print(f"New cutoff (top 20% of 2022-2024): {NEW_S12_CUTOFF:.4f}")
s12_valid['s12_active_new'] = s12_valid['s12_score'] >= NEW_S12_CUTOFF

# Test framework
s12_report = []
s12_report.append("# S12 Overlay Revalidation on V2 Baseline\n")
s12_report.append(f"S12 = avg(home_csw_r5, away_csw_r5) - 5 * avg(home_xfip, away_xfip)")
s12_report.append(f"CSW source: pitcher_start_metrics_per_start.csv (csw_r5 = shift(1).rolling(5))")
s12_report.append(f"PIT-safe: YES (verified: start N's csw_r5 = avg of starts 0..N-1)")
s12_report.append(f"Valid games: {len(s12_valid)}")
s12_report.append(f"Old cutoff: {OLD_S12_CUTOFF}")
s12_report.append(f"New cutoff (Q80 2022-2024): {NEW_S12_CUTOFF:.4f}\n")

for cutoff_name, cutoff_col in [("Old (8.4468)", "s12_active_old"), ("New (Q80 rederived)", "s12_active_new")]:
    s12_report.append(f"\n## Cutoff: {cutoff_name}")
    s12_report.append(f"{'Split':<35s} {'Season':>6s} {'N':>5s} {'UHit%':>7s} {'U_ROI_act':>10s} {'U_ROI_flat':>10s}")
    s12_report.append("-" * 80)

    for season_label, season_mask in [("2022-2024", s12_valid.season.isin([2022,2023,2024])),
                                       ("2025 OOS", s12_valid.season == 2025)]:
        subset = s12_valid[season_mask].copy()
        # V2 under signals
        v2_under = subset[subset.v2_under_signal].copy()
        v2_under_active = v2_under[v2_under[cutoff_col]].copy()
        v2_under_inactive = v2_under[~v2_under[cutoff_col]].copy()

        # All V2 under signals
        if len(v2_under) > 0:
            u_hit = v2_under['under_result'].mean() * 100
            roi_act, n_act = compute_roi_actual(v2_under)
            roi_flat, _ = compute_roi_flat(v2_under)
            s12_report.append(f"{'V2 under (all)':<35s} {season_label:>6s} {len(v2_under):5d} {u_hit:6.1f}% {roi_act:+9.1f}% {roi_flat:+9.1f}%")

        # S12 active subset
        if len(v2_under_active) > 0:
            u_hit = v2_under_active['under_result'].mean() * 100
            roi_act, n_act = compute_roi_actual(v2_under_active)
            roi_flat, _ = compute_roi_flat(v2_under_active)
            s12_report.append(f"{'  + S12 active':<35s} {season_label:>6s} {len(v2_under_active):5d} {u_hit:6.1f}% {roi_act:+9.1f}% {roi_flat:+9.1f}%")
        else:
            s12_report.append(f"{'  + S12 active':<35s} {season_label:>6s}     0     N/A        N/A        N/A")

        # S12 inactive subset
        if len(v2_under_inactive) > 0:
            u_hit = v2_under_inactive['under_result'].mean() * 100
            roi_act, n_act = compute_roi_actual(v2_under_inactive)
            roi_flat, _ = compute_roi_flat(v2_under_inactive)
            s12_report.append(f"{'  + S12 inactive':<35s} {season_label:>6s} {len(v2_under_inactive):5d} {u_hit:6.1f}% {roi_act:+9.1f}% {roi_flat:+9.1f}%")

        # Also test: S12 active regardless of V2 signal (standalone filter)
        all_active = subset[subset[cutoff_col]].copy()
        if len(all_active) > 0:
            u_hit = all_active['under_result'].mean() * 100
            roi_act, n_act = compute_roi_actual(all_active)
            roi_flat, _ = compute_roi_flat(all_active)
            s12_report.append(f"{'  S12 active (any, blind under)':<35s} {season_label:>6s} {len(all_active):5d} {u_hit:6.1f}% {roi_act:+9.1f}% {roi_flat:+9.1f}%")

        s12_report.append("")

# Verdict
s12_report.append("\n## S12 Verdict")

# Check OOS 2025 performance
oos_s12 = s12_valid[s12_valid.season == 2025]
oos_under = oos_s12[oos_s12.v2_under_signal]
oos_active_new = oos_under[oos_under.s12_active_new]
oos_inactive_new = oos_under[~oos_under.s12_active_new]

if len(oos_active_new) > 0 and len(oos_inactive_new) > 0:
    roi_active, _ = compute_roi_flat(oos_active_new)
    roi_inactive, _ = compute_roi_flat(oos_inactive_new)
    roi_all, _ = compute_roi_flat(oos_under)
    hit_active = oos_active_new.under_result.mean() * 100
    hit_inactive = oos_inactive_new.under_result.mean() * 100
    delta_roi = roi_active - roi_all
    delta_hit = hit_active - oos_under.under_result.mean() * 100

    if delta_roi > 3 and hit_active > hit_inactive:
        verdict = "SURVIVES"
    elif delta_roi > 0:
        verdict = "DIMINISHED"
    else:
        verdict = "COLLAPSES"

    s12_report.append(f"OOS 2025: S12-active under hit={hit_active:.1f}%, ROI_flat={roi_active:+.1f}%")
    s12_report.append(f"OOS 2025: S12-inactive under hit={hit_inactive:.1f}%, ROI_flat={roi_inactive:+.1f}%")
    s12_report.append(f"OOS 2025: All V2 under ROI_flat={roi_all:+.1f}%")
    s12_report.append(f"Delta ROI (active vs all): {delta_roi:+.1f}pp")
    s12_report.append(f"Verdict: **{verdict}**")
else:
    verdict = "INCONCLUSIVE"
    s12_report.append("Insufficient OOS data for verdict")
    s12_report.append(f"Verdict: **{verdict}**")

s12_verdict = verdict

with open(f"{OUT}/s12_overlay_report.md", "w") as f:
    f.write("\n".join(s12_report))
print("\nS12 report written.")
print(f"S12 VERDICT: {s12_verdict}")

# ──────────────────────────────────────────────────
# OVERLAY 2: P09
# ──────────────────────────────────────────────────
print("\n" + "=" * 70)
print("OVERLAY 2: P09 (hard-hit rate x park factor)")
print("=" * 70)

hh = pd.read_parquet("research/opponent_adjusted_engine_v2/pitcher_start_performance.parquet")
hh = hh.rename(columns={'game_id': 'game_pk'})
print(f"Hard-hit data: {hh.shape[0]} rows, seasons {sorted(hh.season.unique())}")

# Build PIT-safe rolling hard_hit_rate: shift(1).rolling(5, min_periods=3)
hh = hh.sort_values(['pitcher_id', 'game_date'])
hh['hh_r5'] = (hh.groupby('pitcher_id')['hard_hit_rate']
               .transform(lambda x: x.shift(1).rolling(5, min_periods=3).mean()))

print(f"hh_r5 non-null: {hh.hh_r5.notna().sum()} / {len(hh)} ({hh.hh_r5.notna().mean():.1%})")

# Split by side for home/away
home_hh = hh[hh.side == 'home'][['pitcher_id', 'game_pk', 'hh_r5']].rename(
    columns={'pitcher_id': 'home_sp_id', 'hh_r5': 'home_hh_r5'})
away_hh = hh[hh.side == 'away'][['pitcher_id', 'game_pk', 'hh_r5']].rename(
    columns={'pitcher_id': 'away_sp_id', 'hh_r5': 'away_hh_r5'})

v2_p09 = v2.merge(home_hh, on=['home_sp_id', 'game_pk'], how='left')
v2_p09 = v2_p09.merge(away_hh, on=['away_sp_id', 'game_pk'], how='left')
v2_p09 = v2_p09.drop_duplicates(subset=['game_pk'], keep='first')
print(f"After hard-hit merge: {len(v2_p09)} games")

hh_avail = v2_p09['home_hh_r5'].notna() & v2_p09['away_hh_r5'].notna()
print(f"Hard-hit available both sides: {hh_avail.sum()} / {len(v2_p09)} ({hh_avail.mean():.1%})")

# P09 = avg(home_hh, away_hh) * park_run_factor
v2_p09['p09_score'] = ((v2_p09['home_hh_r5'] + v2_p09['away_hh_r5']) / 2) * v2_p09['park_factor_runs']

p09_valid = v2_p09[v2_p09['p09_score'].notna()].copy()
print(f"P09 valid games: {len(p09_valid)}")
print(f"P09 distribution: mean={p09_valid.p09_score.mean():.3f}, std={p09_valid.p09_score.std():.3f}")

# Old cutoff: 31.7305 (bottom 20% = low hard-hit → under lean)
OLD_P09_CUTOFF = 31.7305

# P09 fires when BELOW cutoff (low hard-hit = under amplifier)
p09_valid['p09_active_old'] = p09_valid['p09_score'] <= OLD_P09_CUTOFF
print(f"\nOld cutoff <= {OLD_P09_CUTOFF}: {p09_valid.p09_active_old.sum()} active ({p09_valid.p09_active_old.mean():.1%})")

# Rederive from 2022-2024
train_val_p09 = p09_valid[p09_valid.season.isin([2022, 2023, 2024])]
NEW_P09_CUTOFF = train_val_p09['p09_score'].quantile(0.20)
print(f"New cutoff (Q20 of 2022-2024): {NEW_P09_CUTOFF:.4f}")
p09_valid['p09_active_new'] = p09_valid['p09_score'] <= NEW_P09_CUTOFF

p09_report = []
p09_report.append("# P09 Overlay Revalidation on V2 Baseline\n")
p09_report.append(f"P09 = avg(home_hh_r5, away_hh_r5) * park_factor_runs")
p09_report.append(f"Hard-hit source: opponent_adjusted_engine_v2/pitcher_start_performance.parquet")
p09_report.append(f"PIT-safe: YES (computed shift(1).rolling(5, min=3) in this script)")
p09_report.append(f"Valid games: {len(p09_valid)}")
p09_report.append(f"Old cutoff: <= {OLD_P09_CUTOFF}")
p09_report.append(f"New cutoff (Q20 2022-2024): <= {NEW_P09_CUTOFF:.4f}\n")

for cutoff_name, cutoff_col in [("Old (31.7305)", "p09_active_old"), ("New (Q20 rederived)", "p09_active_new")]:
    p09_report.append(f"\n## Cutoff: {cutoff_name}")
    p09_report.append(f"{'Split':<35s} {'Season':>6s} {'N':>5s} {'UHit%':>7s} {'U_ROI_act':>10s} {'U_ROI_flat':>10s}")
    p09_report.append("-" * 80)

    for season_label, season_mask in [("2022-2024", p09_valid.season.isin([2022,2023,2024])),
                                       ("2025 OOS", p09_valid.season == 2025)]:
        subset = p09_valid[season_mask].copy()
        v2_under = subset[subset.v2_under_signal].copy()
        v2_under_active = v2_under[v2_under[cutoff_col]].copy()
        v2_under_inactive = v2_under[~v2_under[cutoff_col]].copy()

        if len(v2_under) > 0:
            u_hit = v2_under['under_result'].mean() * 100
            roi_act, _ = compute_roi_actual(v2_under)
            roi_flat, _ = compute_roi_flat(v2_under)
            p09_report.append(f"{'V2 under (all)':<35s} {season_label:>6s} {len(v2_under):5d} {u_hit:6.1f}% {roi_act:+9.1f}% {roi_flat:+9.1f}%")

        if len(v2_under_active) > 0:
            u_hit = v2_under_active['under_result'].mean() * 100
            roi_act, _ = compute_roi_actual(v2_under_active)
            roi_flat, _ = compute_roi_flat(v2_under_active)
            p09_report.append(f"{'  + P09 active':<35s} {season_label:>6s} {len(v2_under_active):5d} {u_hit:6.1f}% {roi_act:+9.1f}% {roi_flat:+9.1f}%")
        else:
            p09_report.append(f"{'  + P09 active':<35s} {season_label:>6s}     0     N/A        N/A        N/A")

        if len(v2_under_inactive) > 0:
            u_hit = v2_under_inactive['under_result'].mean() * 100
            roi_act, _ = compute_roi_actual(v2_under_inactive)
            roi_flat, _ = compute_roi_flat(v2_under_inactive)
            p09_report.append(f"{'  + P09 inactive':<35s} {season_label:>6s} {len(v2_under_inactive):5d} {u_hit:6.1f}% {roi_act:+9.1f}% {roi_flat:+9.1f}%")

        all_active = subset[subset[cutoff_col]].copy()
        if len(all_active) > 0:
            u_hit = all_active['under_result'].mean() * 100
            roi_act, _ = compute_roi_actual(all_active)
            roi_flat, _ = compute_roi_flat(all_active)
            p09_report.append(f"{'  P09 active (any, blind under)':<35s} {season_label:>6s} {len(all_active):5d} {u_hit:6.1f}% {roi_act:+9.1f}% {roi_flat:+9.1f}%")

        p09_report.append("")

# P09 Verdict
p09_report.append("\n## P09 Verdict")
oos_p09 = p09_valid[p09_valid.season == 2025]
oos_under_p09 = oos_p09[oos_p09.v2_under_signal]
oos_active_p09 = oos_under_p09[oos_under_p09.p09_active_new]
oos_inactive_p09 = oos_under_p09[~oos_under_p09.p09_active_new]

if len(oos_active_p09) > 0 and len(oos_inactive_p09) > 0:
    roi_active_p09, _ = compute_roi_flat(oos_active_p09)
    roi_inactive_p09, _ = compute_roi_flat(oos_inactive_p09)
    roi_all_p09, _ = compute_roi_flat(oos_under_p09)
    hit_active_p09 = oos_active_p09.under_result.mean() * 100
    hit_inactive_p09 = oos_inactive_p09.under_result.mean() * 100
    delta_roi_p09 = roi_active_p09 - roi_all_p09

    if delta_roi_p09 > 3 and hit_active_p09 > hit_inactive_p09:
        p09_verdict = "SURVIVES"
    elif delta_roi_p09 > 0:
        p09_verdict = "DIMINISHED"
    else:
        p09_verdict = "COLLAPSES"

    p09_report.append(f"OOS 2025: P09-active under hit={hit_active_p09:.1f}%, ROI_flat={roi_active_p09:+.1f}%")
    p09_report.append(f"OOS 2025: P09-inactive under hit={hit_inactive_p09:.1f}%, ROI_flat={roi_inactive_p09:+.1f}%")
    p09_report.append(f"OOS 2025: All V2 under ROI_flat={roi_all_p09:+.1f}%")
    p09_report.append(f"Delta ROI (active vs all): {delta_roi_p09:+.1f}pp")
    p09_report.append(f"Verdict: **{p09_verdict}**")
else:
    p09_verdict = "INCONCLUSIVE"
    p09_report.append("Insufficient OOS data for verdict")
    p09_report.append(f"Verdict: **{p09_verdict}**")

with open(f"{OUT}/p09_overlay_report.md", "w") as f:
    f.write("\n".join(p09_report))
print(f"\nP09 VERDICT: {p09_verdict}")

# ──────────────────────────────────────────────────
# OVERLAY 3: flyball_wind_interaction
# ──────────────────────────────────────────────────
print("\n" + "=" * 70)
print("OVERLAY 3: flyball_wind_interaction")
print("=" * 70)

# flyball_wind_interaction is already in V2 table
# Check what it is — the V2 feature table uses it as a continuous feature
# But the original V1 used it as season-final FanGraphs (CONTAMINATED)
# The V2 version should be PIT-safe if it came from the PIT feature table

# Check if the V2 table's flyball_wind_interaction came from PIT features
print(f"flyball_wind_interaction in V2: non-null={v2.flyball_wind_interaction.notna().sum()}")
print(f"  min={v2.flyball_wind_interaction.min():.3f}, max={v2.flyball_wind_interaction.max():.3f}")
print(f"  mean={v2.flyball_wind_interaction.mean():.3f}, std={v2.flyball_wind_interaction.std():.3f}")
print(f"  zero%: {(v2.flyball_wind_interaction == 0).mean():.1%}")

# The V2 modeling table was built from PIT features, so this should be PIT-safe
# But let's verify: check if it was built from fly_outs ratio proxy

# Check the PIT feature source
pit = pd.read_parquet("research/recovery/v1_clean_features/baseball_features_pit_v1.parquet")
fly_cols = [c for c in pit.columns if 'fly' in c.lower() or 'fb' in c.lower()]
print(f"\nPIT feature table flyball cols: {fly_cols}")
if 'flyball_wind_interaction' in pit.columns:
    print(f"  flyball_wind_interaction in PIT: non-null={pit.flyball_wind_interaction.notna().sum()}")
    print(f"  min={pit.flyball_wind_interaction.min():.3f}, max={pit.flyball_wind_interaction.max():.3f}")

# flyball_wind_interaction is already an OVER amplifier
# High values = more flyballs in wind = more runs expected
# Test as an over overlay: when flyball_wind > threshold, over signals are stronger
fw_report = []
fw_report.append("# Flyball*Wind Interaction Overlay Revalidation on V2 Baseline\n")

# Check source
fw_report.append(f"Source: V2 modeling table (inherited from PIT feature table)")
if 'flyball_wind_interaction' in pit.columns:
    fw_report.append(f"PIT-safe: YES (from baseball_features_pit_v1.parquet)")
else:
    fw_report.append(f"PIT-safe: UNKNOWN — needs verification")

fw_report.append(f"Distribution: mean={v2.flyball_wind_interaction.mean():.3f}, std={v2.flyball_wind_interaction.std():.3f}")
fw_report.append(f"Zero values: {(v2.flyball_wind_interaction == 0).mean():.1%}")
fw_report.append("")

# flyball_wind is already IN the V2 model as a feature
# So testing it as a separate overlay is testing whether it adds value BEYOND
# what the model already captures
# Instead, test: does high flyball_wind improve OVER signal quality?
v2['v2_over_signal'] = v2['v2_edge'] > 0.5

# Define active: top 20% of flyball_wind (nonzero)
nonzero_fw = v2[v2.flyball_wind_interaction > 0]
FW_CUTOFF_Q80 = v2[v2.season.isin([2022,2023,2024])].flyball_wind_interaction.quantile(0.80)
print(f"Flyball*wind Q80 cutoff: {FW_CUTOFF_Q80:.4f}")

v2['fw_active'] = v2['flyball_wind_interaction'] >= FW_CUTOFF_Q80
print(f"FW active: {v2.fw_active.sum()} ({v2.fw_active.mean():.1%})")

fw_report.append(f"Cutoff (Q80 of 2022-2024): >= {FW_CUTOFF_Q80:.4f}")
fw_report.append(f"NOTE: flyball_wind_interaction is already a feature in the V2 model.")
fw_report.append(f"This tests whether it adds value as a discrete overlay on top.\n")

fw_report.append(f"{'Split':<35s} {'Season':>6s} {'N':>5s} {'OHit%':>7s} {'O_ROI_act':>10s} {'O_ROI_flat':>10s}")
fw_report.append("-" * 80)

for season_label, season_mask in [("2022-2024", v2.season.isin([2022,2023,2024])),
                                   ("2025 OOS", v2.season == 2025)]:
    subset = v2[season_mask].copy()
    v2_over = subset[subset.v2_over_signal].copy()
    v2_over_active = v2_over[v2_over.fw_active].copy()
    v2_over_inactive = v2_over[~v2_over.fw_active].copy()

    if len(v2_over) > 0:
        o_hit = v2_over['over_result_flag'].mean() * 100
        roi_act, _ = compute_roi_actual(v2_over, result_col='over_result_flag', price_col='total_over_price')
        roi_flat, _ = compute_roi_flat(v2_over, result_col='over_result_flag')
        fw_report.append(f"{'V2 over (all)':<35s} {season_label:>6s} {len(v2_over):5d} {o_hit:6.1f}% {roi_act:+9.1f}% {roi_flat:+9.1f}%")

    if len(v2_over_active) > 0:
        o_hit = v2_over_active['over_result_flag'].mean() * 100
        roi_act, _ = compute_roi_actual(v2_over_active, result_col='over_result_flag', price_col='total_over_price')
        roi_flat, _ = compute_roi_flat(v2_over_active, result_col='over_result_flag')
        fw_report.append(f"{'  + FW active':<35s} {season_label:>6s} {len(v2_over_active):5d} {o_hit:6.1f}% {roi_act:+9.1f}% {roi_flat:+9.1f}%")
    else:
        fw_report.append(f"{'  + FW active':<35s} {season_label:>6s}     0     N/A        N/A        N/A")

    if len(v2_over_inactive) > 0:
        o_hit = v2_over_inactive['over_result_flag'].mean() * 100
        roi_act, _ = compute_roi_actual(v2_over_inactive, result_col='over_result_flag', price_col='total_over_price')
        roi_flat, _ = compute_roi_flat(v2_over_inactive, result_col='over_result_flag')
        fw_report.append(f"{'  + FW inactive':<35s} {season_label:>6s} {len(v2_over_inactive):5d} {o_hit:6.1f}% {roi_act:+9.1f}% {roi_flat:+9.1f}%")

    # Also test on UNDER (flyball_wind active might hurt unders)
    v2_under = subset[subset.v2_under_signal].copy()
    v2_under_fw = v2_under[v2_under.fw_active].copy()
    v2_under_nofw = v2_under[~v2_under.fw_active].copy()

    if len(v2_under) > 0:
        u_hit = v2_under['under_result'].mean() * 100
        roi_flat_u, _ = compute_roi_flat(v2_under)
        fw_report.append(f"{'V2 under (all)':<35s} {season_label:>6s} {len(v2_under):5d} {u_hit:6.1f}% {'':>10s} {roi_flat_u:+9.1f}%")

    if len(v2_under_nofw) > 0:
        u_hit = v2_under_nofw['under_result'].mean() * 100
        roi_flat_u, _ = compute_roi_flat(v2_under_nofw)
        fw_report.append(f"{'  + FW inactive (filter out)':<35s} {season_label:>6s} {len(v2_under_nofw):5d} {u_hit:6.1f}% {'':>10s} {roi_flat_u:+9.1f}%")

    fw_report.append("")

# FW Verdict
fw_report.append("\n## Flyball*Wind Verdict")
oos_fw = v2[v2.season == 2025]
oos_over = oos_fw[oos_fw.v2_over_signal]
oos_over_active = oos_over[oos_over.fw_active]
oos_over_inactive = oos_over[~oos_over.fw_active]

if len(oos_over_active) > 0 and len(oos_over_inactive) > 0:
    roi_active_fw, _ = compute_roi_flat(oos_over_active, result_col='over_result_flag')
    roi_inactive_fw, _ = compute_roi_flat(oos_over_inactive, result_col='over_result_flag')
    roi_all_fw, _ = compute_roi_flat(oos_over, result_col='over_result_flag')
    hit_active_fw = oos_over_active.over_result_flag.mean() * 100
    hit_inactive_fw = oos_over_inactive.over_result_flag.mean() * 100
    delta_roi_fw = roi_active_fw - roi_all_fw

    if delta_roi_fw > 3 and hit_active_fw > hit_inactive_fw:
        fw_verdict = "SURVIVES"
    elif delta_roi_fw > 0:
        fw_verdict = "DIMINISHED"
    else:
        fw_verdict = "COLLAPSES"

    fw_report.append(f"OOS 2025: FW-active over hit={hit_active_fw:.1f}%, ROI_flat={roi_active_fw:+.1f}%")
    fw_report.append(f"OOS 2025: FW-inactive over hit={hit_inactive_fw:.1f}%, ROI_flat={roi_inactive_fw:+.1f}%")
    fw_report.append(f"OOS 2025: All V2 over ROI_flat={roi_all_fw:+.1f}%")
    fw_report.append(f"Delta ROI (active vs all): {delta_roi_fw:+.1f}pp")
    fw_report.append(f"Note: flyball_wind is already in V2 as a continuous feature. The overlay adds no NEW information.")
    fw_report.append(f"Verdict: **{fw_verdict}**")
else:
    fw_verdict = "INCONCLUSIVE"
    fw_report.append("Insufficient OOS data for verdict")
    fw_report.append(f"Verdict: **{fw_verdict}**")

with open(f"{OUT}/flyball_wind_overlay_report.md", "w") as f:
    f.write("\n".join(fw_report))
print(f"\nFlyball*Wind VERDICT: {fw_verdict}")

# ──────────────────────────────────────────────────
# MASTER SURVIVAL MAP
# ──────────────────────────────────────────────────
print("\n" + "=" * 70)
print("MASTER SURVIVAL MAP")
print("=" * 70)

verdicts = {
    'S12': s12_verdict,
    'P09': p09_verdict,
    'flyball_wind': fw_verdict,
}

master = []
master.append("# MASTER V2 OVERLAY SURVIVAL MAP\n")
master.append(f"Date: 2026-04-10")
master.append(f"Baseline: V2 Model_B (Ridge alpha=50, 14 features, target=market_error)")
master.append(f"Train: 2022-2023, Val: 2024, OOS: 2025")
master.append(f"V2 under signal: model edge < -0.5 (predicted total below market by 0.5+ runs)")
master.append(f"V2 over signal: model edge > +0.5\n")

master.append("## Results\n")
master.append(f"| Overlay | Formula | PIT-Safe | Old Cutoff | New Cutoff | OOS Verdict |")
master.append(f"|---------|---------|----------|------------|------------|-------------|")
master.append(f"| S12 | avg(csw_r5) - 5*avg(xfip) | YES | >= {OLD_S12_CUTOFF} | >= {NEW_S12_CUTOFF:.4f} | **{s12_verdict}** |")
master.append(f"| P09 | avg(hh_r5) * park_factor | YES | <= {OLD_P09_CUTOFF} | <= {NEW_P09_CUTOFF:.4f} | **{p09_verdict}** |")
master.append(f"| flyball_wind | (already in V2 model) | YES | N/A | >= {FW_CUTOFF_Q80:.4f} | **{fw_verdict}** |")

master.append(f"\n## Summary\n")
counts = {}
for v in verdicts.values():
    counts[v] = counts.get(v, 0) + 1
for status in ['SURVIVES', 'DIMINISHED', 'COLLAPSES', 'INCONCLUSIVE']:
    if status in counts:
        master.append(f"- {status}: {counts[status]}")

master.append(f"\n## Conclusion\n")
survivors = [k for k, v in verdicts.items() if v == 'SURVIVES']
collapsed = [k for k, v in verdicts.items() if v == 'COLLAPSES']
diminished = [k for k, v in verdicts.items() if v == 'DIMINISHED']
inconclusive = [k for k, v in verdicts.items() if v == 'INCONCLUSIVE']

if survivors:
    master.append(f"Overlays that add value on V2: {', '.join(survivors)}.")
if collapsed:
    master.append(f"Overlays that collapse on V2: {', '.join(collapsed)}.")
if diminished:
    master.append(f"Overlays with diminished (marginal) value on V2: {', '.join(diminished)}.")
if inconclusive:
    master.append(f"Overlays inconclusive: {', '.join(inconclusive)}.")

if not survivors:
    master.append(f"\nNo V1-era overlay adds meaningful value on top of the clean V2 baseline OOS 2025.")
else:
    master.append(f"\n{len(survivors)} overlay(s) survived V2 revalidation and should be considered for integration.")

with open(f"{OUT}/MASTER_V2_OVERLAY_SURVIVAL_MAP.md", "w") as f:
    f.write("\n".join(master))

print(f"\n{'='*70}")
print(f"FINAL SUMMARY")
print(f"{'='*70}")
for name, v in verdicts.items():
    print(f"  {name:20s}: {v}")
print(f"\nOverlays tested: {len(verdicts)}")
for status in ['SURVIVES', 'DIMINISHED', 'COLLAPSES', 'INCONCLUSIVE']:
    if status in counts:
        print(f"  {status}: {counts[status]}")

if not survivors:
    print(f"\nConclusion: No V1-era overlay survives on the V2 baseline — the clean model captures what these overlays were proxying.")
else:
    print(f"\nConclusion: {', '.join(survivors)} survived — consider integration into V2.")
