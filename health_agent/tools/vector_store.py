from __future__ import annotations

import hashlib
import uuid
from typing import Any

import requests
from langchain_openai import OpenAIEmbeddings

from config import (
    DASHSCOPE_API_KEY,
    DASHSCOPE_BASE_URL,
    DASHSCOPE_EMBEDDING_MODEL,
    DEFAULT_EMBEDDING_MODEL,
    EMBEDDING_DIM,
    QDRANT_API_KEY,
    VECTOR_COLLECTION_DRUG,
    VECTOR_COLLECTION_FAQ,
    VECTOR_COLLECTION_MEMORY,
    VECTOR_COLLECTION_METRIC,
    VECTOR_COLLECTION_SYMPTOM,
    VECTOR_DB_URL,
)


class VectorStoreClient:
    def __init__(self, base_url: str = VECTOR_DB_URL, api_key: str = QDRANT_API_KEY):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.embeddings = OpenAIEmbeddings(
            api_key=DASHSCOPE_API_KEY,
            base_url=DASHSCOPE_BASE_URL,
            model=DASHSCOPE_EMBEDDING_MODEL or DEFAULT_EMBEDDING_MODEL,
            tiktoken_enabled=False,
            check_embedding_ctx_length=False,
        )

    def _build_headers(self, headers: dict[str, str] | None = None) -> dict[str, str]:
        merged_headers = dict(headers or {})
        if not self.api_key:
            raise RuntimeError("Qdrant API key is not configured. Set QDRANT_API_KEY in your environment.")
        merged_headers.setdefault("api-key", self.api_key)
        return merged_headers

    def _request(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        url = f"{self.base_url}{path}"
        headers = self._build_headers(kwargs.pop("headers", None))
        try:
            response = requests.request(method, url, timeout=20, headers=headers, **kwargs)
            response.raise_for_status()
        except requests.RequestException as exc:
            status_code = exc.response.status_code if getattr(exc, "response", None) is not None else "network"
            if status_code in (401, 403):
                raise RuntimeError(
                    f"Qdrant authentication failed: {method} {url} -> {status_code}. "
                    "Check QDRANT_API_KEY configuration."
                ) from exc
            raise RuntimeError(f"Vector store request failed: {method} {url} -> {status_code}") from exc
        if not response.text:
            return {}
        return response.json()

    def healthcheck(self) -> None:
        self._request("GET", "/collections")

    def collection_exists(self, collection: str) -> bool:
        try:
            self._request("GET", f"/collections/{collection}")
            return True
        except RuntimeError as exc:
            if str(exc).endswith("-> 404"):
                return False
            raise

    def _collection_dimension_matches(self, payload: dict[str, Any]) -> bool:
        size = (
            payload.get("result", {})
            .get("config", {})
            .get("params", {})
            .get("vectors", {})
            .get("size")
        )
        return size == EMBEDDING_DIM

    def ensure_collection(self, collection: str) -> None:
        if self.collection_exists(collection):
            payload = self._request("GET", f"/collections/{collection}")
            if not self._collection_dimension_matches(payload):
                current_size = (
                    payload.get("result", {})
                    .get("config", {})
                    .get("params", {})
                    .get("vectors", {})
                    .get("size")
                )
                raise RuntimeError(
                    f"Qdrant collection '{collection}' uses vector size {current_size}, "
                    f"but the current embedding model expects {EMBEDDING_DIM}. "
                    "Please recreate the collection or update EMBEDDING_DIM."
                )
            return
        body = {
            "vectors": {
                "size": EMBEDDING_DIM,
                "distance": "Cosine",
            }
        }
        self._request("PUT", f"/collections/{collection}", json=body)

    def ensure_collections(self) -> None:
        for collection in (
            VECTOR_COLLECTION_SYMPTOM,
            VECTOR_COLLECTION_DRUG,
            VECTOR_COLLECTION_METRIC,
            VECTOR_COLLECTION_FAQ,
            VECTOR_COLLECTION_MEMORY,
        ):
            self.ensure_collection(collection)

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        return self.embeddings.embed_documents(texts)

    def embed_query(self, text: str) -> list[float]:
        return self.embeddings.embed_query(text)

    def upsert_documents(self, collection: str, docs: list[dict[str, Any]]) -> None:
        points = []
        for doc in docs:
            point_id = doc.get("id") or str(uuid.uuid4())
            if isinstance(point_id, str) and not point_id.isdigit():
                point_id = uuid.uuid5(uuid.NAMESPACE_DNS, point_id).hex
            points.append(
                {
                    "id": point_id,
                    "vector": doc["vector"],
                    "payload": doc["payload"],
                }
            )
        self._request("PUT", f"/collections/{collection}/points?wait=true", json={"points": points})

    def search(self, collection: str, query: str, top_k: int, filters: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        vector = self.embed_query(query)
        payload: dict[str, Any] = {
            "vector": vector,
            "limit": top_k,
            "with_payload": True,
            "with_vector": False,
        }
        if filters:
            payload["filter"] = filters
        data = self._request("POST", f"/collections/{collection}/points/search", json=payload)
        return data.get("result", [])

    def upsert_memory(self, user_id: str, content: str, metadata: dict[str, Any]) -> None:
        vector = self.embed_query(content)
        memory_id = metadata.get("memory_id") or hashlib.md5(content.encode("utf-8")).hexdigest()
        payload = {"user_id": user_id, "content": content, **metadata}
        self.upsert_documents(
            VECTOR_COLLECTION_MEMORY,
            [{"id": str(memory_id), "vector": vector, "payload": payload}],
        )

    def search_memory(self, user_id: str, query: str, top_k: int = 3) -> list[dict[str, Any]]:
        filters = {"must": [{"key": "user_id", "match": {"value": user_id}}]}
        return self.search(VECTOR_COLLECTION_MEMORY, query, top_k=top_k, filters=filters)
