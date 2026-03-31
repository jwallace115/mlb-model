# Top 20 Research Candidates

Ranked by composite score (novelty, mechanism clarity, independence from existing signals, data feasibility).

| Rank | ID | Concept | Domain | Classification | Ideas | Score |
|:-----|:---|:--------|:-------|:---------------|------:|------:|
| 1 | C016 | Cross-market / prop-to-total arbitrage | MARKET_BEHAVIOR | NEW_SIGNAL | 10 | 33.2 |
| 2 | C041 | Umpire strike zone regime | UMPIRE | NEW_SIGNAL | 16 | 32.0 |
| 3 | C003 | Bullpen collapse / blowup tail risk | BULLPEN | NEW_SIGNAL | 8 | 31.4 |
| 4 | C042 | Extreme weather scoring impact | WEATHER | NEW_SIGNAL | 9 | 30.6 |
| 5 | C005 | Bullpen latent fatigue state | BULLPEN | NEW_SIGNAL | 11 | 30.4 |
| 6 | C040 | Umpire behavioral drift / game-state response | UMPIRE | NEW_SIGNAL | 1 | 30.3 |
| 7 | C044 | Weather × pitcher/park interaction | WEATHER | NEW_SIGNAL | 1 | 30.3 |
| 8 | C004 | Bullpen deployment optimization | BULLPEN | NEW_SIGNAL | 6 | 30.2 |
| 9 | C032 | Run distribution tail shape mispricing | RUN_DISTRIBUTION | NEW_SIGNAL | 9 | 30.2 |
| 10 | C001 | Dynamic park environment effect | BALLPARK | NEW_SIGNAL | 8 | 30.1 |
| 11 | C035 | SEQUENCING — unclustered signals | SEQUENCING | NEW_SIGNAL | 11 | 30.0 |
| 12 | C030 | PLAYER_FORM — unclustered signals | PLAYER_FORM | NEW_SIGNAL | 12 | 29.8 |
| 13 | C022 | Pitcher latent fatigue state | PITCHER | UPGRADE_CANDIDATE | 12 | 29.7 |
| 14 | C002 | BALLPARK — unclustered signals | BALLPARK | NEW_SIGNAL | 2 | 29.3 |
| 15 | C036 | Pitch sequencing / approach predictability | SEQUENCING | NEW_SIGNAL | 6 | 29.0 |
| 16 | C006 | Bullpen roster/quality transition | BULLPEN | NEW_SIGNAL | 2 | 28.6 |
| 17 | C012 | LINEUP — unclustered signals | LINEUP | NEW_SIGNAL | 17 | 28.0 |
| 18 | C033 | RUN_DISTRIBUTION — unclustered signals | RUN_DISTRIBUTION | NEW_SIGNAL | 4 | 28.0 |
| 19 | C043 | WEATHER — unclustered signals | WEATHER | NEW_SIGNAL | 2 | 28.0 |
| 20 | C015 | MARKET_BEHAVIOR — unclustered signals | MARKET_BEHAVIOR | NEW_SIGNAL | 4 | 27.6 |

---

## Detailed Descriptions

### 1. Cross-market / prop-to-total arbitrage [C016]

- **Domain:** MARKET_BEHAVIOR
- **Framework variants:** HEURISTIC, MARKET_MICROSTRUCTURE
- **Ideas contributing:** 10
- **No cross-reference to existing signals**
- **Classification:** NEW_SIGNAL


**Mechanism:** Inconsistencies between player props, team totals, and full-game totals create identifiable mispricing windows

---

### 2. Umpire strike zone regime [C041]

- **Domain:** UMPIRE
- **Framework variants:** BAYESIAN_UPDATE, CAUSAL_IV, DISTRIBUTION_MODEL, EVT_TAIL_MODEL, HEURISTIC, MARKET_MICROSTRUCTURE, STATE_MODEL
- **Ideas contributing:** 16
- **No cross-reference to existing signals**
- **Classification:** NEW_SIGNAL


**Mechanism:** Individual umpires have zone tendencies (wide/tight, high/low) that interact with pitcher arsenals and batter types in ways that single over_rate captures poorly

---

### 3. Bullpen collapse / blowup tail risk [C003]

- **Domain:** BULLPEN
- **Framework variants:** BAYESIAN_UPDATE, EVT_TAIL_MODEL, STATE_MODEL
- **Ideas contributing:** 8
- **Cross-ref: **combined_short_exit** (SHADOW, similarity=0.28)**
- **Classification:** NEW_SIGNAL


**Mechanism:** Reliever performance has fat-tailed failure modes (blowup innings) that standard variance models underestimate; creates unpriced OVER tail risk

---

### 4. Extreme weather scoring impact [C042]

- **Domain:** WEATHER
- **Framework variants:** BAYESIAN_UPDATE, CAUSAL_IV, DISTRIBUTION_MODEL, EVT_TAIL_MODEL, MARKET_MICROSTRUCTURE, STATE_MODEL
- **Ideas contributing:** 9
- **No cross-reference to existing signals**
- **Classification:** NEW_SIGNAL


**Mechanism:** Extreme heat, cold, humidity, or wind create nonlinear scoring effects that linear weather adjustments miss; tail weather events are underpriced

---

### 5. Bullpen latent fatigue state [C005]

- **Domain:** BULLPEN
- **Framework variants:** BAYESIAN_UPDATE, CAUSAL_IV, DISTRIBUTION_MODEL, EVT_TAIL_MODEL, HEURISTIC, STATE_MODEL
- **Ideas contributing:** 11
- **Cross-ref: **combined_short_exit** (SHADOW, similarity=0.28)**
- **Classification:** NEW_SIGNAL


**Mechanism:** Bullpen fatigue is a hidden state (not just recent IP) that builds nonlinearly and causes scoring spikes; markets price talent but not fatigue state

---

### 6. Umpire behavioral drift / game-state response [C040]

- **Domain:** UMPIRE
- **Framework variants:** EVT_TAIL_MODEL
- **Ideas contributing:** 1
- **Cross-ref: **ST02** (LIVE, similarity=0.17)**
- **Classification:** NEW_SIGNAL


**Mechanism:** Umpires shift zone and tendencies based on game state, score differential, or fatigue; static umpire ratings miss dynamic within-game behavior

---

### 7. Weather × pitcher/park interaction [C044]

- **Domain:** WEATHER
- **Framework variants:** DISTRIBUTION_MODEL
- **Ideas contributing:** 1
- **Cross-ref: **P09** (LIVE, similarity=0.17)**
- **Classification:** NEW_SIGNAL


**Mechanism:** Weather interacts with pitcher type (flyball/groundball) and park geometry in ways that simple additive models miss

---

### 8. Bullpen deployment optimization [C004]

- **Domain:** BULLPEN
- **Framework variants:** HEURISTIC, MARKET_MICROSTRUCTURE, STATE_MODEL
- **Ideas contributing:** 6
- **No cross-reference to existing signals**
- **Classification:** NEW_SIGNAL


**Mechanism:** Manager bullpen strategy (matchup selection, usage patterns) creates predictable scoring patterns; suboptimal deployment is exploitable

---

### 9. Run distribution tail shape mispricing [C032]

- **Domain:** RUN_DISTRIBUTION
- **Framework variants:** DISTRIBUTION_MODEL, EVT_TAIL_MODEL, STATE_MODEL
- **Ideas contributing:** 9
- **No cross-reference to existing signals**
- **Classification:** NEW_SIGNAL


**Mechanism:** Totals markets assume roughly normal scoring distributions; actual run distributions have fat tails and zero-inflation that create systematic over/under bias

---

### 10. Dynamic park environment effect [C001]

- **Domain:** BALLPARK
- **Framework variants:** BAYESIAN_UPDATE, CAUSAL_IV, EVT_TAIL_MODEL, STATE_MODEL
- **Ideas contributing:** 8
- **Cross-ref: **P09** (LIVE, similarity=0.17)**
- **Classification:** NEW_SIGNAL


**Mechanism:** Park factors vary with weather, time of year, and game time in ways that static seasonal park factors miss; altitude + temperature creates explosive scoring conditions

---

### 11. SEQUENCING — unclustered signals [C035]

- **Domain:** SEQUENCING
- **Framework variants:** DISTRIBUTION_MODEL, EVT_TAIL_MODEL, HEURISTIC, STATE_MODEL
- **Ideas contributing:** 11
- **No cross-reference to existing signals**
- **Classification:** NEW_SIGNAL


**Mechanism:** Mixed sequencing signals without a shared core mechanism

---

### 12. PLAYER_FORM — unclustered signals [C030]

- **Domain:** PLAYER_FORM
- **Framework variants:** CAUSAL_IV, DISTRIBUTION_MODEL, EVT_TAIL_MODEL, STATE_MODEL
- **Ideas contributing:** 12
- **No cross-reference to existing signals**
- **Classification:** NEW_SIGNAL


**Mechanism:** Mixed player_form signals without a shared core mechanism

---

### 13. Pitcher latent fatigue state [C022]

- **Domain:** PITCHER
- **Framework variants:** DISTRIBUTION_MODEL, EVT_TAIL_MODEL, STATE_MODEL
- **Ideas contributing:** 12
- **Cross-ref: **F5_totals** (LIVE, similarity=0.47)**
- **Classification:** UPGRADE_CANDIDATE
- **Upgrade path:** Upgrade F5_totals (First-5-inning total projection) using DISTRIBUTION_MODEL/EVT_TAIL_MODEL/STATE_MODEL framework: Starter fatigue accumulates as a hidden state variable that markets price with lag; pitch count and velocity decline are

**Mechanism:** Starter fatigue accumulates as a hidden state variable that markets price with lag; pitch count and velocity decline are symptoms, not the state itself

---

### 14. BALLPARK — unclustered signals [C002]

- **Domain:** BALLPARK
- **Framework variants:** BAYESIAN_UPDATE, EVT_TAIL_MODEL
- **Ideas contributing:** 2
- **Cross-ref: **P09** (LIVE, similarity=0.17)**
- **Classification:** NEW_SIGNAL


**Mechanism:** Mixed ballpark signals without a shared core mechanism

---

### 15. Pitch sequencing / approach predictability [C036]

- **Domain:** SEQUENCING
- **Framework variants:** DISTRIBUTION_MODEL, HEURISTIC
- **Ideas contributing:** 6
- **No cross-reference to existing signals**
- **Classification:** NEW_SIGNAL


**Mechanism:** Predictable pitch sequencing patterns make pitchers more hittable; markets price aggregate stuff metrics but not sequence-level exploitation

---

### 16. Bullpen roster/quality transition [C006]

- **Domain:** BULLPEN
- **Framework variants:** BAYESIAN_UPDATE, CAUSAL_IV
- **Ideas contributing:** 2
- **No cross-reference to existing signals**
- **Classification:** NEW_SIGNAL


**Mechanism:** Bullpen quality changes (callups, trades, September expansion) create lag in market pricing of team relief quality

---

### 17. LINEUP — unclustered signals [C012]

- **Domain:** LINEUP
- **Framework variants:** BAYESIAN_UPDATE, CAUSAL_IV, DISTRIBUTION_MODEL, EVT_TAIL_MODEL, HEURISTIC, STATE_MODEL
- **Ideas contributing:** 17
- **No cross-reference to existing signals**
- **Classification:** NEW_SIGNAL


**Mechanism:** Mixed lineup signals without a shared core mechanism

---

### 18. RUN_DISTRIBUTION — unclustered signals [C033]

- **Domain:** RUN_DISTRIBUTION
- **Framework variants:** BAYESIAN_UPDATE, STATE_MODEL
- **Ideas contributing:** 4
- **No cross-reference to existing signals**
- **Classification:** NEW_SIGNAL


**Mechanism:** Mixed run_distribution signals without a shared core mechanism

---

### 19. WEATHER — unclustered signals [C043]

- **Domain:** WEATHER
- **Framework variants:** BAYESIAN_UPDATE, DISTRIBUTION_MODEL
- **Ideas contributing:** 2
- **No cross-reference to existing signals**
- **Classification:** NEW_SIGNAL


**Mechanism:** Mixed weather signals without a shared core mechanism

---

### 20. MARKET_BEHAVIOR — unclustered signals [C015]

- **Domain:** MARKET_BEHAVIOR
- **Framework variants:** DISTRIBUTION_MODEL, EVT_TAIL_MODEL, STATE_MODEL
- **Ideas contributing:** 4
- **No cross-reference to existing signals**
- **Classification:** NEW_SIGNAL


**Mechanism:** Mixed market_behavior signals without a shared core mechanism

---

