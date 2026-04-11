#!/usr/bin/env python3
"""
Site Reset Dashboard Patch — 2026-04-11
Applies state model changes to dashboard.py without modifying model logic.

Changes:
1. MLB game card pills: V1 -> legacy amber, F5 -> inactive, S12/P09 -> archived
2. MLB consolidated panel: restructure to 4 states (Active/Shadow/Inactive/Archived)
3. MLB season banner: add "Legacy — Unvalidated" disclaimer to V1 record
4. NHL season performance: add "ARCHIVED — Legacy System" label
5. Tracker tab: add disclaimers to MLB V1 and NHL sections
"""

import re
import sys

DASHBOARD = "/root/mlb-model/dashboard.py"

with open(DASHBOARD, "r") as f:
    content = f.read()

original = content  # for verification

# ═══════════════════════════════════════════════════════════════════════════════
# 1. MLB game card pills — V1, F5, S12, P09
# ═══════════════════════════════════════════════════════════════════════════════

# V1: green -> legacy amber
content = content.replace(
    '_green_mods.append(_mpill("V1", "#22c55e", "#052e16"))',
    '_green_mods.append(_mpill("V1 Legacy", "#f59e0b", "#1c1400"))'
)

# F5 engine: green -> inactive gray
content = content.replace(
    '_green_mods.append(_mpill("F5 engine", "#22c55e", "#052e16"))',
    '_yellow_mods.append(_mpill("F5 Inactive", "#6b7280", "#1a1a2e"))'
)

# S12: green -> archived gray
content = content.replace(
    '_green_mods.append(_mpill("S12", "#22c55e", "#052e16"))',
    '_yellow_mods.append(_mpill("S12 Archived", "#6b7280", "#1a1a2e"))'
)

# P09: green -> archived gray
content = content.replace(
    '_green_mods.append(_mpill("P09", "#22c55e", "#052e16"))',
    '_yellow_mods.append(_mpill("P09 Archived", "#6b7280", "#1a1a2e"))'
)

# F5 RL Signal B: keep green but relabel
content = content.replace(
    '_green_mods.append(_mpill("F5 RL Signal B", "#22c55e", "#052e16"))',
    '_green_mods.append(_mpill("Signal B (F5 RL)", "#22c55e", "#052e16"))'
)

print("[1/7] Game card pills updated")

# ═══════════════════════════════════════════════════════════════════════════════
# 2. Consolidated engine panel — restructure to 4 categories
# ═══════════════════════════════════════════════════════════════════════════════

old_panel_start = "        # GREEN — active engines"
old_panel_end = """        if _html_parts:
            st.html(f'<div style="margin-bottom:8px;line-height:2">{"".join(_html_parts)}</div>')"""

# Find and replace the panel section
panel_start_idx = content.find(old_panel_start)
panel_end_idx = content.find(old_panel_end)
if panel_start_idx == -1 or panel_end_idx == -1:
    print("WARNING: Could not find consolidated panel boundaries")
else:
    panel_end_idx += len(old_panel_end)

    new_panel = """        # GREEN — active engines (only Signal B / F5 Run Line remains active)
        _green_pills = []
        _rls = os.path.join(_status_base, "pipeline", "f5_runline_status.json")
        if os.path.exists(_rls):
            import json as _json_st
            with open(_rls) as _rlsf:
                if _json_st.load(_rlsf).get("status") != "PAUSED":
                    _green_pills.append(_pill("Signal B (F5 RL)", "#22c55e", "#052e16"))

        # YELLOW — shadow monitors
        _yellow_pills = [
            _pill("CS013 bullpen", "#eab308", "#1c1400"),
            _pill("CS028 blowup", "#eab308", "#1c1400"),
            _pill("KP04 K-prop", "#eab308", "#1c1400"),
            _pill("ST02 road", "#eab308", "#1c1400"),
            _pill("CS004", "#eab308", "#1c1400"),
            _pill("BASE_HIGH", "#eab308", "#1c1400"),
            _pill("S12_HIGH", "#eab308", "#1c1400"),
        ]

        # GRAY — inactive (slot preserved, not deployable)
        _gray_pills = [
            _pill("F5 Totals", "#6b7280", "#1a1a2e"),
            _pill("ADJ Hard Hit", "#6b7280", "#1a1a2e"),
            _pill("ADJ Contact", "#6b7280", "#1a1a2e"),
            _pill("ADJ K-rate", "#6b7280", "#1a1a2e"),
            _pill("ADJ BB rate", "#6b7280", "#1a1a2e"),
            _pill("ADJ Run Supp", "#6b7280", "#1a1a2e"),
        ]

        # DIM — archived (legacy, historical only)
        _arch_pills = [
            _pill("V1 Totals", "#94a3b8", "#0f0f1a"),
            _pill("S12 overlay", "#94a3b8", "#0f0f1a"),
            _pill("P09 overlay", "#94a3b8", "#0f0f1a"),
            _pill("Team Totals", "#94a3b8", "#0f0f1a"),
        ]

        _html_parts = []
        if _green_pills:
            _html_parts.append(
                '<span style="color:#22c55e;font-size:0.65em;font-weight:600;margin-right:6px">'
                '\\u25cf Active</span>' + "".join(_green_pills))
        if _yellow_pills:
            _html_parts.append(
                '<span style="color:#eab308;font-size:0.65em;font-weight:600;margin-right:6px;'
                'margin-left:8px">\\u25d0 Shadow</span>' + "".join(_yellow_pills))
        if _gray_pills:
            _html_parts.append(
                '<span style="color:#6b7280;font-size:0.65em;font-weight:600;margin-right:6px;'
                'margin-left:8px">\\u25cb Inactive</span>' + "".join(_gray_pills))
        if _arch_pills:
            _html_parts.append(
                '<span style="color:#4b5563;font-size:0.65em;font-weight:600;margin-right:6px;'
                'margin-left:8px">\\u25a1 Archived</span>' + "".join(_arch_pills))
        if _html_parts:
            st.html(f'<div style="margin-bottom:8px;line-height:2">{"".join(_html_parts)}</div>')"""

    content = content[:panel_start_idx] + new_panel + content[panel_end_idx:]
    print("[2/7] Consolidated panel restructured")

# ═══════════════════════════════════════════════════════════════════════════════
# 3. MLB season banner — add V1 legacy disclaimer
# ═══════════════════════════════════════════════════════════════════════════════

# Find the "Live Production" banner and add disclaimer after it
old_live_prod = "f'\\U0001f4ca Live Production (Mar 30+): '"
new_live_prod = "f'\\U0001f4ca Production Record (Mar 30+): '"
content = content.replace(old_live_prod, new_live_prod)

# Add disclaimer after the hard stop monitor section
old_hs_end = """                st.html(f'<div style="font-size:0.68em;color:#6b7280;margin-bottom:6px">'
                        f'V1 hard stop: <span style="color:{_hs_clr}">{_v1roi:+.1f}%</span>'
                        f' / \\u22128.0% threshold | {_v1n}/50 signals</div>')"""
new_hs_end = old_hs_end + """

            # V1 legacy disclaimer
            st.html('<div style="font-size:0.68em;color:#78716c;margin-bottom:6px;'
                    'padding:4px 8px;background:#1a1a1a;border-radius:4px;border:1px solid #333">'
                    '\\u26a0\\ufe0f V1 historical validation void (Apr 11 reset). '
                    'Engine runs for research continuity. Record shown is unvalidated legacy data.</div>')"""

content = content.replace(old_hs_end, new_hs_end)
print("[3/7] MLB season banner disclaimer added")

# ═══════════════════════════════════════════════════════════════════════════════
# 4. NHL Season Performance — add ARCHIVED label
# ═══════════════════════════════════════════════════════════════════════════════

content = content.replace(
    """st.html('<div class="section-hdr">\\U0001f4ca Season Performance (Historical Backtest)</div>')""",
    """st.html('<div class="section-hdr">\\U0001f4ca Season Performance (Historical Backtest)</div>'
                '<div style="font-size:0.72em;color:#78716c;margin-bottom:6px;'
                'padding:4px 8px;background:#1a1a1a;border-radius:4px;border:1px solid #333">'
                'ARCHIVED \\u2014 Legacy System (MoneyPuck-dependent). '
                'Identity broken Apr 11. New aligned Model A tracker starts fresh.</div>')"""
)
print("[4/7] NHL season performance archived label added")

# ═══════════════════════════════════════════════════════════════════════════════
# 5. NHL 14-day results banner — add legacy notice
# ═══════════════════════════════════════════════════════════════════════════════

# Add note above the NHL recent results W-L-P banner
old_nhl_banner = """    if recent_results:
        W = sum(1 for r in recent_results if r.get("result") == "WIN")
        L = sum(1 for r in recent_results if r.get("result") == "LOSS")
        P = sum(1 for r in recent_results if r.get("result") == "PUSH")
        n = W + L + P
        hit = W / (W + L) if (W + L) > 0 else None
        roi = (W * (100.0 / 110.0) - L) / n * 100 if n > 0 else None"""

new_nhl_banner = """    st.html('<div style="font-size:0.68em;color:#78716c;margin-bottom:4px;'
            'padding:3px 8px;background:#1a1a1a;border-radius:4px;border:1px solid #2d2d44">'
            'NHL Model A aligned \\u2014 new shadow tracker. '
            'Legacy record below is from pre-reset system.</div>')

    if recent_results:
        W = sum(1 for r in recent_results if r.get("result") == "WIN")
        L = sum(1 for r in recent_results if r.get("result") == "LOSS")
        P = sum(1 for r in recent_results if r.get("result") == "PUSH")
        n = W + L + P
        hit = W / (W + L) if (W + L) > 0 else None
        roi = (W * (100.0 / 110.0) - L) / n * 100 if n > 0 else None"""

content = content.replace(old_nhl_banner, new_nhl_banner)
print("[5/7] NHL results banner legacy notice added")

# ═══════════════════════════════════════════════════════════════════════════════
# 6. Tracker tab — MLB V1 label change
# ═══════════════════════════════════════════════════════════════════════════════

# Change "V1 UNDER" to "V1 UNDER (Legacy)" in tracker
content = content.replace(
    'mlb_signals.append({"name": "V1 UNDER"',
    'mlb_signals.append({"name": "V1 Legacy"'
)

# Change "S12 overlay" and "P09 overlay" tracker labels
content = content.replace(
    'mlb_signals.append({"name": "S12 overlay"',
    'mlb_signals.append({"name": "S12 Archived"'
)
content = content.replace(
    'mlb_signals.append({"name": "P09 overlay"',
    'mlb_signals.append({"name": "P09 Archived"'
)

# Change "F5 Run Line" to "Signal B (F5 RL)" in tracker
content = content.replace(
    'mlb_signals.append({"name": "F5 Run Line"',
    'mlb_signals.append({"name": "Signal B (RL)"'
)

print("[6/7] Tracker tab labels updated")

# ═══════════════════════════════════════════════════════════════════════════════
# 7. Add cache-bust comment at end
# ═══════════════════════════════════════════════════════════════════════════════

content = content.replace(
    "# cache bust Wed Apr  2 WNBA archetype tab",
    "# cache bust Fri Apr 11 site reset — state model applied"
)
print("[7/7] Cache bust updated")

# ═══════════════════════════════════════════════════════════════════════════════
# Write
# ═══════════════════════════════════════════════════════════════════════════════

if content == original:
    print("\nERROR: No changes detected. Aborting.")
    sys.exit(1)

with open(DASHBOARD, "w") as f:
    f.write(content)

print(f"\nDashboard patched successfully. File size: {len(content)} chars")
print(f"Delta: {len(content) - len(original):+d} chars")
