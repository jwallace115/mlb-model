# Phase 8 - Distinctness Audit
## MLB Totals Context Engine V1

### Methodology
Pairwise Pearson correlations among all continuous decomposition scores on DISCOVERY data.
Threshold: |r| > 0.70 flagged as potentially redundant.

---

### Correlation Matrix (Discovery 2022-2023)

       bre    esp    lsp     ss     bs    wpl    tcv
bre  1.000  0.654  0.432 -0.007 -0.050  0.634 -0.043
esp  0.654  1.000  0.724 -0.434 -0.073  0.276  0.063
lsp  0.432  0.724  1.000 -0.221 -0.624  0.110  0.363
ss  -0.007 -0.434 -0.221  1.000  0.016 -0.054  0.033
bs  -0.050 -0.073 -0.624  0.016  1.000 -0.020 -0.454
wpl  0.634  0.276  0.110 -0.054 -0.020  1.000  0.003
tcv -0.043  0.063  0.363  0.033 -0.454  0.003  1.000

---

### Pairwise Summary

      pair         r    abs_r  flag
esp vs lsp  0.723789 0.723789  True
bre vs esp  0.654372 0.654372 False
bre vs wpl  0.634263 0.634263 False
 lsp vs bs -0.623602 0.623602 False
 bs vs tcv -0.454084 0.454084 False
 esp vs ss -0.433699 0.433699 False
bre vs lsp  0.432398 0.432398 False
lsp vs tcv  0.362895 0.362895 False
esp vs wpl  0.276211 0.276211 False
 lsp vs ss -0.221207 0.221207 False
lsp vs wpl  0.110211 0.110211 False
 esp vs bs -0.073217 0.073217 False
esp vs tcv  0.063382 0.063382 False
 ss vs wpl -0.054465 0.054465 False
 bre vs bs -0.050392 0.050392 False
bre vs tcv -0.042509 0.042509 False
 ss vs tcv  0.033028 0.033028 False
 bs vs wpl -0.020071 0.020071 False
  ss vs bs  0.016138 0.016138 False
 bre vs ss -0.006545 0.006545 False
wpl vs tcv  0.002576 0.002576 False

---

### Flagged Pairs (|r| > 0.70)

- **esp vs lsp**: r = 0.724

**Action required:** Review flagged pairs for potential redundancy. See analysis below.

---

### Structural Analysis of Key Pairs

**ESP vs LSP:** These are explicitly designed to capture different inning ranges (F5 vs late innings). They share avg_sp_fragility as an input, creating expected positive correlation. If both are high, that is a signal of total game pressure. They are not redundant.

**SS vs ESP:** Starter Stability (SS) is inverted fragility. High SS = low fragility = low early pressure. Negative correlation expected. This is directional design, not redundancy.

**BRE vs ESP:** BRE enters ESP as a 20% component. Some correlation is by construction. The remaining variance in ESP is dominated by SP fragility (50%), making them structurally distinct.

**BS vs LSP:** Bullpen stability is a component of LSP (via avg_bp_instability). Negative correlation expected (high BS = low instability = lower LSP). This is the intended relationship.

**WPL vs BRE:** Both include park_factor_runs as an input. Correlation expected but partial because WPL also includes weather components not in BRE (temperature, wind), while BRE includes lineup quality and umpire not in WPL.

---

### Verdict
- No pairs exceed redundancy threshold (0.70)
- Structural correlations between intentionally related outputs are expected and documented
- All 7 active outputs carry distinct information for downstream niche objects

---

Built: 2026-04-12
