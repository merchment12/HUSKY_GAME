"""Хранилище прогресса: по одному сейву на игрока в SQLite."""
import json
import time
from pathlib import Path

import aiosqlite

SCHEMA = """
CREATE TABLE IF NOT EXISTS players (
    user_id    INTEGER PRIMARY KEY,
    username   TEXT,
    name       TEXT,
    save       TEXT NOT NULL,
    life       REAL NOT NULL DEFAULT 0,
    best_stage INTEGER NOT NULL DEFAULT 0,
    max_ever   INTEGER NOT NULL DEFAULT 1,
    shards     INTEGER NOT NULL DEFAULT 0,
    saves      INTEGER NOT NULL DEFAULT 0,
    created_at INTEGER NOT NULL,
    updated_at INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS players_best ON players(best_stage DESC, life DESC);
"""


class Storage:
    def __init__(self, path: Path):
        self.path = path
        self._db: aiosqlite.Connection | None = None

    async def open(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._db = await aiosqlite.connect(self.path)
        self._db.row_factory = aiosqlite.Row
        await self._db.execute("PRAGMA journal_mode=WAL")
        await self._db.executescript(SCHEMA)
        await self._db.commit()

    async def close(self) -> None:
        if self._db is not None:
            await self._db.close()
            self._db = None

    @property
    def db(self) -> aiosqlite.Connection:
        if self._db is None:
            raise RuntimeError("Storage.open() не вызван")
        return self._db

    async def load(self, user_id: int) -> dict | None:
        async with self.db.execute(
            "SELECT save, life, best_stage, max_ever, shards, updated_at FROM players WHERE user_id=?",
            (user_id,),
        ) as cur:
            row = await cur.fetchone()
        if row is None:
            return None
        try:
            save = json.loads(row["save"])
        except json.JSONDecodeError:
            return None
        return {
            "save": save,
            "life": row["life"],
            "best_stage": row["best_stage"],
            "updated_at": row["updated_at"],
        }

    async def store(self, user_id: int, user: dict, save: dict) -> tuple[str, dict | None]:
        """Пишет сейв, если он не младше сохранённого.

        Возвращает ('ok', None) либо ('stale', серверный_сейв) — клиент тогда
        откатывается на серверную версию.
        """
        stats = save.get("stats") or {}
        life = float(stats.get("life") or 0)
        best_stage = int(save.get("bestStage") or 0)
        current = await self.load(user_id)
        if current is not None and (life < current["life"] - 1 or best_stage < current["best_stage"]):
            return "stale", current

        now = int(time.time())
        name = " ".join(x for x in (user.get("first_name"), user.get("last_name")) if x) or None
        await self.db.execute(
            """
            INSERT INTO players (user_id, username, name, save, life, best_stage, max_ever, shards,
                                 saves, created_at, updated_at)
            VALUES (?,?,?,?,?,?,?,?,1,?,?)
            ON CONFLICT(user_id) DO UPDATE SET
                username=excluded.username, name=excluded.name, save=excluded.save,
                life=excluded.life, best_stage=excluded.best_stage, max_ever=excluded.max_ever,
                shards=excluded.shards, saves=players.saves+1, updated_at=excluded.updated_at
            """,
            (
                user_id,
                user.get("username"),
                name,
                json.dumps(save, ensure_ascii=False, separators=(",", ":")),
                life,
                best_stage,
                int(save.get("maxEver") or 1),
                int(save.get("shards") or 0),
                now,
                now,
            ),
        )
        await self.db.commit()
        return "ok", None

    async def top(self, limit: int = 20) -> list[dict]:
        async with self.db.execute(
            """
            SELECT user_id, username, name, best_stage, max_ever, life
            FROM players ORDER BY best_stage DESC, life DESC LIMIT ?
            """,
            (limit,),
        ) as cur:
            rows = await cur.fetchall()
        return [dict(r) for r in rows]

    async def rank(self, user_id: int) -> int | None:
        async with self.db.execute(
            """
            SELECT COUNT(*) + 1 FROM players p, (SELECT best_stage, life FROM players WHERE user_id=?) me
            WHERE p.best_stage > me.best_stage
               OR (p.best_stage = me.best_stage AND p.life > me.life)
            """,
            (user_id,),
        ) as cur:
            row = await cur.fetchone()
        return row[0] if row else None
