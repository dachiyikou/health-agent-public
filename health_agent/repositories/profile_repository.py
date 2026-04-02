from __future__ import annotations

from health_agent.schemas.memory_schema import UserProfilePayload
from health_agent.tools.db import DBClient


class ProfileRepository:
    def __init__(self, db: DBClient):
        self.db = db

    def get_profile(self, user_id: str) -> dict | None:
        return self.db.get_profile(user_id)

    def save_profile(self, payload: UserProfilePayload) -> None:
        self.db.save_profile(payload)
