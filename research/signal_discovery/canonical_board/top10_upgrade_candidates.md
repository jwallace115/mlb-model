# Top 10 Upgrade Candidates

These concepts apply more advanced mathematical frameworks to mechanisms already partially captured by existing LIVE or SHADOW signals. They represent the highest-value research targets because the mechanism is already validated — only the framework needs upgrading.

| Rank | ID | Concept | Upgrades | Sim | Frameworks |
|:-----|:---|:--------|:---------|----:|:-----------|
| 1 | C022 | Pitcher latent fatigue state | F5_totals | 0.47 | DISTRIBUTION_MODEL, EVT_TAIL_MODEL, STATE_MODEL |
| 2 | C027 | Pitcher repertoire mix change | V1 | 0.44 | BAYESIAN_UPDATE, CAUSAL_IV, DISTRIBUTION_MODEL, EVT_TAIL_MODEL, HEURISTIC, STATE_MODEL |
| 3 | C021 | Pitcher deception / entropy | ADJ_CONTACT | 0.47 | DISTRIBUTION_MODEL, HEURISTIC |
| 4 | C020 | Pitcher command regime shift | V1 | 0.44 | BAYESIAN_UPDATE, CAUSAL_IV, DISTRIBUTION_MODEL, STATE_MODEL |
| 5 | C037 | TRAVEL — unclustered signals | ST02 | 0.47 | CAUSAL_IV |
| 6 | C024 | PITCHER — unclustered signals | V1 | 0.44 | BAYESIAN_UPDATE, CAUSAL_IV, EVT_TAIL_MODEL |
| 7 | C023 | Pitcher injury/IL return adjustment lag | V1 | 0.44 | BAYESIAN_UPDATE, EVT_TAIL_MODEL, STATE_MODEL |
| 8 | C028 | Starter short-leash / early exit | combined_short_exit | 0.86 | EVT_TAIL_MODEL |
| 9 | C039 | Timezone / jet lag effect | ST02 | 0.47 | BAYESIAN_UPDATE, CAUSAL_IV |
| 10 | C038 | Road trip fatigue accumulation | ST02 | 0.82 | CAUSAL_IV, EVT_TAIL_MODEL, STATE_MODEL |

---

## Detailed Upgrade Paths

### 1. Pitcher latent fatigue state [C022]

- **Upgrades:** F5_totals (LIVE)
- **Similarity:** 0.47
- **Domain:** PITCHER
- **Framework variants:** DISTRIBUTION_MODEL, EVT_TAIL_MODEL, STATE_MODEL
- **Ideas:** 12

**Current signal mechanism:** F5_totals uses a regression/heuristic approach.

**Proposed upgrade:** Upgrade F5_totals (First-5-inning total projection) using DISTRIBUTION_MODEL/EVT_TAIL_MODEL/STATE_MODEL framework: Starter fatigue accumulates as a hidden state variable that markets price with lag; pitch count and velocity decline are

**Mechanism:** Starter fatigue accumulates as a hidden state variable that markets price with lag; pitch count and velocity decline are symptoms, not the state itself

---

### 2. Pitcher repertoire mix change [C027]

- **Upgrades:** V1 (LIVE)
- **Similarity:** 0.44
- **Domain:** PITCHER
- **Framework variants:** BAYESIAN_UPDATE, CAUSAL_IV, DISTRIBUTION_MODEL, EVT_TAIL_MODEL, HEURISTIC, STATE_MODEL
- **Ideas:** 12

**Current signal mechanism:** V1 uses a regression/heuristic approach.

**Proposed upgrade:** Upgrade V1 (Pitcher xFIP/CSW quality → full-game total projection) using BAYESIAN_UPDATE/CAUSAL_IV/DISTRIBUTION_MODEL/EVT_TAIL_MODEL/STATE_MODEL framework: Changes in pitch mix (adding/dropping pitches, usage shifts) alter effectiveness before season stats reflect it; markets

**Mechanism:** Changes in pitch mix (adding/dropping pitches, usage shifts) alter effectiveness before season stats reflect it; markets anchor to historical pitch type distributions

---

### 3. Pitcher deception / entropy [C021]

- **Upgrades:** ADJ_CONTACT (SHADOW)
- **Similarity:** 0.47
- **Domain:** PITCHER
- **Framework variants:** DISTRIBUTION_MODEL, HEURISTIC
- **Ideas:** 5

**Current signal mechanism:** ADJ_CONTACT uses a regression/heuristic approach.

**Proposed upgrade:** Upgrade ADJ_CONTACT (Opponent-adjusted contact rate suppression) using DISTRIBUTION_MODEL framework: Pitchers with high entropy (unpredictable sequences) suppress scoring more than metrics suggest; low-entropy pitchers ar

**Mechanism:** Pitchers with high entropy (unpredictable sequences) suppress scoring more than metrics suggest; low-entropy pitchers are more exploitable

---

### 4. Pitcher command regime shift [C020]

- **Upgrades:** V1 (LIVE)
- **Similarity:** 0.44
- **Domain:** PITCHER
- **Framework variants:** BAYESIAN_UPDATE, CAUSAL_IV, DISTRIBUTION_MODEL, STATE_MODEL
- **Ideas:** 7

**Current signal mechanism:** V1 uses a regression/heuristic approach.

**Proposed upgrade:** Upgrade V1 (Pitcher xFIP/CSW quality → full-game total projection) using BAYESIAN_UPDATE/CAUSAL_IV/DISTRIBUTION_MODEL/STATE_MODEL framework: Pitchers alternate between command regimes (sharp/wild) that persist over multi-start windows; markets anchor to season 

**Mechanism:** Pitchers alternate between command regimes (sharp/wild) that persist over multi-start windows; markets anchor to season averages and miss regime transitions

---

### 5. TRAVEL — unclustered signals [C037]

- **Upgrades:** ST02 (LIVE)
- **Similarity:** 0.47
- **Domain:** TRAVEL
- **Framework variants:** CAUSAL_IV
- **Ideas:** 1

**Current signal mechanism:** ST02 uses a regression/heuristic approach.

**Proposed upgrade:** Upgrade ST02 (Road trip game 6+ fatigue UNDER) using CAUSAL_IV framework: Mixed travel signals without a shared core mechanism

**Mechanism:** Mixed travel signals without a shared core mechanism

---

### 6. PITCHER — unclustered signals [C024]

- **Upgrades:** V1 (LIVE)
- **Similarity:** 0.44
- **Domain:** PITCHER
- **Framework variants:** BAYESIAN_UPDATE, CAUSAL_IV, EVT_TAIL_MODEL
- **Ideas:** 5

**Current signal mechanism:** V1 uses a regression/heuristic approach.

**Proposed upgrade:** Upgrade V1 (Pitcher xFIP/CSW quality → full-game total projection) using BAYESIAN_UPDATE/CAUSAL_IV/EVT_TAIL_MODEL framework: Mixed pitcher signals without a shared core mechanism

**Mechanism:** Mixed pitcher signals without a shared core mechanism

---

### 7. Pitcher injury/IL return adjustment lag [C023]

- **Upgrades:** V1 (LIVE)
- **Similarity:** 0.44
- **Domain:** PITCHER
- **Framework variants:** BAYESIAN_UPDATE, EVT_TAIL_MODEL, STATE_MODEL
- **Ideas:** 6

**Current signal mechanism:** V1 uses a regression/heuristic approach.

**Proposed upgrade:** Upgrade V1 (Pitcher xFIP/CSW quality → full-game total projection) using BAYESIAN_UPDATE/EVT_TAIL_MODEL/STATE_MODEL framework: Post-IL return pitchers have altered effectiveness that markets are slow to update; stale priors from pre-injury perform

**Mechanism:** Post-IL return pitchers have altered effectiveness that markets are slow to update; stale priors from pre-injury performance persist for multiple starts

---

### 8. Starter short-leash / early exit [C028]

- **Upgrades:** combined_short_exit (SHADOW)
- **Similarity:** 0.86
- **Domain:** PITCHER
- **Framework variants:** EVT_TAIL_MODEL
- **Ideas:** 4

**Current signal mechanism:** combined_short_exit uses a regression/heuristic approach.

**Proposed upgrade:** Upgrade combined_short_exit (Both starters likely to exit early → bullpen exposure) using EVT_TAIL_MODEL framework: Short starters expose more bullpen innings; when combined with bullpen state, creates predictable scoring environments t

**Mechanism:** Short starters expose more bullpen innings; when combined with bullpen state, creates predictable scoring environments that markets underweight

---

### 9. Timezone / jet lag effect [C039]

- **Upgrades:** ST02 (LIVE)
- **Similarity:** 0.47
- **Domain:** TRAVEL
- **Framework variants:** BAYESIAN_UPDATE, CAUSAL_IV
- **Ideas:** 2

**Current signal mechanism:** ST02 uses a regression/heuristic approach.

**Proposed upgrade:** Upgrade ST02 (Road trip game 6+ fatigue UNDER) using BAYESIAN_UPDATE/CAUSAL_IV framework: Cross-timezone travel disrupts circadian rhythm and reaction time, affecting both pitching and hitting performance for 1

**Mechanism:** Cross-timezone travel disrupts circadian rhythm and reaction time, affecting both pitching and hitting performance for 1-2 games

---

### 10. Road trip fatigue accumulation [C038]

- **Upgrades:** ST02 (LIVE)
- **Similarity:** 0.82
- **Domain:** TRAVEL
- **Framework variants:** CAUSAL_IV, EVT_TAIL_MODEL, STATE_MODEL
- **Ideas:** 6

**Current signal mechanism:** ST02 uses a regression/heuristic approach.

**Proposed upgrade:** Upgrade ST02 (Road trip game 6+ fatigue UNDER) using CAUSAL_IV/EVT_TAIL_MODEL/STATE_MODEL framework: Extended road trips accumulate fatigue that depresses scoring; markets price talent but not cumulative travel load

**Mechanism:** Extended road trips accumulate fatigue that depresses scoring; markets price talent but not cumulative travel load

---

