"""
LangGraph orchestration for MediBot.

Graph structure:
  START → route → (sql | sql_denied | rag)
                       │         │       │
                    sql_node  deny_node  retrieve_node
                       │                     │
                      END               rerank_node
                                             │
                                        generate_node
                                             │
                                            END

State flows through all nodes; each node reads what it needs
and writes its output back to state.
"""
from typing import Literal, TypedDict

from langchain_core.documents import Document
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import END, START, StateGraph

from core.access import collections_for_role
from core.llm import get_llm
from core.schemas import ChatResponse, SourceCitation
from rag.rerank import rerank
from rag.retrieval import hybrid_retrieve
from rag.router import route_question
from rag.sql_rag import sql_rag_chain


# ── State ─────────────────────────────────────────────────────────────────────

class MediBotState(TypedDict):
    question: str
    role: str
    route: str                      # "rag" | "sql" | "sql_denied"
    documents: list[Document]       # retrieved + reranked docs
    answer: str
    sources: list[dict]
    retrieval_type: str             # "hybrid_rag" | "sql_rag"


# ── Node functions ─────────────────────────────────────────────────────────────

def node_route(state: MediBotState) -> MediBotState:
    decision = route_question(state["question"], state["role"])
    return {**state, "route": decision}


def node_sql(state: MediBotState) -> MediBotState:
    answer = sql_rag_chain(state["question"])
    return {
        **state,
        "answer": answer,
        "sources": [],
        "retrieval_type": "sql_rag",
    }


def node_sql_denied(state: MediBotState) -> MediBotState:
    role = state["role"]
    permitted = collections_for_role(role)
    answer = (
        f"As a {role.replace('_', ' ')}, you don't have access to analytical "
        f"database queries. I can answer questions from the "
        f"{', '.join(permitted)} document collections."
    )
    return {
        **state,
        "answer": answer,
        "sources": [],
        "retrieval_type": "hybrid_rag",
    }


def node_retrieve(state: MediBotState) -> MediBotState:
    docs = hybrid_retrieve(state["question"], state["role"])
    return {**state, "documents": docs}


def node_rerank(state: MediBotState) -> MediBotState:
    docs = rerank(state["question"], state["documents"])
    return {**state, "documents": docs}


_RERANK_RELEVANCE_THRESHOLD = 0.05  # below this → treat as out-of-scope


def node_generate(state: MediBotState) -> MediBotState:
    docs = state["documents"]
    role = state["role"]
    question = state["question"]
    permitted = collections_for_role(role)

    if not docs:
        answer = (
            f"I couldn't find relevant information in the "
            f"{', '.join(permitted)} collections to answer your question."
        )
        return {**state, "answer": answer, "sources": [], "retrieval_type": "hybrid_rag"}

    # If every reranked doc scores below threshold, the question is likely about
    # content outside the user's permitted collections — give an RBAC-aware message
    # instead of passing irrelevant chunks to the LLM.
    top_score = max(
        (doc.metadata.get("rerank_score", 0.0) for doc in docs),
        default=0.0,
    )
    if top_score < _RERANK_RELEVANCE_THRESHOLD:
        answer = (
            f"As a {role.replace('_', ' ')}, I can only answer questions from the "
            f"{', '.join(permitted)} collections. "
            f"The information you're asking about doesn't appear to be available in those collections. "
            f"It may belong to a collection your role doesn't have access to."
        )
        return {**state, "answer": answer, "sources": [], "retrieval_type": "hybrid_rag"}

    # Build context block for the LLM
    context_parts = []
    for i, doc in enumerate(docs, 1):
        m = doc.metadata
        context_parts.append(
            f"[{i}] Source: {m.get('source_document', 'unknown')} "
            f"| Section: {m.get('section_title', 'N/A')}\n"
            f"{doc.page_content}"
        )
    context = "\n\n".join(context_parts)

    llm = get_llm()
    messages = [
        SystemMessage(content=(
            f"You are MediBot, an AI assistant for MediAssist Health Network. "
            f"The current user is a {role.replace('_', ' ')} with access to these document collections only: {', '.join(permitted)}. "
            f"Answer the question using ONLY the provided context. "
            f"If the context does not contain the answer, respond with exactly this: "
            f"\"As a {role.replace('_', ' ')}, your accessible collections are: {', '.join(permitted)}. "
            f"The information you are asking about is not available in these collections — "
            f"it may belong to a collection your role does not have access to.\" "
            f"Cite the source number [1], [2] etc. when using information from the context."
        )),
        HumanMessage(content=f"Context:\n{context}\n\nQuestion: {question}"),
    ]
    answer = llm.invoke(messages).content

    sources = [
        {
            "source_document": doc.metadata.get("source_document", ""),
            "section_title":   doc.metadata.get("section_title", ""),
            "collection":      doc.metadata.get("collection", ""),
        }
        for doc in docs
    ]

    return {
        **state,
        "answer": answer,
        "sources": sources,
        "retrieval_type": "hybrid_rag",
    }


# ── Conditional edge ──────────────────────────────────────────────────────────

def edge_after_route(state: MediBotState) -> Literal["node_sql", "node_sql_denied", "node_retrieve"]:
    route = state["route"]
    if route == "sql":
        return "node_sql"
    if route == "sql_denied":
        return "node_sql_denied"
    return "node_retrieve"


# ── Graph builder ─────────────────────────────────────────────────────────────

def build_graph() -> StateGraph:
    graph = StateGraph(MediBotState)

    graph.add_node("node_route",      node_route)
    graph.add_node("node_sql",        node_sql)
    graph.add_node("node_sql_denied", node_sql_denied)
    graph.add_node("node_retrieve",   node_retrieve)
    graph.add_node("node_rerank",     node_rerank)
    graph.add_node("node_generate",   node_generate)

    graph.add_edge(START, "node_route")
    graph.add_conditional_edges("node_route", edge_after_route)
    graph.add_edge("node_sql",        END)
    graph.add_edge("node_sql_denied", END)
    graph.add_edge("node_retrieve",   "node_rerank")
    graph.add_edge("node_rerank",     "node_generate")
    graph.add_edge("node_generate",   END)

    return graph.compile()


# Module-level compiled graph — imported by the API layer
medibot_graph = build_graph()


def run_query(question: str, role: str) -> ChatResponse:
    """
    Single entry point for the API layer.
    Returns a fully populated ChatResponse.
    """
    initial_state: MediBotState = {
        "question": question,
        "role": role,
        "route": "",
        "documents": [],
        "answer": "",
        "sources": [],
        "retrieval_type": "hybrid_rag",
    }

    final_state: MediBotState = medibot_graph.invoke(initial_state)

    return ChatResponse(
        answer=final_state["answer"],
        sources=[SourceCitation(**s) for s in final_state["sources"]],
        retrieval_type=final_state["retrieval_type"],  # type: ignore[arg-type]
        role=role,
    )
