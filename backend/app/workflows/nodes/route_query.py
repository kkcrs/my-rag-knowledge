import re

from app.core.config import settings
from app.llm.query_rewriter import get_query_rewriter
from app.workflows.rag_state import RAGState


_MODEL_IDENTIFIER_RE = re.compile(
    r"(?<![A-Za-z0-9])"
    r"(?=[A-Za-z0-9-]*[A-Za-z])(?=[A-Za-z0-9-]*\d)"
    r"[A-Za-z0-9]+(?:-[A-Za-z0-9]+)*"
    r"(?![A-Za-z0-9])"
)
_MULTI_INTENT_MARKERS = ("对比", "比较", "区别", "差异", "优缺点", "以及", " vs ")


def is_specific_identifier_query(question: str) -> bool:
    """型号/编号类单实体查询固定走 original，避免 LLM 路由漂移。"""
    normalized = f" {question.strip().lower()} "
    if any(marker in normalized for marker in _MULTI_INTENT_MARKERS):
        return False
    return _MODEL_IDENTIFIER_RE.search(question) is not None


async def route_query(state: RAGState) -> RAGState:
    question = state.get("standalone_question") or state["query"]
    if not settings.query_route_enabled:
        # 关闭路由：直接走原始查询，保留 normalize_query 透传的 state["query"]
        return {"route": "original"}

    if is_specific_identifier_query(question):
        return {"route": "original", "query": question}

    result = await get_query_rewriter().optimize(
        question=question,
        multi_query_count=settings.query_multi_query_count,
    )
    # query 字段被显式覆盖：rewrite/hyde 路径下用改写文本去向量召回
    update: RAGState = {"route": result.route, "query": result.query}
    if result.rewritten_query is not None:
        update["rewritten_query"] = result.rewritten_query
    if result.hyde_answer is not None:
        update["hyde_answer"] = result.hyde_answer
    if result.multi_queries is not None:
        update["multi_queries"] = result.multi_queries
    return update
