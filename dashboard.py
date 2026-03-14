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
NBA_RESULTS_FILE  = os.path.join(os.path.dirname(os.path.abspath(__file__)), "nba_results.json")

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


def _nba_conf_badge(conf: str) -> str:
    c = (conf or "LOW").upper()
    return f'<span class="conf-badge conf-{c}">{c.lower()}</span>'


def _nba_picks_table(games: list[dict], h1: bool = False) -> str:
    """Build an HTML table for full-game or H1 picks."""
    if not games:
        return ""

    proj_col  = "pred_h1"  if h1 else "pred_total"
    line_col  = "h1_line"  if h1 else "line"
    edge_col  = "h1_edge"  if h1 else "edge"
    lean_col  = "h1_lean"  if h1 else "lean"
    p_col     = "h1_p_over" if h1 else "p_over"
    conf_col  = "h1_confidence" if h1 else "confidence"

    rows_html = ""
    for g in games:
        matchup   = f"{g['away_team']} @ {g['home_team']}"
        tip       = g.get("game_time_et") or "—"
        lean      = g.get(lean_col) or "—"
        proj      = g.get(proj_col)
        line      = g.get(line_col)
        edge      = g.get(edge_col)
        p_over    = g.get(p_col)
        conf      = g.get(conf_col) or "LOW"
        gap_flag  = bool(g.get("market_gap_flag"))

        proj_s    = f"{float(proj):.1f}" if proj is not None else "—"
        line_s    = f"{float(line):.1f}" if line is not None else "—"
        edge_s    = f"{float(edge):+.1f}" if edge is not None else "—"
        p_s       = f"{float(p_over)*100:.1f}%" if p_over is not None else "—"

        edge_cls  = "edge-pos" if (edge or 0) > 0 else "edge-neg"
        lean_html = _nba_lean_badge(lean)
        conf_html = _nba_conf_badge(conf)
        gap_html  = ' <span style="color:#f59e0b;font-size:0.78em" title="Model/market gap > 12 pts — review manually">⚠ gap</span>' if gap_flag and not h1 else ""

        rows_html += f"""
        <tr>
          <td style="font-weight:600;color:#f1f5f9">{matchup}{gap_html}</td>
          <td style="color:#94a3b8">{tip}</td>
          <td>{lean_html}</td>
          <td style="font-weight:600;color:#e2e8f0">{proj_s}</td>
          <td style="color:#94a3b8">{line_s}</td>
          <td><span class="{edge_cls}">{edge_s}</span></td>
          <td style="color:#94a3b8">{p_s}</td>
          <td>{conf_html}</td>
        </tr>"""

    return f"""
    <table class="analytics-table" style="width:100%">
      <thead><tr>
        <th>Matchup</th><th>Tip</th><th>Lean</th>
        <th>Proj</th><th>Line</th><th>Edge</th>
        <th>P(over)</th><th>Conf</th>
      </tr></thead>
      <tbody>{rows_html}</tbody>
    </table>"""


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

    plays    = nba.get("plays", [])
    no_plays = nba.get("no_plays", [])
    accuracy = nba.get("season_accuracy", {})

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

    # ── full-game picks ───────────────────────────────────────────────────────
    if plays:
        n = len(plays)
        st.html(f'<div class="section-hdr">🎯 Full Game — {n} play{"s" if n != 1 else ""}</div>')
        st.html(_nba_picks_table(plays, h1=False))
    else:
        st.html('<div class="section-hdr">🎯 Full Game</div>')
        st.caption("No full-game plays above threshold today.")

    # ── market gap review block ───────────────────────────────────────────────
    gap_games = [g for g in plays + no_plays if g.get("market_gap_flag")]
    if gap_games:
        rows_html = ""
        for g in gap_games:
            matchup = f"{g['away_team']} @ {g['home_team']}"
            proj    = g.get("pred_total")
            line    = g.get("line")
            edge    = g.get("edge")
            proj_s  = f"{float(proj):.1f}" if proj is not None else "—"
            line_s  = f"{float(line):.1f}" if line is not None else "—"
            edge_s  = f"{float(edge):+.1f}" if edge is not None else "—"
            rows_html += (
                f'<div class="alert-row">'
                f'<div class="alert-icon">⚠</div>'
                f'<div class="alert-body">'
                f'<span class="alert-matchup">{matchup}</span>'
                f'<span class="alert-detail">'
                f'Model {proj_s} vs line {line_s} · gap {edge_s} pts — review before acting'
                f'</span>'
                f'</div></div>'
            )
        st.html(f"""
        <div class="alerts-section" style="margin-top:14px">
          <div class="alerts-title">⚠ Market Gap Review — model/market &gt; 12 pts</div>
          {rows_html}
        </div>
        """)

    # ── H1 picks ──────────────────────────────────────────────────────────────
    h1_plays = [g for g in plays if g.get("pred_h1") is not None]
    h1_no_plays = [g for g in no_plays if g.get("pred_h1") is not None]
    all_h1 = h1_plays + h1_no_plays

    if all_h1:
        st.html(
            f'<div class="section-hdr">⏱ First Half — {len(h1_plays)} play{"s" if len(h1_plays) != 1 else ""} '
            f'({len(all_h1)} games with H1 projection)</div>'
        )
        st.html(_nba_picks_table(all_h1, h1=True))

    # ── no-plays ──────────────────────────────────────────────────────────────
    if no_plays:
        with st.expander(
            f"No Plays — {len(no_plays)} game{'s' if len(no_plays) != 1 else ''}",
            expanded=False
        ):
            st.html(_nba_picks_table(no_plays, h1=False))


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
    tab_mlb, tab_nba = st.tabs(["⚾ MLB", "🏀 NBA"])

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

    with tab_nba:
        _render_nba_tab()


main()
