"""Tiny SQLite layer (standard library only). Data lives in ./data/docs.db"""
import os
import sqlite3
from pathlib import Path

DATA_DIR = Path(os.getenv("DATA_DIR", Path(__file__).parent / "data"))
DB_PATH = DATA_DIR / "docs.db"


def _conn():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(DB_PATH, timeout=30)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA journal_mode=WAL")
    return c


def execute(sql: str, params: tuple = ()) -> None:
    c = _conn()
    try:
        c.execute(sql, params)
        c.commit()
    finally:
        c.close()


def query(sql: str, params: tuple = ()) -> list[dict]:
    c = _conn()
    try:
        return [dict(r) for r in c.execute(sql, params).fetchall()]
    finally:
        c.close()


def init() -> None:
    c = _conn()
    try:
        c.executescript(
            """
            CREATE TABLE IF NOT EXISTS jobs(
              id TEXT PRIMARY KEY, filename TEXT, path TEXT, doc_type_hint TEXT,
              status TEXT, stage TEXT, progress INTEGER DEFAULT 0,
              result TEXT, error TEXT, created_at REAL, finished_at REAL);
            CREATE TABLE IF NOT EXISTS corrections(
              id INTEGER PRIMARY KEY AUTOINCREMENT, job_id TEXT, doc_type TEXT,
              field TEXT, old_value TEXT, new_value TEXT, created_at REAL);
            CREATE TABLE IF NOT EXISTS qa(
              id INTEGER PRIMARY KEY AUTOINCREMENT, job_id TEXT, question TEXT,
              answer_json TEXT, created_at REAL);
            """
        )
        # jobs that were running when the server stopped can never finish
        c.execute(
            "UPDATE jobs SET status='failed', error='Interrupted by server restart' "
            "WHERE status IN ('queued','processing')"
        )
        c.commit()
    finally:
        c.close()
