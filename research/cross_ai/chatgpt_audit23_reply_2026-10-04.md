# Audit #23 — FWD7m / D281
b842af34355c0646a811f6353cbfb3015d4091e0
(E) IND@WAS: NO-GO; main + SNF: NO-GO; MNF: NO-GO for a PRIMARY at this pin.

Verdict decided from executed parser/mapper counterexample; supporting checks continue.

(A) 1. nfl/sim/official_injuries.py:113 removes comment-looking text without respecting quoted attributes, before the D281 allowlist sees it. In the real archived Jayden Daniels row replace `<td>Out</td>` with `<td><a aria-label="<!--">Out</a><a aria-label="-->"></a></td>`. The pin ADMITs all 318 rows but changes `(WAS, 00-0039910, Out)` to `(WAS, 00-0039910, blank)`. Python HTMLParser sees text Out, two quoted attribute values, and zero comments. Using href instead of aria-label also admits the change. This tests an altered copy, not contamination of the installed capture.

(B) All 52 previous probes re-executed: 39 HALT, 13 identical, 0 changed. The old encoded-style repair holds at parse. 23 new probes: 5 HALT, 16 identical, 2 admitted changed sets. Full refresh/gate, clean predictions, baseline, mutations and archive verification are in progress.
