from collections.abc import AsyncIterable
from uuid import UUID

from fastapi import APIRouter, Query, Response
from fastapi.responses import EventSourceResponse
from fastapi.sse import ServerSentEvent

from app.api.deps import CurrentUser, DbSession
from app.api.schemas.chat import (
    ChatRequest,
    ConversationCreate,
    ConversationDetail,
    ConversationListItem,
    ConversationPage,
    ConversationRead,
    MessageRead,
)
from app.services.chat_service import ChatService

router = APIRouter(prefix="/conversations", tags=["chat"])


@router.post(
    "",
    response_model=ConversationRead,
    status_code=201,
    operation_id="createConversation",
)
async def create_conversation(
    user: CurrentUser,
    payload: ConversationCreate,
    session: DbSession,
) -> ConversationRead:
    service = ChatService(session)
    conversation = await service.create_conversation(
        user_id=user.id, title=payload.title
    )
    return ConversationRead.model_validate(conversation)


@router.get(
    "",
    response_model=ConversationPage,
    operation_id="listConversations",
)
async def list_conversations(
    user: CurrentUser,
    session: DbSession,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> ConversationPage:
    service = ChatService(session)
    items, total = await service.list_conversations(
        page=page, page_size=page_size, user_id=user.id
    )
    return ConversationPage(
        items=[
            ConversationListItem(
                id=conv.id,
                title=conv.title,
                updated_at=conv.updated_at,
                message_count=count,
            )
            for conv, count in items
        ],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/{conversation_id}",
    response_model=ConversationDetail,
    operation_id="getConversation",
)
async def get_conversation(
    user: CurrentUser,
    conversation_id: UUID,
    session: DbSession,
) -> ConversationDetail:
    service = ChatService(session)
    conversation, messages = await service.list_messages(
        conversation_id, user_id=user.id
    )
    return ConversationDetail(
        conversation=ConversationRead.model_validate(conversation),
        messages=[MessageRead.from_orm(m) for m in messages],
    )


@router.delete(
    "/{conversation_id}",
    status_code=204,
    operation_id="deleteConversation",
)
async def delete_conversation(
    user: CurrentUser,
    conversation_id: UUID,
    session: DbSession,
) -> Response:
    service = ChatService(session)
    await service.delete_conversation(conversation_id, user_id=user.id)
    return Response(status_code=204)


@router.post(
    "/{conversation_id}/chat",
    operation_id="streamChat",
    response_class=EventSourceResponse,
)
async def stream_chat(
    user: CurrentUser,
    conversation_id: UUID,
    payload: ChatRequest,
    session: DbSession,
) -> AsyncIterable[ServerSentEvent]:
    service = ChatService(session)
    async for sse_event in service.stream_answer(
        conversation_id, payload.question, current_user=user
    ):
        yield ServerSentEvent(
            data=sse_event["data"],
            event=sse_event["event"],
        )
