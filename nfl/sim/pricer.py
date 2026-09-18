#!/usr/bin/env python3
"""
NFL Sim Phase 3 — Pricer.

From an anchored joint sample (team_df + player_df), computes fair probabilities
for all market families. No per-sim Python loops — everything is column ops.
"""

import numpy as np
import pandas as pd


def _prob_to_american(p):
    """Convert probability to American odds."""
    if p <= 0 or p >= 1:
        return 0
    if p >= 0.5:
        return int(round(-100 * p / (1 - p)))
    else:
        return int(round(100 * (1 - p) / p))


def price_game(team_df, player_df, market_spread, market_total,
               home_team, away_team, player_ctx=None, calibration_maps=None):
    """Price all markets from an anchored sample.

    Returns:
      markets_df: (market, side, line, fair_prob, fair_american, calibrated_prob, n_sims)
      leg_matrix: DataFrame with sim_id rows and leg indicator columns for SGP
    """
    N = len(team_df)
    h = team_df["home_score"].values
    a = team_df["away_score"].values
    margin = h - a  # positive = home wins
    total = h + a
    h1h = team_df["home_1h"].values
    a1h = team_df["away_1h"].values
    margin_1h = h1h - a1h
    total_1h = h1h + a1h

    rows = []
    leg_indicators = {"sim_id": np.arange(N)}

    def _add(market, side, line, indicator):
        p = indicator.mean()
        rows.append({
            "market": market, "side": side, "line": float(line),
            "fair_prob": float(p),
            "fair_american": _prob_to_american(p),
            "n_sims": N,
        })
        col_name = f"{market}_{side}_{line}"
        leg_indicators[col_name] = indicator.astype(np.int8)

    # === Game-level markets ===

    # Home moneyline
    _add("moneyline", "home", 0, margin > 0)
    _add("moneyline", "away", 0, margin < 0)

    # Spread ladder: home -14 to +14 by 0.5
    for sp in np.arange(-14, 14.5, 0.5):
        _add("spread", "home", sp, margin + sp > 0)
        _add("spread", "away", -sp, -(margin + sp) > 0)

    # Total ladder: market_total ± 10 by 0.5
    for off in np.arange(-10, 10.5, 0.5):
        line = market_total + off
        _add("total", "over", line, total > line)
        _add("total", "under", line, total < line)

    # Team totals
    for off in np.arange(-10, 10.5, 0.5):
        hl = market_total / 2 - market_spread / 2 + off  # approximate home implied
        al = market_total / 2 + market_spread / 2 + off
        _add("home_total", "over", round(hl * 2) / 2, h > round(hl * 2) / 2)
        _add("home_total", "under", round(hl * 2) / 2, h < round(hl * 2) / 2)
        _add("away_total", "over", round(al * 2) / 2, a > round(al * 2) / 2)
        _add("away_total", "under", round(al * 2) / 2, a < round(al * 2) / 2)

    # 1H spread and total
    for sp in np.arange(-10, 10.5, 0.5):
        _add("1h_spread", "home", sp, margin_1h + sp > 0)
    mkt_1h_total = market_total / 2  # approximate
    for off in np.arange(-6, 6.5, 0.5):
        line = mkt_1h_total + off
        _add("1h_total", "over", line, total_1h > line)
        _add("1h_total", "under", line, total_1h < line)

    # === Player props ===
    if player_df is not None and len(player_df) > 0:
        # Get top players by mean targets/carries
        pmeans = player_df.groupby(["player_id", "player_name", "position", "team"]).agg(
            mean_tgt=("targets", "mean"),
            mean_car=("carries", "mean"),
            mean_patt=("pass_att", "mean"),
        ).reset_index()

        # Top 6 target share + top 2 carry share + QB per team
        for team in [home_team, away_team]:
            tp = pmeans[pmeans["team"] == team]
            # Top 6 by targets
            top_tgt = tp.nlargest(6, "mean_tgt")["player_id"].values
            # Top 2 by carries (non-QB)
            top_car = tp[(tp["position"] != "QB")].nlargest(2, "mean_car")["player_id"].values
            # QB
            qbs = tp[tp["position"] == "QB"].nlargest(1, "mean_patt")["player_id"].values
            selected = set(top_tgt) | set(top_car) | set(qbs)

            for pid in selected:
                pname = tp[tp["player_id"] == pid]["player_name"].iloc[0]
                pos = tp[tp["player_id"] == pid]["position"].iloc[0]
                psims = player_df[player_df["player_id"] == pid]

                # Build per-sim stat arrays (fill missing sims with 0)
                stats = pd.DataFrame({"sim_id": np.arange(N)}).merge(
                    psims[["sim_id", "targets", "receptions", "rec_yds", "rec_td",
                           "carries", "rush_yds", "rush_td", "pass_att", "pass_cmp",
                           "pass_yds", "pass_td", "anytime_td"]],
                    on="sim_id", how="left").fillna(0)

                prefix = f"{pname}_{pos}"

                # Receptions >= k
                for k in range(2, 11):
                    _add(f"rec_{prefix}", "over", k, (stats["receptions"] >= k).values)

                # Receiving yards >= y
                for y in range(20, 130, 10):
                    _add(f"rec_yds_{prefix}", "over", y, (stats["rec_yds"] >= y).values)

                # Rushing yards >= y
                for y in range(20, 130, 10):
                    _add(f"rush_yds_{prefix}", "over", y, (stats["rush_yds"] >= y).values)

                # Rush attempts >= k
                for k in range(5, 25, 5):
                    _add(f"rush_att_{prefix}", "over", k, (stats["carries"] >= k).values)

                # Passing yards >= y (QB)
                if pos == "QB":
                    for y in range(150, 400, 25):
                        _add(f"pass_yds_{prefix}", "over", y, (stats["pass_yds"] >= y).values)
                    # Passing TDs >= k
                    for k in [1, 2, 3]:
                        _add(f"pass_td_{prefix}", "over", k, (stats["pass_td"] >= k).values)

                # Anytime TD
                _add(f"atd_{prefix}", "over", 0.5, (stats["anytime_td"] >= 1).values)

    markets_df = pd.DataFrame(rows)

    # A6: one-sided coherence. Calibrate the over/home side only;
    # the complementary side = 1 - cal_p. This guarantees
    # cal_over + cal_under == 1 for every market/line pair.
    if calibration_maps is not None:
        # Step 1: calibrate every row independently
        markets_df["calibrated_prob"] = markets_df.apply(
            lambda r: _apply_calibration(r, calibration_maps), axis=1)
        # Step 2: enforce coherence — non-primary side = 1 - primary
        _PRIMARY = {"over", "home"}
        for i, row in markets_df.iterrows():
            if row["side"] not in _PRIMARY:
                # Find the primary-side complement
                comp_side = "over" if row["side"] == "under" else "home"
                comp_line = -row["line"] if row["market"] == "spread" else row["line"]
                comp = markets_df[(markets_df["market"] == row["market"]) &
                                  (markets_df["side"] == comp_side) &
                                  (np.abs(markets_df["line"] - comp_line) < 0.01)]
                if not comp.empty:
                    markets_df.at[i, "calibrated_prob"] = 1.0 - comp.iloc[0]["calibrated_prob"]
    else:
        markets_df["calibrated_prob"] = markets_df["fair_prob"]

    leg_matrix = pd.DataFrame(leg_indicators)

    return markets_df, leg_matrix


def _apply_calibration(row, cal_maps):
    """Look up calibrated probability from isotonic maps."""
    market = row["market"]
    p = row["fair_prob"]
    # Determine the calibration family
    if market in ("moneyline", "spread"):
        family = "margin_side"
    elif market in ("total", "1h_total"):
        family = "total_side"
    elif market in ("home_total", "away_total"):
        family = "team_total"
    elif market == "1h_spread":
        family = "margin_side"
    else:
        # Player prop — extract type and position
        family = "prop_default"
        for prop_type in ["rec_yds_", "rush_yds_", "pass_yds_", "rec_", "rush_att_",
                           "pass_td_", "atd_"]:
            if market.startswith(prop_type):
                # Extract position from the market name
                parts = market.split("_")
                pos = parts[-1] if parts[-1] in ("WR", "TE", "RB", "QB") else "WR"
                family = f"prop_{prop_type.rstrip('_')}_{pos}"
                break

    if family in cal_maps:
        xs, ys = cal_maps[family]["x"], cal_maps[family]["y"]
        return float(np.interp(p, xs, ys))
    return p


def sgp_probability_raw(leg_matrix, legs):
    """Joint frequency of all legs hitting in the same sim.

    legs: list of column names from leg_matrix.
    Returns float probability.
    """
    mask = np.ones(len(leg_matrix), dtype=bool)
    for leg in legs:
        if leg in leg_matrix.columns:
            mask &= leg_matrix[leg].values.astype(bool)
        else:
            return 0.0
    return float(mask.mean())


def sgp_probability_raked(leg_matrix, legs, cal_probs):
    """D65: Joint probability with exact binary IPF (raking).

    Each iteration step scales hit weights by t/m and non-hit weights by
    (1-t)/(1-m), where t is the target marginal and m is the current
    weighted marginal. This makes the marginal equal t after one step
    (exact for a single leg).

    Raises on unsupported targets: m == 0 with t > 0, m == 1 with t < 1,
    or t outside (0, 1).

    Args:
        leg_matrix: DataFrame with sim_id rows and indicator columns.
        legs: list of column names from leg_matrix.
        cal_probs: list of calibrated marginal probabilities, same order as legs.

    Returns:
        (joint_probability, effective_sample_size_count)
        ESS is a count (not a fraction): (sum w)^2 / sum(w^2).
    """
    N = len(leg_matrix)
    indicators = np.column_stack([
        leg_matrix[leg].values.astype(np.float64) for leg in legs
    ])  # (N, n_legs)

    # Validate targets
    for j, t in enumerate(cal_probs):
        if t <= 0 or t >= 1:
            raise ValueError(
                f"Target {t} for leg {legs[j]} outside (0, 1)")
        m = indicators[:, j].mean()
        if m == 0:
            raise ValueError(
                f"No sim hits leg {legs[j]} (m=0) but target={t}>0")
        if m == 1 and t < 1:
            raise ValueError(
                f"All sims hit leg {legs[j]} (m=1) but target={t}<1")

    weights = np.ones(N, dtype=np.float64) / N

    for iteration in range(200):
        max_err = 0.0
        for j, t in enumerate(cal_probs):
            col = indicators[:, j]
            m = (weights * col).sum()
            # Exact binary IPF: hits *= t/m, non-hits *= (1-t)/(1-m)
            hit_mask = col == 1
            weights[hit_mask] *= t / m
            weights[~hit_mask] *= (1 - t) / (1 - m)
            # Renormalize
            weights /= weights.sum()
            err = abs((weights * col).sum() - t)
            max_err = max(max_err, err)
        if max_err < 1e-6:
            break
    else:
        raise RuntimeError(
            f"SGP raking did not converge after 200 iterations (max_err={max_err:.2e})"
        )

    # Joint = weighted frequency of all legs hitting
    all_hit = indicators.prod(axis=1)
    joint = (weights * all_hit).sum()

    # Effective sample size (count): (sum w)^2 / sum(w^2)
    # weights sum to 1, so (sum w)^2 = 1; ESS = 1 / sum(w^2)
    ess = 1.0 / (weights ** 2).sum()

    return float(joint), float(ess)


def leg_correlation(leg_matrix, leg_i, leg_j):
    """Phi coefficient between two leg indicators."""
    if leg_i not in leg_matrix.columns or leg_j not in leg_matrix.columns:
        return 0.0
    a = leg_matrix[leg_i].values.astype(float)
    b = leg_matrix[leg_j].values.astype(float)
    n = len(a)
    n11 = (a * b).sum()
    n1x = a.sum()
    nx1 = b.sum()
    n0x = n - n1x
    nx0 = n - nx1
    denom = np.sqrt(n1x * n0x * nx1 * nx0)
    if denom == 0:
        return 0.0
    return float((n * n11 - n1x * nx1) / denom)
