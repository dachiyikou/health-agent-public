from __future__ import annotations

import os
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR.parent
DATA_DIR = PROJECT_ROOT / "data"
KNOWLEDGE_DIR = DATA_DIR / "knowledge"
MEMORY_DIR = DATA_DIR / "memory"
UPLOAD_DIR = DATA_DIR / "uploads"
LOG_DIR = DATA_DIR / "logs"
CACHE_DIR = DATA_DIR / "cache"

PROMPTS_DIR = BASE_DIR / "prompts"


_DEFAULT_DASHSCOPE_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"


def _load_local_env_file() -> None:
    """Load PROJECT_ROOT/.env.local once, without overriding existing env vars."""
    env_file = PROJECT_ROOT / ".env.local"
    if not env_file.exists():
        return

    for raw_line in env_file.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip("\"").strip("'")
        if key:
            os.environ.setdefault(key, value)


_load_local_env_file()


APP_ENV = os.getenv("APP_ENV", "development")
DASHSCOPE_API_KEY = os.getenv("DASHSCOPE_API_KEY", "")
DASHSCOPE_BASE_URL = os.getenv("DASHSCOPE_BASE_URL", _DEFAULT_DASHSCOPE_BASE_URL)
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY", "")

VECTOR_DB_PROVIDER = os.getenv("VECTOR_DB_PROVIDER", "qdrant")
VECTOR_DB_URL = os.getenv("VECTOR_DB_URL", "http://localhost:6333")
VECTOR_DB_GRPC_URL = os.getenv("VECTOR_DB_GRPC_URL", "http://localhost:6334")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY", "")
LANGFUSE_HOST = os.getenv("LANGFUSE_HOST", "http://localhost:3000")
LANGFUSE_PUBLIC_KEY = os.getenv("LANGFUSE_PUBLIC_KEY", "")
LANGFUSE_SECRET_KEY = os.getenv("LANGFUSE_SECRET_KEY", "")
PLAYWRIGHT_MCP_URL = os.getenv("PLAYWRIGHT_MCP_URL", "http://localhost:8931")
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{DATA_DIR / 'app.db'}")

DEFAULT_CHAT_MODEL = os.getenv("DEFAULT_CHAT_MODEL", "qwen-plus")
DEFAULT_REASON_MODEL = os.getenv("DEFAULT_REASON_MODEL", "qwen-plus")
DEFAULT_EMBEDDING_MODEL = os.getenv("DEFAULT_EMBEDDING_MODEL", "text-embedding-v4")
MEMORY_SUMMARY_MODEL = os.getenv("MEMORY_SUMMARY_MODEL", "qwen-plus")
DASHSCOPE_CHAT_MODEL = os.getenv("DASHSCOPE_CHAT_MODEL", DEFAULT_CHAT_MODEL)
DASHSCOPE_REASON_MODEL = os.getenv("DASHSCOPE_REASON_MODEL", DEFAULT_REASON_MODEL)
DASHSCOPE_EMBEDDING_MODEL = os.getenv("DASHSCOPE_EMBEDDING_MODEL", DEFAULT_EMBEDDING_MODEL)
DEFAULT_TIMEZONE = os.getenv("DEFAULT_TIMEZONE", "Asia/Shanghai")

RAG_TOP_K = int(os.getenv("RAG_TOP_K", "5"))
RAG_SCORE_THRESHOLD = float(os.getenv("RAG_SCORE_THRESHOLD", "0.72"))
RAG_CHUNK_SIZE = int(os.getenv("RAG_CHUNK_SIZE", "700"))
RAG_CHUNK_OVERLAP = int(os.getenv("RAG_CHUNK_OVERLAP", "100"))
SESSION_MEMORY_WINDOW = int(os.getenv("SESSION_MEMORY_WINDOW", "8"))
MAX_FOLLOWUP_QUESTIONS = int(os.getenv("MAX_FOLLOWUP_QUESTIONS", "3"))
MEMORY_IMPORTANCE_THRESHOLD = float(os.getenv("MEMORY_IMPORTANCE_THRESHOLD", "0.8"))

VECTOR_COLLECTION_SYMPTOM = os.getenv("VECTOR_COLLECTION_SYMPTOM", "symptom_knowledge")
VECTOR_COLLECTION_DRUG = os.getenv("VECTOR_COLLECTION_DRUG", "drug_knowledge")
VECTOR_COLLECTION_METRIC = os.getenv("VECTOR_COLLECTION_METRIC", "metric_knowledge")
VECTOR_COLLECTION_FAQ = os.getenv("VECTOR_COLLECTION_FAQ", "faq_knowledge")
VECTOR_COLLECTION_MEMORY = os.getenv("VECTOR_COLLECTION_MEMORY", "user_memory")
EMBEDDING_DIM = int(os.getenv("EMBEDDING_DIM", "1024"))

MEMORY_PROFILE_PATH = MEMORY_DIR / "profiles"
MEMORY_SUMMARY_PATH = MEMORY_DIR / "summaries"
MEMORY_SNAPSHOT_PATH = MEMORY_DIR / "snapshots"
LOG_FILE_PATH = LOG_DIR / "app.log"


def ensure_runtime_dirs() -> None:
    for path in (
        DATA_DIR,
        KNOWLEDGE_DIR / "raw",
        KNOWLEDGE_DIR / "cleaned",
        KNOWLEDGE_DIR / "chunks",
        KNOWLEDGE_DIR / "manifests",
        KNOWLEDGE_DIR / "exports",
        MEMORY_PROFILE_PATH,
        MEMORY_SUMMARY_PATH,
        MEMORY_SNAPSHOT_PATH,
        MEMORY_DIR / "exports",
        UPLOAD_DIR,
        LOG_DIR,
        CACHE_DIR,
        PROMPTS_DIR,
    ):
        path.mkdir(parents=True, exist_ok=True)


def sqlite_path_from_url(database_url: str = DATABASE_URL) -> Path:
    if not database_url.startswith("sqlite:///"):
        raise ValueError(f"Unsupported database url: {database_url}")
    return Path(database_url.replace("sqlite:///", "/", 1))


def validate_required_config() -> None:
    missing = []
    if not DASHSCOPE_API_KEY:
        missing.append("DASHSCOPE_API_KEY")
    if not VECTOR_DB_URL:
        missing.append("VECTOR_DB_URL")
    if missing:
        joined = ", ".join(missing)
        raise RuntimeError(f"Missing required configuration: {joined}")


ensure_runtime_dirs()
