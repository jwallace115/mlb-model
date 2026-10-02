"""modules/schedule.py must survive the MLB Stats API refusing hydrate=officials with HTTP 406."""
import sys
from pathlib import Path

import pytest
import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from modules import schedule  # noqa: E402

GAME = {
    "gamePk": 1, "gameType": "R", "gameDate": "2026-06-20T23:05:00Z",
    "status": {"detailedState": "Scheduled"},
    "venue": {"name": "Truist Park"},
    "teams": {
        "home": {"team": {"id": 144, "abbreviation": "ATL"}, "probablePitcher": {"id": 9, "fullName": "A B"}},
        "away": {"team": {"id": 143, "abbreviation": "PHI"}, "probablePitcher": {"id": 8, "fullName": "C D"}},
    },
}


class _Resp:
    def __init__(self, code, payload=None):
        self.status_code, self._p = code, payload or {}

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"{self.status_code}", response=self)

    def json(self):
        return self._p


def test_406_on_officials_falls_back(monkeypatch):
    calls = []

    def fake_get(url, params=None, timeout=None, headers=None):
        calls.append(params["hydrate"])
        if "officials" in params["hydrate"]:
            return _Resp(406)
        return _Resp(200, {"dates": [{"games": [GAME]}]})

    monkeypatch.setattr(schedule.requests, "get", fake_get)
    games = schedule.fetch_schedule("2026-06-20")
    assert calls == ["probablePitcher,officials,linescore,team", "probablePitcher,linescore,team"]
    assert len(games) == 1


def test_other_http_errors_still_raise(monkeypatch):
    monkeypatch.setattr(schedule.requests, "get", lambda *a, **k: _Resp(500))
    with pytest.raises(requests.HTTPError):
        schedule.fetch_schedule("2026-06-20")


def test_all_variants_refused_raises(monkeypatch):
    monkeypatch.setattr(schedule.requests, "get", lambda *a, **k: _Resp(406))
    with pytest.raises(requests.HTTPError):
        schedule.fetch_schedule("2026-06-20")
