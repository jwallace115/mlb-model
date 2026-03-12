"""
Database layer — SQLite via stdlib sqlite3.
Creates tables on first run; all writes go through this module.
"""

import sqlite3
import json
from datetime import date
from config import DB_PATH


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db() -> None:
    """Create all tables if they do not exist."""
    with get_conn() as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS projections (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            game_date       TEXT NOT NULL,
            game_pk         INTEGER NOT NULL,
            home_team       TEXT NOT NULL,
            away_team       TEXT NOT NULL,
            home_sp         TEXT,
            away_sp         TEXT,
            home_sp_xfip    REAL,
            away_sp_xfip    REAL,
            home_sp_siera   REAL,
            away_sp_siera   REAL,
            home_wrc_plus   REAL,
            away_wrc_plus   REAL,
            park_factor     REAL,
            wind_speed      REAL,
            wind_direction  REAL,
            temperature     REAL,
            umpire_name     TEXT,
            umpire_factor   REAL,
            home_bp_fatigue REAL,
            away_bp_fatigue REAL,
            proj_total_full REAL,
            proj_total_f5   REAL,
            confidence      TEXT,
            confidence_score REAL,
            factors_json    TEXT,
            created_at      TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS results (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            projection_id   INTEGER REFERENCES projections(id),
            game_date       TEXT NOT NULL,
            game_pk         INTEGER NOT NULL,
            home_team       TEXT NOT NULL,
            away_team       TEXT NOT NULL,
            actual_total    REAL,
            actual_f5_total REAL,
            line_full       REAL,
            line_f5         REAL,
            result_full     TEXT,
            result_f5       TEXT,
            updated_at      TEXT DEFAULT (datetime('now'))
        );

        CREATE INDEX IF NOT EXISTS idx_proj_date    ON projections(game_date);
        CREATE INDEX IF NOT EXISTS idx_proj_game_pk ON projections(game_pk);
        CREATE INDEX IF NOT EXISTS idx_res_date     ON results(game_date);
        """)


def upsert_projection(row: dict) -> int:
    """Insert or replace a projection row; return the row id."""
    with get_conn() as conn:
        # Try to find existing row for this game_pk
        existing = conn.execute(
            "SELECT id FROM projections WHERE game_pk = ? AND game_date = ?",
            (row["game_pk"], row["game_date"])
        ).fetchone()

        if row.get("factors_json") and not isinstance(row["factors_json"], str):
            row["factors_json"] = json.dumps(row["factors_json"])

        columns = list(row.keys())
        placeholders = ", ".join("?" * len(columns))
        values = [row[c] for c in columns]

        if existing:
            set_clause = ", ".join(f"{c} = ?" for c in columns)
            conn.execute(
                f"UPDATE projections SET {set_clause} WHERE id = ?",
                values + [existing["id"]]
            )
            return existing["id"]
        else:
            cur = conn.execute(
                f"INSERT INTO projections ({', '.join(columns)}) VALUES ({placeholders})",
                values
            )
            return cur.lastrowid


def log_result(game_pk: int, game_date: str, actual_total: float = None,
               actual_f5_total: float = None, line_full: float = None,
               line_f5: float = None) -> None:
    """
    Record a game result and/or market lines.
    Can be called with actual_total=None to store lines before the game is final.
    On subsequent calls (when actual scores arrive) it updates the existing row.
    """
    with get_conn() as conn:
        proj = conn.execute(
            "SELECT * FROM projections WHERE game_pk = ? AND game_date = ?",
            (game_pk, game_date)
        ).fetchone()

        if not proj:
            return  # projection not yet written; caller will retry

        result_full = None
        result_f5   = None
        if line_full is not None and actual_total is not None:
            if actual_total > line_full:
                result_full = "OVER"
            elif actual_total < line_full:
                result_full = "UNDER"
            else:
                result_full = "PUSH"

        if line_f5 is not None and actual_f5_total is not None:
            if actual_f5_total > line_f5:
                result_f5 = "OVER"
            elif actual_f5_total < line_f5:
                result_f5 = "UNDER"
            else:
                result_f5 = "PUSH"

        existing = conn.execute(
            "SELECT id FROM results WHERE game_pk = ? AND game_date = ?",
            (game_pk, game_date)
        ).fetchone()

        if existing:
            # Update only non-None fields to avoid overwriting real scores with None
            updates, vals = [], []
            if actual_total    is not None: updates.append("actual_total = ?");    vals.append(actual_total)
            if actual_f5_total is not None: updates.append("actual_f5_total = ?"); vals.append(actual_f5_total)
            if line_full       is not None: updates.append("line_full = ?");       vals.append(line_full)
            if line_f5         is not None: updates.append("line_f5 = ?");         vals.append(line_f5)
            if result_full     is not None: updates.append("result_full = ?");     vals.append(result_full)
            if result_f5       is not None: updates.append("result_f5 = ?");       vals.append(result_f5)
            if updates:
                conn.execute(
                    f"UPDATE results SET {', '.join(updates)} WHERE id = ?",
                    vals + [existing["id"]]
                )
        else:
            conn.execute("""
                INSERT INTO results
                  (projection_id, game_date, game_pk, home_team, away_team,
                   actual_total, actual_f5_total, line_full, line_f5,
                   result_full, result_f5)
                VALUES (?,?,?,?,?,?,?,?,?,?,?)
            """, (
                proj["id"], game_date, game_pk,
                proj["home_team"], proj["away_team"],
                actual_total, actual_f5_total,
                line_full, line_f5,
                result_full, result_f5,
            ))


def get_recent_projections(days: int = 7) -> list:
    with get_conn() as conn:
        rows = conn.execute("""
            SELECT p.*, r.actual_total, r.line_full, r.result_full,
                   r.actual_f5_total, r.line_f5, r.result_f5
            FROM projections p
            LEFT JOIN results r ON p.game_pk = r.game_pk AND p.game_date = r.game_date
            WHERE p.game_date >= date('now', ? || ' days')
            ORDER BY p.game_date DESC, p.home_team
        """, (f"-{days}",)).fetchall()
        return [dict(r) for r in rows]


def get_season_record() -> dict:
    """Return win/loss record for projections that had a line to compare."""
    with get_conn() as conn:
        row = conn.execute("""
            SELECT
                COUNT(*) AS total,
                SUM(CASE WHEN result_full = 'OVER'  AND p.proj_total_full > line_full  THEN 1 ELSE 0 END) AS correct_over,
                SUM(CASE WHEN result_full = 'UNDER' AND p.proj_total_full < line_full  THEN 1 ELSE 0 END) AS correct_under,
                SUM(CASE WHEN result_full = 'PUSH'  THEN 1 ELSE 0 END)                                    AS pushes
            FROM results r
            JOIN projections p ON r.game_pk = p.game_pk AND r.game_date = p.game_date
            WHERE line_full IS NOT NULL
        """).fetchone()
        return dict(row) if row else {}
