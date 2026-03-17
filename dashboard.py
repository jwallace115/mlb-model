#!/usr/bin/env python3
"""
MLB Totals Model — Streamlit Dashboard
=======================================
Reads from results.json and season_stats.json pushed from the local machine.

Launch:  streamlit run dashboard.py
"""

import json
import os
from datetime import datetime

import streamlit as st

RESULTS_FILE      = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results.json")
SEASON_STATS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "season_stats.json")
NBA_RESULTS_FILE    = os.path.join(os.path.dirname(os.path.abspath(__file__)), "nba_results.json")
NHL_RESULTS_FILE    = os.path.join(os.path.dirname(os.path.abspath(__file__)), "nhl_results.json")
SOCCER_RESULTS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "soccer_results.json")

# ── page config ───────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="I AM NOT UNCERTAIN",
    page_icon="⚾",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── password gate ─────────────────────────────────────────────────────────────

def _check_password() -> bool:
    if st.session_state.get("authenticated"):
        return True

    st.markdown("""
    <style>
    .block-container { padding-top: 0 !important; }
    .gate-wrap {
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        min-height: 80vh;
        gap: 0;
    }
    .gate-title {
        font-size: 1.25em;
        font-weight: 800;
        letter-spacing: 0.18em;
        text-transform: uppercase;
        color: #e2e8f0;
        margin-bottom: 2.2rem;
        text-align: center;
    }
    </style>
    <div class="gate-wrap">
        <div class="gate-title">I AM NOT UNCERTAIN</div>
    </div>
    """, unsafe_allow_html=True)

    col = st.columns([1, 1.4, 1])[1]
    with col:
        pw = st.text_input(
            "Password",
            type="password",
            label_visibility="collapsed",
            placeholder="Password",
            key="pw_input",
        )
        if st.button("Enter", use_container_width=True):
            if pw == "billions":
                st.session_state["authenticated"] = True
                st.rerun()
            else:
                st.error("Incorrect password.")

    return False


if not _check_password():
    st.stop()


# ── CSS ───────────────────────────────────────────────────────────────────────

st.markdown("""
<style>
.block-container { padding-top: 1.2rem; max-width: 860px; }

/* ── Season header ── */
.season-banner {
    background: #0f1117;
    border: 1px solid #1e2535;
    border-radius: 8px;
    padding: 14px 18px;
    margin-bottom: 16px;
}
.season-banner .st-label { font-size: 0.72em; color: #4a5568; text-transform: uppercase; letter-spacing: 0.08em; }
.stat-grid {
    display: flex;
    flex-wrap: wrap;
    gap: 10px 28px;
    align-items: flex-end;
}
.stat-block .num { font-size: 1.7em; font-weight: 700; color: #f1f5f9; line-height: 1.1; }
.stat-block .num.green  { color: #22c55e; }
.stat-block .num.yellow { color: #eab308; }
.stat-block .num.red    { color: #f87171; }
.stat-block .lbl { font-size: 0.72em; color: #4a5568; margin-top: 2px; }
.spring-badge {
    font-size: 0.72em;
    font-weight: 700;
    padding: 3px 10px;
    border-radius: 4px;
    background: #1e3a5f;
    color: #7dd3fc;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    display: inline-block;
    margin-bottom: 10px;
}

/* ── Star record table ── */
.star-table {
    width: 100%;
    border-collapse: collapse;
    font-size: 0.82em;
    margin-top: 8px;
}
.star-table th {
    color: #4a5568;
    font-weight: 600;
    text-align: left;
    padding: 3px 10px 3px 0;
    border-bottom: 1px solid #1e2535;
    font-size: 0.9em;
    text-transform: uppercase;
    letter-spacing: 0.06em;
}
.star-table td {
    padding: 5px 10px 5px 0;
    color: #cbd5e1;
    border-bottom: 1px solid #0f1117;
}
.star-table td.green  { color: #22c55e; font-weight: 700; }
.star-table td.yellow { color: #eab308; font-weight: 700; }
.star-table td.red    { color: #f87171; font-weight: 700; }

/* ── Game cards ── */
.game-card {
    border-radius: 8px;
    padding: 14px 18px;
    margin-bottom: 10px;
    background: #161b27;
    border-left: 4px solid #2d3748;
}
.game-card.star3 { border-left-color: #22c55e; }
.game-card.star2 { border-left-color: #eab308; }
.game-card.star1 { border-left-color: #94a3b8; }
.game-card.noplay {
    background: #0f1117;
    border-left-color: #2d3748;
    opacity: 0.70;
}

/* ── Card header ── */
.card-header {
    display: flex;
    align-items: center;
    gap: 10px;
    flex-wrap: wrap;
    margin-bottom: 3px;
}
.stars { font-size: 1.05em; letter-spacing: -2px; }
.noplay-badge {
    font-size: 0.72em;
    font-weight: 700;
    padding: 2px 8px;
    border-radius: 4px;
    background: #1e2535;
    color: #64748b;
    letter-spacing: 0.05em;
    text-transform: uppercase;
}
.matchup {
    font-size: 1.2em;
    font-weight: 700;
    color: #f1f5f9;
    letter-spacing: 0.015em;
}
.lean-badge {
    font-weight: 700;
    font-size: 0.85em;
    padding: 2px 10px;
    border-radius: 4px;
}
.lean-over   { background: #7f1d1d; color: #fca5a5; }
.lean-under  { background: #0c4a6e; color: #7dd3fc; }
.lean-neutral { background: #1e2535; color: #475569; }

/* ── Meta row ── */
.card-meta {
    font-size: 0.80em;
    color: #4a5568;
    margin-bottom: 8px;
    line-height: 1.4;
}

/* ── Projection row ── */
.proj-row {
    display: flex;
    flex-wrap: wrap;
    gap: 6px 18px;
    font-size: 0.875em;
    margin-bottom: 9px;
    align-items: baseline;
}
.proj-label { color: #4a5568; }
.proj-val   { font-weight: 600; color: #e2e8f0; }
.edge-pos   { color: #f87171; font-weight: 700; }
.edge-neg   { color: #67e8f9; font-weight: 700; }
.conf-badge {
    font-size: 0.72em;
    padding: 1px 6px;
    border-radius: 3px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.05em;
}
.conf-HIGH   { background: #14532d; color: #86efac; }
.conf-MEDIUM { background: #713f12; color: #fde68a; }
.conf-LOW    { background: #1e2535; color: #64748b; }

/* ── Summary ── */
.card-summary {
    font-size: 0.85em;
    color: #718096;
    line-height: 1.65;
    border-top: 1px solid #1e2535;
    padding-top: 8px;
    margin-top: 4px;
}

/* ── Section headers ── */
.section-hdr {
    font-size: 0.72em;
    font-weight: 700;
    letter-spacing: 0.10em;
    color: #4a5568;
    text-transform: uppercase;
    margin: 22px 0 8px 0;
    padding-bottom: 5px;
    border-bottom: 1px solid #1e2535;
}

/* ── Parlay card ── */
.parlay-card {
    background: #13172a;
    border: 1px solid #312e81;
    border-radius: 8px;
    padding: 14px 18px;
    margin-top: 6px;
}
.parlay-card-sharp {
    background: #1a1500;
    border: 1px solid #92400e;
    border-radius: 8px;
    padding: 14px 18px;
    margin-top: 10px;
}
.parlay-card-value {
    background: #0f172a;
    border: 1px solid #312e81;
    border-radius: 8px;
    padding: 14px 18px;
    margin-top: 10px;
}
.parlay-card-risk {
    background: #1a0a0a;
    border: 1px solid #7f1d1d;
    border-radius: 8px;
    padding: 14px 18px;
    margin-top: 10px;
}
.parlay-title {
    font-size: 0.72em;
    font-weight: 700;
    letter-spacing: 0.10em;
    text-transform: uppercase;
    color: #818cf8;
    margin-bottom: 10px;
}
.parlay-title-sharp { color: #f59e0b; }
.parlay-title-value { color: #818cf8; }
.parlay-title-risk  { color: #f87171; }
.parlay-leg {
    display: flex;
    justify-content: space-between;
    align-items: center;
    flex-wrap: wrap;
    gap: 6px;
    padding: 6px 0;
    border-bottom: 1px solid #1e2040;
    font-size: 0.85em;
    color: #cbd5e1;
}
.parlay-leg:last-child { border-bottom: none; }
.parlay-matchup { font-weight: 600; color: #f1f5f9; min-width: 120px; }

/* ── Analytics tables ── */
.analytics-table {
    width: 100%;
    border-collapse: collapse;
    font-size: 0.82em;
    margin-top: 4px;
}
.analytics-table th {
    color: #4a5568;
    font-weight: 600;
    text-align: left;
    padding: 4px 12px 4px 0;
    border-bottom: 1px solid #1e2535;
    font-size: 0.88em;
    text-transform: uppercase;
    letter-spacing: 0.05em;
}
.analytics-table td {
    padding: 6px 12px 6px 0;
    color: #cbd5e1;
    border-bottom: 1px solid #0f1117;
    vertical-align: top;
}
.analytics-table td.dim   { color: #4a5568; }
.analytics-table td.green { color: #22c55e; font-weight: 600; }
.analytics-table td.yellow{ color: #eab308; font-weight: 600; }
.analytics-table td.red   { color: #f87171; font-weight: 600; }

/* ── Alerts section ── */
.alerts-section {
    background: #0f1117;
    border: 1px solid #1e2535;
    border-radius: 8px;
    padding: 14px 18px;
    margin-bottom: 16px;
}
.alerts-title {
    font-size: 0.72em;
    font-weight: 700;
    letter-spacing: 0.10em;
    color: #64748b;
    text-transform: uppercase;
    margin-bottom: 10px;
}
.alert-row {
    display: flex;
    align-items: flex-start;
    gap: 10px;
    padding: 8px 0;
    border-bottom: 1px solid #1e2535;
    font-size: 0.83em;
    line-height: 1.5;
}
.alert-row:last-child { border-bottom: none; }
.alert-icon { font-size: 1.1em; flex-shrink: 0; margin-top: 1px; }
.alert-body { flex: 1; }
.alert-matchup {
    font-weight: 700;
    color: #f1f5f9;
    margin-right: 6px;
}
.alert-detail { color: #94a3b8; }
.alert-proj-change {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    margin-top: 3px;
    font-size: 0.88em;
}
.alert-old  { color: #64748b; text-decoration: line-through; }
.alert-new  { color: #f1f5f9; font-weight: 600; }
.alert-conf { font-size: 0.78em; padding: 1px 5px; border-radius: 3px; }
.alert-conf-down { background: #7f1d1d; color: #fca5a5; }
.alert-txn-desc { color: #94a3b8; font-size: 0.88em; }

/* ── Props rows ── */
.props-section {
    margin-top: 8px;
    padding-top: 7px;
    border-top: 1px solid #1e2535;
}
.props-title {
    font-size: 0.67em;
    font-weight: 700;
    letter-spacing: 0.10em;
    color: #4a5568;
    text-transform: uppercase;
    margin-bottom: 5px;
}
.prop-row {
    display: flex;
    align-items: center;
    gap: 8px;
    flex-wrap: wrap;
    font-size: 0.78em;
    padding: 3px 0;
    color: #718096;
    border-bottom: 1px solid #0f1117;
}
.prop-row:last-child { border-bottom: none; }
.prop-market {
    font-weight: 700;
    font-size: 0.80em;
    padding: 1px 5px;
    border-radius: 3px;
    background: #1e2535;
    color: #64748b;
    letter-spacing: 0.05em;
    text-transform: uppercase;
    min-width: 24px;
    text-align: center;
}
.prop-play-badge {
    font-size: 0.72em;
    font-weight: 700;
    padding: 1px 6px;
    border-radius: 3px;
    background: #14532d;
    color: #86efac;
    letter-spacing: 0.05em;
    text-transform: uppercase;
}
.prop-player { font-weight: 600; color: #cbd5e1; }
.prop-proj   { color: #94a3b8; }
.prop-edge-pos { color: #f87171; font-weight: 700; }
.prop-edge-neg { color: #67e8f9; font-weight: 700; }

</style>
""", unsafe_allow_html=True)


# ── data loading ──────────────────────────────────────────────────────────────

@st.cache_data(ttl=None, show_spinner=False)
def load_results() -> dict | None:
    if not os.path.exists(RESULTS_FILE):
        return None
    with open(RESULTS_FILE) as f:
        return json.load(f)


@st.cache_data(ttl=None, show_spinner=False)
def load_season_stats() -> dict | None:
    if not os.path.exists(SEASON_STATS_FILE):
        return None
    with open(SEASON_STATS_FILE) as f:
        return json.load(f)


@st.cache_data(ttl=None, show_spinner=False)
def load_nba_results() -> dict | None:
    if not os.path.exists(NBA_RESULTS_FILE):
        return None
    with open(NBA_RESULTS_FILE) as f:
        return json.load(f)


def load_nhl_results() -> dict | None:
    if not os.path.exists(NHL_RESULTS_FILE):
        return None
    with open(NHL_RESULTS_FILE) as f:
        return json.load(f)


def load_soccer_results() -> dict | None:
    if not os.path.exists(SOCCER_RESULTS_FILE):
        return None
    with open(SOCCER_RESULTS_FILE) as f:
        return json.load(f)


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


# ── season header rendering ───────────────────────────────────────────────────

def _pct_color(pct: float | None) -> str:
    if pct is None:
        return ""
    if pct >= 55:
        return "green"
    if pct >= 50:
        return "yellow"
    return "red"


def _render_season_header(stats: dict) -> None:
    overall = stats.get("overall", {})
    wins    = overall.get("wins", 0) or 0
    losses  = overall.get("losses", 0) or 0
    pushes  = overall.get("pushes", 0) or 0
    no_line = overall.get("no_line", 0) or 0
    decided = overall.get("decided", 0) or 0
    win_pct = overall.get("win_pct")
    roi     = overall.get("roi")
    units   = overall.get("units")
    total_plays = stats.get("total_plays", 0) or 0
    accuracy = stats.get("projection_accuracy", {})
    is_st   = stats.get("is_spring_training", True)

    spring_badge = (
        '<span class="spring-badge">Spring Training — Tracking Accuracy Only</span>'
        if is_st else ""
    )

    if decided == 0 and no_line == 0:
        # No tracked data at all yet
        return

    # W-L display
    if decided > 0:
        pct_cls = _pct_color(win_pct)
        record_num  = f"{wins}–{losses}"
        record_cls  = pct_cls
        pct_display = f"{win_pct:.1f}%" if win_pct is not None else "—"
        roi_display = f"{roi:+.1f}%" if roi is not None else "—"
        units_display = f"{units:+.2f}" if units is not None else "—"
        roi_cls = "green" if (roi or 0) >= 0 else "red"
    else:
        record_num = "—"
        record_cls = ""
        pct_display = "—"
        roi_display = "—"
        units_display = "—"
        roi_cls = ""

    mae = accuracy.get("mae")
    within1 = accuracy.get("within_1_run")

    # Star record table rows
    by_stars = stats.get("by_stars", {})
    star_rows = ""
    for label in ["⭐⭐⭐", "⭐⭐", "⭐"]:
        s = by_stars.get(label, {})
        w, l = s.get("wins", 0) or 0, s.get("losses", 0) or 0
        p, nl = s.get("pushes", 0) or 0, s.get("no_line", 0) or 0
        n = w + l
        if n == 0 and nl == 0 and p == 0:
            continue
        wp = s.get("win_pct")
        cls = _pct_color(wp)
        pct_str = f"{wp:.1f}%" if wp is not None else "—"
        roi_s = s.get("roi")
        roi_str = f"{roi_s:+.1f}%" if roi_s is not None else "—"
        nl_str = f" + {nl} no-line" if nl else ""
        star_rows += (
            f'<tr><td>{label}</td>'
            f'<td class="{cls}">{w}–{l}</td>'
            f'<td class="{cls}">{pct_str}</td>'
            f'<td>{roi_str}</td>'
            f'<td class="dim">{p}{nl_str}</td></tr>'
        )

    star_table = ""
    if star_rows:
        star_table = f"""
        <table class="star-table" style="margin-top:12px">
          <thead><tr>
            <th>Rating</th><th>Record</th><th>Win %</th>
            <th>ROI</th><th>P / No Line</th>
          </tr></thead>
          <tbody>{star_rows}</tbody>
        </table>"""

    accuracy_html = ""
    if mae is not None:
        within1_str = f"{within1:.1f}%" if within1 is not None else "—"
        accuracy_html = f"""
        <div style="margin-top:12px;padding-top:10px;border-top:1px solid #1e2535">
          <span style="font-size:0.72em;color:#4a5568;text-transform:uppercase;
                       letter-spacing:0.08em">Projection Accuracy</span>
          <div class="stat-grid" style="margin-top:6px">
            <div class="stat-block">
              <div class="num">{mae:.2f}</div>
              <div class="lbl">MAE (runs)</div>
            </div>
            <div class="stat-block">
              <div class="num">{within1_str}</div>
              <div class="lbl">Within 1 run</div>
            </div>
            <div class="stat-block">
              <div class="num">{accuracy.get('within_2_runs', '—')}{'%' if accuracy.get('within_2_runs') else ''}</div>
              <div class="lbl">Within 2 runs</div>
            </div>
          </div>
        </div>"""

    html = f"""
    <div class="season-banner">
      {spring_badge}
      <div class="stat-grid">
        <div class="stat-block">
          <div class="num {record_cls}">{record_num}</div>
          <div class="lbl">Season Record (vs line)</div>
        </div>
        <div class="stat-block">
          <div class="num {record_cls}">{pct_display}</div>
          <div class="lbl">Win %</div>
        </div>
        <div class="stat-block">
          <div class="num {roi_cls}">{roi_display}</div>
          <div class="lbl">ROI</div>
        </div>
        <div class="stat-block">
          <div class="num {roi_cls}">{units_display}</div>
          <div class="lbl">Units</div>
        </div>
        <div class="stat-block">
          <div class="num">{total_plays}</div>
          <div class="lbl">Total Plays</div>
        </div>
        <div class="stat-block">
          <div class="num">{no_line}</div>
          <div class="lbl">No Line</div>
        </div>
      </div>
      {star_table}
      {accuracy_html}
    </div>"""

    st.html(html)


# ── analytics expander ────────────────────────────────────────────────────────

def _analytics_table(rows: list[tuple], headers: list[str]) -> str:
    head = "".join(f"<th>{h}</th>" for h in headers)
    body = ""
    for row in rows:
        cells = ""
        for cell in row:
            cls = ""
            val = cell
            if isinstance(cell, tuple):
                val, cls = cell
            cells += f'<td class="{cls}">{val}</td>'
        body += f"<tr>{cells}</tr>"
    return (
        f'<table class="analytics-table">'
        f'<thead><tr>{head}</tr></thead>'
        f'<tbody>{body}</tbody></table>'
    )


def _wl_row(d: dict) -> tuple:
    w, l = d.get("wins", 0) or 0, d.get("losses", 0) or 0
    wp   = d.get("win_pct")
    roi  = d.get("roi")
    nl   = d.get("no_line", 0) or 0
    cls  = _pct_color(wp)
    record_str = f"{w}–{l}" if (w + l) > 0 else "—"
    pct_str    = f"{wp:.1f}%" if wp is not None else "—"
    roi_str    = f"{roi:+.1f}%" if roi is not None else "—"
    nl_str     = str(nl) if nl else "—"
    return (record_str, cls), (pct_str, cls), (roi_str, ""), (nl_str, "dim")


def _render_analytics(stats: dict) -> None:
    with st.expander("📊 Analytics & Breakdowns", expanded=False):

        # ── by temperature ────────────────────────────────────────────────────
        st.markdown("**Temperature**")
        by_temp = stats.get("by_temperature", {})
        temp_rows = []
        for key in ("cold", "mild", "warm", "dome"):
            d = by_temp.get(key, {})
            label = d.get("label", key)
            if (d.get("wins", 0) or 0) + (d.get("losses", 0) or 0) + (d.get("no_line", 0) or 0) == 0:
                continue
            temp_rows.append(((label, ""),) + _wl_row(d))
        if temp_rows:
            st.html(_analytics_table(temp_rows, ["Temperature", "Record", "Win %", "ROI", "No Line"]))
        else:
            st.caption("No data yet.")

        st.html("<br>")

        # ── by wind ───────────────────────────────────────────────────────────
        st.markdown("**Wind**")
        by_wind = stats.get("by_wind", {})
        wind_rows = []
        for key in ("out", "in", "neutral", "dome"):
            d = by_wind.get(key, {})
            label = d.get("label", key)
            if (d.get("wins", 0) or 0) + (d.get("losses", 0) or 0) + (d.get("no_line", 0) or 0) == 0:
                continue
            wind_rows.append(((label, ""),) + _wl_row(d))
        if wind_rows:
            st.html(_analytics_table(wind_rows, ["Wind", "Record", "Win %", "ROI", "No Line"]))
        else:
            st.caption("No data yet.")

        st.html("<br>")

        # ── by park factor ────────────────────────────────────────────────────
        st.markdown("**Park Factor**")
        by_park = stats.get("by_park", {})
        park_rows = []
        for key in ("pitcher", "neutral", "hitter"):
            d = by_park.get(key, {})
            label = d.get("label", key)
            if (d.get("wins", 0) or 0) + (d.get("losses", 0) or 0) + (d.get("no_line", 0) or 0) == 0:
                continue
            park_rows.append(((label, ""),) + _wl_row(d))
        if park_rows:
            st.html(_analytics_table(park_rows, ["Park", "Record", "Win %", "ROI", "No Line"]))
        else:
            st.caption("No data yet.")

        st.html("<br>")

        # ── projection accuracy by stars ──────────────────────────────────────
        acc = stats.get("projection_accuracy", {})
        by_star_mae = acc.get("mae_by_stars", {})
        if by_star_mae:
            st.markdown("**Projection Accuracy by Star Rating (MAE)**")
            mae_rows = [
                ((label, ""), (f"{mae:.2f} runs", ""))
                for label, mae in by_star_mae.items()
            ]
            st.html(_analytics_table(mae_rows, ["Rating", "MAE"]))
            st.html("<br>")

        # ── factor correlations ───────────────────────────────────────────────
        correlations = stats.get("factor_correlations", [])
        if correlations:
            st.markdown("**Factor Performance** *(segments with 5+ decided plays)*")
            corr_rows = []
            for seg in correlations:
                w, l = seg.get("wins", 0) or 0, seg.get("losses", 0) or 0
                wp   = seg.get("win_pct")
                cls  = _pct_color(wp)
                pct_str = f"{wp:.1f}%" if wp is not None else "—"
                corr_rows.append((
                    (seg["factor"], ""),
                    (f"{w}–{l}", cls),
                    (pct_str, cls),
                ))
            st.html(_analytics_table(corr_rows, ["Factor", "Record", "Win %"]))
            st.html("<br>")

        # ── props record ──────────────────────────────────────────────────────
        props_rec = stats.get("props_record", {})
        if props_rec:
            st.markdown("**Player Props Record**")
            prop_rows = []
            for market, d in props_rec.items():
                w, l = d.get("wins", 0) or 0, d.get("losses", 0) or 0
                wp   = d.get("win_pct")
                roi  = d.get("roi")
                cls  = _pct_color(wp)
                prop_rows.append((
                    (market, ""),
                    (f"{w}–{l}", cls),
                    (f"{wp:.1f}%" if wp is not None else "—", cls),
                    (f"{roi:+.1f}%" if roi is not None else "—", ""),
                ))
            st.html(_analytics_table(prop_rows, ["Market", "Record", "Win %", "ROI"]))
            st.html("<br>")

        # ── parlay stats ──────────────────────────────────────────────────────
        parlay_stats = stats.get("parlay_stats", {})
        if parlay_stats:
            st.markdown("**Parlay Hit Rates**")
            _PARLAY_LABELS = {
                "parlay_3": "Sharp Card (3-leg, ⭐⭐⭐)",
                "parlay_5": "Value Card (5-leg, ⭐⭐+)",
                "parlay_7": "Fun Card (7-leg, ⭐+)",
            }
            p_rows = []
            for ptype in ("parlay_3", "parlay_5", "parlay_7"):
                d = parlay_stats.get(ptype)
                if not d:
                    continue
                hits    = d.get("hits", 0) or 0
                misses_ = d.get("misses", 0) or 0
                hp      = d.get("hit_pct")
                cls     = _pct_color(hp)
                p_rows.append((
                    (_PARLAY_LABELS.get(ptype, ptype), ""),
                    (f"{hits}–{misses_}", cls),
                    (f"{hp:.1f}%" if hp is not None else "—", cls),
                ))
            if p_rows:
                st.html(_analytics_table(p_rows, ["Parlay", "Hit–Miss", "Hit %"]))
                st.html("<br>")

        # ── biggest misses ────────────────────────────────────────────────────
        misses = stats.get("biggest_misses", [])
        if misses:
            st.markdown("**Biggest Model Misses**")
            miss_rows = []
            for m in misses[:8]:
                err   = m.get("projection_error", 0) or 0
                err_str = f"{err:+.1f}"
                res   = m.get("result", "")
                res_cls = "green" if res == "WIN" else "red" if res == "LOSS" else "dim"
                miss_rows.append((
                    (m.get("game_date", ""), "dim"),
                    (m.get("matchup", ""), ""),
                    (f"{m.get('projected_total', '?'):.1f}", ""),
                    (f"{m.get('actual_total', '?'):.1f}", ""),
                    (err_str, "red" if err > 0 else "green"),
                    (res, res_cls),
                    (m.get("star_rating", "—"), ""),
                ))
            st.html(_analytics_table(miss_rows,
                    ["Date", "Game", "Proj", "Actual", "Error", "Result", "Stars"]))


# ── game card rendering ───────────────────────────────────────────────────────

def _lean_badge(lean: str) -> str:
    cls = {"OVER": "lean-over", "UNDER": "lean-under"}.get(lean, "lean-neutral")
    return f'<span class="lean-badge {cls}">{lean}</span>'


def _conf_badge(conf: str) -> str:
    return f'<span class="conf-badge conf-{conf}">{conf.lower()}</span>'


def _proj_row_html(proj: dict, fe: dict, f5e: dict) -> str:
    full    = proj["proj_total_full"]
    f5      = proj["proj_total_f5"]
    line    = fe.get("consensus")
    edge    = fe.get("edge")
    f5_line = f5e.get("consensus")
    conf    = proj["confidence"]

    parts = [
        f'<span class="proj-label">Proj</span> <span class="proj-val">{full:.1f}</span>',
    ]
    if line is not None:
        parts.append(
            f'<span class="proj-label">Line</span> <span class="proj-val">{line:.1f}</span>'
        )
        if edge is not None:
            sign = "+" if edge > 0 else ""
            cls  = "edge-pos" if edge > 0 else "edge-neg"
            parts.append(
                f'<span class="proj-label">Edge</span> '
                f'<span class="{cls}">{sign}{edge:.1f}</span>'
            )
    else:
        parts.append('<span class="proj-label">No line yet</span>')

    f5_str = f'<span class="proj-label">F5</span> <span class="proj-val">{f5:.1f}</span>'
    if f5_line:
        f5_str += f' <span class="proj-label">vs {f5_line:.1f}</span>'
    parts.append(f5_str)
    parts.append(_conf_badge(conf))

    sep = ' <span style="color:#2d3748;margin:0 2px">·</span> '
    return f'<div class="proj-row">{sep.join(parts)}</div>'


def _meta_html(f: dict, game: dict) -> str:
    gtime    = game.get("game_time", "")
    gtime_et = game.get("game_time_et", "")
    time_str = f"{gtime} ({gtime_et})" if gtime_et else gtime

    temp     = f.get("temperature_f")
    wind_mph = f.get("wind_speed_mph") or 0.0
    wind_raw = f.get("wind_desc") or ""
    is_dome  = "dome" in wind_raw.lower()

    parts = [time_str]
    if temp is not None:
        parts.append(f"{temp:.0f}°F")
    if not is_dome and wind_mph >= 5:
        wd = wind_raw.replace("Blowing ", "").replace("blowing ", "")
        parts.append(f"Wind {wind_mph:.0f}mph {wd}")

    return '<div class="card-meta">' + "  ·  ".join(parts) + "</div>"


def _render_alerts(data: dict) -> None:
    """Render the top-of-page ⚡ ALERTS section. Shows nothing if no alerts."""
    lineup_alerts = data.get("alerts") or []
    transactions  = data.get("transactions") or []

    # Only surface transactions that affect a game today
    tx_relevant = [t for t in transactions if t.get("affects_game_pk")]

    if not lineup_alerts and not tx_relevant:
        return

    rows = ""

    for a in lineup_alerts:
        change_type = a.get("change_type", "")
        matchup     = a.get("matchup", "")
        player_out  = a.get("player_out", "")
        player_in   = a.get("player_in")
        old_proj    = a.get("old_projection")
        new_proj    = a.get("new_projection")
        old_conf    = a.get("old_confidence", "")
        new_conf    = a.get("new_confidence", "")

        if "SP_SCRATCH" in change_type:
            icon     = "🚨"
            side     = "HOME" if "HOME" in change_type else "AWAY"
            sub_desc = (
                f"{side} SP: <span style='color:#f87171;font-weight:600'>"
                f"{player_out}</span> → "
                f"<span style='color:#86efac;font-weight:600'>"
                f"{player_in or 'TBD'}</span>"
            )
            proj_html = ""
            if old_proj is not None and new_proj is not None:
                delta     = new_proj - old_proj
                sign      = "+" if delta > 0 else ""
                conf_html = (
                    f'<span class="alert-conf alert-conf-down">'
                    f'{old_conf} → {new_conf}</span>'
                ) if old_conf and new_conf and old_conf != new_conf else ""
                proj_html = (
                    f'<div class="alert-proj-change">'
                    f'<span class="alert-old">Proj {old_proj:.1f}</span>'
                    f'<span style="color:#4a5568">→</span>'
                    f'<span class="alert-new">{new_proj:.1f} ({sign}{delta:.1f})</span>'
                    f'{conf_html}'
                    f'</div>'
                )
        elif change_type == "BATTER_SCRATCH":
            icon     = "⚠️"
            sub_desc = (
                f"<span style='color:#fde68a;font-weight:600'>{player_out}</span> "
                f"scratched — TB prop invalidated"
            )
            proj_html = ""
        else:
            icon     = "📋"
            sub_desc = change_type
            proj_html = ""

        rows += (
            f'<div class="alert-row">'
            f'<div class="alert-icon">{icon}</div>'
            f'<div class="alert-body">'
            f'<span class="alert-matchup">{matchup}</span>'
            f'<span class="alert-detail">{sub_desc}</span>'
            f'{proj_html}'
            f'</div></div>'
        )

    for t in tx_relevant:
        desc     = t.get("description", "")
        matchup  = t.get("affects_matchup", "")
        player   = t.get("player_name", "")
        label    = t.get("type_label", "Transaction")
        rows += (
            f'<div class="alert-row">'
            f'<div class="alert-icon">📋</div>'
            f'<div class="alert-body">'
            f'<span class="alert-matchup">{matchup}</span>'
            f'<span class="alert-detail" style="color:#7dd3fc">[{label}]</span> '
            f'<span class="alert-txn-desc">{desc}</span>'
            f'</div></div>'
        )

    st.html(
        f'<div class="alerts-section">'
        f'<div class="alerts-title">⚡ Alerts</div>'
        f'{rows}'
        f'</div>'
    )


def _render_game_props(props: list[dict]) -> str:
    """Build HTML for props below a game card. Returns empty string if no props."""
    if not props:
        return ""

    rows = ""
    for p in props:
        market   = p.get("market", "")
        player   = p.get("player_name", "")
        proj     = p.get("projection")
        line     = p.get("line")
        edge_pct = p.get("edge_pct")
        lean     = p.get("lean", "")
        is_play  = p.get("is_play", False)

        proj_str = f"{proj:.1f}" if proj is not None else "—"
        line_str = f"{line:.1f}" if line is not None else "no line"

        if edge_pct is not None:
            sign = "+" if lean == "OVER" else "-" if lean == "UNDER" else ""
            edge_cls = "prop-edge-pos" if lean == "OVER" else "prop-edge-neg"
            edge_str = (
                f'<span class="{edge_cls}">{sign}{float(edge_pct)*100:.1f}% {lean}</span>'
            )
        else:
            edge_str = '<span style="color:#4a5568">no line</span>'

        play_badge = (
            '<span class="prop-play-badge">PLAY</span>' if is_play else ""
        )

        rows += (
            f'<div class="prop-row">'
            f'<span class="prop-market">{market}</span>'
            f'{play_badge}'
            f'<span class="prop-player">{player}</span>'
            f'<span class="prop-proj">Proj {proj_str} · Line {line_str}</span>'
            f'· {edge_str}'
            f'</div>'
        )

    return (
        f'<div class="props-section">'
        f'<div class="props-title">Player Props</div>'
        f'{rows}'
        f'</div>'
    )


def _render_card(b: dict) -> None:
    rating  = b["rating"]
    game    = b["game"]
    proj    = b["proj"]
    fe      = b.get("full_edge", {})
    f5e     = b.get("f5_edge", {})
    summary = b.get("summary", "")
    props   = b.get("props", [])
    f       = proj.get("factors", {})
    lean    = proj.get("lean", "NEUTRAL")
    is_play = rating != "NO PLAY"

    star_cls = {"⭐⭐⭐": "star3", "⭐⭐": "star2", "⭐": "star1"}.get(rating, "noplay")
    card_cls = f"game-card {star_cls}" if is_play else "game-card noplay"

    rating_html = (
        f'<span class="stars">{rating}</span>'
        if is_play else
        '<span class="noplay-badge">No Play</span>'
    )
    matchup = f'{game["away_team"]} @ {game["home_team"]}'

    header = (
        f'<div class="card-header">'
        f'{rating_html}'
        f'<span class="matchup">{matchup}</span>'
        f'{"" if lean == "NEUTRAL" else _lean_badge(lean)}'
        f'</div>'
    )

    proj_row = (
        _proj_row_html(proj, fe, f5e) if is_play else
        f'<div class="proj-row">'
        f'<span class="proj-label">Proj</span> '
        f'<span class="proj-val">{proj["proj_total_full"]:.1f}</span>'
        f'</div>'
    )

    props_html  = _render_game_props(props)

    # Inline alert badges on the card for any SP/batter changes
    card_alerts = b.get("alerts") or []
    alert_html  = ""
    for a in card_alerts:
        ct = a.get("type", "")
        if "SP_SCRATCH" in ct:
            side = "Home" if "HOME" in ct else "Away"
            p_out = a.get("player_out", "")
            p_in  = a.get("player_in") or "TBD"
            alert_html += (
                f'<div style="font-size:0.78em;color:#f87171;margin-top:4px">'
                f'🚨 {side} SP scratch: {p_out} → {p_in}'
                f'</div>'
            )
        elif ct == "BATTER_SCRATCH":
            alert_html += (
                f'<div style="font-size:0.78em;color:#fde68a;margin-top:4px">'
                f'⚠️ {a.get("player_out","")} scratched — TB prop invalid'
                f'</div>'
            )

    st.html(
        f'<div class="{card_cls}">'
        f'{header}'
        f'{_meta_html(f, game)}'
        f'{proj_row}'
        f'{alert_html}'
        f'<div class="card-summary">{summary}</div>'
        f'{props_html}'
        f'</div>'
    )


def _render_parlay_card(
    legs: list,
    card_class: str,
    title_class: str,
    icon: str,
    title: str,
    subtitle: str,
) -> None:
    """Render a single parlay card (one of the three tiers)."""
    if len(legs) < 2:
        return

    legs_html = ""
    for i, leg in enumerate(legs, 1):
        matchup      = leg.get("matchup", "")
        market_label = leg.get("market_label", "")
        rating       = leg.get("rating", "")
        proj         = leg.get("projection")
        line         = leg.get("line")
        lean         = leg.get("lean", "")

        proj_str = f"{float(proj):.1f}" if proj is not None else "—"
        line_str = f"{float(line):.1f}" if line is not None else "—"
        lean_cls = "lean-over" if lean == "OVER" else "lean-under" if lean == "UNDER" else ""

        legs_html += (
            f'<div class="parlay-leg">'
            f'<span class="parlay-matchup">{i}. {matchup}</span>'
            f'<span class="lean-badge {lean_cls}" style="font-size:0.78em">{market_label}</span>'
            f'<span style="color:#94a3b8;font-size:0.82em">Proj {proj_str}</span>'
            f'<span style="color:#94a3b8;font-size:0.82em">Line {line_str}</span>'
            f'<span>{rating}</span>'
            f'</div>'
        )

    st.html(
        f'<div class="{card_class}">'
        f'<div class="parlay-title {title_class}">'
        f'{icon} {title} <span style="font-weight:400;text-transform:none;'
        f'letter-spacing:0;font-size:0.9em;opacity:0.7"> — {subtitle}</span>'
        f'</div>'
        f'{legs_html}'
        f'</div>'
    )


def _render_parlays(data: dict) -> None:
    """Render all three parlay cards if legs are available."""
    p3 = data.get("parlay_3") or data.get("parlay", [])
    p5 = data.get("parlay_5", [])
    p7 = data.get("parlay_7", [])

    has_any = any(len(p) >= 2 for p in (p3, p5, p7))
    if not has_any:
        return

    st.html('<div class="section-hdr">⚡ Parlay Cards</div>')

    _render_parlay_card(
        p3,
        card_class="parlay-card-sharp",
        title_class="parlay-title-sharp",
        icon="🔥",
        title="SHARP CARD",
        subtitle="3-leg · ⭐⭐⭐ only",
    )
    _render_parlay_card(
        p5,
        card_class="parlay-card-value",
        title_class="parlay-title-value",
        icon="⚡",
        title="VALUE CARD",
        subtitle="5-leg · ⭐⭐ and higher",
    )
    _render_parlay_card(
        p7,
        card_class="parlay-card-risk",
        title_class="parlay-title-risk",
        icon="🎲",
        title="HIGH RISK / HIGH REWARD",
        subtitle="7-leg · ⭐ and higher — Fun money only",
    )


# ── NBA tab rendering ─────────────────────────────────────────────────────────

def _nba_lean_badge(lean: str) -> str:
    if lean in ("OVER", "over"):
        return '<span class="lean-badge lean-over">OVER</span>'
    if lean in ("UNDER", "under"):
        return '<span class="lean-badge lean-under">UNDER</span>'
    return '<span class="lean-badge lean-neutral">—</span>'


def _nhl_conf_badge(conf: str) -> str:
    c = (conf or "LOW").upper()
    return f'<span class="conf-badge conf-{c}">{c.lower()}</span>'


def _nhl_side_badge(side: str) -> str:
    s = (side or "").upper()
    cls = "lean-over" if s == "OVER" else "lean-under"
    return f'<span class="lean-badge {cls}">{s}</span>'


def _nhl_result_badge(result: str) -> str:
    r = (result or "").upper()
    if r == "WIN":
        return '<span style="color:#22c55e;font-weight:700">WIN</span>'
    if r == "LOSS":
        return '<span style="color:#f87171;font-weight:700">LOSS</span>'
    if r == "PUSH":
        return '<span style="color:#94a3b8;font-weight:700">PUSH</span>'
    return f'<span style="color:#4a5568">{r}</span>'


def _nhl_goalie_status(confirmed: bool, backup: bool, b2b: bool) -> str:
    """Return an inline goalie status string with icon."""
    if backup:
        return '<span style="color:#f59e0b;font-weight:600">⚠ backup</span>'
    if b2b:
        return '<span style="color:#f59e0b;font-weight:600">⚠ B2B fatigue</span>'
    if confirmed:
        return '<span style="color:#22c55e">✓ confirmed</span>'
    return '<span style="color:#4a5568">TBD</span>'


def _render_nhl_signal_card(s: dict) -> None:
    """Render a single NHL signal card matching the MLB card visual style."""
    home    = s.get("home_team", "")
    away    = s.get("away_team", "")
    side    = s.get("signal_side", "")
    edge    = s.get("edge")
    sim     = s.get("sim_prob")
    line    = s.get("closing_total")
    lam     = s.get("lambda_total_calibrated")
    tier    = s.get("confidence_tier", "LOW")
    vol     = s.get("volatility_bucket", "low") or "low"
    caut    = int(s.get("caution_flag") or 0)
    summary = s.get("summary", "")

    conf_h  = bool(s.get("goalie_confirmed_home", True))
    conf_a  = bool(s.get("goalie_confirmed_away", True))
    back_h  = int(s.get("backup_flag_home") or 0)
    back_a  = int(s.get("backup_flag_away") or 0)
    b2b_gh  = int(s.get("home_goalie_b2b") or 0)
    b2b_ga  = int(s.get("away_goalie_b2b") or 0)

    is_play   = tier in ("HIGH", "MEDIUM")
    conf_star = {"HIGH": "star3", "MEDIUM": "star2"}.get(tier, "noplay")
    card_cls  = f"game-card {conf_star}" if is_play else "game-card noplay"

    matchup   = f"{away} @ {home}"
    sep = ' <span style="color:#2d3748;margin:0 2px">·</span> '

    # Header: side badge | matchup | tier badge
    header = (
        f'<div class="card-header">'
        f'{_nhl_side_badge(side)}'
        f'<span class="matchup">{matchup}</span>'
        f'{_nhl_conf_badge(tier)}'
        f'</div>'
    )

    # Stats row: Line | Edge (pp) | Model total | Vol
    edge_pp   = f"{edge * 100:+.1f}pp" if edge is not None else "—"
    ecls      = "edge-pos" if (edge or 0) > 0 else "edge-neg"
    lam_str   = f"{lam:.1f}" if lam is not None else "—"
    line_str  = str(line) if line is not None else "—"
    stats_parts = [
        f'<span class="proj-label">Line</span> <span class="proj-val">{line_str}</span>',
        f'<span class="proj-label">Edge</span> <span class="{ecls}">{edge_pp}</span>',
        f'<span class="proj-label">Model</span> <span class="proj-val">{lam_str}</span>',
        f'<span class="proj-label">Vol</span> <span class="proj-val">{vol}</span>',
    ]
    if sim is not None:
        stats_parts.append(
            f'<span class="proj-label">P({side.lower()})</span> '
            f'<span class="proj-val">{sim * 100:.0f}%</span>'
        )
    stats_row = f'<div class="proj-row">{sep.join(stats_parts)}</div>'

    # Goalie status row
    gh_status = _nhl_goalie_status(conf_h, bool(back_h), bool(b2b_gh))
    ga_status = _nhl_goalie_status(conf_a, bool(back_a), bool(b2b_ga))
    goalie_row = (
        f'<div style="font-size:0.80em;color:#4a5568;margin-bottom:7px">'
        f'<strong style="color:#64748b">{home}</strong> {gh_status}'
        f'&nbsp;&nbsp;|&nbsp;&nbsp;'
        f'<strong style="color:#64748b">{away}</strong> {ga_status}'
        f'</div>'
    )

    # Summary text
    summary_html = (
        f'<div class="card-summary">{summary}</div>'
        if summary else ""
    )

    # Caution banner
    caution_html = ""
    if caut:
        caution_html = (
            '<div style="background:#1c1400;border:1px solid #92400e;border-radius:4px;'
            'padding:5px 10px;margin-top:6px;font-size:0.78em;color:#fde68a">'
            '⚠ 6.5-line over — caution bucket: historically underpriced ~4pp for this model'
            '</div>'
        )

    st.html(
        f'<div class="{card_cls}">'
        f'{header}'
        f'{stats_row}'
        f'{goalie_row}'
        f'{summary_html}'
        f'{caution_html}'
        f'</div>'
    )


def _render_nhl_tab() -> None:
    nhl = load_nhl_results()

    # ── header ────────────────────────────────────────────────────────────────
    col_title, col_btn = st.columns([5, 1])
    with col_title:
        if nhl:
            last_run  = _last_run_label(nhl)
            game_date = nhl.get("game_date", "")
            st.html(
                f"<h3 style='margin:0 0 4px 0'>🏒 NHL Totals</h3>"
                f"<span style='font-size:0.78em;color:#4a5568'>"
                f"Model run {last_run} · Projections for <strong>{game_date}</strong>"
                f"</span>"
            )
        else:
            st.markdown("### 🏒 NHL Totals")
    with col_btn:
        st.write("")
        if st.button("🔄 Refresh", key="nhl_refresh", use_container_width=True):
            st.cache_data.clear()
            st.rerun()

    if nhl is None:
        st.info(
            "No NHL projections available yet. "
            "Run `python push_nhl.py --no-push` on your local machine to publish today's signals."
        )
        return

    # FIX 5: freshness stamp
    last_updated    = nhl.get("last_updated", "")
    signals_source  = nhl.get("signals_source", "")
    src_color       = "#22c55e" if signals_source == "live" else "#f59e0b"
    if last_updated or signals_source:
        src_html = (
            f"&nbsp;&nbsp;|&nbsp;&nbsp;Source: "
            f"<strong style='color:{src_color}'>{signals_source}</strong>"
        ) if signals_source else ""
        st.html(
            f"<div style='font-size:0.75em;color:#4a5568;margin-bottom:8px'>"
            f"Last updated: <strong style='color:#94a3b8'>{last_updated}</strong>"
            f"{src_html}"
            f"</div>"
        )

    today_signals  = nhl.get("today_signals", [])
    recent_results = nhl.get("recent_results", [])
    season_perf    = nhl.get("season_performance", {})
    ot_diag_nhl    = nhl.get("ot_diagnostics", {})

    # ── SECTION 1: Today's Signals ─────────────────────────────────────────────
    st.html('<div class="section-hdr">🎯 Today\'s Signals</div>')
    if today_signals:
        plays    = [s for s in today_signals if s.get("confidence_tier") in ("HIGH", "MEDIUM")]
        no_plays = [s for s in today_signals if s not in plays]
        if plays:
            for s in plays:
                _render_nhl_signal_card(s)
        else:
            st.caption("No HIGH/MEDIUM signals today.")
        if no_plays:
            with st.expander(
                f"Low-confidence signals — {len(no_plays)}",
                expanded=False
            ):
                for s in no_plays:
                    _render_nhl_signal_card(s)
    else:
        st.caption("No qualified signals today (threshold: +10pp edge).")

    # ── SECTION 2: Recent Results (last 14 days) ───────────────────────────────
    st.html('<div class="section-hdr">📋 Recent Results — Last 14 Days</div>')
    if recent_results:
        # Quick W/L/P summary
        W = sum(1 for r in recent_results if r.get("result") == "WIN")
        L = sum(1 for r in recent_results if r.get("result") == "LOSS")
        P = sum(1 for r in recent_results if r.get("result") == "PUSH")
        n = W + L + P
        hit = W / (W + L) if (W + L) > 0 else None
        roi = (W * (100.0 / 110.0) - L) / n * 100 if n > 0 else None

        hit_cls = "green" if (hit or 0) >= 0.525 else "yellow" if (hit or 0) >= 0.50 else "red"
        hit_str = f"{hit * 100:.1f}%" if hit is not None else "—"
        roi_str = f"{roi:+.1f}%" if roi is not None else "—"

        st.html(f"""
        <div class="season-banner" style="padding:10px 16px;margin-bottom:10px">
          <div class="stat-grid">
            <div class="stat-block">
              <div class="num">{W}-{L}-{P}</div>
              <div class="lbl">W-L-P (14d)</div>
            </div>
            <div class="stat-block">
              <div class="num {hit_cls}">{hit_str}</div>
              <div class="lbl">Hit Rate</div>
            </div>
            <div class="stat-block">
              <div class="num">{roi_str}</div>
              <div class="lbl">ROI @ -110</div>
            </div>
          </div>
        </div>
        """)

        # Table of individual results
        rows_html = ""
        for r in recent_results:
            matchup = f"{r.get('away_team','')} @ {r.get('home_team','')}"
            side    = r.get("signal_side", "")
            line    = r.get("closing_total")
            edge    = r.get("edge")
            actual  = r.get("actual_total_goals_final")
            result  = r.get("result", "")
            tier    = r.get("confidence_tier", "LOW")
            gd      = r.get("game_date", "")

            line_s   = str(line) if line is not None else "—"
            edge_s   = f"{edge:+.3f}" if edge is not None else "—"
            actual_s = str(int(actual)) if actual is not None else "—"
            rows_html += (
                f'<tr>'
                f'<td class="dim">{gd}</td>'
                f'<td>{matchup}</td>'
                f'<td>{_nhl_conf_badge(tier)} {_nhl_side_badge(side)}</td>'
                f'<td>{line_s}</td>'
                f'<td class="dim">{edge_s}</td>'
                f'<td class="dim">{actual_s}</td>'
                f'<td>{_nhl_result_badge(result)}</td>'
                f'</tr>'
            )
        st.html(f"""
        <table class="star-table">
          <thead><tr>
            <th>Date</th><th>Matchup</th><th>Signal</th>
            <th>Line</th><th>Edge</th><th>Actual</th><th>Result</th>
          </tr></thead>
          <tbody>{rows_html}</tbody>
        </table>
        """)
    else:
        st.caption("No graded live signals in the past 14 days.")

    # ── SECTION 3: Season Performance (historical) ─────────────────────────────
    st.html('<div class="section-hdr">📊 Season Performance (Historical Backtest)</div>')
    if season_perf:
        tab_val, tab_oos, tab_comb = st.tabs(
            ["2023-24 Validate", "2024-25 OOS", "Combined"]
        )

        def _perf_block(split_key: str):
            d = season_perf.get(split_key, {})
            if not d or d.get("n", 0) == 0:
                st.caption("No data.")
                return
            W, L, P, n = d["W"], d["L"], d["P"], d["n"]
            hit = d.get("hit")
            roi = d.get("roi")
            hit_cls = "green" if (hit or 0) >= 0.525 else "yellow" if (hit or 0) >= 0.50 else "red"
            hit_str = f"{hit * 100:.1f}%" if hit is not None else "—"
            roi_str = f"{roi:+.2f}%" if roi is not None else "—"
            st.html(f"""
            <div class="season-banner">
              <div class="stat-grid">
                <div class="stat-block">
                  <div class="num">{W}-{L}-{P}</div>
                  <div class="lbl">W-L-P (n={n})</div>
                </div>
                <div class="stat-block">
                  <div class="num {hit_cls}">{hit_str}</div>
                  <div class="lbl">Hit Rate</div>
                </div>
                <div class="stat-block">
                  <div class="num">{roi_str}</div>
                  <div class="lbl">ROI @ -110</div>
                </div>
              </div>
            </div>
            """)

            # By confidence tier
            by_tier = season_perf.get("by_confidence_tier", {})
            if by_tier:
                tier_rows = ""
                for tier in ("HIGH", "MEDIUM", "LOW"):
                    td = by_tier.get(tier, {})
                    if not td or td.get("n", 0) == 0:
                        continue
                    th = td.get("hit")    # None when W+L=0
                    tr = td.get("roi")    # None when n=0
                    th_cls  = "green" if (th or 0) >= 0.525 else "yellow" if (th or 0) >= 0.50 else "red"
                    th_disp = f"{th * 100:.1f}%" if th is not None else "—"
                    tr_disp = f"{tr:+.2f}%" if tr is not None else "—"
                    tier_rows += (
                        f'<tr>'
                        f'<td>{_nhl_conf_badge(tier)}</td>'
                        f'<td class="dim">{td["n"]}</td>'
                        f'<td>{td["W"]}-{td["L"]}-{td["P"]}</td>'
                        f'<td class="{th_cls}">{th_disp}</td>'
                        f'<td class="dim">{tr_disp}</td>'
                        f'</tr>'
                    )
                if tier_rows:
                    st.html(f"""
                    <table class="star-table" style="margin-top:8px">
                      <thead><tr>
                        <th>Tier</th><th>n</th><th>W-L-P</th><th>Hit%</th><th>ROI</th>
                      </tr></thead>
                      <tbody>{tier_rows}</tbody>
                    </table>
                    """)

        with tab_val:
            _perf_block("validate")
        with tab_oos:
            _perf_block("oos")
        with tab_comb:
            _perf_block("combined")

        st.html("""
        <div style="font-size:0.75em;color:#4a5568;margin-top:10px;line-height:1.6">
          Validate = 2023-24 (in-sample calibration) · OOS = 2024-25 (blind forward test)<br>
          Threshold: edge ≥ 0.10 · Juice: -110 · Break-even: 52.38%<br>
          Note: 6.5-line OVERs underpriced ~4pp in backtest — use caution flag as guide
        </div>
        """)
    else:
        st.caption("Season performance data unavailable.")

    # ── SECTION 4: OT Diagnostics ─────────────────────────────────────────────
    if ot_diag_nhl and ot_diag_nhl.get("total_graded", 0) > 0:
        ot_g    = ot_diag_nhl.get("ot_games", 0)
        so_g    = ot_diag_nhl.get("so_games", 0)
        total_g = ot_diag_nhl.get("total_graded", 1)
        ot_rt   = ot_diag_nhl.get("ot_rate")
        flips   = ot_diag_nhl.get("ot_flips", 0)
        frate   = ot_diag_nhl.get("ot_flip_rate")
        ul      = ot_diag_nhl.get("under_ot_losses", 0)
        ol      = ot_diag_nhl.get("over_ot_losses", 0)
        ot_rt_s = f"{ot_rt * 100:.1f}%" if ot_rt is not None else "—"
        frate_s = f"{frate * 100:.1f}%" if frate is not None else "—"
        st.html(f"""
        <div style="background:#0f1117;border:1px solid #1e2535;border-radius:6px;
                    padding:10px 14px;margin-bottom:10px;font-size:0.82em">
          <div style="font-size:0.72em;color:#4a5568;text-transform:uppercase;
                      letter-spacing:0.08em;margin-bottom:8px">OT Diagnostics (Live Signals)</div>
          <div style="display:flex;gap:24px;flex-wrap:wrap;margin-bottom:6px">
            <span>OT game rate: <strong>{ot_rt_s}</strong></span>
            <span>OT flips (changed outcome): <strong>{flips}</strong> of {ot_g} OT games ({frate_s})</span>
            <span>Shootout games: <strong>{so_g}</strong></span>
            <span>Under losses from OT: <strong>{ul}</strong></span>
            <span>Over losses from OT: <strong>{ol}</strong></span>
          </div>
          <div style="color:#4a5568;font-size:0.78em">
            Official grading includes OT/SO per sportsbook rules. OT diagnostics are for analysis only.
          </div>
        </div>
        """)

    # ── CLV Summary ────────────────────────────────────────────────────────────
    clv_nhl = nhl.get("clv_summary", {})
    if clv_nhl:
        n_clv    = clv_nhl.get("total_with_clv", 0)
        avg_clv  = clv_nhl.get("avg_clv")
        pct_pos  = clv_nhl.get("pct_positive_clv")
        coverage = clv_nhl.get("clv_coverage", 0.0)

        st.html('<div class="section-hdr">📈 CLV Summary (Closing Line Value)</div>')

        if n_clv < 20:
            st.caption(f"Insufficient sample for CLV conclusions (n={n_clv})")
        elif coverage < 50:
            st.caption(f"CLV coverage low — closing line capture not yet fully populated ({coverage:.0f}%)")
        else:
            avg_clv_s = f"{avg_clv:+.2f}" if avg_clv is not None else "—"
            pct_pos_s = f"{pct_pos:.0f}%" if pct_pos is not None else "—"
            avg_color = "#22c55e" if (avg_clv or 0) > 0 else "#ef4444"
            pct_color = "#22c55e" if (pct_pos or 0) > 50 else "#ef4444"
            by_side   = clv_nhl.get("avg_clv_by_side", {})
            over_clv  = by_side.get("OVER")
            under_clv = by_side.get("UNDER")
            over_s    = f"{over_clv:+.2f}" if over_clv is not None else "—"
            under_s   = f"{under_clv:+.2f}" if under_clv is not None else "—"
            st.html(f"""
            <div class="season-banner" style="padding:10px 16px;margin-bottom:6px">
              <div class="stat-grid">
                <div class="stat-block">
                  <div class="num" style="color:{avg_color}">{avg_clv_s}</div>
                  <div class="lbl">Avg CLV (pts)</div>
                </div>
                <div class="stat-block">
                  <div class="num" style="color:{pct_color}">{pct_pos_s}</div>
                  <div class="lbl">% Positive CLV</div>
                </div>
                <div class="stat-block">
                  <div class="num">{over_s}</div>
                  <div class="lbl">OVER CLV</div>
                </div>
                <div class="stat-block">
                  <div class="num">{under_s}</div>
                  <div class="lbl">UNDER CLV</div>
                </div>
              </div>
            </div>
            <div style="font-size:0.73em;color:#4a5568;margin-top:4px;line-height:1.5">
              CLV measures whether decision lines beat closing lines.
              Positive = sharp. Target: &gt;0 on average.
              NHL skews UNDER — per-side split matters.
            </div>
            """)


# ── Soccer tab rendering ───────────────────────────────────────────────────────

def _soccer_tier_badge(tier: str) -> str:
    colors = {
        "HIGH":   ("#22c55e", "#052e16"),
        "MEDIUM": ("#eab308", "#1c1400"),
        "LOW":    ("#64748b", "#0f172a"),
    }
    fg, bg = colors.get(tier, ("#64748b", "#0f172a"))
    return (
        f'<span style="background:{bg};color:{fg};border:1px solid {fg};'
        f'border-radius:4px;padding:1px 7px;font-size:0.72em;font-weight:700;'
        f'letter-spacing:0.06em;margin-left:6px">{tier}</span>'
    )


def _soccer_move_badge(move: float | None) -> str:
    if move is None:
        return ""
    if move > 0.03:
        return '<span style="color:#22c55e;font-size:0.80em">→ Late $$$ on OVER</span>'
    if move < -0.03:
        return '<span style="color:#f87171;font-size:0.80em">← Late $$$ on UNDER</span>'
    return '<span style="color:#4a5568;font-size:0.80em">→ No significant move</span>'


def _soccer_result_badge(result: str) -> str:
    if result == "WIN":
        return '<td class="green">WIN</td>'
    if result == "LOSS":
        return '<td class="red">LOSS</td>'
    if result == "PUSH":
        return '<td class="yellow">PUSH</td>'
    return '<td class="dim">—</td>'


def _render_soccer_signal_card(s: dict) -> None:
    home    = s.get("home_team", "")
    away    = s.get("away_team", "")
    edge    = s.get("edge")
    tier    = s.get("confidence_tier", "LOW")
    model_t = s.get("model_total")
    move    = s.get("market_move_to_over_2_5")
    lineup  = bool(s.get("lineup_confirmed", False))
    summary = s.get("summary", "")
    gt      = s.get("game_time_et", "")
    league  = s.get("league_id", "")
    over_p  = s.get("over_price")

    is_play   = tier in ("HIGH", "MEDIUM")
    conf_star = {"HIGH": "star3", "MEDIUM": "star2"}.get(tier, "noplay")
    card_cls  = f"game-card {conf_star}" if is_play else "game-card noplay"

    sep = ' <span style="color:#2d3748;margin:0 2px">·</span> '

    league_tag = (
        '<span style="font-size:0.72em;color:#4a5568;margin-right:6px">'
        f'{"🏴󠁧󠁢󠁥󠁮󠁧󠁿 EPL" if league == "EPL" else "🇩🇪 Bundesliga"}'
        f'</span>'
    )
    over_badge = (
        '<span style="background:#052e16;color:#22c55e;border:1px solid #22c55e;'
        'border-radius:4px;padding:1px 7px;font-size:0.72em;font-weight:700;'
        'letter-spacing:0.06em;margin-right:6px">OVER 2.5</span>'
    )

    header = (
        f'<div class="card-header">'
        f'{over_badge}{league_tag}'
        f'<span class="matchup">{away} @ {home}</span>'
        f'{_soccer_tier_badge(tier)}'
        f'</div>'
    )

    edge_pp  = f"{edge * 100:+.1f}pp" if edge is not None else "—"
    ecls     = "edge-pos" if (edge or 0) > 0 else "edge-neg"
    model_s  = f"{model_t:.1f}" if model_t is not None else "—"
    over_s   = f"{over_p:.2f}" if over_p is not None else "—"

    stats_parts = [
        f'<span class="proj-label">Line</span> <span class="proj-val">2.5</span>',
        f'<span class="proj-label">Edge</span> <span class="{ecls}">{edge_pp}</span>',
        f'<span class="proj-label">Model Goals</span> <span class="proj-val">{model_s}</span>',
    ]
    if over_p is not None:
        stats_parts.append(
            f'<span class="proj-label">Over Price</span> <span class="proj-val">{over_s}</span>'
        )
    if gt:
        stats_parts.append(
            f'<span class="proj-label">Kickoff</span> <span class="proj-val">{gt}</span>'
        )
    stats_row = f'<div class="proj-row">{sep.join(stats_parts)}</div>'

    move_html = ""
    move_badge = _soccer_move_badge(move)
    lineup_icon = "✓ Lineup confirmed" if lineup else "? Lineup estimated"
    lineup_color = "#22c55e" if lineup else "#4a5568"
    move_html = (
        f'<div style="font-size:0.80em;color:#4a5568;margin-bottom:7px">'
        f'{move_badge}'
        f'&nbsp;&nbsp;|&nbsp;&nbsp;'
        f'<span style="color:{lineup_color}">{lineup_icon}</span>'
        f'</div>'
    )

    summary_html = (
        f'<div class="card-summary">{summary}</div>' if summary else ""
    )

    st.html(
        f'<div class="{card_cls}">'
        f'{header}{stats_row}{move_html}{summary_html}'
        f'</div>'
    )


def _render_soccer_parlay_candidates(parlay_candidates: list) -> None:
    """
    Render Over 1.5 parlay candidates section.
    Entertainment / parlay-support only — not a validated standalone product.
    """
    st.html('<div class="section-hdr">⚽ Over 1.5 Parlay Candidates</div>')

    # Disclaimer — neutral info style
    st.html(
        '<div style="background:#0f172a;border:1px solid #334155;border-radius:6px;'
        'padding:8px 14px;margin-bottom:12px;font-size:0.80em;color:#94a3b8">'
        '⚠️ <strong>Entertainment / parlay-support only.</strong> '
        'Not validated for standalone betting. Model probability only — '
        'not a proven edge product. Parlay legs are correlated when from the '
        'same league or match day.'
        '</div>'
    )

    if not parlay_candidates:
        st.caption(
            "No Over 1.5 parlay candidates today "
            "(threshold: 80% model probability, 3.2 projected goals)."
        )
        return

    for c in parlay_candidates:
        home      = c.get("home_team", "")
        away      = c.get("away_team", "")
        league    = c.get("league", "")
        tier      = c.get("confidence_tier", "HIGH")
        proj      = c.get("projected_total")
        p_over    = c.get("model_p_over_1_5")
        mkt_p     = c.get("market_implied_p_1_5")
        mkt_line  = c.get("market_line_1_5")
        lineup    = bool(c.get("lineup_confirmed", False))
        gt        = c.get("game_time_et", "")

        league_tag = (
            '<span style="font-size:0.72em;color:#4a5568;margin-right:6px">'
            f'{"🏴󠁧󠁢󠁥󠁮󠁧󠁿 EPL" if league == "EPL" else "🇩🇪 Bundesliga"}'
            '</span>'
        )
        over15_badge = (
            '<span style="background:#1e1b4b;color:#a5b4fc;border:1px solid #6366f1;'
            'border-radius:4px;padding:1px 7px;font-size:0.72em;font-weight:700;'
            'letter-spacing:0.06em;margin-right:6px">OVER 1.5</span>'
        )
        tier_color  = "#22c55e" if tier == "VERY HIGH" else "#f59e0b"
        tier_bg     = "#052e16" if tier == "VERY HIGH" else "#431407"
        tier_border = "#166534" if tier == "VERY HIGH" else "#9a3412"
        tier_badge  = (
            f'<span style="background:{tier_bg};color:{tier_color};'
            f'border:1px solid {tier_border};border-radius:4px;padding:1px 7px;'
            f'font-size:0.72em;font-weight:700;margin-left:6px">{tier}</span>'
        )

        header = (
            f'<div class="card-header">'
            f'{over15_badge}{league_tag}'
            f'<span class="matchup">{away} @ {home}</span>'
            f'{tier_badge}'
            f'</div>'
        )

        sep = ' <span style="color:#2d3748;margin:0 2px">·</span> '
        proj_s  = f"{proj:.1f}" if proj is not None else "—"
        p_s     = f"{p_over * 100:.1f}%" if p_over is not None else "—"

        stats_parts = [
            f'<span class="proj-label">Projected Goals</span> <span class="proj-val">{proj_s}</span>',
            f'<span class="proj-label">P(Over 1.5)</span> <span class="proj-val" style="color:#a5b4fc">{p_s}</span>',
        ]
        if mkt_line is not None and mkt_p is not None:
            mkt_s = f"{mkt_p * 100:.1f}%"
            stats_parts.append(
                f'<span class="proj-label">Market 1.5</span> <span class="proj-val">{mkt_s}</span>'
            )
        if gt:
            stats_parts.append(
                f'<span class="proj-label">Kickoff</span> <span class="proj-val">{gt}</span>'
            )
        stats_row = f'<div class="proj-row">{sep.join(stats_parts)}</div>'

        lineup_icon  = "✓ Lineup confirmed" if lineup else "? Lineup estimated"
        lineup_color = "#22c55e" if lineup else "#4a5568"
        lineup_html  = (
            f'<div style="font-size:0.80em;color:{lineup_color};margin-bottom:4px">'
            f'{lineup_icon}</div>'
        )

        st.html(
            f'<div class="game-card" style="border-color:#334155">'
            f'{header}{stats_row}{lineup_html}'
            f'</div>'
        )


def _render_soccer_tab() -> None:
    soccer = load_soccer_results()

    # ── header ────────────────────────────────────────────────────────────────
    col_title, col_btn = st.columns([5, 1])
    with col_title:
        if soccer:
            last_run  = _last_run_label(soccer)
            game_date = soccer.get("game_date", "")
            st.html(
                f"<h3 style='margin:0 0 4px 0'>⚽ Soccer Over 2.5 Specialist</h3>"
                f"<span style='font-size:0.78em;color:#4a5568'>"
                f"Model run {last_run} · Projections for <strong>{game_date}</strong>"
                f"</span>"
            )
        else:
            st.markdown("### ⚽ Soccer Over 2.5 Specialist")
    with col_btn:
        st.write("")
        if st.button("🔄 Refresh", key="soccer_refresh", use_container_width=True):
            st.cache_data.clear()
            st.rerun()

    if soccer is None:
        st.info(
            "No Soccer projections available yet. "
            "Run `python push_soccer.py --no-push` to publish today's signals."
        )
        return

    st.html(
        '<div style="background:#051f14;border:1px solid #166534;border-radius:6px;'
        'padding:8px 14px;margin-bottom:12px;font-size:0.82em;color:#86efac">'
        '⚽ Soccer model signals <strong>Over 2.5 goals</strong> only. '
        'Under signals are not generated by design.'
        '</div>'
    )

    last_updated   = soccer.get("last_updated", "")
    signals_source = soccer.get("signals_source", "")
    src_color = "#22c55e" if signals_source == "live" else "#f59e0b"
    if last_updated or signals_source:
        src_html = (
            f"&nbsp;&nbsp;|&nbsp;&nbsp;Source: "
            f"<strong style='color:{src_color}'>{signals_source}</strong>"
        ) if signals_source else ""
        st.html(
            f"<div style='font-size:0.75em;color:#4a5568;margin-bottom:8px'>"
            f"Last updated: <strong style='color:#94a3b8'>{last_updated}</strong>"
            f"{src_html}</div>"
        )

    today_signals  = soccer.get("today_signals", [])
    recent_results = soccer.get("recent_results", [])
    season_perf    = soccer.get("season_performance", {})

    # ── SECTION 1: Today's Signals ─────────────────────────────────────────────
    st.html('<div class="section-hdr">🎯 Today\'s Signals — OVER 2.5</div>')
    if today_signals:
        plays    = [s for s in today_signals if s.get("confidence_tier") in ("HIGH", "MEDIUM")]
        low_sigs = [s for s in today_signals if s not in plays]
        if plays:
            for s in plays:
                _render_soccer_signal_card(s)
        else:
            st.caption("No HIGH/MEDIUM signals today.")
        if low_sigs:
            with st.expander(f"LOW confidence signals — {len(low_sigs)}", expanded=False):
                for s in low_sigs:
                    _render_soccer_signal_card(s)
    else:
        st.caption(
            "No qualified Over 2.5 signals today "
            "(threshold: +6pp edge, market move ≥ −3pp, Over only)."
        )

    # ── SECTION 1b: Over 1.5 Parlay Candidates ────────────────────────────────
    _render_soccer_parlay_candidates(soccer.get("parlay_candidates", []))

    # ── SECTION 2: Recent Results ──────────────────────────────────────────────
    st.html('<div class="section-hdr">📋 Recent Results — Last 14 Days</div>')
    if recent_results:
        W = sum(1 for r in recent_results if r.get("result") == "WIN")
        L = sum(1 for r in recent_results if r.get("result") == "LOSS")
        P = sum(1 for r in recent_results if r.get("result") == "PUSH")
        n = W + L + P
        hit = W / (W + L) if (W + L) > 0 else None
        roi = (W * (100.0 / 110.0) - L) / n * 100 if n > 0 else None

        hit_cls = "green" if (hit or 0) >= 0.54 else "yellow" if (hit or 0) >= 0.525 else "red"
        hit_str = f"{hit * 100:.1f}%" if hit is not None else "—"
        roi_str = f"{roi:+.1f}%" if roi is not None else "—"

        st.html(f"""
        <div class="season-banner" style="padding:10px 16px;margin-bottom:10px">
          <div class="stat-grid">
            <div class="stat-block">
              <div class="num">{W}-{L}-{P}</div>
              <div class="lbl">W-L-P (14d)</div>
            </div>
            <div class="stat-block">
              <div class="num {hit_cls}">{hit_str}</div>
              <div class="lbl">Hit Rate</div>
            </div>
            <div class="stat-block">
              <div class="num">{roi_str}</div>
              <div class="lbl">ROI @ -110</div>
            </div>
          </div>
        </div>
        """)

        rows_html = ""
        for r in recent_results:
            gd     = r.get("game_date", "")
            lg     = r.get("league_id", "")
            home   = r.get("home_team", "")
            away   = r.get("away_team", "")
            edge   = r.get("edge")
            actual = r.get("actual_total_goals")
            result = r.get("result", "")
            tier   = r.get("confidence_tier", "LOW")

            matchup  = f"{away} @ {home}"
            edge_s   = f"{edge:+.3f}" if edge is not None else "—"
            actual_s = str(int(actual)) if actual is not None else "—"
            lg_s     = "EPL" if lg == "EPL" else "BUN"

            rows_html += (
                f'<tr>'
                f'<td class="dim">{gd}</td>'
                f'<td class="dim">{lg_s}</td>'
                f'<td>{matchup}</td>'
                f'<td>{_soccer_tier_badge(tier)}</td>'
                f'<td class="dim">{edge_s}</td>'
                f'<td class="dim">{actual_s}</td>'
                f'{_soccer_result_badge(result)}'
                f'</tr>'
            )
        st.html(f"""
        <table class="star-table">
          <thead><tr>
            <th>Date</th><th>League</th><th>Matchup</th>
            <th>Tier</th><th>Edge</th><th>Goals</th><th>Result</th>
          </tr></thead>
          <tbody>{rows_html}</tbody>
        </table>
        """)
    else:
        st.caption("No graded live signals in the past 14 days.")

    # ── SECTION 3: Season Performance ─────────────────────────────────────────
    st.html('<div class="section-hdr">📊 Season Performance</div>')

    overall  = season_perf.get("overall", {})
    oos_ref  = season_perf.get("oos_reference", {})
    deploy_d = soccer.get("deployment_start_date", "2026-03-17")

    # ── Live Results (since deployment) ────────────────────────────────────────
    st.html(
        f"<div style='font-size:0.82em;font-weight:600;color:#94a3b8;"
        f"margin-bottom:6px'>Live Results (since {deploy_d})</div>"
    )
    if overall and overall.get("n", 0) > 0:
        W, L, P = overall["W"], overall["L"], overall["P"]
        n    = overall["n"]
        hit  = overall.get("hit")
        roi  = overall.get("roi")
        hit_cls = "green" if (hit or 0) >= 0.54 else "yellow" if (hit or 0) >= 0.525 else "red"
        hit_s = f"{hit * 100:.1f}%" if hit is not None else "—"
        roi_s = f"{roi:+.2f}%" if roi is not None else "—"
        st.html(f"""
        <div class="season-banner">
          <div class="stat-grid">
            <div class="stat-block"><div class="num">{W}-{L}-{P}</div><div class="lbl">W-L-P (n={n})</div></div>
            <div class="stat-block"><div class="num {hit_cls}">{hit_s}</div><div class="lbl">Hit Rate</div></div>
            <div class="stat-block"><div class="num">{roi_s}</div><div class="lbl">ROI @ -110</div></div>
          </div>
        </div>
        """)

        # By tier
        by_tier = season_perf.get("by_tier", {})
        if by_tier:
            st.caption("By confidence tier")
            tier_rows = ""
            for tier in ("HIGH", "MEDIUM", "LOW"):
                d = by_tier.get(tier, {})
                if not d or d.get("n", 0) == 0:
                    continue
                h = d.get("hit"); r = d.get("roi"); tn = d.get("n", 0)
                h_s = f"{h*100:.1f}%" if h is not None else "—"
                r_s = f"{r:+.2f}%" if r is not None else "—"
                r_cls = "green" if (r or 0) > 0 else "red"
                tier_rows += (
                    f'<tr><td>{tier}</td><td>{tn}</td>'
                    f'<td class="{"green" if (h or 0)>=0.54 else "red"}">{h_s}</td>'
                    f'<td class="{r_cls}">{r_s}</td></tr>'
                )
            if tier_rows:
                st.html(f"""
                <table class="star-table">
                  <thead><tr><th>Tier</th><th>N</th><th>Hit%</th><th>ROI</th></tr></thead>
                  <tbody>{tier_rows}</tbody>
                </table>""")

        # By league
        by_league = season_perf.get("by_league", {})
        if by_league:
            st.caption("By league")
            lg_rows = ""
            for lg, name in [("EPL", "English Premier League"), ("BUN", "Bundesliga")]:
                d = by_league.get(lg, {})
                if not d or d.get("n", 0) == 0:
                    continue
                h = d.get("hit"); r = d.get("roi"); tn = d.get("n", 0)
                h_s = f"{h*100:.1f}%" if h is not None else "—"
                r_s = f"{r:+.2f}%" if r is not None else "—"
                r_cls = "green" if (r or 0) > 0 else "red"
                lg_rows += (
                    f'<tr><td>{name}</td><td>{tn}</td>'
                    f'<td class="{"green" if (h or 0)>=0.54 else "red"}">{h_s}</td>'
                    f'<td class="{r_cls}">{r_s}</td></tr>'
                )
            if lg_rows:
                st.html(f"""
                <table class="star-table">
                  <thead><tr><th>League</th><th>N</th><th>Hit%</th><th>ROI</th></tr></thead>
                  <tbody>{lg_rows}</tbody>
                </table>""")
    else:
        st.caption("No graded live signals yet.")

    # ── OOS Backtest Reference (always shown) ──────────────────────────────────
    st.html(
        "<div style='font-size:0.82em;font-weight:600;color:#94a3b8;"
        "margin-top:16px;margin-bottom:6px'>OOS Backtest Reference (2024-25 holdout)</div>"
    )
    if oos_ref:
        ref_rows = ""
        for tier, d in [("Overall", oos_ref.get("overall", {})),
                        ("HIGH (edge≥10pp)", oos_ref.get("HIGH", {})),
                        ("MEDIUM (8-10pp)", oos_ref.get("MEDIUM", {})),
                        ("LOW (6-8pp)", oos_ref.get("LOW", {}))]:
            if not d:
                continue
            h = d.get("hit"); r = d.get("roi"); tn = d.get("n", 0)
            h_s = f"{h*100:.1f}%" if h is not None else "—"
            r_s = f"{r*100:+.1f}%" if r is not None else "—"
            r_cls = "green" if (r or 0) > 0 else "red"
            ref_rows += (
                f'<tr><td class="dim">{tier}</td><td class="dim">{tn}</td>'
                f'<td class="{"green" if (h or 0)>=0.54 else "yellow"}">{h_s}</td>'
                f'<td class="{r_cls}">{r_s}</td></tr>'
            )
        st.html(f"""
        <table class="star-table">
          <thead><tr><th>Segment</th><th>N</th><th>Hit%</th><th>ROI</th></tr></thead>
          <tbody>{ref_rows}</tbody>
        </table>
        <div style="font-size:0.72em;color:#4a5568;margin-top:6px">
        Over 2.5 specialist · Min edge 6pp · Market move filter −3pp ·
        Juice −110 · Break-even 52.38% · UNDER signals excluded by design.
        </div>
        """)


def _nba_conf_badge(conf: str) -> str:
    c = (conf or "LOW").upper()
    return f'<span class="conf-badge conf-{c}">{c.lower()}</span>'


def _render_nba_card(g: dict) -> None:
    """Render a single NBA game card matching the MLB card visual style."""
    home    = g.get("home_team", "")
    away    = g.get("away_team", "")
    conf    = g.get("confidence", "LOW")
    lean    = g.get("lean", "")
    pred    = g.get("pred_total")
    line    = g.get("line")
    edge    = g.get("edge")
    p_over  = g.get("p_over")
    tip     = g.get("game_time_et") or "—"
    summary = g.get("summary", "")
    gap     = bool(g.get("market_gap_flag"))
    home_inj = g.get("home_injuries") or []
    away_inj = g.get("away_injuries") or []

    pred_h1 = g.get("pred_h1")
    h1_lean = g.get("h1_lean")
    h1_line = g.get("h1_line")
    h1_edge = g.get("h1_edge")
    h1_conf = g.get("h1_confidence")

    is_play = conf in ("HIGH", "MEDIUM")
    conf_star = {"HIGH": "star3", "MEDIUM": "star2"}.get(conf, "noplay")
    card_cls  = f"game-card {conf_star}" if is_play else "game-card noplay"

    matchup   = f"{away} @ {home}"
    lean_html = _nba_lean_badge(lean) if lean and lean not in ("—", "") else ""

    header = (
        f'<div class="card-header">'
        f'{_nba_conf_badge(conf)}'
        f'<span class="matchup">{matchup}</span>'
        f'{lean_html}'
        f'</div>'
    )

    meta = f'<div class="card-meta">{tip}</div>'

    # Playoff context block
    playoff_context_html = ""
    if g.get("is_playoff"):
        po_parts = []
        # Round label
        rnd = g.get("playoff_round") or ""
        if rnd:
            po_parts.append(f'<span style="color:#93c5fd;font-weight:600">{rnd}</span>')
        # Series game number
        sgn = g.get("series_game_number")
        if sgn:
            po_parts.append(f'<span>Game {sgn}</span>')
        # Series standing
        home_wins = g.get("home_series_wins")
        away_wins = g.get("away_series_wins")
        if home_wins is not None and away_wins is not None:
            if home_wins == away_wins:
                standing = f"Series tied {home_wins}–{away_wins}"
            elif home_wins > away_wins:
                standing = f"{home} leads {home_wins}–{away_wins}"
            else:
                standing = f"{away} leads {away_wins}–{home_wins}"
            po_parts.append(f'<span>{standing}</span>')
        # Series blend weight
        bw = g.get("playoff_blend_weight")
        if bw is not None:
            bw_pct = int(round(bw * 100))
            po_parts.append(f'<span style="color:#6b7280">Series weight: {bw_pct}%</span>')
        if po_parts:
            sep2 = ' <span style="color:#2d3748;margin:0 2px">·</span> '
            playoff_context_html = (
                f'<div style="font-size:0.80em;padding:4px 0 2px 0;'
                f'border-top:1px solid #1e3a5f;margin-top:4px;color:#cbd5e1">'
                f'{sep2.join(po_parts)}</div>'
            )

    # Projection row
    sep = ' <span style="color:#2d3748;margin:0 2px">·</span> '
    proj_parts = []
    if pred is not None:
        proj_parts.append(
            f'<span class="proj-label">Proj</span> '
            f'<span class="proj-val">{pred:.1f}</span>'
        )
    if line is not None:
        proj_parts.append(
            f'<span class="proj-label">Line</span> '
            f'<span class="proj-val">{line:.1f}</span>'
        )
    else:
        proj_parts.append('<span class="proj-label">No line yet</span>')
    if edge is not None:
        sign = "+" if edge > 0 else ""
        ecls = "edge-pos" if edge > 0 else "edge-neg"
        proj_parts.append(
            f'<span class="proj-label">Edge</span> '
            f'<span class="{ecls}">{sign}{edge:.1f}</span>'
        )
    if p_over is not None:
        p_dir  = p_over if lean == "OVER" else 1 - p_over
        p_side = "over" if lean == "OVER" else "under"
        proj_parts.append(
            f'<span class="proj-label">P({p_side})</span> '
            f'<span class="proj-val">{p_dir*100:.0f}%</span>'
        )
    proj_row = f'<div class="proj-row">{sep.join(proj_parts)}</div>'

    # H1 secondary row
    h1_row = ""
    if pred_h1 is not None:
        h1_parts = []
        if h1_lean:
            h1_parts.append(_nba_lean_badge(h1_lean))
        h1_parts.append(f'<span class="proj-label">H1</span> <span class="proj-val">{pred_h1:.1f}</span>')
        if h1_line is not None:
            h1_parts.append(f'<span class="proj-label">vs {h1_line:.1f}</span>')
        if h1_edge is not None:
            h1_sign = "+" if h1_edge > 0 else ""
            h1_ecls = "edge-pos" if h1_edge > 0 else "edge-neg"
            h1_parts.append(f'<span class="{h1_ecls}">{h1_sign}{h1_edge:.1f}</span>')
        if h1_conf:
            h1_parts.append(_nba_conf_badge(h1_conf))
        h1_row = (
            f'<div class="proj-row" style="font-size:0.82em;opacity:0.70;'
            f'border-top:1px solid #1e2535;padding-top:5px;margin-top:2px">'
            f'{sep.join(h1_parts)}</div>'
        )

    # Inline warnings
    warn_html = ""
    if gap:
        warn_html += (
            f'<div style="font-size:0.78em;color:#f59e0b;margin-top:4px">'
            f'⚠ Large model/market gap — review before acting'
            f'</div>'
        )
    if away_inj:
        names = ", ".join(away_inj[:3])
        warn_html += (
            f'<div style="font-size:0.78em;color:#fde68a;margin-top:4px">'
            f'⚠ {away}: {names} out/doubtful'
            f'</div>'
        )
    if home_inj:
        names = ", ".join(home_inj[:3])
        warn_html += (
            f'<div style="font-size:0.78em;color:#fde68a;margin-top:4px">'
            f'⚠ {home}: {names} out/doubtful'
            f'</div>'
        )

    summary_html = f'<div class="card-summary">{summary}</div>' if summary else ""

    st.html(
        f'<div class="{card_cls}">'
        f'{header}'
        f'{meta}'
        f'{playoff_context_html}'
        f'{proj_row}'
        f'{h1_row}'
        f'{warn_html}'
        f'{summary_html}'
        f'</div>'
    )


def _render_nba_tab() -> None:
    nba = load_nba_results()

    # ── header row ────────────────────────────────────────────────────────────
    col_title, col_btn = st.columns([5, 1])
    with col_title:
        if nba:
            last_run = _last_run_label(nba)
            game_date = nba.get("game_date", "")
            st.html(
                f"<h3 style='margin:0 0 4px 0'>🏀 NBA Totals</h3>"
                f"<span style='font-size:0.78em;color:#4a5568'>"
                f"Model run {last_run} · Projections for <strong>{game_date}</strong>"
                f"</span>"
            )
        else:
            st.markdown("### 🏀 NBA Totals")
    with col_btn:
        st.write("")
        if st.button("🔄 Refresh", key="nba_refresh", use_container_width=True):
            st.cache_data.clear()
            st.rerun()

    if nba is None:
        st.info(
            "No NBA projections available yet. "
            "Run `python push_nba.py` on your local machine to publish today's card."
        )
        return

    plays               = nba.get("plays", [])
    no_plays            = nba.get("no_plays", [])
    accuracy            = nba.get("season_accuracy", {})
    recent_results      = nba.get("recent_results", [])
    ot_diag_nba         = nba.get("ot_diagnostics", {})
    playoff_performance = nba.get("playoff_performance", {})
    is_playoff_day      = nba.get("is_playoff_day", False)

    # ── Playoff mode banner ────────────────────────────────────────────────────
    if is_playoff_day:
        st.html("""
        <div style="background:#1a2433;border:1px solid #3b5280;border-radius:6px;
                    padding:10px 14px;margin-bottom:12px;font-size:0.82em">
          <span style="color:#60a5fa;font-weight:700">🏆 Playoff Mode Active</span>
          <span style="color:#94a3b8;margin-left:8px">
            Series context features engage from Game 2 onward · σ = 15.5 pts (playoff) · v1_2026_04
          </span>
        </div>
        """)

    # ── season accuracy panel ─────────────────────────────────────────────────
    if accuracy and accuracy.get("total_games", 0) > 0:
        overall   = accuracy.get("overall", {})
        by_conf   = accuracy.get("by_confidence", {})
        n_total   = accuracy.get("total_games", 0)
        mae_all   = overall.get("mae")
        hr_all    = overall.get("hr")
        bias_all  = overall.get("bias")

        hr_cls = "green" if (hr_all or 0) >= 55 else "yellow" if (hr_all or 0) >= 50 else "red"

        conf_rows = ""
        for conf in ["HIGH", "MEDIUM", "LOW"]:
            d = by_conf.get(conf, {})
            if not d:
                continue
            hr_c = d.get("hr", 0)
            hr_cls_c = "green" if hr_c >= 55 else "yellow" if hr_c >= 50 else "red"
            conf_rows += (
                f'<tr>'
                f'<td>{_nba_conf_badge(conf)}</td>'
                f'<td class="dim">{d["n"]}</td>'
                f'<td>{d["mae"]:.2f}</td>'
                f'<td class="{hr_cls_c}">{d["hr"]:.1f}%</td>'
                f'<td class="dim">{d["bias"]:+.2f}</td>'
                f'</tr>'
            )

        st.html(f"""
        <div class="season-banner">
          <div style="font-size:0.72em;color:#4a5568;text-transform:uppercase;
                      letter-spacing:0.08em;margin-bottom:10px">
            Season Accuracy — {n_total} game{"s" if n_total != 1 else ""} graded
          </div>
          <div class="stat-grid">
            <div class="stat-block">
              <div class="num">{mae_all:.2f}</div>
              <div class="lbl">MAE (pts)</div>
            </div>
            <div class="stat-block">
              <div class="num {hr_cls}">{hr_all:.1f}%</div>
              <div class="lbl">Directional HR</div>
            </div>
            <div class="stat-block">
              <div class="num">{bias_all:+.2f}</div>
              <div class="lbl">Bias (pts)</div>
            </div>
          </div>
          {f'''<table class="star-table" style="margin-top:12px">
            <thead><tr>
              <th>Conf</th><th>Games</th><th>MAE</th><th>Dir HR</th><th>Bias</th>
            </tr></thead>
            <tbody>{conf_rows}</tbody>
          </table>''' if conf_rows else ""}
        </div>
        """)
    else:
        st.html("""
        <div class="season-banner">
          <div style="font-size:0.72em;color:#4a5568;text-transform:uppercase;
                      letter-spacing:0.08em;margin-bottom:6px">Season Accuracy</div>
          <div style="color:#4a5568;font-size:0.88em">
            No results graded yet — accuracy panel populates after the first morning
            results run (day after first game day).
          </div>
        </div>
        """)

    # ── OT diagnostics ────────────────────────────────────────────────────────
    if ot_diag_nba and ot_diag_nba.get("total_graded", 0) > 0:
        ot_g   = ot_diag_nba.get("ot_games", 0)
        total_g = ot_diag_nba.get("total_graded", 1)
        ot_rt  = ot_diag_nba.get("ot_rate")
        flips  = ot_diag_nba.get("ot_flips", 0)
        frate  = ot_diag_nba.get("ot_flip_rate")
        ul     = ot_diag_nba.get("under_ot_losses", 0)
        ol     = ot_diag_nba.get("over_ot_losses", 0)
        ot_rt_s  = f"{ot_rt * 100:.1f}%" if ot_rt is not None else "—"
        frate_s  = f"{frate * 100:.1f}%" if frate is not None else "—"
        st.html(f"""
        <div style="background:#0f1117;border:1px solid #1e2535;border-radius:6px;
                    padding:10px 14px;margin-bottom:10px;font-size:0.82em">
          <div style="font-size:0.72em;color:#4a5568;text-transform:uppercase;
                      letter-spacing:0.08em;margin-bottom:8px">OT Diagnostics</div>
          <div style="display:flex;gap:24px;flex-wrap:wrap;margin-bottom:6px">
            <span>OT game rate: <strong>{ot_rt_s}</strong></span>
            <span>OT flips (changed outcome): <strong>{flips}</strong> of {ot_g} OT games ({frate_s})</span>
            <span>Under losses from OT: <strong>{ul}</strong></span>
            <span>Over losses from OT: <strong>{ol}</strong></span>
          </div>
          <div style="color:#4a5568;font-size:0.78em">
            Official grading includes OT per sportsbook rules. OT diagnostics are for analysis only.
          </div>
        </div>
        """)

    # ── Playoff performance panel ─────────────────────────────────────────────
    if playoff_performance and playoff_performance.get("total_playoff_games", 0) > 0:
        po = playoff_performance
        ov = po.get("overall", {})
        w, l, p = ov.get("w", 0), ov.get("l", 0), ov.get("p", 0)
        hit_str = f"{ov['hit_rate'] * 100:.1f}%" if ov.get("hit_rate") is not None else "—"
        roi_str = f"{ov['roi']:+.1f}%" if ov.get("roi") is not None else "—"
        hit_cls = "green" if (ov.get("hit_rate") or 0) >= 0.525 else "yellow" if (ov.get("hit_rate") or 0) >= 0.50 else "red"

        round_rows = ""
        for rnd in ["First Round", "Conference Semifinals", "Conference Finals", "NBA Finals"]:
            rd = po.get("by_round", {}).get(rnd, {})
            if not rd or rd.get("n", 0) == 0:
                continue
            rd_hit = f"{rd['hit_rate'] * 100:.1f}%" if rd.get("hit_rate") is not None else "—"
            rd_roi = f"{rd['roi']:+.1f}%" if rd.get("roi") is not None else "—"
            round_rows += (
                f'<tr><td class="dim">{rnd}</td>'
                f'<td>{rd["w"]}-{rd["l"]}-{rd["p"]}</td>'
                f'<td>{rd_hit}</td><td class="dim">{rd_roi}</td></tr>'
            )

        sg_rows = ""
        for ggrp, sg in po.get("by_series_game", {}).items():
            if not sg or sg.get("n", 0) == 0:
                continue
            sg_hit = f"{sg['hit_rate'] * 100:.1f}%" if sg.get("hit_rate") is not None else "—"
            sg_rows += (
                f'<tr><td class="dim">{ggrp}</td>'
                f'<td>{sg["w"]}-{sg["l"]}-{sg["p"]}</td>'
                f'<td>{sg_hit}</td></tr>'
            )

        po_ot = po.get("ot_stats", {})
        ot_rt_s = f"{po_ot.get('ot_rate', 0) * 100:.1f}%" if po_ot.get("ot_rate") is not None else "—"

        st.html(f"""
        <div class="season-banner" style="margin-bottom:10px">
          <div style="font-size:0.72em;color:#4a5568;text-transform:uppercase;
                      letter-spacing:0.08em;margin-bottom:10px">
            🏆 Playoff Performance — {po['total_playoff_games']} games graded
          </div>
          <div class="stat-grid">
            <div class="stat-block"><div class="num">{w}-{l}-{p}</div><div class="lbl">W-L-P</div></div>
            <div class="stat-block"><div class="num {hit_cls}">{hit_str}</div><div class="lbl">Hit Rate</div></div>
            <div class="stat-block"><div class="num">{roi_str}</div><div class="lbl">ROI @ -110</div></div>
            <div class="stat-block"><div class="num">{ot_rt_s}</div><div class="lbl">OT Rate</div></div>
          </div>
          {f'''<table class="star-table" style="margin-top:10px">
            <thead><tr><th>Round</th><th>W-L-P</th><th>Hit Rate</th><th>ROI</th></tr></thead>
            <tbody>{round_rows}</tbody>
          </table>''' if round_rows else ""}
          {f'''<table class="star-table" style="margin-top:6px">
            <thead><tr><th>Series Games</th><th>W-L-P</th><th>Hit Rate</th></tr></thead>
            <tbody>{sg_rows}</tbody>
          </table>''' if sg_rows else ""}
        </div>
        """)

    # ── H1 coverage note ──────────────────────────────────────────────────────
    st.html("""
    <div style="background:#0f1117;border:1px solid #1e2535;border-radius:6px;
                padding:10px 14px;margin-bottom:14px;font-size:0.78em;color:#4a5568">
      ⚠ <strong style="color:#64748b">H1 data coverage is partial for 2025-26</strong>
      — 536 of 994 games have first-half scores available (ScoreboardV2 API limitation).
      H1 confidence ratings are provisional and treated conservatively;
      no H1 play is rated HIGH regardless of model edge.
    </div>
    """)

    # ── plays ─────────────────────────────────────────────────────────────────
    if plays:
        n = len(plays)
        st.html(f'<div class="section-hdr">🎯 Plays — {n} game{"s" if n != 1 else ""}</div>')
        for g in plays:
            _render_nba_card(g)
    else:
        st.html('<div class="section-hdr">🎯 Plays</div>')
        st.caption("No plays above threshold today.")

    # ── no-plays ──────────────────────────────────────────────────────────────
    if no_plays:
        with st.expander(
            f"No Plays — {len(no_plays)} game{'s' if len(no_plays) != 1 else ''}",
            expanded=False
        ):
            for g in no_plays:
                _render_nba_card(g)

    # ── recent results ────────────────────────────────────────────────────────
    st.html('<div class="section-hdr">📋 Recent Results — Last 14 Days</div>')
    if recent_results:
        W = sum(1 for r in recent_results if r.get("result") == "WIN")
        L = sum(1 for r in recent_results if r.get("result") == "LOSS")
        P = sum(1 for r in recent_results if r.get("result") == "PUSH")
        n = W + L + P
        hit = W / (W + L) if (W + L) > 0 else None
        roi = (W * (100.0 / 110.0) - L) / n * 100 if n > 0 else None

        hit_cls = "green" if (hit or 0) >= 0.525 else "yellow" if (hit or 0) >= 0.50 else "red"
        hit_str = f"{hit * 100:.1f}%" if hit is not None else "—"
        roi_str = f"{roi:+.1f}%" if roi is not None else "—"

        st.html(f"""
        <div class="season-banner" style="padding:10px 16px;margin-bottom:10px">
          <div class="stat-grid">
            <div class="stat-block">
              <div class="num">{W}-{L}-{P}</div>
              <div class="lbl">W-L-P (14d)</div>
            </div>
            <div class="stat-block">
              <div class="num {hit_cls}">{hit_str}</div>
              <div class="lbl">Hit Rate</div>
            </div>
            <div class="stat-block">
              <div class="num">{roi_str}</div>
              <div class="lbl">ROI @ -110</div>
            </div>
          </div>
        </div>
        """)

        rows_html = ""
        for r in recent_results:
            matchup  = f"{r.get('away_team','')} @ {r.get('home_team','')}"
            side     = r.get("signal_side", "")
            line     = r.get("line")
            edge     = r.get("edge")
            actual   = r.get("actual_total")
            result   = r.get("result", "")
            tier     = r.get("tier", "LOW")
            gd       = r.get("game_date", "")

            line_s   = str(line) if line is not None else "—"
            try:
                edge_s = f"{float(edge):+.2f}" if edge is not None else "—"
            except (TypeError, ValueError):
                edge_s = str(edge) if edge is not None else "—"
            try:
                actual_s = f"{float(actual):.0f}" if actual is not None else "—"
            except (TypeError, ValueError):
                actual_s = str(actual) if actual is not None else "—"

            rows_html += (
                f'<tr>'
                f'<td class="dim">{gd}</td>'
                f'<td>{matchup}</td>'
                f'<td>{_nhl_conf_badge(tier)} {_nhl_side_badge(side)}</td>'
                f'<td>{line_s}</td>'
                f'<td class="dim">{edge_s}</td>'
                f'<td class="dim">{actual_s}</td>'
                f'<td>{_nhl_result_badge(result)}</td>'
                f'</tr>'
            )
        st.html(f"""
        <table class="star-table">
          <thead><tr>
            <th>Date</th><th>Matchup</th><th>Signal</th>
            <th>Line</th><th>Edge</th><th>Actual</th><th>Result</th>
          </tr></thead>
          <tbody>{rows_html}</tbody>
        </table>
        """)
    else:
        st.caption("No graded results in the last 14 days.")

    # ── CLV Summary ────────────────────────────────────────────────────────────
    clv = nba.get("clv_summary", {})
    if clv:
        n_clv      = clv.get("total_with_clv", 0)
        avg_clv    = clv.get("avg_clv")
        pct_pos    = clv.get("pct_positive_clv")
        coverage   = clv.get("clv_coverage", 0.0)

        st.html('<div class="section-hdr">📈 CLV Summary (Closing Line Value)</div>')

        if n_clv < 20:
            st.caption(f"Insufficient sample for CLV conclusions (n={n_clv})")
        elif coverage < 50:
            st.caption(f"CLV coverage low — closing line capture not yet fully populated ({coverage:.0f}%)")
        else:
            avg_clv_s  = f"{avg_clv:+.2f}" if avg_clv is not None else "—"
            pct_pos_s  = f"{pct_pos:.0f}%" if pct_pos is not None else "—"
            avg_color  = "#22c55e" if (avg_clv or 0) > 0 else "#ef4444"
            pct_color  = "#22c55e" if (pct_pos or 0) > 50 else "#ef4444"
            st.html(f"""
            <div class="season-banner" style="padding:10px 16px;margin-bottom:6px">
              <div class="stat-grid">
                <div class="stat-block">
                  <div class="num" style="color:{avg_color}">{avg_clv_s}</div>
                  <div class="lbl">Avg CLV (pts)</div>
                </div>
                <div class="stat-block">
                  <div class="num" style="color:{pct_color}">{pct_pos_s}</div>
                  <div class="lbl">% Positive CLV</div>
                </div>
                <div class="stat-block">
                  <div class="num">{n_clv}</div>
                  <div class="lbl">Games w/ CLV</div>
                </div>
                <div class="stat-block">
                  <div class="num">{coverage:.0f}%</div>
                  <div class="lbl">Coverage</div>
                </div>
              </div>
            </div>
            <div style="font-size:0.73em;color:#4a5568;margin-top:4px;line-height:1.5">
              CLV measures whether decision lines beat closing lines.
              Positive = sharp. Target: &gt;0 on average.
            </div>
            """)


# ── main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    data  = load_results()
    stats = load_season_stats()
    last_run = _last_run_label(data) if data else _last_run_label(stats) if stats else "never"

    # ── page header ───────────────────────────────────────────────────────────
    col_title, col_btn = st.columns([5, 1])
    with col_title:
        st.html(
            f"<h3 style='margin:0 0 4px 0'>⚾ I Am Not Uncertain</h3>"
            f"<span style='font-size:0.78em;color:#4a5568'>"
            f"Last updated {last_run}"
            f"</span>"
        )
    with col_btn:
        st.write("")
        if st.button("🔄 Refresh", use_container_width=True):
            st.cache_data.clear()
            st.rerun()

    # ── sport tabs ────────────────────────────────────────────────────────────
    tab_mlb, tab_nba, tab_nhl, tab_soccer = st.tabs(["⚾ MLB", "🏀 NBA", "🏒 NHL", "⚽ Soccer"])

    with tab_mlb:
        # ── season stats banner ───────────────────────────────────────────────
        if stats:
            _render_season_header(stats)

        # ── alerts (lineup changes + transactions) ────────────────────────────
        if data:
            _render_alerts(data)

        # ── no data state ─────────────────────────────────────────────────────
        if data is None:
            st.info(
                "No projections available yet. "
                "Run `python push_results.py` on your local machine to publish today's card."
            )
            if stats:
                _render_analytics(stats)
        else:
            game_date = data.get("game_date", "")
            plays     = data.get("plays", [])
            no_plays  = data.get("no_plays", [])

            if game_date:
                st.caption(f"Projections for **{game_date}**")

            if plays:
                n = len(plays)
                st.html(f'<div class="section-hdr">🎯 Plays — {n} game{"s" if n != 1 else ""}</div>')
                for b in plays:
                    _render_card(b)
            else:
                st.html('<div class="section-hdr">🎯 Plays</div>')
                st.caption("No plays meeting the confidence threshold today.")

            _render_parlays(data)

            if no_plays:
                with st.expander(f"No Plays — {len(no_plays)} game{'s' if len(no_plays) != 1 else ''}"):
                    for b in no_plays:
                        _render_card(b)

            if stats:
                _render_analytics(stats)

            # ── CLV section ───────────────────────────────────────────────────
            clv = (data or {}).get("mlb_clv_summary", {})
            if clv and clv.get("clv_available"):
                with st.expander("📈 MLB Closing Line Value (CLV)", expanded=False):
                    n_clv = clv.get("total_with_clv", 0)
                    cov   = clv.get("clv_coverage_pct", 0.0)
                    if clv.get("coverage_warning"):
                        st.warning(f"CLV coverage low ({cov:.0f}%) — data may be incomplete.")
                    c1, c2, c3, c4 = st.columns(4)
                    avg = clv.get("avg_clv")
                    med = clv.get("median_clv")
                    pct = clv.get("pct_positive_clv")
                    c1.metric("Avg CLV", f"{avg:+.3f}" if avg is not None else "—")
                    c2.metric("Median CLV", f"{med:+.3f}" if med is not None else "—")
                    c3.metric("% Positive CLV", f"{pct:.1f}%" if pct is not None else "—")
                    c4.metric("Games w/ CLV", f"{n_clv} ({cov:.0f}% cov)")
                    by_tier = clv.get("avg_clv_by_tier", {})
                    if any(v is not None for v in by_tier.values()):
                        st.caption("Avg CLV by confidence tier")
                        tc = st.columns(3)
                        for i, t in enumerate(("HIGH", "MEDIUM", "LOW")):
                            v = by_tier.get(t)
                            tc[i].metric(t, f"{v:+.3f}" if v is not None else "—")
                    st.caption(
                        "CLV measures whether decision lines beat closing lines. "
                        "Positive = sharp (line moved in model's favor)."
                    )
            elif clv and not clv.get("clv_available"):
                reason = clv.get("reason", "")
                if "insufficient" in reason:
                    st.caption(f"CLV: insufficient sample ({clv.get('total_with_clv', 0)} games). "
                               "Builds up once refresh.py has captured closing lines.")

    with tab_nba:
        _render_nba_tab()

    with tab_nhl:
        _render_nhl_tab()

    with tab_soccer:
        _render_soccer_tab()


main()
