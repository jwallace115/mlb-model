# Pitcher Archetype Report

**Method:** KMeans (k=6) on rolling 5-start pregame features
**Features:** Barrel rate, hard hit rate, whiff rate, GB rate, FB rate, K rate, HR rate

## Archetypes Identified

| Archetype | N (approx) | Barrel Rate | Hard Hit Rate | Whiff Rate | GB Rate | K Rate | Description |
|:----------|---:|---:|---:|---:|---:|---:|:------------|
| barrel_suppressor | ~21K | 0.028 | 0.336 | 0.243 | 0.370 | 0.220 | Low barrel, low hard hit, balanced |
| gb_suppressor | ~15K | 0.034 | 0.359 | 0.264 | 0.430 | 0.227 | High GB rate + moderate contact suppression |
| power_arm | ~20K | 0.038 | 0.359 | 0.285 | 0.354 | 0.267 | High whiff + high K, moderate contact |
| contact_mgr | ~19K | 0.044 | 0.385 | 0.228 | 0.362 | 0.199 | Low whiff, relies on location/contact |
| contact_mgr_3.0 | ~18K | 0.048 | 0.401 | 0.247 | 0.363 | 0.210 | Higher hard hit than contact_mgr |
| flyball_damage | ~16K | 0.054 | 0.410 | 0.240 | 0.332 | 0.208 | Highest barrel + hard hit + FB rate |

## TB Outcomes by Pitcher Archetype

| Archetype | P(TB=0) vs Batter | P(TB>=2) | P(TB>=3) |
|:----------|---:|---:|---:|
| power_arm | 0.466 | 0.299 | 0.167 |
| barrel_suppressor | 0.455 | 0.308 | 0.175 |
| gb_suppressor | 0.445 | 0.313 | 0.176 |
| contact_mgr_3.0 | 0.430 | 0.330 | 0.194 |
| contact_mgr | 0.428 | 0.328 | 0.191 |
| flyball_damage | 0.431 | 0.330 | 0.197 |

The spread between pitcher archetypes is narrower than hitters: P(TB=0) ranges from 0.428 (contact_mgr) to 0.466 (power_arm) — only 3.8pp. P(TB>=2) ranges from 0.299 to 0.330 — only 3.1pp.

This already hints that pitcher archetypes have less discriminatory power than hitter archetypes for TB outcomes.
