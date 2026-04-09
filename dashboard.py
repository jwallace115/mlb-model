# Last deploy: 2026-04-06 session 2
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

import pandas as pd
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

</style>
""", unsafe_allow_html=True)


# ── data loading ──────────────────────────────────────────────────────────────

@st.cache_data(ttl=300, show_spinner=False)
def load_results() -> dict | None:
    if not os.path.exists(RESULTS_FILE):
        return None
    with open(RESULTS_FILE) as f:
        return json.load(f)


@st.cache_data(ttl=300, show_spinner=False)
def load_season_stats() -> dict | None:
    if not os.path.exists(SEASON_STATS_FILE):
        return None
    with open(SEASON_STATS_FILE) as f:
        return json.load(f)


@st.cache_data(ttl=300, show_spinner=False)
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


def _pipeline_freshness(key: str) -> str:
    """Return HTML snippet showing last pipeline run time for a sport."""
    try:
        lu_path = os.path.join(os.path.dirname(__file__), "shared", "last_updated.json")
        if not os.path.exists(lu_path):
            return "<span style='font-size:0.75em;color:#64748b'>Last updated: unknown</span>"
        with open(lu_path) as f:
            lu = json.load(f)
        ts_str = lu.get(key)
        if not ts_str:
            return "<span style='font-size:0.75em;color:#64748b'>Last updated: unknown</span>"
        from zoneinfo import ZoneInfo
        dt = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
        dt_et = dt.astimezone(ZoneInfo("America/New_York"))
        label = dt_et.strftime("%b %-d, %-I:%M %p ET")
        hours_ago = (datetime.now(dt.tzinfo) - dt).total_seconds() / 3600
        if hours_ago > 26:
            return (f"<span style='font-size:0.75em;color:#eab308'>"
                    f"\u26a0\ufe0f Last updated: {label} (stale)</span>")
        return (f"<span style='font-size:0.75em;color:#94a3b8'>"
                f"\U0001f4ca Last updated: {label}</span>")
    except Exception:
        return "<span style='font-size:0.75em;color:#64748b'>Last updated: unknown</span>"


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
    """Render 2026 season tracking from live signal logs only."""
    import json as _json_sh

    # Read from the three live signal logs (parquet or JSON fallback)
    _base = os.path.dirname(os.path.abspath(__file__))
    total_n = 0; total_wins = 0; total_losses = 0; total_pushes = 0; total_net = 0.0

    for log_name in ["signals_2026", "f5_signals_2026", "f5_runline_2026"]:
        df = None
        for ext in [".parquet", ".json"]:
            for prefix in [os.path.join(_base, "mlb_sim", "logs"), "mlb_sim/logs"]:
                p = os.path.join(prefix, log_name + ext)
                if os.path.exists(p):
                    try:
                        if ext == ".json":
                            import json as _json_hdr
                            with open(p) as _jf:
                                df = pd.DataFrame(_json_hdr.load(_jf))
                        else:
                            df = pd.read_parquet(p)
                    except Exception:
                        pass
                    if df is not None and len(df) > 0:
                        break
            if df is not None and len(df) > 0:
                break
        if df is None or len(df) == 0:
            continue
        try:
            resolved = df[df["resolved"] == 1]
            total_n += len(resolved)
            total_wins += int((resolved["result"] == "WIN").sum())
            # Pushes count as losses for display purposes
            total_losses += int((resolved["result"] == "LOSS").sum())
            total_losses += int((resolved["result"] == "PUSH").sum())
            # Net units: pushes already have net_units=0 in data, but display treats as -stake
            if "net_units" in resolved.columns and "stake_units" in resolved.columns:
                _net = 0.0
                for _, _row in resolved.iterrows():
                    if _row.get("result") == "PUSH":
                        _net -= float(_row.get("stake_units", 0))
                    else:
                        _net += float(_row.get("net_units", 0))
                total_net += _net
            elif "net_units" in resolved.columns:
                total_net += float(resolved["net_units"].sum())
        except Exception:
            pass

    decided = total_wins + total_losses
    win_pct = total_wins / decided * 100 if decided > 0 else None
    wagered = total_n
    roi = total_net / wagered * 100 if wagered > 0 else None

    if total_n == 0:
        st.html(
            '<div class="season-banner">'
            '<div style="color:#94a3b8;font-size:0.88em;padding:8px 0">'
            'Season underway \u2014 tracking from March 25, 2026</div>'
            '</div>'
        )
        return

    record_num = f"{total_wins}\u2013{total_losses}"
    pct_cls = _pct_color(win_pct)
    pct_display = f"{win_pct:.1f}%" if win_pct is not None else "\u2014"
    roi_display = f"{roi:+.1f}%" if roi is not None else "\u2014"
    units_display = f"{total_net:+.2f}"
    roi_cls = "green" if (roi or 0) >= 0 else "red"

    st.html(f"""
    <div class="season-banner">
      <div class="stat-grid">
        <div class="stat-block">
          <div class="num {pct_cls}">{record_num}</div>
          <div class="lbl">Record (all signals)</div>
        </div>
        <div class="stat-block">
          <div class="num {pct_cls}">{pct_display}</div>
          <div class="lbl">Win %</div>
        </div>
        <div class="stat-block">
          <div class="num {roi_cls}">{roi_display}</div>
          <div class="lbl">ROI</div>
        </div>
        <div class="stat-block">
          <div class="num {roi_cls}">{units_display}</div>
          <div class="lbl">Net Units</div>
        </div>
        <div class="stat-block">
          <div class="num">{total_n}</div>
          <div class="lbl">Signals</div>
        </div>
        <div class="stat-block">
          <div class="num">{total_pushes}</div>
          <div class="lbl">Pushes</div>
        </div>
      </div>
    </div>""")


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


def _line_movement_html(current_line, open_total, signal_direction=None):
    """Render a small line-movement indicator (↑0.5 / ↓0.5).

    Args:
        current_line: the displayed line (HR override if active, else API line)
        open_total: the 2 AM opening snapshot line (None if unavailable)
        signal_direction: "UNDER", "OVER", or None — determines green vs grey coloring

    Returns HTML string or "" if no movement or data missing.
    """
    if open_total is None or current_line is None:
        return ""
    try:
        mv = round(float(current_line) - float(open_total), 1)
    except (TypeError, ValueError):
        return ""
    if mv == 0:
        return ""
    arrow = "\u2191" if mv > 0 else "\u2193"  # ↑ or ↓
    # Determine if movement is favorable
    sd = (signal_direction or "").upper()
    if sd == "UNDER":
        favorable = mv < 0  # line dropped = good for under
    elif sd == "OVER":
        favorable = mv > 0  # line rose = good for over
    else:
        favorable = False
    color = "#22c55e" if favorable else "#6b7280"  # green or grey
    return (f' <span style="font-size:0.78em;color:{color};font-weight:500">'
            f'{arrow}{abs(mv):.1f}</span>')


def _proj_row_html(proj: dict, fe: dict, f5e: dict, sim_info: dict = None) -> str:
    full    = proj["proj_total_full"]
    line    = fe.get("consensus")
    conf    = proj["confidence"]

    parts = [
        f'<span class="proj-label">Proj</span> <span class="proj-val">{full:.1f}</span>',
    ]
    if line is not None:
        parts.append(
            f'<span class="proj-label">Line</span> <span class="proj-val">{line:.1f}</span>'
        )

    # Show V1 sim signal info instead of raw edge
    if sim_info and sim_info.get("p_under"):
        pu = sim_info["p_under"]
        stake = sim_info.get("stake", "?")
        cls = "edge-neg"  # blue for under
        parts.append(
            f'<span class="proj-label">p_under</span> '
            f'<span class="{cls}">{pu*100:.1f}%</span> '
            f'<span class="proj-label">{stake}u UNDER</span>'
        )
        if sim_info.get("s12_active"):
            parts.append(
                f'<span style="color:#a78bfa;font-size:0.85em">S12 overlay</span>'
            )
    elif line is None:
        parts.append('<span class="proj-label">No line yet</span>')

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


# ── Shadow signal badge helpers ──────────────────────────────────────────

_hr_override_cache = {}

def _load_hr_overrides(game_date):
    """Load HR line overrides for a date. Returns dict: (game_id, market) → hr_line."""
    if game_date in _hr_override_cache:
        return _hr_override_cache[game_date]
    try:
        from mlb_sim.pipeline.line_overrides import get_all_overrides_for_date
        result = get_all_overrides_for_date(game_date)
    except Exception:
        result = {}
    _hr_override_cache[game_date] = result
    return result


_shadow_cache = {}

def _load_shadow_flags(game_date):
    """Load CS013 and ST02 shadow flags for a date. Returns dict: game_id → flags."""
    cache_key = game_date
    if cache_key in _shadow_cache:
        return _shadow_cache[cache_key]

    flags = {}  # game_id → {"st02": bool, "cs013": bool, "signal_tier": str|None, "cs028": bool, "cs028_cs013_both": bool}
    season = game_date[:4]

    try:
        import json as _json_sh
        # ST02 from shadow_signals
        for _p in [f"mlb_sim/logs/shadow_signals_{season}.json",
                    os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                 "mlb_sim", "logs", f"shadow_signals_{season}.json")]:
            if os.path.exists(_p):
                with open(_p) as _f:
                    for r in _json_sh.load(_f):
                        if r.get("date") == game_date and r.get("signal_name", "").startswith("ST02"):
                            gid = r.get("game_id")
                            flags.setdefault(gid, {"st02": False, "cs013": False, "signal_tier": None})
                            flags[gid]["st02"] = bool(r.get("favorable_zone_flag"))
                break

        # CS013 from cs013_shadow
        for _p in [f"mlb_sim/logs/cs013_shadow_{season}.json",
                    os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                 "mlb_sim", "logs", f"cs013_shadow_{season}.json")]:
            if os.path.exists(_p):
                with open(_p) as _f:
                    for r in _json_sh.load(_f):
                        if r.get("date") == game_date:
                            gid = r.get("game_id")
                            # Skip if insufficient history (null flag)
                            if r.get("cs013_status") == "INSUFFICIENT_2026_HISTORY":
                                continue
                            if r.get("cs013_flag") is None:
                                continue
                            flags.setdefault(gid, {"st02": False, "cs013": False, "signal_tier": None})
                            flags[gid]["cs013"] = bool(r.get("cs013_flag"))
                            flags[gid]["signal_tier"] = r.get("signal_tier")
                break

        # CS028 from cs028_shadow
        for _p in [f"mlb_sim/logs/cs028_shadow_{season}.json",
                    os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                 "mlb_sim", "logs", f"cs028_shadow_{season}.json")]:
            if os.path.exists(_p):
                with open(_p) as _f:
                    for r in _json_sh.load(_f):
                        if r.get("game_date") == game_date and r.get("signal_fires"):
                            gid = r.get("game_id")
                            flags.setdefault(gid, {"st02": False, "cs013": False, "signal_tier": None,
                                                    "cs028": False, "cs028_cs013_both": False})
                            flags[gid]["cs028"] = True
                            flags[gid]["cs028_cs013_both"] = bool(r.get("cs013_also_active"))
                break

        # KP04 from kp04_shadow
        for _p in [f"mlb_sim/logs/kp04_shadow_{season}.json",
                    os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                 "mlb_sim", "logs", f"kp04_shadow_{season}.json")]:
            if os.path.exists(_p):
                with open(_p) as _f:
                    for r in _json_sh.load(_f):
                        if r.get("date") == game_date and r.get("kp04_flag"):
                            gid = str(r.get("game_id"))
                            flags.setdefault(gid, {"st02": False, "cs013": False, "signal_tier": None,
                                                    "cs028": False, "cs028_cs013_both": False, "kp04": False})
                            flags[gid]["kp04"] = True
                break

        # Team Totals from team_total_shadow — join by game_pk
        for _p in [f"mlb_sim/logs/team_total_shadow_{season}.json",
                    os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                 "mlb_sim", "logs", f"team_total_shadow_{season}.json")]:
            if os.path.exists(_p):
                with open(_p) as _f:
                    for r in _json_sh.load(_f):
                        if r.get("date") == game_date and r.get("game_pk"):
                            gpk = str(r["game_pk"])
                            flags.setdefault(gpk, {"st02": False, "cs013": False,
                                                    "signal_tier": None, "cs028": False,
                                                    "cs028_cs013_both": False, "kp04": False})
                            flags[gpk]["tt_under_h"] = bool(r.get("home_tt_under_flag"))
                            flags[gpk]["tt_under_a"] = bool(r.get("away_tt_under_flag"))
                            flags[gpk]["tt_over_h"] = bool(r.get("home_tt_over_flag"))
                            flags[gpk]["tt_posted_h"] = r.get("posted_home_total")
                            flags[gpk]["tt_posted_a"] = r.get("posted_away_total")
                            flags[gpk]["tt_gap_h"] = r.get("gap_home")
                            flags[gpk]["tt_gap_a"] = r.get("gap_away")
                break
    except Exception:
        pass

    _shadow_cache[cache_key] = flags
    return flags


def _shadow_badge_html(game_pk, game_date):
    """Return shadow badge HTML for a game. Empty string if no flags fire.

    Badge priority (strictly enforced — only highest applies):
      1. ST02 + CS013 conflict badge (regardless of tier)
      2. CS013 Tier 1 (HIGH) — red badge
      3. CS013 Tier 2 (LOW) — yellow badge
      4. No badge (CS013=FALSE or signal_tier=null)
    """
    flags = _load_shadow_flags(game_date)
    f = flags.get(game_pk, {})
    st02 = f.get("st02", False)
    cs013 = f.get("cs013", False)
    tier = f.get("signal_tier")

    if st02 and cs013:
        return ('<div style="font-size:0.70em;color:#f59e0b;margin-top:4px;'
                'padding:3px 6px;background:#292524;border-radius:4px;display:inline-block">'
                '\u26a0\ufe0f ST02 + CS013 \u2014 Conflicting signals: road fatigue (UNDER) '
                'vs bullpen deterioration (OVER). Monitor closely.'
                '<span style="color:#78716c;font-size:0.9em"> SHADOW</span></div>')
    elif st02:
        return ('<div style="font-size:0.70em;color:#60a5fa;margin-top:4px;'
                'padding:2px 6px;background:#1e293b;border-radius:4px;display:inline-block">'
                '\U0001f535 ST02 Shadow \u2014 Road fatigue signal active'
                '<span style="color:#475569;font-size:0.9em"> SHADOW</span></div>')
    elif cs013 and tier == "HIGH":
        return ('<div style="font-size:0.70em;color:#f87171;margin-top:4px;'
                'padding:2px 6px;background:#292524;border-radius:4px;display:inline-block">'
                '\U0001f534 CS013 Tier 1 \u2014 Bullpen deterioration + acceleration active'
                '<span style="color:#78716c;font-size:0.9em"> SHADOW</span></div>')
    elif cs013 and tier == "LOW":
        return ('<div style="font-size:0.70em;color:#fbbf24;margin-top:4px;'
                'padding:2px 6px;background:#292524;border-radius:4px;display:inline-block">'
                '\U0001f7e1 CS013 Tier 2 \u2014 Bullpen state deterioration active'
                '<span style="color:#78716c;font-size:0.9em"> SHADOW</span></div>')
    elif cs013:
        # CS013 fires but tier is null (insufficient CS020 data) — no tier badge
        return ('<div style="font-size:0.70em;color:#fbbf24;margin-top:4px;'
                'padding:2px 6px;background:#292524;border-radius:4px;display:inline-block">'
                '\U0001f7e1 CS013 Shadow \u2014 Bullpen state deterioration active'
                '<span style="color:#78716c;font-size:0.9em"> SHADOW</span></div>')

    # CS028: Bayesian bullpen blowup (independent of CS013 tier logic)
    cs028 = f.get("cs028", False)
    if cs028:
        cs028_cs013 = f.get("cs028_cs013_both", False)
        overlap_note = (' <span style="color:#fbbf24;font-size:0.9em">'
                        'CS028+CS013 both active</span>') if cs028_cs013 else ''
        return ('<div style="font-size:0.70em;color:#f87171;margin-top:4px;'
                'padding:2px 6px;background:#292524;border-radius:4px;display:inline-block">'
                '\U0001f534 CS028 bullpen blowup shadow'
                + overlap_note +
                '<span style="color:#78716c;font-size:0.9em"> SHADOW</span></div>')
    return ""


def _render_card(b: dict, signals: list = None, has_partial: bool = False) -> None:
    """Render a unified game card with all signals consolidated.
    signals: list of dicts, each with type/stake/s12_active/side etc.
    has_partial: True if F5/RL signal exists but no V1 (borderline game)."""
    game    = b["game"]
    proj    = b["proj"]
    fe      = b.get("full_edge", {})
    summary = b.get("summary", "")
    f       = proj.get("factors", {})
    lean    = proj.get("lean", "NEUTRAL")

    matchup = f'{game["away_team"]} @ {game["home_team"]}'
    full_proj = proj["proj_total_full"]
    line = fe.get("consensus")

    gtime = game.get("game_time", "")
    gtime_et = game.get("game_time_et", "")
    time_str = gtime_et if gtime_et else gtime

    # Weather
    temp = f.get("temperature_f")
    wind_mph = f.get("wind_speed_mph") or 0.0
    wind_raw = f.get("wind_desc") or ""
    is_dome = "dome" in wind_raw.lower()
    wx_parts = []
    if temp is not None:
        wx_parts.append(f"{temp:.0f}\u00b0F")
    if not is_dome and wind_mph >= 5:
        wd = wind_raw.replace("Blowing ", "").replace("blowing ", "")
        wx_parts.append(f"{wind_mph:.0f}mph wind {wd}")
    wx_line = " \u00b7 ".join(wx_parts) if wx_parts else ""

    if signals:
        # ── PLAY CARD: unified with all signal badges ──
        _stake_colors = {0.5: "#f59e0b", 0.62: "#f97316", 0.625: "#f97316",
                         1.0: "#06b6d4", 1.25: "#22c55e"}

        # Header: matchup + time + weather (line shown in bet rows, not header)
        header_parts = [f'{matchup} \u2014 {time_str}']
        if wx_line:
            header_parts.append(wx_line)
        l1 = (f'<div style="font-size:0.92em;font-weight:700;color:#e2e8f0">'
              f'{" \u00b7 ".join(header_parts)}</div>')

        # Signal badges
        badges = ""
        has_s12 = False
        for sig in signals:
            stype = sig.get("type", "v1")
            stake = sig.get("stake", "?")
            sc = _stake_colors.get(round(float(stake), 2) if stake != "?" else 0, "#67e8f9")
            _stake_display = f"{float(stake):.2f}".rstrip('0').rstrip('.') if stake != "?" else "?"

            # Right-aligned line reference per bet type (HR override in green if present)
            _right_line = ""
            _gpk_sig = str(game.get("game_pk", ""))
            _gdate_sig = game.get("game_date", "")
            _hr_ov = _load_hr_overrides(_gdate_sig)
            if stype == "v1" and line is not None:
                _hr_fg = _hr_ov.get((_gpk_sig, "full_game"))
                _display_ln = float(_hr_fg) if _hr_fg is not None else float(line)
                _ln_color = "#4ade80" if _hr_fg is not None else "#94a3b8"
                _lm_html = _line_movement_html(_display_ln, sig.get("open_line"), "UNDER")
                _right_line = f'<span style="font-size:0.82em;color:{_ln_color};font-weight:400">O/U {_display_ln:.1f}{_lm_html}</span>'
            elif stype in ("f5_under", "f5_over"):
                _f5_ln = sig.get("f5_line")
                if _f5_ln is not None:
                    _hr_f5 = _hr_ov.get((_gpk_sig, "f5_total"))
                    _display_f5 = float(_hr_f5) if _hr_f5 is not None else float(_f5_ln)
                    _f5_color = "#4ade80" if _hr_f5 is not None else "#94a3b8"
                    _f5_dir = "UNDER" if stype == "f5_under" else "OVER"
                    _lm_f5 = _line_movement_html(_display_f5, sig.get("open_line"), _f5_dir)
                    _right_line = f'<span style="font-size:0.82em;color:{_f5_color};font-weight:400">O/U {_display_f5:.1f}{_lm_f5}</span>'
            elif stype == "f5_rl":
                _right_line = f'<span style="font-size:0.82em;color:#94a3b8;font-weight:400">-0.5</span>'

            _row_style = 'display:flex;justify-content:space-between;align-items:baseline;margin-top:4px'

            if stype == "v1":
                badges += (f'<div style="{_row_style}">'
                           f'<span style="font-size:1.05em;font-weight:700;color:{sc}">'
                           f'Full Game Total UNDER \u00b7 {_stake_display}u</span>'
                           f'{_right_line}</div>')
                if sig.get("s12_active"):
                    has_s12 = True
            elif stype == "f5_under":
                badges += (f'<div style="{_row_style}">'
                           f'<span style="font-size:0.95em;font-weight:700;color:#67e8f9">'
                           f'F5 Total UNDER \u00b7 {_stake_display}u</span>'
                           f'{_right_line}</div>')
            elif stype == "f5_over":
                badges += (f'<div style="{_row_style}">'
                           f'<span style="font-size:0.95em;font-weight:700;color:#fbbf24">'
                           f'F5 Total OVER \u00b7 {_stake_display}u</span>'
                           f'{_right_line}</div>')
            elif stype == "f5_rl":
                badges += (f'<div style="{_row_style}">'
                           f'<span style="font-size:0.95em;font-weight:700;color:#a78bfa">'
                           f'F5 Run Line HOME -0.5 \u00b7 {_stake_display}u</span>'
                           f'{_right_line}</div>')

        # Check for P09 and ST02 overlays from V1 signal data
        _has_p09 = any(s.get("p09_active") for s in signals if s.get("type") == "v1")
        _has_st02 = any(s.get("st02_active") for s in signals if s.get("type") == "v1")

        # Per-game modifier pills (green = active overlay, yellow = shadow signal)
        _mpill = lambda label, color, bg: (
            f'<span style="background:{bg};color:{color};border:1px solid {color};'
            f'border-radius:10px;padding:1px 7px;font-size:0.68em;font-weight:600;'
            f'margin-right:3px">{label}</span>')
        _mod_pills = ""
        _green_mods = []
        _yellow_mods = []
        if has_s12:
            _green_mods.append(_mpill("S12", "#22c55e", "#052e16"))
        if _has_p09:
            _green_mods.append(_mpill("P09", "#22c55e", "#052e16"))

        # Shadow signals from per-game log data
        _gpk_sh = str(game.get("game_pk", ""))
        _gdate_sh = game.get("game_date", "")
        _sh_flags = _load_shadow_flags(_gdate_sh).get(_gpk_sh, {})
        if _sh_flags.get("cs013"):
            _yellow_mods.append(_mpill("CS013", "#eab308", "#1c1400"))
        if _sh_flags.get("cs028"):
            _yellow_mods.append(_mpill("CS028", "#eab308", "#1c1400"))
        if _sh_flags.get("kp04"):
            _yellow_mods.append(_mpill("KP04", "#eab308", "#1c1400"))
        if _has_st02:
            _yellow_mods.append(_mpill("ST02", "#eab308", "#1c1400"))

        # Team Total pills — join by game_pk (clean canonical key)
        if _sh_flags.get("tt_under_h"):
            _tt_ph = _sh_flags.get("tt_posted_h", "")
            _tt_gh = _sh_flags.get("tt_gap_h")
            _tt_detail = f" {_tt_ph}" if _tt_ph else ""
            _tt_gap_s = f" ({_tt_gh:+.1f})" if _tt_gh is not None else ""
            _yellow_mods.append(_mpill(f"TT\u2193H{_tt_detail}{_tt_gap_s}", "#60a5fa", "#172554"))
        if _sh_flags.get("tt_under_a"):
            _tt_pa = _sh_flags.get("tt_posted_a", "")
            _tt_ga = _sh_flags.get("tt_gap_a")
            _tt_detail = f" {_tt_pa}" if _tt_pa else ""
            _tt_gap_s = f" ({_tt_ga:+.1f})" if _tt_ga is not None else ""
            _yellow_mods.append(_mpill(f"TT\u2193A{_tt_detail}{_tt_gap_s}", "#60a5fa", "#172554"))
        if _sh_flags.get("tt_over_h"):
            _tt_ph = _sh_flags.get("tt_posted_h", "")
            _tt_gh = _sh_flags.get("tt_gap_h")
            _tt_detail = f" {_tt_ph}" if _tt_ph else ""
            _tt_gap_s = f" ({_tt_gh:+.1f})" if _tt_gh is not None else ""
            _yellow_mods.append(_mpill(f"TT\u2191H{_tt_detail}{_tt_gap_s}", "#eab308", "#1c1400"))

        if _green_mods or _yellow_mods:
            _mod_pills = ('<div style="margin-top:4px;margin-bottom:2px;line-height:1.8">'
                          + "".join(_green_mods) + "".join(_yellow_mods) + '</div>')
        boost = _mod_pills

        # FIX 1: Conversational explanation from signal composition
        _types = [s.get("type", "") for s in signals]
        _has_v1 = "v1" in _types
        _has_f5u = "f5_under" in _types
        _has_f5o = "f5_over" in _types
        _has_rl = "f5_rl" in _types
        _n_sigs = len(signals)

        # Weather context snippet
        _wx_note = ""
        if temp is not None and temp < 55:
            _wx_note = " Cold weather helps suppress scoring."
        elif not is_dome and wind_mph >= 10 and "in" in wind_raw.lower():
            _wx_note = " Wind blowing in adds to the suppressed run environment."
        elif not is_dome and wind_mph >= 10 and "out" in wind_raw.lower():
            _wx_note = " Wind blowing out is a factor, but pitching quality overrides."

        if _n_sigs >= 3:
            _explain = ("Three signals all pointing the same way \u2014 full game under, "
                        "first five under, and the home starter has a significant edge on the mound. "
                        "Strongest conviction play of the day.")
        elif _has_v1 and (_has_f5u or _has_f5o):
            _explain = ("Full game and first five innings both pointing the same direction. "
                        "Two independent signals lining up adds weight to this one." + _wx_note)
        elif _has_v1 and has_s12:
            _explain = ("Elite pitching environment on both sides \u2014 both starters are in peak "
                        "command form. The extra bump in unit size reflects that added conviction." + _wx_note)
        elif _has_v1:
            _explain = ("Strong pitching matchup with conditions favoring the under." + _wx_note
                        if _wx_note else
                        "Pitching quality on both sides favors a lower-scoring game than the market expects.")
        elif _has_f5u or _has_f5o:
            _explain = "First five innings signal only \u2014 starter-driven edge before bullpens enter."
        elif _has_rl:
            _explain = "Home starter has a significant quality edge \u2014 run line value on the first five innings."
        else:
            _explain = "Signal fired based on pitching matchup analysis."

        explain_html = (f'<div style="font-size:0.80em;color:#94a3b8;margin-top:6px;line-height:1.4">'
                        f'{_explain}</div>')

        # Line movement narrative (appended to explanation if available)
        _move_html = ""
        try:
            from mlb_sim.pipeline.line_snapshot_store import compute_movement
            _gk_str = str(game.get("game_pk", ""))
            # Try Odds API game_id from signal data
            _odds_gid = None
            for _sig in signals:
                if _sig.get("odds_game_id"):
                    _odds_gid = _sig["odds_game_id"]
                    break
            _move_data = compute_movement(_odds_gid or _gk_str)
            if _move_data and _move_data.get("movement_summary"):
                _move_html = (f'<div style="font-size:0.78em;color:#64748b;margin-top:3px;font-style:italic">'
                              f'{_move_data["movement_summary"]}</div>')
        except Exception:
            pass

        disclaimer = ('<div style="font-size:0.68em;color:#4b5563;margin-top:6px;font-style:italic">'
                      'Check your book for current line before placing.</div>')

        # Scratch detection badges
        _scratch_html = ""
        for _sig in signals:
            if _sig.get("scratch_voided"):
                _old_sp = _sig.get("original_home_sp") or _sig.get("original_away_sp") or ""
                _new_sp = _sig.get("replacement_home_sp") or _sig.get("replacement_away_sp") or ""
                _scratch_html = (
                    f'<div style="background:#2d1515;border:1px solid #dc2626;border-radius:4px;'
                    f'padding:5px 10px;margin-top:6px;font-size:0.78em;color:#f87171;font-weight:600">'
                    f'\u26a0\ufe0f Voided \u2014 pitcher scratch ({_old_sp} \u2192 {_new_sp})</div>')
                break
            elif _sig.get("scratch_detected"):
                _old_sp = _sig.get("original_home_sp") or _sig.get("original_away_sp") or ""
                _new_sp = _sig.get("replacement_home_sp") or _sig.get("replacement_away_sp") or ""
                _scratch_html = (
                    f'<div style="background:#1c1400;border:1px solid #f59e0b;border-radius:4px;'
                    f'padding:5px 10px;margin-top:6px;font-size:0.78em;color:#fbbf24;font-weight:600">'
                    f'\U0001f504 Updated \u2014 pitcher scratch ({_old_sp} \u2192 {_new_sp})</div>')
                break

        _shadow_html = _shadow_badge_html(game.get("game_pk"), game.get("game_date", ""))

        _border_color = "#dc2626" if any(s.get("scratch_voided") for s in signals) else (
            "#ef4444" if has_partial else "#22c55e")
        st.html(
            f'<div class="game-card" style="border-left:3px solid {_border_color}">'
            f'{l1}{badges}{boost}{explain_html}{_move_html}{_scratch_html}{_shadow_html}{disclaimer}'
            f'</div>'
        )

        # ── Hard Rock line override (play cards only) ──
        _gpk = str(game.get("game_pk", ""))
        _card_suffix = "_shadow" if has_partial else ""
        _gdate = game.get("game_date", "")
        _hr_overrides = _load_hr_overrides(_gdate)
        _hr_markets = []
        if line is not None:
            _hr_markets.append(("full_game", "Full Game", line))
        for _sig in (signals or []):
            if _sig.get("type") in ("f5_under", "f5_over") and _sig.get("f5_line") is not None:
                _hr_markets.append(("f5_total", "F5 Total", float(_sig["f5_line"])))
                break
        if _hr_markets:
            _existing = {m: _hr_overrides.get((_gpk, m)) for m, _, _ in _hr_markets}
            _any_set = any(v is not None for v in _existing.values())
            # Show badges for existing overrides
            if _any_set:
                _hr_badge_parts = []
                for mkt, label, api_ln in _hr_markets:
                    hr_val = _existing.get(mkt)
                    if hr_val is not None:
                        _hr_badge_parts.append(f'{label}: HR {hr_val:.1f} (API {api_ln:.1f})')
                st.html(f'<div style="font-size:0.68em;color:#a78bfa;margin-top:-4px;margin-bottom:4px">'
                        f'\U0001f7e3 {" | ".join(_hr_badge_parts)}</div>')
            # Expander for editing
            with st.expander(f"\u270f\ufe0f HR line override — {matchup}", expanded=False):
                _cols = st.columns(len(_hr_markets) + 1)
                for i, (mkt, label, api_ln) in enumerate(_hr_markets):
                    _key = f"hr_{_gpk}_{mkt}{_card_suffix}"
                    _default = _existing.get(mkt)
                    _cols[i].number_input(
                        f"{label} (API: {api_ln:.1f})",
                        min_value=0.0, max_value=30.0, step=0.5,
                        value=_default if _default else api_ln,
                        key=_key,
                    )
                if _cols[-1].button("Save", key=f"hr_save_{_gpk}{_card_suffix}"):
                    from mlb_sim.pipeline.line_overrides import save_override
                    for mkt, label, api_ln in _hr_markets:
                        _key = f"hr_{_gpk}_{mkt}{_card_suffix}"
                        _val = st.session_state.get(_key)
                        if _val is not None and abs(_val - api_ln) > 0.01:
                            save_override(_gpk, _gdate, mkt, api_ln, _val)
                    st.rerun()

    else:
        # ── NO-PLAY CARD (context only) ──
        # No directional label on non-play cards (removed legacy OVER/UNDER lean)

        line_str = f" | Line: {line:.1f}" if line is not None else ""
        proj_line = f'Proj: {full_proj:.1f}{line_str}'

        # FIX 2: Explain why no signal
        if has_partial:
            _reason = ('<div style="font-size:0.75em;color:#6b7280;margin-top:4px;font-style:italic">'
                       'Secondary signal only \u2014 not enough conviction for a full play.</div>')
        else:
            _reason = ('<div style="font-size:0.75em;color:#6b7280;margin-top:4px;font-style:italic">'
                       'No signals \u2014 outside threshold on all models.</div>')

        _shadow_html_np = _shadow_badge_html(game.get("game_pk"), game.get("game_date", ""))

        # TT pills on no-play cards — same logic as play cards
        _npill = lambda label, color, bg: (
            f'<span style="background:{bg};color:{color};border:1px solid {color};'
            f'border-radius:10px;padding:1px 7px;font-size:0.68em;font-weight:600;'
            f'margin-right:3px">{label}</span>')
        _np_tt_pills = ""
        _gpk_np = str(game.get("game_pk", ""))
        _gdate_np = game.get("game_date", "")
        _np_sh = _load_shadow_flags(_gdate_np).get(_gpk_np, {})
        _np_tt_parts = []
        if _np_sh.get("tt_under_h"):
            _ph = _np_sh.get("tt_posted_h", "")
            _gh = _np_sh.get("tt_gap_h")
            _np_tt_parts.append(_npill(f"TT\u2193H {_ph} ({_gh:+.1f})" if _gh is not None else f"TT\u2193H {_ph}", "#60a5fa", "#172554"))
        if _np_sh.get("tt_under_a"):
            _pa = _np_sh.get("tt_posted_a", "")
            _ga = _np_sh.get("tt_gap_a")
            _np_tt_parts.append(_npill(f"TT\u2193A {_pa} ({_ga:+.1f})" if _ga is not None else f"TT\u2193A {_pa}", "#60a5fa", "#172554"))
        if _np_sh.get("tt_over_h"):
            _ph = _np_sh.get("tt_posted_h", "")
            _gh = _np_sh.get("tt_gap_h")
            _np_tt_parts.append(_npill(f"TT\u2191H {_ph} ({_gh:+.1f})" if _gh is not None else f"TT\u2191H {_ph}", "#eab308", "#1c1400"))
        if _np_tt_parts:
            _np_tt_pills = '<div style="margin-top:4px;line-height:1.8">' + "".join(_np_tt_parts) + '</div>'
            _np_border_override = "#1e3a5f"  # blue border for TT-only cards
        else:
            _np_border_override = None

        _np_border = _np_border_override if _np_border_override else ("#ef4444" if has_partial else "#374151")
        st.html(
            f'<div class="game-card" style="border-left:3px solid {_np_border}">'
            f'<div style="font-size:0.88em;font-weight:700;color:#e2e8f0">'
            f'{matchup} \u2014 {time_str}</div>'
            f'<div style="font-size:0.75em;color:#6b7280;margin-top:2px">'
            f'{wx_line}{" \u00b7 " if wx_line else ""}{proj_line}</div>'
            f'<div class="card-summary">{summary}</div>'
            f'{_np_tt_pills}{_reason}{_shadow_html_np}'
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


def _nhl_conf_badge(conf: str, stake: float = 0.75) -> str:
    c = (conf or "MEDIUM").upper()
    return f'<span class="conf-badge conf-{c}">{c.lower()} \u00b7 {stake}u</span>'


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


_nhl_hr_cache = {}

def _load_nhl_hr_overrides(game_date):
    """Load NHL HR line overrides for a date. Returns dict: game_id → hr_line."""
    if game_date in _nhl_hr_cache:
        return _nhl_hr_cache[game_date]
    result = {}
    try:
        import json as _j
        _p = os.path.join(os.path.dirname(__file__), "nhl", "data", "nhl_line_overrides_2026.json")
        if os.path.exists(_p):
            for o in _j.load(open(_p)):
                if o.get("date") == game_date:
                    result[str(o["game_id"])] = float(o["hard_rock_line"])
    except Exception:
        pass
    _nhl_hr_cache[game_date] = result
    return result

def _save_nhl_hr_override(game_id, date_str, api_line, hr_line):
    """Save an NHL HR line override."""
    import json as _j
    from datetime import datetime as _dt
    _p = os.path.join(os.path.dirname(__file__), "nhl", "data", "nhl_line_overrides_2026.json")
    os.makedirs(os.path.dirname(_p), exist_ok=True)
    overrides = []
    if os.path.exists(_p):
        try:
            overrides = _j.load(open(_p))
        except Exception:
            overrides = []
    overrides = [o for o in overrides if str(o.get("game_id")) != str(game_id)]
    overrides.append({
        "game_id": str(game_id), "date": date_str, "market": "full_game",
        "odds_api_line": api_line, "hard_rock_line": hr_line,
        "entered_at": _dt.now().isoformat(),
    })
    with open(_p, "w") as f:
        _j.dump(overrides, f, indent=2)
    _nhl_hr_cache.pop(date_str, None)


# ── Shared universal card / pill helpers ──────────────────────────────────────

def _render_game_card_universal(
    matchup: str,
    time_str: str,
    tier: str,  # "ACTIVE", "SHADOW", "NONE"
    pills: list[str],  # list of pre-rendered pill HTML strings
    stats: list[str],  # list of "Label: Value" stat strings
    explanation: str = "",
    extra_html: str = "",  # goalie row, weather, etc.
    disclaimer: str = "",
) -> None:
    """Universal game card — one function, every sport, every tier."""
    border_colors = {"ACTIVE": "#16a34a", "SHADOW": "#dc2626", "NONE": "#6b7280"}
    border = border_colors.get(tier, "#6b7280")

    sep = ' <span style="color:#2d3748;margin:0 2px">&middot;</span> '

    # Header
    header = (f'<div style="font-size:0.92em;font-weight:700;color:#e2e8f0">'
              f'{matchup} &mdash; {time_str}</div>')

    # Stats row
    stats_html = ""
    if stats:
        parts = [f'<span style="color:#94a3b8;font-size:0.75em">{s.split(":")[0]}:</span> '
                 f'<span style="color:#e2e8f0;font-size:0.82em;font-weight:600">{s.split(":",1)[1].strip()}</span>'
                 for s in stats if ":" in s]
        stats_html = f'<div style="margin-top:3px">{sep.join(parts)}</div>'

    # Pills row
    pill_html = ""
    if pills:
        pill_html = '<div style="margin-top:4px;line-height:1.8">' + "".join(pills) + '</div>'

    # Explanation
    explain_html = ""
    if explanation:
        explain_html = (f'<div style="font-size:0.75em;color:#6b7280;margin-top:4px;font-style:italic">'
                       f'{explanation}</div>')

    # Shadow disclaimer
    disc_html = ""
    if tier == "SHADOW" and not disclaimer:
        disc_html = ('<div style="font-size:0.68em;color:#f87171;margin-top:4px">'
                    'Research signal &mdash; shadow tracking only, not a play recommendation.</div>')
    elif disclaimer:
        disc_html = f'<div style="font-size:0.68em;color:#94a3b8;margin-top:4px">{disclaimer}</div>'

    st.html(
        f'<div class="game-card" style="border-left:4px solid {border}">'
        f'{header}{stats_html}{pill_html}{extra_html}{explain_html}{disc_html}'
        f'</div>'
    )


def _universal_pill(label: str, color: str, bg: str) -> str:
    """Render a signal pill — standard style across all sports."""
    return (f'<span style="background:{bg};color:{color};border:1px solid {color};'
            f'border-radius:10px;padding:1px 7px;font-size:0.68em;font-weight:600;'
            f'margin-right:3px">{label}</span>')


def _render_nhl_signal_card(s: dict, game_date: str = "") -> None:
    """Render a single NHL signal card. HIGH = play, SHADOW = red-border shadow card."""
    home    = s.get("home_team", "")
    away    = s.get("away_team", "")
    side    = s.get("signal_side", "")
    edge    = s.get("edge")
    sim     = s.get("sim_prob")
    line    = s.get("closing_total")
    lam     = s.get("lambda_total_calibrated")
    tier    = s.get("confidence_tier", "MEDIUM")
    stake   = float(s.get("stake_units") or {"HIGH": 1.0, "MEDIUM": 0.75}.get(tier, 0.75))
    vol     = s.get("volatility_bucket", "low") or "low"
    caut    = int(s.get("caution_flag") or 0)
    summary = s.get("summary", "")

    conf_h  = bool(s.get("goalie_confirmed_home", True))
    conf_a  = bool(s.get("goalie_confirmed_away", True))
    back_h  = int(s.get("backup_flag_home") or 0)
    back_a  = int(s.get("backup_flag_away") or 0)
    b2b_gh  = int(s.get("home_goalie_b2b") or 0)
    b2b_ga  = int(s.get("away_goalie_b2b") or 0)

    is_shadow = tier.startswith("SHADOW_")
    is_play   = tier == "HIGH"
    conf_star = {"HIGH": "star3"}.get(tier, "noplay")
    card_cls  = f"game-card {conf_star}" if is_play else "game-card noplay"
    _border   = "#22c55e" if is_play else ("#dc2626" if is_shadow else "#374151")

    matchup   = f"{away} @ {home}"
    sep = ' <span style="color:#2d3748;margin:0 2px">·</span> '

    # Goalie TBD badge (display flag, not a gate)
    goalie_tbd = ""
    if is_play and (not conf_h or not conf_a):
        goalie_tbd = (' <span style="background:#1c1400;color:#eab308;border:1px solid #eab308;'
                      'border-radius:10px;padding:1px 7px;font-size:0.68em;font-weight:600">'
                      '\u26a0\ufe0f Goalies TBD</span>')

    # Shadow label for MEDIUM/LOW
    shadow_label = ""
    if is_shadow:
        shadow_label = (' <span style="background:#2d1515;color:#f87171;border:1px solid #dc2626;'
                        'border-radius:10px;padding:1px 7px;font-size:0.68em;font-weight:600">'
                        'SHADOW</span>')

    # Header: side badge | matchup | tier badge (with units)
    header = (
        f'<div class="card-header">'
        f'{_nhl_side_badge(side)}'
        f'<span class="matchup">{matchup}</span>'
        f'{_nhl_conf_badge(tier, stake)}{goalie_tbd}{shadow_label}'
        f'</div>'
    )

    # Stats row: Line | Edge (pp) | Model total | Vol
    edge_pp   = f"{edge * 100:+.1f}pp" if edge is not None else "\u2014"
    ecls      = "edge-pos" if (edge or 0) > 0 else "edge-neg"
    lam_str   = f"{lam:.1f}" if lam is not None else "\u2014"
    line_str  = str(line) if line is not None else "\u2014"
    _nhl_lm = _line_movement_html(line, s.get("open_total"), side) if line is not None else ""
    stats_parts = [
        f'<span class="proj-label">Line</span> <span class="proj-val">{line_str}{_nhl_lm}</span>',
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
            '\u26a0 6.5-line over \u2014 caution bucket: historically underpriced ~4pp for this model'
            '</div>'
        )

    st.html(
        f'<div class="{card_cls}" style="border-left:4px solid {_border}">'
        f'{header}'
        f'{stats_row}'
        f'{goalie_row}'
        f'{summary_html}'
        f'{caution_html}'
        f'</div>'
    )

    # ── Hard Rock line override ──
    if is_play and line is not None:
        _gid = str(s.get("game_id", ""))
        _nhl_hr = _load_nhl_hr_overrides(game_date)
        _hr_val = _nhl_hr.get(_gid)
        if _hr_val is not None:
            st.html(f'<div style="font-size:0.68em;color:#a78bfa;margin-top:-4px;margin-bottom:4px">'
                    f'\U0001f7e3 HR {_hr_val:.1f} (API {line})</div>')
        with st.expander(f"\u270f\ufe0f HR line override \u2014 {matchup}", expanded=False):
            _col1, _col2 = st.columns(2)
            _col1.number_input("Total (API: {:.1f})".format(line),
                               min_value=0.0, max_value=15.0, step=0.5,
                               value=_hr_val if _hr_val else line,
                               key=f"nhl_hr_{_gid}")
            if _col2.button("Save", key=f"nhl_hr_save_{_gid}"):
                _val = st.session_state.get(f"nhl_hr_{_gid}")
                if _val is not None and abs(_val - line) > 0.01:
                    _save_nhl_hr_override(_gid, game_date, line, _val)
                st.rerun()


def _render_nhl_tab() -> None:
    nhl = load_nhl_results()

    # Inject open_total from 2 AM snapshot into each signal for line movement display
    if nhl:
        try:
            _nhl_gdate = nhl.get("game_date", "")
            _nhl_open_path = os.path.join(os.path.dirname(__file__), "nhl", "data",
                                           f"nhl_lines_open_{_nhl_gdate.replace('-','_')}.json")
            if os.path.exists(_nhl_open_path):
                with open(_nhl_open_path) as _f:
                    _nhl_open_snaps = json.load(_f)
                _nhl_open_map = {}
                for _s in _nhl_open_snaps:
                    if _s.get("snapshot_type") == "open":
                        _nhl_open_map[(_s.get("home_team",""), _s.get("away_team",""))] = _s.get("total_line")
                for _sig_list in [nhl.get("today_signals", []), nhl.get("signals", [])]:
                    for _s in _sig_list:
                        _k = (_s.get("home_team",""), _s.get("away_team",""))
                        _s["open_total"] = _nhl_open_map.get(_k)
        except Exception:
            pass

    # ── (a) Header ────────────────────────────────────────────────────────────
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

    # ── Freshness stamp ───────────────────────────────────────────────────────
    last_updated   = nhl.get("last_updated", "")
    signals_source = nhl.get("signals_source", "")
    src_color      = "#22c55e" if signals_source == "live" else "#f59e0b"
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

    st.html(_pipeline_freshness("nhl"))

    today_signals  = nhl.get("today_signals", [])
    recent_results = nhl.get("recent_results", [])
    season_perf    = nhl.get("season_performance", {})
    ot_diag_nhl    = nhl.get("ot_diagnostics", {})
    _nhl_game_date = nhl.get("game_date", "")

    # ── Classify signals ──────────────────────────────────────────────────────
    plays    = [s for s in today_signals if s.get("confidence_tier") == "HIGH"]
    shadows  = [s for s in today_signals if s.get("confidence_tier", "").startswith("SHADOW_")]
    no_plays = [s for s in today_signals if s not in plays and s not in shadows]

    # ── (b) Signal status row ─────────────────────────────────────────────────
    n_active  = len(plays)
    n_shadow  = len(shadows)
    st.html(
        f'<div style="font-size:0.80em;color:#94a3b8;margin-bottom:10px">'
        f'Active: <strong style="color:#16a34a">{n_active} HIGH</strong>'
        f'&nbsp;&nbsp;|&nbsp;&nbsp;'
        f'Shadow: <strong style="color:#dc2626">{n_shadow} MEDIUM/LOW</strong>'
        f'</div>'
    )

    # ── (c) Season performance summary ────────────────────────────────────────
    if recent_results:
        W = sum(1 for r in recent_results if r.get("result") == "WIN")
        L = sum(1 for r in recent_results if r.get("result") == "LOSS")
        P = sum(1 for r in recent_results if r.get("result") == "PUSH")
        n = W + L + P
        hit = W / (W + L) if (W + L) > 0 else None
        roi = (W * (100.0 / 110.0) - L) / n * 100 if n > 0 else None

        hit_cls = "green" if (hit or 0) >= 0.525 else "yellow" if (hit or 0) >= 0.50 else "red"
        hit_str = f"{hit * 100:.1f}%" if hit is not None else "\u2014"
        roi_str = f"{roi:+.1f}%" if roi is not None else "\u2014"

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

    # ── Helper: build universal card for an NHL signal ────────────────────────
    def _nhl_universal_card(s: dict) -> None:
        home    = s.get("home_team", "")
        away    = s.get("away_team", "")
        side    = s.get("signal_side", "")
        edge    = s.get("edge")
        sim     = s.get("sim_prob")
        line    = s.get("closing_total")
        lam     = s.get("lambda_total_calibrated")
        tier    = s.get("confidence_tier", "MEDIUM")
        vol     = s.get("volatility_bucket", "low") or "low"
        summary = s.get("summary", "")

        conf_h  = bool(s.get("goalie_confirmed_home", True))
        conf_a  = bool(s.get("goalie_confirmed_away", True))
        back_h  = int(s.get("backup_flag_home") or 0)
        back_a  = int(s.get("backup_flag_away") or 0)
        b2b_gh  = int(s.get("home_goalie_b2b") or 0)
        b2b_ga  = int(s.get("away_goalie_b2b") or 0)

        is_shadow = tier.startswith("SHADOW_")
        is_play   = tier == "HIGH"
        card_tier = "ACTIVE" if is_play else ("SHADOW" if is_shadow else "NONE")

        # Build pills
        card_pills: list[str] = []
        if is_play:
            card_pills.append(_universal_pill("HIGH", "#fff", "#16a34a"))
            if not conf_h or not conf_a:
                card_pills.append(_universal_pill("\u26a0\ufe0f Goalies TBD", "#eab308", "#1c1400"))
        elif is_shadow:
            card_pills.append(_universal_pill("SHADOW", "#fff", "#dc2626"))
            inner_tier = tier.replace("SHADOW_", "")
            if inner_tier == "MEDIUM":
                card_pills.append(_universal_pill("MEDIUM", "#eab308", "#1c1400"))
            elif inner_tier == "LOW":
                card_pills.append(_universal_pill("LOW", "#64748b", "#0f172a"))
        else:
            card_pills.append(_universal_pill(tier, "#64748b", "#0f172a"))

        if side:
            side_color = "#22c55e" if side.upper() == "UNDER" else "#f87171"
            card_pills.append(_universal_pill(side.upper(), side_color, "#0f172a"))

        # Build stats
        edge_pp  = f"{edge * 100:+.1f}pp" if edge is not None else "\u2014"
        lam_str  = f"{lam:.1f}" if lam is not None else "\u2014"
        line_str = str(line) if line is not None else "\u2014"
        card_stats = [
            f"Line: {line_str}",
            f"Edge: {edge_pp}",
            f"Model: {lam_str}",
            f"Vol: {vol}",
        ]
        if sim is not None:
            card_stats.append(f"P({side.lower()}): {sim * 100:.0f}%")

        # Goalie status row (extra_html)
        gh_status = _nhl_goalie_status(conf_h, bool(back_h), bool(b2b_gh))
        ga_status = _nhl_goalie_status(conf_a, bool(back_a), bool(b2b_ga))
        goalie_row = (
            f'<div style="font-size:0.80em;color:#4a5568;margin-top:4px">'
            f'<strong style="color:#64748b">{home}</strong> {gh_status}'
            f'&nbsp;&nbsp;|&nbsp;&nbsp;'
            f'<strong style="color:#64748b">{away}</strong> {ga_status}'
            f'</div>'
        )

        # Caution banner for 6.5-line overs
        caut = int(s.get("caution_flag") or 0)
        caution_html = ""
        if caut:
            caution_html = (
                '<div style="background:#1c1400;border:1px solid #92400e;border-radius:4px;'
                'padding:5px 10px;margin-top:6px;font-size:0.78em;color:#fde68a">'
                '\u26a0 6.5-line over \u2014 caution bucket: historically underpriced ~4pp for this model'
                '</div>'
            )

        matchup = f"{away} @ {home}"
        _render_game_card_universal(
            matchup=matchup,
            time_str="",
            tier=card_tier,
            pills=card_pills,
            stats=card_stats,
            explanation=summary,
            extra_html=goalie_row + caution_html,
        )

        # ── Hard Rock line override (ACTIVE only) ──
        if is_play and line is not None:
            _gid = str(s.get("game_id", ""))
            _nhl_hr = _load_nhl_hr_overrides(_nhl_game_date)
            _hr_val = _nhl_hr.get(_gid)
            if _hr_val is not None:
                st.html(f'<div style="font-size:0.68em;color:#a78bfa;margin-top:-4px;margin-bottom:4px">'
                        f'\U0001f7e3 HR {_hr_val:.1f} (API {line})</div>')
            with st.expander(f"\u270f\ufe0f HR line override \u2014 {matchup}", expanded=False):
                _col1, _col2 = st.columns(2)
                _col1.number_input("Total (API: {:.1f})".format(line),
                                   min_value=0.0, max_value=15.0, step=0.5,
                                   value=_hr_val if _hr_val else line,
                                   key=f"nhl_hr_{_gid}")
                if _col2.button("Save", key=f"nhl_hr_save_{_gid}"):
                    _val = st.session_state.get(f"nhl_hr_{_gid}")
                    if _val is not None and abs(_val - line) > 0.01:
                        _save_nhl_hr_override(_gid, _nhl_game_date, line, _val)
                    st.rerun()

    # ── (d) Today's Plays (ACTIVE) ────────────────────────────────────────────
    _n_games = len(set((s.get("home_team","") + s.get("away_team","")) for s in plays)) if plays else 0
    st.html(f'<div class="section-hdr">\U0001f3af Today\'s Plays \u2014 '
            f'{_n_games} game{"s" if _n_games != 1 else ""} \u00b7 '
            f'{n_active} signal{"s" if n_active != 1 else ""}</div>')
    if plays:
        for s in plays:
            _nhl_universal_card(s)
    else:
        st.caption("No HIGH signals today.")

    # ── (e) Shadow Monitoring (collapsed) ─────────────────────────────────────
    if shadows:
        with st.expander(
            f"Shadow Monitoring \u2014 {len(shadows)} signal{'s' if len(shadows) != 1 else ''}",
            expanded=False
        ):
            for s in shadows:
                _nhl_universal_card(s)

    # ── (f) All Other Games (collapsed) ───────────────────────────────────────
    if no_plays:
        with st.expander(
            f"All Other Games \u2014 {len(no_plays)}",
            expanded=False
        ):
            for s in no_plays:
                _nhl_universal_card(s)

    # ── (g) Recent Results table ──────────────────────────────────────────────
    st.html('<div class="section-hdr">📋 Recent Results — Last 14 Days</div>')
    if recent_results:
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

            line_s   = str(line) if line is not None else "\u2014"
            edge_s   = f"{edge:+.3f}" if edge is not None else "\u2014"
            actual_s = str(int(actual)) if actual is not None else "\u2014"
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

    # ── Season Performance (historical) ───────────────────────────────────────
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
            hit_str = f"{hit * 100:.1f}%" if hit is not None else "\u2014"
            roi_str = f"{roi:+.2f}%" if roi is not None else "\u2014"
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
                    th_disp = f"{th * 100:.1f}%" if th is not None else "\u2014"
                    tr_disp = f"{tr:+.2f}%" if tr is not None else "\u2014"
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

    # ── (h) OT Diagnostics ────────────────────────────────────────────────────
    if ot_diag_nhl and ot_diag_nhl.get("total_graded", 0) > 0:
        ot_g    = ot_diag_nhl.get("ot_games", 0)
        so_g    = ot_diag_nhl.get("so_games", 0)
        total_g = ot_diag_nhl.get("total_graded", 1)
        ot_rt   = ot_diag_nhl.get("ot_rate")
        flips   = ot_diag_nhl.get("ot_flips", 0)
        frate   = ot_diag_nhl.get("ot_flip_rate")
        ul      = ot_diag_nhl.get("under_ot_losses", 0)
        ol      = ot_diag_nhl.get("over_ot_losses", 0)
        ot_rt_s = f"{ot_rt * 100:.1f}%" if ot_rt is not None else "\u2014"
        frate_s = f"{frate * 100:.1f}%" if frate is not None else "\u2014"
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

    # ── CLV Summary ───────────────────────────────────────────────────────────
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
            avg_clv_s = f"{avg_clv:+.2f}" if avg_clv is not None else "\u2014"
            pct_pos_s = f"{pct_pos:.0f}%" if pct_pos is not None else "\u2014"
            avg_color = "#22c55e" if (avg_clv or 0) > 0 else "#ef4444"
            pct_color = "#22c55e" if (pct_pos or 0) > 50 else "#ef4444"
            by_side   = clv_nhl.get("avg_clv_by_side", {})
            over_clv  = by_side.get("OVER")
            under_clv = by_side.get("UNDER")
            over_s    = f"{over_clv:+.2f}" if over_clv is not None else "\u2014"
            under_s   = f"{under_clv:+.2f}" if under_clv is not None else "\u2014"
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

    # ── AI Review ─────────────────────────────────────────────────────────────
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
        # Active scope restriction note
        scope_note = soccer.get("active_scope_note", "")
        if scope_note:
            st.html(
                f'<div style="background:#1a1500;border:1px solid #854d0e;border-radius:6px;'
                f'padding:8px 14px;margin-bottom:12px;font-size:0.82em;color:#fbbf24">'
                f'{scope_note}'
                f'</div>'
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


_nba_hr_cache = {}

def _load_nba_hr_overrides(game_date):
    """Load NBA HR line overrides for a date. Returns dict: game_id → hr_line."""
    if game_date in _nba_hr_cache:
        return _nba_hr_cache[game_date]
    result = {}
    try:
        import json as _j
        _p = os.path.join(os.path.dirname(__file__), "nba", "data", "nba_line_overrides_2026.json")
        if os.path.exists(_p):
            for o in _j.load(open(_p)):
                if o.get("date") == game_date:
                    result[str(o["game_id"])] = float(o["hard_rock_line"])
    except Exception:
        pass
    _nba_hr_cache[game_date] = result
    return result

def _save_nba_hr_override(game_id, date_str, api_line, hr_line):
    """Save an NBA HR line override."""
    import json as _j
    from datetime import datetime as _dt
    _p = os.path.join(os.path.dirname(__file__), "nba", "data", "nba_line_overrides_2026.json")
    os.makedirs(os.path.dirname(_p), exist_ok=True)
    overrides = []
    if os.path.exists(_p):
        try:
            overrides = _j.load(open(_p))
        except Exception:
            overrides = []
    overrides = [o for o in overrides if str(o.get("game_id")) != str(game_id)]
    overrides.append({
        "game_id": str(game_id), "date": date_str, "market": "full_game",
        "odds_api_line": api_line, "hard_rock_line": hr_line,
        "entered_at": _dt.now().isoformat(),
    })
    with open(_p, "w") as f:
        _j.dump(overrides, f, indent=2)
    _nba_hr_cache.pop(date_str, None)


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
            "P1": ("Round 1 Early \u2014 Series suppression · 1.0u", "#60a5fa"),
            "P2": ("Round 1 Late \u2014 Survival desperation · 0.75u", "#fbbf24"),
            "P4": ("Conference Finals \u2014 Elite offense · 0.75u", "#fbbf24"),
        }
        po_label, po_color = po_labels.get(bet_tier, (bet_tier, "#a3a3a3"))
        po_sizing = g.get("playoff_board_sizing", 0)
        if g.get("finals_modifier") and po_sizing != po_labels.get(bet_tier, (None, None))[0]:
            po_label = f"{po_label} (Finals −0.25u)"
        proj_parts.append(f'<span style="color:{po_color};font-weight:600">🏆 {po_label}</span>')
        if line is not None:
            _nba_sig_dir = signal_dir if signal_dir else lean
            _nba_lm = _line_movement_html(line, g.get("open_total"), _nba_sig_dir)
            proj_parts.append(f'<span class="proj-label">Line</span> <span class="proj-val">{line:.1f}{_nba_lm}</span>')
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
            _nba_sig_dir = signal_dir if signal_dir else lean
            _nba_lm = _line_movement_html(line, g.get("open_total"), _nba_sig_dir)
            proj_parts.append(f'<span class="proj-label">Line</span> <span class="proj-val">{line:.1f}{_nba_lm}</span>')
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
            _nba_lm = _line_movement_html(line, g.get("open_total"), lean)
            proj_parts.append(f'<span class="proj-label">Line</span> <span class="proj-val">{line:.1f}{_nba_lm}</span>')
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

    # Archetype signal badge — only show if signal has content
    arch_html = ""
    _arch_sig = g.get("archetype_signal")
    _arch_note = g.get("archetype_note") or ""
    if _arch_sig and _arch_sig not in (None, "None", "", "<NA>") and _arch_note:
        arch_total = g.get("archetype_best_total")
        arch_total_str = f" (best UNDER: {arch_total})" if arch_total and str(arch_total) not in ("None", "<NA>", "") else ""
        arch_html = (
            f'<div style="font-size:0.82em;color:#c084fc;margin-top:4px;'
            f'padding:4px 8px;background:#1a0a2e;border-radius:4px;border:1px solid #7c3aed">'
            f'⚡ ARCHETYPE: {_arch_note}{arch_total_str}'
            f'</div>'
        )

    # Shot profile signal badge — only show if signal has content
    # When another tier is the active bet, show shot as context only
    shot_html = ""
    _shot_sig = g.get("shot_signal")
    if _shot_sig and _shot_sig not in (None, "None", "", "<NA>"):
        shot_dir = g.get("shot_direction", "") or ""
        shot_note = g.get("shot_note", "") or ""
        sig_class = g.get("signal_class", "") or ""
        _is_context = bet_tier and bet_tier not in ("PASS", "CONTEXT") and sig_class not in ("TIER_1A", "TIER_1B", "TIER_2", "DOUBLE_SIGNAL")
        if sig_class == "DOUBLE_SIGNAL":
            badge_bg = "#064e3b"; badge_border = "#059669"; badge_label = "DOUBLE SIGNAL"
        elif sig_class == "CONFLICT":
            badge_bg = "#451a03"; badge_border = "#d97706"; badge_label = "CONFLICT — PASS"
        elif _is_context:
            badge_bg = "#1a1a2e"; badge_border = "#4b5563"; badge_label = "📊 CONTEXT: Shot Profile"
        else:
            badge_bg = "#1e1b4b"; badge_border = "#6366f1"; badge_label = "SHOT PROFILE"
        shot_html = (
            f'<div style="font-size:0.82em;color:#a5b4fc;margin-top:4px;'
            f'padding:4px 8px;background:{badge_bg};border-radius:4px;border:1px solid {badge_border}">'
            f'🎯 {badge_label}: {shot_dir} — {_shot_sig} ({shot_note})'
            f'</div>'
        )

    # Venue signal badge — only show if signal has content
    # When REF_UNDER is the active bet, show venue as context only
    venue_html = ""
    _venue_sig = g.get("venue_signal")
    if _venue_sig and _venue_sig not in (None, "None", "", "<NA>"):
        venue_note = g.get("venue_note") or ""
        _venue_is_context = bet_tier and bet_tier in ("REF_UNDER",) and g.get("ref_signal") == "CONFLICT"
        if _venue_is_context:
            venue_html = (
                f'<div style="font-size:0.82em;color:#9ca3af;margin-top:4px;'
                f'padding:4px 8px;background:#1a1a2e;border-radius:4px;border:1px solid #4b5563">'
                f'📊 CONTEXT: Venue OVER — {venue_note}'
                f'</div>'
            )
        else:
            venue_html = (
                f'<div style="font-size:0.82em;color:#fb923c;margin-top:4px;'
                f'padding:4px 8px;background:#431407;border-radius:4px;border:1px solid #ea580c">'
                f'🏟️ VENUE: OVER — {venue_note}'
                f'</div>'
            )

    # Playoff signal board badge — only show in actual playoff games with a board signal
    playoff_board_html = ""
    po_board = g.get("playoff_board")
    _is_playoff = g.get("is_playoff", False)
    if po_board and _is_playoff and str(po_board) not in (None, "None", "", "<NA>"):
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
    elif g.get("finals_modifier") and _is_playoff:
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

    # When signal direction differs from base model lean, demote summary to context
    import re as _re
    _base_lean = lean.upper() if lean else ""
    _sig_dir = signal_dir.upper() if signal_dir else ""
    _summary_conflict = (is_play and _sig_dir and _base_lean
                         and _sig_dir != _base_lean
                         and _sig_dir not in ("", "CONFLICT", "—"))
    if _summary_conflict and summary:
        # Strip "P(under) XX%" or "P(over) XX%" phrases that contradict signal direction
        _clean = _re.sub(r'P\((under|over)\)\s*\d+%[,.\s]*', '', summary).strip()
        _clean = _re.sub(r'\s*—\s*$', '', _clean)  # trailing dash cleanup
        summary_html = (
            f'<div style="font-size:0.75em;color:#6b7280;margin-top:4px;font-style:italic">'
            f'Model context: {_clean}</div>'
        ) if _clean else ""
    else:
        summary_html = f'<div class="card-summary">{summary}</div>' if summary else ""

    _nba_border = "#22c55e" if is_play else "#374151"
    st.html(
        f'<div class="{card_cls}" style="border-left:4px solid {_nba_border}">'
        f'{header}'
        f'{meta}'
        f'{playoff_context_html}'
        f'{proj_row}'
        f'{h1_row}'
        f'{warn_html}'
        f'{venue_html}'
        f'{shot_html}'
        f'{arch_html}'
        f'{playoff_board_html}'
        f'{ref_html}'
        f'{paused_html}'
        f'{summary_html}'
        f'</div>'
    )

    # ── Hard Rock line override (play cards only) ──
    if is_play and line is not None:
        _nba_gdate = g.get("game_date", "")
        _nba_gid = str(g.get("game_id", f"{away}_{home}"))
        _nba_hr = _load_nba_hr_overrides(_nba_gdate)
        _hr_val = _nba_hr.get(_nba_gid)
        if _hr_val is not None:
            st.html(f'<div style="font-size:0.68em;color:#a78bfa;margin-top:-4px;margin-bottom:4px">'
                    f'\U0001f7e3 HR {_hr_val:.1f} (API {line:.1f})</div>')
        with st.expander(f"\u270f\ufe0f HR line override \u2014 {matchup}", expanded=False):
            _c1, _c2 = st.columns(2)
            _c1.number_input("Total (API: {:.1f})".format(line),
                             min_value=100.0, max_value=300.0, step=0.5,
                             value=_hr_val if _hr_val else line,
                             key=f"nba_hr_{_nba_gid}")
            if _c2.button("Save", key=f"nba_hr_save_{_nba_gid}"):
                _val = st.session_state.get(f"nba_hr_{_nba_gid}")
                if _val is not None and abs(_val - line) > 0.01:
                    _save_nba_hr_override(_nba_gid, _nba_gdate, line, _val)
                st.rerun()


def _render_nba_tab() -> None:
    nba = load_nba_results()

    # Inject open_total from 2 AM snapshot into each game for line movement display
    if nba:
        try:
            _nba_gdate = nba.get("game_date", "")
            _nba_open_path = os.path.join(os.path.dirname(__file__), "nba", "data",
                                           f"nba_lines_open_{_nba_gdate.replace('-','_')}.json")
            if os.path.exists(_nba_open_path):
                with open(_nba_open_path) as _f:
                    _nba_open_snaps = json.load(_f)
                _nba_open_map = {}
                for _s in _nba_open_snaps:
                    if _s.get("snapshot_type") == "open":
                        _nba_open_map[(_s.get("home_team",""), _s.get("away_team",""))] = _s.get("total_line")
                for _g in nba.get("plays", []) + nba.get("no_plays", []):
                    _k = (_g.get("home_team",""), _g.get("away_team",""))
                    _g["open_total"] = _nba_open_map.get(_k)
        except Exception:
            pass

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

    # ── Playoff mode banner ──────────────────────────────────────────────────
    _nba_plays = nba.get("plays", []) + nba.get("no_plays", [])
    _any_playoff = any(g.get("is_playoff") for g in _nba_plays)
    if _any_playoff:
        st.html(
            '<div style="background:#1a1a2e;border:2px solid #f59e0b;border-radius:8px;'
            'padding:10px 16px;margin-bottom:12px;text-align:center">'
            '<span style="font-size:1.1em;font-weight:700;color:#fbbf24">'
            '\U0001f3c6 PLAYOFF MODE ACTIVE</span></div>'
        )

    picks_tab, review_tab = st.tabs(["Today's Picks", "Results Review"])

    with picks_tab:
        st.html(_pipeline_freshness("nba"))

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
                    _today_str = nba.get("game_date", "") if nba else ""
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
            _nba_wagers = n  # 1 wager per game in NBA
            st.html(f'<div class="section-hdr">\U0001f3af Plays \u2014 {n} game{"s" if n != 1 else ""}'
                    f' \u00b7 {_nba_wagers} wager{"s" if _nba_wagers != 1 else ""}</div>')
            for g in plays:
                _render_nba_card(g)
        else:
            _n_games_total = len(plays) + len(no_plays)
            if _n_games_total > 0:
                st.html(
                    f'<div style="background:#1a1a2e;border:1px solid #333;border-radius:8px;'
                    f'padding:14px 18px;margin-bottom:12px">'
                    f'<div style="font-size:1.0em;font-weight:700;color:#94a3b8;margin-bottom:4px">'
                    f'\U0001f3c0 No NBA plays today</div>'
                    f'<div style="font-size:0.85em;color:#6b7280">'
                    f'{_n_games_total} game{"s" if _n_games_total != 1 else ""} scheduled '
                    f'\u2014 no qualifying signals above threshold.</div></div>')
            else:
                st.html(
                    '<div style="background:#1a1a2e;border:1px solid #333;border-radius:8px;'
                    'padding:14px 18px;margin-bottom:12px">'
                    '<div style="font-size:1.0em;font-weight:700;color:#94a3b8;margin-bottom:4px">'
                    '\U0001f3c0 No NBA games scheduled today</div></div>')

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
    # ── Opening Night game card — March 25, 2026 ─────────────────────────
    _od_date = "2026-03-25"
    _od_games = [
        {"away": "NYY", "home": "SFG", "time": "8:05 PM ET", "pk": "823243"},
    ]

    # Check if Opening Night is today or in the future
    from datetime import date as _dt_date
    _today_str = (data or {}).get("game_date", _dt_date.today().isoformat())
    if _today_str <= _od_date:
        st.html('<div class="section-hdr">Opening Night \u2014 March 25, 2026</div>')

        # Load V1 and F5 signals for March 27
        _od_v1_sigs = {}
        _od_f5_sigs = {}
        try:
            _od_v1_path = os.path.join(os.path.dirname(__file__), "mlb_sim", "logs", "signals_2026.parquet")
            if os.path.exists(_od_v1_path):
                _od_v1_df = pd.read_parquet(_od_v1_path)
                for _, _r in _od_v1_df[_od_v1_df["date"] == _od_date].iterrows():
                    _od_v1_sigs[str(_r["game_id"])] = _r
        except Exception:
            pass
        try:
            _od_f5_path = os.path.join(os.path.dirname(__file__), "mlb_sim", "logs", "f5_signals_2026.parquet")
            if os.path.exists(_od_f5_path):
                _od_f5_df = pd.read_parquet(_od_f5_path)
                for _, _r in _od_f5_df[_od_f5_df["date"] == _od_date].iterrows():
                    _od_f5_sigs[str(_r["game_id"])] = _r
        except Exception:
            pass

        # Load current lines from results.json plays/no_plays
        _od_lines = {}
        if data and data.get("game_date") == _od_date:
            for _g in (data.get("plays", []) + data.get("no_plays", [])):
                _gpk = str(_g.get("game_pk", ""))
                _ln = _g.get("line") or _g.get("consensus_line")
                if _gpk and _ln is not None:
                    _od_lines[_gpk] = _ln

        for _og in _od_games:
            _pk = _og["pk"]
            _v1 = _od_v1_sigs.get(_pk)
            _f5 = _od_f5_sigs.get(_pk)
            _line = _od_lines.get(_pk)
            _has_signal = _v1 is not None or _f5 is not None

            # Card styling
            _bg = "#1a2433" if _has_signal else "#1a1a2e"
            _border = "#3b82f6" if _has_signal else "#374151"
            _text_clr = "#e2e8f0" if _has_signal else "#6b7280"

            _card = (f'<div style="background:{_bg};border:1px solid {_border};'
                     f'border-radius:6px;padding:10px 14px;margin-bottom:6px">')
            # Header: matchup + time + line
            _line_str = f"{float(_line):.1f}" if _line else "Lines pending"
            _card += (f'<div style="color:{_text_clr};font-size:0.88em;font-weight:600">'
                      f'{_og["away"]} @ {_og["home"]} \u00b7 {_og["time"]} \u00b7 '
                      f'O/U {_line_str}</div>')

            # V1 signal
            if _v1 is not None:
                _v1_ln = f"{float(_v1['line_at_signal_time']):.1f}" if pd.notna(_v1.get("line_at_signal_time")) else "TBD"
                _v1_pu = f"{float(_v1['raw_p_under'])*100:.1f}%" if pd.notna(_v1.get("raw_p_under")) else ""
                _card += (f'<div style="color:#60a5fa;font-size:0.80em;margin-top:4px">'
                          f'\u25b6 V1 UNDER {_v1_ln} \u00b7 {_v1["stake_units"]}u \u00b7 '
                          f'p_under={_v1_pu}</div>')

            # F5 signal
            if _f5 is not None:
                _f5_side = _f5.get("f5_signal_side", "")
                _f5_ln = f"{float(_f5['f5_line']):.1f}" if pd.notna(_f5.get("f5_line")) else "TBD"
                _f5_p = _f5.get("p_under_full") if _f5_side == "UNDER" else _f5.get("p_over_full")
                _f5_p_str = f"{float(_f5_p)*100:.1f}%" if pd.notna(_f5_p) else ""
                _f5_clr = "#60a5fa" if _f5_side == "UNDER" else "#fbbf24"
                _card += (f'<div style="color:{_f5_clr};font-size:0.80em;margin-top:2px">'
                          f'\u25b6 F5 {_f5_side} {_f5_ln} \u00b7 {_f5["stake_units"]}u \u00b7 '
                          f'p={_f5_p_str}</div>')

            # No signal
            if not _has_signal:
                _card += ('<div style="color:#6b7280;font-size:0.78em;margin-top:4px">'
                          'No signal</div>')

            _card += '</div>'
            st.html(_card)

    # ── season stats banner ───────────────────────────────────────────────
    if stats:
        _render_season_header(stats)

    # (single-content tab — Results Review removed, content lives in Tracker tab)
    if True:
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

        # ── Consolidated engine & shadow status panel ─────────────────────
        try:
            _status_base = os.path.join(os.path.dirname(__file__), "mlb_sim")
            _pill = lambda label, color, bg: (
                f'<span style="background:{bg};color:{color};border:1px solid {color};'
                f'border-radius:10px;padding:2px 8px;font-size:0.68em;font-weight:600;'
                f'margin-right:4px;white-space:nowrap">{label}</span>')

            # GREEN — active engines
            _green_pills = []
            # Sim engine
            _es = os.path.join(_status_base, "pipeline", "engine_status.json")
            if os.path.exists(_es):
                import json as _json_st
                with open(_es) as _esf:
                    if _json_st.load(_esf).get("status") != "PAUSED":
                        _green_pills.append(_pill("Sim engine", "#22c55e", "#052e16"))
            # F5 engine
            _f5s = os.path.join(_status_base, "pipeline", "f5_engine_status.json")
            if os.path.exists(_f5s):
                with open(_f5s) as _f5sf:
                    if _json_st.load(_f5sf).get("status") != "PAUSED":
                        _green_pills.append(_pill("F5 engine", "#22c55e", "#052e16"))
            # F5 Run Line
            _rls = os.path.join(_status_base, "pipeline", "f5_runline_status.json")
            if os.path.exists(_rls):
                with open(_rls) as _rlsf:
                    if _json_st.load(_rlsf).get("status") != "PAUSED":
                        _green_pills.append(_pill("F5 Run Line", "#22c55e", "#052e16"))
            # S12 overlay
            _s12c = os.path.join(_status_base, "pipeline", "s12_overlay_config.json")
            if os.path.exists(_s12c):
                with open(_s12c) as _s12f:
                    if _json_st.load(_s12f).get("s12_cutoff_top20"):
                        _green_pills.append(_pill("S12 overlay", "#22c55e", "#052e16"))
            # P09 overlay
            _p09c = os.path.join(_status_base, "pipeline", "p09_overlay_config.json")
            if os.path.exists(_p09c):
                with open(_p09c) as _p09f:
                    if _json_st.load(_p09f).get("p09_cutoff_bottom20"):
                        _green_pills.append(_pill("P09 overlay", "#22c55e", "#052e16"))
            # YELLOW — shadow monitors (always shown; these are wired in run_model.py)
            _yellow_pills = [
                _pill("CS013 bullpen", "#eab308", "#1c1400"),
                _pill("CS028 blowup", "#eab308", "#1c1400"),
                _pill("KP04 K-prop", "#eab308", "#1c1400"),
                _pill("ST02 road", "#eab308", "#1c1400"),
                _pill("Short exit", "#eab308", "#1c1400"),
                _pill("Team Totals", "#eab308", "#1c1400"),
            ]

            _html_parts = []
            if _green_pills:
                _html_parts.append(
                    f'<span style="color:#64748b;font-size:0.65em;font-weight:600;margin-right:6px">'
                    f'\u25cf Active</span>' + "".join(_green_pills))
            if _yellow_pills:
                _html_parts.append(
                    f'<span style="color:#64748b;font-size:0.65em;font-weight:600;margin-right:6px;'
                    f'margin-left:8px">\u25d0 Shadow</span>' + "".join(_yellow_pills))
            if _html_parts:
                st.html(f'<div style="margin-bottom:8px;line-height:2">{"".join(_html_parts)}</div>')
        except Exception:
            pass

        # ── MLB Sim Engine — UNDER signals (2026 live) ───────────────────────
        try:
            _sim_base = os.path.join(os.path.dirname(__file__), "mlb_sim")
            _sim_status_path = os.path.join(_sim_base, "pipeline", "engine_status.json")
            _sim_signals_path = os.path.join(_sim_base, "logs", "signals_2026.parquet")
            _sim_perf_path = os.path.join(_sim_base, "logs", "rolling_performance_2026.json")

            # Engine status indicator
            if os.path.exists(_sim_status_path):
                import json as _json2
                with open(_sim_status_path) as _sf:
                    _sim_status = _json2.load(_sf)
                if _sim_status.get("status") == "PAUSED":
                    st.html('<div style="background:#2d1515;border:2px solid #dc2626;border-radius:6px;'
                            'padding:8px 12px;margin-bottom:8px;font-size:0.85em;color:#f87171;font-weight:600">'
                            '⚠️ MLB Under Engine paused — manual review required before resuming.</div>')
                else:
                    pass  # Status shown in consolidated panel above

            # Today's V1 signals now shown on unified game cards above

            # ── Unified season performance (reads from signal JSONs directly) ──
            import json as _json3
            _MLB_CUT = "2026-03-30"
            _mlb_tab_v1 = []
            try:
                with open(os.path.join(_sim_base, "logs", "signals_2026.json")) as _f:
                    _mlb_tab_v1 = [r for r in _json3.load(_f) if r.get("result") and (r.get("date","") or "") >= _MLB_CUT]
            except Exception:
                pass
            _mlb_tab_f5 = []
            try:
                with open(os.path.join(_sim_base, "logs", "f5_signals_2026.json")) as _f:
                    _mlb_tab_f5 = [r for r in _json3.load(_f) if r.get("result") and (r.get("date","") or "") >= _MLB_CUT]
            except Exception:
                pass
            _mlb_tab_rl = []
            try:
                with open(os.path.join(_sim_base, "logs", "f5_runline_2026.json")) as _f:
                    _mlb_tab_rl = [r for r in _json3.load(_f) if r.get("result") and (r.get("date","") or "") >= _MLB_CUT]
            except Exception:
                pass

            _v1_live = [r for r in _mlb_tab_v1 if not r.get("shadow_only")]
            _v1_shadow = [r for r in _mlb_tab_v1 if r.get("shadow_only")]
            _all_live = _v1_live + _mlb_tab_f5 + _mlb_tab_rl

            def _mt_wlp(recs):
                w = sum(1 for r in recs if r.get("result") == "WIN")
                l = sum(1 for r in recs if r.get("result") == "LOSS")
                return w, l

            def _mt_roi(recs):
                net = sum(float(r.get("net_units", 0) or 0) for r in recs)
                risked = sum(abs(float(r.get("stake_units", 1) or 1)) for r in recs)
                return (round(net / risked * 100, 1), round(net, 2)) if risked > 0 else (0.0, 0.0)

            _tw, _tl = _mt_wlp(_all_live)
            _troi, _tnet = _mt_roi(_all_live)
            _tn = _tw + _tl
            _roi_clr = "#4ade80" if _troi > 0 else "#fbbf24" if _troi > -4 else "#f87171"

            if _tn > 0:
                st.html(
                    f'<div style="font-size:0.78em;color:#e2e8f0;margin-bottom:4px;font-weight:600">'
                    f'\U0001f4ca Live Production (Mar 30+): '
                    f'<span style="color:#e2e8f0">{_tw}-{_tl}</span>'
                    f' <span style="color:{_roi_clr}">ROI {_troi:+.1f}%</span>'
                    f' <span style="color:#94a3b8">({_tnet:+.2f}u)</span></div>')

                # Engine breakdown
                _eng_parts = []
                _v1w, _v1l = _mt_wlp(_v1_live)
                if _v1w + _v1l > 0:
                    _v1r, _ = _mt_roi(_v1_live)
                    _eng_parts.append(f"V1: {_v1w}-{_v1l} ({_v1r:+.1f}%)")
                _f5w, _f5l = _mt_wlp(_mlb_tab_f5)
                if _f5w + _f5l > 0:
                    _f5r, _ = _mt_roi(_mlb_tab_f5)
                    _eng_parts.append(f"F5: {_f5w}-{_f5l} ({_f5r:+.1f}%)")
                _rlw, _rll = _mt_wlp(_mlb_tab_rl)
                if _rlw + _rll > 0:
                    _rlr, _ = _mt_roi(_mlb_tab_rl)
                    _eng_parts.append(f"RL: {_rlw}-{_rll} ({_rlr:+.1f}%)")
                if _eng_parts:
                    st.html(f'<div style="font-size:0.68em;color:#6b7280;margin-bottom:2px">'
                            f'{" | ".join(_eng_parts)}</div>')

                # Hard stop monitor (V1 live only)
                _v1n = _v1w + _v1l
                _v1roi, _ = _mt_roi(_v1_live) if _v1n > 0 else (0.0, 0.0)
                _hs_clr = "#4ade80" if _v1roi > 0 else "#fbbf24" if _v1roi > -4 else "#f87171"
                from datetime import date as _hs_date
                if _hs_date.today() <= _hs_date(2026, 4, 30):
                    st.html(f'<div style="font-size:0.68em;color:#6b7280;margin-bottom:6px">'
                            f'\u23f8 Hard stop suspended through April 30 \u2014 manual re-evaluation May 1'
                            f' | V1: <span style="color:{_hs_clr}">{_v1roi:+.1f}%</span> ({_v1n} signals)</div>')
                else:
                    st.html(f'<div style="font-size:0.68em;color:#6b7280;margin-bottom:6px">'
                            f'V1 hard stop: <span style="color:{_hs_clr}">{_v1roi:+.1f}%</span>'
                            f' / \u22128.0% threshold | {_v1n}/50 signals</div>')

            # Shadow monitor
            if _v1_shadow:
                _shw, _shl = _mt_wlp(_v1_shadow)
                _shn = _shw + _shl
                if _shn > 0:
                    _shroi, _shnet = _mt_roi(_v1_shadow)
                    st.html(
                        f'<div style="font-size:0.68em;color:#6b7280;margin-top:4px;'
                        f'padding:4px 8px;background:#1a1a2e;border-radius:4px;border:1px solid #333">'
                        f'Shadow (BASE_HIGH, S12_HIGH): '
                        f'{_shw}-{_shl} | {_shroi:+.1f}% ROI | {_shnet:+.2f}u'
                        f'</div>')

            # Recent results table
            if os.path.exists(_sim_signals_path):
                _sim_sigs = pd.read_parquet(_sim_signals_path)
                _resolved = _sim_sigs[_sim_sigs["resolved"].isin([1, 2])].sort_values("date", ascending=False).head(20)
                _pending = _sim_sigs[_sim_sigs["resolved"] == 0].sort_values("date", ascending=False).head(5)
                _show = pd.concat([_pending, _resolved]).head(20)
                if len(_show) > 0:
                    with st.expander("📋 Recent Sim Signals", expanded=False):
                        _rows_html = ""
                        for _, _r in _show.iterrows():
                            _res = _r.get("result", "Pending") or "Pending"
                            _net = f"{float(_r['net_units']):+.2f}u" if pd.notna(_r.get("net_units")) else "—"
                            _clr = "#4ade80" if _res == "WIN" else "#f87171" if _res == "LOSS" else "#6b7280" if _res == "PUSH" else "#4b5563"
                            _pu = f"{float(_r['raw_p_under'])*100:.0f}%" if pd.notna(_r.get("raw_p_under")) else "—"
                            _ln = f"{float(_r['line_at_signal_time']):.1f}" if pd.notna(_r.get("line_at_signal_time")) else "—"
                            _act = f"{float(_r['actual_total']):.0f}" if pd.notna(_r.get("actual_total")) else "—"
                            # Check for HR override
                            _gid = str(_r.get("game_id", ""))
                            _hr = _load_hr_overrides(str(_r.get("date", ""))).get((_gid, "full_game"))
                            if _hr is not None:
                                _ln = f'<span style="color:#a78bfa">HR {_hr:.1f}</span> <span style="color:#4b5563">(API {_ln})</span>'
                            _rows_html += (f'<tr style="color:{_clr}">'
                                           f'<td>{_r.get("date","")}</td>'
                                           f'<td>{_r.get("away_team","")}@{_r.get("home_team","")}</td>'
                                           f'<td>{_ln}</td><td>{_pu}</td><td>{_r.get("stake_units","")}u</td>'
                                           f'<td>{_act}</td><td>{_res}</td><td>{_net}</td></tr>')
                        st.html(f'<table style="font-size:0.75em;width:100%;border-collapse:collapse">'
                                f'<tr style="color:#94a3b8"><th>Date</th><th>Matchup</th><th>Line</th>'
                                f'<th>p_under</th><th>Stake</th><th>Actual</th><th>Result</th><th>Net</th></tr>'
                                f'{_rows_html}</table>')
        except Exception:
            pass

        # ── F5 Signal Engine — Under + Over on first-5-innings totals ────────
        try:
            _f5_base = os.path.join(os.path.dirname(__file__), "mlb_sim")
            _f5_status_path = os.path.join(_f5_base, "pipeline", "f5_engine_status.json")
            _f5_signals_path = os.path.join(_f5_base, "logs", "f5_signals_2026.parquet")
            _f5_perf_path = os.path.join(_f5_base, "logs", "f5_rolling_performance_2026.json")

            # F5 engine status
            if os.path.exists(_f5_status_path):
                import json as _json_f5s
                with open(_f5_status_path) as _f5sf:
                    _f5_status = _json_f5s.load(_f5sf)
                if _f5_status.get("status") == "PAUSED":
                    st.html('<div style="background:#2d1515;border:2px solid #dc2626;border-radius:6px;'
                            'padding:8px 12px;margin-bottom:8px;font-size:0.85em;color:#f87171;font-weight:600">'
                            '\u26a0\ufe0f F5 Engine paused \u2014 manual review required.</div>')
                else:
                    pass  # Status shown in consolidated panel above

            # F5 performance now shown in unified block above

            # F5 recent results
            if os.path.exists(_f5_signals_path):
                _f5_all = pd.read_parquet(_f5_signals_path)
                _f5_resolved = _f5_all[_f5_all["resolved"].isin([1, 2])].sort_values(
                    "date", ascending=False).head(15)
                _f5_pending = _f5_all[_f5_all["resolved"] == 0].sort_values(
                    "date", ascending=False).head(5)
                _f5_show = pd.concat([_f5_pending, _f5_resolved]).head(15)
                if len(_f5_show) > 0:
                    with st.expander("\U0001f4cb Recent F5 Signals", expanded=False):
                        _f5_rows_html = ""
                        for _, _fr in _f5_show.iterrows():
                            _f5_res = _fr.get("result", "Pending") or "Pending"
                            _f5_net = (f"{float(_fr['net_units']):+.2f}u"
                                       if pd.notna(_fr.get("net_units")) else "\u2014")
                            _f5_clr = ("#4ade80" if _f5_res == "WIN"
                                       else "#f87171" if _f5_res == "LOSS"
                                       else "#9ca3af" if _f5_res == "PUSH"
                                       else "#d1d5db" if _f5_res == "POSTPONED"
                                       else "#4b5563")
                            _f5_ln_d = (f"{float(_fr['f5_line']):.1f}"
                                        if pd.notna(_fr.get("f5_line")) else "\u2014")
                            # Check for HR override
                            _f5_gid = str(_fr.get("game_id", ""))
                            _f5_hr = _load_hr_overrides(str(_fr.get("date", ""))).get((_f5_gid, "f5_total"))
                            if _f5_hr is not None:
                                _f5_ln_d = f'<span style="color:#a78bfa">HR {_f5_hr:.1f}</span> <span style="color:#4b5563">(API {_f5_ln_d})</span>'
                            _f5_side_d = _fr.get("f5_signal_side", "")
                            _f5_stake_d = _fr.get("stake_units", "")
                            _f5_act_d = (f"{float(_fr['actual_f5_total']):.0f}"
                                         if pd.notna(_fr.get("actual_f5_total")) else "\u2014")
                            _f5_rows_html += (
                                f'<tr style="color:{_f5_clr}">'
                                f'<td>{_fr.get("date","")}</td>'
                                f'<td>{_fr.get("away_team","")}@{_fr.get("home_team","")}</td>'
                                f'<td>{_f5_ln_d}</td><td>{_f5_side_d}</td>'
                                f'<td>{_f5_stake_d}u</td><td>{_f5_act_d}</td>'
                                f'<td>{_f5_res}</td><td>{_f5_net}</td></tr>')
                        st.html(
                            f'<table style="font-size:0.75em;width:100%;border-collapse:collapse">'
                            f'<tr style="color:#94a3b8"><th>Date</th><th>Matchup</th>'
                            f'<th>F5 Line</th><th>Side</th><th>Stake</th>'
                            f'<th>Actual</th><th>Result</th><th>Net</th></tr>'
                            f'{_f5_rows_html}</table>')
                else:
                    st.html('<div style="font-size:0.78em;color:#6b7280">'
                            'No resolved F5 signals yet.</div>')

        except Exception:
            pass

        # ── F5 Run Line Signal Engine (Live) ─────────────────────────────────
        try:
            _rl_base = os.path.join(os.path.dirname(__file__), "mlb_sim")
            _rl_status_path = os.path.join(_rl_base, "pipeline", "f5_runline_status.json")
            _rl_signals_path = os.path.join(_rl_base, "logs", "f5_runline_2026.parquet")
            _rl_perf_path = os.path.join(_rl_base, "logs", "f5_runline_performance_2026.json")

            # Status
            if os.path.exists(_rl_status_path):
                import json as _json_rl
                with open(_rl_status_path) as _rlf:
                    _rl_status = _json_rl.load(_rlf)
                if _rl_status.get("status") == "PAUSED":
                    st.html('<div style="background:#2d1515;border:2px solid #dc2626;border-radius:6px;'
                            'padding:8px 12px;margin-bottom:8px;font-size:0.85em;color:#f87171;font-weight:600">'
                            '\u26a0\ufe0f F5 Run Line paused \u2014 manual review required.</div>')
                else:
                    pass  # Status shown in consolidated panel above

            # F5 RL performance now shown in unified block above

            # Recent results
            if os.path.exists(_rl_signals_path):
                _rl_all = pd.read_parquet(_rl_signals_path)
                _rl_resolved = _rl_all[_rl_all["resolved"].isin([1, 2])].sort_values(
                    "date", ascending=False).head(10)
                _rl_pending = _rl_all[_rl_all["resolved"] == 0].sort_values(
                    "date", ascending=False).head(5)
                _rl_show = pd.concat([_rl_pending, _rl_resolved]).head(10)
                if len(_rl_show) > 0:
                    with st.expander("\U0001f4cb Recent F5 Run Line Signals", expanded=False):
                        _rl_rows = ""
                        for _, _rr in _rl_show.iterrows():
                            _rl_res = _rr.get("result", "Pending") or "Pending"
                            _rl_net = (f"{float(_rr['net_units']):+.2f}u"
                                       if pd.notna(_rr.get("net_units")) else "\u2014")
                            _rl_c = ("#4ade80" if _rl_res == "WIN"
                                     else "#f87171" if _rl_res == "LOSS"
                                     else "#9ca3af" if _rl_res == "PUSH"
                                     else "#4b5563")
                            _rl_gap_d = f"{float(_rr.get('xfip_gap', 0)):.1f}" if pd.notna(_rr.get("xfip_gap")) else ""
                            _rl_pr_d = f"{int(_rr.get('bet_price', 0))}" if pd.notna(_rr.get("bet_price")) else ""
                            _rl_mg = f"{int(_rr.get('f5_margin', 0))}" if pd.notna(_rr.get("f5_margin")) else "\u2014"
                            _rl_rows += (
                                f'<tr style="color:{_rl_c}">'
                                f'<td>{_rr.get("date","")}</td>'
                                f'<td>{_rr.get("away_team","")}@{_rr.get("home_team","")}</td>'
                                f'<td>{_rl_gap_d}</td><td>HOME {_rl_pr_d}</td>'
                                f'<td>{_rl_mg}</td><td>{_rl_res}</td><td>{_rl_net}</td></tr>')
                        st.html(
                            f'<table style="font-size:0.75em;width:100%;border-collapse:collapse">'
                            f'<tr style="color:#94a3b8"><th>Date</th><th>Matchup</th>'
                            f'<th>Gap</th><th>Bet</th><th>Margin</th>'
                            f'<th>Result</th><th>Net</th></tr>'
                            f'{_rl_rows}</table>')

        except Exception:
            pass

        # Team Total signals now integrated into game card pills above (TT↓H, TT↓A, TT↑H)

        # ── Market Timing section (research display) ─────────────────────────
        try:
            _timing_path = os.path.join(os.path.dirname(__file__), "mlb_sim", "logs", "timing_analysis_2026.json")
            if os.path.exists(_timing_path):
                import json as _json_t
                with open(_timing_path) as _tf:
                    _timing = _json_t.load(_tf)
                _coh = _timing.get("cohorts", {})
                _max_n = max((c.get("n", 0) for c in _coh.values()), default=0)
                with st.expander("📊 Market Timing (research)", expanded=False):
                    if _max_n < 25:
                        st.html(f'<div style="font-size:0.78em;color:#6b7280">'
                                f'Market timing analysis available after 25 resolved signals ({_max_n} so far).</div>')
                    else:
                        _t_rows = ""
                        for _tname, _tlabel in [("signal_time", "Signal time"),
                                                ("open", "Open (7AM)"),
                                                ("midday", "Midday (11AM)"),
                                                ("close_pull", "Close pull (5PM)")]:
                            _tc = _coh.get(_tname, {})
                            _tn = _tc.get("n", 0)
                            _insuf = " (INSUF)" if _tc.get("insufficient") else ""
                            _twr = f"{_tc['win_rate']:.0f}%" if _tc.get("win_rate") is not None else "—"
                            _troi = f"{_tc['observational_roi']:+.1f}%" if _tc.get("observational_roi") is not None else "—"
                            _tal = f"{_tc['avg_line']:.1f}" if _tc.get("avg_line") is not None else "—"
                            _tclv = f"{_tc['avg_clv']:+.2f}" if _tc.get("avg_clv") is not None else "—"
                            _t_rows += (f'<tr><td>{_tlabel}</td><td>{_tn}{_insuf}</td>'
                                        f'<td>{_twr}</td><td>{_troi}</td><td>{_tal}</td><td>{_tclv}</td></tr>')
                        st.html(f'<table style="font-size:0.72em;width:100%;border-collapse:collapse">'
                                f'<tr style="color:#94a3b8"><th>Pull Time</th><th>N</th><th>Win%</th>'
                                f'<th>Obs ROI</th><th>Avg Line</th><th>Avg CLV</th></tr>'
                                f'{_t_rows}</table>'
                                f'<div style="font-size:0.65em;color:#4b5563;margin-top:4px">'
                                f'Win/loss graded at each cohort\'s captured line, not production closing line. '
                                f'Close pull = latest scheduled pregame pull, not guaranteed market close.</div>')

                        # Complete records comparison
                        _comp = _timing.get("complete_records", {})
                        _cn = _comp.get("n_complete_records", 0)
                        if _cn >= 25:
                            _c_rows = ""
                            for _tname, _tlabel in [("signal_time", "Signal"),
                                                    ("open", "Open"), ("midday", "Midday"),
                                                    ("close_pull", "Close")]:
                                _cc = _comp.get(_tname, {})
                                _cwr = f"{_cc['win_rate']:.0f}%" if _cc.get("win_rate") is not None else "—"
                                _croi = f"{_cc['observational_roi']:+.1f}%" if _cc.get("observational_roi") is not None else "—"
                                _c_rows += f'<tr><td>{_tlabel}</td><td>{_cwr}</td><td>{_croi}</td></tr>'
                            st.html(f'<div style="font-size:0.70em;color:#94a3b8;margin-top:6px">'
                                    f'Complete records ({_cn} signals with all four lines):</div>'
                                    f'<table style="font-size:0.70em;width:60%;border-collapse:collapse">'
                                    f'<tr style="color:#6b7280"><th>Cohort</th><th>Win%</th><th>Obs ROI</th></tr>'
                                    f'{_c_rows}</table>')
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

            # Load ALL signals into unified per-game map: team_key → [signal_list]
            import json as _json_sig
            _game_signals = {}  # "away@home" → list of signal dicts
            _base_dir = os.path.dirname(os.path.abspath(__file__))

            def _load_json_signals(name, sig_type, date_field="date"):
                for _p in [os.path.join(_base_dir, "mlb_sim", "logs", name),
                           f"mlb_sim/logs/{name}"]:
                    if not os.path.exists(_p):
                        continue
                    try:
                        with open(_p) as _f:
                            _rows = _json_sig.load(_f)
                        for _r in _rows:
                            if str(_r.get(date_field, "")) != str(game_date):
                                continue
                            _tk = f'{_r.get("away_team","")}@{_r.get("home_team","")}'
                            if _tk not in _game_signals:
                                _game_signals[_tk] = []
                            _info = {"type": sig_type, "stake": float(_r.get("stake_units", 0))}
                            _info["signal_status"] = _r.get("signal_status")
                            # Scratch detection fields (all signal types)
                            _info["scratch_detected"] = bool(_r.get("scratch_detected", False))
                            _info["scratch_voided"] = bool(_r.get("scratch_voided", False))
                            _info["original_home_sp"] = _r.get("original_home_sp")
                            _info["replacement_home_sp"] = _r.get("replacement_home_sp")
                            _info["original_away_sp"] = _r.get("original_away_sp")
                            _info["replacement_away_sp"] = _r.get("replacement_away_sp")
                            if sig_type == "v1":
                                _info["s12_active"] = bool(_r.get("s12_overlay_active", 0))
                                _info["p09_active"] = bool(_r.get("p09_overlay_active", 0))
                                _info["st02_active"] = bool(_r.get("st02_overlay_active", 0))
                                _info["p_under"] = float(_r.get("raw_p_under", 0))
                                _info["line"] = _r.get("line_at_signal_time")
                                _info["open_line"] = _r.get("open_line")
                                _info["shadow_only"] = bool(_r.get("shadow_only", False))
                                _info["signal_class"] = _r.get("signal_class", "")
                            elif sig_type in ("f5_under", "f5_over"):
                                side = _r.get("f5_signal_side", "")
                                _info["type"] = "f5_under" if side == "UNDER" else "f5_over"
                                _info["f5_line"] = _r.get("f5_line")
                                _info["p_under"] = float(_r.get("p_under_full", 0))
                                _info["p_over"] = float(_r.get("p_over_full", 0))
                            _game_signals[_tk].append(_info)
                    except Exception:
                        pass
                    break

            _load_json_signals("signals_2026.json", "v1")
            _load_json_signals("f5_signals_2026.json", "f5_under")  # type corrected inside
            _load_json_signals("f5_runline_2026.json", "f5_rl")

            # Check for PRELIMINARY signals — show banner only 2-7 AM ET
            from datetime import datetime as _prelim_dt
            from zoneinfo import ZoneInfo as _prelim_tz
            _et_hour = _prelim_dt.now(_prelim_tz("America/New_York")).hour
            if 2 <= _et_hour < 7:
                _has_prelim = any(
                    s.get("signal_status") == "PRELIMINARY"
                    for sigs in _game_signals.values() for s in sigs
                )
                if _has_prelim:
                    st.html(
                        '<div style="background:#1c1400;border:2px solid #d97706;border-radius:8px;'
                        'padding:10px 16px;margin-bottom:12px">'
                        '<span style="color:#fbbf24;font-weight:700;font-size:0.95em">'
                        '\u26a0\ufe0f PRELIMINARY</span>'
                        '<span style="color:#fde68a;margin-left:8px;font-size:0.85em">'
                        'Opening lines captured at 2 AM ET. Final signals update at 7 AM ET.'
                        '</span></div>')

            st.html(_pipeline_freshness("mlb_confirm"))

            all_games = (plays or []) + (no_plays or [])
            play_cards = []
            shadow_cards = []
            noplay_cards = []
            for b in all_games:
                _tk = f'{b["game"]["away_team"]}@{b["game"]["home_team"]}'
                _sigs = _game_signals.get(_tk, [])
                if _sigs:
                    # Split: if ALL V1 signals for this game are shadow_only (and no F5/RL),
                    # route to shadow. Otherwise route to live plays.
                    _live_sigs = [s for s in _sigs if not s.get("shadow_only")]
                    _shadow_sigs = [s for s in _sigs if s.get("shadow_only")]
                    if _live_sigs:
                        play_cards.append((b, _live_sigs))
                    if _shadow_sigs:
                        shadow_cards.append((b, _shadow_sigs))
                    if not _live_sigs and not _shadow_sigs:
                        play_cards.append((b, _sigs))  # fallback: treat as live
                else:
                    noplay_cards.append((b, False))

            # ── Yesterday's results (live bets only) ──────────────────────
            try:
                from datetime import datetime as _dt_rt, timedelta as _td_rt
                _yesterday = (_dt_rt.strptime(game_date, "%Y-%m-%d") - _td_rt(days=1)).strftime("%Y-%m-%d")

                def _load_signal_json(name):
                    for _p in [os.path.join(os.path.dirname(os.path.abspath(__file__)),
                               "mlb_sim", "logs", name), f"mlb_sim/logs/{name}"]:
                        if os.path.exists(_p):
                            try:
                                with open(_p) as _f:
                                    return _json_sig.load(_f)
                            except Exception:
                                pass
                    return []

                def _engine_stats_live(rows, date_filter):
                    """Stats for live bets only (excludes shadow_only=True)."""
                    resolved = [r for r in rows
                                if r.get("resolved") == 1
                                and r.get("result") in ("WIN", "LOSS", "PUSH")
                                and r.get("date") == date_filter
                                and not r.get("shadow_only")]
                    w = sum(1 for r in resolved if r["result"] == "WIN")
                    l = sum(1 for r in resolved if r["result"] == "LOSS")
                    net = sum(float(r.get("net_units", 0) or 0) for r in resolved)
                    n = w + l
                    return {"w": w, "l": l, "n": n, "net": net}

                _v1_rows = _load_signal_json("signals_2026.json")
                _f5_rows = _load_signal_json("f5_signals_2026.json")
                _rl_rows = _load_signal_json("f5_runline_2026.json")

                _v1_y = _engine_stats_live(_v1_rows, _yesterday)
                _f5_y = _engine_stats_live(_f5_rows, _yesterday)
                _rl_y = _engine_stats_live(_rl_rows, _yesterday)

                # Parlay yesterday
                _pt_data = None
                for _pp in [os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            "mlb_sim", "logs", "parlay_tracker_2026.json"),
                            "mlb_sim/logs/parlay_tracker_2026.json"]:
                    if os.path.exists(_pp):
                        try:
                            with open(_pp) as _pf:
                                _pt_data = _json_sig.load(_pf)
                        except Exception:
                            pass
                        break

                def _parlay_result(pt_data, tier, date_str):
                    if not pt_data:
                        return '<span style="color:#6b7280">\u2014</span>'
                    parlays = pt_data.get(tier, {}).get("parlays", [])
                    for p in parlays:
                        if p.get("date") == date_str:
                            r = p.get("result", "pending")
                            if r == "WIN": return '<span style="color:#4ade80">W</span>'
                            elif r == "LOSS": return '<span style="color:#f87171">L</span>'
                            else: return '<span style="color:#6b7280">pending</span>'
                    return '<span style="color:#6b7280">\u2014</span>'

                _has_yesterday = _v1_y["n"] + _f5_y["n"] + _rl_y["n"] > 0

                def _fmt_rec(s):
                    if s["n"] == 0:
                        return ""
                    clr = "#4ade80" if s["net"] >= 0 else "#f87171"
                    return f'<span style="color:{clr}">{s["w"]}-{s["l"]} ({s["net"]:+.1f}u)</span>'

                _html = f'<div style="font-size:0.78em;color:#e2e8f0;padding:10px 14px;background:#0f1729;border-radius:6px;border:1px solid #1e2d4a;margin-bottom:12px">'
                _html += f'<div style="font-weight:700;color:#94a3b8;margin-bottom:4px">YESTERDAY \u2014 {_yesterday}</div>'
                if _has_yesterday:
                    if _v1_y["n"] > 0:
                        _html += f'<div>Full Game: {_fmt_rec(_v1_y)}</div>'
                    if _f5_y["n"] > 0:
                        _html += f'<div>F5 Total: {_fmt_rec(_f5_y)}</div>'
                    if _rl_y["n"] > 0:
                        _html += f'<div>F5 Run Line: {_fmt_rec(_rl_y)}</div>'
                    _html += f'<div>Parlays: 3-Leg {_parlay_result(_pt_data, "three_leg", _yesterday)} | 5-Leg {_parlay_result(_pt_data, "five_leg", _yesterday)}</div>'
                else:
                    _html += '<div style="color:#6b7280">No results yet</div>'
                _html += '<div style="margin-top:6px;font-size:0.88em;color:#4b5563">\u2192 See \U0001f4ca Tracker tab for full season stats</div>'
                _html += '</div>'
                st.html(_html)
            except Exception:
                pass

            # ── Shadow signals summary ────────────────────────────────────
            try:
                _sf = _load_shadow_flags(game_date)
                _n_games = len(plays or []) + len(no_plays or [])
                _n_st02 = sum(1 for f in _sf.values() if f.get("st02"))
                _n_cs013 = sum(1 for f in _sf.values() if f.get("cs013"))
                _n_conflict = sum(1 for f in _sf.values() if f.get("st02") and f.get("cs013"))
                if _n_st02 > 0 or _n_cs013 > 0:
                    _sh_parts = []
                    if _n_cs013 > 0:
                        _sh_parts.append(f'CS013 fires on {_n_cs013} of {_n_games} games')
                    if _n_st02 > 0:
                        _sh_parts.append(f'ST02 fires on {_n_st02} of {_n_games} games')
                    if _n_conflict > 0:
                        _sh_parts.append(f'Both fire (conflict) on {_n_conflict}')
                    _sh_text = ' &middot; '.join(_sh_parts)
                    st.html(
                        f'<div style="font-size:0.72em;color:#6b7280;padding:6px 14px;'
                        f'background:#0d1117;border-radius:4px;border:1px solid #1e293b;'
                        f'margin-bottom:10px">'
                        f'<span style="color:#78716c">SHADOW SIGNALS TODAY</span> &mdash; '
                        f'{_sh_text}</div>')
            except Exception:
                pass

            # Play cards — sort by max stake descending, then game time
            def _card_sort_key(item):
                b, sigs = item
                max_stake = max((float(s.get("stake", 0)) for s in sigs), default=0)
                gtime = b.get("game", {}).get("game_time_et", "") or b.get("game", {}).get("game_time", "") or "99:99"
                return (-max_stake, gtime)

            play_cards.sort(key=_card_sort_key)

            if play_cards:
                _n_games = len(play_cards)
                _n_wagers = sum(len(sigs) for _, sigs in play_cards)
                st.html(f'<div class="section-hdr">Today\u2019s Plays \u2014 '
                        f'{_n_games} game{"s" if _n_games != 1 else ""} \u00b7 '
                        f'{_n_wagers} wager{"s" if _n_wagers != 1 else ""}</div>')
                for b, sigs in play_cards:
                    _render_card(b, signals=sigs)

            # Shadow monitoring section (BASE_HIGH and S12_HIGH — non-P09 high conviction)
            if shadow_cards:
                st.html(
                    '<div style="margin-top:16px;padding:8px 14px;background:#1a1a2e;'
                    'border:1px solid #333;border-radius:6px;font-size:0.82em;color:#ef4444;font-weight:700">'
                    'SHADOW MONITORING \u2014 NOT FOR BETTING</div>')
                for b, sigs in shadow_cards:
                    _render_card(b, signals=sigs, has_partial=True)

            # Just For Fun parlays — built from play_cards only (same pool as Today's Plays)
            if len(play_cards) >= 3:
                _parlay_legs = []
                for _b, _sigs in play_cards:
                    _g = _b.get("game", {})
                    _tk = f'{_g.get("away_team", "")} @ {_g.get("home_team", "")}'
                    # V1 takes priority, then F5, then RL
                    _v1_sig = next((s for s in _sigs if s.get("type") == "v1"), None)
                    _f5_sig = next((s for s in _sigs if s.get("type") in ("f5_under", "f5_over")), None)
                    if _v1_sig:
                        _parlay_legs.append({
                            "matchup": _tk,
                            "bet": "FULL GAME UNDER",
                            "p": float(_v1_sig.get("p_under", 0)),
                        })
                    elif _f5_sig:
                        _f5_side = "OVER" if _f5_sig.get("type") == "f5_over" else "UNDER"
                        _f5_p = float(_f5_sig.get("p_under", 0) if _f5_side == "UNDER" else _f5_sig.get("p_over", 0))
                        _parlay_legs.append({
                            "matchup": _tk,
                            "bet": f"F5 {_f5_side}",
                            "p": _f5_p if _f5_p > 0 else 0.5,
                        })
                _parlay_legs.sort(key=lambda x: x["p"], reverse=True)

                if len(_parlay_legs) >= 3:
                    def _render_parlay_card(title, legs):
                        html = (f'<div style="margin:8px 0;padding:10px 14px;background:#0f1729;'
                                f'border-radius:6px;border:1px solid #1e2d4a">')
                        html += (f'<div style="font-size:0.82em;font-weight:700;color:#94a3b8;'
                                 f'margin-bottom:6px;letter-spacing:0.05em">'
                                 f'\u2500\u2500 {title} \u2500\u2500</div>')
                        for leg in legs:
                            html += (f'<div style="font-size:0.82em;color:#e2e8f0;margin-bottom:3px;'
                                     f'padding:3px 0">'
                                     f'\U0001f535 {leg["matchup"]} \u2014 {leg["bet"]}</div>')
                        html += ('<div style="font-size:0.65em;color:#4b5563;margin-top:6px;font-style:italic">'
                                 'Fun only \u00b7 Not a recommended wager</div>')
                        html += '</div>'
                        return html

                    st.html('<div style="font-size:0.92em;font-weight:700;color:#fbbf24;'
                            'margin-top:14px;margin-bottom:4px">\u26a1 JUST FOR FUN PARLAYS</div>')
                    st.html(_render_parlay_card("3-LEG PARLAY", _parlay_legs[:3]))
                    if len(_parlay_legs) >= 5:
                        st.html(_render_parlay_card("5-LEG PARLAY", _parlay_legs[:5]))

                    # Parlay record display
                    _pt_data = None
                    for _pt_path in [os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                     "mlb_sim", "logs", "parlay_tracker_2026.json"),
                                     "mlb_sim/logs/parlay_tracker_2026.json"]:
                        if os.path.exists(_pt_path):
                            try:
                                with open(_pt_path) as _ptf:
                                    _pt_data = _json_sig.load(_ptf)
                            except Exception:
                                pass
                            break

                    if _pt_data:
                        _s3 = _pt_data.get("three_leg", {}).get("summary", {})
                        _s5 = _pt_data.get("five_leg", {}).get("summary", {})
                        _t3 = _s3.get("total", 0)
                        _t5 = _s5.get("total", 0)
                        _combined = _t3 + _t5

                        if _combined > 0:
                            _w3 = _s3.get("wins", 0); _l3 = _s3.get("losses", 0)
                            _w5 = _s5.get("wins", 0); _l5 = _s5.get("losses", 0)
                            _wr = (_w3 + _w5) / _combined * 100 if _combined > 0 else 0
                            _net3 = _s3.get("net_units", 0); _net5 = _s5.get("net_units", 0)

                            if _wr > 40:
                                _flavor = "Running hot \u2014 enjoy it while it lasts"
                            elif _wr < 20:
                                _flavor = "This is why we don\u2019t bet parlays"
                            else:
                                _flavor = "Parlays are entertainment, not strategy"

                            st.html(
                                f'<div style="margin:8px 0;padding:8px 14px;background:#0f1729;'
                                f'border-radius:6px;border:1px solid #1e2d4a;font-size:0.78em">'
                                f'<div style="display:flex;gap:30px;color:#94a3b8">'
                                f'<div><span style="font-weight:700">3-LEG</span> '
                                f'{_w3}-{_l3} | Net: {_net3:+.1f}u</div>'
                                f'<div><span style="font-weight:700">5-LEG</span> '
                                f'{_w5}-{_l5} | Net: {_net5:+.1f}u</div>'
                                f'</div>'
                                f'<div style="font-size:0.85em;color:#6b7280;margin-top:4px;'
                                f'font-style:italic">{_flavor}</div>'
                                f'</div>')
                        else:
                            _p3 = _s3.get("pending", 0); _p5 = _s5.get("pending", 0)
                            st.html(
                                f'<div style="font-size:0.72em;color:#6b7280;margin-top:6px;font-style:italic">'
                                f'Tracking started March 26, 2026 '
                                f'({_p3 + _p5} pending)</div>')

            # No-play cards — collapsed
            if noplay_cards:
                with st.expander(f"All Other Games Today ({len(noplay_cards)})"):
                    for b, _partial in noplay_cards:
                        _render_card(b, has_partial=_partial)

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

    # ── NRFI Parlay Helper (Research) ────────────────────────────────────
    _render_nrfi_helper_section()

    # ── SGP Monitor — Phase 0 ─────────────────────────────────────────────
    _render_sgp_section()


def _render_nrfi_helper_section():
    """NRFI Parlay Helper — research shadow tracker display."""
    import json as _nrfi_json
    from datetime import date as _nrfi_date

    nrfi_path = os.path.join(os.path.dirname(__file__), "research", "mlb_first_inning",
                             "nrfi_shadow_log_2026.json")
    if not os.path.exists(nrfi_path):
        return

    try:
        with open(nrfi_path) as _f:
            nrfi_log = _nrfi_json.load(_f)
    except Exception:
        return

    if not nrfi_log:
        return

    st.divider()
    st.html(
        '<div style="font-size:0.88em;font-weight:700;color:#94a3b8;margin-bottom:4px">'
        'NRFI Parlay Helper (Research)</div>'
        '<div style="font-size:0.72em;color:#64748b;margin-bottom:8px">'
        'Educated guess filter \u2014 not a betting signal. '
        'Based on historical NRFI suppression patterns.<br>'
        '<span style="font-size:0.90em">Excludes CONTACT_RISK home starters '
        'and games where both teams changed top-3 lineup.</span></div>')

    today = _nrfi_date.today().isoformat()
    today_all = [e for e in nrfi_log if e.get("date") == today]

    # Determine whether Phase 11 data is available for today
    has_p11 = any(e.get("qualifies_phase11") is not None for e in today_all)

    if has_p11:
        today_entries = [e for e in today_all if e.get("qualifies_phase11") is True]
    else:
        today_entries = [e for e in today_all
                         if e.get("qualifies_phase8", e.get("qualifies"))]

    if today_entries:
        for e in sorted(today_entries, key=lambda x: x.get("p_yrfi", 1)):
            p = e.get("p_yrfi", 0)
            rank = e.get("combined_rank_pct", 0)
            stab_parts = []
            sh = e.get("top3_stability_home")
            sa = e.get("top3_stability_away")
            if sh and sh != "unknown":
                stab_parts.append(f"H:{sh}")
            if sa and sa != "unknown":
                stab_parts.append(f"A:{sa}")
            stab_str = (" \u00b7 top3=" + ",".join(stab_parts)) if stab_parts else ""
            st.html(
                f'<div style="background:#0d1a0d;border:1px solid #166534;border-radius:6px;'
                f'padding:8px 14px;margin-bottom:4px;font-size:0.82em">'
                f'<span style="color:#86efac;font-weight:600">'
                f'{e.get("away_team")} @ {e.get("home_team")}</span>'
                f'<span style="color:#64748b;margin-left:12px">'
                f'p(YRFI)={p:.3f} \u00b7 rank={rank:.0%}{stab_str}</span></div>')
    else:
        st.html(
            '<div style="font-size:0.78em;color:#64748b;padding:6px 14px;'
            'background:#0f1117;border-radius:4px;margin-bottom:4px">'
            'No qualifying NRFI candidates today.</div>')

    if not has_p11:
        # Show note when Phase 11 lineup filter hasn't run yet
        p8_today = [e for e in today_all
                     if e.get("qualifies_phase8", e.get("qualifies"))]
        if p8_today:
            st.html(
                '<div style="font-size:0.68em;color:#64748b;padding:2px 14px;'
                'font-style:italic">'
                'Awaiting lineup confirmation for final filter.</div>')

    # Compact tracker — use best available qualification
    resolved = [e for e in nrfi_log if e.get("resolved")]
    quals_resolved = [e for e in resolved
                      if e.get("qualifies_phase11",
                               e.get("qualifies_phase8",
                                     e.get("qualifies")))]
    total_logged = len(nrfi_log)
    total_quals = sum(1 for e in nrfi_log
                      if e.get("qualifies_phase11",
                               e.get("qualifies_phase8",
                                     e.get("qualifies"))))
    dates_logged = len(set(e.get("date") for e in nrfi_log))

    if resolved:
        all_nrfi = sum(1 for e in resolved if e.get("result_nrfi") == 1)
        all_pct = all_nrfi / len(resolved) * 100
        qual_nrfi = sum(1 for e in quals_resolved if e.get("result_nrfi") == 1)
        qual_pct = (qual_nrfi / len(quals_resolved) * 100) if quals_resolved else 0
        avg_pool = total_quals / max(dates_logged, 1)

        st.html(
            f'<div style="font-size:0.72em;color:#64748b;padding:4px 14px">'
            f'{total_logged} games logged \u00b7 {total_quals} qualifiers \u00b7 '
            f'{dates_logged} days \u00b7 avg pool {avg_pool:.1f}/day<br>'
            f'Qualifier NRFI: <span style="color:#94a3b8">'
            f'{qual_nrfi}/{len(quals_resolved)} ({qual_pct:.1f}%)</span> \u00b7 '
            f'Full-slate NRFI: <span style="color:#94a3b8">'
            f'{all_nrfi}/{len(resolved)} ({all_pct:.1f}%)</span>'
            f'</div>')
    else:
        st.html(
            f'<div style="font-size:0.72em;color:#64748b;padding:4px 14px">'
            f'{total_logged} games logged \u00b7 {total_quals} qualifiers \u00b7 '
            f'awaiting grading</div>')


def _render_sgp_section():
    """SGP Phase 0 monitor — structural containment pricing."""
    import json as _sgp_json
    from datetime import date as _sgp_date

    st.divider()
    st.html('<div class="section-hdr">\U0001f3af SGP Monitor \u2014 Phase 0</div>')
    st.html(
        '<div style="font-size:0.80em;color:#94a3b8;margin-bottom:8px">'
        'Same Game Parlay Monitor \u2014 Hits O0.5 \u00d7 TB (structural containment)<br>'
        '<span style="font-size:0.90em;color:#64748b">'
        'Fair price = TB leg standalone. Log Hard Rock SGP price to measure excess hold.</span>'
        '</div>')

    today = _sgp_date.today().isoformat()
    fair_path = os.path.join(os.path.dirname(__file__), "mlb", "sgp_phase0", "fair_prices",
                             f"fair_sgp_{today.replace('-','_')}.parquet")

    if not os.path.exists(fair_path):
        st.info("SGP data not yet available \u2014 automation runs at 7:00 AM.")
        return

    try:
        sgp_df = pd.read_parquet(fair_path)
    except Exception as e:
        st.error(f"Failed to load SGP data: {e}")
        return

    n_a = len(sgp_df[sgp_df["pair_type"] == "A"])
    n_b = len(sgp_df[sgp_df["pair_type"] == "B"])
    st.caption(f"{today} \u2014 Pair A: {n_a} | Pair B: {n_b}")

    # Session state for logged prices
    if "sgp_logged" not in st.session_state:
        st.session_state["sgp_logged"] = {}

    def _american_to_implied(price):
        if price > 0: return 100 / (price + 100)
        if price < 0: return abs(price) / (abs(price) + 100)
        return 0.5

    def _american_to_decimal(price):
        if price > 0: return (price / 100) + 1
        if price < 0: return (100 / abs(price)) + 1
        return 2.0

    sgp_tab_a, sgp_tab_b = st.tabs(["Pair A \u2014 TB O1.5", "Pair B \u2014 TB O2.5"])

    for sgp_tab, pair, pair_label in [(sgp_tab_a, "A", "TB O1.5"), (sgp_tab_b, "B", "TB O2.5")]:
        with sgp_tab:
            sub = sgp_df[sgp_df["pair_type"] == pair].sort_values("fair_combined_prob", ascending=False)
            if sub.empty:
                st.caption("No candidates for this pair type.")
                continue

            for _, row in sub.iterrows():
                player = row["player_name"]
                game_str = f"{row['away_team']} @ {row['home_team']}"
                ref_book = row["reference_book"]
                tb_price = int(row["leg2_price"])
                fair_prob = row["fair_combined_prob"]
                key = f"sgp_{player}_{pair}_{row['game_id']}"

                # Check if already logged (in file or session)
                already_logged = pd.notna(row.get("book_sgp_price")) or key in st.session_state["sgp_logged"]

                with st.container():
                    c1, c2, c3, c4 = st.columns([3, 2, 2, 2])
                    c1.markdown(f"**{player}**")
                    c1.caption(f"{game_str} \u00b7 {ref_book}")
                    c2.metric(f"{pair_label} ref", f"{tb_price:+d}")
                    c3.metric("Fair prob", f"{fair_prob*100:.1f}%")

                    if already_logged:
                        logged = st.session_state["sgp_logged"].get(key, {})
                        bp = logged.get("book_sgp_price") or (int(row["book_sgp_price"]) if pd.notna(row.get("book_sgp_price")) else None)
                        if bp:
                            bp_impl = _american_to_implied(bp)
                            eh = bp_impl - fair_prob
                            c4.metric("Book SGP", f"{bp:+d}")
                            if eh > 0.05:
                                st.error(f"Excess hold: {eh:.1%} \u2014 book charging significant premium")
                            elif eh > 0.02:
                                st.warning(f"Excess hold: {eh:.1%} \u2014 moderate")
                            else:
                                st.success(f"Excess hold: {eh:.1%} \u2014 fair or better")
                            dec = _american_to_decimal(bp)
                            ev = fair_prob * (dec - 1) - (1 - fair_prob)
                            st.caption(f"EV: {ev:+.3f} units")
                    else:
                        sgp_input = c4.number_input("HR SGP", value=None, step=5,
                                                     key=f"sgp_input_{key}",
                                                     placeholder="-145",
                                                     label_visibility="collapsed")
                        if c4.button("Log", key=f"sgp_btn_{key}"):
                            if sgp_input is not None and sgp_input != 0:
                                bp = int(sgp_input)
                                bp_impl = round(_american_to_implied(bp), 4)
                                eh = round(bp_impl - fair_prob, 4)
                                dec = round(_american_to_decimal(bp), 4)
                                ev = round(fair_prob * (dec - 1) - (1 - fair_prob), 4)

                                st.session_state["sgp_logged"][key] = {
                                    "book_sgp_price": bp, "excess_hold": eh, "ev": ev}

                                # Append to manual log
                                log_path = os.path.join(os.path.dirname(__file__),
                                                         "mlb", "sgp_phase0", "sgp_manual_log.json")
                                entry = {
                                    "date": today, "player": player, "pair": pair,
                                    "book": "hardrock", "book_sgp_price": bp,
                                    "book_sgp_implied_prob": bp_impl,
                                    "same_book_tb_price": None,
                                    "same_book_tb_implied_prob": None,
                                    "same_book_comparison": False,
                                    "reference_book_mismatch": True,
                                    "fair_combined_prob": round(fair_prob, 4),
                                    "fair_american_odds": tb_price,
                                    "edge": round(fair_prob - bp_impl, 4),
                                    "excess_hold": eh, "ev_per_unit": ev,
                                    "result": None,
                                }
                                log = []
                                if os.path.exists(log_path):
                                    try:
                                        with open(log_path) as _f:
                                            log = _sgp_json.load(_f)
                                    except: pass
                                log.append(entry)
                                with open(log_path, "w") as _f:
                                    _sgp_json.dump(log, _f, indent=2)

                                # Update fair_sgp parquet
                                try:
                                    fdf = pd.read_parquet(fair_path)
                                    mask = (fdf["player_name"] == player) & (fdf["pair_type"] == pair)
                                    fdf.loc[mask, "book_sgp_price"] = bp
                                    fdf.loc[mask, "book_sgp_implied_prob"] = bp_impl
                                    fdf.loc[mask, "excess_hold"] = eh
                                    fdf.loc[mask, "ev_per_unit"] = ev
                                    fdf.to_parquet(fair_path, index=False)
                                except: pass

                                # Rebuild tracker
                                try:
                                    from mlb.sgp_phase0.update_summary_tracker import rebuild
                                    rebuild()
                                except: pass

                                st.rerun()

    # Summary row
    tracker_path = os.path.join(os.path.dirname(__file__), "mlb", "sgp_phase0", "summary_tracker.parquet")
    if os.path.exists(tracker_path):
        try:
            tracker = pd.read_parquet(tracker_path)
            today_logged = tracker[tracker["date"] == today] if "date" in tracker.columns else pd.DataFrame()
            n_today = len(today_logged)
            n_total = len(tracker)
            avg_eh = tracker["excess_hold"].mean() * 100 if tracker["excess_hold"].notna().any() else 0
            st.caption(f"Logged today: {n_today} | Avg excess hold: {avg_eh:+.1f}% | Season total: {n_total}")
        except:
            st.caption("No prices logged yet today.")
    else:
        st.caption("No prices logged yet today.")


# ── main ──────────────────────────────────────────────────────────────────────

def _render_home_tab() -> None:
    """Render the home landing tab with GIF, today's signals, and season snapshot."""
    from datetime import date as _home_date

    # ── GIF ──
    _gif_path = os.path.join(os.path.dirname(__file__), "assets", "fu_money.gif")
    if os.path.exists(_gif_path):
        st.image(_gif_path, use_container_width=True)
    st.html('<div style="text-align:center;color:#6b7280;font-size:0.75em;margin-top:-4px;'
            'margin-bottom:16px;letter-spacing:1px">iamnotuncertain.net</div>')

    # ── Today's Signals ──
    _today = _home_date.today().isoformat()
    st.html('<div style="font-size:1.0em;font-weight:700;color:#e2e8f0;margin-bottom:8px">'
            "Today's Signals</div>")

    _sig_rows = []

    # MLB
    try:
        _mlb_p = os.path.join(os.path.dirname(__file__), "mlb_sim", "logs", "signals_2026.json")
        if os.path.exists(_mlb_p):
            with open(_mlb_p) as _f:
                _mlb_sigs = [s for s in json.load(_f)
                             if s.get("date") == _today and s.get("resolved") != 1
                             and not s.get("scratch_voided")]
            if _mlb_sigs:
                _dirs = set(s.get("signal_side", "UNDER") for s in _mlb_sigs)
                _sig_rows.append(("⚾ MLB", len(_mlb_sigs), " / ".join(sorted(_dirs))))
    except Exception:
        pass

    # NBA
    try:
        nba_r = load_nba_results()
        if nba_r and nba_r.get("game_date") == _today:
            _nba_plays = nba_r.get("plays", [])
            if _nba_plays:
                _dirs = set(p.get("lean", "").upper() for p in _nba_plays if p.get("lean"))
                _sig_rows.append(("🏀 NBA", len(_nba_plays), " / ".join(sorted(_dirs))))
    except Exception:
        pass

    # NHL
    try:
        nhl_r = load_nhl_results()
        if nhl_r and nhl_r.get("game_date") == _today:
            _nhl_sigs = nhl_r.get("signals", [])
            if _nhl_sigs:
                _dirs = set(s.get("signal_side", "") for s in _nhl_sigs)
                _sig_rows.append(("🏒 NHL", len(_nhl_sigs), " / ".join(sorted(_dirs))))
    except Exception:
        pass

    # Soccer
    try:
        soc_r = load_soccer_results()
        if soc_r and soc_r.get("game_date") == _today:
            _soc_plays = soc_r.get("plays", [])
            if _soc_plays:
                _dirs = set(p.get("lean", "").upper() for p in _soc_plays if p.get("lean"))
                _sig_rows.append(("⚽ Soccer", len(_soc_plays), " / ".join(sorted(_dirs))))
    except Exception:
        pass

    # Golf
    try:
        golf_r = load_golf_results()
        if golf_r:
            _golf_cands = [p for p in golf_r.get("candidates", []) if p.get("classification") in ("candidate", "lean")]
            if _golf_cands:
                _sig_rows.append(("⛳ Golf", len(_golf_cands), "OUTRIGHT"))
    except Exception:
        pass

    if _sig_rows:
        _hdr = ('<div style="display:flex;padding:4px 8px;font-size:0.72em;color:#6b7280;'
                'border-bottom:1px solid #333">'
                '<span style="width:120px">Sport</span>'
                '<span style="width:80px;text-align:center">Signals</span>'
                '<span style="flex:1">Direction</span></div>')
        _body = ""
        for sport, n, dirs in _sig_rows:
            _body += (f'<div style="display:flex;padding:6px 8px;font-size:0.85em;color:#e2e8f0;'
                      f'border-bottom:1px solid #1e293b">'
                      f'<span style="width:120px;font-weight:600">{sport}</span>'
                      f'<span style="width:80px;text-align:center;color:#fbbf24;font-weight:700">{n}</span>'
                      f'<span style="flex:1;color:#94a3b8">{dirs}</span></div>')
        st.html(f'<div style="background:#0f172a;border:1px solid #1e293b;border-radius:8px;'
                f'overflow:hidden;margin-bottom:16px">{_hdr}{_body}</div>')
    else:
        st.html('<div style="color:#6b7280;font-size:0.85em;font-style:italic;margin-bottom:16px">'
                'No active signals today.</div>')

    # ── Betting Windows ──
    st.html('<div style="font-size:1.0em;font-weight:700;color:#e2e8f0;margin-bottom:8px">'
            '\U0001f4c5 Today\'s Betting Windows</div>')

    _dow = _home_date.today().weekday()  # 0=Mon, 1=Tue, 3=Thu, 4=Fri
    # Sports with signals today (from _sig_rows built above)
    _active_sports = {r[0] for r in _sig_rows} if _sig_rows else set()

    _windows = [
        ("\u26be MLB",     "7:00 AM ET",     "Confirm run complete, final signals locked",   "\u26be MLB" in _active_sports),
        ("\U0001f3c0 NBA", "9:30 AM / 6:30 PM", "Morning run actionable. Evening captures late injuries.", "\U0001f3c0 NBA" in _active_sports),
        ("\U0001f3d2 NHL", "5:00 PM ET",     "Goalies confirmed, evening pipeline complete", "\U0001f3d2 NHL" in _active_sports),
        ("\u26bd Soccer",  "10:00 AM ET",    "Daily pipeline complete",                      "\u26bd Soccer" in _active_sports),
        ("\u26f3 Golf",    "Thu 8:00 AM ET", "Close capture complete, lines finalized",      _dow in (0, 1, 3)),
    ]

    # Golf note by day
    _golf_note = ""
    if _dow == 1:
        _golf_note = " \u2014 Open capture today"
    elif _dow == 3:
        _golf_note = " \u2014 Close capture + post-R1 tonight"
    elif _dow == 0:
        _golf_note = " \u2014 Grader runs today"

    _hdr = ('<div style="display:flex;padding:5px 8px;font-size:0.70em;color:#6b7280;'
            'border-bottom:1px solid #333">'
            '<span style="width:110px">Sport</span>'
            '<span style="width:110px">Bet After</span>'
            '<span style="flex:1">Why</span></div>')
    _body = ""
    for sport, bet_after, why, active in _windows:
        if active:
            _row_color = "#fbbf24"
            _row_bg = "background:#1c1400;"
            _fw = "font-weight:600"
        else:
            _row_color = "#4b5563"
            _row_bg = ""
            _fw = "font-weight:400"
        _extra = _golf_note if "Golf" in sport else ""
        _body += (f'<div style="display:flex;padding:6px 8px;font-size:0.82em;color:{_row_color};'
                  f'{_row_bg}border-bottom:1px solid #1e293b;{_fw}">'
                  f'<span style="width:110px">{sport}</span>'
                  f'<span style="width:110px">{bet_after}</span>'
                  f'<span style="flex:1">{why}{_extra}</span></div>')

    st.html(f'<div style="background:#0f172a;border:1px solid #1e293b;border-radius:8px;'
            f'overflow:hidden;margin-bottom:12px">{_hdr}{_body}</div>')

    st.html('<div style="font-size:0.75em;color:#6b7280;line-height:1.6">'
            '\u26a0\ufe0f Preliminary MLB signals available at 2:00 AM ET<br>'
            '\u2705 Final signals confirmed at 7:00 AM ET</div>')


# ── NCAAF Portal Shock tab rendering ──────────────────────────────────────────

def _ncaaf_pill(label: str, color: str, bg: str) -> str:
    """Render an NCAAF signal pill — same style as MLB modifier pills."""
    return (f'<span style="background:{bg};color:{color};border:1px solid {color};'
            f'border-radius:10px;padding:1px 7px;font-size:0.68em;font-weight:600;'
            f'margin-right:3px">{label}</span>')


def _render_ncaaf_signal_card(s: dict) -> None:
    """Render a single NCAAF signal card — matches MLB/NHL card visual style."""
    team = s.get("team", "")
    opponent = s.get("opponent", "")
    side = s.get("side", "")
    spread = s.get("spread")
    week = s.get("week", "")
    conf = s.get("conference", "")
    result = s.get("ats_result")

    # Tier-based styling
    t3 = s.get("portal_tier_3", False)
    t2 = s.get("portal_tier_2", False)
    highest = s.get("highest_tier", "TIER_1_BASE")

    if t3:
        border_color = "#22c55e"
    elif t2:
        border_color = "#eab308"
    else:
        border_color = "#374151"

    # Build signal pills
    pills = []
    pills.append(_ncaaf_pill("Portal", "#60a5fa", "#172554"))
    if t2:
        pills.append(_ncaaf_pill("Favored", "#eab308", "#1c1400"))
    if t3:
        pills.append(_ncaaf_pill("Premium", "#22c55e", "#052e16"))
    pill_html = '<div style="margin-top:4px;margin-bottom:2px;line-height:1.8">' + "".join(pills) + '</div>'

    # Result badge
    result_html = ""
    if result == "COVER":
        result_html = '<span style="color:#22c55e;font-weight:700;margin-left:6px">COVER</span>'
    elif result == "NO_COVER":
        result_html = '<span style="color:#ef4444;font-weight:700;margin-left:6px">NO COVER</span>'
    elif result == "PUSH":
        result_html = '<span style="color:#94a3b8;font-weight:700;margin-left:6px">PUSH</span>'

    # Spread display
    spread_str = f"{spread:+.1f}" if spread is not None else ""

    # Stats row
    sep = ' <span style="color:#2d3748;margin:0 2px">&middot;</span> '
    stats_parts = [
        f'<span style="color:#94a3b8;font-size:0.75em">Spread</span> '
        f'<span style="color:#e2e8f0;font-weight:600">{spread_str}</span>',
        f'<span style="color:#94a3b8;font-size:0.75em">Conf</span> '
        f'<span style="color:#e2e8f0">{conf}</span>',
        f'<span style="color:#94a3b8;font-size:0.75em">Net shock</span> '
        f'<span style="color:#e2e8f0">{s.get("net_star_shock", "")}</span>',
        f'<span style="color:#94a3b8;font-size:0.75em">Ret PPA</span> '
        f'<span style="color:#e2e8f0">{s.get("returning_ppa", ""):.1%}</span>'
        if isinstance(s.get("returning_ppa"), (int, float)) else "",
    ]
    stats_parts = [p for p in stats_parts if p]
    stats_row = sep.join(stats_parts)

    # Card HTML
    st.html(
        f'<div style="background:#111827;border:1px solid {border_color};border-radius:8px;'
        f'padding:10px 14px;margin-bottom:8px">'
        f'<div style="display:flex;justify-content:space-between;align-items:center">'
        f'<div>'
        f'<span style="color:#e2e8f0;font-weight:700;font-size:0.95em">'
        f'Wk{week} {sep} {team} vs {opponent}</span>'
        f'{result_html}'
        f'</div>'
        f'<span style="color:{border_color};font-size:0.75em;font-weight:600">'
        f'{highest.replace("TIER_1_","").replace("TIER_2_","").replace("TIER_3_","")}</span>'
        f'</div>'
        f'<div style="margin-top:4px;font-size:0.8em">{stats_row}</div>'
        f'{pill_html}'
        f'<div style="color:#64748b;font-size:0.72em;margin-top:4px">'
        f'Market may be overcorrecting for portal departures — retained core intact.</div>'
        f'</div>'
    )


def _render_ncaaf_portal_tab() -> None:
    """NCAAF Portal Shock — research-grade early-season signal (Weeks 1-4)."""
    import json as _ncaaf_json

    st.markdown("### 🏈 NCAAF Portal Overcorrection — Weeks 1-4")
    st.caption("Research signal. Validated on 2022-2025 Weeks 1-4 only.")

    log_path = os.path.join(os.path.dirname(__file__), "ncaaf", "logs",
                            "portal_shock_signal_log.json")

    if not os.path.exists(log_path):
        st.info("No NCAAF portal shock signal log found. "
                "Signal activates Weeks 1-4 of the college football season "
                "(late August - September).")
        return

    with open(log_path) as _f:
        signals = _ncaaf_json.load(_f)

    if not signals:
        st.info("No qualifying signals logged yet.")
        return

    # Current season signals
    from datetime import date as _ncaaf_date
    current_year = _ncaaf_date.today().year
    current_season = current_year if _ncaaf_date.today().month >= 8 else current_year

    current = [s for s in signals if s.get("season") == current_season]

    # ── Current season game cards ──
    if current:
        st.markdown(f"#### {current_season} Season Qualifiers")
        for s in sorted(current, key=lambda x: (x.get("week", 0), x.get("team", ""))):
            _render_ncaaf_signal_card(s)
    else:
        st.info(f"No {current_season} qualifiers yet. "
                f"Signal activates Weeks 1-4 (late August - September).")

    # ── Historical performance summary ──
    st.markdown("---")
    st.markdown("#### 2022-2025 Backtested Performance")

    graded = [s for s in signals if s.get("ats_result") in ("COVER", "NO_COVER")]
    if not graded:
        return

    # Tier summary table
    tier_rows = []
    for tier_label, display in [("TIER_1_BASE", "Tier 1 — Base"),
                                 ("TIER_2_STRONG", "Tier 2 — Strong"),
                                 ("TIER_3_PREMIUM", "Tier 3 — Premium")]:
        # Count all signals at this tier level or higher
        if tier_label == "TIER_1_BASE":
            tsub = graded  # all are at least Tier 1
        elif tier_label == "TIER_2_STRONG":
            tsub = [s for s in graded if s.get("portal_tier_2")]
        else:
            tsub = [s for s in graded if s.get("portal_tier_3")]
        tc = sum(1 for s in tsub if s["ats_result"] == "COVER")
        tn = len(tsub)
        tr = tc / tn * 100 if tn > 0 else 0
        tier_rows.append({"Tier": display, "N": tn, "Covers": tc,
                          "ATS %": f"{tr:.1f}%", "Record": f"{tc}-{tn - tc}"})

    import pandas as _ncaaf_pd
    st.dataframe(_ncaaf_pd.DataFrame(tier_rows).set_index("Tier"),
                 use_container_width=True)

    st.caption("ATS % includes all qualifying team-games at that tier level or higher. "
               "Research-grade — not a full NCAAF model.")


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

    # ── health status banner ─────────────────────────────────────────────────
    try:
        _hs_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "shared", "health_status.json")
        if os.path.exists(_hs_path):
            with open(_hs_path) as _hsf:
                _hs = json.load(_hsf)
            _hs_age = (datetime.utcnow() - datetime.fromisoformat(_hs["generated_at"].replace("Z","+00:00")).replace(tzinfo=None)).total_seconds() / 3600
            if _hs_age <= 26:
                _hs_overall = _hs.get("overall_status", "GREEN")
                _hs_warns = _hs.get("warnings", [])
                _hs_errs = _hs.get("errors", [])
                if _hs_overall == "GREEN":
                    st.html('<div style="font-size:0.68em;color:#22c55e;margin-bottom:4px">'
                            '\u2705 All systems operational</div>')
                elif _hs_overall == "YELLOW":
                    _hs_w1 = _hs_warns[0] if _hs_warns else ""
                    with st.expander(f"\u26a0\ufe0f {len(_hs_warns)} warning(s) \u2014 {_hs_w1}", expanded=False):
                        for w in _hs_warns:
                            st.html(f'<div style="font-size:0.75em;color:#eab308">{w}</div>')
                elif _hs_overall == "RED":
                    _hs_e1 = _hs_errs[0] if _hs_errs else ""
                    with st.expander(f"\U0001f534 {len(_hs_errs)} error(s) \u2014 {_hs_e1}", expanded=True):
                        for e in _hs_errs:
                            st.html(f'<div style="font-size:0.75em;color:#f87171">{e}</div>')
                        for w in _hs_warns:
                            st.html(f'<div style="font-size:0.75em;color:#eab308">{w}</div>')
    except Exception:
        pass

    # ── sport tabs ────────────────────────────────────────────────────────────
    tab_home, tab_mlb, tab_nba, tab_nhl, tab_soccer, tab_nfl, tab_golf, tab_wnba_arch, tab_ncaaf, tab_reviews, tab_tracker = st.tabs(["\U0001f3e0", "⚾ MLB", "🏀 NBA", "🏒 NHL", "⚽ Soccer", "🏈 NFL", "⛳ Golf", "🏀 WNBA", "🏈 NCAAF", "📋 Reviews", "📊 Tracker"])

    with tab_home:
        _render_home_tab()

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

    with tab_wnba_arch:
        _render_wnba_archetype_tab()

    with tab_ncaaf:
        _render_ncaaf_portal_tab()

    with tab_reviews:
        _render_reviews_tab()

    with tab_tracker:
        _render_tracker_tab()


# ── WNBA Archetype tab rendering ──────────────────────────────────────────────

_ARCH_SHORT = {
    "HIGH_AST_RATE_LOW_OPP_FTA_RATE": "AST",
    "HIGH_TOP2_SHARE_LOW_N_PLAYERS": "TOP2",
    "HIGH_PF_RATE_LOW_STL_TOV_RATIO": "PF",
    "HIGH_STL_TOV_RATIO_LOW_TOV_RATE": "STL",
}


@st.cache_data(ttl=300)
def _load_wnba_arch_registry():
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        "wnba_archetype_board", "config", "archetype_signal_registry.json")
    try:
        with open(path) as f:
            return json.load(f)
    except Exception:
        return []


@st.cache_data(ttl=300)
def _load_wnba_arch_signals_2026():
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        "wnba_archetype_board", "data", "signals", "wnba_archetype_signals_2026.json")
    try:
        with open(path) as f:
            return json.load(f)
    except Exception:
        return []


@st.cache_data(ttl=300)
def _load_wnba_arch_tracker():
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        "wnba_archetype_board", "data", "logs", "signal_tracker.parquet")
    try:
        return pd.read_parquet(path)
    except Exception:
        return pd.DataFrame()


@st.cache_data(ttl=300)
def _load_wnba_arch_historical():
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        "wnba_archetype_board", "reports", "historical_signal_performance.csv")
    try:
        return pd.read_csv(path)
    except Exception:
        return pd.DataFrame()


def _wnba_arch_tier_badge(tier: str) -> str:
    """Top-right confidence tier badge following _conf_badge pattern."""
    colors = {
        "TIER_1": ("gold", "#fbbf24", "#422006"),
        "TIER_2": ("silver", "#94a3b8", "#1e293b"),
        "TIER_3": ("gray", "#64748b", "#1e2535"),
    }
    label, color, bg = colors.get(tier, ("?", "#64748b", "#1e2535"))
    return (f'<span style="background:{bg};color:{color};border:1px solid {color};'
            f'border-radius:4px;padding:2px 8px;font-size:0.75em;font-weight:700;'
            f'letter-spacing:0.05em;text-transform:uppercase;float:right">{tier}</span>')


def _wnba_arch_signal_pill(sig: dict, mode_label: str = "") -> str:
    """Archetype signal pill following MLB modifier pill pattern."""
    tier = sig.get("confidence_tier", "TIER_3")
    is_top = tier in ("TIER_1", "TIER_2")
    color = "#22c55e" if is_top else "#eab308"
    bg = "#052e16" if is_top else "#1c1400"
    sid = sig.get("signal_id", "?")
    h_short = _ARCH_SHORT.get(sig.get("home_archetype", ""), "?")
    a_short = _ARCH_SHORT.get(sig.get("away_archetype", ""), "?")
    direction = sig.get("direction", "?")
    mode_tag = ""
    if mode_label:
        mode_tag = f' <span style="font-size:0.80em;opacity:0.7">{mode_label}</span>'
    return (f'<span style="background:{bg};color:{color};border:1px solid {color};'
            f'border-radius:10px;padding:2px 8px;font-size:0.75em;font-weight:600;'
            f'margin-right:4px;margin-bottom:3px;display:inline-block">'
            f'[{sid}] {h_short} vs {a_short} \u2192 {direction}{mode_tag}</span>')


def _wnba_arch_render_game_card(game: dict, matched_signals: list, registry_map: dict) -> None:
    """Render a single WNBA archetype game card."""
    home = game.get("home_team", "?")
    away = game.get("away_team", "?")
    gdate = game.get("game_date", "")
    closing = game.get("closing_total")
    expansion = game.get("expansion_game", False)
    h_state_src = game.get("home_state_source", "")
    a_state_src = game.get("away_state_source", "")

    # Check for conflicts
    directions = set()
    for s in matched_signals:
        reg = registry_map.get(s.get("signal_id"))
        if reg:
            directions.add(reg.get("direction"))
    is_conflict = len(directions) > 1

    # Border color: green if closing_total, orange-red if conflict, red if no line
    if is_conflict:
        border = "#ef4444"
    elif closing is not None:
        border = "#22c55e"
    else:
        border = "#dc2626"

    matchup = f"{away} @ {home}"

    # Best tier among matched signals
    tier_rank = {"TIER_1": 1, "TIER_2": 2, "TIER_3": 3}
    best_tier = "TIER_3"
    secondary_tiers = []
    for s in matched_signals:
        reg = registry_map.get(s.get("signal_id"))
        if reg:
            t = reg.get("confidence_tier", "TIER_3")
            if tier_rank.get(t, 3) < tier_rank.get(best_tier, 3):
                best_tier = t
    for s in matched_signals:
        reg = registry_map.get(s.get("signal_id"))
        if reg:
            t = reg.get("confidence_tier", "TIER_3")
            if t != best_tier and t not in secondary_tiers:
                secondary_tiers.append(t)

    # Header
    line_str = f"O/U {closing:.1f}" if closing is not None else "No line"
    status = "CONFLICT" if is_conflict else ""
    header = (
        f'<div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:4px">'
        f'<div>'
        f'<span style="font-size:1.05em;font-weight:700;color:#e2e8f0">{matchup}</span>'
        f'<span style="font-size:0.78em;color:#6b7280;margin-left:8px">{gdate}</span>'
        f'<span style="font-size:0.78em;color:#94a3b8;margin-left:8px">{line_str}</span>'
        f'</div>'
        f'<div>{_wnba_arch_tier_badge(best_tier)}</div>'
        f'</div>'
    )

    # Secondary tier note
    sec_html = ""
    if secondary_tiers:
        sec_html = (f'<div style="text-align:right;font-size:0.68em;color:#64748b;margin-top:-2px">'
                    f'Also: {", ".join(secondary_tiers)}</div>')

    # Conflict banner
    conflict_html = ""
    if is_conflict:
        conflict_html = (
            '<div style="background:#2d1515;border:1px solid #ef4444;border-radius:4px;'
            'padding:5px 10px;margin-top:6px;font-size:0.78em;color:#f87171;font-weight:600">'
            'Conflicting season/state signals \u2014 excluded from primary tracking</div>'
        )

    # Signal pills
    pills_html = '<div style="margin-top:4px;line-height:2.0">'
    for s in matched_signals:
        reg = registry_map.get(s.get("signal_id"))
        if reg:
            mode_label = reg.get("archetype_mode", "")
            pills_html += _wnba_arch_signal_pill(reg, mode_label)
    pills_html += '</div>'

    # Inline metrics per signal
    metrics_html = '<div style="margin-top:3px;font-size:0.75em;color:#6b7280">'
    for s in matched_signals:
        reg = registry_map.get(s.get("signal_id"))
        if reg:
            sid = reg.get("signal_id", "?")
            n = reg.get("discovery_N", 0)
            roi = reg.get("discovery_proxy_roi", 0)
            # Get hit rate from historical performance if available
            hit = ""
            metrics_html += (f'{sid}: N={n} \u00b7 ROI +{roi:.1f}% '
                             f'<span style="color:#2d3748;margin:0 4px">\u00b7</span>')
    metrics_html = metrics_html.rstrip(' <span style="color:#2d3748;margin:0 4px">\u00b7</span>')
    metrics_html += '</div>'

    # Small flags
    flags_html = ""
    flag_parts = []
    if expansion:
        flag_parts.append('<span style="color:#f59e0b;font-size:0.72em">\U0001f536 Expansion game</span>')
    if h_state_src == "SEASON_ONLY" or a_state_src == "SEASON_ONLY":
        flag_parts.append('<span style="color:#94a3b8;font-size:0.72em">\U0001f4c5 Season-only</span>')
    if flag_parts:
        flags_html = f'<div style="margin-top:4px">{" &nbsp; ".join(flag_parts)}</div>'

    st.html(
        f'<div class="game-card" style="border-left:4px solid {border}">'
        f'{header}{sec_html}{pills_html}{metrics_html}{conflict_html}{flags_html}'
        f'</div>'
    )


def _render_wnba_archetype_tab() -> None:
    """WNBA Archetype Signals tab."""
    registry = _load_wnba_arch_registry()
    signals_2026 = _load_wnba_arch_signals_2026()
    tracker = _load_wnba_arch_tracker()
    hist_perf = _load_wnba_arch_historical()

    # Validate confidence_tier is present
    if registry and "confidence_tier" not in registry[0]:
        st.error("confidence_tier missing from archetype_signal_registry.json")
        return

    registry_map = {s["signal_id"]: s for s in registry}

    # Build tier map for tracker lookups
    tier_map = {s["signal_id"]: s.get("confidence_tier", "TIER_3") for s in registry}

    # ── Section 1: Status Caption ──
    st.caption("\U0001f3c0 WNBA Archetype Signals \u2014 Structural team matchup signals. "
               "Monitoring 2026 season for live validation.")
    st.html(_pipeline_freshness("wnba"))

    # ── Section 2: Today's Games ──
    if not signals_2026:
        # Check if season hasn't started (before May typically)
        from datetime import date
        today = date.today()
        if today.month < 5:
            st.html('<div class="game-card" style="border-left:4px solid #374151">'
                    '<div style="font-size:0.92em;font-weight:700;color:#e2e8f0">'
                    'WNBA season not started yet. System ready for opening day.</div></div>')
        else:
            st.html('<div class="game-card" style="border-left:4px solid #374151">'
                    '<div style="font-size:0.92em;font-weight:700;color:#e2e8f0">'
                    'No WNBA archetype signals today.</div>'
                    '<div style="font-size:0.78em;color:#6b7280;margin-top:3px">'
                    'Signals will appear automatically on game days.</div></div>')
    else:
        # Group signals by game_id
        game_signals = {}
        for s in signals_2026:
            gid = s.get("game_id", "")
            if gid not in game_signals:
                game_signals[gid] = {"game": s, "signals": []}
            game_signals[gid]["signals"].append(s)

        # Separate primary, conflict, and no-signal games
        primary_cards = []
        conflict_cards = []
        no_signal = []

        for gid, gs in game_signals.items():
            matched = gs["signals"]
            # Determine if any actual signals matched
            has_signal = any(s.get("signal_id") for s in matched)
            if not has_signal:
                no_signal.append(gs["game"])
                continue

            # Check for direction conflict
            dirs = set()
            for s in matched:
                reg = registry_map.get(s.get("signal_id"))
                if reg:
                    dirs.add(reg.get("direction"))
            if len(dirs) > 1:
                conflict_cards.append(gs)
            else:
                # Sort by best tier
                best = min(
                    (registry_map.get(s.get("signal_id"), {}).get("confidence_tier", "TIER_3")
                     for s in matched if s.get("signal_id")),
                    default="TIER_3"
                )
                primary_cards.append((best, gs))

        # Sort primary: TIER_1 first
        primary_cards.sort(key=lambda x: x[0])

        for _, gs in primary_cards:
            _wnba_arch_render_game_card(gs["game"], gs["signals"], registry_map)

        # Conflict cards
        if conflict_cards:
            st.html('<div style="font-size:0.78em;color:#ef4444;font-weight:600;'
                    'margin-top:12px;margin-bottom:4px">Excluded Conflicts</div>')
            for gs in conflict_cards:
                _wnba_arch_render_game_card(gs["game"], gs["signals"], registry_map)

        # No signal games
        if no_signal:
            with st.expander(f"No Signal Games Today ({len(no_signal)})"):
                for g in no_signal:
                    away = g.get("away_team", "?")
                    home = g.get("home_team", "?")
                    cl = g.get("closing_total")
                    line_s = f" \u00b7 O/U {cl:.1f}" if cl is not None else ""
                    st.html(f'<div style="font-size:0.82em;color:#6b7280">'
                            f'{away} @ {home}{line_s}</div>')

    # ── Section 3: Historical Signal Board ──
    st.html('<div style="margin-top:18px;border-top:1px solid #1e293b;padding-top:12px">'
            '<span style="font-size:0.95em;font-weight:700;color:#e2e8f0">'
            'Historical Signal Board</span></div>')

    if hist_perf.empty:
        st.warning("Historical performance file not found.")
    else:
        # Row 1 — Overall
        total_n = int(hist_perf["N"].sum())
        total_w = int(hist_perf["W"].astype(int).sum())
        total_l = int(hist_perf["L"].astype(int).sum())
        # Compute aggregate proxy ROI weighted by N
        total_roi = (hist_perf["proxy_roi"] * hist_perf["N"]).sum() / total_n if total_n else 0
        # Positive seasons: count unique seasons in tracker
        pos_seasons = "4/4"  # frozen from research
        c1, c2, c3 = st.columns(3)
        c1.metric("Total Signals", total_n)
        c2.metric("Proxy ROI", f"+{total_roi:.1f}%")
        c3.metric("Positive Seasons", pos_seasons)

        # Row 2 — By mode
        mc1, mc2 = st.columns(2)
        for col, mode in [(mc1, "SEASON"), (mc2, "STATE")]:
            sub = hist_perf[hist_perf["mode"] == mode]
            if not sub.empty:
                mn = int(sub["N"].sum())
                mr = (sub["proxy_roi"] * sub["N"]).sum() / mn if mn else 0
                col.metric(f"{mode.title()} Mode", f"N={mn}, ROI +{mr:.1f}%")

        # Row 3 — By direction
        dc1, dc2 = st.columns(2)
        for col, d in [(dc1, "OVER"), (dc2, "UNDER")]:
            sub = hist_perf[hist_perf["direction"] == d]
            if not sub.empty:
                dn = int(sub["N"].sum())
                dr = (sub["proxy_roi"] * sub["N"]).sum() / dn if dn else 0
                col.metric(f"{d.title()}", f"N={dn}, ROI +{dr:.1f}%")

        # Row 4 — By tier (from registry confidence_tier)
        tc1, tc2, tc3 = st.columns(3)
        for col, tier in [(tc1, "TIER_1"), (tc2, "TIER_2"), (tc3, "TIER_3")]:
            tier_ids = [s["signal_id"] for s in registry if s.get("confidence_tier") == tier]
            sub = hist_perf[hist_perf["signal_id"].isin(tier_ids)]
            if not sub.empty:
                tn = int(sub["N"].sum())
                tr = (sub["proxy_roi"] * sub["N"]).sum() / tn if tn else 0
                col.metric(tier, f"N={tn}, ROI +{tr:.1f}%")

        # Top 3 by ROI
        st.html('<div style="font-size:0.85em;font-weight:600;color:#94a3b8;margin-top:12px">'
                'Top 3 Signals by ROI</div>')
        top3 = hist_perf.nlargest(3, "proxy_roi")
        for _, row in top3.iterrows():
            sid = row["signal_id"]
            reg = registry_map.get(sid, {})
            tier = reg.get("confidence_tier", "?")
            h_short = _ARCH_SHORT.get(reg.get("home_archetype", ""), "?")
            a_short = _ARCH_SHORT.get(reg.get("away_archetype", ""), "?")
            direction = row.get("direction", "?")
            n = int(row["N"])
            hit = row.get("hit_rate", 0)
            roi = row.get("proxy_roi", 0)
            tier_colors = {"TIER_1": "#fbbf24", "TIER_2": "#94a3b8", "TIER_3": "#64748b"}
            tc = tier_colors.get(tier, "#64748b")
            st.html(
                f'<div class="game-card" style="border-left:3px solid {tc};padding:8px 14px">'
                f'<div style="display:flex;justify-content:space-between;align-items:center">'
                f'<span style="font-size:0.88em;font-weight:700;color:#e2e8f0">'
                f'[{sid}] {h_short} vs {a_short} \u2192 {direction}</span>'
                f'<span style="font-size:0.72em;color:{tc};font-weight:600">{tier}</span></div>'
                f'<div style="font-size:0.75em;color:#6b7280;margin-top:2px">'
                f'N={n} \u00b7 Hit {hit:.1f}% \u00b7 ROI +{roi:.1f}%</div></div>'
            )

        # All 7 signals expander
        with st.expander("View all 7 frozen signals"):
            # Build display table sorted by tier then ROI desc
            display_rows = []
            for _, row in hist_perf.iterrows():
                sid = row["signal_id"]
                reg = registry_map.get(sid, {})
                tier = reg.get("confidence_tier", "TIER_3")
                h_short = _ARCH_SHORT.get(reg.get("home_archetype", ""), "?")
                a_short = _ARCH_SHORT.get(reg.get("away_archetype", ""), "?")
                display_rows.append({
                    "Signal": sid,
                    "Mode": row.get("mode", "?"),
                    "Matchup": f"{h_short} vs {a_short}",
                    "Direction": row.get("direction", "?"),
                    "Tier": tier,
                    "N": int(row["N"]),
                    "ROI": f"+{row.get('proxy_roi', 0):.1f}%",
                })
            df_display = pd.DataFrame(display_rows)
            df_display = df_display.sort_values(
                by=["Tier", "ROI"], ascending=[True, False]
            )
            st.dataframe(df_display, use_container_width=True, hide_index=True)

    # ── Section 4: Tracker ──
    st.html('<div style="margin-top:18px;border-top:1px solid #1e293b;padding-top:12px">'
            '<span style="font-size:0.95em;font-weight:700;color:#e2e8f0">'
            'Signal Tracker</span></div>')

    if tracker.empty:
        st.html('<div style="font-size:0.82em;color:#6b7280">'
                'No tracker data available.</div>')
    else:
        # Check for 2026 data
        has_2026 = (tracker["season"] == 2026).any() if "season" in tracker.columns else False

        if not has_2026:
            st.html('<div style="font-size:0.80em;color:#94a3b8;font-style:italic;margin-bottom:8px">'
                    '2026 live tracking not started \u2014 displaying historical backfill only.</div>')

        # Add tier column from registry
        tracker = tracker.copy()
        tracker["tier"] = tracker["signal_id"].map(tier_map).fillna("TIER_3")

        # Exclude conflicts from summary
        non_conflict = tracker[tracker["signal_conflict"] == 0] if "signal_conflict" in tracker.columns else tracker
        conflicts = tracker[tracker["signal_conflict"] == 1] if "signal_conflict" in tracker.columns else pd.DataFrame()

        graded = non_conflict[non_conflict["result"].isin(["WIN", "LOSS", "PUSH"])]
        total_graded = len(graded)
        w = (graded["result"] == "WIN").sum()
        l = (graded["result"] == "LOSS").sum()
        p = (graded["result"] == "PUSH").sum()
        hit_pct = w / (w + l) * 100 if (w + l) > 0 else 0

        sc1, sc2, sc3, sc4 = st.columns(4)
        sc1.metric("Graded", total_graded)
        sc2.metric("W-L-P", f"{w}-{l}-{p}")
        sc3.metric("Hit%", f"{hit_pct:.1f}%")
        # Proxy ROI from tracker
        if "market_error" in graded.columns and "direction" in graded.columns:
            correct = 0
            for _, r in graded.iterrows():
                me = r.get("market_error", 0) or 0
                d = r.get("direction", "")
                if (d == "OVER" and me > 0) or (d == "UNDER" and me < 0):
                    correct += 1
            roi_pct = (correct / total_graded - 0.5) * 100 * 2 if total_graded > 0 else 0
        else:
            roi_pct = 0
        sc4.metric("ROI", f"+{roi_pct:.1f}%" if roi_pct >= 0 else f"{roi_pct:.1f}%")

        # By tier
        st.html('<div style="font-size:0.78em;font-weight:600;color:#94a3b8;margin-top:8px">'
                'By Tier</div>')
        tc1, tc2, tc3 = st.columns(3)
        for col, tier in [(tc1, "TIER_1"), (tc2, "TIER_2"), (tc3, "TIER_3")]:
            sub = graded[graded["tier"] == tier]
            sw = (sub["result"] == "WIN").sum()
            sl = (sub["result"] == "LOSS").sum()
            sp = (sub["result"] == "PUSH").sum()
            sh = sw / (sw + sl) * 100 if (sw + sl) > 0 else 0
            col.metric(tier, f"{sw}-{sl}-{sp} ({sh:.0f}%)")

        # By mode
        st.html('<div style="font-size:0.78em;font-weight:600;color:#94a3b8;margin-top:4px">'
                'By Mode</div>')
        mc1, mc2 = st.columns(2)
        for col, mode in [(mc1, "SEASON"), (mc2, "STATE")]:
            sub = graded[graded["archetype_mode"] == mode]
            sw = (sub["result"] == "WIN").sum()
            sl = (sub["result"] == "LOSS").sum()
            sp = (sub["result"] == "PUSH").sum()
            sh = sw / (sw + sl) * 100 if (sw + sl) > 0 else 0
            col.metric(f"{mode.title()}", f"{sw}-{sl}-{sp} ({sh:.0f}%)")

        # By expansion
        if "expansion_game" not in tracker.columns:
            # Derive from team data — skip if not available
            pass
        else:
            ec1, ec2 = st.columns(2)
            exp_sub = graded[graded["expansion_game"] == True]
            non_exp = graded[graded["expansion_game"] == False]
            for col, label, sub in [(ec1, "Expansion", exp_sub), (ec2, "Non-Expansion", non_exp)]:
                sw = (sub["result"] == "WIN").sum()
                sl = (sub["result"] == "LOSS").sum()
                sp = (sub["result"] == "PUSH").sum()
                sh = sw / (sw + sl) * 100 if (sw + sl) > 0 else 0
                col.metric(label, f"{sw}-{sl}-{sp} ({sh:.0f}%)" if len(sub) else "N/A")

        # Conflicts excluded count
        if len(conflicts) > 0:
            st.html(f'<div style="font-size:0.72em;color:#6b7280;margin-top:4px">'
                    f'Conflicts excluded: {len(conflicts)}</div>')

        # Recent 10
        st.html('<div style="font-size:0.78em;font-weight:600;color:#94a3b8;margin-top:12px">'
                'Most Recent Graded</div>')
        recent = graded.sort_values("game_date", ascending=False).head(10)
        if len(recent) > 0:
            display_cols = ["game_date", "away_team", "home_team", "signal_id",
                            "direction", "closing_total", "actual_total", "result"]
            avail = [c for c in display_cols if c in recent.columns]
            st.dataframe(recent[avail], use_container_width=True, hide_index=True)
        else:
            st.html('<div style="font-size:0.82em;color:#6b7280">No graded signals yet.</div>')


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

    st.html(_pipeline_freshness("golf"))

    if golf is None:
        st.info("No Golf data available yet. Run `python push_golf.py` to generate.")
        return

    picks_tab, matchup_tab, g13_tab, g14_tab, g15_tab, info_tab = st.tabs(["Outright Board", "Matchups", "G13 Wave", "G14 Tail", "G15 Field", "Model Info"])

    with picks_tab:
        ev_name = golf.get("event_name", "No active event")
        n_cand = golf.get("n_candidates", 0)
        n_lean = golf.get("n_leans", 0)
        st.html(f'<div class="section-hdr">{ev_name} \u2014 '
                f'{n_cand} candidates, {n_lean} leans</div>')

        plays = golf.get("plays", [])

        # Filter unactionable: under + odds < -200
        plays = [p for p in plays if not (
            p.get("direction") == "under" and p.get("close_odds") is not None and p["close_odds"] < -200)]

        # Filter rows with missing book probability
        import math as _math
        plays = [p for p in plays if p.get("market_prob") is not None
                 and not (isinstance(p.get("market_prob"), float) and _math.isnan(p["market_prob"]))]

        if not plays:
            st.info("\u23f3 Waiting for odds \u2014 Hard Rock lines not yet available via API. "
                    "Check back after the next scheduled odds pull.")
        else:
            # Split by market
            _mkt_map = {}
            for p in plays:
                m = p.get("market", "make_cut")
                _mkt_map.setdefault(m, []).append(p)

            _board_tabs = ["Make Cut", "Top 20", "Top 10", "Top 5", "Winner"]
            _board_keys = ["make_cut", "top_20", "top_10", "top_5", "win"]
            _active_tabs = [t for t, k in zip(_board_tabs, _board_keys) if _mkt_map.get(k)]
            _active_keys = [k for k in _board_keys if _mkt_map.get(k)]

            if not _active_tabs:
                st.caption("No candidates this week.")
            else:
                _sub_tabs = st.tabs(_active_tabs)

                for _st, _mk in zip(_sub_tabs, _active_keys):
                    with _st:
                        _mkt_plays = _mkt_map.get(_mk, [])

                        # Sort: over first, then under; leans before candidates within each
                        def _sort_key(p):
                            d = 0 if p.get("direction") == "over" else 1
                            c = 0 if p.get("classification") == "lean" else 1
                            e = -(p.get("edge", 0) or 0)
                            return (d, c, e)

                        _mkt_plays.sort(key=_sort_key)

                        # Split leans and candidates
                        _leans = [p for p in _mkt_plays if p.get("classification") == "lean"]
                        _cands = [p for p in _mkt_plays if p.get("classification") == "candidate"]

                        # Header row
                        st.html(
                            '<div style="display:flex;padding:4px 0;border-bottom:2px solid #333;'
                            'font-size:0.72em;color:#64748b;font-weight:600">'
                            '<span style="width:180px">Player</span>'
                            '<span style="width:70px">Model %</span>'
                            '<span style="width:70px">Book %</span>'
                            '<span style="width:70px">Edge</span>'
                            '<span style="width:60px">Dir</span>'
                            '<span style="width:60px">Odds</span></div>')

                        def _render_play_row(p):
                            cls = p.get("classification", "")
                            badge_color = "#f1c40f" if cls == "lean" else "#2ecc71"
                            edge = p.get("edge", 0) or 0
                            direction = p.get("direction", "")
                            odds_str = ""
                            if p.get("close_odds"):
                                o = p["close_odds"]
                                odds_str = "%+d" % int(o) if o >= 0 else "%d" % int(o)
                            mp = p.get("market_prob", 0)
                            mp_str = f"{mp:.1f}%" if mp and not (isinstance(mp, float) and mp != mp) else "\u2014"
                            dir_color = "#4ade80" if direction == "over" else "#60a5fa"
                            st.html(
                                f'<div style="display:flex;align-items:center;padding:5px 0;border-bottom:1px solid #1e2d4a">'
                                f'<span style="width:180px;font-weight:600;color:#e2e8f0">{p.get("player_name","")}</span>'
                                f'<span style="width:70px;color:#e2e8f0">{p.get("model_prob",0):.1f}%</span>'
                                f'<span style="width:70px;color:#94a3b8">{mp_str}</span>'
                                f'<span style="width:70px;color:{"#4ade80" if edge>0 else "#f87171"}">{edge:+.1f}%</span>'
                                f'<span style="width:60px;color:{dir_color}">{direction}</span>'
                                f'<span style="width:60px;color:#94a3b8">{odds_str}</span></div>')

                        # Show leans always
                        if _leans:
                            for p in _leans:
                                _render_play_row(p)
                        elif not _cands:
                            st.caption("No signals this tournament.")

                        # Candidates in expander
                        if _cands:
                            with st.expander(f"Show all candidates ({len(_cands)})", expanded=False):
                                for p in _cands:
                                    _render_play_row(p)

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

    with g13_tab:
        g13_status = golf.get("g13_status", "")
        g13_plays = golf.get("g13_signals", [])
        g13_avoids = golf.get("g13_avoids", [])

        _status_color = "#22c55e" if g13_status == "LIVE_SHADOW" else "#f59e0b"
        st.html(f'<div class="section-hdr">G13 Wave Weather \u2014 Make Cut '
                f'<span style="color:{_status_color};font-size:0.8em">[{g13_status or "INACTIVE"}]</span></div>')

        if g13_plays:
            st.html('<div style="font-size:0.78em;color:#94a3b8;margin-bottom:8px">'
                    'Rule: adj_make_cut_edge \u2265 4% AND draw_quintile \u2208 {Q4, Q5}'
                    '</div>')
            for gp in g13_plays:
                _edge = gp.get("adj_edge", 0)
                _q = gp.get("draw_quintile", "?")
                _odds_str = ""
                if gp.get("close_odds"):
                    o = gp["close_odds"]
                    _odds_str = "%+d" % int(o) if o >= 0 else "%d" % int(o)
                st.html(
                    f'<div style="display:flex;align-items:center;padding:6px 0;border-bottom:1px solid #1e2d4a">'
                    f'<span style="background:#22c55e;color:#fff;padding:2px 8px;border-radius:4px;'
                    f'font-size:0.75rem;margin-right:10px">G13 WAVE</span>'
                    f'<span style="width:180px;font-weight:600;color:#e2e8f0">{gp.get("player_name","")}</span>'
                    f'<span style="width:40px;color:#60a5fa">Q{_q}</span>'
                    f'<span style="width:80px;color:#94a3b8">DG {gp.get("dg_cut_prob",0):.1f}%</span>'
                    f'<span style="width:80px;color:#e2e8f0">Adj {gp.get("adj_cut_prob",0):.1f}%</span>'
                    f'<span style="width:80px;color:#94a3b8">{gp.get("book","")}</span>'
                    f'<span style="width:60px;color:#94a3b8">{_odds_str}</span>'
                    f'<span style="width:80px;color:#22c55e;font-weight:600">{_edge:+.1f}%</span>'
                    f'</div>')
        else:
            st.caption("No G13 signals this week. Tee times and weather forecast needed.")

        if g13_avoids:
            st.html('<div style="margin-top:16px;padding:8px 14px;background:#1a1a2e;'
                    'border:1px solid #333;border-radius:6px;font-size:0.82em;color:#ef4444;font-weight:700">'
                    'Q1 DRAW AVOID \u2014 Informational Only</div>')
            for ga in g13_avoids:
                _odds_str = ""
                if ga.get("close_odds"):
                    o = ga["close_odds"]
                    _odds_str = "%+d" % int(o) if o >= 0 else "%d" % int(o)
                st.html(
                    f'<div style="display:flex;align-items:center;padding:4px 0;border-bottom:1px solid #1e1e2e">'
                    f'<span style="background:#ef4444;color:#fff;padding:2px 8px;border-radius:4px;'
                    f'font-size:0.72rem;margin-right:10px">Q1 AVOID</span>'
                    f'<span style="width:180px;color:#94a3b8">{ga.get("player_name","")}</span>'
                    f'<span style="width:80px;color:#94a3b8">DG {ga.get("dg_cut_prob",0):.1f}%</span>'
                    f'<span style="width:60px;color:#94a3b8">{_odds_str}</span>'
                    f'<span style="width:80px;color:#f87171">edge {ga.get("dg_edge",0):+.1f}%</span>'
                    f'</div>')

        # G13×S6 composite shadow count
        try:
            _comp_log_path = os.path.join(os.path.dirname(__file__), "golf", "shadow", "golf_shadow_log.parquet")
            if os.path.exists(_comp_log_path):
                _comp_log = pd.read_parquet(_comp_log_path)
                _comp_n = (_comp_log.get("composite_flag") == "G13_S6_REGULAR_HARD").sum() if "composite_flag" in _comp_log.columns else 0
                if _comp_n > 0:
                    st.html(
                        f'<div style="font-size:0.72em;color:#6b7280;margin-top:8px;'
                        f'padding:4px 8px;background:#1a1a2e;border-radius:4px;border:1px solid #333">'
                        f'G13\u00d7S6 Composite [SHADOW] \u2014 N: {_comp_n} signals this season</div>')
        except Exception:
            pass

        # CL03 Inside-Cut shadow count
        try:
            _cl03_log_path = os.path.join(os.path.dirname(__file__), "golf", "shadow", "golf_shadow_log.parquet")
            if os.path.exists(_cl03_log_path):
                _cl03_log = pd.read_parquet(_cl03_log_path)
                _cl03_n = _cl03_log["cl03_flag"].sum() if "cl03_flag" in _cl03_log.columns else 0
                if _cl03_n > 0:
                    st.html(
                        f'<div style="font-size:0.72em;color:#6b7280;margin-top:8px;'
                        f'padding:4px 8px;background:#1a1a2e;border-radius:4px;border:1px solid #333">'
                        f'CL03 Inside-Cut [SHADOW] \u2014 N: {int(_cl03_n)} signals logged this season</div>')
        except Exception:
            pass

    with g14_tab:
        g14_status = golf.get("g14_status", "")
        g14_plays = golf.get("g14_signals", [])
        g14_win_watch = golf.get("g14_win_watchlist", [])
        g14_field = golf.get("g14_field_type", "")
        g14_kill = golf.get("g14_kill_switch", False)

        _g14_color = "#60a5fa" if g14_status == "LIVE_SHADOW" else "#f59e0b"
        st.html(f'<div class="section-hdr">G14 Tail Balance \u2014 Top 10 / Top 5 '
                f'<span style="color:{_g14_color};font-size:0.8em">[{g14_status or "INACTIVE"}]</span></div>')

        if g14_kill:
            st.html('<div style="background:#2d1515;border:2px solid #dc2626;border-radius:6px;'
                    'padding:10px;margin-bottom:8px;color:#f87171;font-weight:700">'
                    'G14 signals suppressed this week \u2014 anomaly detected</div>')
        elif g14_field == "WEAK":
            st.html('<div style="background:#1a1a2e;border:1px solid #4b5563;border-radius:6px;'
                    'padding:10px;margin-bottom:8px;color:#94a3b8">'
                    'G14 inactive this week \u2014 weak field</div>')

        if g14_plays and not g14_kill:
            st.html('<div style="font-size:0.78em;color:#94a3b8;margin-bottom:8px">'
                    'Rule: overlay_edge \u2265 2% AND tb_bucket=HIGH AND field=STRONG</div>')
            for gp in g14_plays:
                _edge = gp.get("adj_edge", 0)
                _odds_str = ""
                if gp.get("close_odds"):
                    o = gp["close_odds"]
                    _odds_str = "%+d" % int(o) if o >= 0 else "%d" % int(o)
                st.html(
                    f'<div style="display:flex;align-items:center;padding:6px 0;border-bottom:1px solid #1e2d4a">'
                    f'<span style="background:#3b82f6;color:#fff;padding:2px 8px;border-radius:4px;'
                    f'font-size:0.75rem;margin-right:10px">G14 TAIL</span>'
                    f'<span style="width:160px;font-weight:600;color:#e2e8f0">{gp.get("player_name","")}</span>'
                    f'<span style="width:50px;color:#94a3b8;font-size:0.8em">{gp.get("skill_band","")}</span>'
                    f'<span style="width:70px;color:#e2e8f0">{gp.get("market","")}</span>'
                    f'<span style="width:70px;color:#94a3b8">DG {gp.get("dg_prob",0):.1f}%</span>'
                    f'<span style="width:70px;color:#e2e8f0">Adj {gp.get("adj_prob",0):.1f}%</span>'
                    f'<span style="width:70px;color:#94a3b8">{gp.get("book","")}</span>'
                    f'<span style="width:55px;color:#94a3b8">{_odds_str}</span>'
                    f'<span style="width:70px;color:#60a5fa;font-weight:600">{_edge:+.1f}%</span>'
                    f'</div>')
        elif not g14_kill and g14_field != "WEAK":
            st.caption("No G14 signals this week.")

        if g14_win_watch:
            st.html('<div style="margin-top:12px;padding:6px 14px;background:#1a1a2e;'
                    'border:1px solid #4b5563;border-radius:6px;font-size:0.82em;color:#94a3b8">'
                    'WIN WATCHLIST \u2014 Tracking Only</div>')
            for gw in g14_win_watch:
                st.html(
                    f'<div style="display:flex;align-items:center;padding:4px 0;border-bottom:1px solid #1e1e2e">'
                    f'<span style="background:#4b5563;color:#d1d5db;padding:2px 8px;border-radius:4px;'
                    f'font-size:0.72rem;margin-right:10px">WIN WATCH</span>'
                    f'<span style="width:160px;color:#94a3b8">{gw.get("player_name","")}</span>'
                    f'<span style="width:90px;color:#94a3b8">DG {gw.get("dg_win_prob",0):.1f}%</span>'
                    f'<span style="width:90px;color:#94a3b8">Adj {gw.get("adj_win_prob",0):.1f}%</span>'
                    f'<span style="width:80px;color:#6b7280">edge {gw.get("win_edge",0):+.1f}%</span>'
                    f'</div>')

    with g15_tab:
        g15_status = golf.get("g15_status", "")
        g15_plays = golf.get("g15_signals", [])
        g15_ed = golf.get("g15_elite_density_bucket", "")
        g15_kill = golf.get("g15_kill_switch", False)

        _g15_color = "#f97316" if g15_status == "LIVE_SHADOW" else "#6b7280"
        st.html(f'<div class="section-hdr">G15 Elite Density \u2014 Top 20 '
                f'<span style="color:{_g15_color};font-size:0.8em">[{g15_status or "INACTIVE"}]</span></div>')

        if g15_kill:
            st.html('<div style="background:#2d1515;border:2px solid #dc2626;border-radius:6px;'
                    'padding:10px;margin-bottom:8px;color:#f87171;font-weight:700">'
                    'G15 signals suppressed this week \u2014 anomaly detected</div>')
        elif g15_ed == "HIGH":
            st.html('<div style="background:#052e16;border:1px solid #22c55e;border-radius:6px;'
                    'padding:8px 14px;margin-bottom:8px;color:#4ade80;font-weight:600">'
                    'G15 ACTIVE \u2014 High Elite Density Field</div>')
        elif g15_ed:
            st.html(f'<div style="background:#1a1a2e;border:1px solid #4b5563;border-radius:6px;'
                    f'padding:8px 14px;margin-bottom:8px;color:#94a3b8">'
                    f'G15 inactive this week \u2014 field not high elite density ({g15_ed})</div>')

        if g15_plays and not g15_kill:
            st.html('<div style="font-size:0.78em;color:#94a3b8;margin-bottom:8px">'
                    'Rule: top_20_edge \u2265 4% AND elite_density = HIGH</div>')
            for gp in g15_plays:
                _edge = gp.get("adj_edge", 0)
                _odds_str = ""
                if gp.get("close_odds"):
                    o = gp["close_odds"]
                    _odds_str = "%+d" % int(o) if o >= 0 else "%d" % int(o)
                st.html(
                    f'<div style="display:flex;align-items:center;padding:6px 0;border-bottom:1px solid #1e2d4a">'
                    f'<span style="background:#f97316;color:#fff;padding:2px 8px;border-radius:4px;'
                    f'font-size:0.75rem;margin-right:10px">G15 FIELD</span>'
                    f'<span style="width:160px;font-weight:600;color:#e2e8f0">{gp.get("player_name","")}</span>'
                    f'<span style="width:80px;color:#94a3b8">DG {gp.get("dg_top20_prob",0):.1f}%</span>'
                    f'<span style="width:80px;color:#e2e8f0">Adj {gp.get("adj_top20_prob",0):.1f}%</span>'
                    f'<span style="width:70px;color:#94a3b8">{gp.get("book","")}</span>'
                    f'<span style="width:55px;color:#94a3b8">{_odds_str}</span>'
                    f'<span style="width:70px;color:#f97316;font-weight:600">{_edge:+.1f}%</span>'
                    f'</div>')
        elif not g15_kill and g15_ed == "HIGH":
            st.caption("No G15 signals this week (no edges above threshold).")

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


# ── Performance Tracker tab ───────────────────────────────────────────────────

def _render_tracker_tab() -> None:
    """Cross-sport performance tracker. Read-only — no signal logic."""
    import json as _tj
    from datetime import date as _tdate, timedelta as _ttd, datetime as _tdt

    # Last updated timestamp
    _tracker_ts = ""
    try:
        from zoneinfo import ZoneInfo
        _et = ZoneInfo("America/New_York")
        _perf_path = os.path.join(os.path.dirname(__file__), "mlb_sim", "logs", "rolling_performance_2026.json")
        if os.path.exists(_perf_path):
            with open(_perf_path) as _f:
                _perf = _tj.load(_f)
            _ts_raw = _perf.get("last_updated") or _perf.get("generated_at")
            if _ts_raw:
                _utc_dt = _tdt.fromisoformat(_ts_raw.replace("Z", "+00:00"))
                _et_dt = _utc_dt.astimezone(_et)
                _tracker_ts = _et_dt.strftime("%b %-d, %Y %-I:%M %p ET")
        if not _tracker_ts:
            _mtime = os.path.getmtime(_perf_path)
            _utc_dt = _tdt.fromtimestamp(_mtime, tz=ZoneInfo("UTC"))
            _et_dt = _utc_dt.astimezone(_et)
            _tracker_ts = _et_dt.strftime("%b %-d, %Y %-I:%M %p ET")
    except Exception:
        pass

    _ts_html = (f'<span style="float:right;font-size:0.72em;color:#64748b">Last updated: {_tracker_ts}</span>'
                if _tracker_ts else "")
    st.html(f"<h4 style='margin:0 0 8px 0'>📊 Performance Tracker{_ts_html}</h4>")

    today = _tdate.today()
    window = st.radio(
        "Time window", ["Last 7 Days", "Last 30 Days", "Season to Date"],
        index=2, horizontal=True, key="tracker_window",
    )
    if window == "Last 7 Days":
        cutoff = (today - _ttd(days=7)).isoformat()
    elif window == "Last 30 Days":
        cutoff = (today - _ttd(days=30)).isoformat()
    else:
        cutoff = "2026-01-01"

    def _wlp(records, result_key="result", win_val="WIN", loss_val="LOSS", push_val="PUSH"):
        w = sum(1 for r in records if r.get(result_key) == win_val)
        l = sum(1 for r in records if r.get(result_key) == loss_val)
        p = sum(1 for r in records if r.get(result_key) == push_val)
        return w, l, p

    def _roi_from_units(records, net_key="net_units", stake_key="stake_units"):
        net = sum(float(r.get(net_key, 0) or 0) for r in records if r.get(net_key) is not None)
        risked = sum(abs(float(r.get(stake_key, 1) or 1)) for r in records)
        return round(net / risked * 100, 1) if risked > 0 else 0.0, round(net, 2)

    def _roi_flat(w, l, p):
        n = w + l + p
        if n == 0:
            return 0.0, 0.0
        net = w * 0.909 - l * 1.0
        return round(net / n * 100, 1), round(net, 2)

    _NHL_STAKE_DEFAULT = {"HIGH": 1.0, "MEDIUM": 0.75, "LOW": 0.5}

    def _nhl_roi_units(records):
        """Unit-weighted ROI for NHL signals. Falls back to tier-based default if stake_units missing."""
        net = 0.0
        risked = 0.0
        for r in records:
            s = float(r.get("stake_units") or _NHL_STAKE_DEFAULT.get(r.get("confidence_tier", "MEDIUM"), 0.75))
            res = r.get("result", "")
            risked += s
            if res == "WIN":
                net += s * (100 / 110)
            elif res == "LOSS":
                net -= s
        return (round(net / risked * 100, 1), round(net, 2)) if risked > 0 else (0.0, 0.0)

    def _compute_movement(records, side_key="signal_side", lm_key="line_movement", cutoff_date="2026-04-01"):
        """Compute CLV% and line movement counts from records."""
        # CLV%: bets where clv > 0
        clv_pos = sum(1 for r in records if (r.get("clv") or r.get("closing_line_value") or 0) > 0)
        clv_total = sum(1 for r in records if r.get("clv") is not None or r.get("closing_line_value") is not None)
        clv_pct = round(clv_pos / clv_total * 100, 1) if clv_total >= 10 else None

        # Line movement (only for bets from April 1 onward)
        moved_with = 0; moved_against = 0; neutral = 0
        for r in records:
            d = r.get("date") or r.get("game_date") or ""
            if d < cutoff_date:
                continue
            lm = r.get(lm_key)
            if lm is None or not isinstance(lm, (int, float)):
                continue
            side = (r.get(side_key) or "").upper()
            if side == "UNDER":
                if lm < -0.1: moved_with += 1
                elif lm > 0.1: moved_against += 1
                else: neutral += 1
            elif side == "OVER":
                if lm > 0.1: moved_with += 1
                elif lm < -0.1: moved_against += 1
                else: neutral += 1
        return clv_pct, moved_with, moved_against, neutral

    def _render_sport_panel(emoji, name, ow, ol, op, roi_pct, units_net, signal_rows,
                            clv_pct=None, moved_with=0, moved_against=0, neutral=0):
        n = ow + ol + op
        rec_str = f"{ow}-{ol}-{op}"
        roi_color = "#22c55e" if roi_pct > 0 else ("#f87171" if roi_pct < 0 else "#94a3b8")
        units_color = "#22c55e" if units_net > 0 else ("#f87171" if units_net < 0 else "#94a3b8")

        if n == 0:
            st.html(
                f'<div style="background:#1e1e2e;border:1px solid #333;border-radius:8px;'
                f'padding:12px 16px;margin-bottom:10px">'
                f'<span style="font-size:1.1em;font-weight:700">{emoji} {name}</span>'
                f'<span style="color:#64748b;margin-left:12px;font-size:0.85em">No data yet</span>'
                f'</div>')
            return

        # CLV + movement metrics row
        _clv_str = f"{clv_pct:.1f}%" if clv_pct is not None else "N/A"
        _clv_color = "#22c55e" if clv_pct is not None and clv_pct > 50 else (
            "#f87171" if clv_pct is not None and clv_pct < 50 else "#94a3b8")
        _mv_total = moved_with + moved_against + neutral
        _mv_html = ""
        if _mv_total > 0:
            _mv_html = (
                f'<span style="font-size:0.80em;color:#94a3b8;margin-left:8px">'
                f'Lines: <span style="color:#22c55e">\u2713{moved_with}</span>'
                f' <span style="color:#f87171">\u2717{moved_against}</span>'
                f' <span style="color:#64748b">\u2014{neutral}</span></span>')

        st.html(
            f'<div style="background:#1e1e2e;border:1px solid #333;border-radius:8px;'
            f'padding:12px 16px;margin-bottom:2px">'
            f'<div style="display:flex;align-items:center;gap:16px;flex-wrap:wrap">'
            f'<span style="font-size:1.1em;font-weight:700">{emoji} {name}</span>'
            f'<span style="font-size:0.9em;color:#e2e8f0;font-weight:600">{rec_str}</span>'
            f'<span style="font-size:0.85em;color:{roi_color};font-weight:600">ROI: {roi_pct:+.1f}%</span>'
            f'<span style="font-size:0.85em;color:{units_color}">Units: {units_net:+.2f}</span>'
            f'<span style="font-size:0.80em;color:{_clv_color}">CLV: {_clv_str}</span>'
            f'{_mv_html}'
            f'</div></div>')

        if signal_rows:
            header = (
                '<div style="display:grid;grid-template-columns:1fr 40px 40px 40px 80px 70px;'
                'padding:4px 16px;font-size:0.72em;color:#64748b;font-weight:600;'
                'border-bottom:1px solid #333">'
                '<span>Signal</span><span>W</span><span>L</span><span>P</span>'
                '<span>Record</span><span>ROI</span></div>')
            rows_html = ""
            for sr in signal_rows:
                sw, sl, sp, s_roi = sr["w"], sr["l"], sr["p"], sr["roi"]
                sn = sw + sl + sp
                srec = f"{sw}-{sl}-{sp}" if sn > 0 else "0-0-0"
                sr_color = "#22c55e" if s_roi > 0 else ("#f87171" if s_roi < 0 else "#64748b")
                roi_str = f"{s_roi:+.1f}%" if sn > 0 else "\u2014"
                rows_html += (
                    f'<div style="display:grid;grid-template-columns:1fr 40px 40px 40px 80px 70px;'
                    f'padding:3px 16px;font-size:0.78em;color:#cbd5e1;'
                    f'border-bottom:1px solid #1a1a2e">'
                    f'<span>{sr["name"]}</span><span>{sw}</span><span>{sl}</span><span>{sp}</span>'
                    f'<span>{srec}</span><span style="color:{sr_color}">{roi_str}</span></div>')
            st.html(
                f'<div style="background:#16162a;border:1px solid #333;border-radius:0 0 8px 8px;'
                f'margin-bottom:10px;overflow:hidden">{header}{rows_html}</div>')

    # ── MLB ──
    _MLB_RESTRUCTURE = "2026-03-30"  # signal class restructuring date

    mlb_v1_all = []
    try:
        with open("mlb_sim/logs/signals_2026.json") as _f:
            mlb_v1_all = [r for r in _tj.load(_f) if (r.get("date", "") or "") >= cutoff and r.get("result")]
    except Exception:
        pass
    mlb_f5_all = []
    try:
        with open("mlb_sim/logs/f5_signals_2026.json") as _f:
            mlb_f5_all = [r for r in _tj.load(_f) if (r.get("date", "") or "") >= cutoff and r.get("result")]
    except Exception:
        pass
    mlb_rl_all = []
    try:
        with open("mlb_sim/logs/f5_runline_2026.json") as _f:
            mlb_rl_all = [r for r in _tj.load(_f) if (r.get("date", "") or "") >= cutoff and r.get("result")]
    except Exception:
        pass

    # Full season live: pre-restructure (all bets) + post-restructure (shadow_only=False)
    mlb_v1_post = [r for r in mlb_v1_all if (r.get("date", "") or "") >= _MLB_RESTRUCTURE]
    mlb_v1_pre = [r for r in mlb_v1_all if (r.get("date", "") or "") < _MLB_RESTRUCTURE]
    mlb_f5_post = [r for r in mlb_f5_all if (r.get("date", "") or "") >= _MLB_RESTRUCTURE]
    mlb_f5_pre = [r for r in mlb_f5_all if (r.get("date", "") or "") < _MLB_RESTRUCTURE]
    mlb_rl_post = [r for r in mlb_rl_all if (r.get("date", "") or "") >= _MLB_RESTRUCTURE]
    mlb_rl_pre = [r for r in mlb_rl_all if (r.get("date", "") or "") < _MLB_RESTRUCTURE]

    # Post-restructure: exclude shadow V1
    mlb_v1_post_live = [r for r in mlb_v1_post if not r.get("shadow_only")]
    mlb_v1_shadow = [r for r in mlb_v1_post if r.get("shadow_only")]

    # Full season live = all pre-restructure + post-restructure live only
    mlb_v1_full_live = mlb_v1_pre + mlb_v1_post_live
    mlb_f5_full = mlb_f5_all  # F5 has no shadow concept
    mlb_rl_full = mlb_rl_all  # RL has no shadow concept

    # ── PRIMARY: Full Season ──
    mlb_signals = []
    v1_w, v1_l, v1_p = _wlp(mlb_v1_full_live)
    v1_roi, v1_net = _roi_from_units(mlb_v1_full_live)
    mlb_signals.append({"name": "V1 UNDER", "w": v1_w, "l": v1_l, "p": v1_p, "roi": v1_roi})

    f5u = [r for r in mlb_f5_full if r.get("f5_signal_side") == "UNDER"]
    f5o = [r for r in mlb_f5_full if r.get("f5_signal_side") == "OVER"]
    f5u_w, f5u_l, f5u_p = _wlp(f5u)
    f5u_roi, _ = _roi_from_units(f5u)
    f5o_w, f5o_l, f5o_p = _wlp(f5o)
    f5o_roi, _ = _roi_from_units(f5o)
    mlb_signals.append({"name": "F5 UNDER", "w": f5u_w, "l": f5u_l, "p": f5u_p, "roi": f5u_roi})
    mlb_signals.append({"name": "F5 OVER", "w": f5o_w, "l": f5o_l, "p": f5o_p, "roi": f5o_roi})

    rl_w, rl_l, rl_p = _wlp(mlb_rl_full)
    rl_roi, _ = _roi_from_units(mlb_rl_full)
    mlb_signals.append({"name": "F5 Run Line", "w": rl_w, "l": rl_l, "p": rl_p, "roi": rl_roi})

    s12 = [r for r in mlb_v1_full_live if r.get("s12_overlay_active")]
    s12_w, s12_l, s12_p = _wlp(s12)
    s12_roi, _ = _roi_from_units(s12)
    mlb_signals.append({"name": "S12 overlay", "w": s12_w, "l": s12_l, "p": s12_p, "roi": s12_roi})

    p09 = [r for r in mlb_v1_full_live if r.get("p09_overlay_active")]
    p09_w, p09_l, p09_p = _wlp(p09)
    p09_roi, _ = _roi_from_units(p09)
    mlb_signals.append({"name": "P09 overlay", "w": p09_w, "l": p09_l, "p": p09_p, "roi": p09_roi})

    all_mlb_live = mlb_v1_full_live + mlb_f5_full + mlb_rl_full
    mw, ml, mp = _wlp(all_mlb_live)
    m_roi, m_net = _roi_from_units(all_mlb_live)
    _m_clv, _m_mw, _m_ma, _m_mn = _compute_movement(all_mlb_live, side_key="signal_side")

    st.html('<div style="font-size:0.72em;color:#64748b;margin-bottom:2px">'
            'Full Season \u2014 Mar 25, 2026 \u2192 Today</div>')
    _render_sport_panel("\u26be", "MLB", mw, ml, mp, m_roi, m_net, mlb_signals,
                        clv_pct=_m_clv, moved_with=_m_mw, moved_against=_m_ma, neutral=_m_mn)

    # ── SECONDARY: Post-Restructure (Mar 30+) — collapsed ──
    all_post_live = mlb_v1_post_live + mlb_f5_post + mlb_rl_post
    pw, pl, pp = _wlp(all_post_live)
    pn = pw + pl + pp
    if pn > 0:
        p_roi, p_net = _roi_from_units(all_post_live)
        _proi_color = "#22c55e" if p_roi > 0 else ("#f87171" if p_roi < 0 else "#64748b")
        with st.expander(f"Post-Restructure \u2014 Mar 30+ ({pn} bets)", expanded=False):
            st.html(
                f'<div style="background:#1a1a2e;border:1px solid #2d2d44;border-radius:6px;'
                f'padding:10px 14px;margin-bottom:4px">'
                f'<div style="display:flex;align-items:center;gap:14px;flex-wrap:wrap">'
                f'<span style="font-size:0.88em;color:#94a3b8;font-weight:600">'
                f'Post-Restructure \u2014 Mar 30, 2026 \u2192 Today</span>'
                f'<span style="font-size:0.82em;color:#e2e8f0">{pw}-{pl}-{pp}</span>'
                f'<span style="font-size:0.82em;color:{_proi_color}">ROI: {p_roi:+.1f}%</span>'
                f'<span style="font-size:0.82em;color:#94a3b8">Units: {p_net:+.2f}</span>'
                f'</div>'
                f'<div style="font-size:0.70em;color:#4b5563;margin-top:6px;font-style:italic">'
                f'Signal classes restructured March 30. Shadow routing + P09/S12 overlays active.</div>'
                f'</div>')

    # ── Shadow observation (BASE_HIGH, S12_HIGH — not traded live) ──
    if mlb_v1_shadow:
        sh_w, sh_l, sh_p = _wlp(mlb_v1_shadow)
        sh_roi, sh_net = _roi_from_units(mlb_v1_shadow)
        sh_n = sh_w + sh_l + sh_p
        if sh_n > 0:
            _shroi_color = "#22c55e" if sh_roi > 0 else ("#f87171" if sh_roi < 0 else "#64748b")
            with st.expander(f"Shadow observation ({sh_n} bets \u2014 not traded live)", expanded=False):
                st.html(
                    f'<div style="background:#1a1a2e;border:1px solid #2d2d44;border-radius:6px;'
                    f'padding:10px 14px;margin-bottom:4px">'
                    f'<div style="display:flex;align-items:center;gap:14px;flex-wrap:wrap">'
                    f'<span style="font-size:0.88em;color:#64748b;font-weight:600">'
                    f'V1 Shadow \u2014 BASE_HIGH + S12_HIGH</span>'
                    f'<span style="font-size:0.82em;color:#94a3b8">{sh_w}-{sh_l}-{sh_p}</span>'
                    f'<span style="font-size:0.82em;color:{_shroi_color}">ROI: {sh_roi:+.1f}%</span>'
                    f'<span style="font-size:0.82em;color:#94a3b8">Units: {sh_net:+.2f}</span>'
                    f'</div>'
                    f'<div style="font-size:0.70em;color:#4b5563;margin-top:6px;font-style:italic">'
                    f'Shadow signals lack P09 confirmation. Tracked for validation \u2014 not included in live record.</div>'
                    f'</div>')

    # ── NBA ──
    nba_records = []
    try:
        _nba = pd.read_parquet("nba/data/nba_signal_log.parquet")
        _nba = _nba[_nba["game_date"] >= cutoff]
        _nba = _nba[_nba["result"].notna()]
        nba_records = _nba.to_dict("records")
    except Exception:
        pass

    nw, nl, np_ = _wlp(nba_records)
    nba_signals = []
    venue_only = [r for r in nba_records if r.get("venue_signal") and not r.get("oreb_confirms")]
    venue_oreb = [r for r in nba_records if r.get("venue_signal") and r.get("oreb_confirms")]
    ref_under = [r for r in nba_records if r.get("tier") == "REF_UNDER"]
    def _nba_sub_roi(sub):
        """Unit-weighted ROI for NBA signal subsets."""
        if sub and sub[0].get("units_won_lost") is not None:
            net = sum(float(r.get("units_won_lost", 0) or 0) for r in sub)
            risked = sum(float(r.get("units", 1) or 1) for r in sub)
            return round(net / risked * 100, 1) if risked > 0 else 0.0
        tw, tl, tp = _wlp(sub)
        r, _ = _roi_flat(tw, tl, tp)
        return r

    for label, sub in [("Venue OVER", venue_only), ("Venue+OREB", venue_oreb), ("REF UNDER", ref_under)]:
        tw, tl, tp = _wlp(sub)
        tr = _nba_sub_roi(sub)
        nba_signals.append({"name": label, "w": tw, "l": tl, "p": tp, "roi": tr})

    if nba_records and nba_records[0].get("units_won_lost") is not None:
        n_net = sum(float(r.get("units_won_lost", 0) or 0) for r in nba_records)
        n_risked = sum(float(r.get("units", 1) or 1) for r in nba_records)
        n_roi = round(n_net / n_risked * 100, 1) if n_risked > 0 else 0.0
    else:
        n_roi, n_net = _roi_flat(nw, nl, np_)
    # NBA signal_side is stored as "lean" in signal log
    _nba_mv_records = [{"signal_side": r.get("lean", "").upper(), "line_movement": r.get("line_movement"),
                         "clv": r.get("clv"), "game_date": r.get("game_date")} for r in nba_records]
    _n_clv, _n_mw, _n_ma, _n_mn = _compute_movement(_nba_mv_records)
    _render_sport_panel("\U0001f3c0", "NBA", nw, nl, np_, n_roi, round(n_net, 2), nba_signals,
                        clv_pct=_n_clv, moved_with=_n_mw, moved_against=_n_ma, neutral=_n_mn)

    # ── NHL ──
    nhl_records = []
    try:
        _nhl = pd.read_parquet("nhl/nhl_decisions.parquet")
        _nhl = _nhl[(_nhl["split"] == "live") & (_nhl["game_date"] >= cutoff)]
        _nhl = _nhl[_nhl["result"].isin(["WIN", "LOSS", "PUSH"])]
        nhl_records = _nhl.to_dict("records")
    except Exception:
        pass

    hw, hl_, hp = _wlp(nhl_records)
    nhl_signals = []
    for label, filt in [("OVER", lambda r: r.get("signal_side") == "OVER"),
                         ("UNDER", lambda r: r.get("signal_side") == "UNDER")]:
        sub = [r for r in nhl_records if filt(r)]
        tw, tl, tp = _wlp(sub)
        tr, _ = _nhl_roi_units(sub)
        nhl_signals.append({"name": label, "w": tw, "l": tl, "p": tp, "roi": tr})
    for tier in ["HIGH", "MEDIUM"]:
        sub = [r for r in nhl_records if r.get("confidence_tier") == tier]
        tw, tl, tp = _wlp(sub)
        tr, _ = _nhl_roi_units(sub)
        nhl_signals.append({"name": f"{tier} tier", "w": tw, "l": tl, "p": tp, "roi": tr})

    h_roi, h_net = _nhl_roi_units(nhl_records)
    _h_clv, _h_mw, _h_ma, _h_mn = _compute_movement(nhl_records)
    _render_sport_panel("\U0001f3d2", "NHL", hw, hl_, hp, h_roi, h_net, nhl_signals,
                        clv_pct=_h_clv, moved_with=_h_mw, moved_against=_h_ma, neutral=_h_mn)

    # ── Soccer ──
    soc_records = []
    try:
        _soc = pd.read_parquet("soccer/data/soccer_decisions.parquet")
        _soc["game_date"] = pd.to_datetime(_soc["game_date"]).dt.strftime("%Y-%m-%d")
        _soc = _soc[(_soc["split"] == "live") & (_soc["game_date"] >= cutoff) & (_soc["graded"] == 1)]
        soc_records = _soc.to_dict("records")
    except Exception:
        pass

    sw_, sl__, sp_ = _wlp(soc_records)
    soc_signals = []
    for lg in ["EPL", "BUN", "LG1", "SEA"]:
        sub = [r for r in soc_records if r.get("league_id") == lg]
        tw, tl, tp = _wlp(sub)
        tr, _ = _roi_flat(tw, tl, tp)
        soc_signals.append({"name": lg, "w": tw, "l": tl, "p": tp, "roi": tr})
    for tier in ["HIGH", "MEDIUM", "LOW"]:
        sub = [r for r in soc_records if r.get("confidence_tier") == tier]
        tw, tl, tp = _wlp(sub)
        tr, _ = _roi_flat(tw, tl, tp)
        soc_signals.append({"name": f"{tier} tier", "w": tw, "l": tl, "p": tp, "roi": tr})

    s_roi, s_net = _roi_flat(sw_, sl__, sp_)
    _s_clv, _s_mw, _s_ma, _s_mn = _compute_movement(soc_records)
    _render_sport_panel("\u26bd", "Soccer", sw_, sl__, sp_, s_roi, s_net, soc_signals,
                        clv_pct=_s_clv, moved_with=_s_mw, moved_against=_s_ma, neutral=_s_mn)

    # ── Golf ──
    golf_records = []
    try:
        _golf = pd.read_parquet("golf/shadow/golf_shadow_log.parquet")
        _golf = _golf[(_golf["calendar_year"] == 2026) & (_golf["actual_result"].notna())]
        for _, r in _golf.iterrows():
            golf_records.append({
                "result": "WIN" if r["actual_result"] == 1 else "LOSS",
                "market": r.get("market", ""),
            })
    except Exception:
        pass

    gw, gl, gp = _wlp(golf_records)
    golf_signals = []
    for mkt in ["make_cut", "top_20", "top_10", "top_5", "win"]:
        sub = [r for r in golf_records if r.get("market") == mkt]
        mw_, ml_, mp_ = _wlp(sub)
        mr, _ = _roi_flat(mw_, ml_, mp_)
        golf_signals.append({"name": mkt.replace("_", " ").title(), "w": mw_, "l": ml_, "p": mp_, "roi": mr})

    g_roi, g_net = _roi_flat(gw, gl, gp)
    _render_sport_panel("\u26f3", "Golf", gw, gl, gp, g_roi, g_net, golf_signals)

    st.html('<div style="font-size:0.70em;color:#4b5563;margin-top:8px;font-style:italic">'
            'CLV > 50% = making correct bets regardless of short-term results. '
            'Lines: \u2713 = moved with signal, \u2717 = moved against, \u2014 = neutral. '
            'Movement tracked from Apr 1, 2026.</div>')


main()
# cache bust Wed Apr  2 WNBA archetype tab
