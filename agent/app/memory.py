"""
Phase D — Memory Layer.
SQLite FTS5 store for incident history.
Used by agent loop to detect recurring patterns and inject host context.

DB file: dev_env/output/memory.db  (dev)
         /var/lib/aeonx-agent/memory.db  (prod, set MEMORY_DB_PATH)
"""
import sqlite3
import os
import json
import threading
from datetime import datetime, timezone, timedelta

_DB_PATH = os.environ.get(
    "MEMORY_DB_PATH",
    os.path.join(os.path.dirname(os.path.abspath(__file__)),
                 "../../dev_env/output/memory.db")
)
_lock = threading.Lock()


def _conn() -> sqlite3.Connection:
    db = sqlite3.connect(os.path.normpath(_DB_PATH), check_same_thread=False)
    db.row_factory = sqlite3.Row
    return db


def init_db():
    """Create tables if not exist and purge records older than 30 days. Called at agent startup."""
    with _lock:
        db = _conn()
        db.executescript("""
            CREATE TABLE IF NOT EXISTS incidents (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                incident_id TEXT UNIQUE,
                host        TEXT,
                client      TEXT,
                alert_name  TEXT,
                category    TEXT,
                severity    TEXT,
                action      TEXT,
                solution_id TEXT,
                confidence  REAL,
                false_positive INTEGER DEFAULT 0,
                created_at  TEXT
            );

            CREATE VIRTUAL TABLE IF NOT EXISTS incidents_fts USING fts5(
                incident_id,
                host,
                alert_name,
                category,
                action,
                content='incidents',
                content_rowid='id'
            );

            CREATE TRIGGER IF NOT EXISTS incidents_ai AFTER INSERT ON incidents BEGIN
                INSERT INTO incidents_fts(rowid, incident_id, host, alert_name, category, action)
                VALUES (new.id, new.incident_id, new.host, new.alert_name, new.category, new.action);
            END;
        """)
        # Purge incidents older than 15 days
        cutoff = (datetime.now(timezone.utc) - timedelta(days=15)).isoformat()
        db.execute("DELETE FROM incidents WHERE created_at < ?", (cutoff,))
        db.commit()
        db.close()


def write_incident(incident_id: str, host: str, client: str, alert_name: str,
                   category: str, severity: str, action: str,
                   solution_id: str = "", confidence: float = 0.0,
                   false_positive: bool = False):
    """Write a resolved incident to memory."""
    with _lock:
        db = _conn()
        try:
            db.execute("""
                INSERT OR IGNORE INTO incidents
                (incident_id, host, client, alert_name, category, severity,
                 action, solution_id, confidence, false_positive, created_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?)
            """, (incident_id, host, client, alert_name, category, severity,
                  action, solution_id, confidence, int(false_positive),
                  datetime.now(timezone.utc).isoformat()))
            db.commit()
        finally:
            db.close()


def get_host_history(host: str, days: int = 3) -> dict:
    """
    Return incident summary for a host over the last N days.
    Default window: 3 days. Used by agent loop for context injection.
    """
    since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    db = _conn()
    try:
        rows = db.execute("""
            SELECT alert_name, category, action, severity, false_positive, created_at
            FROM incidents
            WHERE host = ? AND created_at >= ?
            ORDER BY created_at DESC
            LIMIT 20
        """, (host, since)).fetchall()

        if not rows:
            return {"host": host, "total": 0, "days": days, "incidents": [],
                    "recurring": [], "false_positives": 0}

        # Count recurring alerts
        from collections import Counter
        names = Counter(r["alert_name"] for r in rows)
        recurring = [{"alert": n, "count": c} for n, c in names.most_common() if c >= 2]
        fp_count = sum(1 for r in rows if r["false_positive"])

        return {
            "host": host,
            "total": len(rows),
            "days": days,
            "false_positives": fp_count,
            "recurring": recurring,
            "incidents": [
                {"alert": r["alert_name"], "action": r["action"],
                 "severity": r["severity"], "ts": r["created_at"][:16]}
                for r in rows[:5]  # last 5 for brevity
            ],
        }
    finally:
        db.close()


def search_incidents(query: str, host: str = "", limit: int = 5) -> list[dict]:
    """
    FTS5 full-text search across incident history.
    Used by get_recent_alerts tool.
    """
    db = _conn()
    try:
        if host:
            rows = db.execute("""
                SELECT i.alert_name, i.category, i.action, i.severity,
                       i.false_positive, i.created_at
                FROM incidents i
                JOIN incidents_fts fts ON i.id = fts.rowid
                WHERE incidents_fts MATCH ? AND i.host = ?
                ORDER BY i.created_at DESC LIMIT ?
            """, (query, host, limit)).fetchall()
        else:
            rows = db.execute("""
                SELECT i.alert_name, i.category, i.action, i.severity,
                       i.false_positive, i.created_at
                FROM incidents i
                JOIN incidents_fts fts ON i.id = fts.rowid
                WHERE incidents_fts MATCH ?
                ORDER BY i.created_at DESC LIMIT ?
            """, (query, limit)).fetchall()

        return [dict(r) for r in rows]
    except Exception:
        return []
    finally:
        db.close()
