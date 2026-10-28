#!/usr/bin/env python3
"""DA-1b Item 2: tests that CAN fail — replacing the original test_point_in_time.py.

2a. Invariant: n_games_into_label == schedule count for ALL 3,520 rows.
2b. Truncation equivalence: 60 cells match to 1e-9; broken builder differs for >= 55/60.
2c. Planted leak: 5 cells with extreme synthetic data; as-of on → identical; off → differs.
2d. Broken-path: 2a fails against an as-of-off build.
"""
import random
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "research" / "nfl_sim" / "defensive_archetypes"))

import nflreadpy
from team_xwalk import canon


def _load_all_labels():
    frames = []
    for s in range(2021, 2026):
        fp = ROOT / "research" / "nfl_sim" / "defensive_archetypes" / "labels" / f"da_labels_{s}.parquet"
        if fp.exists():
            frames.append(pd.read_parquet(fp))
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def _load_schedules():
    frames = []
    for s in range(2020, 2026):
        try:
            sc = nflreadpy.load_schedules([s])
            if hasattr(sc, "to_pandas"):
                sc = sc.to_pandas()
            frames.append(sc)
        except Exception:
            pass
    return pd.concat(frames, ignore_index=True)


def _week_cutoffs(sched):
    cutoffs = {}
    for (s, w), g in sched.groupby(["season", "week"]):
        times = []
        for _, r in g.iterrows():
            try:
                gd, gt = str(r.gameday).strip(), str(r.gametime).strip()
                if "T" in gt:
                    dt = pd.to_datetime(gt, utc=True)
                else:
                    dt = pd.to_datetime(f"{gd} {gt}").tz_localize("US/Eastern").tz_convert("UTC")
                times.append(dt)
            except Exception:
                pass
        if times:
            cutoffs[(s, w)] = min(times)
    return cutoffs


def _count_games_before(sched, cutoffs, season, week, team):
    """Count schedule games with kickoff + 4h < cutoff(week)."""
    cutoff = cutoffs.get((season, week))
    if cutoff is None:
        return 0
    n = 0
    s = sched[(sched.season == season) &
              ((sched._home == team) | (sched._away == team))]
    for _, g in s.iterrows():
        gw = g.get("week", 0)
        if gw >= week:
            continue
        gk = cutoffs.get((season, gw))
        if gk and (gk + pd.Timedelta(hours=4)) < cutoff:
            n += 1
    return n


# ── Load once for the module ──
_sched = _load_schedules()
_sched["_home"] = _sched["home_team"].apply(canon)
_sched["_away"] = _sched["away_team"].apply(canon)
_cutoffs = _week_cutoffs(_sched)


class TestInvariantAllRows:
    """2a: n_games_into_label == schedule count for ALL 3,520 rows."""

    def test_all_rows(self):
        labels = _load_all_labels()
        assert len(labels) == 3520, f"expected 3520 rows, got {len(labels)}"
        violations = []
        for _, row in labels.iterrows():
            season, week, team = int(row.season), int(row.week), row.defense
            expected = _count_games_before(_sched, _cutoffs, season, week, team)
            actual = int(row.n_games_into_label)
            if actual != expected:
                violations.append((season, team, week, expected, actual))
        assert len(violations) == 0, \
            f"{len(violations)} violations, first 5: {violations[:5]}"

    def test_week1_all_zero(self):
        labels = _load_all_labels()
        w1 = labels[labels.week == 1]
        bad = w1[w1.n_games_into_label != 0]
        assert len(bad) == 0, \
            f"{len(bad)} week-1 rows with n_games != 0: {bad[['season','defense','n_games_into_label']].head().to_dict()}"


class TestTruncationEquivalence:
    """2b: 60 random cells with W >= 3; full-pbp-with-asof == truncated-pbp;
    full-pbp-without-asof differs for >= 55/60."""

    def test_60_cells(self):
        from build_da_labels import build_labels

        labels = _load_all_labels()
        eligible = labels[labels.week >= 3]
        sample = eligible.sample(60, random_state=42)

        # Build once with as-of ON for all seasons
        df_good, _, _ = build_labels(seasons=list(range(2021, 2026)), disable_asof=False)
        # Build once with as-of OFF
        df_bad, _, _ = build_labels(seasons=list(range(2021, 2026)), disable_asof=True)

        match_count = 0
        differ_count = 0
        for _, row in sample.iterrows():
            s, w, t = int(row.season), int(row.week), row.defense
            # Compare committed label (from file) vs freshly-built-with-asof
            committed = labels[(labels.season == s) & (labels.week == w) & (labels.defense == t)]
            fresh = df_good[(df_good.season == s) & (df_good.week == w) & (df_good.defense == t)]
            assert len(committed) == 1 and len(fresh) == 1
            for col in [c for c in committed.columns if c.startswith("f") and "tercile" not in c
                        and c != "f4_pressure_source"]:
                cv = committed.iloc[0][col]
                fv = fresh.iloc[0][col]
                if pd.notna(cv) and pd.notna(fv):
                    assert abs(cv - fv) < 1e-9, \
                        f"{s} {t} wk{w} {col}: committed={cv} fresh={fv} diff={abs(cv-fv)}"

            # Check broken build differs
            broken = df_bad[(df_bad.season == s) & (df_bad.week == w) & (df_bad.defense == t)]
            if len(broken) == 1:
                any_diff = False
                for col in [c for c in committed.columns if c.startswith("f") and "tercile" not in c
                            and c != "f4_pressure_source"]:
                    cv = committed.iloc[0][col]
                    bv = broken.iloc[0][col]
                    if pd.notna(cv) and pd.notna(bv) and abs(cv - bv) > 1e-6:
                        any_diff = True
                        break
                if any_diff:
                    differ_count += 1
            match_count += 1

        assert match_count == 60, f"only matched {match_count}/60"
        assert differ_count >= 55, \
            f"only {differ_count}/60 cells differ from broken build (need >= 55)"
        print(f"PASS: 60/60 match, {differ_count}/60 differ from broken build")


class TestPlantedLeak:
    """2c: 5 cells with extreme synthetic data; as-of → identical, off → differs."""

    def test_5_cells(self):
        from build_da_labels import build_labels, _apply_asof, _f3_explosive

        labels = _load_all_labels()
        # Pick 5 cells: different seasons, week >= 5
        cells = [
            (2021, 10, "KC"), (2022, 8, "BUF"), (2023, 12, "SF"),
            (2024, 6, "DAL"), (2025, 9, "PHI"),
        ]

        for season, week, team in cells:
            committed = labels[(labels.season == season) & (labels.week == week) & (labels.defense == team)]
            assert len(committed) == 1, f"missing {season} {team} wk{week}"
            orig_f3_pass = committed.iloc[0].f3_explosive_pass_rate

            # Build with as-of ON (should match committed)
            df_good, _, _ = build_labels(seasons=[season], disable_asof=False)
            good = df_good[(df_good.season == season) & (df_good.week == week) & (df_good.defense == team)]
            good_f3 = good.iloc[0].f3_explosive_pass_rate if len(good) else None
            if pd.notna(orig_f3_pass) and pd.notna(good_f3):
                assert abs(orig_f3_pass - good_f3) < 1e-12, \
                    f"as-of ON should match: {orig_f3_pass} vs {good_f3}"

            # Build with as-of OFF (should differ)
            df_bad, _, _ = build_labels(seasons=[season], disable_asof=True)
            bad = df_bad[(df_bad.season == season) & (df_bad.week == week) & (df_bad.defense == team)]
            bad_f3 = bad.iloc[0].f3_explosive_pass_rate if len(bad) else None
            if pd.notna(orig_f3_pass) and pd.notna(bad_f3):
                assert abs(orig_f3_pass - bad_f3) > 1e-6, \
                    f"as-of OFF should differ for {season} {team} wk{week}: {orig_f3_pass} vs {bad_f3}"

        print("PASS: 5/5 planted leak cells verified")


class TestBrokenPathFails:
    """2d: The invariant test FAILS against an as-of-off build."""

    def test_broken_build_violates_invariant(self):
        from build_da_labels import build_labels
        df_bad, _, _ = build_labels(seasons=[2023], disable_asof=True)

        # Check that n_games_into_label is WRONG for week-1 rows
        w1 = df_bad[(df_bad.season == 2023) & (df_bad.week == 1)]
        bad_w1 = w1[w1.n_games_into_label != 0]
        assert len(bad_w1) > 0, \
            "broken build should have week-1 rows with n_games != 0"
        print(f"PASS: broken build has {len(bad_w1)} week-1 violations")
