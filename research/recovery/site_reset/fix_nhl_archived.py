#!/usr/bin/env python3
"""Add ARCHIVED label to NHL Season Performance section."""

DASHBOARD = "/root/mlb-model/dashboard.py"

with open(DASHBOARD) as f:
    content = f.read()

target = 'st.html(\'<div class="section-hdr">\U0001f4ca Season Performance (Historical Backtest)</div>\')'
idx = content.find(target)
if idx == -1:
    print("Target string not found")
    exit(1)

insert_after = idx + len(target)
disclaimer = """
    st.html('<div style="font-size:0.72em;color:#78716c;margin-bottom:6px;'
            'padding:4px 8px;background:#1a1a1a;border-radius:4px;border:1px solid #333">'
            'ARCHIVED \\u2014 Legacy System (MoneyPuck-dependent). '
            'Identity broken Apr 11. New aligned Model A tracker starts fresh.</div>')"""

content = content[:insert_after] + disclaimer + content[insert_after:]

with open(DASHBOARD, "w") as f:
    f.write(content)

print("NHL Season Performance archived label added")
