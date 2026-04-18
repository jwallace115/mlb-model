# MLB Substrate Stack — Master Acceptance Memo

**Accepted:** 2026-04-15  
**Basis:** Forensic stack-wide audit  
**Classification:** Non-pristine but usable

---

## 1. PURPOSE

This memo records acceptance of the current MLB research substrate stack as the base layer for future matchup and archetype work. Acceptance is based on forensic verification of all five substrates, not on individual self-audits alone. This memo freezes the accepted state before the team-code normalization repair that must precede matchup-table construction.

## 2. ACCEPTED STACK

Five substrates are accepted:

1. **Hitter substrate** — per-batter-per-game Statcast quality (197,497 rows)
2. **Lineup state substrate** — team-game rolling offensive state with 4 windows (19,712 rows)
3. **Per-start starter substrate** — realized per-start box-score + Statcast enrichment (19,914 rows)
4. **Rolling starter profile substrate** — pitcher-level rolling profile with 3 windows (19,914 rows)
5. **Bullpen substrate** — team-game rolling bullpen fatigue/availability state (19,804 rows)

All cover 2022–2026 (2026 partial). These are the current approved base-layer research objects.

## 3. WHY THE STACK IS ACCEPTED

- All five substrates were judged substantively PIT-safe by the forensic audit
- All five substrates were judged identity-stable (zero grain duplicates, row/column counts match registries)
- Shift(1) behavior was verified empirically for both rolling substrates (lineup state and rolling starter profile)
- The bullpen substrate was accepted only after independent forensic verification resolved its process violations — the builder's self-audit was not sufficient alone
- The overall stack verdict was **non-pristine but usable** — the stack is accepted as a base layer, not as a finished matchup engine

## 4. FROZEN CAVEATS

These caveats are documented conditions of acceptance, not reasons to reject the stack:

- **Team-code normalization is mandatory** before any cross-substrate team-keyed join. Lineup state and bullpen use FG-style codes (ARI, CHW, KCR, SDP, SFG, TBR, WSN). Rolling starter profile and hitter use Statcast-style codes (AZ, CWS, KC, SD, SF, TB, WSH, ATH). Naive team-keyed joins will silently drop ~24% of rows for 8 teams.
- **Rolling starter Statcast fields use available-only averaging.** When a start within a rolling window lacks Statcast enrichment, pandas `rolling().mean()` silently averages over the non-null subset. A last_3 window with 1 unenriched start produces a value from 2 observations, indistinguishable from a fully observed window.
- **Bullpen process history remains part of the record.** The repair used background tasks and the self-audit falsely claimed otherwise. Substantive repair was independently verified and accepted, but process attestation from that builder cannot be fully trusted.

## 5. WHAT MUST HAPPEN NEXT

1. A narrow team-code normalization audit/fix — standardize team codes across all five substrates or build a normalization layer for the join step
2. That normalization fix is incremental and comes after this memo
3. Matchup-table construction should occur only after the normalization artifact is frozen
4. No accepted substrate should be casually rebuilt while doing that work

## 6. STATUS

MLB substrate stack is ACCEPTED as the current base layer for future matchup/archetype work. Acceptance is based on forensic verification and includes documented caveats that must be honored downstream.

Acceptance classification: non-pristine but usable. This memo does not change any live or shadow object behavior. Future join-layer work must inherit the frozen caveats explicitly.
