from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from config import (
    MEMORY_IMPORTANCE_THRESHOLD,
    MEMORY_PROFILE_PATH,
    MEMORY_SUMMARY_PATH,
    SESSION_MEMORY_WINDOW,
    VECTOR_COLLECTION_MEMORY,
)
from memory.profile_store import ProfileStore
from memory.summarizer import SessionSummarizer
from schemas.memory_schema import SessionSummaryPayload, UserMemoryPayload, UserProfilePayload
from tools.db import DBClient
from tools.vector_store import VectorStoreClient


class MemoryManager:
    def __init__(self, db: DBClient, vector_store: VectorStoreClient):
        self.db = db
        self.vector_store = vector_store
        self.profile_store = ProfileStore(db)
        self.summarizer = SessionSummarizer()

    def read_session_context(self, session_id: str, limit: int = SESSION_MEMORY_WINDOW) -> list[dict[str, Any]]:
        return self.db.get_recent_messages(session_id, limit=limit)

    def read_profile(self, user_id: str) -> dict[str, Any]:
        profile = self.profile_store.get(user_id)
        if profile:
            return profile
        return {
            "user_id": user_id,
            "age_range": None,
            "gender": None,
            "chronic_diseases": [],
            "allergies": [],
            "long_term_medications": [],
            "timezone": None,
            "profile_summary": "",
        }

    def search_semantic_memory(self, user_id: str, query: str, top_k: int = 3) -> list[dict[str, Any]]:
        return self.vector_store.search_memory(user_id, query, top_k=top_k)

    def should_persist_memory(self, fact: dict[str, Any]) -> bool:
        return float(fact.get("importance", 0.0)) >= MEMORY_IMPORTANCE_THRESHOLD

    def persist_profile_fact(self, user_id: str, fact: dict[str, Any]) -> None:
        profile = self.read_profile(user_id)
        field = fact.get("field")
        value = fact.get("value")
        if not field or value in (None, ""):
            return
        if field in {"allergies", "chronic_diseases", "long_term_medications"}:
            existing = list(profile.get(field, []))
            if value not in existing:
                existing.append(value)
            profile[field] = existing
        else:
            profile[field] = value
        payload = UserProfilePayload(**profile)
        self.profile_store.upsert(payload)
        profile_path = MEMORY_PROFILE_PATH / f"{user_id}.json"
        profile_path.write_text(payload.model_dump_json(indent=2), encoding="utf-8")

    def persist_semantic_memory(self, user_id: str, memory_text: str, importance: float, source_message_id: int | None = None) -> None:
        payload = UserMemoryPayload(
            user_id=user_id,
            memory_type="semantic_fact",
            content=memory_text,
            summary=memory_text,
            importance=importance,
            source_message_id=source_message_id,
        )
        memory_id = self.db.save_memory(payload)
        self.vector_store.upsert_memory(
            user_id=user_id,
            content=memory_text,
            metadata={"memory_id": memory_id, "importance": importance},
        )

    def maybe_persist(self, user_id: str, session_id: str, parsed: dict[str, Any], source_message_id: int | None = None) -> list[dict[str, Any]]:
        stored_facts: list[dict[str, Any]] = []
        for fact in parsed.get("memory_facts", []):
            if not self.should_persist_memory(fact):
                continue
            self.persist_profile_fact(user_id, fact)
            self.persist_semantic_memory(
                user_id=user_id,
                memory_text=fact["content"],
                importance=float(fact.get("importance", MEMORY_IMPORTANCE_THRESHOLD)),
                source_message_id=source_message_id,
            )
            stored_facts.append(fact)
        if len(self.read_session_context(session_id, limit=SESSION_MEMORY_WINDOW)) >= 6:
            self.summarize_session(session_id, user_id)
        return stored_facts

    def summarize_session(self, session_id: str, user_id: str) -> SessionSummaryPayload | None:
        messages = self.read_session_context(session_id, limit=12)
        if not messages:
            return None
        summary = self.summarizer.summarize_messages(messages)
        payload = SessionSummaryPayload(session_id=session_id, user_id=user_id, summary=summary)
        summary_path = MEMORY_SUMMARY_PATH / f"{session_id}.md"
        summary_path.write_text(summary, encoding="utf-8")
        snapshot_path = MEMORY_SUMMARY_PATH.parent / "snapshots" / f"{session_id}.json"
        snapshot_path.write_text(
            json.dumps({"session_id": session_id, "user_id": user_id, "messages": messages}, ensure_ascii=True, indent=2),
            encoding="utf-8",
        )
        return payload
