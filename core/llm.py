"""
Generic LLM factory.

Switch providers by setting LLM_PROVIDER in .env — no code changes needed.
All returned objects implement LangChain's BaseChatModel interface:
  llm.invoke(messages)  →  AIMessage
  llm.stream(messages)  →  AsyncIterator[AIMessageChunk]

Supported providers:
  groq        — fast inference, free tier, Llama / Mixtral / Gemma
  anthropic   — Claude family
  openai      — GPT-4o / GPT-4o-mini
  huggingface — open models via HF Inference API
"""
from functools import lru_cache

from langchain_core.language_models.chat_models import BaseChatModel
from core.config import settings


@lru_cache(maxsize=1)
def get_llm() -> BaseChatModel:
    provider = settings.llm_provider

    if provider == "groq":
        from langchain_groq import ChatGroq
        return ChatGroq(
            api_key=settings.groq_api_key,
            model=settings.groq_model,
            temperature=0.1,
        )

    if provider == "anthropic":
        from langchain_anthropic import ChatAnthropic
        return ChatAnthropic(
            api_key=settings.anthropic_api_key,
            model=settings.anthropic_model,
            temperature=0.1,
        )

    if provider == "openai":
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(
            api_key=settings.openai_api_key,
            model=settings.openai_model,
            temperature=0.1,
        )

    if provider == "huggingface":
        from langchain_huggingface import ChatHuggingFace, HuggingFaceEndpoint
        endpoint = HuggingFaceEndpoint(
            repo_id=settings.hf_model,
            huggingfacehub_api_token=settings.huggingfacehub_api_token,
            temperature=0.1,
            max_new_tokens=1024,
        )
        return ChatHuggingFace(llm=endpoint)

    raise ValueError(
        f"Unknown LLM_PROVIDER '{provider}'. "
        "Valid options: groq, anthropic, openai, huggingface"
    )
