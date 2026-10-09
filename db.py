"""SQLite persistence; no cloud/database server required."""
import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path

DB_PATH = os.getenv('WZ_DATABASE', str(Path(__file__).resolve().parent.parent / 'data' / 'wichtelzauber.sqlite3'))

SCHEMA = """
PRAGMA foreign_keys=ON;
CREATE TABLE IF NOT EXISTS admins (
 id TEXT PRIMARY KEY, username TEXT NOT NULL UNIQUE COLLATE NOCASE,
 password_hash TEXT NOT NULL, failed_attempts INTEGER NOT NULL DEFAULT 0,
 locked_until TEXT, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS groups (
 id TEXT PRIMARY KEY, owner_id TEXT NOT NULL REFERENCES admins(id) ON DELETE CASCADE,
 invite_token TEXT NOT NULL UNIQUE, name TEXT NOT NULL, description TEXT NOT NULL DEFAULT '',
 rules TEXT NOT NULL DEFAULT '', budget_cents INTEGER, event_date TEXT, location TEXT NOT NULL DEFAULT '',
 archived INTEGER NOT NULL DEFAULT 0, notice TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS participants (
 id TEXT PRIMARY KEY, group_id TEXT NOT NULL REFERENCES groups(id) ON DELETE CASCADE,
 name TEXT NOT NULL, pin_hash TEXT, status TEXT NOT NULL DEFAULT 'new'
 CHECK(status IN ('new','pending','active','reset')),
 wish TEXT NOT NULL DEFAULT '', opened_at TEXT,
 failed_attempts INTEGER NOT NULL DEFAULT 0, locked_until TEXT,
 created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_participants_group ON participants(group_id);
CREATE TABLE IF NOT EXISTS exclusions (
 id TEXT PRIMARY KEY, group_id TEXT NOT NULL REFERENCES groups(id) ON DELETE CASCADE,
 giver_id TEXT NOT NULL REFERENCES participants(id) ON DELETE CASCADE,
 receiver_id TEXT NOT NULL REFERENCES participants(id) ON DELETE CASCADE,
 kind TEXT NOT NULL CHECK(kind IN ('pair','direct')),
 pair_key TEXT, UNIQUE(group_id, giver_id, receiver_id), CHECK(giver_id != receiver_id)
);
CREATE TABLE IF NOT EXISTS draw_rounds (
 id TEXT PRIMARY KEY, group_id TEXT NOT NULL REFERENCES groups(id) ON DELETE CASCADE,
 state TEXT NOT NULL CHECK(state IN ('active','invalidated')),
 created_at TEXT NOT NULL, invalidated_at TEXT
);
CREATE UNIQUE INDEX IF NOT EXISTS one_active_round_per_group ON draw_rounds(group_id) WHERE state='active';
CREATE TABLE IF NOT EXISTS assignments (
 id TEXT PRIMARY KEY, round_id TEXT NOT NULL REFERENCES draw_rounds(id) ON DELETE CASCADE,
 giver_id TEXT NOT NULL REFERENCES participants(id) ON DELETE CASCADE,
 receiver_id TEXT NOT NULL REFERENCES participants(id) ON DELETE CASCADE,
 UNIQUE(round_id, giver_id), UNIQUE(round_id, receiver_id), CHECK(giver_id != receiver_id)
);
CREATE TABLE IF NOT EXISTS sessions (
 token_hash TEXT PRIMARY KEY, kind TEXT NOT NULL CHECK(kind IN ('admin','member')),
 subject_id TEXT NOT NULL, csrf_token TEXT NOT NULL, expires_at TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_session_subject ON sessions(kind, subject_id);
CREATE TABLE IF NOT EXISTS audit_events (
 id TEXT PRIMARY KEY, group_id TEXT NOT NULL REFERENCES groups(id) ON DELETE CASCADE,
 actor TEXT NOT NULL, action TEXT NOT NULL, detail TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL
);
"""


def connect(db_path=None):
    p = str(db_path or os.getenv('WZ_DATABASE', DB_PATH))
    Path(p).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(p, timeout=20, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA foreign_keys=ON')
    conn.execute('PRAGMA busy_timeout=20000')
    return conn


def initialize(db_path=None):
    with connect(db_path) as conn:
        conn.executescript(SCHEMA)
        conn.execute('PRAGMA journal_mode=WAL')


@contextmanager
def transaction(db_path=None):
    conn = connect(db_path)
    try:
        conn.execute('BEGIN IMMEDIATE')
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def one(conn, sql, args=()):
    return conn.execute(sql, args).fetchone()


def all_rows(conn, sql, args=()):
    return [dict(x) for x in conn.execute(sql, args)]
