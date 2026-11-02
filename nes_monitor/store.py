from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


@dataclass(frozen=True)
class Seen:
    thread_id: int
    title: str
    url: str
    prefix: str
    author: str
    posted_at: str
    snippet: str
    reason: str
    matched: bool
    notified: bool


class Store:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(path)
        self._db.row_factory = sqlite3.Row
        self._db.execute(
            """
            CREATE TABLE IF NOT EXISTS threads (
                id INTEGER PRIMARY KEY,
                title TEXT NOT NULL,
                url TEXT NOT NULL,
                prefix TEXT,
                author TEXT,
                posted_at TEXT,
                snippet TEXT,
                reason TEXT,
                matched INTEGER NOT NULL,
                notified INTEGER NOT NULL,
                first_seen TEXT NOT NULL
            )
            """
        )
        self._db.commit()

    def close(self) -> None:
        self._db.close()

    def known_ids(self) -> set[int]:
        rows = self._db.execute("SELECT id FROM threads").fetchall()
        return {row["id"] for row in rows}

    def pending(self) -> list[Seen]:
        rows = self._db.execute(
            "SELECT * FROM threads WHERE matched = 1 AND notified = 0 ORDER BY id"
        ).fetchall()
        return [_seen(row) for row in rows]

    def save(self, item: Seen) -> None:
        self._db.execute(
            """
            INSERT INTO threads (
                id, title, url, prefix, author, posted_at, snippet, reason,
                matched, notified, first_seen
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                title = excluded.title,
                url = excluded.url,
                prefix = excluded.prefix,
                author = excluded.author,
                posted_at = excluded.posted_at,
                snippet = excluded.snippet,
                reason = excluded.reason,
                matched = excluded.matched,
                notified = excluded.notified
            """,
            (
                item.thread_id,
                item.title,
                item.url,
                item.prefix,
                item.author,
                item.posted_at,
                item.snippet,
                item.reason,
                int(item.matched),
                int(item.notified),
                _now(),
            ),
        )
        self._db.commit()

    def mark_notified(self, thread_id: int) -> None:
        self._db.execute("UPDATE threads SET notified = 1 WHERE id = ?", (thread_id,))
        self._db.commit()


def _seen(row: sqlite3.Row) -> Seen:
    return Seen(
        thread_id=row["id"],
        title=row["title"],
        url=row["url"],
        prefix=row["prefix"] or "",
        author=row["author"] or "",
        posted_at=row["posted_at"] or "",
        snippet=row["snippet"] or "",
        reason=row["reason"] or "",
        matched=bool(row["matched"]),
        notified=bool(row["notified"]),
    )


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
