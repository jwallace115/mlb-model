"""history_spender: never spends into the reserve, never buys a key twice, writes nothing on errors."""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import history_spender as hs  # noqa: E402

NOW = datetime(2026, 10, 2, 6, 10, tzinfo=timezone.utc)


class FakeApi:
    fp = "test0000"

    def __init__(self, remaining, status=200, events_status=200):
        self.remaining, self.status, self.events_status, self.calls = remaining, status, events_status, []

    def get(self, path, params):
        self.calls.append((path, params.get("date")))
        if path == "/sports":
            return 200, [], self.remaining, 0
        if path.endswith("/events"):
            if self.events_status != 200:
                return self.events_status, None, self.remaining, 0
            self.remaining -= 1
            return 200, {"timestamp": params["date"], "data": [
                {"id": "ev1", "commence_time": "2025-09-05T00:20:00Z", "home_team": "PHI", "away_team": "DAL"}]}, self.remaining, 1
        if self.status != 200:
            return self.status, None, self.remaining, 0
        cost = 30 if path.endswith("/odds") and "/events/" not in path else 10 * len(params["markets"].split(","))
        self.remaining -= cost
        ev = {"id": "ev1", "commence_time": "2025-09-05T00:20:00Z", "home_team": "PHI", "away_team": "DAL",
              "bookmakers": [{"key": "pinnacle", "markets": [{"key": "totals", "last_update": "x",
                              "outcomes": [{"name": "Over", "point": 47.5, "price": -110}]}]}]}
        data = ev if "/events/" in path else [ev]
        return 200, {"timestamp": params["date"], "data": data}, self.remaining, cost


def _setup(tmp_path, monkeypatch, jobs):
    tmp_path.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(hs, "ROOT", tmp_path)
    monkeypatch.setattr(hs, "ARCHIVE", tmp_path / "data" / "odds_archive")
    monkeypatch.setattr(hs, "LEDGER", tmp_path / "data" / "odds_archive" / "_history_ledger.jsonl")
    monkeypatch.setattr(hs, "STATUS", tmp_path / "status" / "history_spender.json")
    cfg = {"books": ["pinnacle"], "folders": {"americanfootball_nfl": "nfl"},
           "seasons": {"americanfootball_nfl": {"2025": ["2025-09-04", "2025-09-05"]}}, "jobs": jobs}
    args = SimpleNamespace(reserve_floor=50_000, reserve_per_day=8_000, max_credits=0, until="23:59",
                           ignore_clock=True, min_free_gb=0.0, workers=2, only=None)
    return cfg, args


GRID = {"id": "nfl_lines_hourly", "sport": "americanfootball_nfl", "kind": "grid", "seasons": ["2025"], "step_min": 60}
EVENT = {"id": "nfl_props", "sport": "americanfootball_nfl", "kind": "event", "seasons": ["2025"], "offsets_h": [24, 1],
         "markets": ["player_pass_yds", "player_receptions"]}


def test_grid_buys_every_hour_once_and_resumes(tmp_path, monkeypatch):
    cfg, args = _setup(tmp_path, monkeypatch, [GRID])
    api = FakeApi(5_000_000)
    assert hs.Run(api, cfg, args, NOW).main() == 0
    paid = [c for c in api.calls if c[0].endswith("/odds")]
    assert len(paid) == 48  # 2 days x 24 h
    assert len(list((tmp_path / "data/odds_archive/nfl/history/nfl_lines_hourly/season=2025").glob("*.parquet"))) == 48
    api2 = FakeApi(5_000_000)
    hs.Run(api2, cfg, args, NOW).main()
    assert [c for c in api2.calls if c[0].endswith("/odds")] == []  # nothing bought twice


def test_stops_at_reserve(tmp_path, monkeypatch):
    cfg, args = _setup(tmp_path, monkeypatch, [GRID])
    reserve = 50_000 + 8_000 * 30  # Oct 2 -> 30 days left incl. today
    api = FakeApi(reserve + 100)   # room for ~3 calls of 30
    hs.Run(api, cfg, args, NOW).main()
    assert api.remaining >= reserve - 30 * args.workers  # never more than one in-flight batch past the line
    st = json.loads((tmp_path / "status/history_spender.json").read_text())["latest"]
    assert "reserve" in st["stop_reason"]


def test_event_job_and_unsupported_market(tmp_path, monkeypatch):
    cfg, args = _setup(tmp_path, monkeypatch, [EVENT])
    api = FakeApi(5_000_000)
    hs.Run(api, cfg, args, NOW).main()
    out = tmp_path / "data/odds_archive/nfl/history/nfl_props/season=2025"
    assert sorted(p.name for p in out.glob("*.parquet")) == ["ev1_T-1h.parquet", "ev1_T-24h.parquet"]
    cfg2, args2 = _setup(tmp_path / "b", monkeypatch, [EVENT])
    api422 = FakeApi(5_000_000, status=422)
    hs.Run(api422, cfg2, args2, NOW).main()
    assert not list((tmp_path / "b").rglob("ev1_T-*.parquet"))


def test_http_error_writes_nothing_and_401_halts(tmp_path, monkeypatch):
    cfg, args = _setup(tmp_path, monkeypatch, [GRID])
    api = FakeApi(5_000_000, status=500)
    hs.Run(api, cfg, args, NOW).main()
    assert not list(tmp_path.rglob("snap_*.parquet"))
    cfg2, args2 = _setup(tmp_path / "c", monkeypatch, [GRID])
    api401 = FakeApi(5_000_000, status=401)
    hs.Run(api401, cfg2, args2, NOW).main()
    st = json.loads((tmp_path / "c/status/history_spender.json").read_text())["latest"]
    assert "401" in st["stop_reason"]
