import hashlib
import json
import time
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import NotFoundError
from app.db.models import Conversation, Message
from app.db.repositories.conversation_repo import ConversationRepository
from collections.abc import AsyncIterator
from app.core.logging import get_logger
from app.db.models import AnswerCitation, Conversation, Message, User
from app.db.repositories.citation_repo import AnswerCitationRepository
from app.db.session import AsyncSessionLocal
from app.llm.answer_verifier import VerifyResult, get_answer_verifier
from app.llm.prompts import REFUSAL_ANSWER
from app.services.permission_service import (
    WILDCARD_PERMISSION_TAG,
    compute_user_permission_tags,
)
from app.core.observability import build_trace_url, get_current_trace_id
from app.retrieval.vector_retriever import RetrievedChunk
from app.workflows.graph import get_rag_graph
from langsmith import traceable
from app.workflows.nodes import load_context, stream_generate
from app.workflows.rag_state import RAGState

logger = get_logger(__name__)

ANSWER_CACHE_REVISION = "rag-answer-v1"


def _build_answer_cache_key(state: RAGState) -> str:
    """Bind a reusable answer to the normalized intent and exact evidence text."""
    question = state.get("standalone_question") or state["question"]
    payload = {
        "revision": ANSWER_CACHE_REVISION,
        "question": " ".join(question.casefold().split()),
        "model": settings.chat_model,
        "seed": settings.chat_seed,
        "verify_answer": settings.verify_answer_enabled,
        "evidence": [
            {
                "chunk_id": str(chunk.chunk_id),
                "content_sha256": hashlib.sha256(
                    chunk.content.encode("utf-8")
                ).hexdigest(),
            }
            for chunk in state.get("retrieved_chunks", [])
        ],
    }
    serialized = json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _serialize_citation(chunk: RetrievedChunk, ordinal: int) -> dict:
    """citations SSE 事件载荷格式,与CitationRead对齐。

    ordinal 必须显式传入：与 prompt 中给 LLM 看到的「片段 N」编号一致，
    前端按这个数字渲染 [N] 角标，避免后续顺序丢失导致引用串号。
    """
    return {
        "ordinal": ordinal,
        "chunk_id": str(chunk.chunk_id),
        "document_id": str(chunk.document_id),
        "document_name": chunk.document_name,
        "page_no": chunk.page_no,
        "section_path": chunk.section_path,
        "score": round(chunk.score, 4),
        "quote": chunk.content,
        "retrieval_meta": _build_retrieval_meta(chunk),  # 混合检索调试元数据
    }


def _serialize_agent_steps(state: RAGState) -> list[dict]:
    """SSE / metadata 共用的 agent_steps 载荷格式。

    state 内字段全部用原生 Python 类型，直接 JSON 序列化即可。这里做一层显式拷贝，
    避免后续节点继续追加时影响已发出的事件 / 已持久化的 metadata。
    """
    return [dict(step) for step in state.get("agent_steps", [])]



@dataclass(frozen=True)
class EvaluationAnswer:
    """评测专用：跑一遍 RAG 拿到的非流式结果快照。"""

    answer: str
    refused: bool
    chunks: list[RetrievedChunk]
    query_route: dict
    agent_steps: list[dict]
    verify_result: VerifyResult | None
    trace_id: str | None
    latency_ms: int
    first_token_latency_ms: int | None
    error_message: str | None = None
    citations: list[dict] = field(default_factory=list)
class ChatService:
    """注意：

    - 非流式接口（创建会话 / 历史）使用 FastAPI 注入的请求级 session
    - 流式问答使用独立 session（与请求生命周期解耦），由 stream_answer 内部管理
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # 注意缩进，这些都是 ChatService 类里的函数
    async def create_conversation(self, title: str = "新对话", *, user_id: UUID | None = None) -> Conversation:
        repo = ConversationRepository(self.session)
        conversation = await repo.create(title=title)
        if user_id is not None:
            conversation.user_id = user_id
        await self.session.commit()
        await self.session.refresh(conversation)
        return conversation

    async def get_conversation(self, conversation_id: UUID, *, user_id: UUID | None = None) -> Conversation:
        repo = ConversationRepository(self.session)
        conversation = await repo.get(conversation_id, user_id=user_id)
        if conversation is None:
            raise NotFoundError("会话不存在")
        return conversation

    async def list_messages(
        self, conversation_id: UUID, *, user_id: UUID | None = None,
    ) -> tuple[Conversation, list[Message]]:
        conversation = await self.get_conversation(conversation_id, user_id=user_id)
        repo = ConversationRepository(self.session)
        messages = await repo.list_messages(conversation_id)
        return conversation, messages

    async def list_conversations(
        self, page: int, page_size: int, *, user_id: UUID | None = None
    ) -> tuple[list[tuple[Conversation, int]], int]:
        repo = ConversationRepository(self.session)
        return await repo.list_page(page=page, page_size=page_size, user_id=user_id)

    async def delete_conversation(self, conversation_id: UUID, *, user_id: UUID | None = None) -> None:
        repo = ConversationRepository(self.session)
        deleted = await repo.delete(conversation_id, user_id=user_id)
        if not deleted:
            raise NotFoundError("会话不存在")
        await self.session.commit()

    # 注意缩进，这些都是 ChatService 类里的函数
    @traceable(name="ChatService.stream_answer", run_type="chain")
    async def stream_answer(
        self, conversation_id: UUID, question: str, *, current_user: User,
    ) -> AsyncIterator[dict]:
        """流式问答 SSE 数据。"""
        await self.get_conversation(conversation_id, user_id=current_user.id)
        permissions = compute_user_permission_tags(current_user)

        async with AsyncSessionLocal() as session:
            try:
                trace_id = get_current_trace_id()
                state: RAGState = {
                    "conversation_id": conversation_id,
                    "question": question,
                    "permissions": permissions,
                    "trace_id": trace_id,
                }

                # 1. 加载上下文（仅历史消息，本轮 user 消息尚未入库）。
                # load_context 是唯一需要 DB session 的节点，由 service 先填好再交给图。
                state.update(await load_context(state, session))

                # 2. 跑 RAG 子图：normalize_query -> route_query -> 检索决策循环
                final_state = await get_rag_graph().ainvoke(state)
                state.update(final_state)  # type: ignore[arg-type]

                if not state.get("refused"):
                    state["answer_cache_key"] = _build_answer_cache_key(state)

                # 3. user 消息落库
                await self._persist_user_message(state, session)

                yield {
                    "event": "message_start",
                    "data": {
                        "user_message_id": str(state["user_message_id"]),
                        "trace_id": trace_id,
                        "trace_url": build_trace_url(trace_id),
                    },
                }

                yield {
                    "event": "query_route",
                    "data": _build_query_route_payload(state),
                }

                yield {
                    "event": "agent_steps",
                    "data": {"steps": _serialize_agent_steps(state)},
                }

                # 拒答路径下不发 citations。retrieved_chunks 可能还残留 agent 循环
                # 中途某一轮的候选（被 observe_context 判为不足），但语义上既然已经拒答，
                # 前端就不该再展示这些参考资料。
                citations_payload = (
                    []
                    if state.get("refused")
                    else [
                        _serialize_citation(c, ordinal=i)
                        for i, c in enumerate(
                            state.get("retrieved_chunks", []), start=1
                        )
                    ]
                )

                yield {
                    "event": "citations",
                    "data": {"citations": citations_payload},
                }

                # 5. 生成：拒答直接发答案文案；否则逐 token 流式
                verify_result: VerifyResult | None = None
                cached_message: Message | None = None
                if not state.get("refused"):
                    cached_message = await ConversationRepository(
                        session
                    ).find_cached_answer(
                        state["conversation_id"], state["answer_cache_key"]
                    )

                if state.get("refused"):
                    yield {
                        "event": "token",
                        "data": {"delta": state["answer"]},
                    }
                elif cached_message is not None:
                    state["answer"] = cached_message.content
                    state["answer_cache_hit"] = True
                    yield {"event": "token", "data": {"delta": state["answer"]}}
                else:
                    state["answer_cache_hit"] = False
                    answer_parts: list[str] = []
                    async for delta in stream_generate(state):
                        answer_parts.append(delta)
                        yield {"event": "token", "data": {"delta": delta}}
                    state["answer"] = "".join(answer_parts)

                # 6. 答案校验
                if (
                    settings.verify_answer_enabled
                    and not state.get("refused")
                    and cached_message is not None
                ):
                    cached_verify = cached_message.extra_metadata.get(
                        "verify_result", {}
                    )
                    verify_result = VerifyResult(
                        verified=True,
                        reason=str(cached_verify.get("reason") or ""),
                    )
                    yield {
                        "event": "verify_result",
                        "data": _build_verify_payload(
                            verify_result, replacement_answer=None
                        ),
                    }
                elif settings.verify_answer_enabled and not state.get("refused"):
                    verify_result = await get_answer_verifier().verify(
                        question=state.get("standalone_question") or state["question"],
                        answer=state["answer"],
                        chunks=list(state.get("retrieved_chunks", [])),
                    )
                    replacement = REFUSAL_ANSWER if not verify_result.verified else None
                    if verify_result is not None and not verify_result.verified:
                        state["answer"] = REFUSAL_ANSWER
                        state["refused"] = True
                    yield {
                        "event": "verify_result",
                        "data": _build_verify_payload(
                            verify_result, replacement_answer=replacement
                        ),
                    }

                # 7. assistant 消息 + citations 同事务落库
                await self._persist_assistant_message(
                    state, session, verify_result=verify_result
                )

                yield {
                    "event": "message_end",
                    "data": {
                        "message_id": str(state["assistant_message_id"]),
                        "refused": bool(state.get("refused")),
                    },
                }

            except Exception as exc:
                logger.exception("chat stream failed: conversation_id=%s", conversation_id)
                # 注意：user 消息可能已在前置独立 commit，这里只回滚未提交的改动
                # （比如 assistant 写入中途失败）。保留 user 消息便于前端重试 / 重说。
                await session.rollback()
                yield {
                    "event": "error",
                    "data": {
                        "code": "chat_stream_failed",
                        "message": str(exc).strip() or "问答处理失败",
                    },
                }

        # 注意缩进，这些都是 ChatService 类里的函数

    @traceable(name="ChatService.answer_for_evaluation", run_type="chain")
    async def answer_for_evaluation(self, question: str) -> EvaluationAnswer:
        """跑一遍完整 RAG 拿非流式结果，用于离线评测。"""
        started_at = time.perf_counter()
        trace_id = get_current_trace_id()

        state: RAGState = {
            "conversation_id": UUID(int=0),
            "question": question,
            "chat_history": [],
            "permissions": [WILDCARD_PERMISSION_TAG],
            "trace_id": trace_id,
        }

        try:
            final_state = await get_rag_graph().ainvoke(state)
            state.update(final_state)  # type: ignore[arg-type]

            verify_result: VerifyResult | None = None
            first_token_latency_ms: int | None = None

            if state.get("refused"):
                answer = state["answer"]
            else:
                parts: list[str] = []
                async for delta in stream_generate(state):
                    if first_token_latency_ms is None:
                        first_token_latency_ms = int(
                            (time.perf_counter() - started_at) * 1000
                        )
                    parts.append(delta)
                answer = "".join(parts)
                state["answer"] = answer

            if settings.verify_answer_enabled:
                verify_result = await get_answer_verifier().verify(
                    question=question,
                    answer=answer,
                    chunks=list(state.get("retrieved_chunks", [])),
                )

            if not verify_result.verified:
                answer = REFUSAL_ANSWER
                state["answer"] = answer
                state["refused"] = True

            chunks = list(state.get("retrieved_chunks", []))
            refused = bool(state.get("refused"))
            citations = (
                []
                if refused
                else [_serialize_citation(c, ordinal=i) for i, c in enumerate(chunks, 1)]
            )

            return EvaluationAnswer(
                answer=answer,
                refused=refused,
                chunks=chunks,
                query_route=_build_query_route_payload(state),
                agent_steps=_serialize_agent_steps(state),
                verify_result=verify_result,
                trace_id=trace_id,
                latency_ms=int((time.perf_counter() - started_at) * 1000),
                first_token_latency_ms=first_token_latency_ms,
                citations=citations,
            )

        except Exception as exc:
            logger.exception("evaluation answer failed: question=%r", question)
            return EvaluationAnswer(
                answer="",
                refused=False,
                chunks=[],
                query_route=_build_query_route_payload(state),
                agent_steps=_serialize_agent_steps(state),
                verify_result=None,
                trace_id=trace_id,
                latency_ms=int((time.perf_counter() - started_at) * 1000),
                first_token_latency_ms=None,
                error_message=str(exc).strip() or exc.__class__.__name__,
            )
    async def _persist_user_message(
        self, state: RAGState, session: AsyncSession
    ) -> None:
        """流式开始前先把 user 消息落库并 commit；首次提问时顺手把会话标题改成问题前 30 字。

        必须在 load_context 之后调用：load_context 读到的"历史消息"不应包含本轮提问。
        标题更新放在同一事务里，避免新建会话后侧栏一直显示「新对话」。
        """
        repo = ConversationRepository(session)
        # 首次提问（会话还没有任何消息）→ 把默认标题改成本次问题
        if await repo.count_messages(state["conversation_id"]) == 0:
            await repo.update_title_if_default(
                state["conversation_id"], state["question"]
            )

        user_msg = ConversationRepository.make_user_message(
            state["conversation_id"], content=state["question"]
        )
        await repo.add_messages([user_msg])
        await session.commit()
        state["user_message_id"] = user_msg.id

    async def _persist_assistant_message(
        self,
        state: RAGState,
        session: AsyncSession,
        *,
        verify_result: VerifyResult | None,
    ) -> None:
        """流式生成结束后落库 assistant 消息及其引用，单事务保证两者原子。"""
        conv_repo = ConversationRepository(session)
        citation_repo = AnswerCitationRepository(session)

        extra_metadata: dict = {
            "refused": bool(state.get("refused")),
            "query_route": _build_query_route_payload(state),
            "agent_steps": _serialize_agent_steps(state),
            "answer_cache_key": state.get("answer_cache_key"),
            "answer_cache_hit": bool(state.get("answer_cache_hit")),
            "answer_cache_eligible": bool(
                not state.get("refused")
                and (
                    not settings.verify_answer_enabled
                    or (verify_result is not None and verify_result.verified)
                )
            ),
            "trace_id": state.get("trace_id"),
        }
        if verify_result is not None:
            extra_metadata["verify_result"] = _build_verify_payload(
                verify_result, replacement_answer=None
            )

        assistant_msg = ConversationRepository.make_assistant_message(
            state["conversation_id"],
            content=state["answer"],
            extra_metadata=extra_metadata,
        )

        await conv_repo.add_messages([assistant_msg])

        if not state.get("refused"):
            citations = [
                AnswerCitation(
                    message_id=assistant_msg.id,
                    ordinal=ordinal,
                    document_id=chunk.document_id,
                    chunk_id=chunk.chunk_id,
                    document_name=chunk.document_name,
                    page_no=chunk.page_no,
                    quote=chunk.content,
                    retrieval_meta=_build_retrieval_meta(chunk),  # 混合检索调试元数据
                )
                for ordinal, chunk in enumerate(
                    state.get("retrieved_chunks", []), start=1
                )
            ]
            await citation_repo.bulk_add(citations)

        await session.commit()
        state["assistant_message_id"] = assistant_msg.id

def _build_query_route_payload(state: RAGState) -> dict:
    """SSE / metadata 共用的 query_route 载荷格式。

    始终携带 4 个可选字段（None 也保留），前端可据此判断展示哪种调试面板。
    """
    return {
        "route": state.get("route", "original"),
        "query": state.get("query", ""),
        "rewritten_query": state.get("rewritten_query"),
        "hyde_answer": state.get("hyde_answer"),
        "multi_queries": state.get("multi_queries"),
    }

def _build_retrieval_meta(chunk: RetrievedChunk) -> dict:
    """混合检索调试元数据"""
    return {
        "sources": list(chunk.sources),
        "vector_rank": chunk.vector_rank,
        "vector_score": (
            round(chunk.vector_score, 4) if chunk.vector_score is not None else None
        ),
        "keyword_rank": chunk.keyword_rank,
        "keyword_score": (
            round(chunk.keyword_score, 4) if chunk.keyword_score is not None else None
        ),
        "rrf_score": (
            round(chunk.rrf_score, 6) if chunk.rrf_score is not None else None
        ),
        "rerank_score": (
            round(chunk.rerank_score, 4) if chunk.rerank_score is not None else None
        ),
    }


def _build_verify_payload(
    result: VerifyResult, *, replacement_answer: str | None
) -> dict:
    """verify_result SSE / metadata 共用载荷。"""
    payload: dict = {
        "verified": result.verified,
        "reason": result.reason or None,
    }
    if not result.verified and replacement_answer is not None:
        payload["replacement_answer"] = replacement_answer
    return payload
