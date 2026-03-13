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
            lean            TEXT,
            star_rating     TEXT,
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

        CREATE TABLE IF NOT EXISTS graded_results (
            id                   INTEGER PRIMARY KEY AUTOINCREMENT,
            game_date            TEXT NOT NULL,
            game_pk              INTEGER NOT NULL,
            home_team            TEXT,
            away_team            TEXT,
            projected_total      REAL,
            recommendation       TEXT,
            star_rating          TEXT,
            star_count           INTEGER,
            confidence           TEXT,
            confidence_score     REAL,
            was_a_play           INTEGER DEFAULT 0,
            line                 REAL,
            edge                 REAL,
            actual_total         REAL,
            projection_error     REAL,
            result               TEXT,
            sp_home              TEXT,
            sp_away              TEXT,
            sp_home_xfip         REAL,
            sp_away_xfip         REAL,
            home_wrc_plus        REAL,
            away_wrc_plus        REAL,
            park_factor          REAL,
            temperature          REAL,
            wind_speed           REAL,
            wind_direction       REAL,
            wind_desc            TEXT,
            umpire               TEXT,
            umpire_rating        REAL,
            home_bullpen_innings REAL,
            away_bullpen_innings REAL,
            graded_at            TEXT DEFAULT (datetime('now')),
            UNIQUE(game_pk, game_date)
        );

        CREATE TABLE IF NOT EXISTS props (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            game_date     TEXT NOT NULL,
            game_pk       INTEGER NOT NULL,
            player_name   TEXT NOT NULL,
            team          TEXT,
            market        TEXT NOT NULL,   -- "K" | "TB"
            projection    REAL,
            line          REAL,
            edge          REAL,
            edge_pct      REAL,
            lean          TEXT,
            is_play       INTEGER DEFAULT 0,
            actual        REAL,
            result        TEXT,
            confidence    TEXT,
            created_at    TEXT DEFAULT (datetime('now')),
            UNIQUE(game_pk, game_date, player_name, market)
        );

        CREATE INDEX IF NOT EXISTS idx_proj_date    ON projections(game_date);
        CREATE INDEX IF NOT EXISTS idx_proj_game_pk ON projections(game_pk);
        CREATE INDEX IF NOT EXISTS idx_res_date     ON results(game_date);
        CREATE INDEX IF NOT EXISTS idx_gr_date      ON graded_results(game_date);
        CREATE INDEX IF NOT EXISTS idx_gr_result    ON graded_results(result);
        CREATE INDEX IF NOT EXISTS idx_props_date   ON props(game_date);
        CREATE INDEX IF NOT EXISTS idx_props_game   ON props(game_pk, game_date);
        """)

        # Migrate existing projections table — add lean/star_rating columns if missing
        for col, coltype in [("lean", "TEXT"), ("star_rating", "TEXT")]:
            try:
                conn.execute(f"ALTER TABLE projections ADD COLUMN {col} {coltype}")
            except Exception:
                pass  # column already exists


def upsert_projection(row: dict) -> int:
    """Insert or replace a projection row; return the row id."""
    with get_conn() as conn:
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


def write_graded_result(row: dict) -> None:
    """Upsert a fully graded result row."""
    with get_conn() as conn:
        columns = list(row.keys())
        placeholders = ", ".join("?" * len(columns))
        values = [row[c] for c in columns]
        set_clause = ", ".join(f"{c} = excluded.{c}" for c in columns
                               if c not in ("game_pk", "game_date"))
        conn.execute(
            f"INSERT INTO graded_results ({', '.join(columns)}) VALUES ({placeholders}) "
            f"ON CONFLICT(game_pk, game_date) DO UPDATE SET {set_clause}",
            values,
        )


def log_result(game_pk: int, game_date: str, actual_total: float = None,
               actual_f5_total: float = None, line_full: float = None,
               line_f5: float = None) -> None:
    """
    Record a game result and/or market lines.
    Can be called with actual_total=None to store lines before the game is final.
    """
    with get_conn() as conn:
        proj = conn.execute(
            "SELECT * FROM projections WHERE game_pk = ? AND game_date = ?",
            (game_pk, game_date)
        ).fetchone()

        if not proj:
            return

        result_full = None
        result_f5   = None
        if line_full is not None and actual_total is not None:
            if actual_total > line_full:   result_full = "OVER"
            elif actual_total < line_full: result_full = "UNDER"
            else:                          result_full = "PUSH"

        if line_f5 is not None and actual_f5_total is not None:
            if actual_f5_total > line_f5:   result_f5 = "OVER"
            elif actual_f5_total < line_f5: result_f5 = "UNDER"
            else:                           result_f5 = "PUSH"

        existing = conn.execute(
            "SELECT id FROM results WHERE game_pk = ? AND game_date = ?",
            (game_pk, game_date)
        ).fetchone()

        if existing:
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


def write_prop(row: dict) -> None:
    """Upsert a player prop row (projection + optional actual/result)."""
    with get_conn() as conn:
        columns = list(row.keys())
        placeholders = ", ".join("?" * len(columns))
        values = [row[c] for c in columns]
        conflict_keys = {"game_pk", "game_date", "player_name", "market"}
        set_clause = ", ".join(
            f"{c} = excluded.{c}" for c in columns if c not in conflict_keys
        )
        conn.execute(
            f"INSERT INTO props ({', '.join(columns)}) VALUES ({placeholders}) "
            f"ON CONFLICT(game_pk, game_date, player_name, market) DO UPDATE SET {set_clause}",
            values,
        )


def get_prop_season_stats() -> dict:
    """Return prop W/L summary grouped by market."""
    with get_conn() as conn:
        rows = conn.execute("""
            SELECT
                market,
                COUNT(*) AS total,
                SUM(CASE WHEN result = 'WIN'  THEN 1 ELSE 0 END) AS wins,
                SUM(CASE WHEN result = 'LOSS' THEN 1 ELSE 0 END) AS losses,
                SUM(CASE WHEN result = 'PUSH' THEN 1 ELSE 0 END) AS pushes
            FROM props
            WHERE is_play = 1 AND result IS NOT NULL
            GROUP BY market
        """).fetchall()
        out = {}
        for r in rows:
            d    = dict(r)
            net  = d["wins"] + d["losses"]
            roi  = round((d["wins"] * 0.9091 - d["losses"]) / net * 100, 1) if net else None
            wpct = round(d["wins"] / net * 100, 1) if net else None
            out[d["market"]] = {**d, "decided": net, "win_pct": wpct, "roi": roi}
        return out


def get_props_for_date(game_date: str) -> list[dict]:
    """Return all props rows for a given date."""
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM props WHERE game_date = ? ORDER BY game_pk, market, player_name",
            (game_date,),
        ).fetchall()
        return [dict(r) for r in rows]


def get_all_graded_results() -> list[dict]:
    """Return all rows from graded_results ordered by date desc."""
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM graded_results ORDER BY game_date DESC, home_team"
        ).fetchall()
        return [dict(r) for r in rows]


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
                SUM(CASE WHEN result = 'WIN'  THEN 1 ELSE 0 END) AS wins,
                SUM(CASE WHEN result = 'LOSS' THEN 1 ELSE 0 END) AS losses,
                SUM(CASE WHEN result = 'PUSH' THEN 1 ELSE 0 END) AS pushes,
                SUM(CASE WHEN result = 'NO_LINE' THEN 1 ELSE 0 END) AS no_line,
                SUM(CASE WHEN result = 'PENDING' THEN 1 ELSE 0 END) AS pending
            FROM graded_results
            WHERE was_a_play = 1
        """).fetchone()
        return dict(row) if row else {}
