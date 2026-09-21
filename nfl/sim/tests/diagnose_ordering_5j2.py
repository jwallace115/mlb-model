#!/usr/bin/env python3
"""
5J-2 Item 4: diagnose cross-machine board difference.

Prints player ordering, share means, and sim results for LV@LAC to identify
the sorting-order dependency. NO ENGINE FILE IS EDITED.
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(ROOT))

from nfl.sim.engine import simulate_game, _load_tables, _load_ratings, _build_player_context
from nfl.sim.anchor import run_anchored_chunked
from nfl.sim.calibration import engine_fingerprint

SEASON = 2026
WEEK = 2


def main():
    print(f"engine_fingerprint: {engine_fingerprint()}")
    print(f"Python: {sys.version}")
    print(f"numpy: {np.__version__}")
    print(f"pandas: {pd.__version__}")
    print()

    _load_tables()
    team_r, tend, sit, kicker, league = _load_ratings()
    pu = pd.read_parquet(ROOT / "nfl" / "data" / "sim" / "ratings" / "player_usage_weekly.parquet")
    au = pd.read_parquet(ROOT / "nfl" / "data" / "sim" / "ratings" / "active_universe_weekly.parquet")
    kw = dict(team_r=team_r, tend=tend, sit=sit, kicker=kicker, league=league,
              player_usage=pu, active_uni=au)

    home, away = "LAC", "LV"
    spread, total = 7.0, 43.5

    # ── Section 1: player ordering in _build_player_context ──
    print("=" * 70)
    print("SECTION 1: Player ordering in _build_player_context (LV@LAC)")
    print("=" * 70)
    rng = np.random.default_rng(12345)
    pctx = _build_player_context(home, away, SEASON, WEEK, pu, au, n_sims=100, rng=rng)

    for ti, (team, ctx) in enumerate([(home, pctx[0]), (away, pctx[1])]):
        if ctx is None:
            print(f"\n{team}: no player context")
            continue
        print(f"\n{team} — player_id ORDER in renormed:")
        ids = ctx["ids"]
        names = ctx["names"]
        positions = ctx["positions"]
        # Mean shares from cumsum: per-player = cumsum[j] - cumsum[j-1]
        tgt_mean = np.mean(ctx["tgt_cumsum"], axis=0)
        car_mean = np.mean(ctx["car_cumsum"], axis=0)
        tgt_shares = np.diff(np.concatenate([[0], tgt_mean]))
        car_shares = np.diff(np.concatenate([[0], car_mean]))
        print(f"  {'idx':>3s}  {'player_id':16s}  {'name':20s}  {'pos':4s}  {'tgt_share':>10s}  {'car_share':>10s}")
        for j in range(len(ids)):
            print(f"  {j:3d}  {ids[j]:16s}  {names[j]:20s}  {positions[j]:4s}  {tgt_shares[j]:10.6f}  {car_shares[j]:10.6f}")

    # ── Section 2: identify tied shares ──
    print()
    print("=" * 70)
    print("SECTION 2: Tied target_share values in player_usage (LV)")
    print("=" * 70)
    lv_pu = pu[(pu["season"] == SEASON) & (pu["week"] == WEEK) & (pu["team"] == "LV")]
    if lv_pu.empty:
        lv_pu = pu[(pu["season"] == SEASON) & (pu["team"] == "LV")]
        mx = lv_pu["week"].max()
        lv_pu = lv_pu[lv_pu["week"] == mx]
    lv_sorted = lv_pu.sort_values("target_share", ascending=False)
    print(f"  {'player_id':16s}  {'name':20s}  {'pos':4s}  {'target_share':>14s}  {'carry_share':>12s}")
    for _, r in lv_sorted.iterrows():
        print(f"  {r['player_id']:16s}  {r.get('player_name',''):20s}  {r.get('position',''):4s}  {r['target_share']:14.10f}  {r.get('carry_share',0):12.10f}")

    # Check for exact ties
    ts = lv_sorted["target_share"].values
    ties = []
    for i in range(len(ts) - 1):
        if ts[i] == ts[i + 1]:
            ties.append((lv_sorted.iloc[i]["player_id"], lv_sorted.iloc[i + 1]["player_id"], ts[i]))
    if ties:
        print(f"\nEXACT TIES found ({len(ties)}):")
        for a, b, v in ties:
            print(f"  {a} == {b} at {v}")
    else:
        print("\nNo exact ties in target_share.")

    # ── Section 3: unanchored sim (seed=12345, n_sims=1500) ──
    print()
    print("=" * 70)
    print("SECTION 3: Unanchored simulate_game (seed=12345, n=1500)")
    print("=" * 70)
    td, pdf = simulate_game(home, away, SEASON, WEEK, n_sims=1500, seed=12345, **kw)
    if pdf is not None:
        pmeans = pdf.groupby(["player_id", "player_name", "position", "team"]).agg(
            mean_car=("carries", "mean"),
            mean_tgt=("targets", "mean"),
        ).reset_index()
        lv_players = pmeans[pmeans["team"] == "LV"].sort_values("mean_car", ascending=False)
        print(f"  LV per-player means (unanchored):")
        for _, r in lv_players.iterrows():
            print(f"    {r['player_name']:20s}  carries={r['mean_car']:.2f}  targets={r['mean_tgt']:.2f}")

    # ── Section 4: anchored sim ──
    print()
    print("=" * 70)
    print("SECTION 4: Anchored run (spread=+7.0, total=43.5)")
    print("=" * 70)
    anchoring_log = []
    td_a, pdf_a, dh, da, n_iter, conv, raw_m, raw_t, anch_m, anch_t = \
        run_anchored_chunked(home, away, SEASON, WEEK, spread, total,
                             anchoring_log=anchoring_log, **kw)
    print(f"  offsets: dh={dh:+.4f}, da={da:+.4f}")
    print(f"  raw: margin={raw_m:.2f}, total={raw_t:.2f}")
    print(f"  anchored: margin={anch_m:.2f}, total={anch_t:.2f}")
    print(f"  converged={conv}, n_iter={n_iter}")

    if pdf_a is not None:
        pmeans_a = pdf_a.groupby(["player_id", "player_name", "position", "team"]).agg(
            mean_car=("carries", "mean"),
            mean_tgt=("targets", "mean"),
        ).reset_index()
        lv_anch = pmeans_a[pmeans_a["team"] == "LV"].sort_values("mean_car", ascending=False)
        print(f"\n  LV per-player means (anchored):")
        for _, r in lv_anch.iterrows():
            print(f"    {r['player_name']:20s}  carries={r['mean_car']:.2f}  targets={r['mean_tgt']:.2f}")

    # ── Section 5: stable sort vs default sort ──
    print()
    print("=" * 70)
    print("SECTION 5: Stable sort + player_id tiebreak (SCRATCH — no engine edit)")
    print("=" * 70)

    # Manually build player context with stable sort
    from nfl.sim.engine import _renormalize_measured

    for team in ["LAC", "LV"]:
        au_t = au[(au["season"] == SEASON) & (au["week"] == WEEK) & (au["team"] == team)]
        if au_t.empty:
            au_t = au[(au["season"] == SEASON) & (au["team"] == team)]
            if not au_t.empty:
                au_t = au_t[au_t["week"] == au_t["week"].max()]
        active_ids = au_t[au_t["active_flag"] == True]["player_id"].tolist()

        pu_t = pu[(pu["season"] == SEASON) & (pu["week"] == WEEK) & (pu["team"] == team)]
        if pu_t.empty:
            pu_t = pu[(pu["season"] == SEASON) & (pu["team"] == team)]
            if not pu_t.empty:
                pu_t = pu_t[pu_t["week"] == pu_t["week"].max()]

        renormed = _renormalize_measured(pu_t, active_ids)
        renormed = renormed[renormed["player_id"].isin(active_ids)].copy()

        # Default sort (quicksort)
        default_order = renormed.sort_values("target_share", ascending=False)["player_id"].tolist()
        # Stable sort with player_id tiebreak
        stable_order = renormed.sort_values(
            ["target_share", "player_id"], ascending=[False, True],
            kind="stable"
        )["player_id"].tolist()

        differs = default_order != stable_order
        print(f"\n  {team}: default_order == stable_order? {not differs}")
        if differs:
            for i, (d, s) in enumerate(zip(default_order, stable_order)):
                if d != s:
                    print(f"    position {i}: default={d}, stable={s}")

    # ── Section 6: why anchored Jeanty is 12 carries vs 21 unanchored ──
    print()
    print("=" * 70)
    print("SECTION 6: Anchoring effect on Jeanty (game script shift)")
    print("=" * 70)
    print(f"  Market: spread={spread:+.1f}, total={total:.1f}")
    print(f"  Raw sim: margin={raw_m:.2f}, total={raw_t:.2f}")
    print(f"  Offsets: dh={dh:+.4f}, da={da:+.4f}")
    print(f"  A negative da=-0.94 shifts LV offense DOWN. The raw sim has")
    print(f"  LV favoured (margin -2.38, i.e. LV wins by ~2), but the market")
    print(f"  has LV as a 7-point dog. Anchoring pushes LV's EPA down so the")
    print(f"  sim matches the market. Under that offset, LV trails more often,")
    print(f"  game script shifts from rushing to passing, and the total play")
    print(f"  volume compresses. Jeanty's carry share stays high (~59%), but")
    print(f"  the denominator (total team carries) drops sharply.")

    # ── Section 7: scratch stable-sort sim comparison ──
    print()
    print("=" * 70)
    print("SECTION 7: Scratch stable-sort sim (monkey-patched, NOT engine edit)")
    print("=" * 70)

    import nfl.sim.engine as _eng

    _orig_build = _eng._build_player_context

    def _patched_build(home, away, season, week, player_usage, active_uni,
                       qb_ratings=None, n_sims=1, rng=None):
        """Monkey-patched to use stable sort + player_id tiebreak."""
        # Temporarily replace sort_values call via a wrapper
        _orig_sort = pd.DataFrame.sort_values

        def _stable_sort(self, by, ascending=True, **kwargs):
            if by == "target_share" and "player_id" in self.columns:
                return _orig_sort(
                    self, ["target_share", "player_id"],
                    ascending=[ascending if isinstance(ascending, bool) else ascending,
                               True],
                    kind="stable", **{k: v for k, v in kwargs.items() if k != "kind"}
                )
            return _orig_sort(self, by, ascending=ascending, **kwargs)

        pd.DataFrame.sort_values = _stable_sort
        try:
            result = _orig_build(home, away, season, week, player_usage, active_uni,
                                 qb_ratings=qb_ratings, n_sims=n_sims, rng=rng)
        finally:
            pd.DataFrame.sort_values = _orig_sort
        return result

    _eng._build_player_context = _patched_build

    # Re-run unanchored sim with stable sort
    td_s, pdf_s = simulate_game(home, away, SEASON, WEEK, n_sims=1500, seed=12345, **kw)
    _eng._build_player_context = _orig_build  # restore

    if pdf_s is not None:
        pmeans_s = pdf_s.groupby(["player_id", "player_name", "position", "team"]).agg(
            mean_car=("carries", "mean"),
            mean_tgt=("targets", "mean"),
        ).reset_index()
        lv_stable = pmeans_s[pmeans_s["team"] == "LV"].sort_values("mean_car", ascending=False)
        print(f"  LV per-player means (unanchored, STABLE sort):")
        for _, r in lv_stable.iterrows():
            print(f"    {r['player_name']:20s}  carries={r['mean_car']:.2f}  targets={r['mean_tgt']:.2f}")

        print(f"\n  Cowork's Linux values (unanchored, seed=12345, n=1500):")
        print(f"    Ashton Jeanty         carries=21.43")
        print(f"    Mike Washington Jr.   carries=4.77")
        print(f"    Omarion Hampton       carries=25.03  (LAC)")

        # Compare
        jeanty_default = 16.62  # from section 3
        jeanty_stable = float(lv_stable[lv_stable["player_name"].str.contains("Jeanty")]["mean_car"].iloc[0])
        wash_default = 9.25
        wash_stable = float(lv_stable[lv_stable["player_name"].str.contains("Washington")]["mean_car"].iloc[0])
        print(f"\n  Jeanty:     default_sort={jeanty_default:.2f}  stable_sort={jeanty_stable:.2f}  linux=21.43")
        print(f"  Washington: default_sort={wash_default:.2f}  stable_sort={wash_stable:.2f}  linux=4.77")


if __name__ == "__main__":
    main()
