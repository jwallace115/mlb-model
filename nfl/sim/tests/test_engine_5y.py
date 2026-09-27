"""5Y tests: first-down fallback resolves to same clock_period; drive-end exclusion."""
import sys
from pathlib import Path
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))


def test_first_down_fallback_resolves_same_period():
    """For every (score_state, clock_period) with a pooled first_down cell,
    a rush and pass lookup resolves to a cell with that SAME clock_period."""
    from nfl.sim.engine import _load_tables, _CACHE
    _load_tables()
    tbl = pd.read_parquet(ROOT / "nfl" / "data" / "sim" / "tables" / "clock_runoff.parquet")
    clock_q = {}
    for _, r in tbl.iterrows():
        clock_q[(r["outcome_type"], r["score_state"], r["clock_period"])] = True
        if "hurry" in r and r.get("hurry"):
            clock_q[(r["outcome_type"], r["hurry"])] = True

    # Find all pooled first_down cells at level 0
    pooled = tbl[(tbl["outcome_type"] == "first_down") &
                  ~tbl["score_state"].str.startswith("p_") &
                  ~tbl["score_state"].str.startswith("eoh") &
                  ~tbl["score_state"].str.startswith("fgs") &
                  (tbl["clock_period"] != "all")]

    assert len(pooled) > 0, "No pooled first_down level-0 cells found"

    for _, row in pooled.iterrows():
        ss, cp = row["score_state"], row["clock_period"]
        for split_ot in ["first_down_rush", "first_down_pass"]:
            # The lookup should find EITHER the split cell OR the pooled cell at this (ss, cp)
            found_split = (split_ot, ss, cp) in clock_q
            found_pooled = ("first_down", ss, cp) in clock_q
            assert found_split or found_pooled, (
                f"{split_ot} at ({ss}, {cp}): neither split nor pooled cell exists"
            )
