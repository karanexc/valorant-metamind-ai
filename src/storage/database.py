from __future__ import annotations

import sqlite3
from pathlib import Path

import pandas as pd


SCHEMA = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS events (
    event_id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    tier TEXT,
    url TEXT,
    scraped_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS matches (
    match_id TEXT PRIMARY KEY,
    event_id TEXT,
    label TEXT,
    title TEXT,
    url TEXT,
    scraped_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (event_id) REFERENCES events(event_id)
);

CREATE TABLE IF NOT EXISTS player_map_stats (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id TEXT,
    event TEXT,
    tier TEXT,
    match_id TEXT,
    match_title TEXT,
    map TEXT,
    player TEXT,
    team TEXT,
    agent TEXT,
    kills INTEGER,
    deaths INTEGER,
    assists INTEGER,
    acs INTEGER,
    rating REAL,
    kda REAL,
    scraped_at TEXT DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(match_id, map, player, team, agent),
    FOREIGN KEY (event_id) REFERENCES events(event_id),
    FOREIGN KEY (match_id) REFERENCES matches(match_id)
);
"""


def connect(db_path: str | Path) -> sqlite3.Connection:
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(db_path: str | Path) -> None:
    with connect(db_path) as conn:
        conn.executescript(SCHEMA)


def upsert_event(conn: sqlite3.Connection, event: dict) -> None:
    conn.execute(
        """
        INSERT INTO events (event_id, title, tier, url)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(event_id) DO UPDATE SET
            title = excluded.title,
            tier = excluded.tier,
            url = excluded.url,
            scraped_at = CURRENT_TIMESTAMP
        """,
        (event.get("event_id"), event.get("title"), event.get("tier"), event.get("url") or event.get("url_path")),
    )


def upsert_match(conn: sqlite3.Connection, match: dict, event_id: str, title: str | None = None) -> None:
    conn.execute(
        """
        INSERT INTO matches (match_id, event_id, label, title, url)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(match_id) DO UPDATE SET
            event_id = excluded.event_id,
            label = excluded.label,
            title = COALESCE(excluded.title, matches.title),
            url = excluded.url,
            scraped_at = CURRENT_TIMESTAMP
        """,
        (match.get("match_id"), event_id, match.get("label"), title, match.get("url")),
    )


def delete_player_stats_for_match(conn: sqlite3.Connection, match_id: str) -> None:
    conn.execute("DELETE FROM player_map_stats WHERE match_id = ?", (str(match_id),))


def upsert_player_stats(conn: sqlite3.Connection, rows: list[dict]) -> None:
    if not rows:
        return

    conn.executemany(
        """
        INSERT INTO player_map_stats (
            event_id, event, tier, match_id, match_title, map, player, team, agent,
            kills, deaths, assists, acs, rating, kda
        )
        VALUES (
            :event_id, :event, :tier, :match_id, :match_title, :map, :player, :team, :agent,
            :kills, :deaths, :assists, :acs, :rating, :kda
        )
        ON CONFLICT(match_id, map, player, team, agent) DO UPDATE SET
            event_id = excluded.event_id,
            event = excluded.event,
            tier = excluded.tier,
            match_title = excluded.match_title,
            kills = excluded.kills,
            deaths = excluded.deaths,
            assists = excluded.assists,
            acs = excluded.acs,
            rating = excluded.rating,
            kda = excluded.kda,
            scraped_at = CURRENT_TIMESTAMP
        """,
        rows,
    )


def load_player_stats_from_db(db_path: str | Path) -> pd.DataFrame:
    with connect(db_path) as conn:
        return pd.read_sql_query("SELECT * FROM player_map_stats", conn)


def database_summary(db_path: str | Path) -> dict:
    with connect(db_path) as conn:
        return {
            "events": conn.execute("SELECT COUNT(*) FROM events").fetchone()[0],
            "matches": conn.execute("SELECT COUNT(*) FROM matches").fetchone()[0],
            "player_map_stats": conn.execute("SELECT COUNT(*) FROM player_map_stats").fetchone()[0],
            "players": conn.execute("SELECT COUNT(DISTINCT player) FROM player_map_stats").fetchone()[0],
            "teams": conn.execute("SELECT COUNT(DISTINCT team) FROM player_map_stats").fetchone()[0],
        }
