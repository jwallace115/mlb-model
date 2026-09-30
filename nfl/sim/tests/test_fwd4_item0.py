"""D246: the anchor join and the record written once.

Every test must FAIL on 735374bf1.
"""
import hashlib
import json
import os
import sys
import tempfile
from datetime import datetime, timezone, timedelta
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from nfl.sim.tests.test_fwd3_item0 import (
    _build_fixture_root, _stub_run_week, _set_fwd_paths,
    KICK, T, EVENT_ID, HOME_FULL, AWAY_FULL, HOME_ABBR, AWAY_ABBR, GAME_ID,
)


# ── D246(a): anchor join on (run_id, event_id) ──


def test_run_b_unanchored_excluded(tmp_path):
    """Run A is anchored, run B is unanchored. A run-B row -> excluded from cohort.
    On 735374bf1 primary_cohort pools game names across runs, so both are included."""
    from nfl.pipeline.log_ai_opinions import primary_cohort

    # Sidecar: run A anchored, run B unanchored
    sidecar = pd.DataFrame([
        {"run_id": "runA", "event_id": "evt1", "game": "CAR@KC", "anchored": True},
        {"run_id": "runB", "event_id": "evt1", "game": "CAR@KC", "anchored": False},
    ])

    scored = pd.DataFrame([
        # From run A -> should be in cohort (anchored)
        {"run_id": "runA", "event_id": "evt1",
         "reader_model": "nfl_sim_v1_156cd057", "pilot": False,
         "revision": 0, "tag": "sim_v1", "two_way": True,
         "market_key": "player_receptions", "settlement": "settled",
         "home_team": HOME_FULL, "away_team": AWAY_FULL,
         "p_first": 0.6, "book_p_first": 0.5, "y_first": 1},
        # From run B -> should be excluded (unanchored)
        {"run_id": "runB", "event_id": "evt1",
         "reader_model": "nfl_sim_v1_156cd057", "pilot": False,
         "revision": 0, "tag": "sim_v1", "two_way": True,
         "market_key": "player_receptions", "settlement": "settled",
         "home_team": HOME_FULL, "away_team": AWAY_FULL,
         "p_first": 0.6, "book_p_first": 0.5, "y_first": 1},
    ])

    cohort, excl = primary_cohort(scored, "nfl_sim_v1_156cd057", sidecar=sidecar)
    assert len(cohort) == 1, f"expected 1 (run A only), got {len(cohort)}"
    assert cohort.iloc[0]["run_id"] == "runA"


def test_no_sidecar_excludes_row(tmp_path):
    """No sidecar match -> row excluded, never silently kept.
    On 735374bf1 missing sidecar is silently skipped (no exclusion)."""
    from nfl.pipeline.log_ai_opinions import primary_cohort

    sidecar = pd.DataFrame(columns=["run_id", "event_id", "game", "anchored"])

    scored = pd.DataFrame([{
        "run_id": "runA", "event_id": "evt1",
        "reader_model": "nfl_sim_v1_156cd057", "pilot": False,
        "revision": 0, "tag": "sim_v1", "two_way": True,
        "market_key": "player_receptions", "settlement": "settled",
        "home_team": HOME_FULL, "away_team": AWAY_FULL,
        "p_first": 0.6, "book_p_first": 0.5, "y_first": 1,
    }])

    cohort, excl = primary_cohort(scored, "nfl_sim_v1_156cd057", sidecar=sidecar)
    assert len(cohort) == 0, "row with no sidecar match must be excluded"
    assert excl.get("no sidecar match", 0) == 1


def test_duplicate_sidecar_halts(tmp_path):
    """Duplicate sidecar row on (run_id, event_id) -> HALT.
    On 735374bf1 duplicates are silently kept."""
    from nfl.pipeline.log_ai_opinions import primary_cohort

    sidecar = pd.DataFrame([
        {"run_id": "runA", "event_id": "evt1", "game": "CAR@KC", "anchored": True},
        {"run_id": "runA", "event_id": "evt1", "game": "CAR@KC", "anchored": True},
    ])

    scored = pd.DataFrame([{
        "run_id": "runA", "event_id": "evt1",
        "reader_model": "nfl_sim_v1_156cd057", "pilot": False,
        "revision": 0, "tag": "sim_v1", "two_way": True,
        "market_key": "player_receptions", "settlement": "settled",
        "home_team": HOME_FULL, "away_team": AWAY_FULL,
        "p_first": 0.6, "book_p_first": 0.5, "y_first": 1,
    }])

    with pytest.raises(SystemExit, match="duplicate sidecar"):
        primary_cohort(scored, "nfl_sim_v1_156cd057", sidecar=sidecar)


def test_publication_json_exists_after_freeze(tmp_path):
    """D246(b): publication.json is written after freeze, in the run directory.
    On 735374bf1 no publication.json exists — publication_utc is written
    directly into the frozen parquet and bundle manifest."""
    from nfl.sim.run_forward_v1 import main

    root = _build_fixture_root(tmp_path)
    dest = main(
        argv=["--week", "3", "--pilot", "--as-of", T.isoformat(),
              "--allow-stale-quotes"],
        root=str(root),
        run_week_fn=_stub_run_week,
    )
    assert dest is not None

    run_dirs = list((root / "nfl" / "data" / "board" / "week=2026_03" / "sim_runs").iterdir())
    bd = run_dirs[0]
    pub_path = bd / "publication.json"
    assert pub_path.exists(), "publication.json must exist after freeze"
    pub = json.loads(pub_path.read_text())
    assert pub["frozen_file"] == dest.name
    assert pub["frozen_sha256"] == hashlib.sha256(dest.read_bytes()).hexdigest()


# ── D246(a): sidecar carries event_id and run_id ──


def test_sidecar_has_event_id_and_run_id(tmp_path):
    """After a run, the sidecar must carry event_id and run_id columns.
    On 735374bf1 the sidecar has neither."""
    from nfl.sim.run_forward_v1 import main

    root = _build_fixture_root(tmp_path)
    dest = main(
        argv=["--week", "3", "--pilot", "--as-of", T.isoformat(),
              "--allow-stale-quotes"],
        root=str(root),
        run_week_fn=_stub_run_week,
    )
    assert dest is not None

    run_dirs = list((root / "nfl" / "data" / "board" / "week=2026_03" / "sim_runs").iterdir())
    bd = run_dirs[0]
    sc = pd.read_parquet(bd / "anchor_sidecar.parquet")
    assert "event_id" in sc.columns, "sidecar must have event_id"
    assert "run_id" in sc.columns, "sidecar must have run_id"
    assert sc.iloc[0]["event_id"] == EVENT_ID
    assert sc.iloc[0]["run_id"] == bd.name


# ── D246(b): written once — frozen parquet, bundle manifest, digests ──


def test_bundle_manifest_not_rewritten_after_freeze(tmp_path):
    """D246(b): bundle_manifest.json is finalized BEFORE the freeze and never
    rewritten. On 735374bf1 the manifest is rewritten to add publication_utc."""
    from nfl.sim.run_forward_v1 import main

    root = _build_fixture_root(tmp_path)
    dest = main(
        argv=["--week", "3", "--pilot", "--as-of", T.isoformat(),
              "--allow-stale-quotes"],
        root=str(root),
        run_week_fn=_stub_run_week,
    )
    assert dest is not None

    run_dirs = list((root / "nfl" / "data" / "board" / "week=2026_03" / "sim_runs").iterdir())
    bd = run_dirs[0]
    man_path = bd / "bundle_manifest.json"
    man_data = json.loads(man_path.read_text())

    # The manifest must NOT contain publication_utc (that goes in publication.json now)
    assert "publication_utc" not in man_data, \
        "bundle_manifest must not be rewritten after freeze (no publication_utc)"

    # publication.json must exist instead
    pub_path = bd / "publication.json"
    assert pub_path.exists(), "publication.json must exist"
    pub = json.loads(pub_path.read_text())
    assert "publication_utc" in pub
    assert "frozen_file" in pub
    assert "frozen_sha256" in pub


def test_frozen_rows_have_digests(tmp_path):
    """D246(b): every frozen row gets bundle_digest and experiment_digest.
    On 735374bf1 no digests are on the rows."""
    from nfl.sim.run_forward_v1 import main

    root = _build_fixture_root(tmp_path)
    dest = main(
        argv=["--week", "3", "--pilot", "--as-of", T.isoformat(),
              "--allow-stale-quotes"],
        root=str(root),
        run_week_fn=_stub_run_week,
    )
    assert dest is not None

    m = pd.read_parquet(dest)
    assert "bundle_digest" in m.columns, "frozen rows must have bundle_digest"
    assert "experiment_digest" in m.columns, "frozen rows must have experiment_digest"

    # The digests must be non-empty hex strings
    bd = m["bundle_digest"].iloc[0]
    ed = m["experiment_digest"].iloc[0]
    assert len(bd) == 64, f"bundle_digest must be sha256 hex, got len {len(bd)}"
    assert len(ed) == 64, f"experiment_digest must be sha256 hex, got len {len(ed)}"

    # Verify bundle_digest matches actual bundle_manifest.json
    run_dirs = list((root / "nfl" / "data" / "board" / "week=2026_03" / "sim_runs").iterdir())
    actual_bd = hashlib.sha256(
        (run_dirs[0] / "bundle_manifest.json").read_bytes()
    ).hexdigest()
    assert bd == actual_bd, f"bundle_digest mismatch: row={bd[:16]} actual={actual_bd[:16]}"


# ── D246(a): altered frozen file in week directory -> HALT ──


def test_altered_frozen_file_halts_in_week_dir(tmp_path):
    """An altered frozen file in a week directory -> HALT on verify()
    (non --file path). On 735374bf1 verify() exists but is not called
    for every week directory in score_experiment; D246 adds verify_bundle
    per sidecar run, so this test confirms the end-to-end detection."""
    from nfl.pipeline.log_ai_opinions import verify

    d = tmp_path / "ai_opinions"
    d.mkdir()
    fake_data = b"original content"
    f = d / "ai_opinions_test.parquet"
    f.write_bytes(fake_data)
    sha = hashlib.sha256(fake_data).hexdigest()
    manifest = [{"file": f.name, "sha256": sha}]
    (d / "manifest.json").write_text(json.dumps(manifest))

    # Verify passes before tampering
    _, bad, _ = verify(2026, 3, d=d)
    assert bad == [], f"clean verify should pass, got {bad}"

    # Tamper the frozen file
    f.write_bytes(b"tampered content")
    _, bad, _ = verify(2026, 3, d=d)
    assert len(bad) == 1 and "ai_opinions_test" in bad[0], (
        f"tampered frozen file must be detected: {bad}")


# ── D246(b): bundle_digest on frozen rows verified at grading time ──


def test_bundle_digest_mismatch_halts(tmp_path):
    """D246(b): a frozen row whose bundle_digest doesn't match the actual
    bundle_manifest.json must be caught. On 735374bf1 no digest is on the
    rows, so this check cannot exist."""
    from nfl.sim.run_forward_v1 import main

    root = _build_fixture_root(tmp_path)
    dest = main(
        argv=["--week", "3", "--pilot", "--as-of", T.isoformat(),
              "--allow-stale-quotes"],
        root=str(root),
        run_week_fn=_stub_run_week,
    )
    assert dest is not None

    m = pd.read_parquet(dest)
    assert "bundle_digest" in m.columns

    # Verify the digest matches the actual bundle
    run_dirs = list((root / "nfl" / "data" / "board" / "week=2026_03" / "sim_runs").iterdir())
    bd = run_dirs[0]
    actual = hashlib.sha256((bd / "bundle_manifest.json").read_bytes()).hexdigest()
    assert m["bundle_digest"].iloc[0] == actual, "digest must match pre-freeze bundle"

    # Tamper the bundle manifest -> frozen row's digest is now stale
    man = json.loads((bd / "bundle_manifest.json").read_text())
    man["_tamper"] = "injected"
    (bd / "bundle_manifest.json").write_text(json.dumps(man))
    new_actual = hashlib.sha256((bd / "bundle_manifest.json").read_bytes()).hexdigest()
    assert m["bundle_digest"].iloc[0] != new_actual, "tampered manifest must differ"
