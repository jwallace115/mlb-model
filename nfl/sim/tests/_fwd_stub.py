"""FWD6 test helpers: fixture inputs a forward run now requires, and a stub run_week that
writes what the real run_week writes in forward-run mode (identity columns, the solver's
returned anchor state, and a read set).

The stub's read set records the bundle inputs it "read" with their real hashes, so the
harness's read-set proof runs for real on every stub-driven test. Tests of the read-set
mechanism itself use the real run_week (test_fwd6_item0.py).
"""
import hashlib
import json
import shutil
from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parents[3]
# D260: a COMMITTED roster fixture (2026 KC/CAR/PIT/CLE rows of nflverse rosters_weekly),
# so the suite never depends on the gitignored production roster.
ROSTER_FIXTURE = Path(__file__).resolve().parent / "fixtures" / "rosters_weekly_fixture.parquet"

RATINGS_FILES = [
    "team_ratings_weekly.parquet", "tendencies_weekly.parquet",
    "tendencies_situational_weekly.parquet", "qb_ratings_weekly.parquet",
    "kicker_weekly.parquet", "league_baselines.parquet",
    "player_usage_weekly.parquet", "active_universe_weekly.parquet",
]


def add_fwd6_fixture_inputs(root, played_week=2, teams=(("KC", "CAR"),), kick=None,
                            target_week=3):
    """Copy every prediction input a forward run needs (ratings from the repo, the roster
    FIXTURE), write a minimal PBP file in which each (home, away) pair completed a game in
    `played_week` (an END GAME row), and a schedule snapshot holding each pair's
    target-week game at `kick`."""
    root = Path(root)
    rd = root / "nfl" / "data" / "sim" / "ratings"
    rd.mkdir(parents=True, exist_ok=True)
    for f in RATINGS_FILES:
        shutil.copy2(REPO / "nfl" / "data" / "sim" / "ratings" / f, rd / f)
    pbp_dir = root / "nfl" / "data" / "pbp"
    pbp_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(ROSTER_FIXTURE, pbp_dir / "rosters_weekly.parquet")
    # record-only inputs (copied into the run, not read by the prediction): tiny synthetic
    # files so the copy is always exercised
    pd.DataFrame([{"season": 2026, "week": played_week, "team": t, "full_name": "Fixture Player",
                   "report_status": "Questionable"} for pair in teams for t in pair]
                 ).to_parquet(pbp_dir / "injuries.parquet", index=False)
    pd.DataFrame([{"season": None, "dt": "2026-09-30", "team": t, "pos_abb": "QB",
                   "player_name": "Fixture QB", "pos_rank": 1} for pair in teams for t in pair]
                 ).to_parquet(pbp_dir / "depth_charts.parquet", index=False)
    rows = []
    for home, away in teams:
        gid = f"2026_{played_week:02d}_{away}_{home}"
        for desc in ("kickoff", "END GAME"):
            rows.append({"game_id": gid, "season": 2026, "week": played_week,
                         "home_team": home, "away_team": away, "home_score": 24,
                         "away_score": 17, "desc": desc})
    pd.DataFrame(rows).to_parquet(pbp_dir / "pbp_2026.parquet", index=False)
    if kick is not None:
        from zoneinfo import ZoneInfo
        k_et = kick.astimezone(ZoneInfo("America/New_York"))
        sched = [{"game_id": f"2026_{target_week:02d}_{away}_{home}", "season": 2026,
                  "game_type": "REG", "week": target_week, "gameday": k_et.strftime("%Y-%m-%d"),
                  "gametime": k_et.strftime("%H:%M"), "home_team": home, "away_team": away}
                 for home, away in teams]
        pd.DataFrame(sched).to_parquet(pbp_dir / "schedules_2026.parquet", index=False)


def _sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def write_read_set(out_dir, input_dir, props_file, extra=(), bundle_dir=None):
    """A read set listing every required input and bundle file with real hashes."""
    from nfl.sim.read_set import MUST_READ, MUST_READ_BUNDLE
    entries = [{"path": str((Path(input_dir) / f).resolve()), "sha256": _sha(Path(input_dir) / f),
                "reads": 1} for f in MUST_READ]
    bdir = Path(bundle_dir) if bundle_dir is not None else Path(props_file).parent
    entries += [{"path": str((bdir / f).resolve()), "sha256": _sha(bdir / f), "reads": 1}
                for f in MUST_READ_BUNDLE]
    entries += list(extra)
    doc = {"entries": entries, "conflicts": [], "network_attempts": []}
    (Path(out_dir) / "read_set.json").write_text(json.dumps(doc, indent=1) + "\n")


def write_stub_outputs(out_dir, week, run_id, input_dir, props_file, game_id, picks,
                       anchor=None, season=2026, identity_override=None, bundle_dir=None):
    """picks: list of dicts (game_id, player_id, player_name, family, line, cal_p, side, tier)."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    ident = {"season": season, "week": int(week), "run_id": run_id}
    if identity_override:
        ident.update(identity_override)
    pdf = pd.DataFrame(picks, columns=["game_id", "player_id", "player_name", "family",
                                       "line", "cal_p", "side", "tier"])
    for k, v in ident.items():
        pdf[k] = v
    pdf.to_parquet(out_dir / "picks_log.parquet", index=False)
    alog = pd.DataFrame([{"game": game_id, "iter": 0, "margin": -3.1, "total": 45.6,
                          "err_m": -0.1, "err_t": 0.1, "converged": True}])
    for k, v in ident.items():
        alog[k] = v
    alog.to_parquet(out_dir / "anchoring_log.parquet", index=False)
    if anchor is not False:
        tgt = {"spread": -3.0, "total": 45.5}
        if bundle_dir is not None:
            from nfl.sim.run_forward_v1 import lines_dict_from_bundle
            tgt = lines_dict_from_bundle(Path(bundle_dir)).get(game_id, tgt)
        ar = pd.DataFrame(anchor or [{"game": game_id, "iterations": 1, "converged": True,
                                      "anch_m": tgt["spread"] - 0.1, "anch_t": tgt["total"] + 0.1,
                                      "target_spread": tgt["spread"],
                                      "target_total": tgt["total"]}])
        for k, v in ident.items():
            ar[k] = v
        ar.to_parquet(out_dir / "anchor_returned.parquet", index=False)
    if bundle_dir is not None:
        # what the real worker writes: its invocation, read from the bundle itself
        from nfl.sim.run_forward_v1 import lines_dict_from_bundle
        lines = lines_dict_from_bundle(Path(bundle_dir))
        fr = json.loads((Path(bundle_dir) / "freshness.json").read_text())
        (out_dir / "invocation.json").write_text(json.dumps(
            {"season": season, "week": int(week), "run_id": run_id, "cutoff_T": fr["cutoff_T"],
             "bundle_dir": str(bundle_dir), "lines": lines, "games": sorted(lines)},
            indent=1, sort_keys=True) + "\n")
    if input_dir is not None:
        write_read_set(out_dir, input_dir, props_file, bundle_dir=bundle_dir)
