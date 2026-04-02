from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import pandas as pd

from health_agent.config import (
    KNOWLEDGE_DIR,
    RAG_CHUNK_OVERLAP,
    RAG_CHUNK_SIZE,
    RAG_SCORE_THRESHOLD,
    RAG_TOP_K,
    VECTOR_COLLECTION_DRUG,
    VECTOR_COLLECTION_FAQ,
    VECTOR_COLLECTION_METRIC,
    VECTOR_COLLECTION_SYMPTOM,
)
from health_agent.tools.vector_store import VectorStoreClient

try:
    from pypdf import PdfReader
except Exception:  # pragma: no cover - optional dependency in current environment
    PdfReader = None


class RAGService:
    DOMAIN_TO_COLLECTION = {
        "symptom": VECTOR_COLLECTION_SYMPTOM,
        "drug": VECTOR_COLLECTION_DRUG,
        "metric": VECTOR_COLLECTION_METRIC,
        "faq": VECTOR_COLLECTION_FAQ,
    }

    def __init__(self, vector_store: VectorStoreClient):
        self.vector_store = vector_store

    def ingest_documents(self, source_dir: str | Path, domain: str) -> dict[str, Any]:
        collection = self.DOMAIN_TO_COLLECTION[domain]
        source_path = Path(source_dir)
        if not source_path.exists():
            raise FileNotFoundError(f"Knowledge directory not found: {source_path}")
        ingested = 0
        chunks_written = 0
        for path in sorted(source_path.iterdir()):
            if not path.is_file():
                continue
            text = self.clean_document(path)
            if not text.strip():
                continue
            cleaned_path = KNOWLEDGE_DIR / "cleaned" / f"{path.stem}.txt"
            cleaned_path.write_text(text, encoding="utf-8")
            chunks = self.chunk_document(text, chunk_size=RAG_CHUNK_SIZE, overlap=RAG_CHUNK_OVERLAP)
            chunk_docs = []
            vectors = self.vector_store.embed_texts(chunks)
            for idx, (chunk, vector) in enumerate(zip(chunks, vectors, strict=False)):
                chunk_id = f"{path.stem}-{idx}"
                chunk_path = KNOWLEDGE_DIR / "chunks" / f"{chunk_id}.json"
                payload = {
                    "chunk_id": chunk_id,
                    "source": path.name,
                    "domain": domain,
                    "text": chunk,
                    "path": str(path),
                }
                chunk_path.write_text(json.dumps(payload, ensure_ascii=True, indent=2), encoding="utf-8")
                chunk_docs.append({"id": chunk_id, "vector": vector, "payload": payload})
            if chunk_docs:
                self.vector_store.upsert_documents(collection, chunk_docs)
                manifest_path = KNOWLEDGE_DIR / "manifests" / f"{path.stem}.json"
                manifest_path.write_text(
                    json.dumps(
                        {
                            "source": str(path),
                            "domain": domain,
                            "collection": collection,
                            "chunks": [doc["payload"]["chunk_id"] for doc in chunk_docs],
                        },
                        ensure_ascii=True,
                        indent=2,
                    ),
                    encoding="utf-8",
                )
                ingested += 1
                chunks_written += len(chunk_docs)
        return {"ingested_documents": ingested, "chunks_written": chunks_written, "collection": collection}

    def clean_document(self, path: str | Path) -> str:
        path = Path(path)
        suffix = path.suffix.lower()
        if suffix in {".txt", ".md"}:
            text = path.read_text(encoding="utf-8")
        elif suffix == ".json":
            data = json.loads(path.read_text(encoding="utf-8"))
            text = json.dumps(data, ensure_ascii=False, indent=2)
        elif suffix == ".csv":
            text = pd.read_csv(path).to_csv(index=False)
        elif suffix in {".xlsx", ".xls"}:
            text = pd.read_excel(path).to_csv(index=False)
        elif suffix == ".pdf":
            if PdfReader is None:
                raise RuntimeError("pypdf is required to ingest PDF files")
            reader = PdfReader(str(path))
            text = "\n".join(page.extract_text() or "" for page in reader.pages)
        else:
            raise ValueError(f"Unsupported document type: {suffix}")
        text = re.sub(r"\s+\n", "\n", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()

    def chunk_document(self, text: str, chunk_size: int, overlap: int) -> list[str]:
        chunks: list[str] = []
        start = 0
        while start < len(text):
            end = start + chunk_size
            chunks.append(text[start:end])
            if end >= len(text):
                break
            start = max(end - overlap, 0)
        return chunks

    def retrieve(self, query: str, domain: str, top_k: int = RAG_TOP_K) -> dict[str, Any]:
        collection = self.DOMAIN_TO_COLLECTION[domain]
        hits = self.vector_store.search(collection, query, top_k=top_k)
        filtered = [hit for hit in hits if float(hit.get("score", 0.0)) >= RAG_SCORE_THRESHOLD]
        citations = [
            {
                "source": hit["payload"].get("source", "unknown"),
                "collection": collection,
                "score": float(hit.get("score", 0.0)),
                "chunk_id": hit["payload"].get("chunk_id"),
            }
            for hit in filtered
        ]
        return {
            "context": self.build_context(filtered),
            "citations": citations,
            "hits": filtered,
        }

    def build_context(self, hits: list[dict[str, Any]]) -> str:
        blocks = []
        for hit in hits:
            payload = hit.get("payload", {})
            blocks.append(f"[{payload.get('source', 'unknown')}] {payload.get('text', '')}")
        return "\n\n".join(blocks)
