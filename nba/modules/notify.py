"""
Pushover notification sender.

Sends push notifications for high-confidence NBA plays.
Credentials loaded from environment: PUSHOVER_TOKEN, PUSHOVER_USER.

Gracefully no-ops if credentials are not set — daily run continues without
notifications.
"""

import logging
import os
from typing import Optional

import requests

logger = logging.getLogger(__name__)

_PUSHOVER_URL = "https://api.pushover.net/1/messages.json"

_TOKEN = os.environ.get("PUSHOVER_TOKEN", "")
_USER  = os.environ.get("PUSHOVER_USER",  "")


def _send(title: str, message: str, priority: int = 0) -> bool:
    """
    Send one Pushover notification.
    priority: 0 = normal, 1 = high (bypasses quiet hours), -1 = low/quiet.
    Returns True on success, False on failure.
    """
    if not _TOKEN or not _USER:
        logger.warning("PUSHOVER_TOKEN/PUSHOVER_USER not set — notification skipped")
        return False
    try:
        resp = requests.post(
            _PUSHOVER_URL,
            data={
                "token":   _TOKEN,
                "user":    _USER,
                "title":   title,
                "message": message,
                "priority": priority,
            },
            timeout=10,
        )
        resp.raise_for_status()
        logger.info(f"Pushover sent: {title!r}")
        return True
    except Exception as e:
        logger.warning(f"Pushover failed: {e}")
        return False


def send_nba_card(plays: list[dict], game_date: str) -> None:
    """
    Send Pushover notification for NBA HIGH confidence plays.
    One message containing all HIGH plays. Skips if no HIGH plays exist.

    play dict keys: home_team, away_team, lean, pred_total, line, edge,
                    confidence, h1_lean, pred_h1, h1_line, h1_edge, game_time_et
    """
    high_plays = [p for p in plays if p.get("confidence") == "HIGH"]
    if not high_plays:
        logger.info("No HIGH confidence NBA plays — Pushover not sent")
        return

    lines = [f"[NBA] {game_date} — {len(high_plays)} HIGH confidence play(s)\n"]
    for p in high_plays:
        matchup = f"{p['away_team']} @ {p['home_team']}"
        lean    = p.get("lean", "?")
        pred    = p.get("pred_total", 0)
        line    = p.get("line")
        edge    = p.get("edge")
        time_et = p.get("game_time_et", "")

        line_str = f"Line {line:.1f}" if line else "No line"
        edge_str = f"Edge {edge:+.1f}" if edge is not None else ""
        lines.append(
            f"• {matchup} ({time_et})\n"
            f"  {lean}  Proj {pred:.1f}  {line_str}  {edge_str}"
        )

        # H1 if available
        pred_h1  = p.get("pred_h1")
        h1_line  = p.get("h1_line")
        h1_lean  = p.get("h1_lean")
        h1_edge  = p.get("h1_edge")
        if pred_h1 and h1_lean:
            h1_line_str = f"H1 Line {h1_line:.1f}" if h1_line else "No H1 line"
            h1_edge_str = f"Edge {h1_edge:+.1f}" if h1_edge is not None else ""
            lines.append(
                f"  H1: {h1_lean}  H1 Proj {pred_h1:.1f}  {h1_line_str}  {h1_edge_str}"
            )

    message = "\n".join(lines)
    _send(
        title=f"NBA Plays — {game_date}",
        message=message,
        priority=0,
    )


def send_mlb_plays_alert(plays: list[dict], game_date: str) -> None:
    """
    Send Pushover notification for MLB HIGH/⭐⭐⭐ plays.
    Separate from NBA — clearly labeled.
    """
    if not plays:
        return
    lines = [f"[MLB] {game_date} — {len(plays)} play(s)\n"]
    for p in plays:
        g    = p.get("game", {})
        proj = p.get("proj", {})
        fe   = p.get("full_edge", {})
        matchup = f"{g.get('away_team','?')} @ {g.get('home_team','?')}"
        lean    = proj.get("lean", "?")
        pred    = proj.get("proj_total_full", 0)
        line    = fe.get("consensus")
        edge    = fe.get("edge")
        rating  = p.get("rating", "")
        line_str = f"Line {line:.1f}" if line else "No line"
        edge_str = f"Edge {edge:+.1f}" if edge is not None else ""
        lines.append(f"• {rating} {matchup}  {lean}  Proj {pred:.1f}  {line_str}  {edge_str}")

    _send(
        title=f"MLB Plays — {game_date}",
        message="\n".join(lines),
        priority=0,
    )
