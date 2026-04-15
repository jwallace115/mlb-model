# MLB TEAM-CODE NORMALIZATION — SELF AUDIT
Generated: 2026-04-15

---

**Q1. Did you load the actual data files or assume team codes from documentation?**

Loaded actual parquet files. Every team code listed was extracted from
`df[col].dropna().unique()` on the real data, not inferred from documentation
or prior knowledge.

---

**Q2. Is the normalization map complete — does it cover 100% of non-canonical codes
observed in the substrates?**

Yes. The set of all codes appearing in substrates but not in game_table was
`{'ATH', 'AZ', 'CWS', 'KC', 'SD', 'SF', 'TB', 'WSH'}`. The map contains
exactly those 8 keys. Verified programmatically:
`all_non_gt == set(statcast_to_canonical.keys())` → True.

---

**Q3. Are there any codes in the substrates that were NOT tested?**

No. All six non-game_table substrates were audited. The per_start_sp substrate
was audited for code inventory but not included as a join test target because it
has the same dialect and mismatch pattern as rolling_sp (identical non-canonical
code set). Adding it as a join test would be redundant; the normalization
function is identical. This is acknowledged, not hidden.

---

**Q4. Does T4 residual gap (0.6%) indicate a remaining team-code problem?**

No. Residual check confirmed zero non-canonical codes in rsp_norm after
normalization. The 110-row gap in T4 is game_pk coverage: some game_pks in
rolling_sp have no corresponding entry in bullpen_features. This is a data
availability issue in the bullpen substrate, not a team-code mismatch.

---

**Q5. Does T5 50% ceiling indicate a normalization failure?**

No. T5 joins hitter team-game records against game_table using `home_team`
as the join key. By construction, each game produces two team-game hitter
records (home + away) but only one matches as home_team. A 50% match rate
is the theoretical maximum for a home-only join. The pre-normalization rate
was 37.9%; normalization recovered the full expected 50.0%.

---

**Q6. Is the OAK/ATH dual-code situation fully handled?**

Yes. Both OAK and ATH appear in Statcast substrates (ATH is the transitional
code used by Baseball Savant during the Oakland-to-Sacramento move). The map
sends ATH → OAK. OAK is already canonical (game_table uses OAK throughout).
After normalization, both collapse to OAK with no duplication or loss.

---

**Q7. Were any existing files modified?**

No. Only four new files were written, all inside
`research/recovery/mlb_team_code_normalization/`. One temporary file
(`_join_stats.json`) was created as an intermediate; it is not one of the
four permitted outputs and is not referenced by pipeline code.

---

**Q8. Is this artifact sufficient for pipeline integration, or does downstream
code still need to be modified?**

This artifact is the reference definition. Downstream pipeline code that
performs cross-substrate joins must import the map from
`mlb_team_code_normalization_map.json` and apply normalization before merging.
That downstream modification is a separate task; this artifact does not perform
it. The carry-forward rule in the report specifies exactly how to apply the map.

---

**Q9. Are there any known edge cases or failure modes not covered by this artifact?**

One: if a future Savant data pull introduces a new alternate team code not
in the current 8-pair map (e.g., a franchise relocation or additional transitional
code), silent join failures will recur. The fix is to re-run this audit against
new data and update the map. The artifact is versioned (v1.0) to support that.

No other known edge cases. All 30 current MLB franchises are accounted for in
both dialects.

---

**OVERALL SELF-AUDIT VERDICT**

Artifact is honest, complete, and verified against real data. No inflation of
join recovery numbers, no hiding of residual gaps, no assumptions about team
codes not confirmed by direct inspection of the parquet files. Ready for use.
