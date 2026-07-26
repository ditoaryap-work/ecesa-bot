from __future__ import annotations
"""
SQLite wrapper via aiosqlite.
Menyimpan: alert state, SSH log history, mute state, maintenance log.
"""
import asyncio
import aiosqlite
from core.config import DB_PATH


async def init_db() -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript("""
            CREATE TABLE IF NOT EXISTS alert_state (
                key       TEXT PRIMARY KEY,
                status    TEXT NOT NULL DEFAULT 'ok',
                fired_at  TEXT,
                count     INTEGER DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS ssh_log (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                user      TEXT,
                ip        TEXT,
                trusted   INTEGER DEFAULT 0,
                logged_at TEXT DEFAULT (datetime('now','localtime'))
            );

            CREATE TABLE IF NOT EXISTS mute (
                id         INTEGER PRIMARY KEY CHECK (id = 1),
                until      TEXT
            );
            INSERT OR IGNORE INTO mute (id, until) VALUES (1, NULL);

            CREATE TABLE IF NOT EXISTS maintenance (
                id         INTEGER PRIMARY KEY CHECK (id = 1),
                active     INTEGER DEFAULT 0,
                started_at TEXT
            );
            INSERT OR IGNORE INTO maintenance (id, active) VALUES (1, 0);

            CREATE TABLE IF NOT EXISTS disk_snapshot (
                id         INTEGER PRIMARY KEY CHECK (id = 1),
                used_gb    REAL,
                snapped_at TEXT DEFAULT (datetime('now','localtime'))
            );
        """)
        await db.commit()


# ─── Alert State ─────────────────────────────────────────────────────────────

async def get_alert_state(key: str) -> dict:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT status, fired_at, count FROM alert_state WHERE key = ?", (key,)
        ) as cur:
            row = await cur.fetchone()
            if row:
                return dict(row)
            return {"status": "ok", "fired_at": None, "count": 0}


async def set_alert_state(key: str, status: str) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        if status == "fail":
            await db.execute("""
                INSERT INTO alert_state (key, status, fired_at, count)
                VALUES (?, 'fail', datetime('now','localtime'), 1)
                ON CONFLICT(key) DO UPDATE SET
                    status   = 'fail',
                    fired_at = CASE WHEN status != 'fail' THEN datetime('now','localtime') ELSE fired_at END,
                    count    = CASE WHEN status != 'fail' THEN 1 ELSE count + 1 END
            """, (key,))
        else:
            await db.execute("""
                INSERT INTO alert_state (key, status, fired_at, count)
                VALUES (?, 'ok', NULL, 0)
                ON CONFLICT(key) DO UPDATE SET status = 'ok', fired_at = NULL, count = 0
            """, (key,))
        await db.commit()


# ─── SSH Log ─────────────────────────────────────────────────────────────────

async def add_ssh_log(user: str, ip: str, trusted: bool) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO ssh_log (user, ip, trusted) VALUES (?, ?, ?)",
            (user, ip, 1 if trusted else 0)
        )
        await db.commit()


async def get_ssh_logs(limit: int = 20) -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT user, ip, trusted, logged_at FROM ssh_log ORDER BY id DESC LIMIT ?",
            (limit,)
        ) as cur:
            return [dict(r) for r in await cur.fetchall()]


# ─── Mute ─────────────────────────────────────────────────────────────────────

async def set_mute(until_iso: str | None) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE mute SET until = ? WHERE id = 1", (until_iso,))
        await db.commit()


async def is_muted() -> tuple[bool, str | None]:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT until FROM mute WHERE id = 1") as cur:
            row = await cur.fetchone()
            if not row or not row[0]:
                return False, None
            from datetime import datetime
            until = datetime.fromisoformat(row[0])
            if datetime.now() < until:
                return True, row[0]
            # expired — auto-clear
            await db.execute("UPDATE mute SET until = NULL WHERE id = 1")
            await db.commit()
            return False, None


# ─── Maintenance ─────────────────────────────────────────────────────────────

async def set_maintenance(active: bool) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        if active:
            await db.execute("""
                UPDATE maintenance SET active = 1,
                started_at = datetime('now','localtime') WHERE id = 1
            """)
        else:
            await db.execute("UPDATE maintenance SET active = 0, started_at = NULL WHERE id = 1")
        await db.commit()


async def get_maintenance() -> dict:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT active, started_at FROM maintenance WHERE id = 1") as cur:
            row = await cur.fetchone()
            return dict(row) if row else {"active": 0, "started_at": None}


# ─── Disk Snapshot ────────────────────────────────────────────────────────────

async def get_disk_snapshot() -> float | None:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT used_gb FROM disk_snapshot WHERE id = 1") as cur:
            row = await cur.fetchone()
            return row[0] if row else None


async def set_disk_snapshot(used_gb: float) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO disk_snapshot (id, used_gb) VALUES (1, ?)
            ON CONFLICT(id) DO UPDATE SET used_gb = ?, snapped_at = datetime('now','localtime')
        """, (used_gb, used_gb))
        await db.commit()
