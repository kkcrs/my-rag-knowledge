from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models import Conversation, Message, MessageRole

DEFAULT_CONVERSATION_TITLE = "新对话"


class ConversationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, title: str = DEFAULT_CONVERSATION_TITLE) -> Conversation:
        conversation = Conversation(title=title)
        self.session.add(conversation)
        await self.session.flush()
        return conversation

    async def get(self, conversation_id: UUID, *, user_id: UUID | None = None) -> Conversation | None:
        if user_id is None:
            return await self.session.get(Conversation, conversation_id)
        stmt = select(Conversation).where(
            Conversation.id == conversation_id,
            Conversation.user_id == user_id,
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def list_messages(self, conversation_id: UUID) -> list[Message]:
        """按时间正序返回所有消息（含引用）。前端展示历史用。"""
        stmt = (
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.created_at.asc(), Message.id.asc())
            .options(selectinload(Message.citations))
        )
        return list((await self.session.execute(stmt)).scalars().all())

    async def recent_messages(self, conversation_id: UUID, limit: int) -> list[Message]:
        """取最近 N 条消息，按时间正序返回"""
        if limit <= 0:
            return []
        # 先倒序取 N 条，再在 Python 侧反转为正序
        stmt = (
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.created_at.desc(), Message.id.desc())
            .limit(limit)
        )
        rows = list((await self.session.execute(stmt)).scalars().all())
        return list(reversed(rows))

    async def find_cached_answer(
        self, conversation_id: UUID, answer_cache_key: str
    ) -> Message | None:
        """Return the newest verified answer for the exact question/evidence key."""
        stmt = (
            select(Message)
            .where(
                Message.conversation_id == conversation_id,
                Message.role == MessageRole.ASSISTANT,
                Message.extra_metadata.op("->>")("answer_cache_key")
                == answer_cache_key,
                Message.extra_metadata.op("->>")("answer_cache_eligible")
                == "true",
            )
            .order_by(Message.created_at.desc(), Message.id.desc())
            .limit(1)
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def add_messages(self, messages: Sequence[Message]) -> None:
        if not messages:
            return
        self.session.add_all(messages)
        await self.session.flush()

    async def count_messages(self, conversation_id: UUID) -> int:
        stmt = select(func.count(Message.id)).where(
            Message.conversation_id == conversation_id
        )
        return int((await self.session.execute(stmt)).scalar_one())

    async def list_page(
        self, page: int, page_size: int, *, user_id: UUID | None = None,
    ) -> tuple[list[tuple[Conversation, int]], int]:
        page = max(page, 1)
        page_size = max(min(page_size, 100), 1)
        offset = (page - 1) * page_size

        stmt = (
            select(Conversation, func.count(Message.id))
            .outerjoin(Message, Message.conversation_id == Conversation.id)
            .group_by(Conversation.id)
            .order_by(Conversation.updated_at.desc())
            .limit(page_size)
            .offset(offset)
        )
        count_stmt = select(func.count(Conversation.id))
        if user_id is not None:
            stmt = stmt.where(Conversation.user_id == user_id)
            count_stmt = count_stmt.where(Conversation.user_id == user_id)

        rows = (await self.session.execute(stmt)).all()
        items = [(row[0], int(row[1])) for row in rows]
        total = int((await self.session.execute(count_stmt)).scalar_one())
        return items, total

    async def delete(self, conversation_id: UUID, *, user_id: UUID | None = None) -> bool:
        """硬删会话。"""
        conversation = await self.get(conversation_id, user_id=user_id)
        if conversation is None:
            return False
        await self.session.delete(conversation)
        await self.session.flush()
        return True

    async def update_title_if_default(
        self, conversation_id: UUID, title: str
    ) -> None:
        """首次提问后把"新对话"自动改成问题前 N 字。"""
        new_title = title.strip()
        if not new_title:
            return
        conversation = await self.get(conversation_id)
        if conversation is None or conversation.title != DEFAULT_CONVERSATION_TITLE:
            return
        conversation.title = new_title[:30]
        await self.session.flush()

    @staticmethod
    def make_user_message(conversation_id: UUID, content: str) -> Message:
        return Message(conversation_id=conversation_id, role=MessageRole.USER, content=content)

    @staticmethod
    def make_assistant_message(
        conversation_id: UUID,
        content: str,
        *,
        extra_metadata: dict | None = None,
    ) -> Message:
        return Message(
            conversation_id=conversation_id,
            role=MessageRole.ASSISTANT,
            content=content,
            extra_metadata=extra_metadata or {},
        )
