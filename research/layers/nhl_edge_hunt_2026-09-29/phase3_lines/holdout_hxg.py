#!/usr/bin/env python3
"""H_XG, opened once on 2025-26 (PREREGISTRATION_P3.md addendum)."""
import sys, contextlib, io
from pathlib import Path
import numpy as np, pandas as pd
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "out"))
with contextlib.redirect_stdout(io.StringIO()):
    import scan as P1
th = P1.TH["xgpct_b"][1]
M = pd.read_parquet(HERE / "games_lines.parquet")
M = M[M.pin_p_over.notna()].copy()
M["y"] = np.where(M.tot > M.tl_pin, 1.0, np.where(M.tot < M.tl_pin, 0.0, np.nan)); M = M[M.y.notna()]
M["flag"] = (M.h_xgpct_b >= th) | (M.a_xgpct_b >= th)
M["under"] = 1 - M.y; M["pu"] = 1 - M.pin_p_over
M["ret_u"] = np.where(M.under == 1, M.med_dec_under - 1, -1.0)
M["ret_o"] = np.where(M.y == 1, M.med_dec_over - 1, -1.0)
def f(s):
    return pd.Series({"n": len(s), "under": s.under.mean(), "pin_under": s.pu.mean(),
                      "z": (s.under - s.pu).sum() / np.sqrt((s.pu * (1 - s.pu)).sum()),
                      "ROI_under_median": s.ret_u.mean(), "ROI_over_median": s.ret_o.mean(),
                      "breakeven_under": (1 / s.med_dec_under).mean()})
out = []
for lab, ss in [("D 2022-24", [2022, 2023]), ("V 2024-25", [2024]), ("H 2025-26", [2025])]:
    s = M[M.season.isin(ss)]
    out.append(f(s[s.flag]).rename(f"{lab} | flagged (bet Under)"))
    out.append(f(s[~s.flag]).rename(f"{lab} | not flagged"))
H = M[(M.season == 2025) & M.flag]
T = pd.DataFrame(out)
bym = H.groupby(H.date.dt.to_period("M")).apply(f)
text = "# H_XG — one declared test on 2025-26\n\n" + T.round(4).to_markdown() + "\n\n## 2025-26 flagged games by month\n\n" + bym.round(4).to_markdown() + "\n"
(HERE / "H_XG_result.md").write_text(text); print(text)
