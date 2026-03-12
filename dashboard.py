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
.parlay-title {
    font-size: 0.72em;
    font-weight: 700;
    letter-spacing: 0.10em;
    text-transform: uppercase;
    color: #818cf8;
    margin-bottom: 10px;
}
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

/* ── Responsive ── */
@media (max-width: 600px) {
    .matchup { font-size: 1.05em; }
    .proj-row { gap: 4px 12px; }
    .parlay-leg { font-size: 0.78em; }
    .stat-grid { gap: 8px 18px; }
}
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


def _last_run_label(data: dict) -> str:
    ts = data.get("generated_at")
    if not ts:
        return "never"
    try:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        return dt.strftime("%b %-d at %-I:%M %p UTC")
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

    st.markdown(html, unsafe_allow_html=True)


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
            st.markdown(
                _analytics_table(temp_rows, ["Temperature", "Record", "Win %", "ROI", "No Line"]),
                unsafe_allow_html=True
            )
        else:
            st.caption("No data yet.")

        st.markdown("<br>", unsafe_allow_html=True)

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
            st.markdown(
                _analytics_table(wind_rows, ["Wind", "Record", "Win %", "ROI", "No Line"]),
                unsafe_allow_html=True
            )
        else:
            st.caption("No data yet.")

        st.markdown("<br>", unsafe_allow_html=True)

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
            st.markdown(
                _analytics_table(park_rows, ["Park", "Record", "Win %", "ROI", "No Line"]),
                unsafe_allow_html=True
            )
        else:
            st.caption("No data yet.")

        st.markdown("<br>", unsafe_allow_html=True)

        # ── projection accuracy by stars ──────────────────────────────────────
        acc = stats.get("projection_accuracy", {})
        by_star_mae = acc.get("mae_by_stars", {})
        if by_star_mae:
            st.markdown("**Projection Accuracy by Star Rating (MAE)**")
            mae_rows = [
                ((label, ""), (f"{mae:.2f} runs", ""))
                for label, mae in by_star_mae.items()
            ]
            st.markdown(
                _analytics_table(mae_rows, ["Rating", "MAE"]),
                unsafe_allow_html=True
            )
            st.markdown("<br>", unsafe_allow_html=True)

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
            st.markdown(
                _analytics_table(corr_rows, ["Factor", "Record", "Win %"]),
                unsafe_allow_html=True
            )
            st.markdown("<br>", unsafe_allow_html=True)

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
            st.markdown(
                _analytics_table(miss_rows,
                    ["Date", "Game", "Proj", "Actual", "Error", "Result", "Stars"]),
                unsafe_allow_html=True
            )


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


def _render_card(b: dict) -> None:
    rating  = b["rating"]
    game    = b["game"]
    proj    = b["proj"]
    fe      = b.get("full_edge", {})
    f5e     = b.get("f5_edge", {})
    summary = b.get("summary", "")
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

    st.markdown(
        f'<div class="{card_cls}">'
        f'{header}'
        f'{_meta_html(f, game)}'
        f'{proj_row}'
        f'<div class="card-summary">{summary}</div>'
        f'</div>',
        unsafe_allow_html=True,
    )


def _render_parlay(parlay: list) -> None:
    if len(parlay) < 2:
        return

    st.markdown(
        f'<div class="section-hdr">⚡ {len(parlay)}-Leg Parlay Card</div>',
        unsafe_allow_html=True,
    )
    legs = ""
    for i, b in enumerate(parlay, 1):
        g    = b["game"]
        proj = b["proj"]
        fe   = b.get("full_edge", {})
        lean = proj.get("lean", "NEUTRAL")

        matchup  = f"{g['away_team']} @ {g['home_team']}"
        proj_str = f"{proj['proj_total_full']:.1f}"
        line_str = f"{fe['consensus']:.1f}" if fe.get("consensus") else "—"
        edge_str = f"{fe['edge']:+.1f}" if fe.get("edge") is not None else "—"
        lean_cls = "lean-over" if lean == "OVER" else "lean-under"

        legs += (
            f'<div class="parlay-leg">'
            f'<span class="parlay-matchup">{i}. {matchup}</span>'
            f'<span class="lean-badge {lean_cls}" style="font-size:0.78em">'
            f'{lean} {proj_str}</span>'
            f'<span><span style="color:#4a5568">Line</span> {line_str}</span>'
            f'<span><span style="color:#4a5568">Edge</span> {edge_str}</span>'
            f'<span>{b["rating"]}</span>'
            f'</div>'
        )

    st.markdown(
        f'<div class="parlay-card">'
        f'<div class="parlay-title">⚡ Parlay</div>'
        f'{legs}'
        f'</div>',
        unsafe_allow_html=True,
    )


# ── main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    data  = load_results()
    stats = load_season_stats()
    last_run = _last_run_label(data) if data else _last_run_label(stats) if stats else "never"

    # ── page header ───────────────────────────────────────────────────────────
    col_title, col_btn = st.columns([5, 1])
    with col_title:
        st.markdown(
            f"### ⚾ I Am Not Uncertain"
            f"<br><span style='font-size:0.78em;color:#4a5568'>"
            f"Last updated {last_run}"
            f"</span>",
            unsafe_allow_html=True,
        )
    with col_btn:
        st.write("")
        if st.button("🔄 Refresh", use_container_width=True):
            st.cache_data.clear()
            st.rerun()

    # ── season stats banner ───────────────────────────────────────────────────
    if stats:
        _render_season_header(stats)

    # ── no data state ─────────────────────────────────────────────────────────
    if data is None:
        st.info(
            "No projections available yet. "
            "Run `python push_results.py` on your local machine to publish today's card."
        )
        if stats:
            _render_analytics(stats)
        return

    game_date = data.get("game_date", "")
    plays     = data.get("plays", [])
    no_plays  = data.get("no_plays", [])
    parlay    = data.get("parlay", [])

    if game_date:
        st.caption(f"Projections for **{game_date}**")

    # ── plays ─────────────────────────────────────────────────────────────────
    if plays:
        n = len(plays)
        st.markdown(
            f'<div class="section-hdr">🎯 Plays — {n} game{"s" if n != 1 else ""}</div>',
            unsafe_allow_html=True,
        )
        for b in plays:
            _render_card(b)
    else:
        st.markdown('<div class="section-hdr">🎯 Plays</div>', unsafe_allow_html=True)
        st.caption("No plays meeting the confidence threshold today.")

    # ── parlay ────────────────────────────────────────────────────────────────
    _render_parlay(parlay)

    # ── no-plays ──────────────────────────────────────────────────────────────
    if no_plays:
        with st.expander(f"No Plays — {len(no_plays)} game{'s' if len(no_plays) != 1 else ''}"):
            for b in no_plays:
                _render_card(b)

    # ── analytics ─────────────────────────────────────────────────────────────
    if stats:
        _render_analytics(stats)


main()
