"""D258 (FWD6 item 2): the experiment's canonical reader is reserved, and every
publication has a durable receipt.

Audit #8 (A2): the shared logger wrote a fresh canonical-reader, revision-0 opinion that
the pinned verifier and scorer accepted; deleting publication.json after a genuine
freeze left verify_bundle clean. Every test fails on e0fc3d2d6.
"""
import hashlib
import json
import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "nfl" / "pipeline" / "tests"))

from nfl.sim.tests.test_fwd3_item0 import _build_fixture_root, _stub_run_week, T  # noqa: E402

CANON = "nfl_sim_v1_156cd057"


def _harness(root):
    from nfl.sim.run_forward_v1 import main
    return main(argv=["--week", "3", "--pilot", "--as-of", T.isoformat(),
                      "--allow-stale-quotes"], root=str(root), run_week_fn=_stub_run_week)


def _run_dir(root):
    return next((root / "nfl" / "data" / "board" / "week=2026_03" / "sim_runs").iterdir())


# ── (a) the canonical reader is reserved ──

def test_shared_logger_refuses_canonical_reader(tmp_path):
    """The auditor's A2 write: a canonical-reader freeze through the shared logger HALTs,
    in any spelling, so it can neither be scored nor block the harness's first freeze."""
    import test_ai_opinions_n59 as T59
    from nfl.pipeline import log_ai_opinions as L
    s = L.build_sheet(T59._props(), T59._lines(), T59.NOW)
    for reader in (CANON, f"  {CANON} ", CANON.upper()):
        with pytest.raises(SystemExit, match="reserved for a forward experiment"):
            L.freeze(s, T59._filled(s), 2026, 4, False, T59.NOW, d=tmp_path / "w4",
                     reader_model=reader)
    assert not list((tmp_path / "w4").glob("ai_opinions_*.parquet")) if (tmp_path / "w4").exists() else True


def test_reserved_readers_come_from_the_experiment_manifests():
    from nfl.pipeline.log_ai_opinions import reserved_readers
    em = json.loads((ROOT / "research" / "nfl_sim" / "FWD_EXPERIMENT_v1.json").read_text())
    assert em["canonical_reader"] in reserved_readers()


def test_shared_logger_still_freezes_other_readers(tmp_path):
    import test_ai_opinions_n59 as T59
    from nfl.pipeline import log_ai_opinions as L
    s = L.build_sheet(T59._props(), T59._lines(), T59.NOW)
    dest, sha, m = L.freeze(s, T59._filled(s), 2026, 4, False, T59.NOW, d=tmp_path / "w4",
                            reader_model="claude-opus-5-5")
    assert dest.exists() and (m["revision"] == 0).all()


# ── (b) receipts ──

def test_freeze_writes_a_complete_receipt(tmp_path):
    from nfl.sim.run_forward_v1 import load_receipts, receipt_status
    root = _build_fixture_root(tmp_path)
    dest = _harness(root)
    bd = _run_dir(root)
    recs = load_receipts(root)
    assert len(recs) == 1
    r = recs[0]
    assert r["run_id"] == bd.name
    assert r["frozen_sha256"] == hashlib.sha256(Path(dest).read_bytes()).hexdigest()
    assert r["bundle_digest"] == hashlib.sha256((bd / "bundle_manifest.json").read_bytes()).hexdigest()
    assert r["experiment_digest"] == hashlib.sha256(
        (root / "research" / "nfl_sim" / "FWD_EXPERIMENT_v1.json").read_bytes()).hexdigest()
    assert r["publication_json_sha256"] == hashlib.sha256((bd / "publication.json").read_bytes()).hexdigest()
    assert r["pilot"] is True
    assert receipt_status(bd.name, root) == "complete"


def test_deleting_publication_json_is_detected(tmp_path):
    """Audit #8: deleting publication.json after a genuine freeze left verify_bundle clean."""
    from nfl.sim.run_forward_v1 import verify_bundle, receipt_status
    root = _build_fixture_root(tmp_path)
    _harness(root)
    bd = _run_dir(root)
    (bd / "publication.json").unlink()
    assert any("publication.json missing" in b for b in verify_bundle(bd))
    assert receipt_status(bd.name, root) == "mismatch"


def test_edited_publication_json_is_detected(tmp_path):
    from nfl.sim.run_forward_v1 import verify_bundle
    root = _build_fixture_root(tmp_path)
    _harness(root)
    bd = _run_dir(root)
    pub = json.loads((bd / "publication.json").read_text())
    pub["publication_utc"] = "2099-01-01T16:00:00+00:00"
    (bd / "publication.json").write_text(json.dumps(pub))
    assert any("differs from its receipt" in b for b in verify_bundle(bd))


def test_freeze_without_receipt_is_not_complete(tmp_path, monkeypatch):
    """A frozen file whose receipt was never written is 'no receipt' — not a completed freeze."""
    import nfl.sim.run_forward_v1 as fwd
    root = _build_fixture_root(tmp_path)
    monkeypatch.setattr(fwd, "append_receipt", lambda root, receipt: None)
    _harness(root)
    assert fwd.receipt_status(_run_dir(root).name, root) == "no receipt"


def test_unlisted_file_in_run_directory_is_detected(tmp_path):
    from nfl.sim.run_forward_v1 import verify_bundle
    root = _build_fixture_root(tmp_path)
    _harness(root)
    bd = _run_dir(root)
    (bd / "outputs" / "planted.parquet").write_bytes(b"x")
    assert any("unlisted file: outputs/planted.parquet" in b for b in verify_bundle(bd))


def test_frozen_rows_carry_the_real_experiment_digest(tmp_path):
    """Every frozen row's experiment_digest is sha256 of the experiment manifest (a
    mutation writing 64 zeros survived audit #8), and bundle_digest is the bundle's."""
    root = _build_fixture_root(tmp_path)
    dest = _harness(root)
    rows = pd.read_parquet(dest)
    want = hashlib.sha256((root / "research" / "nfl_sim" / "FWD_EXPERIMENT_v1.json").read_bytes()).hexdigest()
    assert set(rows["experiment_digest"]) == {want}
    bd = _run_dir(root)
    assert set(rows["bundle_digest"]) == {hashlib.sha256((bd / "bundle_manifest.json").read_bytes()).hexdigest()}
