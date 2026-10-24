"""OPS-CAD3b tests (RED first against a523978e1: _run_post_freeze_steps does not exist)."""
import subprocess
from shared.pipeline import window_watch as ww


def _timeout_runner(cmd, **kw):
    raise subprocess.TimeoutExpired(cmd, kw.get("timeout"))


class _Res:
    def __init__(self, rc, err=""):
        self.returncode = rc
        self.stderr = err


def test_post_freeze_timeout_is_warning_not_crash(tmp_path, capsys):
    out = ww._run_post_freeze_steps(tmp_path, {}, runner=_timeout_runner, timeouts={"picks_adapters": 1, "build_site": 1})
    assert out == {"picks_adapters": "timeout", "build_site": "timeout"}
    assert "WARNING: picks_adapters timed out" in capsys.readouterr().out


def test_post_freeze_runs_build_site_after_adapter_failure(tmp_path):
    calls = []

    def runner(cmd, **kw):
        calls.append(cmd[-1].split("/")[-1])
        return _Res(1, "boom") if "picks_adapters" in cmd[-1] else _Res(0)

    out = ww._run_post_freeze_steps(tmp_path, {}, runner=runner)
    assert calls == ["picks_adapters.py", "build_site.py"]
    assert out == {"picks_adapters": "exit 1", "build_site": "ok"}


def test_post_freeze_default_timeouts_cover_measured_vm_runtime():
    # picks_adapters measured 158-222 s on the VM (10-24); 120 s was the crash
    assert ww.POST_FREEZE_TIMEOUTS["picks_adapters"] >= 300


def test_sport_from_argv():
    assert ww._sport_from_argv(["x", "--once", "--sport", "ncaaf"]) == "ncaaf"
    assert ww._sport_from_argv(["x", "--sport=nfl"]) == "nfl"
    assert ww._sport_from_argv(["x"]) == "nfl"
