"""D252/D258(c): the FWD5 item-1 tests that were never delivered.

The experiment's logger is nfl/sim/fwd_v1_logger.py (a byte-identical, hashed copy);
the shared nfl/pipeline/log_ai_opinions.py belongs to NHL and the AI readers.
"""
import json
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "nfl" / "pipeline" / "tests"))

from nfl.sim.tests.test_fwd3_item0 import _build_fixture_root, _set_fwd_paths  # noqa: E402

CANON = "nfl_sim_v1_156cd057"


def test_decoupling_shared_change_passes_pinned_change_halts(tmp_path):
    import nfl.sim.run_forward_v1 as fwd
    root = _build_fixture_root(tmp_path)
    shared = root / "nfl" / "pipeline" / "log_ai_opinions.py"
    shared.parent.mkdir(parents=True, exist_ok=True)
    shared.write_text((ROOT / "nfl" / "pipeline" / "log_ai_opinions.py").read_text())
    saved = (fwd.PROPS_DIR, fwd.LINES_DIR, fwd.BOARD_ROOT, fwd.EXPERIMENT_MANIFEST)
    _set_fwd_paths(fwd, root)
    try:
        shared.write_text(shared.read_text() + "\n# an NHL edit\n")
        fwd.check_experiment_manifest(_root=root)          # passes: not part of the experiment
        pinned = root / "nfl" / "sim" / "fwd_v1_logger.py"
        pinned.write_text(pinned.read_text() + "\n# an edit\n")
        with pytest.raises(SystemExit, match="experiment manifest hash mismatch"):
            fwd.check_experiment_manifest(_root=root)
    finally:
        fwd.PROPS_DIR, fwd.LINES_DIR, fwd.BOARD_ROOT, fwd.EXPERIMENT_MANIFEST = saved


def test_live_path_never_imports_shared_logger(tmp_path):
    """main() on the fixture root, live (no --pilot, no --as-of), in a SUBPROCESS: the
    shared logger module must not be loaded."""
    code = textwrap.dedent(f"""
        import sys, json
        from datetime import datetime, timezone, timedelta
        sys.path.insert(0, {str(ROOT)!r})
        from pathlib import Path
        from nfl.sim.tests.test_fwd3_item0 import _build_fixture_root, _stub_run_week
        from nfl.sim.run_forward_v1 import main
        kick = datetime.now(timezone.utc).replace(microsecond=0) + timedelta(hours=2)
        root = _build_fixture_root(Path({str(tmp_path)!r}), kick=kick)
        dest = main(argv=["--week", "3", "--window-hours", "4"], root=str(root),
                    run_week_fn=_stub_run_week)
        print("FROZEN", dest is not None)
        print("SHARED_LOADED", "nfl.pipeline.log_ai_opinions" in sys.modules)
    """)
    r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=300)
    assert "FROZEN True" in r.stdout, r.stdout[-2000:] + r.stderr[-2000:]
    assert "SHARED_LOADED False" in r.stdout


def _sheet():
    import test_ai_opinions_n59 as T59
    from nfl.sim import fwd_v1_logger as P
    return T59, P.build_sheet(T59._props(), T59._lines(), T59.NOW)


def test_interop_ai_reader_first_then_canonical(tmp_path):
    from datetime import timedelta
    from nfl.pipeline import log_ai_opinions as L
    from nfl.sim import fwd_v1_logger as P
    T59, s = _sheet()
    board = tmp_path / "board"
    d = board / "week=2026_04" / "ai_opinions"
    L.freeze(s, T59._filled(s), 2026, 4, False, T59.NOW, d=d, reader_model="claude-opus-5-5",
             board_root=board)
    later = T59.NOW + timedelta(minutes=5)
    s2 = P.build_sheet(T59._props(), T59._lines(), later)
    _, _, m = P.freeze(s2, T59._filled(s2), 2026, 4, False, later, d=d, reader_model=CANON,
                       board_root=board, run_id="R1")
    assert (m["revision"] == 0).all()
    for verify in (P.verify, L.verify):
        entries, bad, unlisted = verify(2026, 4, d=d)
        assert bad == [] and unlisted == [] and len(entries) == 2
    # a second canonical freeze of the same contracts is refused
    later2 = later + timedelta(minutes=5)
    s3 = P.build_sheet(T59._props(), T59._lines(), later2)
    with pytest.raises(SystemExit, match="already frozen"):
        P.freeze(s3, T59._filled(s3), 2026, 4, False, later2, d=d, reader_model=CANON,
                 board_root=board)


def test_interop_canonical_first_then_ai_reader_and_shared_cannot_write_canonical(tmp_path):
    """The reverse order the audit found missing: the shared logger can never write the
    first canonical freeze (so it cannot block the harness), and an AI reader freezing
    after the canonical one is unaffected."""
    from datetime import timedelta
    from nfl.pipeline import log_ai_opinions as L
    from nfl.sim import fwd_v1_logger as P
    T59, s = _sheet()
    board = tmp_path / "board"
    d = board / "week=2026_04" / "ai_opinions"
    with pytest.raises(SystemExit, match="reserved"):
        L.freeze(s, T59._filled(s), 2026, 4, False, T59.NOW, d=d, reader_model=CANON,
                 board_root=board)
    _, _, m = P.freeze(s, T59._filled(s), 2026, 4, False, T59.NOW, d=d, reader_model=CANON,
                       board_root=board, run_id="R1")
    assert (m["revision"] == 0).all()
    later = T59.NOW + timedelta(minutes=5)
    s2 = L.build_sheet(T59._props(), T59._lines(), later)
    _, _, m2 = L.freeze(s2, T59._filled(s2), 2026, 4, False, later, d=d,
                        reader_model="claude-fable-5-1", board_root=board)
    assert (m2["revision"] == 0).all()
    for verify in (P.verify, L.verify):
        entries, bad, unlisted = verify(2026, 4, d=d)
        assert bad == [] and unlisted == [] and len(entries) == 2
