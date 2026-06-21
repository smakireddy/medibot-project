"""
Cross-encoder reranking.

Scores each (query, passage) pair jointly — unlike bi-encoders which score
query and passage independently. This catches relevance signals that
embedding similarity misses (e.g. negation, specificity, term overlap).

Pipeline: top-10 from Qdrant → reranker → top-3 passed to LLM.
Only the top-3 reach the LLM prompt; the rest are discarded.
"""
from functools import lru_cache

from sentence_transformers import CrossEncoder
from langchain_core.documents import Document

from core.config import settings


@lru_cache(maxsize=1)
def _get_reranker() -> CrossEncoder:
    return CrossEncoder(settings.reranker_model)


def rerank(question: str, docs: list[Document]) -> list[Document]:
    """
    Score each doc against the query jointly, return top-n sorted by score.
    Logs scores so you can see reranking effect during development.
    """
    if not docs:
        return []

    reranker = _get_reranker()
    pairs = [[question, doc.page_content] for doc in docs]
    scores: list[float] = reranker.predict(pairs).tolist()

    scored = sorted(zip(scores, docs), key=lambda x: x[0], reverse=True)

    # Log scores — useful to see that rank 4-5 often beats rank 1
    print("[rerank] scores:", [f"{s:.3f}" for s, _ in scored])

    top_docs = []
    for score, doc in scored[: settings.rerank_top_n]:
        doc.metadata["rerank_score"] = round(score, 4)
        top_docs.append(doc)

    return top_docs
