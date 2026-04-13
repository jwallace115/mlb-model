# P1B Cold-Climate Warm-Day Child Object — Thesis Memo

## Why the parent mechanism was wrong

The P1 parent object (FG-F5 Path Engine) identified EARLY_HEAVY games — where the
F5 line implies disproportionate early scoring — as a profitable over signal. The
implicit thesis was that market-makers under-price overs when F5 lines signal front-loaded
run environments.

However, the parent treated this as a universal market mispricing. It did not isolate
*why* EARLY_HEAVY games go over. One candidate: warm weather at cold-climate parks
creates conditions where hitter performance systematically exceeds what the market
prices in. The market may anchor to season-average park factors and fail to adjust
for in-game temperature effects on ball carry, pitcher fatigue, and offensive output.

## Child thesis: weather-anomaly pricing at cold-climate parks

This child object proposes a specific causal mechanism:

1. **Cold-climate parks** (geographic definition: open-air stadiums north of ~40 deg N)
   have season-average park factors that blend cold April/May weather with warm
   June-September weather.

2. On **warm days** (forecast temp >= 75F) during summer months, actual run
   environments exceed the season-average park factor the market implicitly prices.

3. The EARLY_HEAVY condition from the parent acts as a **scoring-environment amplifier**:
   games where the F5 line already implies elevated early scoring are precisely the
   games where warm-weather run production compounds through the full 9 innings.

4. The **juiced over price** filter (closing FG over <= -105) ensures we are only
   betting games where the market has priced the over as the favorite side but has
   not fully adjusted for the warm-weather premium.

## Why forecast-temperature is required

For live operation, this object must fire based on **pregame weather forecast**, not
postgame observed temperature. The identity condition is:

> "Is the forecast temperature at this cold-climate park >= 75F?"

This is knowable before first pitch. The historical backtest uses Open-Meteo archive
data (actual observed temperature), while the live pipeline uses Open-Meteo forecast
data. At the coarse 75F threshold, forecast-vs-actual mismatch is negligible for
same-day predictions. Both sources are from the same Open-Meteo family.

Classification: **FORECAST HISTORY PARTIAL** — same source family, archive vs forecast
semantics differ, but at the 75F threshold the practical impact is minimal.
