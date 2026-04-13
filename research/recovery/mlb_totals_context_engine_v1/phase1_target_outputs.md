# Phase 1 - Target Outputs
## MLB Totals Context Engine V1 - Eight Decomposition Outputs

---

### Output 1: Baseline Run Environment (BRE)
**Plain-English Meaning:** A continuous score summarizing the expected per-game run scoring baseline before any game-day context is applied. Combines park factor, umpire over-rate, and team offensive quality into a single structural baseline. Answers: is this fundamentally a high-scoring or low-scoring venue and lineup combination?

**Intended Use:** Sets the prior for all other decomposition outputs. A weather lift in a pitcher park (BRE=low) means something different than the same wind in a hitter park (BRE=high). Niche objects use BRE to segment their population into high/med/low run environments before computing their own signal.

**Format:** Continuous score 0-100, bucketed into LOW (<40), MEDIUM (40-60), HIGH (>60). Bucket labels used for niche object segmentation.

**Future Research Questions:**
- Do niche under objects perform better in low-BRE buckets independently of their stated condition?
- Is BRE stable year-over-year for the same park/team combinations?
- Does BRE correlate with umpire over-rate changes when new umpires join the rotation?

---

### Output 2: Early Scoring Pressure (ESP)
**Plain-English Meaning:** A score measuring how much run-scoring pressure is concentrated in innings 1-5, driven by starter fragility, opposing offense depth, and early lineup quality. High ESP means the game is structurally likely to see significant scoring in the first 5 innings. Low ESP means starters are likely to suppress early run accumulation.

**Intended Use:** Primary input for F5 totals niche objects. An F5 over object that fires in high-ESP games has a fundamentally different structural profile than one that fires in low-ESP games. Also used to compute Late Scoring Pressure as a residual.

**Format:** Continuous score 0-100, bucketed into LOW (<35), MEDIUM (35-60), HIGH (>60).

**Future Research Questions:**
- Does high ESP predict F5 over at above-baseline rates in OOS data?
- Is there a nonlinear threshold above which ESP predicts blow-up innings?
- How does ESP interact with ballpark factors in dome stadiums?

---

### Output 3: Late Scoring Pressure (LSP)
**Plain-English Meaning:** A score measuring how much run-scoring pressure is generated in innings 6-9, driven by bullpen instability, lineup depth, and park/weather conditions that persist into late game. High LSP does not require high ESP - a game can have dominant starters (low ESP) but exhausted bullpens (high LSP).

**Intended Use:** Identifies games where the full-game total is dominated by late-game run accumulation. Critical for distinguishing games where the under holds through F5 but the full-game over hits (starter bridges, bullpen implosion). Niche objects targeting full-game vs F5 divergence use LSP.

**Format:** Continuous score 0-100, bucketed into LOW (<35), MEDIUM (35-60), HIGH (>60).

**Future Research Questions:**
- Does high LSP predict innings 6-9 scoring at above-baseline rates?
- Is the over rate higher for high-LSP, low-ESP games than for games where both are high?
- How does rest pattern affect LSP independently of raw bullpen quality?

---

### Output 4: Starter Stability (SS)
**Plain-English Meaning:** A score measuring how likely both starters are to go deep into the game, maintain quality through the lineup rotation, and avoid early exits that cascade into bullpen reliance. High SS means both starters are structurally positioned for 6+ innings of above-average performance. Low SS (fragility) means one or both starters are likely to exit early or post poor rate stats.

**Intended Use:** The anchor input for P1B-style under objects. SS is computed from rolling pitcher game logs (PIT-safe), not season-level xFIP. Niche objects that condition on both starters going deep need SS to identify their structural population without using market proxies (line level).

**Format:** Continuous 0-100, bucketed into FRAGILE (<35), AVERAGE (35-60), STABLE (>60). Also produces a binary flag: BOTH_STABLE (both individual scores above 55).

**Future Research Questions:**
- Does BOTH_STABLE predict actual innings pitched beyond 6.0 at >70% rates?
- Is SS predictive of starter exit in high-temperature games independently?
- Does the second-time-through-order effect show up in rolling K-rate degradation?

---

### Output 5: Bullpen Stability (BS)
**Plain-English Meaning:** A score measuring how available and effective both teams bullpens are entering the game. High BS means both bullpens are fresh and their top relievers are available. Low BS (instability) means high recent usage, compressed rest, or depleted closer availability. This is separate from bullpen quality - a team can have elite relievers who are unavailable.

**Intended Use:** Complements Starter Stability. A game with high SS and high BS is structurally under-favored. A game with low SS and low BS is structurally over-favored. The interaction is more informative than either alone. Downstream niche objects use BS to condition their population.

**Format:** Continuous 0-100, bucketed into UNSTABLE (<35), NEUTRAL (35-60), STABLE (>60).

**Future Research Questions:**
- Does bullpen instability (low BS) predict higher late-game run totals independently of starter performance?
- Is there a rest-pattern threshold below which BS reliably identifies implosion risk?
- How does high-leverage availability interact with raw BS score?

---

### Output 6: Weather and Park Lift (WPL)
**Plain-English Meaning:** A composite score measuring how much the physical environment (park factor, weather conditions, roof status) lifts or suppresses run scoring relative to a neutral environment. High WPL means the game is being played in conditions that structurally favor run scoring. Negative WPL means conditions actively suppress runs.

**Intended Use:** Provides environmental context that all other outputs assume is being controlled for. A niche object should know whether it is firing in high-WPL or low-WPL games to understand if its edge is structural or luck correlated with favorable conditions. WPL is also used to adjust BRE when game-day conditions diverge from park norms.

**Format:** Signed continuous score -100 to +100. Bucketed: SUPPRESSED (<-20), NEUTRAL (-20 to +20), LIFTED (>20).

**Future Research Questions:**
- Is WPL predictive of actual scoring above and beyond closing line for outdoor stadiums?
- Does WPL interact with umpire zone size in known over-calling environments?
- Is the wind direction component stable or regime-dependent by ballpark?

---

### Output 7: Total Compression / Volatility State (TCV)
**Plain-English Meaning:** A score measuring how volatile or compressed the expected run distribution is for this game. High volatility means the game is structurally capable of a wide range of outcomes (2 runs or 20 runs are both plausible). Low volatility / high compression means the distribution is tight - the game is unlikely to blow up in either direction. This is about variance, not mean.

**Intended Use:** Critical for understanding when the market total is a bad proxy for true distribution. A compressed game at 8.5 runs is different from a volatile game at 8.5 runs - the tail risks are completely different. Niche objects that target specific outcome buckets (game ends 7-9 runs, game ends 12+ runs) need TCV to condition their population.

**Format:** Continuous 0-100 (higher = more volatile). Bucketed: COMPRESSED (<35), BALANCED (35-60), VOLATILE (>60).

**Future Research Questions:**
- Does high TCV predict higher standard deviation of actual totals within the same closing line bucket?
- Can TCV identify games where the market is systematically mispriced due to line anchor bias?
- Does volatility correlate with doubleheader scheduling or team travel patterns?

---

### Output 8: Market Path Shape (MPS)
**Plain-English Meaning:** A categorical classification of how the total line moved from open to close. EARLY-HEAVY means most movement happened in the first few hours after line posting. LATE-HEAVY means the line moved significantly in the 2-3 hours before game time. BALANCED means movement was distributed. COMPRESSED means the line barely moved and closed near open.

**Intended Use:** Provides market intelligence context for all niche objects. An object that fires on COMPRESSED market path games is operating in fundamentally different conditions than one that fires on LATE-HEAVY movers. Informed money tends to move lines early; public money tends to move lines late. Understanding which regime a game is in allows niche objects to assess whether the closing line is sharp or drifted.

**Format:** Categorical: EARLY-HEAVY, LATE-HEAVY, BALANCED, COMPRESSED, DATA-BLOCKED.

**Future Research Questions:**
- Does EARLY-HEAVY market path predict sharper closing lines vs LATE-HEAVY?
- Is COMPRESSED market path correlated with specific weather conditions or scheduling factors?
- Do niche objects with sharp edge ratings perform better in EARLY-HEAVY vs LATE-HEAVY games?

---

## Summary Table

| Output | Type | Levels | Primary Use |
|--------|------|--------|-------------|
| Baseline Run Environment | Continuous/Bucketed | LOW/MED/HIGH | Population prior |
| Early Scoring Pressure | Continuous/Bucketed | LOW/MED/HIGH | F5 objects |
| Late Scoring Pressure | Continuous/Bucketed | LOW/MED/HIGH | Full-game objects |
| Starter Stability | Continuous/Bucketed | FRAGILE/AVG/STABLE | Under objects, P1B |
| Bullpen Stability | Continuous/Bucketed | UNSTABLE/NEUTRAL/STABLE | Over objects |
| Weather/Park Lift | Signed/Bucketed | SUPPRESSED/NEUTRAL/LIFTED | Environmental context |
| Total Compression/Volatility | Continuous/Bucketed | COMPRESSED/BALANCED/VOLATILE | Tail risk objects |
| Market Path Shape | Categorical | 5 states | Market intelligence |

---

Built: 2026-04-12
