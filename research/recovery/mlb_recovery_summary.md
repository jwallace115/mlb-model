# MLB Recovery Summary — Executive Brief

**Date:** 2026-04-10

---

## What Happened

The V1 Ridge model (25-feature totals model, `phase9_baseline_model.pkl`) was trained on historical data from `sim/data/feature_table.parquet`. That feature table was built by `sim/phase2_build_features.py`, which calls `sim/modules/fg_historical.py` to pull FanGraphs stats. The FG API call uses `season=YYYY, ind=0`, which returns **full-season aggregates** — meaning every game in April 2022 sees the pitcher's September 2022 xFIP. This is textbook lookahead contamination.

---

## What Is Contaminated

**14 of 25 V1 features** are contaminated. All trace to one source: `fg_historical.py` pulling season-final FG/Savant data.

Contaminated features: SP xFIP (x2), SP K% (x2), SP BB% (x2), SP avg_ip (x2), wRC+ (x2), bullpen_delta (x2), bp_delta_exposure (x2), plus flyball_wind_interaction.

**Two trained models affected:**
- V1 Ridge (14/25 features contaminated)
- S2 Starter Path (1/9 features contaminated — sp_xfip)

**Five live objects caveated** (live inference clean, thresholds derived from contaminated data):
- V1 Ridge live inference
- S2 Starter Path live inference
- S12 Overlay cutoff
- F5 Totals thresholds
- F5 Run Line threshold

---

## What Is Clean

Everything built from per-game boxscores with `shift(1)` or per-start Statcast with `shift(1).rolling()`:
- CS013, CS028, CS004, KP04, Combined Short Exit (shadow signals)
- ADJ opponent-adjusted signals
- ST02 overlay (schedule only)
- high_leverage_avail (bullpen feature)
- All static features (park, weather, umpire, rest, DH)
- Team Totals Engine (live API + PIT-fixed PGL)
- Cross-market and TT-to-side research (market data only)
- Side Engine clean rerun (PIT features, already rebuilt)

---

## What To Trust

**Trust fully:** All CLEAN objects. They have no contamination path.

**Trust with caveat:** V1 Ridge live output. The live inference is clean (pulls today's FG data). The model weights are suboptimal but not directionally wrong — xFIP genuinely predicts totals, the model just learned slightly inflated coefficients from artificially clean training data.

**Do not trust:** The V1 historical backtest numbers. The +6.5% 2024 ROI, +2.3% STRONG tier 2025 OOS — these were measured with contaminated training. The true OOS numbers will be worse. How much worse is unknown until we retrain.

---

## What Happens Next

1. **Immediate (today):** No changes to live pipeline. V1 stays live. All signals treated as MEDIUM confidence.

2. **This week:** Build PIT-clean V1 feature table. K%, BB%, avg_ip from pitcher_game_logs (data already available). Merge with existing PIT FIP, BP FIP, offense RPG from side engine rebuild.

3. **Next week:** Retrain V1 Ridge on PIT features. Run honest OOS backtest against real closing lines. Compare to contaminated V1 results.

4. **If OOS is viable (within 3pp of contaminated):** Swap model pkl, update sigma, cascade to S2/S12/F5 thresholds.

5. **If OOS is not viable (>5pp worse):** Keep contaminated V1 live, investigate whether the model has any real edge at all.

---

## Blunt Assessment

The V1 Ridge model's historical performance numbers are inflated. We do not know by how much. The live inference is still clean and the model is still doing something useful — it just may be doing it with less precision than we thought.

The right move is to retrain on honest data and accept whatever the honest numbers say. If the PIT model shows +0.5% OOS instead of +2.3%, that is the truth. If it shows -2% OOS, that is also the truth.

The worst outcome is not a weaker model — it is continuing to make sizing and threshold decisions based on inflated backtest numbers. That is what the PIT retrain fixes.

Estimated time to completion: 10-15 hours of work, achievable in 1-2 days.
