"""Tiny SQLite layer. JSON-ish columns are stored as TEXT and decoded here."""
import json
import sqlite3
import threading
import time
import uuid
from typing import Any, Iterable, Optional

from .config import DB_PATH

_local = threading.local()
JSON_COLS = {"meta", "analysis", "prefs", "scores", "settings", "social", "exports", "result"}

SCHEMA = """
CREATE TABLE IF NOT EXISTS projects(
  id TEXT PRIMARY KEY, name TEXT, source_type TEXT, source_url TEXT,
  video_path TEXT, proxy_path TEXT, thumb_path TEXT, meta TEXT, status TEXT,
  stage TEXT, progress REAL DEFAULT 0, error TEXT, language TEXT,
  analysis TEXT, prefs TEXT, created_at REAL, updated_at REAL);
CREATE TABLE IF NOT EXISTS clips(
  id TEXT PRIMARY KEY, project_id TEXT, idx INTEGER, title TEXT, start REAL, end REAL,
  score REAL, scores TEXT, reason TEXT, hook TEXT, caption TEXT, kind TEXT,
  selected INTEGER DEFAULT 1, settings TEXT, social TEXT, exports TEXT, created_at REAL);
CREATE TABLE IF NOT EXISTS jobs(
  id TEXT PRIMARY KEY, project_id TEXT, clip_id TEXT, kind TEXT, status TEXT,
  stage TEXT, progress REAL DEFAULT 0, message TEXT, error TEXT, result TEXT,
  created_at REAL, updated_at REAL);
CREATE INDEX IF NOT EXISTS idx_clips_project ON clips(project_id);
CREATE INDEX IF NOT EXISTS idx_jobs_project ON jobs(project_id);
"""


def conn() -> sqlite3.Connection:
    c = getattr(_local, "c", None)
    if c is None:
        c = sqlite3.connect(DB_PATH, timeout=30)
        c.row_factory = sqlite3.Row
        c.execute("PRAGMA journal_mode=WAL")
        c.execute("PRAGMA foreign_keys=ON")
        _local.c = c
    return c


def init() -> None:
    conn().executescript(SCHEMA)
    conn().commit()


def new_id() -> str:
    return uuid.uuid4().hex[:12]


def _decode(row: Optional[sqlite3.Row]) -> Optional[dict]:
    if row is None:
        return None
    d = dict(row)
    for k in JSON_COLS:
        if k in d and isinstance(d[k], str):
            try:
                d[k] = json.loads(d[k])
            except ValueError:
                d[k] = None
    return d


def _enc(v: Any) -> Any:
    return json.dumps(v) if isinstance(v, (dict, list)) else v


def one(sql: str, args: Iterable = ()) -> Optional[dict]:
    return _decode(conn().execute(sql, tuple(args)).fetchone())


def many(sql: str, args: Iterable = ()) -> list:
    return [_decode(r) for r in conn().execute(sql, tuple(args)).fetchall()]


def insert(table: str, row: dict) -> None:
    cols = ",".join(row)
    qs = ",".join("?" for _ in row)
    conn().execute(f"INSERT INTO {table}({cols}) VALUES({qs})", [_enc(v) for v in row.values()])
    conn().commit()


def update(table: str, id_: str, **fields) -> None:
    if not fields:
        return
    if table in ("projects", "jobs"):
        fields["updated_at"] = time.time()
    sets = ",".join(f"{k}=?" for k in fields)
    conn().execute(f"UPDATE {table} SET {sets} WHERE id=?", [*(_enc(v) for v in fields.values()), id_])
    conn().commit()


def delete(table: str, where: str, args: Iterable = ()) -> None:
    conn().execute(f"DELETE FROM {table} WHERE {where}", tuple(args))
    conn().commit()
