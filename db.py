import sqlite3
import os
from datetime import datetime

DB_PATH = os.path.expanduser('~/Library/Application Support/homenetmon/data.db')

# Keep 7 days of history; max chart window is 1 hour
_PRUNE_SECONDS = 7 * 24 * 3600


def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute('''
            CREATE TABLE IF NOT EXISTS pings (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp  REAL    NOT NULL,
                host       TEXT    NOT NULL,
                host_type  TEXT    NOT NULL,
                latency_ms REAL,
                success    INTEGER NOT NULL
            )
        ''')
        # Composite index matches all query WHERE clauses
        conn.execute(
            'CREATE INDEX IF NOT EXISTS idx_host_ts ON pings(host_type, timestamp)'
        )


def insert_ping(host, host_type, latency_ms, success):
    now = datetime.now().timestamp()
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            'INSERT INTO pings (timestamp, host, host_type, latency_ms, success) VALUES (?,?,?,?,?)',
            (now, host, host_type, latency_ms, 1 if success else 0)
        )
        conn.execute(
            'DELETE FROM pings WHERE timestamp < ?',
            (now - _PRUNE_SECONDS,)
        )


def get_recent_pings(host_type, seconds=120):
    cutoff = datetime.now().timestamp() - seconds
    with sqlite3.connect(DB_PATH) as conn:
        return conn.execute(
            'SELECT timestamp, latency_ms, success FROM pings '
            'WHERE host_type=? AND timestamp > ? ORDER BY timestamp',
            (host_type, cutoff)
        ).fetchall()


def get_stats(host_type, seconds=120):
    cutoff = datetime.now().timestamp() - seconds
    with sqlite3.connect(DB_PATH) as conn:
        row = conn.execute('''
            SELECT
                COUNT(*)                                                      AS total,
                SUM(success)                                                  AS successes,
                AVG(CASE WHEN success=1 AND latency_ms IS NOT NULL
                         THEN latency_ms END)                                 AS avg_ms,
                MIN(CASE WHEN success=1 AND latency_ms IS NOT NULL
                         THEN latency_ms END)                                 AS min_ms,
                MAX(CASE WHEN success=1 AND latency_ms IS NOT NULL
                         THEN latency_ms END)                                 AS max_ms
            FROM pings
            WHERE host_type=? AND timestamp > ?
        ''', (host_type, cutoff)).fetchone()

    total = row[0] or 0
    if not total:
        return {'loss_pct': 0.0, 'avg_ms': None, 'min_ms': None, 'max_ms': None, 'count': 0}

    successes = row[1] or 0
    return {
        'loss_pct': round(((total - successes) / total) * 100, 1),
        'avg_ms':   round(row[2], 1) if row[2] is not None else None,
        'min_ms':   round(row[3], 1) if row[3] is not None else None,
        'max_ms':   round(row[4], 1) if row[4] is not None else None,
        'count':    total,
    }
