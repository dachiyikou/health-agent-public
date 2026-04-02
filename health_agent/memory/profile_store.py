from __future__ import annotations

from schemas.memory_schema import UserProfilePayload
from tools.db import DBClient


class ProfileStore:
    def __init__(self, db: DBClient):
        self.db = db

    def get(self, user_id: str) -> dict | None:
        return self.db.get_profile(user_id)

    def upsert(self, payload: UserProfilePayload) -> None:
        self.db.save_profile(payload)
