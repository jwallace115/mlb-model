"""Item 4: capture_health WARNs when the newest slip is older than 3 days. No real slips."""
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import capture_health as ch  # noqa: E402


def _ledger(root, newest_et):
    d = root / "bets" / "ledger"
    d.mkdir(parents=True)
    pd.DataFrame({"slip_id": ["a", "b"], "placed_local": pd.to_datetime(["2026-09-01 12:00", newest_et])}) \
        .to_parquet(d / "slips.parquet", index=False)


NOW = datetime(2026, 10, 3, 13, 0, tzinfo=timezone.utc)


def test_stale_ledger_warns_with_its_age(tmp_path):
    _ledger(tmp_path, "2026-09-27 20:17")             # ET -> 2026-09-28 00:17Z, 5.5 days before NOW
    status, msg = ch.check_bet_ledger(tmp_path, NOW)
    assert status == "WARN" and "5.5 days old" in msg and "bets/inbox/" in msg


def test_fresh_ledger_is_ok(tmp_path):
    _ledger(tmp_path, "2026-10-02 12:30")
    assert ch.check_bet_ledger(tmp_path, NOW)[0] == "OK"


def test_no_ledger_on_this_host_is_not_a_warning(tmp_path):
    assert ch.check_bet_ledger(tmp_path, NOW)[0] == "ABSENT"
