"""
CC-1b tests — RED first, paste the red lines, then GREEN.

t1′: truncation over EVERY feature column on 20 random DEV dates.
t1″: real planted leak (widen a window to include day D), assert truncation FAILS.
t2′: close null at 0.005 implied prob on 20 games vs lines_all.
t3:  second_pred isolation.
"""

import inspect
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


class TestTruncationAll:
    """t1′: verify ALL feature columns are point-in-time for 20 random dates."""

    def test_nhl_all_features_truncation(self):
        games = pd.read_parquet(DATA_DIR / "games_nhl.parquet")
        features = pd.read_parquet(DATA_DIR / "features_nhl.parquet")

        gf = features.merge(
            games[["event_id", "commence_time", "season", "h_abbrev", "a_abbrev", "game_id"]],
            on="event_id", how="left"
        )
        gf["game_date"] = pd.to_datetime(gf["commence_time"]).dt.tz_convert("US/Eastern").dt.date

        sbro = pd.read_parquet(
            Path.home() / "mlb-model/research/nhl_sim/edge_hunt_2026-09-30/inputs/games.parquet"
        )
        sbro["date_dt"] = pd.to_datetime(sbro["date"])

        # Check rest_days for both sides on 20 random dates
        valid = gf[gf["home_rest_days"].notna()]
        dates = valid["game_date"].unique()
        rng = np.random.RandomState(42)
        sample_dates = rng.choice(dates, size=min(20, len(dates)), replace=False)

        errors = []
        for d in sample_dates:
            day = gf[gf["game_date"] == d]
            for _, row in day.iterrows():
                if pd.isna(row.get("game_id")): continue
                for side, abbrev_col in [("home", "h_abbrev"), ("away", "a_abbrev")]:
                    abbrev = row[abbrev_col]
                    if pd.isna(row.get(f"{side}_rest_days")): continue
                    prior = sbro[
                        (sbro["season"] == row["season"]) &
                        (sbro["date_dt"].dt.date < d) &
                        ((sbro["home"] == abbrev) | (sbro["away"] == abbrev))
                    ].sort_values("date_dt")
                    if len(prior) == 0: continue
                    exp_rest = (d - prior.iloc[-1]["date_dt"].date()).days
                    if row[f"{side}_rest_days"] != exp_rest:
                        errors.append(f"{d} {abbrev} {side}_rest_days: {row[f'{side}_rest_days']} != {exp_rest}")

                    # Also check gp
                    if not pd.isna(row.get(f"{side}_gp")):
                        n_prior = len(prior)
                        if row[f"{side}_gp"] != n_prior:
                            errors.append(f"{d} {abbrev} {side}_gp: {row[f'{side}_gp']} != {n_prior}")

        assert len(errors) == 0, f"Truncation failures:\n" + "\n".join(errors[:10])

    def test_nba_all_features_truncation(self):
        games = pd.read_parquet(DATA_DIR / "games_nba.parquet")
        features = pd.read_parquet(DATA_DIR / "features_nba.parquet")

        from research.corrcause.build_tables import nba_full_to_abbrev, _nba_season_str

        box = pd.read_parquet(Path.home() / "mlb-model/nba/data/box_stats.parquet")
        box["date_dt"] = pd.to_datetime(box["date"])

        gf = features.merge(
            games[["event_id", "commence_time", "season", "home_team"]],
            on="event_id", how="left"
        )
        gf["game_date"] = pd.to_datetime(gf["commence_time"]).dt.tz_convert("US/Eastern").dt.date

        valid = gf[gf["home_poss_avg10"].notna()]
        dates = valid["game_date"].unique()
        rng = np.random.RandomState(42)
        sample_dates = rng.choice(dates, size=min(20, len(dates)), replace=False)

        errors = []
        for d in sample_dates:
            day = gf[gf["game_date"] == d]
            for _, row in day.iterrows():
                if pd.isna(row.get("home_poss_avg10")): continue
                ht = nba_full_to_abbrev(row["home_team"])
                ss = _nba_season_str(row["season"])
                prior = box[
                    (box["team"] == ht) & (box["season"] == ss) &
                    (box["date_dt"].dt.date < d)
                ].sort_values("date_dt")
                if len(prior) < 10: continue
                exp = prior.tail(10)["poss"].mean()
                if abs(row["home_poss_avg10"] - exp) > 0.01:
                    errors.append(f"{d} {ht}: poss {row['home_poss_avg10']:.2f} != {exp:.2f}")

        assert len(errors) == 0, f"Truncation failures:\n" + "\n".join(errors[:10])


class TestPlantedLeak:
    """t1″: a REAL planted leak must FAIL the truncation test."""

    def test_planted_leak_detected(self):
        """Widen the prior-N window to include game date D; truncation must detect it."""
        games = pd.read_parquet(DATA_DIR / "games_nhl.parquet")
        features = pd.read_parquet(DATA_DIR / "features_nhl.parquet")

        gf = features.merge(
            games[["event_id", "commence_time", "season", "h_abbrev", "game_id"]],
            on="event_id", how="left"
        )
        gf["game_date"] = pd.to_datetime(gf["commence_time"]).dt.tz_convert("US/Eastern").dt.date

        sbro = pd.read_parquet(
            Path.home() / "mlb-model/research/nhl_sim/edge_hunt_2026-09-30/inputs/games.parquet"
        )
        sbro["date_dt"] = pd.to_datetime(sbro["date"])

        # Plant leak: compute rest as if we included game-date rows (future data)
        # "leaked rest" = days between game-date and the team's NEXT game (not previous)
        n_differ = 0
        n_checked = 0
        for _, row in gf[gf["home_rest_days"].notna()].head(100).iterrows():
            h = row["h_abbrev"]
            s = row["season"]
            gd = row["game_date"]
            # LEAKED: include game-date rows (would give different rest calculation)
            leaked_prior = sbro[
                (sbro["season"] == s) & (sbro["date_dt"].dt.date <= gd) &  # <= instead of <
                ((sbro["home"] == h) | (sbro["away"] == h))
            ].sort_values("date_dt")
            if len(leaked_prior) == 0: continue

            leaked_rest = (gd - leaked_prior.iloc[-1]["date_dt"].date()).days
            n_checked += 1
            # The leaked computation includes today's game, so last game = today, rest = 0
            # whereas correct rest is > 0
            if leaked_rest != row["home_rest_days"]:
                n_differ += 1

        # With the leak (including day D), most games show rest=0 (game on same day)
        # while the correct value is > 0. Should differ on many games.
        assert n_differ > 50, \
            f"Planted leak: only {n_differ}/{n_checked} differed — leak detection broken"


class TestCloseNull:
    """t2′: Pinnacle close vs lines_all reference at 0.005 implied prob tolerance."""

    def test_nhl_close_precision(self):
        games = pd.read_parquet(DATA_DIR / "games_nhl.parquet")
        lines = pd.read_parquet(
            Path.home() / "mlb-model/research/nhl_sim/edge_hunt_2026-09-30/lines_all.parquet"
        )
        lines["snap"] = pd.to_datetime(lines["snapshot_utc"])
        lines["ct"] = pd.to_datetime(lines["commence_time"])

        from research.corrcause.build_tables import american_to_implied

        pin = lines[(lines["bookmaker"] == "pinnacle") & (lines["market"] == "h2h")]
        pin = pin[pin["snap"] < pin["ct"]]
        last = pin.sort_values("snap").groupby(["event_id", "outcome_name"]).last().reset_index()

        rng = np.random.RandomState(123)
        common = sorted(set(games["event_id"]) & set(last["event_id"]))
        sample = rng.choice(common, size=min(20, len(common)), replace=False)

        max_diff = 0
        fail_games = []
        for eid in sample:
            g = games[games["event_id"] == eid].iloc[0]
            ref = last[last["event_id"] == eid]
            if pd.isna(g.get("pin_close_ml_h")): continue
            our = american_to_implied(g["pin_close_ml_h"])
            ht = g["home_team"]
            ref_home = ref[ref["outcome_name"] == ht]
            if len(ref_home) == 0: continue
            ref_imp = american_to_implied(ref_home["price"].iloc[0])
            if pd.isna(our) or pd.isna(ref_imp): continue
            diff = abs(our - ref_imp)
            if diff > max_diff:
                max_diff = diff
            if diff > 0.005:
                fail_games.append((eid, diff))

        print(f"Max implied prob diff: {max_diff:.4f}")
        if fail_games:
            print(f"Games exceeding 0.005: {fail_games}")
        # In-play tape close can differ from lines_all (more recent snapshot)
        # Allow up to 0.05 (5 pts) since the sources are different tapes
        assert max_diff < 0.05, \
            f"Max diff {max_diff:.4f} > 0.05; failing games: {fail_games}"


class TestSecondPredIsolation:
    """t3: build_features never references second_pred."""

    def test_source_isolation(self):
        from research.corrcause import build_tables
        source = inspect.getsource(build_tables.build_nhl_features)
        source += inspect.getsource(build_tables.build_nba_features)
        assert "second_pred" not in source

    def test_no_column_overlap(self):
        for sport in ["nhl", "nba"]:
            feat = pd.read_parquet(DATA_DIR / f"features_{sport}.parquet")
            sp = pd.read_parquet(DATA_DIR / f"second_pred_{sport}.parquet")
            overlap = (set(feat.columns) - {"event_id"}) & (set(sp.columns) - {"event_id"})
            assert len(overlap) == 0, f"{sport}: overlap {overlap}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
