"""SQLite durability for completed calls, experiment snapshots and event ordering."""
from contextlib import contextmanager
import json
from pathlib import Path
import sqlite3


class Store:
    def __init__(self, path):
        self.path = str(path)
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with self.connection() as db:
            db.executescript('''
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS calls (key TEXT PRIMARY KEY, value TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS experiments (id TEXT PRIMARY KEY, signature TEXT UNIQUE NOT NULL, updated_at TEXT NOT NULL, value TEXT NOT NULL);
            ''')

    @contextmanager
    def connection(self):
        db = sqlite3.connect(self.path, timeout=30)
        try:
            with db:
                yield db
        finally:
            db.close()

    def call(self, key):
        with self.connection() as db:
            row = db.execute("SELECT value FROM calls WHERE key = ?", (key,)).fetchone()
        return json.loads(row[0]) if row else None

    def save_call(self, key, value):
        with self.connection() as db:
            db.execute("INSERT OR IGNORE INTO calls VALUES (?,?)", (key, json.dumps(value)))

    def save(self, experiment):
        with self.connection() as db:
            db.execute("INSERT INTO experiments VALUES (?,?,?,?) ON CONFLICT(id) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at",
                       (experiment["id"], experiment["signature"], experiment["updated_at"], json.dumps(experiment)))

    def get(self, experiment_id=None, signature=None):
        column, value = ("id", experiment_id) if experiment_id else ("signature", signature)
        with self.connection() as db:
            row = db.execute(f"SELECT value FROM experiments WHERE {column} = ?", (value,)).fetchone()
        return json.loads(row[0]) if row else None

    def all(self):
        with self.connection() as db:
            rows = db.execute("SELECT value FROM experiments ORDER BY updated_at DESC").fetchall()
        return [json.loads(r[0]) for r in rows]

    def recover(self):
        for experiment in self.all():
            if experiment["status"] in {"queued", "running"}:
                experiment.update(status="interrupted", phase="interrupted", error="The server stopped. Resume to reuse completed calls.")
                self.save(experiment)
