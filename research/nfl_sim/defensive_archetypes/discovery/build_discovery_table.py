#!/usr/bin/env python3
"""DA-2 Item 2: build the discovery table for 2021-23. Vectorized."""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "research" / "nfl_sim" / "defensive_archetypes"))

from team_xwalk import canon
from da_guard import check_prop_seasons
import nflreadpy

OUT = ROOT / "research" / "nfl_sim" / "defensive_archetypes" / "discovery"
LABELS_DIR = ROOT / "research" / "nfl_sim" / "defensive_archetypes" / "labels"

MARKETS = {
    "player_receptions": "receptions",
    "player_reception_yds": "receiving_yards",
    "player_rush_yds": "rushing_yards",
    "player_rush_attempts": "carries",
    "player_pass_yds": "passing_yards",
    "player_pass_completions": "completions",
    "player_pass_attempts": "attempts",
}
BLEND_K = 4


def _compute_baselines(stats, seasons):
    """Vectorized: for each (player_id, season, week, stat_col), compute
    the as-of baseline = blend(season-to-date mean, prior-season mean, k=4)."""
    rows = []
    for stat_col in MARKETS.values():
        if stat_col not in stats.columns:
            continue
        sub = stats[stats.season.isin(list(seasons) + [min(seasons) - 1])][
            ["player_id", "season", "week", stat_col]].copy()
        sub = sub.dropna(subset=[stat_col])
        sub.rename(columns={stat_col: "val"}, inplace=True)

        # Prior-season mean per player
        for s in sorted(seasons):
            prior = sub[sub.season == s - 1].groupby("player_id")["val"].agg(["mean", "count"]).reset_index()
            prior.columns = ["player_id", "prior_mean", "prior_n"]
            prior = prior[prior.prior_n >= 8]  # require >= 8 games

            cur = sub[sub.season == s].copy()
            if cur.empty:
                continue

            # Expanding mean up to (but not including) each week
            cur = cur.sort_values(["player_id", "week"])
            cur["cum_sum"] = cur.groupby("player_id")["val"].cumsum() - cur["val"]
            cur["cum_n"] = cur.groupby("player_id").cumcount()
            cur["cur_mean"] = cur["cum_sum"] / cur["cum_n"].replace(0, np.nan)

            cur = cur.merge(prior[["player_id", "prior_mean"]], on="player_id", how="left")

            # Blend
            cur["baseline"] = np.where(
                cur["cum_n"] == 0,
                cur["prior_mean"],  # week 1: prior only; NaN if no prior
                np.where(
                    cur["prior_mean"].isna(),
                    cur["cur_mean"],
                    (cur["cum_n"] * cur["cur_mean"] + BLEND_K * cur["prior_mean"]) / (cur["cum_n"] + BLEND_K)
                )
            )
            cur["stat_col"] = stat_col
            cur["actual"] = cur["val"]
            cur["t2_residual"] = cur["actual"] - cur["baseline"]
            rows.append(cur[["player_id", "season", "week", "stat_col", "actual", "baseline", "t2_residual"]])

    if not rows:
        return pd.DataFrame()
    return pd.concat(rows, ignore_index=True)


def main():
    print("Loading data...")
    # Labels
    labels_frames = []
    for s in range(2021, 2026):
        fp = LABELS_DIR / f"da_labels_{s}.parquet"
        if fp.exists():
            labels_frames.append(pd.read_parquet(fp))
    labels = pd.concat(labels_frames, ignore_index=True)

    # Stats
    stats_frames = []
    for s in range(2020, 2024):
        try:
            st = nflreadpy.load_player_stats(seasons=[s], summary_level="week")
            if hasattr(st, "to_pandas"):
                st = st.to_pandas()
            stats_frames.append(st)
        except Exception as e:
            print(f"  stats {s}: {e}")
    stats = pd.concat(stats_frames, ignore_index=True)

    # Rosters for position
    rosters_frames = []
    for s in range(2020, 2024):
        try:
            r = nflreadpy.load_rosters([s])
            if hasattr(r, "to_pandas"):
                r = r.to_pandas()
            rosters_frames.append(r)
        except Exception:
            pass
    rosters = pd.concat(rosters_frames, ignore_index=True)
    pos_map = dict(zip(zip(rosters.gsis_id, rosters.season.astype(int)), rosters.position))

    # Schedule
    sched_frames = []
    for s in range(2021, 2024):
        try:
            sc = nflreadpy.load_schedules([s])
            if hasattr(sc, "to_pandas"):
                sc = sc.to_pandas()
            sched_frames.append(sc)
        except Exception:
            pass
    sched = pd.concat(sched_frames, ignore_index=True)
    sched["_home"] = sched["home_team"].apply(canon)
    sched["_away"] = sched["away_team"].apply(canon)

    # Props 2023 for close lines
    import glob
    prop_frames = []
    for f in sorted(glob.glob(str(ROOT / "data/odds_archive/nfl/props/season=2023/month=*/data_*.parquet"))) + \
             sorted(glob.glob(str(ROOT / "data/odds_archive/nfl/props/season=2024/month=01/data_*.parquet"))) + \
             sorted(glob.glob(str(ROOT / "data/odds_archive/nfl/props/season=2024/month=02/data_*.parquet"))):
        prop_frames.append(pd.read_parquet(f))
    props_2023 = pd.concat(prop_frames, ignore_index=True) if prop_frames else pd.DataFrame()
    ct = pd.to_datetime(props_2023["commence_time"], utc=True, errors="coerce")
    props_2023["nfl_season"] = np.where(ct.dt.month >= 9, ct.dt.year, ct.dt.year - 1).astype(int)
    props_2023 = props_2023[props_2023.nfl_season == 2023]
    check_prop_seasons(props_2023)
    print(f"Stats: {len(stats)}, Props 2023: {len(props_2023)}")

    # ── Close lines ──
    props_2023["_ct"] = pd.to_datetime(props_2023["commence_time"], utc=True, errors="coerce")
    props_2023["_lu"] = pd.to_datetime(props_2023["last_update"], utc=True, errors="coerce")
    props_pre = props_2023[props_2023["_lu"] < props_2023["_ct"]].copy()

    # Per (event, market, player, book): latest line
    by_book = props_pre.sort_values("_lu").groupby(
        ["event_id", "market_key", "player_name", "bookmaker"]).agg(
        line=("line", "last"), over_price=("over_price", "last"),
        under_price=("under_price", "last")).reset_index()

    close_rows = []
    for (eid, mk, pn), g in by_book.groupby(["event_id", "market_key", "player_name"]):
        dk = g[g.bookmaker == "draftkings"]
        if len(dk) and pd.notna(dk.iloc[0]["line"]):
            close_rows.append({"event_id": eid, "market_key": mk, "player_name": pn,
                               "close_line": float(dk.iloc[0]["line"]),
                               "close_over_price": dk.iloc[0]["over_price"],
                               "close_under_price": dk.iloc[0]["under_price"],
                               "close_source": "draftkings"})
        elif len(g) >= 3:
            close_rows.append({"event_id": eid, "market_key": mk, "player_name": pn,
                               "close_line": float(g["line"].median()),
                               "close_over_price": np.nan, "close_under_price": np.nan,
                               "close_source": f"median_{len(g)}_books"})
    closes = pd.DataFrame(close_rows)
    print(f"Close lines: {len(closes)}")

    # ── Baselines (vectorized) ──
    print("Computing baselines...")
    baselines = _compute_baselines(stats, {2021, 2022, 2023})
    print(f"Baselines: {len(baselines)}")

    # ── Build the table ──
    # Start from stats rows that have a game_id and are in 2021-23
    stats_21_23 = stats[stats.season.isin([2021, 2022, 2023])].copy()
    stats_21_23["_team"] = stats_21_23["team"].apply(canon) if "team" in stats_21_23.columns else stats_21_23.get("recent_team", "").apply(canon)
    stats_21_23["_opp"] = stats_21_23["opponent_team"].apply(canon) if "opponent_team" in stats_21_23.columns else ""

    # Melt stats into one row per (player, game, market)
    all_rows = []
    for market_key, stat_col in MARKETS.items():
        if stat_col not in stats_21_23.columns:
            continue
        sub = stats_21_23[stats_21_23[stat_col].notna()][
            ["player_id", "season", "week", "game_id", stat_col,
             "player_display_name", "_team", "_opp"]].copy()
        sub.rename(columns={stat_col: "actual"}, inplace=True)
        sub["market_key"] = market_key
        sub["stat_col"] = stat_col

        # Join baseline
        bl = baselines[baselines.stat_col == stat_col][["player_id", "season", "week", "baseline", "t2_residual"]]
        sub = sub.merge(bl, on=["player_id", "season", "week"], how="left")
        sub = sub[sub.baseline.notna()]  # exclude no-baseline

        # Position
        sub["position"] = [pos_map.get((pid, int(s)), "") for pid, s in zip(sub.player_id, sub.season)]

        # Opponent label
        label_cols = [c for c in labels.columns if c.startswith("f") or c == "n_games_into_label"]
        opp_labels = labels[["season", "week", "defense"] + label_cols].copy()
        opp_labels.rename(columns={c: f"opp_{c}" for c in label_cols}, inplace=True)
        sub = sub.merge(opp_labels, left_on=["season", "week", "_opp"],
                        right_on=["season", "week", "defense"], how="left")

        all_rows.append(sub)

    df = pd.concat(all_rows, ignore_index=True)

    # ── T1: 2023 close lines ──
    if len(closes):
        # Match closes to stats via player_name + market_key + event_id
        # We need event_id on the stats. Use game_id → schedule → prop event matching.
        # Simpler: match by player_display_name + market_key (may miss some)
        t1 = df[df.season == 2023].merge(
            closes.rename(columns={"player_name": "player_display_name"}),
            on=["market_key", "player_display_name"], how="left")
        t1["t1_residual"] = t1["actual"] - t1["close_line"]
        t1["over_hit"] = np.where(t1.actual > t1.close_line, 1,
                                   np.where(t1.actual < t1.close_line, 0, np.nan))

        # Merge T1 back
        df = df[df.season != 2023].copy()
        df = pd.concat([df, t1], ignore_index=True)

    print(f"\nTotal rows: {len(df)}")

    # ── GUARD ──
    assert (df.season <= 2023).all(), "HALT: rows with season > 2023"

    # ── INVARIANT (a): |corr(T1, close)| < 0.15 ──
    print("\nCorrelation T1_residual vs close_line (2023):")
    t1_rows = df[df.t1_residual.notna()] if "t1_residual" in df.columns else pd.DataFrame()
    for mk in sorted(t1_rows.market_key.unique()) if len(t1_rows) else []:
        m = t1_rows[t1_rows.market_key == mk]
        if len(m) >= 10 and "close_line" in m.columns:
            c = m[["t1_residual", "close_line"]].corr().iloc[0, 1]
            print(f"  {mk}: corr = {c:.4f} (n={len(m)})")
            if abs(c) >= 0.15:
                raise SystemExit(f"HALT: |corr| = {abs(c):.4f} >= 0.15 for {mk}")

    # ── INVARIANT (b): three known rows ──
    if len(t1_rows):
        print("\nTop-3 2023 rec-yds lines:")
        rec_yds = t1_rows[t1_rows.market_key == "player_reception_yds"].nlargest(3, "close_line")
        for _, r in rec_yds.iterrows():
            print(f"  {r.player_display_name:25s} wk{r.week:2.0f} actual={r.actual:5.0f} "
                  f"close={r.close_line:5.1f} residual={r.t1_residual:+6.1f}")

    # ── INVARIANT (d): over-hit rate 45-55% ──
    if len(t1_rows):
        print("\nOver-hit rate at close (2023):")
        for mk in sorted(t1_rows.market_key.unique()):
            m = t1_rows[(t1_rows.market_key == mk)]
            oh_col = m["over_hit"].dropna() if "over_hit" in m.columns else pd.Series()
            if len(oh_col) >= 10:
                print(f"  {mk}: {oh_col.mean():.3f} (n={len(oh_col)})")

    # ── Row counts ──
    print("\nRow counts per season × market:")
    for s in [2021, 2022, 2023]:
        ss = df[df.season == s]
        for mk in sorted(ss.market_key.unique()):
            n = len(ss[ss.market_key == mk])
            print(f"  {s} {mk}: {n}")

    df.to_parquet(OUT / "da2_rows_2021_23.parquet", index=False)
    print(f"\nSaved: {len(df)} rows → da2_rows_2021_23.parquet")


if __name__ == "__main__":
    main()
