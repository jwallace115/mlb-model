# Source Audit — Statcast Interaction Families

## Available Statcast Features (per-start, 2022-2025)

| Feature | Column | Coverage (2024-2025) | Status |
|---------|--------|---------------------|--------|
| Release extension | extension | 99.9% | **AVAILABLE** |
| Spin rate (FF) | spin_rate_ff | 99.7% | **AVAILABLE** |
| Spin rate (SL) | spin_rate_sl | 90.0% | **AVAILABLE** |
| Hard hit rate | hard_hit_rate | 100.0% | **AVAILABLE** |
| Barrel rate | barrel_rate | 100.0% | **AVAILABLE** |
| Whiff rate | whiff_rate | 100.0% | **AVAILABLE** |
| Zone rate | zone_rate | 100.0% | **AVAILABLE** |
| Chase rate | chase_rate | 100.0% | **AVAILABLE** |
| Zone contact rate | zone_contact_rate | 100.0% | **AVAILABLE** |
| Avg exit velo | avg_exit_velo | 100.0% | **AVAILABLE** |
| Avg launch angle | avg_launch_angle | 100.0% | **AVAILABLE** |

## NOT Available Locally

| Feature | Required By | Status |
|---------|------------|--------|
| Groundball rate | Family 2 | **MISSING** — feature_table has column but ALL NaN |
| Flyball rate | Family 2 | **MISSING** |
| Active spin % | Family 3 | **MISSING** — not in Statcast per-start |
| Pitch tempo | Family 5 | **MISSING** — not in Statcast per-start |
| Team OAA | Family 4 | **MISSING** — not available locally |

## Family Feasibility

| Family | Feasible? | Notes |
|--------|-----------|-------|
| F1: Extension × Command | **YES** | extension + zone_rate/whiff_rate available |
| F2: Contact × Groundball | **NO** — GB rate not available | Can substitute launch_angle proxy |
| F3: Spin Loss × Contact | **PARTIAL** — spin_rate_ff available, active spin not | Use FF spin rate directly |
| F4: OAA Defense | **NO** — team OAA not available | SHELVE immediately |
| F5: Pitch Tempo | **NO** — tempo not available | SHELVE immediately |

## Adaptations
- Family 2: substitute avg_launch_angle as GB proxy (low launch angle ≈ high GB rate)
- Family 3: use spin_rate_ff directly instead of active spin %
- Families 4 and 5: SHELVE due to insufficient data
