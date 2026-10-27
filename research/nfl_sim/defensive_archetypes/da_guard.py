"""DA discovery/validation guard.

Module-level check that HALTs if any prop row with nfl_season in (2024, 2025)
is loaded while DA_PHASE != "validation".
"""
import os
import sys

HOLDOUT_SEASONS = {2024, 2025}
DA_PHASE = os.environ.get("DA_PHASE", "discovery")


def check_prop_seasons(df, season_col="nfl_season"):
    """HALT if any holdout season is present and DA_PHASE != validation."""
    if DA_PHASE == "validation":
        return
    if season_col not in df.columns:
        return
    present = set(df[season_col].dropna().astype(int).unique())
    leak = present & HOLDOUT_SEASONS
    if leak:
        raise SystemExit(
            f"HALT: prop rows from holdout seasons {sorted(leak)} loaded "
            f"while DA_PHASE={DA_PHASE!r} (set DA_PHASE=validation to proceed)")
