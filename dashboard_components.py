"""
Dashboard shared components — rendering primitives used across tabs.
Extracted from dashboard.py during modular refactor (2026-04-11).
"""

import json
import os
from datetime import datetime

import streamlit as st


# ── Pipeline labels ───────────────────────────────────────────────────────────

_PIPELINE_LABELS = {
    "mlb_prelim": "MLB prelim",
    "mlb_confirm": "MLB confirm",
    "results_grader": "Results grader",
    "nhl": "NHL",
    "nba": "NBA",
    "soccer": "Soccer",
    "golf": "Golf",
    "health_check": "Health check",
    "wnba": "WNBA",
}


# ── Data loading ──────────────────────────────────────────────────────────────

_BASE_DIR = os.path.dirname(os.path.abspath(__file__))

GOLF_RESULTS_FILE = os.path.join(_BASE_DIR, "golf_results.json")


@st.cache_data(ttl=300, show_spinner=False)
def load_golf_results() -> dict | None:
    if not os.path.exists(GOLF_RESULTS_FILE):
        return None
    with open(GOLF_RESULTS_FILE) as f:
        return json.load(f)


def load_nba_results() -> dict | None:
    path = os.path.join(_BASE_DIR, "nba_results.json")
    if not os.path.exists(path):
        return None
    with open(path) as f:
        return json.load(f)


def load_nhl_results() -> dict | None:
    path = os.path.join(_BASE_DIR, "nhl_results.json")
    if not os.path.exists(path):
        return None
    with open(path) as f:
        return json.load(f)


def load_soccer_results() -> dict | None:
    path = os.path.join(_BASE_DIR, "soccer_results.json")
    if not os.path.exists(path):
        return None
    with open(path) as f:
        return json.load(f)


# ── Pipeline freshness ────────────────────────────────────────────────────────

def _load_last_updated() -> dict:
    try:
        lu_path = os.path.join(_BASE_DIR, "shared", "last_updated.json")
        if os.path.exists(lu_path):
            with open(lu_path) as f:
                return json.load(f)
    except Exception:
        pass
    return {}


def _pipeline_freshness(*keys: str) -> str:
    """Return HTML snippet showing last pipeline run time.

    Accepts one or more keys — picks the most recent among them.
    """
    try:
        lu = _load_last_updated()
        if not lu:
            return "<span style='font-size:0.75em;color:#64748b'>Last updated: unknown</span>"
        from zoneinfo import ZoneInfo
        best_dt = None
        best_key = None
        for key in keys:
            ts_str = lu.get(key)
            if not ts_str or not isinstance(ts_str, str) or "T" not in ts_str:
                continue
            dt = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
            if best_dt is None or dt > best_dt:
                best_dt = dt
                best_key = key
        if best_dt is None:
            return "<span style='font-size:0.75em;color:#64748b'>Last updated: unknown</span>"
        dt_et = best_dt.astimezone(ZoneInfo("America/New_York"))
        label = dt_et.strftime("%b %-d, %-I:%M %p ET")
        pipe_label = _PIPELINE_LABELS.get(best_key, best_key)
        hours_ago = (datetime.now(best_dt.tzinfo) - best_dt).total_seconds() / 3600
        # Suppress staleness for off-season sports (WNBA pre-May 16)
        _stale_threshold = 1000 if best_key == "wnba" and datetime.now().month < 6 else 26
        if hours_ago > _stale_threshold:
            return (f"<span style='font-size:0.75em;color:#eab308'>"
                    f"\u26a0\ufe0f Last updated: {label} \u00b7 {pipe_label} (stale)</span>")
        return (f"<span style='font-size:0.75em;color:#94a3b8'>"
                f"\U0001f4ca Last updated: {label} \u00b7 {pipe_label}</span>")
    except Exception:
        return "<span style='font-size:0.75em;color:#64748b'>Last updated: unknown</span>"


def _global_freshness() -> str:
    """Return HTML showing the most recent timestamp across ALL pipeline keys."""
    lu = _load_last_updated()
    all_keys = [k for k in lu if k != "health_check"]
    return _pipeline_freshness(*all_keys) if all_keys else _pipeline_freshness("health_check")


# ── Last run label ────────────────────────────────────────────────────────────

def _last_run_label(data: dict) -> str:
    ts = data.get("generated_at")
    if not ts:
        return "never"
    try:
        from zoneinfo import ZoneInfo
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        dt_et = dt.astimezone(ZoneInfo("America/New_York"))
        return dt_et.strftime("%b %-d at %-I:%M %p ET")
    except Exception:
        return ts


# ── Universal card / pill helpers ─────────────────────────────────────────────

def _render_game_card_universal(
    matchup: str,
    time_str: str,
    tier: str,
    wagers: list[str] | None = None,
    pills: list[str] | None = None,
    stats: list[str] | None = None,
    weather: str = "",
    extra_html: str = "",
    disclaimer: str = "",
) -> None:
    """Universal game card — one function, every sport, every tier."""
    border_colors = {"ACTIVE": "#16a34a", "SHADOW": "#dc2626", "NONE": "#6b7280"}
    border = border_colors.get(tier, "#6b7280")
    sep = ' <span style="color:#2d3748;margin:0 2px">&middot;</span> '

    # Line 1: matchup + time + weather
    hdr_parts = [matchup]
    if time_str: hdr_parts.append(time_str)
    if weather: hdr_parts.append(weather)
    header = (f'<div style="font-size:0.92em;font-weight:700;color:#e2e8f0">'
              f'{sep.join(hdr_parts)}</div>')

    # Line 2: wager lines
    wager_html = ""
    if wagers:
        wc = "#16a34a" if tier == "ACTIVE" else "#e2e8f0"
        wager_html = '<div style="margin-top:2px">' + "".join(
            f'<div style="font-size:0.85em;font-weight:700;color:{wc}">{w}</div>'
            for w in wagers) + '</div>'

    # Line 3: pills
    pill_html = ""
    if pills:
        pill_html = '<div style="margin-top:4px;line-height:1.8">' + "".join(pills) + '</div>'

    # Line 4: stats
    stats_html = ""
    if stats:
        parts = [f'<span style="color:#94a3b8;font-size:0.75em">{s.split(":")[0]}:</span> '
                 f'<span style="color:#e2e8f0;font-size:0.82em;font-weight:600">{s.split(":",1)[1].strip()}</span>'
                 for s in stats if ":" in s]
        stats_html = f'<div style="margin-top:3px">{sep.join(parts)}</div>'

    # Line 5: disclaimer
    disc_html = ""
    if tier == "SHADOW" and not disclaimer:
        disc_html = ('<div style="font-size:0.68em;color:#f87171;margin-top:4px">'
                    'Research signal &mdash; not a play recommendation.</div>')
    elif disclaimer:
        disc_html = f'<div style="font-size:0.68em;color:#94a3b8;margin-top:4px">{disclaimer}</div>'

    st.html(
        f'<div class="game-card" style="border-left:4px solid {border}">'
        f'{header}{wager_html}{pill_html}{stats_html}{extra_html}{disc_html}'
        f'</div>'
    )


def _universal_pill(label: str, color: str, bg: str) -> str:
    """Render a signal pill — standard style across all sports."""
    return (f'<span style="background:{bg};color:{color};border:1px solid {color};'
            f'border-radius:10px;padding:1px 7px;font-size:0.68em;font-weight:600;'
            f'margin-right:3px">{label}</span>')


def _render_signal_status_row(active_labels: list[str], shadow_labels: list[str]) -> None:
    """Render standardized signal status row — two rows, pill style matching MLB."""
    _pill = lambda label, color, bg: (
        f'<span style="background:{bg};color:{color};border:1px solid {color};'
        f'border-radius:10px;padding:2px 8px;font-size:0.72em;font-weight:600;'
        f'margin-right:4px">{label}</span>')
    html = ""
    if active_labels:
        green_pills = "".join(_pill(l, "#fff", "#16a34a") for l in active_labels)
        html += (f'<div style="margin-bottom:4px">'
                 f'<span style="color:#64748b;font-size:0.65em;font-weight:600;margin-right:6px">'
                 f'\u25cf Active</span>{green_pills}</div>')
    if shadow_labels:
        yellow_pills = "".join(_pill(l, "#eab308", "#1c1400") for l in shadow_labels)
        html += (f'<div>'
                 f'<span style="color:#64748b;font-size:0.65em;font-weight:600;margin-right:6px">'
                 f'\u25d0 Shadow</span>{yellow_pills}</div>')
    if html:
        st.html(f'<div style="margin-bottom:10px">{html}</div>')


# ── Status header ─────────────────────────────────────────────────────────────

def render_status_header(object_name, object_id, status, tracker_start,
                         current_threshold=None, replaces=None, last_updated=None):
    """Reusable status header for any rebuilt tab."""
    # Status badge colors
    badge_colors = {
        "LIVE": ("#22c55e", "#052e16"),
        "SHADOW": ("#eab308", "#1c1400"),
        "INACTIVE": ("#6b7280", "#1f2937"),
        "ARCHIVED": ("#ef4444", "#450a0a"),
    }
    text_color, bg_color = badge_colors.get(status, ("#6b7280", "#1f2937"))

    badge = (f'<span style="background:{bg_color};color:{text_color};border:1px solid {text_color};'
             f'border-radius:12px;padding:2px 10px;font-size:0.72em;font-weight:700;'
             f'margin-left:8px">{status}</span>')

    # Row 1: name + badge
    st.html(f'<div style="font-size:1.1em;font-weight:700;color:#e2e8f0;margin-bottom:4px">'
            f'{object_name}{badge}</div>')

    # Row 2: metadata
    meta_parts = [f'ID: <code>{object_id}</code>']
    meta_parts.append(f'Tracker started: {tracker_start}')
    if last_updated:
        meta_parts.append(f'Last updated: {last_updated}')
    st.html(f'<div style="font-size:0.72em;color:#64748b;margin-bottom:4px">'
            f'{" &nbsp;|&nbsp; ".join(meta_parts)}</div>')

    # Row 3: threshold
    show_threshold = (status in ("LIVE", "SHADOW") or
                      (status == "INACTIVE" and current_threshold))
    if current_threshold and show_threshold:
        th_style = 'color:#94a3b8' if status != "ARCHIVED" else 'color:#4b5563'
        st.html(f'<div style="font-size:0.72em;{th_style};margin-bottom:4px">'
                f'Threshold: {current_threshold}</div>')

    # Row 4: replaces
    if replaces:
        st.html(f'<div style="font-size:0.68em;color:#4b5563;margin-bottom:8px">'
                f'Replaces: {replaces}</div>')
