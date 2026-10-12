"""
ON utilities: sign normalisation, event matching, quote selection.

Fixes documented in ON-D5 (ChatGPT audit c23e62419):
- Sign: raw home handicap h → expected home margin q = −h
- Event identity: (season, home, away, kickoff ±1h, event_id)
- Close: last quote strictly BEFORE kickoff; max-age preference; no in-play
"""
import zlib
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

ET = ZoneInfo("America/New_York")

# ─── 1a. SIGN NORMALISATION ──────────────────────────────────────────────

def handicap_to_home_margin(h):
    """Convert a bookmaker home handicap to expected home margin.

    Odds API convention: home handicap h = −3 means home favored by 3.
    Expected home margin q = −h = +3.
    """
    if h is None or (isinstance(h, float) and np.isnan(h)):
        return None
    return -h


def compute_gap(ours_m, h):
    """Gap between our number and the book's implied home margin.

    ours_m: our expected home margin (home − away)
    h: raw home handicap from the book
    Returns: ours_m − (−h) = ours_m + h  (signed gap)
    """
    q = handicap_to_home_margin(h)
    if q is None:
        return None
    return ours_m - q


def is_confident(ours_m, h, err_m):
    """True when |gap| ≥ err_m AND |gap| ≥ 1.0 pt."""
    gap = compute_gap(ours_m, h)
    if gap is None:
        return False
    return abs(gap) >= err_m and abs(gap) >= 1.0


# ─── 1b. EVENT MATCHING ──────────────────────────────────────────────────

def kickoff_utc_from_nflverse(gameday, gametime):
    """Construct a UTC kickoff datetime from nflverse gameday + gametime (ET)."""
    dt_str = f"{gameday} {gametime}"
    local = datetime.strptime(dt_str, "%Y-%m-%d %H:%M").replace(tzinfo=ET)
    return local.astimezone(timezone.utc)


def match_game_to_event(home, away, kickoff_utc, season, spreads_df,
                        team_col="team_abbr", full_to_abbr=None):
    """Match a game to an Odds API event_id.

    Rules (ON-D5 1b):
    - Both mapped teams present in the event
    - commence_time within ±1 hour of kickoff_utc
    - Exactly one match; ambiguous → raise ValueError (HALT)
    - A rematch later in the season must not select the earlier meeting
      (enforced by the ±1h kickoff window)
    """
    home_rows = spreads_df[spreads_df[team_col] == home]
    away_rows = spreads_df[spreads_df[team_col] == away]
    candidate_eids = set(home_rows["event_id"].unique()) & set(away_rows["event_id"].unique())

    if not candidate_eids:
        return None

    commence_col = "commence_time"
    matches = []
    for eid in candidate_eids:
        evt = spreads_df[spreads_df["event_id"] == eid]
        ct = pd.to_datetime(evt[commence_col].iloc[0], utc=True)
        diff = abs((ct - kickoff_utc).total_seconds())
        if diff <= 3600:  # within ±1 hour
            matches.append((eid, ct))

    if len(matches) == 0:
        return None
    if len(matches) > 1:
        raise ValueError(
            f"HALT: ambiguous event match for {away}@{home} kick={kickoff_utc}: "
            f"{[m[0] for m in matches]}"
        )
    return matches[0][0]


# ─── 1c. QUOTE SELECTION ─────────────────────────────────────────────────

MAX_QUOTE_AGE_PREFERRED_H = 3  # prefer quotes within 3h of kick
# Quotes with snapshot_utc >= kickoff are in-play and never usable as a close.

def select_close_quote(quotes_df, kickoff_utc, snapshot_col="snapshot_utc"):
    """Select the closing quote: last quote strictly BEFORE kickoff.

    Returns (selected_row, flag) where flag is one of:
    - "preferred": quote within MAX_QUOTE_AGE_PREFERRED_H of kick
    - "stale": quote is the last pre-kick but > MAX_QUOTE_AGE_PREFERRED_H old
    - None: no valid pre-kick quote found

    Rejects future-dated quotes (snapshot_utc > now at call time is impossible
    for historical data; for live data the caller filters).
    """
    if len(quotes_df) == 0:
        return None, None

    df = quotes_df.copy()
    df[snapshot_col] = pd.to_datetime(df[snapshot_col], utc=True)
    kickoff = pd.Timestamp(kickoff_utc).tz_localize("UTC") if pd.Timestamp(kickoff_utc).tzinfo is None else pd.Timestamp(kickoff_utc).tz_convert("UTC")

    # Filter: strictly before kickoff (no in-play)
    pre_kick = df[df[snapshot_col] < kickoff].sort_values(snapshot_col)
    if len(pre_kick) == 0:
        return None, None

    # Preferred: last quote ≤ MAX_QUOTE_AGE_PREFERRED_H before kick
    preferred_cutoff = kickoff - pd.Timedelta(hours=MAX_QUOTE_AGE_PREFERRED_H)
    preferred = pre_kick[pre_kick[snapshot_col] >= preferred_cutoff]

    if len(preferred) > 0:
        return preferred.iloc[-1], "preferred"
    else:
        return pre_kick.iloc[-1], "stale"


def select_decision_quote(quotes_df, cutoff_utc, snapshot_col="snapshot_utc"):
    """Select the decision quote: last quote strictly BEFORE the prediction cutoff.

    Used for the benchmark quote at prediction time.
    """
    if len(quotes_df) == 0:
        return None

    df = quotes_df.copy()
    df[snapshot_col] = pd.to_datetime(df[snapshot_col], utc=True)
    cutoff = pd.Timestamp(cutoff_utc).tz_localize("UTC") if pd.Timestamp(cutoff_utc).tzinfo is None else pd.Timestamp(cutoff_utc).tz_convert("UTC")

    pre_cutoff = df[df[snapshot_col] < cutoff].sort_values(snapshot_col)
    if len(pre_cutoff) == 0:
        return None
    return pre_cutoff.iloc[-1]


# ─── 2c. STABLE SEEDS ────────────────────────────────────────────────────

def stable_seed(game_id, chunk_index, season=None, week=None):
    """Deterministic seed via zlib.crc32 — independent of PYTHONHASHSEED.

    seed = crc32(game_id + ":" + str(chunk_index)) & 0x7FFFFFFF
    """
    key = f"{game_id}:{chunk_index}"
    if season is not None:
        key = f"{season}:{week}:{key}"
    return zlib.crc32(key.encode("utf-8")) & 0x7FFFFFFF


# ─── 2a. MONDAY CUTOFF ───────────────────────────────────────────────────

def monday_cutoff_utc(season, week):
    """Monday 12:00 America/New_York of the given game week, returned as UTC.

    NFL weeks start on the Tuesday after the prior week's Monday Night game.
    The Monday of game week is the day BEFORE the first Tuesday.
    We use nflverse gameday to find the week's first game, then back-calculate
    the Monday.
    """
    # This is a helper; callers provide the actual Monday date when possible.
    # For now, construct Monday = first gameday of the week adjusted.
    raise NotImplementedError("Use compute_prediction_cutoff with schedule data")


def compute_prediction_cutoff(game_week_monday_date):
    """Given the Monday date (str YYYY-MM-DD), return Monday 12:00 ET as UTC."""
    local = datetime.strptime(game_week_monday_date, "%Y-%m-%d").replace(
        hour=12, minute=0, second=0, tzinfo=ET
    )
    return local.astimezone(timezone.utc)


def game_is_admitted(kickoff_utc, prediction_cutoff_utc, buffer_hours=4):
    """A prior game is admitted only if kickoff + buffer_hours < cutoff.

    This excludes the previous week's Monday Night game from the current
    week's Monday-noon cutoff (MNF kicks ~20:15 ET + 4h = ~00:15 Tue > Mon noon).
    """
    end = kickoff_utc + timedelta(hours=buffer_hours)
    return end < prediction_cutoff_utc
