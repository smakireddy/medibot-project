"""
Question router — decides hybrid RAG vs SQL RAG.

Uses a two-stage approach:
  Stage 1: Fast keyword check (no LLM call, <1ms)
  Stage 2: LLM classification only if keywords are ambiguous

SQL RAG is triggered for questions asking for counts, aggregations, or
statistics over structured data. Everything else goes to hybrid RAG.

Role permission for SQL is enforced here before routing.
"""
import re
from typing import Literal

from langchain_core.messages import HumanMessage, SystemMessage

from core.access import SQL_ALLOWED_ROLES
from core.llm import get_llm

RouteDecision = Literal["rag", "sql", "sql_denied"]

# Strong signal keywords — if any match, route to SQL without LLM call
_SQL_KEYWORDS = re.compile(
    r"\b(how many|count|total|sum|average|avg|percentage|ratio|"
    r"most|least|top \d|highest|lowest|breakdown|distribution|"
    r"how much|statistics|stat|report|trend|compare|versus|vs\.?)\b",
    re.IGNORECASE,
)


def _keyword_route(question: str) -> Literal["sql", "rag", "unclear"]:
    if _SQL_KEYWORDS.search(question):
        return "sql"
    return "unclear"


def _llm_route(question: str) -> Literal["sql", "rag"]:
    """Fallback: ask the LLM to classify when keywords are ambiguous."""
    llm = get_llm()
    messages = [
        SystemMessage(content=(
            "You decide whether a question needs a SQL database query or "
            "a document search to answer.\n\n"
            "SQL: questions about counts, totals, statistics, trends, or "
            "specific records from a database (claims, tickets).\n"
            "RAG: questions about procedures, policies, guidelines, or "
            "medical knowledge from documents.\n\n"
            "Reply with exactly one word: SQL or RAG"
        )),
        HumanMessage(content=question),
    ]
    response = llm.invoke(messages).content.strip().upper()
    return "sql" if "SQL" in response else "rag"


def route_question(question: str, role: str) -> RouteDecision:
    """
    Return the routing decision for a question + role combination.

    sql_denied: question is analytical but role lacks SQL permission.
    sql:        analytical question, role permitted.
    rag:        knowledge/document question.
    """
    keyword_result = _keyword_route(question)

    if keyword_result == "unclear":
        decision = _llm_route(question)
    else:
        decision = keyword_result

    if decision == "sql" and role not in SQL_ALLOWED_ROLES:
        return "sql_denied"

    return decision
