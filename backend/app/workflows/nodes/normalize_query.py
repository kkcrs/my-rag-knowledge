from app.llm.query_rewriter import get_query_rewriter
from app.workflows.rag_state import RAGState


_CONTEXT_MARKERS = (
    "它",
    "这个",
    "那个",
    "上述",
    "上面",
    "前面",
    "刚才",
    "之前提到",
    "该产品",
    "该设备",
    "该型号",
    "其中",
)
_SHORT_FOLLOW_UP_SUFFIXES = (
    "呢",
    "怎么样",
    "如何",
    "多少",
    "有哪些",
    "是什么",
    "可以吗",
    "支持吗",
)


def needs_contextualization(question: str) -> bool:
    """仅对明确依赖上文的追问做 LLM 上下文化。

    完整实体名或型号必须原样保留，避免模型把上一轮回答改写进检索 query。
    """
    text = question.strip()
    if any(marker in text for marker in _CONTEXT_MARKERS):
        return True
    return len(text) <= 20 and text.endswith(_SHORT_FOLLOW_UP_SUFFIXES)


async def normalize_query(state: RAGState) -> RAGState:
    question = state["question"].strip()
    history = state.get("chat_history") or []
    if not history or not needs_contextualization(question):
        return {"standalone_question": question, "query": question}

    rewritten = await get_query_rewriter().contextualize(
        question=question, history=history
    )
    standalone_question = rewritten.strip() or question
    return {
        "standalone_question": standalone_question,
        "query": standalone_question,
    }
