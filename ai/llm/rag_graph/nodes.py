from __future__ import annotations

from typing import Any

from langchain_core.documents import Document
from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage
from langchain_openai import ChatOpenAI

from .prompts import ANSWER_PROMPT, GRADER_PROMPT, REWRITE_PROMPT, SYSTEM_AGENT_PROMPT
from .state import RAGState
from .tools import parse_hits


def _latest_user_question(state: RAGState) -> str:
    for msg in reversed(state["messages"]):
        if isinstance(msg, HumanMessage):
            return msg.content if isinstance(msg.content, str) else str(msg.content)
    return state.get("question", "")


def generate_query_or_respond(state: RAGState, llm_with_tools: ChatOpenAI) -> dict[str, Any]:
    """Узел-агент: решает, вызывать retriever_tool или отвечать сразу."""
    question = _latest_user_question(state)
    messages = [SystemMessage(content=SYSTEM_AGENT_PROMPT), *state["messages"]]
    response = llm_with_tools.invoke(messages)
    return {
        "messages": [response],
        "question": question,
    }


def grade_documents(state: RAGState, grader_llm: ChatOpenAI, max_retries: int = 2) -> dict[str, Any]:
    """
    Оценивает, достаточно ли релевантны документы.
    Возвращает action для маршрутизации: 'generate' или 'rewrite'.
    """
    retries = state.get("retries", 0) or 0

    tool_messages = [m for m in state["messages"] if isinstance(m, ToolMessage)]
    raw_hits = parse_hits(tool_messages[-1].content) if tool_messages else []

    docs: list[Document] = []
    for hit in raw_hits:
        payload = hit.get("payload") or {}
        text = payload.get("text") or ""
        if text:
            docs.append(Document(page_content=text, metadata=payload))

    state["raw_hits"] = raw_hits
    state["documents"] = docs

    if not docs:
        next_action = "generate" if retries >= max_retries else "rewrite"
        return {
            "raw_hits": raw_hits,
            "documents": docs,
            "retries": retries + 1,
            "action": next_action,
        }

    question = state.get("question", _latest_user_question(state))
    preview = "\n\n".join(d.page_content[:500] for d in docs[:4])
    prompt = (
        f"{GRADER_PROMPT}\n\n"
        f"Вопрос:\n{question}\n\n"
        f"Документы:\n{preview}"
    )
    decision = grader_llm.invoke([HumanMessage(content=prompt)])
    content = decision.content.lower().strip() if isinstance(decision.content, str) else str(decision.content).lower()

    if "yes" in content:
        return {
            "raw_hits": raw_hits,
            "documents": docs,
            "action": "generate",
        }

    next_action = "generate" if retries >= max_retries else "rewrite"
    return {
        "raw_hits": raw_hits,
        "documents": docs,
        "retries": retries + 1,
        "action": next_action,
    }


def decide_after_grading(state: RAGState) -> str:
    """Маршрутизация после узла оценки документов."""
    action = (state.get("action") or "").strip().lower()
    if action == "rewrite":
        return "rewrite"
    return "generate"


def rewrite_question(state: RAGState, llm: ChatOpenAI) -> dict[str, Any]:
    """Переписывает вопрос для повторного ретрива."""
    question = state.get("question", _latest_user_question(state))
    prompt = f"{REWRITE_PROMPT}\n\nИсходный вопрос:\n{question}"
    rewritten = llm.invoke([HumanMessage(content=prompt)])
    rewritten_text = rewritten.content if isinstance(rewritten.content, str) else str(rewritten.content)
    return {
        "question": rewritten_text.strip(),
        "retries": (state.get("retries", 0) or 0) + 1,
        "messages": [HumanMessage(content=rewritten_text.strip())],
    }


def generate_answer(state: RAGState, llm: ChatOpenAI) -> dict[str, Any]:
    """Генерирует финальный ответ на основе найденных документов."""
    question = state.get("question", _latest_user_question(state))
    docs = state.get("documents", [])
    context = "\n\n---\n\n".join(d.page_content for d in docs[:8]).strip()
    if not context:
        context = "Контекст не найден."
    prompt = (
        f"{ANSWER_PROMPT}\n\n"
        f"Вопрос:\n{question}\n\n"
        f"Контекст:\n{context}"
    )
    answer = llm.invoke([HumanMessage(content=prompt)])
    answer_text = answer.content if isinstance(answer.content, str) else str(answer.content)
    return {
        "generation": answer_text,
        "messages": [answer],
    }
