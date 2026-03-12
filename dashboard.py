#!/usr/bin/env python3
"""
MLB Totals Model — Streamlit Dashboard
=======================================
Reads from results.json, which is pushed from the local machine each morning
after run_model.py completes (via push_results.py).

Launch:  streamlit run dashboard.py
"""

import json
import os
from datetime import datetime

import streamlit as st

RESULTS_FILE  = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results.json")
EDGE_MIN_RUNS = 0.5   # mirrors config.py

# ── page config ───────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="MLB Totals Model",
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

/* ── Season record ── */
.record-bar {
    display: flex;
    flex-wrap: wrap;
    gap: 20px 32px;
    background: #0f1117;
    border-radius: 8px;
    padding: 12px 18px;
    margin-bottom: 18px;
    border: 1px solid #1e2535;
}
.record-stat .num { font-size: 1.6em; font-weight: 700; color: #f1f5f9; line-height: 1.1; }
.record-stat .lbl { font-size: 0.75em; color: #4a5568; }

/* ── Responsive ── */
@media (max-width: 600px) {
    .matchup { font-size: 1.05em; }
    .proj-row { gap: 4px 12px; }
    .parlay-leg { font-size: 0.78em; }
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


def _last_run_label(data: dict) -> str:
    ts = data.get("generated_at")
    if not ts:
        return "unknown"
    try:
        dt = datetime.fromisoformat(ts)
        return dt.strftime("%b %-d at %I:%M %p")
    except Exception:
        return ts


# ── rendering helpers ─────────────────────────────────────────────────────────

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


def _render_record(record: dict) -> None:
    total = record.get("total", 0)
    if not total:
        return

    correct = (record.get("correct_over") or 0) + (record.get("correct_under") or 0)
    pushes  = record.get("pushes") or 0
    decided = total - pushes
    losses  = decided - correct
    pct     = (correct / decided * 100) if decided > 0 else 0.0

    st.markdown(
        f'<div class="record-bar">'
        f'<div class="record-stat">'
        f'  <div class="num">{correct}–{losses}</div>'
        f'  <div class="lbl">Season Record (vs line)</div>'
        f'</div>'
        f'<div class="record-stat">'
        f'  <div class="num">{pct:.1f}%</div>'
        f'  <div class="lbl">Win Rate</div>'
        f'</div>'
        f'<div class="record-stat">'
        f'  <div class="num">{total}</div>'
        f'  <div class="lbl">Total Tracked</div>'
        f'</div>'
        f'<div class="record-stat">'
        f'  <div class="num">{pushes}</div>'
        f'  <div class="lbl">Pushes</div>'
        f'</div>'
        f'</div>',
        unsafe_allow_html=True,
    )


# ── main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    # Header
    col_title, col_btn = st.columns([5, 1])

    data = load_results()
    last_run = _last_run_label(data) if data else "never"

    with col_title:
        st.markdown(
            f"### ⚾ MLB Totals Model"
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

    # No data state
    if data is None:
        st.info(
            "No projections available yet. "
            "Run `python3 push_results.py` on your local machine to publish today's card."
        )
        return

    game_date = data.get("date", "")
    plays     = data.get("plays", [])
    no_plays  = data.get("no_plays", [])
    parlay    = data.get("parlay", [])
    record    = data.get("season_record", {})

    if game_date:
        st.caption(f"Projections for **{game_date}**")

    # Season record
    _render_record(record)

    # Plays
    if plays:
        n = len(plays)
        st.markdown(
            f'<div class="section-hdr">🎯 Plays — {n} game{"s" if n != 1 else ""}</div>',
            unsafe_allow_html=True,
        )
        for b in plays:
            _render_card(b)
    else:
        st.markdown(
            '<div class="section-hdr">🎯 Plays</div>',
            unsafe_allow_html=True,
        )
        st.caption("No plays meeting the confidence threshold today.")

    # Parlay
    _render_parlay(parlay)

    # No-plays
    if no_plays:
        with st.expander(f"No Plays — {len(no_plays)} game{'s' if len(no_plays) != 1 else ''}"):
            for b in no_plays:
                _render_card(b)


main()
