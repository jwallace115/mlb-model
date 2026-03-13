"""
Weather module — Open-Meteo API (free, no key required).

For each stadium, fetches:
  - temperature (°F) at game time
  - wind speed (mph) at game time
  - wind direction (degrees, meteorological: 0=N, 90=E, 180=S, 270=W)
  - weather description

Computes a wind_factor and temp_factor for the projection engine.
"""

import logging
import math
from datetime import datetime, timezone
from typing import Optional

import requests

from config import (
    OPEN_METEO_API, STADIUMS,
    TEMP_BASELINE_F, TEMP_RUNS_PER_DEG,
    WIND_RUNS_PER_MPH, DATA_DIR,
)

logger = logging.getLogger(__name__)


def get_roof_status(team_abb: str) -> str:
    """
    Return the roof status for today's game: 'open', 'closed', or 'unknown'.
    Reads from data/roof_status.json (format: {date: {team_abb: status}}).
    Returns 'unknown' if file doesn't exist or team not listed for today.
    """
    import os
    path = os.path.join(DATA_DIR, "roof_status.json")
    if not os.path.exists(path):
        return "unknown"
    try:
        import json
        with open(path) as f:
            data = json.load(f)
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        return data.get(today, {}).get(team_abb.upper(), "unknown")
    except Exception:
        return "unknown"


_WMO_CODES = {
    0: "Clear", 1: "Mainly Clear", 2: "Partly Cloudy", 3: "Overcast",
    45: "Foggy", 48: "Icy Fog",
    51: "Light Drizzle", 53: "Drizzle", 55: "Heavy Drizzle",
    61: "Light Rain", 63: "Rain", 65: "Heavy Rain",
    71: "Light Snow", 73: "Snow", 75: "Heavy Snow",
    80: "Rain Showers", 81: "Showers", 82: "Heavy Showers",
    95: "Thunderstorm", 96: "Thunderstorm w/ Hail", 99: "Heavy Thunderstorm",
}


def fetch_weather(team_abb: str, game_time_et: str = None) -> dict:
    """
    Fetch weather for *team_abb*'s stadium.

    game_time_et: 12-hour ET time string like '07:05 PM ET' from the schedule.
                  If None, defaults to 7 PM ET.
    Returns a dict with temperature_f, wind_speed_mph, wind_direction_deg,
    wind_factor, temp_factor, description, and is_dome.
    """
    stadium = STADIUMS.get(team_abb)
    if not stadium:
        logger.warning(f"No stadium data for {team_abb}")
        return _neutral_weather(team_abb)

    # Fixed dome — always climate controlled
    if stadium.get("dome"):
        return {
            "team":            team_abb,
            "stadium":         stadium["name"],
            "temperature_f":   72.0,
            "wind_speed_mph":  0.0,
            "wind_direction":  0,
            "wind_factor":     1.0,
            "temp_factor":     1.0,
            "wind_desc":       "Dome",
            "description":     "Dome — climate controlled",
            "is_dome":         True,
        }

    # Retractable roof — check today's status
    if stadium.get("retractable_roof"):
        roof = get_roof_status(team_abb)
        if roof == "closed":
            logger.info(f"{team_abb}: retractable roof confirmed CLOSED — using dome weather")
            return {
                "team":            team_abb,
                "stadium":         stadium["name"],
                "temperature_f":   72.0,
                "wind_speed_mph":  0.0,
                "wind_direction":  0,
                "wind_factor":     1.0,
                "temp_factor":     1.0,
                "wind_desc":       "Roof Closed",
                "description":     "Retractable roof closed — climate controlled",
                "is_dome":         True,
            }
        elif roof == "open":
            logger.info(f"{team_abb}: retractable roof confirmed OPEN — using live weather")
        else:
            logger.info(f"{team_abb}: retractable roof status unknown — using live weather")
        # Fall through to fetch live weather

    lat, lon = stadium["lat"], stadium["lon"]

    # Parse game time → UTC hour, accounting for ET offset and date rollover
    game_hour_utc = _parse_game_hour_utc(game_time_et)
    # ET is UTC-5 in March (before DST) / UTC-4 after DST (Mar 8)
    # Open-Meteo returns times in the stadium's local timezone ("timezone=auto")
    # so we target local time directly
    game_hour_local = _parse_game_hour_local(game_time_et)

    try:
        resp = requests.get(
            OPEN_METEO_API,
            params={
                "latitude":          lat,
                "longitude":         lon,
                "hourly":            "temperature_2m,windspeed_10m,winddirection_10m,weathercode",
                "temperature_unit":  "fahrenheit",
                "windspeed_unit":    "mph",
                "timezone":          "auto",
                "forecast_days":     2,
            },
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        logger.error(f"Open-Meteo request failed for {team_abb}: {e}")
        return _neutral_weather(team_abb)

    hourly = data.get("hourly", {})
    times  = hourly.get("time", [])
    temps  = hourly.get("temperature_2m", [])
    winds  = hourly.get("windspeed_10m", [])
    wdirs  = hourly.get("winddirection_10m", [])
    wcodes = hourly.get("weathercode", [])

    # Target today's date (local to stadium) at the game's local hour
    # Open-Meteo returns local times when timezone=auto
    local_today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    # If it's already past midnight UTC, the ET date might be yesterday
    # Use ET date for games in North America
    et_offset = -4  # EDT after Mar 8 DST change
    et_now = datetime.now(timezone.utc) + __import__('datetime').timedelta(hours=et_offset)
    local_today = et_now.strftime("%Y-%m-%d")

    target_str = f"{local_today}T{game_hour_local:02d}:00"

    idx = 0
    for i, t in enumerate(times):
        if t >= target_str:
            idx = i
            break

    temp_f   = float(temps[idx])  if idx < len(temps)  else 72.0
    wind_mph = float(winds[idx])  if idx < len(winds)   else 0.0
    wind_dir = float(wdirs[idx])  if idx < len(wdirs)   else 0.0
    wcode    = int(wcodes[idx])   if idx < len(wcodes)  else 0

    wind_factor = _calc_wind_factor(wind_mph, wind_dir, stadium["cf_bearing"])
    temp_factor = 1.0 + (temp_f - TEMP_BASELINE_F) * TEMP_RUNS_PER_DEG

    wind_desc = _wind_direction_desc(wind_dir, stadium["cf_bearing"])

    return {
        "team":            team_abb,
        "stadium":         stadium["name"],
        "temperature_f":   round(temp_f, 1),
        "wind_speed_mph":  round(wind_mph, 1),
        "wind_direction":  round(wind_dir),
        "wind_factor":     round(wind_factor, 4),
        "temp_factor":     round(temp_factor, 4),
        "wind_desc":       wind_desc,
        "description":     _WMO_CODES.get(wcode, "Unknown"),
        "is_dome":         False,
    }


def _parse_game_hour_local(game_time_et: str | None) -> int:
    """
    Parse a game time string like '07:05 PM ET' and return the ET hour (0-23).
    Defaults to 19 (7 PM) if unparseable.
    """
    if not game_time_et:
        return 19
    try:
        # Strip ' ET' suffix
        t = game_time_et.replace(" ET", "").strip()
        dt = datetime.strptime(t, "%I:%M %p")
        return dt.hour
    except Exception:
        return 19


def _parse_game_hour_utc(game_time_et: str | None) -> int:
    """Return the UTC hour for a given ET game time (kept for reference)."""
    et_hour = _parse_game_hour_local(game_time_et)
    # After Mar 8 DST: EDT = UTC-4
    return (et_hour + 4) % 24


def _calc_wind_factor(wind_mph: float, wind_from_deg: float, cf_bearing: float) -> float:
    """
    Calculate multiplicative wind factor on runs.

    wind_from_deg: meteorological wind direction (where wind is coming FROM).
    cf_bearing: compass bearing from home plate to center field.
    """
    if wind_mph < 2.0:
        return 1.0

    # Convert "wind from" to "wind to" direction
    wind_to_deg = (wind_from_deg + 180) % 360

    # Angle between wind direction and CF bearing
    angle_diff = math.radians(cf_bearing - wind_to_deg)
    # dot product component: +1 = fully blowing out, -1 = fully blowing in
    out_component = math.cos(angle_diff)

    wind_effect = wind_mph * out_component * WIND_RUNS_PER_MPH
    return 1.0 + wind_effect


def _wind_direction_desc(wind_from_deg: float, cf_bearing: float) -> str:
    """Human-readable wind description relative to the ballpark."""
    wind_to_deg = (wind_from_deg + 180) % 360
    angle_diff  = (cf_bearing - wind_to_deg + 360) % 360
    if angle_diff < 45 or angle_diff > 315:
        return "Blowing Out to CF"
    elif 45 <= angle_diff < 135:
        return "Blowing L to R"
    elif 135 <= angle_diff < 225:
        return "Blowing In from CF"
    else:
        return "Blowing R to L"


def _neutral_weather(team_abb: str) -> dict:
    return {
        "team":            team_abb,
        "stadium":         STADIUMS.get(team_abb, {}).get("name", "Unknown"),
        "temperature_f":   72.0,
        "wind_speed_mph":  0.0,
        "wind_direction":  0,
        "wind_factor":     1.0,
        "temp_factor":     1.0,
        "wind_desc":       "Unknown",
        "description":     "Data unavailable",
        "is_dome":         False,
    }
