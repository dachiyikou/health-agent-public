from __future__ import annotations

from health_agent.config import (
    VECTOR_COLLECTION_DRUG,
    VECTOR_COLLECTION_FAQ,
    VECTOR_COLLECTION_MEMORY,
    VECTOR_COLLECTION_METRIC,
    VECTOR_COLLECTION_SYMPTOM,
)
from health_agent.tools.vector_store import VectorStoreClient


COLLECTIONS = [
    VECTOR_COLLECTION_SYMPTOM,
    VECTOR_COLLECTION_DRUG,
    VECTOR_COLLECTION_METRIC,
    VECTOR_COLLECTION_FAQ,
    VECTOR_COLLECTION_MEMORY,
]


def main() -> None:
    client = VectorStoreClient()
    client.healthcheck()
    for collection in COLLECTIONS:
        if client.collection_exists(collection):
            client._request("DELETE", f"/collections/{collection}")
            print(f"deleted: {collection}")
    client.ensure_collections()
    print("recreated collections with the current embedding dimension.")


if __name__ == "__main__":
    main()
