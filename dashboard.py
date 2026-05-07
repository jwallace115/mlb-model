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
from zoneinfo import ZoneInfo

import pandas as pd
import streamlit as st

_ET = ZoneInfo("America/New_York")

def _today_et() -> str:
    """Return today's date in ET as YYYY-MM-DD string."""
    return datetime.now(_ET).date().isoformat()

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



# ── shared components ─────────────────────────────────────────────────────────
from dashboard_components import (
    _pipeline_freshness,
    _global_freshness,
    _last_run_label,
    _render_game_card_universal,
    _universal_pill,
    _render_signal_status_row,
    load_nba_results as _dc_load_nba_results,
    load_nhl_results as _dc_load_nhl_results,
    load_soccer_results as _dc_load_soccer_results,
)

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
def load_golf_results() -> dict | None:
    if not os.path.exists(GOLF_RESULTS_FILE):
        return None
    with open(GOLF_RESULTS_FILE) as f:
        return json.load(f)

def load_nba_results() -> dict | None:
    return _dc_load_nba_results()

def load_nhl_results() -> dict | None:
    return _dc_load_nhl_results()

def load_soccer_results() -> dict | None:
    return _dc_load_soccer_results()


# ── stub sport tabs (rebuilding) ──────────────────────────────────────────────

def _render_mlb_tab(data: dict | None, stats: dict | None) -> None:
    import json, os
    from datetime import date, datetime
    from collections import defaultdict
    from dashboard_components import (render_status_header, _universal_pill,
                                       _render_game_card_universal,
                                       _render_signal_status_row)

    # ═══════════════════════════════════════════════════════════════════════════
    # A. SHADOW PILLS ROW
    # ═══════════════════════════════════════════════════════════════════════════
    _render_signal_status_row(
        active_labels=[],
        shadow_labels=["Night Dog", "BP Adv Dog", "P1B Cold-Warm",
                       "YRFI 1+", "YRFI 2+", "YRFI 3+", "NRFI Card (info)"],
    )

    # ═══════════════════════════════════════════════════════════════════════════
    # B. TIMESTAMP
    # ═══════════════════════════════════════════════════════════════════════════
    _mlb_lu = None
    try:
        _lu_data = json.load(open(os.path.join(os.path.dirname(__file__), "shared", "last_updated.json")))
        for _lk in ["mlb_confirm", "mlb_prelim"]:
            _lts = _lu_data.get(_lk)
            if _lts and isinstance(_lts, str) and "T" in _lts:
                from zoneinfo import ZoneInfo
                _ldt = datetime.fromisoformat(_lts.replace("Z", "+00:00"))
                _mlb_lu = _ldt.astimezone(ZoneInfo("America/New_York")).strftime("%b %-d, %-I:%M %p ET")
                break
    except Exception:
        pass
    if _mlb_lu:
        st.html(f'<div style="font-size:0.68em;color:#64748b;margin-bottom:8px">Last updated: {_mlb_lu}</div>')

    # ═══════════════════════════════════════════════════════════════════════════
    # DATA LOADERS
    # ═══════════════════════════════════════════════════════════════════════════
    _base = os.path.dirname(__file__)

    def _load_json(rel_path, key=None):
        try:
            p = os.path.join(_base, rel_path)
            if os.path.exists(p):
                raw = json.load(open(p))
                return raw.get(key, []) if key else raw
        except Exception:
            pass
        return []

    night_all = _load_json("mlb/logs/mlb_mixed_night_dog_shadow_2026.json", "signals")
    bp_all = _load_json("mlb/logs/mlb_mixed_bp_adv_dog_shadow_2026.json", "signals")
    _p1b_all = _load_json("mlb/logs/mlb_p1b_coldwarm_earlyheavy_over_shadow_2026.json", "signals")
    _yrfi_all = _load_json("mlb/logs/yrfi_shadow_2026.json")

    # NRFI selector
    _nrfi_raw = _load_json("mlb/logs/nrfi_selector_v1_2026.json", "selections")
    _nrfi_seen = set()
    _nrfi_deduped = []
    for _ns in _nrfi_raw:
        _ngpk = _ns.get("game_pk")
        if _ngpk not in _nrfi_seen:
            _nrfi_seen.add(_ngpk)
            _nrfi_deduped.append(_ns)
    top3_all = [s for s in _nrfi_deduped if s.get("selected_top3")]

    # ═══════════════════════════════════════════════════════════════════════════
    # YRFI TIER STATS HELPER
    # ═══════════════════════════════════════════════════════════════════════════
    def _yrfi_tier_stats(entries, tier_key):
        fired = [e for e in entries if e.get(tier_key) is True]
        graded = [e for e in fired if e.get("result_graded") is True]
        n_graded = len(graded)
        wins = sum(1 for e in graded if e.get("result_yrfi") == 1)
        losses = sum(1 for e in graded if e.get("result_yrfi") == 0)
        hit_rate = (wins / n_graded * 100) if n_graded > 0 else 0.0
        profit_entries = [e for e in graded if e.get("yrfi_profit_units") is not None]
        n_priced = len(profit_entries)
        profit_sum = sum((e.get("yrfi_profit_units") or 0) for e in profit_entries)
        roi = (profit_sum / n_priced * 100) if n_priced > 0 else 0.0
        month_profit = defaultdict(float)
        for e in profit_entries:
            gd = e.get("game_date", "")
            if len(gd) >= 7:
                month_profit[gd[:7]] += (e.get("yrfi_profit_units") or 0)
        months_pos = sum(1 for m in month_profit if month_profit[m] > 0)
        return {"fired_n": len(fired), "graded_n": n_graded,
                "wins": wins, "losses": losses,
                "hit_rate": hit_rate, "roi": roi, "months_positive": months_pos}

    # ═══════════════════════════════════════════════════════════════════════════
    # C. TODAY'S NRFI CARD MINI-BLOCK
    # ═══════════════════════════════════════════════════════════════════════════
    today = _today_et()
    today_top3 = sorted(
        [s for s in top3_all if s.get("run_date") == today],
        key=lambda x: x.get("selector_rank", 99),
    )
    if today_top3:
        _nrfi_legs_html = ""
        for s in today_top3:
            _rank = s.get("selector_rank", "?")
            _mu = s.get("matchup") or f"{s.get('away_team','?')} @ {s.get('home_team','?')}"
            _f5 = s.get("f5_total")
            _f5s = f"F5: {_f5:.1f}" if _f5 else "F5: \u2014"
            _nrfi_legs_html += (
                f'<div style="padding:2px 0;font-size:0.85em;color:#e2e8f0">'
                f'<span style="color:#60a5fa;font-weight:700">#{_rank}</span>'
                f'&nbsp;&nbsp;{_mu}&nbsp;&nbsp;'
                f'<span style="color:#94a3b8;font-size:0.9em">{_f5s}</span></div>'
            )
        st.html(
            f'<div style="border:1px solid #6b7280;border-radius:8px;padding:10px 14px;'
            f'background:#0f1729;margin:8px 0">'
            f'<div style="font-size:0.85em;font-weight:700;color:#e2e8f0;margin-bottom:6px">'
            f"Today's NRFI Card \u00b7 {len(today_top3)} legs \u00b7 "
            f'<span style="color:#94a3b8;font-size:0.8em">informational only</span></div>'
            f'{_nrfi_legs_html}</div>'
        )

    # ═══════════════════════════════════════════════════════════════════════════
    # D. TODAY'S MLB SLATE — PER-GAME UNIVERSAL CARDS
    # ═══════════════════════════════════════════════════════════════════════════
    st.html('<div style="font-size:0.95em;font-weight:700;color:#e2e8f0;margin:16px 0 8px 0">'
            "Today's MLB Slate</div>")

    night_today = [s for s in night_all if s.get("game_date") == today]
    bp_today = [s for s in bp_all if s.get("game_date") == today]
    p1b_today = [s for s in _p1b_all if s.get("date") == today]
    yrfi_today = [e for e in _yrfi_all
                  if e.get("game_date") == today
                  and (e.get("yrfi_1plus") or e.get("yrfi_2plus") or e.get("yrfi_3plus"))]

    game_signals = defaultdict(list)
    for sig in night_today:
        _gk = sig.get("game_pk", sig.get("game_id", ""))
        game_signals[_gk].append(("night_dog", sig))
    for sig in bp_today:
        _gk = sig.get("game_pk", sig.get("game_id", ""))
        game_signals[_gk].append(("bp_adv_dog", sig))
    for sig in p1b_today:
        _gk = sig.get("game_pk")
        if _gk:
            game_signals[_gk].append(("p1b_coldwarm", sig))
    for sig in yrfi_today:
        _gk = sig.get("game_pk", f"{sig.get('game_date')}|{sig.get('home_team')}|{sig.get('away_team')}")
        game_signals[_gk].append(("yrfi", sig))
    for sig in today_top3:
        _gk = sig.get("game_pk")
        if _gk:
            game_signals[_gk].append(("nrfi_leg", sig))

    if game_signals:
        for _gpk, _sigs in game_signals.items():
            _first = _sigs[0][1]
            _matchup = _first.get("matchup") or f"{_first.get('away_team','?')} @ {_first.get('home_team','?')}"
            _time_et = ""
            _tutc = _first.get("game_time_utc", "")
            if _tutc and len(_tutc) >= 16:
                try:
                    from zoneinfo import ZoneInfo
                    _tdt = datetime.fromisoformat(_tutc.replace("Z", "+00:00"))
                    _time_et = _tdt.astimezone(ZoneInfo("America/New_York")).strftime("%-I:%M %p ET")
                except Exception:
                    pass

            pills = []
            wagers = []
            stats_lines = []

            for _stype, _sig in _sigs:
                if _stype == "night_dog":
                    pills.append(_universal_pill("Night Dog", "#fff", "#2563eb"))
                    _dog = _sig.get("dog_team", "?")
                    _ml = _sig.get("dog_ml_price", "?")
                    wagers.append(f"{_dog} ML {_ml} \u00b7 Night Dog \u00b7 MIXED")
                elif _stype == "bp_adv_dog":
                    pills.append(_universal_pill("BP Adv Dog", "#fff", "#2563eb"))
                    _dog = _sig.get("dog_team", "?")
                    _ml = _sig.get("dog_ml_price", "?")
                    _bpd = _sig.get("dog_bp_era", 0)
                    _bpf = _sig.get("fav_bp_era", 0)
                    _bpds = f"{_bpd:.2f}" if isinstance(_bpd, (int, float)) else str(_bpd)
                    _bpfs = f"{_bpf:.2f}" if isinstance(_bpf, (int, float)) else str(_bpf)
                    wagers.append(f"{_dog} ML {_ml} \u00b7 BP Adv Dog \u00b7 BP {_bpds} vs {_bpfs}")
                elif _stype == "p1b_coldwarm":
                    pills.append(_universal_pill("P1B Cold-Warm", "#fff", "#2563eb"))
                    _fg = _sig.get("fg_total", 0)
                    _op = _sig.get("over_price", "")
                    _tmp = _sig.get("forecast_temp_f", 0)
                    _fgs = f"{_fg:.1f}" if isinstance(_fg, (int, float)) else str(_fg)
                    _tmps = f"{_tmp:.0f}" if isinstance(_tmp, (int, float)) else str(_tmp)
                    wagers.append(f"FG OVER {_fgs} {_op} \u00b7 P1B Cold-Warm \u00b7 {_tmps}\u00b0F")
                elif _stype == "nrfi_leg":
                    pills.append(_universal_pill("NRFI Card (info)", "#fff", "#6b7280"))
                    _f5v = _sig.get("f5_total")
                    _f5s = f"{_f5v:.1f}" if _f5v else "\u2014"
                    wagers.append(f"NRFI leg \u00b7 F5 total {_f5s} \u00b7 part of today's parlay card")

            # YRFI: only highest tier pill
            _yrfi_sigs_here = [s for t, s in _sigs if t == "yrfi"]
            if _yrfi_sigs_here:
                _ye = _yrfi_sigs_here[0]
                if _ye.get("yrfi_3plus"):
                    pills.append(_universal_pill("YRFI 3+ HIGH-CONV", "#fff", "#dc2626"))
                    _tl = "3+"
                elif _ye.get("yrfi_2plus"):
                    pills.append(_universal_pill("YRFI 2+ PRIMARY", "#fff", "#16a34a"))
                    _tl = "2+"
                else:
                    pills.append(_universal_pill("YRFI 1+", "#fff", "#94a3b8"))
                    _tl = "1+"
                _fdp = _ye.get("fd_yrfi_price")
                _be = _ye.get("fd_break_even")
                if _fdp is not None and isinstance(_fdp, (int, float)):
                    _bes = f" \u00b7 BE {_be*100:.1f}%" if _be else ""
                    wagers.append(f"YRFI \u00b7 FD {int(_fdp):+d} \u00b7 {_tl} consensus{_bes}")
                else:
                    wagers.append(f"YRFI \u00b7 FD price unavailable \u00b7 {_tl} consensus")
                _fsigs = _ye.get("fired_signals", [])
                if _fsigs:
                    stats_lines.append(f"Signals: {', '.join(_fsigs)}")
                _ac = (_ye.get("away_batting_context") or {}).get("signal_count", 0)
                _hc = (_ye.get("home_batting_context") or {}).get("signal_count", 0)
                _ctx = "both" if _ac > 0 and _hc > 0 else ("away" if _ac > 0 else "home")
                stats_lines.append(f"Context: {_ctx}")

            _render_game_card_universal(
                matchup=_matchup,
                time_str=_time_et,
                tier="SHADOW",
                wagers=wagers,
                pills=pills,
                stats=stats_lines if stats_lines else None,
            )
    else:
        st.html(
            '<div style="font-size:0.75em;color:#6b7280;padding:6px 12px;background:#0d1117;'
            'border-radius:4px;border:1px solid #1e293b">'
            'No MLB signals today \u2014 next slate pending</div>'
        )

    # ═══════════════════════════════════════════════════════════════════════════
    # E. TRACKER PERFORMANCE
    # ═══════════════════════════════════════════════════════════════════════════
    st.html('<hr style="border:none;border-top:2px solid #1e293b;margin:24px 0 16px 0">')
    st.html('<div style="font-size:0.95em;font-weight:700;color:#e2e8f0;margin:0 0 8px 0">'
            'Tracker Performance</div>')

    def _perf_row(label, record, hit_str, roi_str, detail, bg="#0f1729", badge_html=""):
        st.html(
            f'<div style="font-size:0.78em;color:#e2e8f0;padding:8px 12px;background:{bg};'
            f'border-radius:4px;border:1px solid #1e2d4a;margin-bottom:4px">'
            f'<span style="color:#94a3b8;font-weight:600;display:inline-block;min-width:130px">'
            f'{label}</span>{badge_html}'
            f' &nbsp;|&nbsp; <span style="font-weight:700">{record}</span>'
            f' &nbsp;|&nbsp; Hit: {hit_str}'
            f' &nbsp;|&nbsp; ROI: {roi_str}'
            f' &nbsp;|&nbsp; {detail}</div>'
        )

    # Night Dog
    _nd_res = [s for s in night_all if s.get("win_loss") in ("W", "L")]
    _nd_w = sum(1 for s in _nd_res if s.get("win_loss") == "W")
    _nd_l = len(_nd_res) - _nd_w
    _nd_pend = len(night_all) - len(_nd_res)
    _perf_row("Night Dog", f"{_nd_w}-{_nd_l}",
              f"{_nd_w/len(_nd_res)*100:.1f}%" if _nd_res else "--", "--",
              f"{len(_nd_res)} resolved, {_nd_pend} pending")

    # BP Adv Dog
    _bp_res = [s for s in bp_all if s.get("win_loss") in ("W", "L")]
    _bp_w = sum(1 for s in _bp_res if s.get("win_loss") == "W")
    _bp_l = len(_bp_res) - _bp_w
    _bp_pend = len(bp_all) - len(_bp_res)
    _perf_row("BP Adv Dog", f"{_bp_w}-{_bp_l}",
              f"{_bp_w/len(_bp_res)*100:.1f}%" if _bp_res else "--", "--",
              f"{len(_bp_res)} resolved, {_bp_pend} pending")

    # P1B Cold-Warm
    _p1b_res = [s for s in _p1b_all if s.get("result") in ("W", "L")]
    _p1b_w = sum(1 for s in _p1b_res if s.get("result") == "W")
    _p1b_l = len(_p1b_res) - _p1b_w
    _p1b_pend = len([s for s in _p1b_all if not s.get("graded")])
    _p1b_roi_u = 0.0
    _p1b_roi_n = 0
    for _ps in _p1b_res:
        _pp = _ps.get("over_price")
        if _pp and isinstance(_pp, (int, float)) and _pp != 0:
            _p1b_roi_u += (100 / abs(_pp)) if _pp < 0 else (_pp / 100) if _ps["result"] == "W" else -1
            _p1b_roi_n += 1
    _p1b_roi_s = f"{_p1b_roi_u/_p1b_roi_n*100:+.1f}%" if _p1b_roi_n > 0 else "--"
    _perf_row("P1B Cold-Warm", f"{_p1b_w}-{_p1b_l}",
              f"{_p1b_w/len(_p1b_res)*100:.1f}%" if _p1b_res else "--", _p1b_roi_s,
              f"{len(_p1b_res)} resolved (fires Jun\u2013Sep)")

    # YRFI tiers
    _badge_primary = ('<span style="background:#052e16;color:#22c55e;border:1px solid #22c55e;'
                       'border-radius:8px;padding:1px 6px;font-size:0.65em;font-weight:700;'
                       'margin-left:4px">PRIMARY</span>')
    _badge_hc = ('<span style="background:#1c0d0d;color:#dc2626;border:1px solid #dc2626;'
                  'border-radius:8px;padding:1px 6px;font-size:0.65em;font-weight:700;'
                  'margin-left:4px">HIGH-CONV</span>')

    for _tk, _tl, _badge, _gn in [
        ("yrfi_1plus", "YRFI 1+", "", None),
        ("yrfi_2plus", "YRFI 2+", _badge_primary, 100),
        ("yrfi_3plus", "YRFI 3+", _badge_hc, 50),
    ]:
        _ys = _yrfi_tier_stats(_yrfi_all, _tk)
        _yr = f'{_ys["wins"]}-{_ys["losses"]}' if _ys["graded_n"] > 0 else "0-0"
        _yh = f'{_ys["hit_rate"]:.1f}%' if _ys["graded_n"] > 0 else "--"
        _yro = f'{_ys["roi"]:+.1f}%' if _ys["graded_n"] > 0 else "--"
        _det = f'N={_ys["graded_n"]} graded'
        if _gn is not None:
            _det = f'N={_ys["graded_n"]}/{_gn} graded'
        if _tk == "yrfi_2plus":
            _det += f' \u00b7 {_ys["months_positive"]}/3 months pos'
        _perf_row(_tl, _yr, _yh, _yro, _det, badge_html=_badge)

    # NRFI Card (INFO)
    _nrfi_res = [s for s in top3_all if s.get("nrfi_result") is not None]
    _nrfi_w = sum(1 for s in _nrfi_res if s.get("win_loss") == "W")
    _nrfi_l = len(_nrfi_res) - _nrfi_w
    _nrfi_pend = len(top3_all) - len(_nrfi_res)
    _nrfi_hit = f"{_nrfi_w/len(_nrfi_res)*100:.1f}%" if _nrfi_res else "--"
    _res_dates = sorted(set(s["run_date"] for s in _nrfi_res)) if _nrfi_res else []
    _cw = sum(1 for d in _res_dates if all(s.get("win_loss") == "W" for s in _nrfi_res if s["run_date"] == d))
    _ct = len(_res_dates)
    _card_str = f"Card: {_cw}/{_ct}" if _ct > 0 else "Card: --"
    _info_badge = ('<span style="background:#1f1814;color:#94a3b8;border:1px solid #78716c;'
                    'border-radius:8px;padding:1px 6px;font-size:0.65em;font-weight:700;'
                    'margin-left:4px">INFO</span>')
    _perf_row("NRFI Card", f"{_nrfi_w}-{_nrfi_l}", f"Leg: {_nrfi_hit}",
              _card_str, f"{len(_nrfi_res)} resolved, {_nrfi_pend} pending",
              bg="#1f1814", badge_html=_info_badge)

    # ═══════════════════════════════════════════════════════════════════════════
    # F. SIGNAL DEFINITIONS EXPANDER
    # ═══════════════════════════════════════════════════════════════════════════
    with st.expander("Signal definitions", expanded=False):
        st.html(
            '<div style="font-size:0.72em;color:#94a3b8;line-height:1.7">'
            '<p><b>Night Dog:</b> Dog ML when night game \u00b7 MIXED class. Tracker started Apr 12, 2026.</p>'
            '<p><b>BP Adv Dog:</b> Dog ML when dog BP ERA &lt; fav BP ERA \u00b7 MIXED class. '
            'Tracker started Apr 12, 2026.</p>'
            '<p><b>P1B Cold-Warm:</b> Full-game OVER when EARLY_HEAVY scoring + cold park + '
            'temp \u226575\u00b0F + Jun\u2013Sep + over \u2264-105. Fires Jun\u2013Sep only.</p>'
            '<p><b>YRFI Robust V1:</b> 6 launch-angle/contact signals. Three tiers '
            '(1+/2+/3+ unique signals fired). Market: FanDuel YRFI. Tracker started May 7, 2026.<br>'
            'Promotion gates \u2014 2+: N\u2265100, ROI &gt; +5%, hit rate &gt; BE +3pp, '
            '3+ months positive. 3+: N\u226550, ROI &gt; +8%, hit rate &gt; BE +5pp.</p>'
            '<p><b>NRFI Card:</b> F5 total \u22644.0, top 3 daily picks. INFORMATIONAL ONLY \u2014 '
            'F5\u22644.0 produces 59.3% NRFI; market prices at -150 (BE 59.9%); edge -0.6pp. '
            'Use as parlay filter, not capital-deployable signal.</p>'
            '</div>'
        )


def _render_nba_tab() -> None:
    import json, os
    from datetime import date, datetime
    import pandas as pd
    from dashboard_components import (render_status_header, _universal_pill,
                                       _render_game_card_universal, _pipeline_freshness)

    # --- 1. LOAD TIMESTAMPS ---
    lu = None
    try:
        lu_path = os.path.join(os.path.dirname(__file__), "shared", "last_updated.json")
        lu_data = json.load(open(lu_path))
        nba_ts = lu_data.get("nba")
        if nba_ts:
            from zoneinfo import ZoneInfo
            dt = datetime.fromisoformat(nba_ts.replace("Z", "+00:00"))
            lu = dt.astimezone(ZoneInfo("America/New_York")).strftime("%b %-d, %-I:%M %p ET")
    except Exception:
        pass

    # --- 2. STATUS HEADERS ---
    render_status_header(
        object_name="\U0001f3c0 NBA Road Warrior Model",
        object_id="nba_road_warrior_20260322",
        status="LIVE",
        tracker_start="March 22, 2026",
        current_threshold="venue + archetype qualifying",
        replaces="NBA Base Model \u2014 archived March 2026",
        last_updated=lu,
    )

    render_status_header(
        object_name="\U0001f3c0 NBA Referee Under",
        object_id="nba_ref_under_20260322",
        status="SHADOW",
        tracker_start="March 22, 2026",
        current_threshold="ref crew match + 0.75u flat",
        last_updated=lu,
    )

    # --- 3. LOAD SIGNAL LOG ---
    log_path = os.path.join(os.path.dirname(__file__), "nba", "data", "nba_signal_log.parquet")
    signal_log = pd.DataFrame()
    try:
        if os.path.exists(log_path):
            signal_log = pd.read_parquet(log_path)
    except Exception:
        pass

    # --- 4. SIGNAL STATUS PILLS ---
    rw_signals = signal_log[signal_log["signal_type"].str.contains("ROAD_WARRIOR", na=False)] if len(signal_log) else pd.DataFrame()
    ref_signals = signal_log[signal_log["signal_type"].str.contains("REF_UNDER", na=False)] if len(signal_log) else pd.DataFrame()
    oreb_signals = signal_log[signal_log["signal_type"].str.contains("OREB_CONFIRMS", na=False)] if len(signal_log) else pd.DataFrame()

    active_pills = []
    if len(rw_signals):
        rw_tiers = set(rw_signals["tier"].dropna().unique())
        active_pills.append(_universal_pill("Road Warrior", "#fff", "#16a34a"))
        for t in ["TIER_1A", "TIER_1B", "TIER_2"]:
            if t in rw_tiers:
                active_pills.append(_universal_pill(t, "#fff", "#dc2626"))

    if active_pills:
        pill_html = "".join(active_pills)
        st.html(
            '<div style="margin:8px 0">'
            '<span style="color:#22c55e;font-size:0.68em;font-weight:600;margin-right:6px">'
            '\u25cf Active</span>' + pill_html + '</div>'
        )

    shadow_pills = []
    if len(ref_signals):
        shadow_pills.append(_universal_pill("Ref Under", "#fff", "#2563eb"))
    if len(oreb_signals):
        shadow_pills.append(_universal_pill("OREB Confirms", "#fff", "#2563eb"))

    if shadow_pills:
        pill_html = "".join(shadow_pills)
        st.html(
            '<div style="margin:8px 0">'
            '<span style="color:#64748b;font-size:0.68em;font-weight:600;margin-right:6px">'
            '\u25d0 Shadow</span>' + pill_html + '</div>'
        )

    # --- 5. ARCHETYPE RULES BLOCK ---
    rules_html = (
        '<div style="font-size:0.72em;color:#94a3b8;padding:8px 12px;background:#0d1117;'
        'border-radius:4px;border:1px solid #1e293b;margin:8px 0">'
        '<div style="font-weight:600;color:#78716c;margin-bottom:4px">Active Signal Archetypes</div>'
        '<div><b>ROAD_WARRIOR_at_STRONG_HOME</b>: venue_signal + away team qualifies &rarr; OVER</div>'
        '<div style="margin-top:2px">TIER_1A: 1.5u &nbsp;|&nbsp; TIER_1B: 1.5u &nbsp;|&nbsp; TIER_2: 1.0u</div>'
        '<div style="color:#4b5563;margin-top:4px">'
        'Shadow: REF_UNDER (0.75u flat) &nbsp;|&nbsp; OREB_CONFIRMS &nbsp;|&nbsp; BALANCED_vs_PASSIVE</div>'
        '</div>'
    )
    st.html(rules_html)

    # --- 6. TODAY'S SIGNALS ---
    today_str = _today_et()
    results_path = os.path.join(os.path.dirname(__file__), "nba_results.json")
    today_plays = []
    nba_meta = {}
    try:
        if os.path.exists(results_path):
            nba_meta = json.load(open(results_path))
            today_plays = nba_meta.get("plays", [])
    except Exception:
        pass

    # Also check signal log for today
    today_from_log = signal_log[signal_log["game_date"] == today_str] if len(signal_log) and "game_date" in signal_log.columns else pd.DataFrame()

    st.html(
        '<div style="font-size:0.85em;font-weight:700;color:#e2e8f0;margin:12px 0 6px 0">'
        "Today's Signals</div>"
    )

    if len(today_plays):
        for p in today_plays:
            away = p.get("away_team", "?")
            home = p.get("home_team", "?")
            matchup = f"{away} @ {home}"
            tier = p.get("tier", p.get("confidence", ""))
            side = p.get("signal_side", p.get("lean", ""))
            line = p.get("line", p.get("closing_line", "?"))
            edge = p.get("edge", 0)
            pred = p.get("pred_total", "?")

            stake_map = {"TIER_1A": "1.5u", "TIER_1B": "1.5u", "TIER_2": "1.0u"}
            stake = stake_map.get(tier, "0.75u")
            wagers = [f"{side} {line} \u00b7 {stake}"]
            pills = [_universal_pill(tier, "#fff", "#dc2626")]

            stats_list = []
            if pred and pred != "?":
                stats_list.append(f"Model: {pred:.1f}" if isinstance(pred, (int, float)) else f"Model: {pred}")
            if edge:
                stats_list.append(f"Edge: {edge:.1f}" if isinstance(edge, (int, float)) else f"Edge: {edge}")

            _render_game_card_universal(
                matchup=matchup,
                time_str="",
                tier=tier,
                wagers=wagers,
                pills=pills,
                stats=stats_list,
            )
    elif len(today_from_log):
        for _, row in today_from_log.iterrows():
            away = row.get("away_team", "?")
            home = row.get("home_team", "?")
            matchup = f"{away} @ {home}"
            tier = row.get("tier", "")
            side = row.get("direction", "")
            line = row.get("closing_line", "?")
            sig_type = row.get("signal_type", "")

            stake_map = {"TIER_1A": "1.5u", "TIER_1B": "1.5u", "TIER_2": "1.0u", "REF_UNDER": "0.75u"}
            stake = stake_map.get(tier, "0.5u")
            wagers = [f"{side} {line} \u00b7 {stake}"]

            is_rw = "ROAD_WARRIOR" in sig_type
            pill_bg = "#dc2626" if is_rw else "#2563eb"
            pill_label = tier if is_rw else "REF_UNDER"
            pills = [_universal_pill(pill_label, "#fff", pill_bg)]

            disclaimer = None if is_rw else "Shadow signal \u2014 not a live wager"
            _render_game_card_universal(
                matchup=matchup,
                time_str="",
                tier="SHADOW" if not is_rw else tier,
                wagers=wagers,
                pills=pills,
                stats=[f"Type: {sig_type}"],
                disclaimer=disclaimer,
            )
    else:
        st.html(
            '<div style="font-size:0.75em;color:#6b7280;padding:6px 12px;background:#0d1117;'
            'border-radius:4px;border:1px solid #1e293b">'
            'No signals today \u2014 next slate pending</div>'
        )

    # --- 7. ROAD WARRIOR TRACKER ---
    st.html(
        '<div style="font-size:0.85em;font-weight:700;color:#e2e8f0;margin:16px 0 6px 0">'
        'Road Warrior Tracker</div>'
    )

    rw_resolved = rw_signals[rw_signals["result"].isin(["WIN", "LOSS", "PUSH"])] if len(rw_signals) else pd.DataFrame()
    rw_wins = int((rw_resolved["result"] == "WIN").sum()) if len(rw_resolved) else 0
    rw_losses = int((rw_resolved["result"] == "LOSS").sum()) if len(rw_resolved) else 0
    rw_pushes = int((rw_resolved["result"] == "PUSH").sum()) if len(rw_resolved) else 0
    rw_n = rw_wins + rw_losses
    rw_pnl = float(rw_resolved["units_won_lost"].sum()) if len(rw_resolved) and "units_won_lost" in rw_resolved.columns else 0
    rw_staked = float(rw_resolved["units"].sum()) if len(rw_resolved) and "units" in rw_resolved.columns else 0
    rw_roi = (rw_pnl / rw_staked * 100) if rw_staked > 0 else 0
    rw_hit = (rw_wins / rw_n * 100) if rw_n > 0 else 0

    st.html(
        f'<div style="font-size:0.78em;color:#e2e8f0;padding:8px 12px;background:#0f1729;'
        f'border-radius:4px;border:1px solid #1e2d4a;margin-bottom:8px">'
        f'<span style="font-weight:700">{rw_wins}-{rw_losses}-{rw_pushes}</span>'
        f' &nbsp;|&nbsp; Hit: {rw_hit:.1f}% &nbsp;|&nbsp; ROI: {rw_roi:+.1f}%'
        f' &nbsp;|&nbsp; P&L: {rw_pnl:+.2f}u'
        f' &nbsp;|&nbsp; {len(rw_signals) - len(rw_resolved)} pending'
        f'</div>'
    )

    if len(rw_signals):
        rows = []
        for _, s in rw_signals.iterrows():
            rows.append({
                "Date": s.get("game_date", ""),
                "Matchup": f"{s.get('away_team', '?')}@{s.get('home_team', '?')}",
                "Tier": s.get("tier", ""),
                "Dir": s.get("direction", ""),
                "Line": s.get("closing_line", ""),
                "Units": s.get("units", ""),
                "Result": s.get("result", "pending") if pd.notna(s.get("result")) else "pending",
                "P&L": f"{s['units_won_lost']:+.2f}" if pd.notna(s.get("units_won_lost")) else "",
            })
        df_rw = pd.DataFrame(rows)
        st.dataframe(df_rw, use_container_width=True, hide_index=True)

    # --- 8. REF UNDER SHADOW TRACKER ---
    st.html(
        '<div style="font-size:0.85em;font-weight:700;color:#e2e8f0;margin:16px 0 6px 0">'
        'Referee Under Shadow Tracker</div>'
    )

    ref_resolved = ref_signals[ref_signals["result"].isin(["WIN", "LOSS", "PUSH"])] if len(ref_signals) else pd.DataFrame()
    ref_wins = int((ref_resolved["result"] == "WIN").sum()) if len(ref_resolved) else 0
    ref_losses = int((ref_resolved["result"] == "LOSS").sum()) if len(ref_resolved) else 0
    ref_pushes = int((ref_resolved["result"] == "PUSH").sum()) if len(ref_resolved) else 0
    ref_n = ref_wins + ref_losses
    ref_pnl = float(ref_resolved["units_won_lost"].sum()) if len(ref_resolved) and "units_won_lost" in ref_resolved.columns else 0
    ref_staked = float(ref_resolved["units"].sum()) if len(ref_resolved) and "units" in ref_resolved.columns else 0
    ref_roi = (ref_pnl / ref_staked * 100) if ref_staked > 0 else 0
    ref_hit = (ref_wins / ref_n * 100) if ref_n > 0 else 0

    st.html(
        f'<div style="font-size:0.78em;color:#e2e8f0;padding:8px 12px;background:#0f1729;'
        f'border-radius:4px;border:1px solid #1e2d4a;margin-bottom:8px">'
        f'<span style="font-weight:700">{ref_wins}-{ref_losses}-{ref_pushes}</span>'
        f' &nbsp;|&nbsp; Hit: {ref_hit:.1f}% &nbsp;|&nbsp; ROI: {ref_roi:+.1f}%'
        f' &nbsp;|&nbsp; P&L: {ref_pnl:+.2f}u (shadow)'
        f' &nbsp;|&nbsp; {len(ref_signals) - len(ref_resolved)} pending'
        f'</div>'
    )

    if len(ref_signals):
        rows = []
        for _, s in ref_signals.iterrows():
            rows.append({
                "Date": s.get("game_date", ""),
                "Matchup": f"{s.get('away_team', '?')}@{s.get('home_team', '?')}",
                "Dir": s.get("direction", ""),
                "Line": s.get("closing_line", ""),
                "Result": s.get("result", "pending") if pd.notna(s.get("result")) else "pending",
                "P&L": f"{s['units_won_lost']:+.2f}" if pd.notna(s.get("units_won_lost")) else "",
            })
        df_ref = pd.DataFrame(rows)
        st.dataframe(df_ref, use_container_width=True, hide_index=True)

    # --- 9. SEASON ACCURACY BLOCK ---
    season_acc = nba_meta.get("season_accuracy", {})
    if season_acc:
        overall = season_acc.get("overall", {})
        st.html(
            '<div style="font-size:0.85em;font-weight:700;color:#e2e8f0;margin:16px 0 6px 0">'
            'Core Model Accuracy</div>'
        )
        n_games = overall.get("n", 0)
        mae = overall.get("mae", 0)
        hr = overall.get("hr", 0)
        bias = overall.get("bias", 0)
        st.html(
            f'<div style="font-size:0.78em;color:#e2e8f0;padding:8px 12px;background:#0f1729;'
            f'border-radius:4px;border:1px solid #1e2d4a;margin-bottom:8px">'
            f'{n_games} games graded &nbsp;|&nbsp; MAE: {mae:.1f} &nbsp;|&nbsp; '
            f'Hit rate: {hr:.1f}% &nbsp;|&nbsp; Bias: {bias:+.1f}'
            f'</div>'
        )

    # --- 10. LEGACY DISCLOSURE ---
    st.html(
        '<hr style="border:none;border-top:1px solid #1e293b;margin:20px 0 12px 0">'
        '<div style="font-size:0.68em;color:#4b5563;padding:6px 12px;background:#0a0a0a;'
        'border-radius:4px;border:1px solid #1a1a1a">'
        '<div style="font-weight:600;margin-bottom:3px">'
        'NBA Base Model \u2014 Archived March 2026</div>'
        'Prior full-game totals model (ridge-based) was retired in favor of '
        'archetype-driven signal detection. Legacy W-L record and ROI figures '
        'belong to a different model object and are excluded from current metrics. '
        'Archived archetypes: PLAYOFF_BOARDS (inactive, monitoring only).'
        '</div>'
    )



def _render_nhl_tab() -> None:
    import json, os
    from datetime import date, datetime
    from dashboard_components import (render_status_header, _universal_pill,
                                       _render_game_card_universal, _pipeline_freshness)

    # --- 1. STATUS HEADER ---
    lu = None
    try:
        lu_path = os.path.join(os.path.dirname(__file__), "shared", "last_updated.json")
        lu_data = json.load(open(lu_path))
        nhl_ts = lu_data.get("nhl")
        if nhl_ts:
            from zoneinfo import ZoneInfo
            dt = datetime.fromisoformat(nhl_ts.replace("Z", "+00:00"))
            lu = dt.astimezone(ZoneInfo("America/New_York")).strftime("%b %-d, %-I:%M %p ET")
    except Exception:
        pass

    render_status_header(
        object_name="\U0001f3d2 NHL Aligned Model A",
        object_id="nhl_shadow_aligned_20260411",
        status="SHADOW",
        tracker_start="April 11, 2026",
        current_threshold="edge \u2265 0.12",
        replaces="NHL Legacy System \u2014 archived April 2026",
        last_updated=lu,
    )

    # --- 2. LOAD SHADOW DATA ---
    shadow_path = os.path.join(os.path.dirname(__file__), "nhl", "logs", "nhl_shadow_aligned_2026.json")
    shadow_data = []
    try:
        if os.path.exists(shadow_path):
            raw = json.load(open(shadow_path))
            if isinstance(raw, dict) and "signals" in raw:
                shadow_data = raw["signals"]
            elif isinstance(raw, list):
                shadow_data = raw
    except Exception:
        pass

    # Dedup by game_id (prevents multiple pipeline runs from inflating counts)
    _seen_gpk = set()
    _deduped = []
    for _s in shadow_data:
        _gpk = _s.get("game_id", _s.get("game_pk"))
        if _gpk not in _seen_gpk:
            _seen_gpk.add(_gpk)
            _deduped.append(_s)
    shadow_data = _deduped

    # --- 3. SIGNAL STATUS ROW ---
    fired_tiers = set()
    for s in shadow_data:
        tier = s.get("tier", "")
        clean = tier.replace("SHADOW_", "")
        if clean:
            fired_tiers.add(clean)

    shadow_pills = [_universal_pill("Model A", "#fff", "#2563eb")]
    for tier_name in ["HIGH", "MEDIUM", "LOW"]:
        if tier_name in fired_tiers:
            shadow_pills.append(_universal_pill(tier_name, "#fff", "#dc2626"))

    if shadow_pills:
        pill_html = "".join(shadow_pills)
        st.html(
            '<div style="margin:8px 0">'
            '<span style="color:#64748b;font-size:0.68em;font-weight:600;margin-right:6px">'
            '\u25d0 Shadow</span>' + pill_html + '</div>'
        )
    else:
        st.html(
            '<div style="font-size:0.72em;color:#6b7280;margin:8px 0">'
            '\u25d0 Shadow \u2014 No shadow signals yet, monitoring active</div>'
        )

    # --- 4. SHADOW RULES BLOCK ---
    rules_html = (
        '<div style="font-size:0.72em;color:#94a3b8;padding:8px 12px;background:#0d1117;'
        'border-radius:4px;border:1px solid #1e293b;margin:8px 0">'
        '<div style="font-weight:600;color:#78716c;margin-bottom:4px">Active Shadow Ruleset</div>'
        '<div>Drift correction: disabled (0.0)</div>'
        '<div>Fire threshold: edge \u2265 0.12</div>'
        '<div>HIGH: edge \u2265 0.40 \u2192 1.0u &nbsp;|&nbsp; '
        'MEDIUM: edge \u2265 0.20 \u2192 0.5u &nbsp;|&nbsp; '
        'LOW: edge \u2265 0.12 \u2192 0.5u</div>'
        '<div style="color:#4b5563;margin-top:4px">'
        'Legacy disabled: MoneyPuck paths, drift (+0.4458), push corrections</div>'
        '</div>'
    )
    st.html(rules_html)

    # --- 5. TODAY'S GAMES ---
    today = _today_et()
    today_signals = [s for s in shadow_data if s.get("game_date", "") == today]

    st.html(
        '<div style="font-size:0.85em;font-weight:700;color:#e2e8f0;margin:12px 0 6px 0">'
        "Today's Signals</div>"
    )

    if today_signals:
        for sig in today_signals:
            away = sig.get("away_team", "?")
            home = sig.get("home_team", "?")
            matchup = f"{away} @ {home}"
            tier_raw = sig.get("tier", "LOW").replace("SHADOW_", "")
            edge = sig.get("edge", 0)
            direction = sig.get("signal_side", "UNDER")
            total = sig.get("closing_total", "?")
            pred = sig.get("lambda_total", "?")
            stake = "1.0u" if tier_raw == "HIGH" else "0.5u"

            wagers = [f"{direction} {total} \u00b7 {stake} shadow"]
            pills = [_universal_pill(tier_raw, "#fff", "#dc2626")]
            stats_list = []
            if pred and pred != "?":
                if isinstance(pred, (int, float)):
                    stats_list.append(f"Model: {pred:.2f}")
                else:
                    stats_list.append(f"Model: {pred}")
            if edge:
                if isinstance(edge, (int, float)):
                    stats_list.append(f"Edge: {edge:.3f}")
                else:
                    stats_list.append(f"Edge: {edge}")
            if total and total != "?":
                stats_list.append(f"Close: {total}")

            _render_game_card_universal(
                matchup=matchup,
                time_str="",
                tier="SHADOW",
                wagers=wagers,
                pills=pills,
                stats=stats_list,
                disclaimer="Research shadow \u2014 not a live wager recommendation",
            )
    else:
        st.html(
            '<div style="font-size:0.75em;color:#6b7280;padding:6px 12px;background:#0d1117;'
            'border-radius:4px;border:1px solid #1e293b">'
            'No signals today \u2014 next slate pending</div>'
        )

    # --- 6. SHADOW TRACKER SUMMARY ---
    st.html(
        '<div style="font-size:0.85em;font-weight:700;color:#e2e8f0;margin:16px 0 6px 0">'
        'Shadow Tracker \u2014 New Object (started April 11, 2026)</div>'
    )

    resolved = [s for s in shadow_data if s.get("result") in ("WIN", "LOSS", "PUSH")]
    wins = sum(1 for s in resolved if s.get("result") == "WIN")
    losses = sum(1 for s in resolved if s.get("result") == "LOSS")
    pushes = sum(1 for s in resolved if s.get("result") == "PUSH")
    n = wins + losses
    roi = ((wins - losses) / n * 100 / 1.1) if n > 0 else 0
    hit = (wins / n * 100) if n > 0 else 0

    st.html(
        f'<div style="font-size:0.78em;color:#e2e8f0;padding:8px 12px;background:#0f1729;'
        f'border-radius:4px;border:1px solid #1e2d4a;margin-bottom:8px">'
        f'<span style="font-weight:700">{wins}-{losses}-{pushes}</span>'
        f' &nbsp;|&nbsp; Hit: {hit:.1f}% &nbsp;|&nbsp; ROI: {roi:+.1f}% (flat -110)'
        f' &nbsp;|&nbsp; N: {len(resolved)} resolved, '
        f'{len(shadow_data) - len(resolved)} pending'
        f'</div>'
    )

    # Signal table
    if shadow_data:
        import pandas as pd
        rows = []
        for s in shadow_data:
            away = s.get("away_team", "?")
            home = s.get("home_team", "?")
            edge_val = s.get("edge")
            edge_str = f"{edge_val:.3f}" if isinstance(edge_val, (int, float)) else ""
            rows.append({
                "Date": s.get("game_date", ""),
                "Matchup": f"{away}@{home}",
                "Dir": s.get("signal_side", ""),
                "Total": s.get("closing_total", ""),
                "Edge": edge_str,
                "Tier": s.get("tier", "").replace("SHADOW_", ""),
                "Result": s.get("result", "pending"),
            })
        df = pd.DataFrame(rows)
        st.dataframe(df, use_container_width=True, hide_index=True)

    # --- 7. LEGACY DISCLOSURE ---
    st.html(
        '<hr style="border:none;border-top:1px solid #1e293b;margin:20px 0 12px 0">'
        '<div style="font-size:0.68em;color:#4b5563;padding:6px 12px;background:#0a0a0a;'
        'border-radius:4px;border:1px solid #1a1a1a">'
        '<div style="font-weight:600;margin-bottom:3px">'
        'Legacy NHL System \u2014 Archived April 2026</div>'
        'Prior W-L record (12-7 HIGH tier) belongs to a different model object '
        'that used MoneyPuck-dependent features and stale priors. '
        'Legacy results are not comparable to current shadow object and are '
        'excluded from all current metrics.'
        '</div>'
    )


def _render_soccer_tab() -> None:
    st.markdown("---")
    st.markdown("**System reset \u2014 rebuilding.**")


def _render_nfl_tab() -> None:
    st.markdown("---")
    st.markdown("**System reset \u2014 rebuilding.**")


def _render_wnba_archetype_tab() -> None:
    st.markdown("---")
    st.markdown("**System reset \u2014 rebuilding.**")


def _render_ncaaf_portal_tab() -> None:
    st.markdown("---")
    st.markdown("**System reset \u2014 rebuilding.**")


# ── Home tab ──────────────────────────────────────────────────────────────────

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
    _today = _today_et()
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

    _dow = datetime.now(_ET).weekday()  # 0=Mon, 1=Tue, 3=Thu, 4=Fri
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



# ── Golf tab (preserved exactly) ───────────────────────────────────────────────

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



# ── main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    data  = load_results()
    stats = load_season_stats()

    # ── page header
    col_title, col_btn = st.columns([5, 1])
    with col_title:
        st.html(
            f"<h3 style='margin:0 0 4px 0'>\u26be I Am Not Uncertain</h3>"
        )
        st.html(_global_freshness())
    with col_btn:
        st.write("")
        if st.button("\U0001f504 Refresh", use_container_width=True):
            st.cache_data.clear()
            st.rerun()

    # ── health status banner
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

    # ── sport tabs
    tab_home, tab_mlb, tab_nba, tab_nhl, tab_soccer, tab_nfl, tab_golf, tab_wnba_arch, tab_ncaaf = st.tabs(
        ["\U0001f3e0", "\u26be MLB", "\U0001f3c0 NBA", "\U0001f3d2 NHL", "\u26bd Soccer", "\U0001f3c8 NFL", "\u26f3 Golf", "\U0001f3c0 WNBA", "\U0001f3c8 NCAAF"])

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


main()
# cache bust Fri Apr 11 site reset — modular refactor applied
