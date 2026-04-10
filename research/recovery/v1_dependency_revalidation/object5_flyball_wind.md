# OBJECT 5: flyball_wind_interaction

## Feature Definition

flyball_wind_interaction = flyball_pct * wind_factor_effective
- flyball_pct: from season-final FanGraphs (CONTAMINATED)
- wind_factor_effective: per-game Open-Meteo (CLEAN)

## PIT Alternative Check

PIT flyball_wind_interaction: 9715/9715 non-null
  mean=0.2188, std=0.3450
  min=0.0000, max=1.1000

Build script (lines 171-178):
  
  
  def build_flyball_proxy(pgl):
      """Build flyball rate from PGL fly_outs with expanding + shift(1)."""
      print("Building flyball proxy from PGL...")
      sp = pgl[pgl["starter_flag"] == 1].copy()
      sp = sp.sort_values(["player_id", "game_date"]).reset_index(drop=True)

## Feature Contribution in Clean V1
Ridge coefficient: 0.110575
Rank by |coef|: #11 of 25
Scaled contribution: mean=0.0001, std=0.1109
  as fraction of prediction range: ~2.5%

## Verdict: DIMINISHED
The PIT rebuild used fly_outs/(fly_outs+ground_outs) as a proxy for flyball%.
The feature has coefficient 0.1106 (rank 11/25), contributing
modestly to predictions. The PIT proxy is noisier than season-final FG fb%.
In LIVE operation, flyball% comes fresh from FG API (clean).
Impact: small — feature explains ~2-3% of total prediction variance.