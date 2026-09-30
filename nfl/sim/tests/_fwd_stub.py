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

RATINGS_FILES = [
    "team_ratings_weekly.parquet", "tendencies_weekly.parquet",
    "tendencies_situational_weekly.parquet", "qb_ratings_weekly.parquet",
    "kicker_weekly.parquet", "league_baselines.parquet",
    "player_usage_weekly.parquet", "active_universe_weekly.parquet",
]


def add_fwd6_fixture_inputs(root, played_week=2, teams=(("KC", "CAR"),)):
    """Copy every prediction input a forward run needs and write a minimal PBP file in
    which each (home, away) pair completed a game in `played_week` (an END GAME row)."""
    root = Path(root)
    rd = root / "nfl" / "data" / "sim" / "ratings"
    rd.mkdir(parents=True, exist_ok=True)
    for f in RATINGS_FILES:
        shutil.copy2(REPO / "nfl" / "data" / "sim" / "ratings" / f, rd / f)
    pbp_dir = root / "nfl" / "data" / "pbp"
    pbp_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(REPO / "nfl" / "data" / "pbp" / "rosters_weekly.parquet",
                 pbp_dir / "rosters_weekly.parquet")
    rows = []
    for home, away in teams:
        gid = f"2026_{played_week:02d}_{away}_{home}"
        for desc in ("kickoff", "END GAME"):
            rows.append({"game_id": gid, "season": 2026, "week": played_week,
                         "home_team": home, "away_team": away, "home_score": 24,
                         "away_score": 17, "desc": desc})
    pd.DataFrame(rows).to_parquet(pbp_dir / "pbp_2026.parquet", index=False)


def _sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def write_read_set(out_dir, input_dir, props_file, extra=()):
    """A read set listing every required input (and the bundle props) with real hashes."""
    from nfl.sim.read_set import MUST_READ
    entries = [{"path": str((Path(input_dir) / f).resolve()), "sha256": _sha(Path(input_dir) / f),
                "reads": 1} for f in MUST_READ]
    entries.append({"path": str(Path(props_file).resolve()), "sha256": _sha(props_file), "reads": 1})
    entries += list(extra)
    doc = {"entries": entries, "conflicts": [], "network_attempts": []}
    (Path(out_dir) / "read_set.json").write_text(json.dumps(doc, indent=1) + "\n")


def write_stub_outputs(out_dir, week, run_id, input_dir, props_file, game_id, picks,
                       anchor=None, season=2026, identity_override=None):
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
        ar = pd.DataFrame(anchor or [{"game": game_id, "iterations": 1, "converged": True,
                                      "anch_m": -3.1, "anch_t": 45.6,
                                      "target_spread": -3.0, "target_total": 45.5}])
        for k, v in ident.items():
            ar[k] = v
        ar.to_parquet(out_dir / "anchor_returned.parquet", index=False)
    if input_dir is not None:
        write_read_set(out_dir, input_dir, props_file)
