"""
Phase V2.2-A1: Odds backfill from football-data.co.uk CSVs.

Reads B365 opening and closing odds for 2.5 line from existing CSVs.
Derives 1.5 and 3.5 fair probabilities via Poisson inversion (no API needed).
Computes vig-removed fair probabilities and line movement features.

Output: soccer/data/odds_historical.parquet
"""

import logging
import os
import warnings

import numpy as np
import pandas as pd
from scipy import stats
from scipy.optimize import brentq

warnings.filterwarnings("ignore")

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

BASE_DIR  = os.path.dirname(os.path.abspath(__file__))
DATA_DIR  = os.path.join(BASE_DIR, "data")
CACHE_DIR = os.path.join(DATA_DIR, "cache")

CANONICAL_PATH = os.path.join(DATA_DIR, "soccer_canonical.parquet")
OUTPUT_PATH    = os.path.join(DATA_DIR, "odds_historical.parquet")

# Map season_year → CSV filename suffix
SEASON_CSV_MAP = {
    "2019-20": "1920",
    "2020-21": "2021",
    "2021-22": "2122",
    "2022-23": "2223",
    "2023-24": "2324",
    "2024-25": "2425",
}

SEP = "═" * 72


# ── Vig removal ────────────────────────────────────────────────────────────────

def remove_vig(over_dec: float, under_dec: float) -> tuple[float, float]:
    """
    Vig-remove decimal over/under odds.
    Returns (fair_p_over, fair_p_under).
    """
    if over_dec <= 1.0 or under_dec <= 1.0:
        return np.nan, np.nan
    imp_over  = 1.0 / over_dec
    imp_under = 1.0 / under_dec
    total     = imp_over + imp_under
    if total <= 0:
        return np.nan, np.nan
    return imp_over / total, imp_under / total


# ── Poisson inversion for 1.5 / 3.5 lines ─────────────────────────────────────

def _poisson_over_prob(mu: float, threshold: float) -> float:
    """P(X >= threshold+1) where X ~ Poisson(mu)."""
    # P(over k.5) = P(X >= k+1) = 1 - P(X <= k)
    k = int(threshold)  # e.g. 2.5 → k=2
    return 1.0 - stats.poisson.cdf(k, mu)


def fair_p_to_mu(fair_p_over_2_5: float) -> float:
    """
    Solve for Poisson μ such that P(X >= 3 | Poisson(μ)) = fair_p_over_2_5.
    Returns μ, clipped to [0.5, 8.0].
    """
    if np.isnan(fair_p_over_2_5) or fair_p_over_2_5 <= 0 or fair_p_over_2_5 >= 1:
        return np.nan
    try:
        # f(μ) = P_over_2.5(μ) - target  →  find root
        f = lambda mu: _poisson_over_prob(mu, 2.5) - fair_p_over_2_5
        # Search in [0.5, 8.0]
        if f(0.5) * f(8.0) > 0:
            # Can't bracket — return approximate
            return np.clip(fair_p_over_2_5 * 4.5, 0.5, 8.0)
        mu = brentq(f, 0.5, 8.0, xtol=1e-4)
        return float(mu)
    except Exception:
        return np.nan


def derive_line_probs(fair_p_over_2_5: float) -> dict:
    """
    Given vig-removed fair P(over 2.5), derive:
      - market_implied_total_goals (mu)
      - market_fair_p_over_1_5
      - market_fair_p_over_3_5
      - market_fair_p_under_2_5
      - market_low_total_pressure
      - market_high_total_pressure
    """
    result = {
        "market_implied_mu":          np.nan,
        "market_fair_p_over_1_5":     np.nan,
        "market_fair_p_over_2_5":     fair_p_over_2_5,
        "market_fair_p_over_3_5":     np.nan,
        "market_fair_p_under_2_5":    1.0 - fair_p_over_2_5 if not np.isnan(fair_p_over_2_5) else np.nan,
        "market_low_total_pressure":  np.nan,
        "market_high_total_pressure": np.nan,
    }
    mu = fair_p_to_mu(fair_p_over_2_5)
    if np.isnan(mu):
        return result
    result["market_implied_mu"]       = mu
    p_over_1_5 = _poisson_over_prob(mu, 1.5)
    p_over_3_5 = _poisson_over_prob(mu, 3.5)
    result["market_fair_p_over_1_5"]     = p_over_1_5
    result["market_fair_p_over_3_5"]     = p_over_3_5
    result["market_low_total_pressure"]  = p_over_1_5 - fair_p_over_2_5
    result["market_high_total_pressure"] = fair_p_over_2_5 - p_over_3_5
    return result


# ── CSV parsing ────────────────────────────────────────────────────────────────

def parse_csv(league: str, season_suffix: str) -> pd.DataFrame:
    """
    Parse football-data.co.uk CSV.
    Returns DataFrame with game-level 2.5 opening and closing odds.
    """
    path = os.path.join(CACHE_DIR, f"fd_{league}_{season_suffix}.csv")
    if not os.path.exists(path):
        logger.warning(f"CSV not found: {path}")
        return pd.DataFrame()

    df = pd.read_csv(path, on_bad_lines="skip")

    # Required columns
    req = ["Date", "HomeTeam", "AwayTeam"]
    over_open_col  = "B365>2.5"
    under_open_col = "B365<2.5"
    over_close_col = "B365C>2.5"
    under_close_col = "B365C<2.5"

    for c in req:
        if c not in df.columns:
            logger.warning(f"Missing column {c} in {path}")
            return pd.DataFrame()

    # Parse date (dd/mm/yyyy)
    df["game_date"] = pd.to_datetime(df["Date"], format="%d/%m/%Y", errors="coerce")
    df = df.dropna(subset=["game_date", "HomeTeam", "AwayTeam"])

    # Extract odds columns
    for col in [over_open_col, under_open_col, over_close_col, under_close_col]:
        if col not in df.columns:
            df[col] = np.nan
        else:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    df["ref_over_open"]   = df[over_open_col]
    df["ref_under_open"]  = df[under_open_col]
    df["ref_over_close"]  = df[over_close_col]
    df["ref_under_close"] = df[under_close_col]

    # Referee (EPL only)
    df["referee"] = df["Referee"] if "Referee" in df.columns else np.nan

    return df[[
        "game_date", "HomeTeam", "AwayTeam",
        "ref_over_open", "ref_under_open",
        "ref_over_close", "ref_under_close",
        "referee",
    ]].copy()


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print(f"\n{SEP}")
    print("  PHASE V2.2-A1: ODDS BACKFILL (football-data.co.uk CSVs)")
    print(SEP)

    canon = pd.read_parquet(CANONICAL_PATH)
    canon["game_date"] = pd.to_datetime(canon["game_date"])
    logger.info(f"Canonical: {len(canon):,} games")

    rows = []

    for _, game in canon.iterrows():
        gid     = game["game_id"]
        league  = game["league_id"]
        season  = game["season_year"]
        gdate   = game["game_date"]
        home    = game["home_team"]
        away    = game["away_team"]

        suffix  = SEASON_CSV_MAP.get(season)
        if suffix is None:
            continue

        # Parse CSV (cached per call is wasteful; load outside loop below)
        rows.append({
            "game_id":  gid,
            "league_id": league,
            "season_year": season,
            "game_date": gdate,
            "home_team": home,
            "away_team": away,
        })

    # Build game index
    game_index = pd.DataFrame(rows)

    # Parse all CSVs into one DataFrame
    csv_frames = []
    all_leagues = sorted(game_index["league_id"].unique())
    for league in all_leagues:
        for season_year, suffix in SEASON_CSV_MAP.items():
            df = parse_csv(league, suffix)
            if df.empty:
                continue
            df["league_id"]   = league
            df["season_year"] = season_year
            csv_frames.append(df)

    all_csv = pd.concat(csv_frames, ignore_index=True)
    all_csv["game_date"] = pd.to_datetime(all_csv["game_date"])
    logger.info(f"CSV rows loaded: {len(all_csv):,}")

    # Match CSV rows to canonical by (league, game_date, HomeTeam, AwayTeam)
    # Drop season_year from csv to avoid _x/_y conflict (game_index has it)
    csv_for_merge = all_csv.rename(
        columns={"HomeTeam": "home_team", "AwayTeam": "away_team"}
    ).drop(columns=["season_year"], errors="ignore")

    merged = game_index.merge(
        csv_for_merge,
        on=["league_id", "game_date", "home_team", "away_team"],
        how="left",
    )
    logger.info(f"Merged: {len(merged):,} rows  "
                f"match_rate={merged['ref_over_close'].notna().mean():.1%}")

    # ── Compute vig-removed fair probabilities ─────────────────────────────────
    logger.info("Computing vig-removed fair probabilities...")

    # Closing
    fair_close = merged.apply(
        lambda r: remove_vig(r["ref_over_close"], r["ref_under_close"]), axis=1
    )
    merged["fair_p_over_2_5_close"]  = [x[0] for x in fair_close]
    merged["fair_p_under_2_5_close"] = [x[1] for x in fair_close]

    # Opening
    fair_open = merged.apply(
        lambda r: remove_vig(r["ref_over_open"], r["ref_under_open"]), axis=1
    )
    merged["fair_p_over_2_5_open"]   = [x[0] for x in fair_open]

    # ── Poisson-derived 1.5 / 3.5 probabilities ───────────────────────────────
    logger.info("Deriving 1.5/3.5 fair probabilities via Poisson inversion...")

    derived_close = merged["fair_p_over_2_5_close"].apply(derive_line_probs)
    derived_df    = pd.DataFrame(derived_close.tolist())
    for col in derived_df.columns:
        merged[col] = derived_df[col].values

    # ── Line movement features ─────────────────────────────────────────────────
    merged["market_move_to_over_2_5"]   = (
        merged["fair_p_over_2_5_close"] - merged["fair_p_over_2_5_open"]
    )
    merged["market_move_magnitude_2_5"] = merged["market_move_to_over_2_5"].abs()
    merged["market_late_move_over"]     = (merged["market_move_to_over_2_5"] > 0.03).astype(float)
    merged["market_late_move_under"]    = (merged["market_move_to_over_2_5"] < -0.03).astype(float)
    merged["market_odds_available"]     = merged["fair_p_over_2_5_close"].notna().astype(float)

    # ── Output schema ──────────────────────────────────────────────────────────
    output_cols = [
        "game_id", "league_id", "season_year", "game_date",
        # Primary market features (closing)
        "market_fair_p_over_2_5",
        "market_fair_p_under_2_5",
        "market_fair_p_over_1_5",
        "market_fair_p_over_3_5",
        # Market structure
        "market_implied_mu",
        "market_low_total_pressure",
        "market_high_total_pressure",
        # Opening
        "fair_p_over_2_5_open",
        # Line movement
        "market_move_to_over_2_5",
        "market_move_magnitude_2_5",
        "market_late_move_over",
        "market_late_move_under",
        "market_odds_available",
        # Raw odds (for reference)
        "ref_over_open", "ref_under_open",
        "ref_over_close", "ref_under_close",
        # Referee (bonus)
        "referee",
    ]

    out = merged[output_cols].copy()
    out.to_parquet(OUTPUT_PATH, index=False)
    logger.info(f"Saved: {OUTPUT_PATH}  ({len(out):,} rows)")

    # ── Audit ──────────────────────────────────────────────────────────────────
    print(f"\n{SEP}")
    print("  A1 ODDS AUDIT")
    print(SEP)

    print(f"\n  {'League':<8} {'Season':<10} {'N':>5} {'2.5_cov':>10} {'1.5_cov':>10} {'3.5_cov':>10}")
    print(f"  {'-'*58}")

    for season in sorted(out["season_year"].unique()):
        for league in sorted(out["league_id"].unique()):
            sub = out[(out["season_year"] == season) & (out["league_id"] == league)]
            if sub.empty:
                continue
            n        = len(sub)
            cov_2_5  = sub["market_fair_p_over_2_5"].notna().mean()
            cov_1_5  = sub["market_fair_p_over_1_5"].notna().mean()
            cov_3_5  = sub["market_fair_p_over_3_5"].notna().mean()
            flag_2_5 = "✓" if cov_2_5 >= 0.70 else "⚠"
            print(f"  {league:<8} {season:<10} {n:>5} {flag_2_5}{cov_2_5:>8.1%} {cov_1_5:>10.1%} {cov_3_5:>10.1%}")

    print()
    print(f"  Overall market_odds_available: {out['market_odds_available'].mean():.1%}")
    print(f"  market_fair_p_over_2_5 mean: {out['market_fair_p_over_2_5'].mean():.4f}")
    print(f"  market_implied_mu mean:       {out['market_implied_mu'].mean():.4f}")
    print(f"  line_move mean:               {out['market_move_to_over_2_5'].mean():.4f}")
    print()
    print(f"  Saved → {OUTPUT_PATH}")
    print()


if __name__ == "__main__":
    main()
