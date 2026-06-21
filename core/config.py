import warnings
from typing import Literal

from pydantic import model_validator
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

    @model_validator(mode="after")
    def _warn_insecure_defaults(self) -> "Settings":
        _KNOWN_WEAK_SECRET = "medibot-dev-secret-change-me"
        if self.jwt_secret == _KNOWN_WEAK_SECRET or len(self.jwt_secret) < 32:
            warnings.warn(
                "JWT_SECRET is set to an insecure default. "
                "Set a strong random secret (≥32 chars) in your .env before deploying.",
                stacklevel=2,
            )
        return self


settings = Settings()
