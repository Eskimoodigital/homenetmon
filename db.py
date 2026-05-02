import sqlite3
import os
from datetime import datetime

DB_PATH = os.path.expanduser('~/Library/Application Support/homenetmon/data.db')


def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute('''
        CREATE TABLE IF NOT EXISTS pings (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp REAL    NOT NULL,
            host      TEXT    NOT NULL,
            host_type TEXT    NOT NULL,
            latency_ms REAL,
            success   INTEGER NOT NULL
        )
    ''')
    conn.execute('CREATE INDEX IF NOT EXISTS idx_ts ON pings(timestamp)')
    conn.commit()
    conn.close()


def insert_ping(host, host_type, latency_ms, success):
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        'INSERT INTO pings (timestamp, host, host_type, latency_ms, success) VALUES (?,?,?,?,?)',
        (datetime.now().timestamp(), host, host_type, latency_ms, 1 if success else 0)
    )
    conn.commit()
    conn.close()


def get_recent_pings(host_type, seconds=120):
    conn = sqlite3.connect(DB_PATH)
    cutoff = datetime.now().timestamp() - seconds
    rows = conn.execute(
        'SELECT timestamp, latency_ms, success FROM pings '
        'WHERE host_type=? AND timestamp > ? ORDER BY timestamp',
        (host_type, cutoff)
    ).fetchall()
    conn.close()
    return rows


def get_stats(host_type, seconds=120):
    conn = sqlite3.connect(DB_PATH)
    cutoff = datetime.now().timestamp() - seconds
    rows = conn.execute(
        'SELECT latency_ms, success FROM pings WHERE host_type=? AND timestamp > ?',
        (host_type, cutoff)
    ).fetchall()
    conn.close()

    if not rows:
        return {'loss_pct': 0.0, 'avg_ms': None, 'min_ms': None, 'max_ms': None, 'count': 0}

    total = len(rows)
    good = [r[0] for r in rows if r[1] == 1 and r[0] is not None]
    loss_pct = ((total - len(good)) / total) * 100

    return {
        'loss_pct': round(loss_pct, 1),
        'avg_ms':   round(sum(good) / len(good), 1) if good else None,
        'min_ms':   round(min(good), 1) if good else None,
        'max_ms':   round(max(good), 1) if good else None,
        'count':    total,
    }
