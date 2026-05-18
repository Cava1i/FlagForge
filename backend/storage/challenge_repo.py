"""SQLite repository for challenge index records."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from backend.storage.db import connect


class ChallengeRepo:
    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)

    def upsert(self, challenge: dict[str, Any]) -> dict[str, Any]:
        with connect(self.db_path) as connection:
            existing = connection.execute(
                "SELECT id FROM challenges WHERE path = ?", (challenge["path"],)
            ).fetchone()
            if existing:
                connection.execute(
                    """
                    UPDATE challenges
                    SET name = ?, slug = ?, category = ?, value = ?,
                        connection_info = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                    """,
                    (
                        challenge["name"],
                        challenge["slug"],
                        challenge.get("category"),
                        challenge.get("value"),
                        challenge.get("connection_info"),
                        existing["id"],
                    ),
                )
                challenge_id = existing["id"]
            else:
                cursor = connection.execute(
                    """
                    INSERT INTO challenges
                        (name, slug, path, category, value, connection_info)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        challenge["name"],
                        challenge["slug"],
                        challenge["path"],
                        challenge.get("category"),
                        challenge.get("value"),
                        challenge.get("connection_info"),
                    ),
                )
                challenge_id = cursor.lastrowid
        result = self.get(challenge_id)
        if result is None:
            raise RuntimeError("challenge upsert failed")
        return result

    def list(self) -> list[dict[str, Any]]:
        with connect(self.db_path) as connection:
            rows = connection.execute(
                """
                SELECT id, name, slug, path, category, value, connection_info,
                       created_at, updated_at
                FROM challenges
                ORDER BY id ASC
                """
            ).fetchall()
        return [dict(row) for row in rows]

    def get(self, challenge_id: int) -> dict[str, Any] | None:
        with connect(self.db_path) as connection:
            row = connection.execute(
                """
                SELECT id, name, slug, path, category, value, connection_info,
                       created_at, updated_at
                FROM challenges
                WHERE id = ?
                """,
                (challenge_id,),
            ).fetchone()
        return dict(row) if row else None

    def update_summary(self, challenge_id: int, fields: dict[str, Any]) -> dict[str, Any] | None:
        allowed = {"name", "slug", "category", "value", "connection_info"}
        updates = {key: value for key, value in fields.items() if key in allowed}
        if not updates:
            return self.get(challenge_id)

        assignments = ", ".join(f"{key} = ?" for key in updates)
        values = list(updates.values())
        values.append(challenge_id)
        with connect(self.db_path) as connection:
            connection.execute(
                f"""
                UPDATE challenges
                SET {assignments}, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                values,
            )
        return self.get(challenge_id)

    def delete(self, challenge_id: int) -> bool:
        with connect(self.db_path) as connection:
            cursor = connection.execute("DELETE FROM challenges WHERE id = ?", (challenge_id,))
            return cursor.rowcount > 0
