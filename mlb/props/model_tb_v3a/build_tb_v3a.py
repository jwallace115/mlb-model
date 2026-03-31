#!/usr/bin/env python3
"""
MLB Props — Total Bases v3a
Player card + prop-context PA + predefined tiers.
"""

import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
DATA_DIR = PROJECT_ROOT / "mlb" / "data"
PROPS_DIR = PROJECT_ROOT / "mlb" / "props"
PROC_DIR = PROPS_DIR / "processed"
OUT_DIR = Path(__file__).resolve().parent

N_SIMS = 2000
RNG = np.random.default_rng(42)

# Time weights for multi-season player card
SEASON_WEIGHTS = {"current": 0.60, "prev": 0.30, "older": 0.10}
RECENT_FORM_CAP = 0.20  # max 20% shift from player card

OUTCOMES = ["bases_0", "singles", "doubles", "triples", "home_runs"]
BASES = np.array([0, 1, 2, 3, 4])

def roi_110(w, n):
    if n == 0: return np.nan
    return (w * (100/110) - (n - w)) / n * 100

def _to_implied(odds):
    if pd.isna(odds) or odds == 0: return np.nan
    return 100 / (odds + 100) if odds > 0 else abs(odds) / (abs(odds) + 100)

def devig(ov, un):
    ro, ru = _to_implied(ov), _to_implied(un)
    if pd.isna(ro) or pd.isna(ru): return np.nan, np.nan
    t = ro + ru
    return (ro/t, ru/t) if t > 0 else (np.nan, np.nan)

def realized_roi(wins, odds):
    total = len(odds)
    if total == 0: return np.nan
    profit = sum((o/100 if o > 0 else 100/abs(o)) if w == 1 else -1 for w, o in zip(wins, odds))
    return profit / total * 100

def brier_score(p, o):
    mask = pd.notna(p) & pd.notna(o)
    return float(((np.array(p[mask]) - np.array(o[mask]))**2).mean()) if mask.sum() > 0 else np.nan


def main():
    out = []
    def log(s=""):
        out.append(s)
        print(s, flush=True)

    log("=" * 65)
    log("MLB PROPS — TOTAL BASES v3a")
    log("=" * 65)
    log()

    h = pd.read_parquet(DATA_DIR / "hitter_game_logs.parquet")
    mv = pd.read_parquet(PROC_DIR / "props_market_view.parquet")

    h["game_date"] = pd.to_datetime(h["game_date"])
    starters = h[h["starter_flag"] == 1].copy().sort_values(["player_id", "game_date"])

    starters["tb"] = starters["singles"] + 2*starters["doubles"] + 3*starters["triples"] + 4*starters["home_runs"]
    starters["bases_0"] = starters["plate_appearances"] - starters["singles"] - starters["doubles"] - starters["triples"] - starters["home_runs"]

    # ── COMPONENT 3: Prop-context PA distributions ──
    log("COMPONENT 3 — Prop-context PA distributions...")
    prop_context = starters[starters["plate_appearances"] >= 3]
    log(f"  Prop-context games: {len(prop_context):,}/{len(starters):,} ({len(prop_context)/len(starters)*100:.1f}%)")

    pa_dists = {}
    for ha in ["H", "A"]:
        for slot in range(1, 10):
            vals = prop_context[(prop_context["home_away"] == ha) &
                                 (prop_context["batting_order_position"] == slot)]["plate_appearances"].values
            pa_dists[(ha, slot)] = vals if len(vals) > 50 else prop_context["plate_appearances"].values

    log("  PA by slot (prop-context):")
    for ha in ["H", "A"]:
        for slot in [1, 5, 9]:
            log(f"    {ha} slot {slot}: mean={pa_dists[(ha,slot)].mean():.2f}")
    log()

    # ── COMPONENT 4: Predefined player tiers ──
    log("COMPONENT 4 — Predefined player tiers...")

    # Compute per-player career stats for tiering
    player_stats = starters.groupby("player_id").agg(
        career_pa=("plate_appearances", "sum"),
        n_games=("game_pk", "count"),
        player_name=("player_name", "first"),
        modal_slot=("batting_order_position", lambda x: x.mode().iloc[0] if len(x.mode()) > 0 else 5),
    ).reset_index()

    # Slot stability: fraction of games in most common slot
    slot_stability = starters.groupby("player_id").apply(
        lambda g: (g["batting_order_position"] == g["batting_order_position"].mode().iloc[0]).mean()
        if len(g["batting_order_position"].mode()) > 0 else 0
    ).reset_index(name="slot_stability")

    player_stats = player_stats.merge(slot_stability, on="player_id")

    # Tier assignment
    def assign_tier(row):
        if row["career_pa"] >= 300 and row["modal_slot"] <= 6 and row["slot_stability"] >= 0.70:
            return "A"
        elif row["career_pa"] >= 150 or (row["career_pa"] >= 100 and row["slot_stability"] >= 0.50):
            return "B"
        else:
            return "C"

    player_stats["tier"] = player_stats.apply(assign_tier, axis=1)
    tier_counts = player_stats["tier"].value_counts()
    log(f"  Tier A: {tier_counts.get('A', 0)}")
    log(f"  Tier B: {tier_counts.get('B', 0)}")
    log(f"  Tier C: {tier_counts.get('C', 0)}")
    tier_lookup = player_stats.set_index("player_id")["tier"].to_dict()
    log()

    # ── COMPONENT 1+2: Player cards + recent form ──
    log("COMPONENT 1+2 — Building player cards with recent form...")

    # Build per-season outcome rates per player
    season_rates = {}
    for hand_filter in [None, "L", "R"]:
        sub = starters if hand_filter is None else starters[starters["opp_pitcher_hand"] == hand_filter]
        for (pid, season), g in sub.groupby(["player_id", "season"]):
            total_pa = g["plate_appearances"].sum()
            if total_pa < 20:
                continue
            rates = np.array([
                g["bases_0"].sum() / total_pa,
                g["singles"].sum() / total_pa,
                g["doubles"].sum() / total_pa,
                g["triples"].sum() / total_pa,
                g["home_runs"].sum() / total_pa,
            ])
            rates = np.maximum(rates, 0)
            rates = rates / rates.sum()
            key = (pid, season, hand_filter or "ALL")
            season_rates[key] = (rates, total_pa)

    # League average fallback
    all_pa = starters["plate_appearances"].sum()
    league_rates = np.array([
        starters["bases_0"].sum() / all_pa,
        starters["singles"].sum() / all_pa,
        starters["doubles"].sum() / all_pa,
        starters["triples"].sum() / all_pa,
        starters["home_runs"].sum() / all_pa,
    ])
    league_rates = league_rates / league_rates.sum()

    def get_player_card(pid, game_date, opp_hand, game_season):
        """Build multi-season weighted player card."""
        # Determine season weights
        seasons_available = []
        for s in [game_season, game_season - 1, game_season - 2]:
            key_platoon = (pid, s, opp_hand)
            key_overall = (pid, s, "ALL")
            if key_platoon in season_rates:
                seasons_available.append((s, key_platoon))
            elif key_overall in season_rates:
                seasons_available.append((s, key_overall))

        if not seasons_available:
            return league_rates.copy(), False

        # Weight by recency
        weighted = np.zeros(5)
        total_weight = 0
        for s, key in seasons_available:
            rates, pa = season_rates[key]
            if s == game_season:
                w = SEASON_WEIGHTS["current"]
            elif s == game_season - 1:
                w = SEASON_WEIGHTS["prev"]
            else:
                w = SEASON_WEIGHTS["older"]
            weighted += rates * w
            total_weight += w

        if total_weight > 0:
            weighted /= total_weight

        weighted = np.maximum(weighted, 0)
        weighted = weighted / weighted.sum()
        return weighted, True

    def apply_recent_form(card_rates, pid, game_date, game_season, opp_hand):
        """Apply capped recent form overlay."""
        # Get recent 30 PA
        player_games = starters[(starters["player_id"] == pid) &
                                 (starters["game_date"] < game_date) &
                                 (starters["season"] == game_season)]
        if opp_hand in ("L", "R"):
            player_games_split = player_games[player_games["opp_pitcher_hand"] == opp_hand]
            if len(player_games_split) >= 5:
                player_games = player_games_split

        # Take last ~30 PA worth of games
        recent = player_games.tail(10)  # ~30 PA
        total_pa = recent["plate_appearances"].sum()
        if total_pa < 15:
            return card_rates  # not enough recent data

        recent_rates = np.array([
            recent["bases_0"].sum() / total_pa,
            recent["singles"].sum() / total_pa,
            recent["doubles"].sum() / total_pa,
            recent["triples"].sum() / total_pa,
            recent["home_runs"].sum() / total_pa,
        ])
        recent_rates = np.maximum(recent_rates, 0)
        recent_rates = recent_rates / recent_rates.sum()

        # Apply cap: max 20% shift from card
        adjusted = card_rates.copy()
        for i in range(5):
            max_shift = card_rates[i] * RECENT_FORM_CAP
            delta = recent_rates[i] - card_rates[i]
            delta = np.clip(delta, -max_shift, max_shift)
            adjusted[i] = card_rates[i] + delta

        adjusted = np.maximum(adjusted, 0)
        adjusted = adjusted / adjusted.sum()
        return adjusted

    # ── Join to TB market ──
    log("Joining to TB market view...")
    tb_mv = mv[mv["prop_type"] == "TB"].copy()
    has_odds = tb_mv["consensus_over_odds"].notna() & tb_mv["consensus_under_odds"].notna()
    pct = has_odds.mean() * 100
    log(f"  Odds coverage: {pct:.1f}%")
    if pct < 80:
        log("STOPPING: odds < 80%")
        return
    tb_mv = tb_mv[has_odds].copy()
    tb_mv["player_id"] = tb_mv["player_id"].astype(float)

    # Need lineup info
    feat = starters[["game_pk", "player_id", "game_date", "season",
                       "batting_order_position", "home_away", "opp_pitcher_hand",
                       "plate_appearances", "tb"]].copy()
    feat["game_date_str"] = feat["game_date"].dt.strftime("%Y-%m-%d")
    feat["player_id"] = feat["player_id"].astype(float)

    joined = tb_mv.merge(feat, left_on=["player_id", "game_date"],
                           right_on=["player_id", "game_date_str"],
                           how="inner", suffixes=("", "_feat"))
    # Clean duplicates
    for c in list(joined.columns):
        if c.endswith("_feat"):
            base = c.replace("_feat", "")
            if base in joined.columns:
                joined.drop(columns=[c], inplace=True)

    log(f"  Joined: {len(joined):,} rows")
    log()

    # ── SIMULATE ──
    log("Running simulations...")
    all_plays = []
    count = 0

    for _, row in joined.iterrows():
        pid = int(row["player_id"])
        gd = pd.Timestamp(row["game_date"])
        season = int(row["season"])
        opp_hand = row.get("opp_pitcher_hand", "R")
        ha = row.get("home_away", "A")
        slot = int(row.get("batting_order_position", 5))
        line = row["consensus_line"]

        # Build player card
        card_rates, has_card = get_player_card(pid, gd, opp_hand, season)
        if not has_card:
            card_rates = league_rates.copy()

        # Apply recent form
        final_rates = apply_recent_form(card_rates, pid, gd, season, opp_hand)

        # Draw PA
        pa_dist = pa_dists.get((ha, slot), pa_dists.get(("A", 5)))
        pa_draws = RNG.choice(pa_dist, size=N_SIMS)

        # Vectorized simulation
        max_pa = int(pa_draws.max()) + 1
        all_outcomes = RNG.choice(BASES, size=(N_SIMS, max_pa), p=final_rates)
        pa_mask = np.arange(max_pa)[None, :] < pa_draws[:, None]
        tb_sims = (all_outcomes * pa_mask).sum(axis=1)

        p_over = float((tb_sims > line).mean())
        p_under = float((tb_sims <= line).mean())

        imp_over, imp_under = devig(row["consensus_over_odds"], row["consensus_under_odds"])
        if pd.isna(imp_over):
            continue

        edge_over = p_over - imp_over
        edge_under = p_under - imp_under
        lean = "OVER" if edge_over > edge_under and edge_over > 0 else \
               "UNDER" if edge_under > 0 else "NO_PLAY"
        edge = edge_over if lean == "OVER" else edge_under if lean == "UNDER" else 0
        bucket = "5%+" if abs(edge) >= 0.05 else "2-5%" if abs(edge) >= 0.02 else "0-2%"

        actual = row.get("actual_value", np.nan)
        win = np.nan
        if lean == "OVER" and not pd.isna(actual):
            win = 1.0 if actual > line else 0.0
        elif lean == "UNDER" and not pd.isna(actual):
            win = 1.0 if actual < line else 0.0

        actual_odds = row.get("best_over_odds" if lean == "OVER" else "best_under_odds",
                               row.get("consensus_over_odds" if lean == "OVER" else "consensus_under_odds", -110))
        if pd.isna(actual_odds): actual_odds = -110

        tier = tier_lookup.get(pid, "C")
        iso = 0
        # Compute ISO from card
        if has_card:
            iso = final_rates[2] + 2*final_rates[3] + 3*final_rates[4]  # approximate ISO proxy

        all_plays.append({
            "player_name": row["player_name"], "player_id": pid,
            "game_date": row["game_date"], "season": season,
            "dataset_split": row["dataset_split"],
            "lineup_slot": slot, "home_away": ha,
            "opp_pitcher_hand": opp_hand,
            "tier": tier, "iso_proxy": round(iso, 4),
            "line": line, "projection": round(float(tb_sims.mean()), 2),
            "model_prob_over": round(p_over, 4),
            "model_prob_under": round(p_under, 4),
            "implied_prob_over": round(imp_over, 4),
            "implied_prob_under": round(imp_under, 4),
            "edge": round(edge, 4), "lean": lean,
            "edge_bucket": bucket,
            "actual_value": actual,
            "actual_PA": row.get("plate_appearances", np.nan),
            "projected_PA": round(float(pa_draws.mean()), 2),
            "actual_odds": actual_odds,
            "bet_win": win,
            "has_card": has_card,
        })

        count += 1
        if count % 10000 == 0:
            log(f"  {count:,}...")

    plays = pd.DataFrame(all_plays)
    plays.to_parquet(OUT_DIR / "backtest_results.parquet", index=False)
    plays.to_csv(OUT_DIR / "backtest_results.csv", index=False)
    log(f"\n  Total: {len(plays):,}, with outcomes: {plays['bet_win'].notna().sum():,}")

    # ══════════════════════════════════════════════════════════
    # REPORTING
    # ══════════════════════════════════════════════════════════

    # Section 0
    log(f"\n{'='*65}\nSECTION 0 — PLAYER TIERS + WEIGHTS\n{'='*65}")
    log(f"  Season weights: current={SEASON_WEIGHTS['current']}, prev={SEASON_WEIGHTS['prev']}, older={SEASON_WEIGHTS['older']}")
    log(f"  Recent form cap: {RECENT_FORM_CAP:.0%}")
    log(f"  Tier distribution in plays:")
    for t in ["A", "B", "C"]:
        n = (plays["tier"] == t).sum()
        log(f"    Tier {t}: {n:,} ({n/len(plays)*100:.1f}%)")
    log(f"  Player cards found: {plays['has_card'].sum():,}/{len(plays):,} ({plays['has_card'].mean()*100:.1f}%)")

    # Section 1: PA accuracy
    log(f"\n{'='*65}\nSECTION 1 — PA ACCURACY\n{'='*65}")
    val = plays[(plays["dataset_split"] == "VALIDATION") & plays["actual_PA"].notna()]
    for slot in range(1, 10):
        s = val[val["lineup_slot"] == slot]
        if len(s) > 50:
            log(f"  Slot {slot}: proj={s['projected_PA'].mean():.2f}, actual={s['actual_PA'].mean():.2f}, "
                f"delta={s['projected_PA'].mean()-s['actual_PA'].mean():+.2f}")

    # Section 2: Calibration
    log(f"\n{'='*65}\nSECTION 2 — CALIBRATION\n{'='*65}")
    val_cal = plays[(plays["dataset_split"] == "VALIDATION") & plays["actual_value"].notna()]
    cal_pass = True
    log(f"{'Bucket':<12s} {'N':>6s} {'Model':>7s} {'Actual':>7s} {'Delta':>7s}")
    log("-" * 42)
    for lo, hi, label in [(0, 0.35, "<35%"), (0.35, 0.45, "35-45%"), (0.45, 0.55, "45-55%"),
                           (0.55, 0.65, "55-65%"), (0.65, 0.75, "65-75%"), (0.75, 1.01, "75%+")]:
        mask = (val_cal["model_prob_over"] >= lo) & (val_cal["model_prob_over"] < hi)
        b = val_cal[mask]
        if len(b) < 20: continue
        mp = b["model_prob_over"].mean()
        ar = (b["actual_value"] > b["line"]).mean()
        delta = ar - mp
        flag = " ⚠" if abs(delta) > 0.10 else " ✗" if abs(delta) > 0.15 else ""
        if abs(delta) > 0.15: cal_pass = False
        log(f"{label:<12s} {len(b):>6d} {mp:>6.1%} {ar:>6.1%} {delta:>+6.1%}{flag}")

    actual_over = (val_cal["actual_value"] > val_cal["line"]).astype(float)
    brier = brier_score(val_cal["model_prob_over"], actual_over)
    log(f"\nBrier: {brier:.4f}  Calibration: {'PASS' if cal_pass else 'FAIL'}")

    # Sections 3-5: Results
    for split_label, split_val in [("VALIDATION (2024)", "VALIDATION"), ("OOS (2025)", "OOS")]:
        v = plays[(plays["dataset_split"] == split_val) & (plays["lean"] != "NO_PLAY") & plays["bet_win"].notna()]
        if len(v) == 0: continue

        log(f"\n{'='*65}\n{split_label}\n{'='*65}")
        w = v["bet_win"].sum(); n = len(v)
        roi_a = realized_roi(v["bet_win"].values, v["actual_odds"].values)
        log(f"  Overall: N={n:,}, hit={w/n*100:.1f}%, ROI_actual={roi_a:+.1f}%")

        for d in ["OVER", "UNDER"]:
            sub = v[v["lean"] == d]
            if len(sub) > 0:
                sr = realized_roi(sub["bet_win"].values, sub["actual_odds"].values)
                log(f"  {d}: N={len(sub):,}, hit={sub['bet_win'].mean()*100:.1f}%, ROI={sr:+.1f}%")

        # Edge buckets
        log("  Edge buckets:")
        for bk in ["0-2%", "2-5%", "5%+"]:
            sub = v[v["edge_bucket"] == bk]
            if len(sub) > 0:
                sr = realized_roi(sub["bet_win"].values, sub["actual_odds"].values)
                log(f"    {bk}: N={len(sub):,}, hit={sub['bet_win'].mean()*100:.1f}%, ROI={sr:+.1f}%")

        # TIER SEGMENTATION (Section 4)
        log(f"\n  BY PLAYER TIER:")
        for tier in ["A", "B", "C"]:
            sub = v[v["tier"] == tier]
            if len(sub) < 50: continue
            sr = realized_roi(sub["bet_win"].values, sub["actual_odds"].values)
            log(f"    Tier {tier}: N={len(sub):,}, hit={sub['bet_win'].mean()*100:.1f}%, ROI={sr:+.1f}%")

        # Tier × direction
        log(f"  BY TIER × DIRECTION:")
        for tier in ["A", "B"]:
            for d in ["OVER", "UNDER"]:
                sub = v[(v["tier"] == tier) & (v["lean"] == d)]
                if len(sub) < 30: continue
                sr = realized_roi(sub["bet_win"].values, sub["actual_odds"].values)
                log(f"    Tier {tier} {d}: N={len(sub):,}, hit={sub['bet_win'].mean()*100:.1f}%, ROI={sr:+.1f}%")

        # Section 5: Structural
        log(f"\n  BY ISO PROFILE:")
        for label, lo_i, hi_i in [("Low (<.04)", 0, 0.04), ("Med (.04-.08)", 0.04, 0.08), ("High (>.08)", 0.08, 1)]:
            sub = v[(v["iso_proxy"] >= lo_i) & (v["iso_proxy"] < hi_i)]
            if len(sub) < 50: continue
            sr = realized_roi(sub["bet_win"].values, sub["actual_odds"].values)
            log(f"    {label}: N={len(sub):,}, hit={sub['bet_win'].mean()*100:.1f}%, ROI={sr:+.1f}%")

        log(f"\n  BY LINEUP SLOT:")
        for label, slots in [("Top (1-3)", [1,2,3]), ("Mid (4-6)", [4,5,6]), ("Bot (7-9)", [7,8,9])]:
            sub = v[v["lineup_slot"].isin(slots)]
            if len(sub) < 50: continue
            sr = realized_roi(sub["bet_win"].values, sub["actual_odds"].values)
            log(f"    {label}: N={len(sub):,}, hit={sub['bet_win'].mean()*100:.1f}%, ROI={sr:+.1f}%")

    # Section 7: Recommendation
    log(f"\n{'='*65}\nSECTION 7 — PRODUCTION RECOMMENDATION\n{'='*65}")

    val_v = plays[(plays["dataset_split"] == "VALIDATION") & (plays["lean"] != "NO_PLAY") & plays["bet_win"].notna()]
    oos_v = plays[(plays["dataset_split"] == "OOS") & (plays["lean"] != "NO_PLAY") & plays["bet_win"].notna()]

    # Check overall
    overall_roi = realized_roi(val_v["bet_win"].values, val_v["actual_odds"].values) if len(val_v) > 0 else np.nan
    log(f"  Overall val ROI: {overall_roi:+.1f}%")

    # Check each tier
    for tier in ["A", "B"]:
        sub_v = val_v[val_v["tier"] == tier]
        sub_o = oos_v[oos_v["tier"] == tier]
        if len(sub_v) < 200: continue
        v_roi = realized_roi(sub_v["bet_win"].values, sub_v["actual_odds"].values)
        o_roi = realized_roi(sub_o["bet_win"].values, sub_o["actual_odds"].values) if len(sub_o) > 0 else np.nan
        passes = v_roi >= 3.0 and (pd.isna(o_roi) or o_roi >= 0)
        log(f"  Tier {tier}: val ROI={v_roi:+.1f}%, OOS={o_roi:+.1f}% → {'PASS' if passes else 'FAIL'}")

        # Check tier × direction
        for d in ["OVER", "UNDER"]:
            sub_vd = val_v[(val_v["tier"] == tier) & (val_v["lean"] == d)]
            sub_od = oos_v[(oos_v["tier"] == tier) & (oos_v["lean"] == d)]
            if len(sub_vd) < 100: continue
            vd_roi = realized_roi(sub_vd["bet_win"].values, sub_vd["actual_odds"].values)
            od_roi = realized_roi(sub_od["bet_win"].values, sub_od["actual_odds"].values) if len(sub_od) > 0 else np.nan
            passes_d = vd_roi >= 3.0 and (pd.isna(od_roi) or od_roi >= 0)
            log(f"    Tier {tier} {d}: val ROI={vd_roi:+.1f}%, OOS={od_roi:+.1f}% → {'PASS' if passes_d else 'FAIL'}")

    log()

    # Section 8: Observations
    log(f"{'='*65}\nSECTION 8 — OBSERVATIONS\n{'='*65}")
    log(f"1. Calibration: {'PASS' if cal_pass else 'FAIL'}, Brier={brier:.4f}")
    log(f"2. Overall ROI: {overall_roi:+.1f}%")
    log("3. Player card + tier approach provides structured evaluation")
    log("4. Next: park factor + pitcher profile interaction (TB v3b)")

    with open(OUT_DIR / "tb_v3a_summary.txt", "w") as f:
        f.write("\n".join(out))

    log(f"\n{'='*65}\nFiles saved to mlb/props/model_tb_v3a/\n{'='*65}")


if __name__ == "__main__":
    main()
