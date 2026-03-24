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
GOLF_RESULTS_FILE   = os.path.join(os.path.dirname(os.path.abspath(__file__)), "golf_results.json")

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


def load_golf_results() -> dict | None:
    if not os.path.exists(GOLF_RESULTS_FILE):
        return None
    with open(GOLF_RESULTS_FILE) as f:
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


def _render_review_tab(sport: str, review_data: dict | None) -> None:
    """Render the AI-generated results review sub-tab."""
    if review_data is None:
        st.caption("No results review available yet — runs daily after grading.")
        return

    daily = review_data.get("daily_review") or {}
    weekly = review_data.get("weekly_review") or {}

    # Daily review
    if daily:
        status = daily.get("generation_status", "")
        date_rev = daily.get("date_reviewed", "")
        rec = daily.get("record_summary", {})
        overall = rec.get("overall", {})

        if date_rev:
            st.caption(f"Results for **{date_rev}**")

        if overall:
            w, l, p = overall.get("w", 0), overall.get("l", 0), overall.get("p", 0)
            n = w + l + p
            if n > 0:
                roi = round((w * (100.0 / 110.0) - l) / n * 100, 1)
                st.html(
                    f"<span style='font-size:1.1em;font-weight:700'>"
                    f"{w}–{l}–{p} &nbsp; "
                    f"<span style='color:{'#4ade80' if roi >= 0 else '#f87171'}'>"
                    f"{roi:+.1f}% ROI</span></span>"
                )

        if status == "success" and daily.get("narrative"):
            st.markdown(daily["narrative"])
        elif status == "no_games":
            st.caption("No graded plays for this date.")
        elif status in ("no_api_key", "client_init_failed"):
            st.caption("AI review unavailable — API key not configured.")
        elif status == "failed":
            st.caption("Review generation failed — check logs.")
        else:
            st.caption("No review available yet.")
    else:
        st.caption("No daily review available yet.")

    # Weekly review (Sundays only)
    if weekly and weekly.get("generation_status") == "success":
        ws = weekly.get("week_start", "")
        we = weekly.get("week_end", "")
        st.divider()
        st.markdown(f"**Weekly Review ({ws} – {we})**")
        rec_w = weekly.get("record_summary", {}).get("overall", {})
        if rec_w:
            ww, wl, wp = rec_w.get("w", 0), rec_w.get("l", 0), rec_w.get("p", 0)
            nw = ww + wl + wp
            if nw > 0:
                roi_w = round((ww * (100.0 / 110.0) - wl) / nw * 100, 1)
                st.html(
                    f"<span style='font-size:0.95em;font-weight:600'>"
                    f"{ww}–{wl}–{wp} &nbsp;"
                    f"<span style='color:{'#4ade80' if roi_w >= 0 else '#f87171'}'>"
                    f"{roi_w:+.1f}% ROI</span></span>"
                )
        st.markdown(weekly["narrative"])


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

    picks_tab, review_tab = st.tabs(["Today's Picks", "Results Review"])

    with picks_tab:
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

    with review_tab:
        _render_review_tab("nhl", {"daily_review": nhl.get("daily_review"), "weekly_review": nhl.get("weekly_review")})


# ── Soccer tab rendering ───────────────────────────────────────────────────────

_SOCCER_LEAGUE_DISPLAY = {
    "EPL": "\U0001F3F4\U000E0067\U000E0062\U000E0065\U000E006E\U000E0067\U000E007F EPL",
    "BUN": "\U0001F1E9\U0001F1EA Bundesliga",
    "LGA": "\U0001F1EA\U0001F1F8 La Liga",
    "SEA": "\U0001F1EE\U0001F1F9 Serie A",
    "LG1": "\U0001F1EB\U0001F1F7 Ligue 1",
}


def _soccer_league_label(league_id: str) -> str:
    return _SOCCER_LEAGUE_DISPLAY.get(league_id, league_id)


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
        f'{_soccer_league_label(league)}'
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


def _parlay_candidate_card_html(c: dict) -> str:
    """Build HTML for a single Over 1.5 candidate card."""
    home     = c.get("home_team", "")
    away     = c.get("away_team", "")
    league   = c.get("league", "")
    tier     = c.get("confidence_tier", "HIGH")
    proj     = c.get("projected_total")
    p_over   = c.get("model_p_over_1_5")
    mkt_p    = c.get("market_implied_p_1_5")
    mkt_line = c.get("market_line_1_5")
    lineup   = bool(c.get("lineup_confirmed", False))
    gt       = c.get("game_time_et", "")

    league_tag = (
        '<span style="font-size:0.72em;color:#4a5568;margin-right:6px">'
        f'{_soccer_league_label(league)}'
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
    proj_s = f"{proj:.1f}" if proj is not None else "—"
    p_s    = f"{p_over * 100:.1f}%" if p_over is not None else "—"
    stats_parts = [
        f'<span class="proj-label">Projected Goals</span> <span class="proj-val">{proj_s}</span>',
        f'<span class="proj-label">P(Over 1.5)</span> <span class="proj-val" style="color:#a5b4fc">{p_s}</span>',
    ]
    if mkt_line is not None and mkt_p is not None:
        stats_parts.append(
            f'<span class="proj-label">Market 1.5</span>'
            f' <span class="proj-val">{mkt_p * 100:.1f}%</span>'
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
    return (
        f'<div class="game-card" style="border-color:#334155">'
        f'{header}{stats_row}{lineup_html}'
        f'</div>'
    )


def _render_soccer_parlay_candidates(parlay_candidates: list,
                                     suggested_parlay: dict) -> None:
    """
    Render Over 1.5 parlay section: suggested parlay + additional candidates.
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

    # ── Suggested parlay block ────────────────────────────────────────────────
    sp = suggested_parlay or {}
    leg_count   = sp.get("leg_count", 0)
    combined_p  = sp.get("combined_prob")
    corr_note   = sp.get("correlation_note", False)
    legs        = sp.get("legs", [])

    if leg_count == 0:
        # No candidates at all
        st.caption(
            "No parlay candidates today — check back on the next match day."
        )
        return

    if leg_count == 1:
        header_label = "1 Parlay Candidate Today (insufficient for multi-leg)"
    elif leg_count == 2:
        header_label = f"Suggested 2-Leg Parlay (only {len(parlay_candidates)} candidates today)"
    else:
        header_label = "🎯 Suggested 3-Leg Parlay"

    # Build leg rows HTML
    sep = ' <span style="color:#2d3748;margin:0 2px">·</span> '
    legs_html = ""
    for i, leg in enumerate(legs):
        lg       = leg.get("league", "")
        home     = leg.get("home_team", "")
        away     = leg.get("away_team", "")
        gt       = leg.get("game_time_et", "")
        proj     = leg.get("projected_total")
        p_over   = leg.get("model_p_over_1_5")
        tier     = leg.get("confidence_tier", "HIGH")
        edge_1_5 = leg.get("edge_1_5")

        league_ico = _soccer_league_label(lg).split(" ")[0]
        tier_color = "#22c55e" if tier == "VERY HIGH" else "#f59e0b"
        tier_badge = (
            f'<span style="background:#1a1a2e;color:{tier_color};'
            f'border:1px solid {tier_color};border-radius:3px;padding:0 5px;'
            f'font-size:0.70em;font-weight:700;margin-left:5px">{tier}</span>'
        )

        p_s    = f"{p_over * 100:.1f}%" if p_over is not None else "—"
        proj_s = f"{proj:.1f}" if proj is not None else "—"

        parts = [
            f'<span style="color:#e2e8f0;font-weight:600">{away} @ {home}</span>',
            f'<span style="color:#94a3b8">P(1.5): <strong style="color:#a5b4fc">{p_s}</strong></span>',
            f'<span style="color:#94a3b8">Proj: {proj_s} goals</span>',
        ]
        if gt:
            parts.append(f'<span style="color:#64748b">{gt} ET</span>')

        legs_html += (
            f'<div style="padding:6px 0;border-bottom:1px solid #1e293b;'
            f'font-size:0.83em">'
            f'{league_ico} {sep.join(parts)}{tier_badge}'
            f'</div>'
        )

    # Combined probability row
    comb_s = f"{combined_p * 100:.1f}%" if combined_p is not None else "—"
    corr_html = (
        '<div style="font-size:0.76em;color:#f59e0b;margin-top:6px">'
        '⚠️ Multiple legs from same league — may be correlated'
        '</div>'
        if corr_note else ""
    )
    footer_html = (
        f'<div style="margin-top:8px;font-size:0.82em;color:#94a3b8">'
        f'Estimated combined probability: '
        f'<strong style="color:#e2e8f0">{comb_s}</strong>'
        f'</div>'
        f'<div style="font-size:0.72em;color:#4a5568;margin-top:3px">'
        f'Assumes independence — actual probability may be lower if legs are correlated.'
        f'</div>'
        f'{corr_html}'
    )

    st.html(
        f'<div class="game-card" style="border-color:#4338ca;background:#0f0f2e">'
        f'<div class="card-header" style="margin-bottom:4px">'
        f'<span style="font-weight:700;color:#c7d2fe;font-size:0.95em">{header_label}</span>'
        f'<span style="font-size:0.72em;color:#64748b;margin-left:8px">'
        f'High-confidence goal environments — parlay use only</span>'
        f'</div>'
        f'{legs_html}'
        f'{footer_html}'
        f'</div>'
    )

    # ── Additional candidates list (capped at 6, sorted P DESC) ──────────────
    if parlay_candidates:
        st.html(
            '<div style="font-size:0.78em;font-weight:600;color:#64748b;'
            'margin:14px 0 6px 0;text-transform:uppercase;letter-spacing:0.05em">'
            'All Candidates Today</div>'
        )
        for c in parlay_candidates[:6]:
            st.html(_parlay_candidate_card_html(c))


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

    picks_tab, review_tab = st.tabs(["Today's Picks", "Results Review"])

    with picks_tab:
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
        _render_soccer_parlay_candidates(
            soccer.get("parlay_candidates", []),
            soccer.get("suggested_parlay", {}),
        )

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
                for lg in sorted(by_league.keys()):
                    name = _soccer_league_label(lg)
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

        # ── League Deployment Status ──────────────────────────────────────────────
        league_deploy = soccer.get("league_deployment", {})
        if league_deploy:
            st.html(
                "<div style='font-size:0.82em;font-weight:600;color:#94a3b8;"
                "margin-top:16px;margin-bottom:6px'>League Status</div>"
            )
            status_lines = []
            for lid, info in sorted(league_deploy.items()):
                s = info.get("status", "")
                name = info.get("display_name", lid)
                if s == "active":
                    status_lines.append(f"<span style='color:#4ade80'>&#10003;</span> Active — {name}")
                elif "oos_gate" in s:
                    status_lines.append(f"<span style='color:#fbbf24'>&#9888;</span> Excluded (OOS gate) — {name}")
                elif "coverage" in s:
                    status_lines.append(f"<span style='color:#f87171'>&#10007;</span> Excluded (coverage) — {name}")
                else:
                    status_lines.append(f"<span style='color:#94a3b8'>&#8226;</span> {s} — {name}")
            st.html("<div style='font-size:0.78em;line-height:1.8'>" + "<br>".join(status_lines) + "</div>")

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

    with review_tab:
        _render_review_tab("soccer", {"daily_review": soccer.get("daily_review"), "weekly_review": soccer.get("weekly_review")})


def _nba_tier_badge(tier: str) -> str:
    """Render tier badge for NBA signal system."""
    styles = {
        "TIER_1A": ("background:#451a03;color:#fbbf24;border:1px solid #d97706", "CORE · 1.5u"),
        "TIER_1B": ("background:#451a03;color:#fbbf24;border:1px solid #d97706", "TIER 1B · 1.5u"),
        "TIER_2": ("background:#431407;color:#fb923c;border:1px solid #ea580c", "TIER 2 · 1.0u"),
        "CONTEXT": ("background:#1f2937;color:#9ca3af;border:1px solid #4b5563", "CONTEXT · 0u"),
        "PASS": ("background:#451a03;color:#fbbf24;border:1px solid #d97706", "CONFLICT"),
        # Playoff signal boards
        "P1": ("background:#1a2433;color:#60a5fa;border:1px solid #3b82f6", "🏆 P1 · 1.0u"),
        "P2": ("background:#422006;color:#fbbf24;border:1px solid #d97706", "🏆 P2 · 0.75u"),
        "P4": ("background:#422006;color:#fbbf24;border:1px solid #d97706", "🏆 P4 · 0.75u"),
        # Referee standalone
        "REF_UNDER": ("background:#1a2433;color:#60a5fa;border:1px solid #3b82f6", "📋 REF UNDER · 0.75u"),
    }
    style, label = styles.get(tier, ("background:#1f2937;color:#6b7280", tier or "—"))
    return f'<span style="padding:2px 8px;border-radius:4px;font-size:0.75em;font-weight:600;{style}">{label}</span>'


def _nba_conf_badge(conf: str) -> str:
    """Legacy conf badge — still used by other code paths."""
    c = (conf or "LOW").upper()
    return f'<span class="conf-badge conf-{c}">{c.lower()}</span>'


def _render_nba_card(g: dict) -> None:
    """Render a single NBA game card."""
    home    = g.get("home_team", "")
    away    = g.get("away_team", "")
    conf    = g.get("confidence", "LOW")
    bet_tier = g.get("bet_tier")
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

    # Use tier system instead of HIGH/MEDIUM/LOW
    is_play = bet_tier in ("TIER_1A", "TIER_1B", "TIER_2", "P1", "P2", "P4", "REF_UNDER")
    conf_star = {"TIER_1A": "star3", "TIER_1B": "star3", "TIER_2": "star2",
                 "P1": "star3", "P2": "star2", "P4": "star2",
                 "REF_UNDER": "star2"}.get(bet_tier, "noplay")
    card_cls  = f"game-card {conf_star}" if is_play else "game-card noplay"

    matchup   = f"{away} @ {home}"

    # Determine lean from signal direction, not base model
    # Playoff boards take priority
    signal_dir = g.get("playoff_board_direction") or g.get("venue_direction") or g.get("shot_direction") or lean
    lean_html = _nba_lean_badge(signal_dir) if signal_dir and signal_dir not in ("—", "", "CONFLICT") else ""

    header = (
        f'<div class="card-header">'
        f'{_nba_tier_badge(bet_tier) if bet_tier else ""}'
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

    # Projection row — show signal tier info instead of base model predictions
    sep = ' <span style="color:#2d3748;margin:0 2px">·</span> '
    proj_parts = []
    bet_tier = g.get("bet_tier")

    if bet_tier in ("P1", "P2", "P4"):
        # Playoff board play
        po_labels = {
            "P1": ("R1 Early UNDER · 1.0u", "#60a5fa"),
            "P2": ("R1 Late OVER · 0.75u", "#fbbf24"),
            "P4": ("CF Early OVER · 0.75u", "#fbbf24"),
        }
        po_label, po_color = po_labels.get(bet_tier, (bet_tier, "#a3a3a3"))
        po_sizing = g.get("playoff_board_sizing", 0)
        if g.get("finals_modifier") and po_sizing != po_labels.get(bet_tier, (None, None))[0]:
            po_label = f"{po_label} (Finals −0.25u)"
        proj_parts.append(f'<span style="color:{po_color};font-weight:600">🏆 {po_label}</span>')
        if line is not None:
            proj_parts.append(f'<span class="proj-label">Line</span> <span class="proj-val">{line:.1f}</span>')
        sgn = g.get("series_game_number")
        if sgn:
            proj_parts.append(f'<span class="proj-label">Game</span> <span class="proj-val">{sgn}</span>')
    elif bet_tier in ("TIER_1A", "TIER_1B", "TIER_2"):
        # Signal-driven play — show tier, direction, and line
        tier_labels = {"TIER_1A": "CORE · 1.5u", "TIER_1B": "Tier 1B · 1.5u", "TIER_2": "Tier 2 · 1.0u"}
        tier_colors = {"TIER_1A": "#fbbf24", "TIER_1B": "#fbbf24", "TIER_2": "#fb923c"}
        tl = tier_labels.get(bet_tier, bet_tier)
        tc = tier_colors.get(bet_tier, "#a3a3a3")
        proj_parts.append(f'<span style="color:{tc};font-weight:600">{tl}</span>')
        if line is not None:
            proj_parts.append(f'<span class="proj-label">Line</span> <span class="proj-val">{line:.1f}</span>')
        # Show which signals fire
        signals = []
        if g.get("venue_direction"): signals.append("Venue")
        if g.get("shot_direction") and g.get("shot_direction") not in ("CONFLICT",): signals.append("Shot")
        if g.get("oreb_confirms"): signals.append("OREB")
        if g.get("archetype_direction"): signals.append("Pace")
        if signals:
            proj_parts.append(f'<span class="proj-label">Signals</span> <span class="proj-val">{" + ".join(signals)}</span>')
    else:
        # Non-play — show line only for reference, no model predictions
        if line is not None:
            proj_parts.append(f'<span class="proj-label">Line</span> <span class="proj-val">{line:.1f}</span>')
        else:
            proj_parts.append('<span class="proj-label">No line yet</span>')

    proj_row = f'<div class="proj-row">{sep.join(proj_parts)}</div>'

    # H1 row suppressed — base model H1 predictions not deployed
    h1_row = ""

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

    # Archetype signal badge
    arch_html = ""
    if g.get("archetype_signal"):
        arch_note = g.get("archetype_note", "")
        arch_total = g.get("archetype_best_total")
        arch_total_str = f" (best UNDER: {arch_total})" if arch_total else ""
        arch_html = (
            f'<div style="font-size:0.82em;color:#c084fc;margin-top:4px;'
            f'padding:4px 8px;background:#1a0a2e;border-radius:4px;border:1px solid #7c3aed">'
            f'⚡ ARCHETYPE: {arch_note}{arch_total_str}'
            f'</div>'
        )

    # Shot profile signal badge
    shot_html = ""
    if g.get("shot_signal"):
        shot_dir = g.get("shot_direction", "")
        shot_note = g.get("shot_note", "")
        sig_class = g.get("signal_class", "")
        if sig_class == "DOUBLE_SIGNAL":
            badge_bg = "#064e3b"; badge_border = "#059669"; badge_label = "DOUBLE SIGNAL"
        elif sig_class == "CONFLICT":
            badge_bg = "#451a03"; badge_border = "#d97706"; badge_label = "CONFLICT — PASS"
        else:
            badge_bg = "#1e1b4b"; badge_border = "#6366f1"; badge_label = "SHOT PROFILE"
        shot_html = (
            f'<div style="font-size:0.82em;color:#a5b4fc;margin-top:4px;'
            f'padding:4px 8px;background:{badge_bg};border-radius:4px;border:1px solid {badge_border}">'
            f'🎯 {badge_label}: {shot_dir} — {g.get("shot_signal","")} ({shot_note})'
            f'</div>'
        )

    # Venue signal badge
    venue_html = ""
    if g.get("venue_signal"):
        venue_note = g.get("venue_note", "")
        venue_html = (
            f'<div style="font-size:0.82em;color:#fb923c;margin-top:4px;'
            f'padding:4px 8px;background:#431407;border-radius:4px;border:1px solid #ea580c">'
            f'🏟️ VENUE: OVER — {venue_note}'
            f'</div>'
        )

    # Playoff signal board badge
    playoff_board_html = ""
    po_board = g.get("playoff_board")
    if po_board:
        po_dir = g.get("playoff_board_direction", "")
        po_sizing = g.get("playoff_board_sizing", 0)
        po_note = g.get("playoff_board_note", "")
        po_color = "#60a5fa" if po_dir == "UNDER" else "#fbbf24"
        po_bg = "#1a2433" if po_dir == "UNDER" else "#422006"
        po_border = "#3b82f6" if po_dir == "UNDER" else "#d97706"
        playoff_board_html = (
            f'<div style="font-size:0.82em;color:{po_color};margin-top:4px;'
            f'padding:6px 10px;background:{po_bg};border-radius:4px;border:1px solid {po_border}">'
            f'🏆 <strong>PLAYOFF {po_board}: {po_dir} {po_sizing}u</strong>'
            f'<div style="font-size:0.90em;color:#94a3b8;margin-top:2px">{po_note}</div>'
            f'</div>'
        )
    elif g.get("finals_modifier"):
        playoff_board_html = (
            f'<div style="font-size:0.82em;color:#60a5fa;margin-top:4px;'
            f'padding:4px 8px;background:#1a2433;border-radius:4px;border:1px solid #3b82f6">'
            f'🏆 Finals UNDER modifier — reduce any OVER by 0.25u'
            f'</div>'
        )

    # Referee signal badge
    ref_html = ""
    ref_sig = g.get("ref_signal", "UNKNOWN")
    if ref_sig == "REF_OVER":
        adj = g.get("ref_sizing_adj", 0)
        ref_html = (
            f'<div style="font-size:0.82em;color:#4ade80;margin-top:4px;'
            f'padding:4px 8px;background:#052e16;border-radius:4px;border:1px solid #16a34a">'
            f'📋 REF_OVER — {int(g.get("crew_high_count",0))} high-scoring refs'
            f'{f" (+{adj:.1f}u)" if adj > 0 else ""}'
            f'</div>'
        )
    elif ref_sig == "REF_UNDER" and bet_tier != "REF_UNDER":
        ref_html = (
            f'<div style="font-size:0.82em;color:#93c5fd;margin-top:4px;'
            f'padding:4px 8px;background:#1a2433;border-radius:4px;border:1px solid #3b82f6">'
            f'📋 REF_UNDER — 0 high-scoring refs (UNDER lean)'
            f'</div>'
        )
    elif ref_sig == "CONFLICT":
        ref_html = (
            f'<div style="font-size:0.82em;color:#fbbf24;margin-top:4px;'
            f'padding:4px 8px;background:#451a03;border-radius:4px;border:1px solid #d97706">'
            f'📋 REF CONFLICT — ref signal opposes existing direction'
            f'</div>'
        )
    elif ref_sig != "UNKNOWN" and ref_sig != "NONE":
        pass  # NONE = no badge
    # UNKNOWN = pending (show if refs not yet available)
    elif ref_sig == "UNKNOWN" and is_play:
        ref_html = (
            f'<div style="font-size:0.75em;color:#6b7280;margin-top:2px;font-style:italic">'
            f'REF: pending (run ref_scrape.py after 6:30pm)'
            f'</div>'
        )

    # Paused RS signals in playoffs
    paused_html = ""
    if g.get("playoff_venue_paused"):
        paused_html += (
            f'<div style="font-size:0.75em;color:#6b7280;margin-top:2px;font-style:italic">'
            f'Venue OVER PAUSED in playoffs (reverses to UNDER historically)'
            f'</div>'
        )
    if g.get("playoff_shot_under_paused"):
        paused_html += (
            f'<div style="font-size:0.75em;color:#6b7280;margin-top:2px;font-style:italic">'
            f'Shot UNDER PAUSED in playoffs (reverses historically)'
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
        f'{arch_html}'
        f'{shot_html}'
        f'{venue_html}'
        f'{playoff_board_html}'
        f'{ref_html}'
        f'{paused_html}'
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

    picks_tab, review_tab = st.tabs(["Today's Picks", "Results Review"])

    with picks_tab:
        plays               = nba.get("plays", [])
        no_plays            = nba.get("no_plays", [])
        accuracy            = nba.get("season_accuracy", {})
        recent_results      = nba.get("recent_results", [])
        ot_diag_nba         = nba.get("ot_diagnostics", {})
        playoff_performance = nba.get("playoff_performance", {})
        is_playoff_day      = nba.get("is_playoff_day", False)

        # ── Segment overlay status ────────────────────────────────────────────────
        try:
            _nba_ovl_path = os.path.join(os.path.dirname(__file__), "nba", "config_segment_overlay.json")
            if os.path.exists(_nba_ovl_path):
                with open(_nba_ovl_path) as _f:
                    _nba_ovl = json.load(_f)
                if _nba_ovl.get("overlay_active"):
                    st.html('<div style="font-size:0.78em;color:#4ade80;margin-bottom:6px">🎯 Segment overlay active (fast pace OVER boost)</div>')

                    # Phase 6 shadow status
                    _p6_rs = os.path.join(os.path.dirname(__file__), "nba", "data", "nba_phase6_rs_shadow.parquet")
                    _p6_po = os.path.join(os.path.dirname(__file__), "nba", "data", "nba_phase6_po_shadow.parquet")
                    _p6_parts = []
                    for _p6p, _p6l in [(_p6_rs, "RS"), (_p6_po, "PO")]:
                        if os.path.exists(_p6p):
                            _p6d = pd.read_parquet(_p6p)
                            _p6g = _p6d[_p6d["result"].isin(["WIN", "LOSS"])]
                            if len(_p6g) > 0:
                                _w6 = (_p6g["result"] == "WIN").sum()
                                _n6 = len(_p6g)
                                _r6 = (_w6 * (100/110) - (_n6-_w6)) / _n6 * 100
                                _p6_parts.append(f"{_p6l}: {_n6} bets, {_w6/_n6*100:.0f}% hit, {_r6:+.0f}% ROI")
                    if _p6_parts:
                        st.html(f'<div style="font-size:0.72em;color:#94a3b8;margin-bottom:6px">📊 Small-edge shadow: {" | ".join(_p6_parts)}</div>')

                # High-line UNDER shadow tracking
                _hl_path = os.path.join(os.path.dirname(__file__), "nba", "data", "high_line_under_shadow.csv")
                if os.path.exists(_hl_path):
                    _hld = pd.read_csv(_hl_path, dtype=str)
                    # Today's tagged games
                    _today_str = _nba.get("game_date", "")
                    _hl_today = _hld[_hld["game_date"] == _today_str]
                    for _, _hlr in _hl_today.iterrows():
                        st.html(f'<div style="font-size:0.72em;color:#a78bfa;margin-bottom:3px">'
                                f'📊 SHADOW: {_hlr["away_team"]} @ {_hlr["home_team"]} — '
                                f'line {_hlr["closing_line"]} — tracking UNDER</div>')
                    # Season summary
                    _hl_graded = _hld[_hld["result"].isin(["CORRECT", "INCORRECT", "PUSH"])]
                    if len(_hl_graded) > 0:
                        _hl_n = len(_hl_graded)
                        _hl_w = (_hl_graded["result"] == "CORRECT").sum()
                        _hl_l = (_hl_graded["result"] == "INCORRECT").sum()
                        _hl_hr = _hl_w / (_hl_w + _hl_l) * 100 if (_hl_w + _hl_l) > 0 else 0
                        _hl_me = _hl_graded["market_error"].astype(float).mean()
                        st.html(f'<div style="font-size:0.72em;color:#94a3b8;margin-bottom:6px">'
                                f'📊 High Line Shadow: N={_hl_n} | HR={_hl_hr:.0f}% | ME={_hl_me:+.1f} (2025-26 tracking)</div>')
        except Exception:
            pass

        # ── Playoff mode banner ────────────────────────────────────────────────────
        if is_playoff_day:
            st.html("""
            <div style="background:#1a2433;border:1px solid #3b5280;border-radius:6px;
                        padding:10px 14px;margin-bottom:12px;font-size:0.82em">
              <span style="color:#60a5fa;font-weight:700">🏆 Playoff Mode Active</span>
              <span style="color:#94a3b8;margin-left:8px">
                Series context features engage from Game 2 onward · σ = 15.5 pts (playoff) · v1_2026_04
              </span>
              <div style="margin-top:6px;font-size:0.92em;color:#cbd5e1">
                <strong>Active Playoff Boards:</strong>
                <span style="color:#60a5fa">P1 R1 G1-2 UNDER 1.0u</span> ·
                <span style="color:#fbbf24">P2 R1 G5-7 OVER 0.75u</span> ·
                <span style="color:#fbbf24">P4 CF G1-4 OVER 0.75u</span>
                <span style="color:#6b7280;margin-left:6px">| Venue OVER + Shot UNDER paused</span>
              </div>
            </div>
            """)

        # ── NBA stop rule suspension banner ───────────────────────────────────────
        _nba_stop = (nba or {}).get("stop_rule_status", {})
        _nba_model_susp  = _nba_stop.get("model_suspended", False)
        _nba_tier_susps  = _nba_stop.get("suspended_tiers", [])
        _nba_full_detail = _nba_stop.get("full_model_details", {})
        _nba_tier_detail = _nba_stop.get("tier_details", {})

        if _nba_model_susp:
            _fn = _nba_full_detail.get("n", "?")
            _fr = _nba_full_detail.get("roi")
            _fr_str = f"{_fr:.1f}%" if _fr is not None else "?"
            st.html(f"""
            <div style="background:#2d1515;border:2px solid #dc2626;border-radius:8px;
                        padding:12px 16px;margin-bottom:14px">
              <span style="color:#f87171;font-weight:700;font-size:1.05em">
                🚨 NBA MODEL FULLY SUSPENDED
              </span>
              <span style="color:#fca5a5;margin-left:10px;font-size:0.88em">
                Full-model ROI hit {_fr_str} on {_fn} live plays (threshold: −12%).
                All signals are paused.
              </span>
              <div style="color:#fca5a5;font-size:0.80em;margin-top:6px">
                Manual reset required:
                <code>python nba_reset_stop_rules.py --reason "..."</code>
              </div>
            </div>
            """)
        elif _nba_tier_susps:
            for _t in _nba_tier_susps:
                _td = _nba_tier_detail.get(_t, {})
                _tn = _td.get("n", "?")
                _tr = _td.get("roi")
                _tr_str = f"{_tr:.1f}%" if _tr is not None else "?"
                st.html(f"""
                <div style="background:#2d1b0e;border:2px solid #d97706;border-radius:8px;
                            padding:12px 16px;margin-bottom:8px">
                  <span style="color:#fbbf24;font-weight:700;font-size:1.05em">
                    ⛔ NBA {_t} tier suspended
                  </span>
                  <span style="color:#fde68a;margin-left:10px;font-size:0.88em">
                    {_t}-confidence tier ROI hit {_tr_str} on {_tn} live plays
                    (threshold: −10%). {_t} signals paused. Other tiers continue.
                  </span>
                  <div style="color:#fde68a;font-size:0.80em;margin-top:6px">
                    Manual reset required:
                    <code>python nba_reset_stop_rules.py --reason "..."</code>
                  </div>
                </div>
                """)

        # ── Signal System Tracking Panel ──────────────────────────────────────────
        sig_track = nba.get("signal_tracking", {})
        n_plays = sig_track.get("total_plays", 0)

        if n_plays > 0:
            by_tier = sig_track.get("by_tier", {})
            overall_hit = sig_track.get("overall_hit_pct", 0)
            overall_pnl = sig_track.get("overall_units_pnl", 0)
            pnl_cls = "green" if overall_pnl > 0 else "red"

            tier_rows = ""
            for tier, label, hist_roi in [("TIER1","Tier 1 (Venue+OREB)","+19.3%"),
                                           ("TIER2","Tier 2 (Venue)","+13.5%"),
                                           ("TIER3","Tier 3 (Shot+Venue)","+9.4%")]:
                d = by_tier.get(tier, {})
                if not d: continue
                hr_c = d.get("hit_pct", 0)
                hr_cls = "green" if hr_c >= 55 else "yellow" if hr_c >= 50 else "red"
                pnl_c = d.get("units_pnl", 0)
                tier_rows += (
                    f'<tr><td>{label}</td><td>{d["n"]}</td>'
                    f'<td class="{hr_cls}">{hr_c:.1f}%</td>'
                    f'<td class="{"green" if pnl_c>0 else "red"}">{pnl_c:+.1f}u</td>'
                    f'<td class="dim">{hist_roi}</td></tr>'
                )

            st.html(f"""
            <div class="season-banner">
              <div style="font-size:0.72em;color:#4a5568;text-transform:uppercase;
                          letter-spacing:0.08em;margin-bottom:10px">
                Signal System — {n_plays} play{"s" if n_plays != 1 else ""} tracked
              </div>
              <div class="stat-grid">
                <div class="stat-block">
                  <div class="num {"green" if overall_hit>=55 else "yellow" if overall_hit>=50 else "red"}">{overall_hit:.1f}%</div>
                  <div class="lbl">Hit Rate</div>
                </div>
                <div class="stat-block">
                  <div class="num {pnl_cls}">{overall_pnl:+.1f}u</div>
                  <div class="lbl">Units P&L</div>
                </div>
              </div>
              {f"""<table class="star-table" style="margin-top:12px">
                <thead><tr>
                  <th>Tier</th><th>Plays</th><th>Hit%</th><th>P&L</th><th>Hist ROI</th>
                </tr></thead>
                <tbody>{tier_rows}</tbody>
              </table>""" if tier_rows else ""}
            </div>
            """)
        else:
            st.html("""
            <div class="season-banner">
              <div style="font-size:0.72em;color:#4a5568;text-transform:uppercase;
                          letter-spacing:0.08em;margin-bottom:6px">Signal System Tracking</div>
              <div style="color:#4a5568;font-size:0.88em">
                Live since March 22, 2026. No graded plays yet.<br>
                Historical backtested ROI: Tier 1 +19.3%, Tier 2 +13.5%, Tier 3 +9.4%
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

        # ── Matchup Signal Boards (synergy-tested deployment tiers) ────────────
        all_games = plays + no_plays
        tier1a = [g for g in all_games if g.get("bet_tier") == "TIER_1A"]
        tier1b = [g for g in all_games if g.get("bet_tier") == "TIER_1B"]
        tier2 = [g for g in all_games if g.get("bet_tier") == "TIER_2"]
        context = [g for g in all_games if g.get("bet_tier") == "CONTEXT"]
        conflicts = [g for g in all_games if g.get("bet_tier") == "PASS"]
        has_signals = tier1a or tier1b or tier2 or context or conflicts

        if has_signals:
            st.html('<div class="section-hdr" style="margin-top:16px">Matchup Signal Board</div>')

            def _render_signal_row(g, tier_color, tier_label):
                matchup = "%s @ %s" % (g.get("away_team",""), g.get("home_team",""))
                line = g.get("line")
                line_str = " · Total: %.1f" % line if line else ""
                oreb_tag = " · OREB confirms" if g.get("oreb_confirms") else ""
                signals = []
                if g.get("venue_direction"): signals.append("venue")
                if g.get("shot_direction") and g.get("shot_direction") not in ("CONFLICT",): signals.append("shot")
                if g.get("archetype_direction"): signals.append("pace")
                sig_str = " + ".join(signals) if signals else ""
                return (
                    f'<div style="padding:5px 8px;margin:2px 0;background:{tier_color};'
                    f'border-radius:4px;font-size:0.82em">'
                    f'<strong>{tier_label}</strong> {matchup} — OVER{line_str}'
                    f' · {sig_str}{oreb_tag}</div>')

            if tier1a:
                st.html('<div style="font-size:0.85em;color:#fbbf24;padding:4px 0;font-weight:600">'
                        'CORE — BET OVER (1.5 units) · DAL/UTA/PHI @ IND/OKC/SAS (77.5% hit, N=40)</div>')
                for g in tier1a:
                    st.html(_render_signal_row(g, "#451a03;border:1px solid #d97706;color:#fef3c7", "CORE"))

            if tier1b:
                st.html('<div style="font-size:0.85em;color:#fbbf24;padding:4px 0;font-weight:600;margin-top:6px">'
                        'TIER 1B — BET OVER (1.5 units) · Pruned Venue + OREB confirmation</div>')
                for g in tier1b:
                    st.html(_render_signal_row(g, "#451a03;border:1px solid #d97706;color:#fef3c7", "T1B"))

            if tier2:
                st.html('<div style="font-size:0.85em;color:#fb923c;padding:4px 0;font-weight:600;margin-top:6px">'
                        'TIER 2 — BET OVER (1.0 unit) · Pruned Venue standalone (64.3% hit, N=236)</div>')
                for g in tier2:
                    st.html(_render_signal_row(g, "#431407;border:1px solid #ea580c;color:#fed7aa", "T2"))

            if context:
                st.html('<div style="font-size:0.85em;color:#9ca3af;padding:4px 0;font-weight:600;margin-top:6px">'
                        'CONTEXT ONLY — DO NOT BET (negative ROI standalone)</div>')
                for g in context:
                    matchup = "%s @ %s" % (g.get("away_team",""), g.get("home_team",""))
                    d = g.get("archetype_direction") or g.get("shot_direction", "")
                    note = g.get("archetype_note") or g.get("shot_note", "")
                    st.html(
                        f'<div style="padding:3px 8px;margin:2px 0;font-size:0.82em;color:#6b7280;'
                        f'border-left:3px solid #4b5563">'
                        f'{matchup} — {d} · {note} · ⚠ context only</div>')

            if conflicts:
                st.html('<div style="font-size:0.85em;color:#fbbf24;padding:4px 0;font-weight:600;margin-top:6px">'
                        'CONFLICT — PASS</div>')
                for g in conflicts:
                    matchup = "%s @ %s" % (g.get("away_team",""), g.get("home_team",""))
                    st.html(
                        f'<div style="padding:3px 8px;margin:2px 0;font-size:0.82em;color:#fde68a;'
                        f'border-left:3px solid #d97706">'
                        f'🟡 {matchup} — signals disagree — PASS</div>')

            st.caption(
                "System bets OVER signals only. CORE = DAL/UTA/PHI @ IND/OKC/SAS (77.5% hit). "
                "Tier 1B = Pruned Venue + OREB (~64%+). Tier 2 = Pruned Venue standalone (64.3%). "
                "UNDER signals (pace, shot under) are DO NOT BET — negative ROI standalone."
            )

    with review_tab:
        _render_review_tab("nba", {"daily_review": nba.get("daily_review"), "weekly_review": nba.get("weekly_review")})


# ── mlb tab renderer ──────────────────────────────────────────────────────────

def _render_mlb_tab(data: dict | None, stats: dict | None) -> None:
    # ── season stats banner ───────────────────────────────────────────────
    if stats:
        _render_season_header(stats)

    # ── alerts (lineup changes + transactions) ────────────────────────────
    if data:
        _render_alerts(data)

    picks_tab, review_tab = st.tabs(["Today's Picks", "Results Review"])

    with picks_tab:
        # ── stop rule suspension banner ────────────────────────────────────────
        _mlb_stop = (data or {}).get("stop_rule_status", {})
        _mlb_model_susp  = _mlb_stop.get("model_suspended", False)
        _mlb_tier_susps  = _mlb_stop.get("suspended_tiers", [])
        _mlb_full_detail = _mlb_stop.get("full_model_details", {})
        _mlb_tier_detail = _mlb_stop.get("tier_details", {})

        if _mlb_model_susp:
            # Case B: full model suspended
            _fn = _mlb_full_detail.get("n", "?")
            _fr = _mlb_full_detail.get("roi")
            _fr_str = f"{_fr:.1f}%" if _fr is not None else "?"
            st.html(f"""
            <div style="background:#2d1515;border:2px solid #dc2626;border-radius:8px;
                        padding:12px 16px;margin-bottom:14px">
              <span style="color:#f87171;font-weight:700;font-size:1.05em">
                🚨 MLB MODEL FULLY SUSPENDED
              </span>
              <span style="color:#fca5a5;margin-left:10px;font-size:0.88em">
                Full-model ROI hit {_fr_str} on {_fn} live plays (threshold: −12%).
                All signals are paused.
              </span>
              <div style="color:#fca5a5;font-size:0.80em;margin-top:6px">
                Manual reset required:
                <code>python mlb_reset_stop_rules.py --reason "..."</code>
              </div>
            </div>
            """)
        elif _mlb_tier_susps:
            # Case A: one or more tiers suspended, model still running
            for _t in _mlb_tier_susps:
                _td = _mlb_tier_detail.get(_t, {})
                _tn = _td.get("n", "?")
                _tr = _td.get("roi")
                _tr_str = f"{_tr:.1f}%" if _tr is not None else "?"
                st.html(f"""
                <div style="background:#2d1b0e;border:2px solid #d97706;border-radius:8px;
                            padding:12px 16px;margin-bottom:8px">
                  <span style="color:#fbbf24;font-weight:700;font-size:1.05em">
                    ⛔ MLB {_t} tier suspended
                  </span>
                  <span style="color:#fde68a;margin-left:10px;font-size:0.88em">
                    {_t}-confidence tier ROI hit {_tr_str} on {_tn} live plays
                    (threshold: −10%). {_t} signals paused. Other tiers continue.
                  </span>
                  <div style="color:#fde68a;font-size:0.80em;margin-top:6px">
                    Manual reset required:
                    <code>python mlb_reset_stop_rules.py --reason "..."</code>
                  </div>
                </div>
                """)

        # ── segment overlay status ─────────────────────────────────────────────
        try:
            import json as _json
            _ovl_path = os.path.join(os.path.dirname(__file__), "mlb", "config_segment_overlay.json")
            if os.path.exists(_ovl_path):
                with open(_ovl_path) as _f:
                    _ovl_cfg = _json.load(_f)
                if _ovl_cfg.get("overlay_active"):
                    _ovl_stop_path = os.path.join(os.path.dirname(__file__), "mlb", "data", "mlb_overlay_stop_rules.json")
                    _ovl_stop = {}
                    if os.path.exists(_ovl_stop_path):
                        with open(_ovl_stop_path) as _f:
                            _ovl_stop = _json.load(_f)
                    _suspended = _ovl_stop.get("overlay_suspended", False)
                    _seg_stats = _ovl_stop.get("segment_stats", {})
                    if _suspended:
                        st.html('<div style="background:#2d1515;border:1px solid #dc2626;border-radius:6px;padding:8px;margin-bottom:8px;font-size:0.82em;color:#f87171">⛔ Segment overlay suspended</div>')
                    else:
                        st.html('<div style="font-size:0.78em;color:#4ade80;margin-bottom:6px">🎯 Segment overlay active (calm+pitcher_ump, low_total+warm → OVER boost)</div>')
        except Exception:
            pass

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

    with review_tab:
        _render_review_tab("mlb", data)


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
    tab_mlb, tab_nba, tab_nhl, tab_soccer, tab_nfl, tab_golf, tab_reviews = st.tabs(["⚾ MLB", "🏀 NBA", "🏒 NHL", "⚽ Soccer", "🏈 NFL", "⛳ Golf", "📋 Reviews"])

    with tab_mlb:
        _render_mlb_tab(data, stats)

    with tab_nba:
        _render_nba_tab()

    with tab_nhl:
        _render_nhl_tab()

    with tab_soccer:
        _render_soccer_tab()

    with tab_nfl:
        _render_nfl_tab()

    with tab_golf:
        _render_golf_tab()

    with tab_reviews:
        _render_reviews_tab()


# ── Reviews tab rendering ─────────────────────────────────────────────────────

def _render_reviews_tab() -> None:
    st.html("<h4 style='margin:0 0 8px 0'>📋 Reviews & Alerts</h4>")

    # Load state
    state_path = os.path.join(os.path.dirname(__file__), "review_engine", "engine_state.json")
    if os.path.exists(state_path):
        with open(state_path) as f:
            state = json.load(f)
    else:
        state = {"issued_checkpoints": [], "last_weekly": None}

    # Active alerts from recent checkpoint files
    cp_dir = os.path.join(os.path.dirname(__file__), "reviews", "checkpoints")
    wk_dir = os.path.join(os.path.dirname(__file__), "reviews", "weekly")

    # Recent checkpoints
    st.html("<div style='font-size:0.85em;font-weight:600;color:#94a3b8;margin-top:12px'>Recent Checkpoints</div>")
    if os.path.exists(cp_dir):
        files = sorted([f for f in os.listdir(cp_dir) if f.endswith(".txt")], reverse=True)
        if files:
            for f in files[:5]:
                with open(os.path.join(cp_dir, f)) as fh:
                    content = fh.read()
                with st.expander(f"📌 {f}", expanded=False):
                    st.code(content, language=None)
        else:
            st.caption("No checkpoints triggered yet.")
    else:
        st.caption("No checkpoints triggered yet.")

    # Latest weekly digest
    st.html("<div style='font-size:0.85em;font-weight:600;color:#94a3b8;margin-top:16px'>Latest Weekly Digest</div>")
    if os.path.exists(wk_dir):
        files = sorted([f for f in os.listdir(wk_dir) if f.endswith(".txt")], reverse=True)
        if files:
            with open(os.path.join(wk_dir, files[0])) as fh:
                st.code(fh.read(), language=None)
        else:
            st.caption("No weekly digest generated yet. Runs every Sunday.")
    else:
        st.caption("No weekly digest generated yet.")

    # Upcoming checkpoints
    st.html("<div style='font-size:0.85em;font-weight:600;color:#94a3b8;margin-top:16px'>Pending Checkpoints</div>")
    cfg_path = os.path.join(os.path.dirname(__file__), "review_engine", "checkpoint_config.json")
    if os.path.exists(cfg_path):
        with open(cfg_path) as f:
            cfg = json.load(f)
        issued = set(state.get("issued_checkpoints", []))
        pending = []
        for mid, mcfg in cfg.get("models", {}).items():
            if mcfg.get("mode") == "dormant":
                continue
            for cp in mcfg.get("checkpoints", []):
                cp_id = f"{mid}_{cp}"
                if cp_id not in issued:
                    pending.append(f"{mcfg['sport']} {mcfg['phase']}: {cp}-bet checkpoint")
        if pending:
            for p in pending:
                st.html(f"<div style='font-size:0.78em;color:#94a3b8'>⏳ {p}</div>")
        else:
            st.caption("All checkpoints reached.")


# ── NFL tab rendering ──────────────────────────────────────────────────────────

def _render_nfl_tab() -> None:
    nfl_path = os.path.join(os.path.dirname(__file__), "nfl_results.json")
    if not os.path.exists(nfl_path):
        st.caption("NFL model not yet deployed. Run push_nfl.py to generate data.")
        return

    with open(nfl_path) as f:
        nfl = json.load(f)

    model_status = nfl.get("model_status", "not_deployed")

    picks_tab, review_tab = st.tabs(["Today's Picks", "Results Review"])

    with picks_tab:
        st.html(
            f"<div style='font-size:0.82em;color:#f59e0b;font-weight:600;"
            f"margin-bottom:8px'>Status: {nfl.get('model_description', '')}</div>"
        )

        # ── Conditional Edges (Phase 8) ──────────────────────────────
        cond = nfl.get("conditional_signals", {})
        cond_today = cond.get("today", [])

        if cond_today:
            st.html(
                "<div style='font-size:0.88em;font-weight:700;color:#4ade80;"
                "margin-bottom:8px'>🎯 Conditional Edge Signals</div>"
            )
            for s in cond_today:
                home = s.get("home_team", "")
                away = s.get("away_team", "")
                seg = s.get("display_name", s.get("segment_name", ""))
                line = s.get("closing_total_line")
                week = s.get("week")
                risk = s.get("risk_note", "standard")
                risk_badge = ""
                if "HIGH" in str(risk).upper() or "monitor" in str(risk).lower():
                    risk_badge = '<span style="color:#f59e0b;font-size:0.75em"> ⚠️ Monitor</span>'

                st.html(f"""
                <div style="background:#1a1a2e;border:1px solid #22c55e;border-radius:8px;padding:12px;margin-bottom:8px">
                  <div>
                    <span style="background:#052e16;color:#22c55e;padding:2px 8px;border-radius:4px;font-size:0.75em;font-weight:600">{seg}</span>
                    {risk_badge}
                  </div>
                  <div style="font-weight:600;font-size:0.95em;margin-top:6px">{away} @ {home}</div>
                  <div style="font-size:0.85em;color:#94a3b8">
                    OVER {line} | Week {week}
                  </div>
                </div>
                """)
        else:
            st.caption("No conditional edge signals today.")

        # Segment performance (live only)
        seg_perf = cond.get("segment_performance", {})
        if seg_perf:
            st.html(
                "<div style='font-size:0.82em;font-weight:600;color:#94a3b8;"
                "margin-top:16px;margin-bottom:6px'>Segment Performance (Live Only)</div>"
            )
            for seg_name, sp in seg_perf.items():
                n = sp.get("live_n", 0)
                hit = sp.get("live_hit_rate")
                roi = sp.get("live_roi")
                status = sp.get("status", "active")
                status_icon = "✅" if status == "active" else "⛔"

                if n < 10:
                    st.caption(f"{status_icon} {seg_name}: Insufficient live sample (n={n})")
                elif hit is not None and roi is not None:
                    color = "#4ade80" if roi > 0 else "#f87171"
                    st.html(f"""
                    <div style="font-size:0.78em;color:#94a3b8">
                      {status_icon} <b>{seg_name}</b>: {n} signals, hit={hit*100:.1f}%,
                      <span style="color:{color}">ROI={roi:+.1f}%</span>
                    </div>
                    """)

        # Conditional stop rules
        cond_stop = cond.get("stop_rule_status", {})
        if cond_stop.get("model_suspended"):
            st.html('<div style="background:#7f1d1d;color:#fca5a5;padding:8px;border-radius:6px;margin-top:8px">⛔ NFL conditional model suspended</div>')
        elif cond_stop.get("suspended_segments"):
            for seg in cond_stop["suspended_segments"]:
                st.html(f'<div style="font-size:0.78em;color:#f87171">⛔ {seg} suspended</div>')

        # OOS reference
        oos_ref = nfl.get("oos_reference", {})
        if oos_ref:
            st.html(
                "<div style='font-size:0.82em;font-weight:600;color:#94a3b8;"
                "margin-top:16px;margin-bottom:6px'>OOS Backtest Reference (2024)</div>"
            )
            st.html(f"""
            <div style='font-size:0.78em;color:#94a3b8;line-height:1.8'>
              Hit rate: {oos_ref.get('overall_hit', 0)*100:.1f}% |
              ROI: {oos_ref.get('overall_roi', 0):+.1f}% |
              N: {oos_ref.get('n_signals', 0)} |
              Status: {oos_ref.get('model_status', 'unknown')}
              <br>{oos_ref.get('note', '')}
            </div>
            """)

    with review_tab:
        _render_review_tab("nfl", {
            "daily_review": nfl.get("daily_review"),
            "weekly_review": nfl.get("weekly_review"),
        })


def _render_golf_tab() -> None:
    golf = load_golf_results()

    col_title, col_btn = st.columns([5, 1])
    with col_title:
        if golf:
            ev_name = golf.get("event_name", "")
            last_up = golf.get("last_updated", golf.get("generated_at", ""))[:19]
            major_tag = " (Major)" if golf.get("is_major") else ""
            st.html(f"<h3 style='margin:0 0 4px 0'>&#9971; Golf Shadow{major_tag}</h3>"
                    f"<span style='color:#888;font-size:0.85rem'>Last updated {last_up}</span>")
        else:
            st.html("<h3 style='margin:0 0 4px 0'>&#9971; Golf Shadow</h3>")
    with col_btn:
        st.write("")
        if st.button("Refresh", key="golf_refresh", use_container_width=True):
            st.cache_data.clear()
            st.rerun()

    if golf is None:
        st.info("No Golf data available yet. Run `python push_golf.py` to generate.")
        return

    picks_tab, matchup_tab, info_tab = st.tabs(["Outright Board", "Matchups", "Model Info"])

    with picks_tab:
        ev_name = golf.get("event_name", "No active event")
        n_cand = golf.get("n_candidates", 0)
        n_lean = golf.get("n_leans", 0)
        st.html(f'<div class="section-hdr">{ev_name} &mdash; '
                f'{n_cand} candidates, {n_lean} leans</div>')

        plays = golf.get("plays", [])
        if plays:
            for p in plays:
                cls = p.get("classification", "")
                badge_color = "#2ecc71" if cls == "candidate" else "#f1c40f" if cls == "lean" else "#888"
                edge = p.get("edge", 0)
                direction = p.get("direction", "")
                odds_str = ""
                if p.get("close_odds"):
                    o = p["close_odds"]
                    odds_str = "%+d" % int(o) if o >= 0 else "%d" % int(o)
                st.html(
                    f'<div style="display:flex;align-items:center;padding:6px 0;border-bottom:1px solid #eee">'
                    f'<span style="background:{badge_color};color:#fff;padding:2px 8px;border-radius:4px;'
                    f'font-size:0.75rem;margin-right:10px">{cls.upper()}</span>'
                    f'<span style="width:180px;font-weight:600">{p.get("player_name","")}</span>'
                    f'<span style="width:90px;color:#666">{p.get("market","").replace("_"," ")}</span>'
                    f'<span style="width:70px">{p.get("model_prob",0):.1f}%</span>'
                    f'<span style="width:70px;color:#888">{p.get("market_prob",0):.1f}%</span>'
                    f'<span style="width:70px;color:{"#2ecc71" if edge>0 else "#e74c3c"}">{edge:+.1f}%</span>'
                    f'<span style="width:60px">{direction}</span>'
                    f'<span style="width:60px;color:#888">{odds_str}</span></div>')
        else:
            st.caption("No candidates this week.")

        st.html('<div class="section-hdr">Season Summary</div>')
        ss = golf.get("season_stats", {})
        if ss:
            cols = st.columns(len(ss))
            for i, (mkt, stats) in enumerate(ss.items()):
                with cols[i]:
                    st.metric(mkt.replace("_", " ").title(),
                              f"{stats.get('hit_rate', 0):.1f}% hit",
                              f"{stats.get('roi', 0):+.1f}% ROI")
                    st.caption(f"N={stats.get('n', 0)}, CLV={stats.get('clv', 0):+.1f}%")

        recent = golf.get("recent_results", [])
        if recent:
            st.html('<div class="section-hdr">Recent Tournaments</div>')
            for r in recent:
                roi_color = "#2ecc71" if r.get("roi", 0) > 0 else "#e74c3c"
                st.html(
                    f'<div style="padding:4px 0;border-bottom:1px solid #f0f0f0">'
                    f'<span style="width:200px;display:inline-block">{r.get("event_name","")}</span>'
                    f'<span style="width:100px;display:inline-block">{r.get("n_candidates",0)} cands</span>'
                    f'<span style="width:80px;display:inline-block">{r.get("hit_rate",0):.0f}% hit</span>'
                    f'<span style="width:80px;display:inline-block;color:{roi_color}">'
                    f'{r.get("roi",0):+.1f}%</span></div>')

    with matchup_tab:
        matchup_plays = golf.get("matchup_candidates", [])
        mn_cand = golf.get("matchup_n_candidates", 0)
        mn_lean = golf.get("matchup_n_leans", 0)
        st.html(f'<div class="section-hdr">Matchup Candidates &mdash; '
                f'{mn_cand} candidates, {mn_lean} leans</div>')

        if matchup_plays:
            for mp in matchup_plays:
                cls = mp.get("classification", "")
                badge_color = "#2ecc71" if cls == "candidate" else "#f1c40f"
                edge = mp.get("bet_edge", 0)
                p3 = mp.get("player_3", "")
                players = "%s vs %s" % (mp.get("player_1", ""), mp.get("player_2", ""))
                if p3:
                    players += " vs %s" % p3
                st.html(
                    f'<div style="display:flex;align-items:center;padding:6px 0;border-bottom:1px solid #eee">'
                    f'<span style="background:{badge_color};color:#fff;padding:2px 8px;border-radius:4px;'
                    f'font-size:0.75rem;margin-right:10px">{cls.upper()}</span>'
                    f'<span style="width:300px;font-weight:600">{players}</span>'
                    f'<span style="width:80px;color:#666">{mp.get("match_type","").replace("_"," ")[:12]}</span>'
                    f'<span style="width:80px;color:#888">{mp.get("book","")[:10]}</span>'
                    f'<span style="width:70px;color:#2ecc71">{edge:+.1f}%</span></div>')
        else:
            st.caption("No matchup candidates this week. Matchup odds typically available Tue-Thu.")

        st.caption("Soft book tracking: building sample for Bovada/Bet365 hypothesis test. "
                   "2020-2022 profitable window has closed at FanDuel/DraftKings.")

    with info_tab:
        mi = golf.get("model_info", {})
        st.html('<div class="section-hdr">Model Details</div>')
        st.markdown(
            "- **Model**: %s\n- **OOS AUC**: %.3f\n- **OOS Brier**: %.3f\n"
            "- **Confidence tier**: %s\n- **Note**: %s\n"
            "- **Key finding**: Signal exists in -200 to -110 odds zone only. "
            "Heavy favorites (-300+) show breakeven ROI despite correct predictions.\n"
            "- **Markets**: make_cut (primary), top_20 (secondary), win/top_5/top_10 (passive)"
            % (mi.get("model", "DG-only"), mi.get("oos_auc", 0), mi.get("oos_brier", 0),
               mi.get("confidence_tier", "LOW"), mi.get("note", "")))


main()
