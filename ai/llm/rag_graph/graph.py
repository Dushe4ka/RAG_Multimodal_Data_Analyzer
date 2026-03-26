from __future__ import annotations

from functools import partial
from typing import Optional

from langgraph.graph import END, START, StateGraph
from langgraph.prebuilt import ToolNode, tools_condition
from langchain_openai import ChatOpenAI

from ai.vector.vector_store import VectorStore
from config import settings

from .nodes import decide_after_grading, generate_answer, generate_query_or_respond, grade_documents, rewrite_question
from .state import RAGState
from .tools import build_retriever_tool


def _build_default_llm() -> ChatOpenAI:
    return ChatOpenAI(
        model=settings.OPENAI_MODEL,
        api_key=settings.OPENAI_API_KEY,
        temperature=0.2,
    )


def build_rag_graph(
    vector_store: VectorStore,
    *,
    workspace_id: Optional[str] = None,
    max_retries: int = 2,
    llm: Optional[ChatOpenAI] = None,
):
    """
    Собирает agentic-RAG граф:
    generate_query_or_respond -> retrieve -> grade -> (rewrite|generate) -> END
    """
    base_llm = llm or _build_default_llm()
    retriever_tool = build_retriever_tool(vector_store=vector_store, workspace_id=workspace_id)
    llm_with_tools = base_llm.bind_tools([retriever_tool])

    workflow = StateGraph(RAGState)
    workflow.add_node(
        "generate_query_or_respond",
        partial(generate_query_or_respond, llm_with_tools=llm_with_tools),
    )
    workflow.add_node("retrieve", ToolNode([retriever_tool]))
    workflow.add_node(
        "grade_documents",
        partial(grade_documents, grader_llm=base_llm, max_retries=max_retries),
    )
    workflow.add_node("rewrite_question", partial(rewrite_question, llm=base_llm))
    workflow.add_node("generate_answer", partial(generate_answer, llm=base_llm))

    workflow.add_edge(START, "generate_query_or_respond")
    workflow.add_conditional_edges(
        "generate_query_or_respond",
        tools_condition,
        {"tools": "retrieve", END: END},
    )
    workflow.add_edge("retrieve", "grade_documents")
    workflow.add_conditional_edges(
        "grade_documents",
        decide_after_grading,
        {"generate": "generate_answer", "rewrite": "rewrite_question"},
    )
    workflow.add_edge("rewrite_question", "generate_query_or_respond")
    workflow.add_edge("generate_answer", END)

    return workflow.compile()
