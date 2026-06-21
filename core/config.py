from typing import Literal
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # ── LLM provider selection ────────────────────────────────────────────────
    llm_provider: Literal["groq", "anthropic", "openai", "huggingface"] = "groq"

    # Groq
    groq_api_key: str = ""
    groq_model: str = "llama-3.1-8b-instant"

    # Anthropic
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-haiku-4-5"

    # OpenAI
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"

    # Hugging Face Inference API
    huggingfacehub_api_token: str = ""
    hf_model: str = "mistralai/Mistral-7B-Instruct-v0.3"

    # ── Qdrant ────────────────────────────────────────────────────────────────
    qdrant_url: str = "http://localhost:6333"
    qdrant_api_key: str = ""
    qdrant_collection: str = "medibot"

    # ── Auth ──────────────────────────────────────────────────────────────────
    jwt_secret: str = "medibot-dev-secret-change-me"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 480

    # ── DB ────────────────────────────────────────────────────────────────────
    db_path: str = "data/db/mediassist.db"

    # ── Embedding / reranker (local, no API cost) ─────────────────────────────
    dense_model: str = "BAAI/bge-small-en-v1.5"
    reranker_model: str = "BAAI/bge-reranker-base"

    # ── Retrieval knobs ───────────────────────────────────────────────────────
    retrieval_top_k: int = 10   # candidates fetched from Qdrant
    rerank_top_n: int = 3       # final chunks passed to LLM


settings = Settings()
