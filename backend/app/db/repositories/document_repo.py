from uuid import UUID

from sqlalchemy import String, func, literal, select
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.repositories.chunk_repo import _permission_where

from app.db.models import Document, DocumentStatus


class DocumentRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(self, document_id: UUID, *, permission_tags: list[str] | None = None) -> Document | None:
        stmt = select(Document).where(Document.id == document_id)
        if permission_tags is not None:
            stmt = _apply_permission_filter(stmt, permission_tags)
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def get_by_hash(self, file_hash: str) -> Document | None:
        stmt = select(Document).where(Document.file_hash == file_hash)
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def add(self, document: Document) -> Document:
        self.session.add(document)
        await self.session.flush()
        return document

    async def update_status(
        self,
        document_id: UUID,
        status: DocumentStatus,
        *,
        error_message: str | None = None,
    ) -> None:
        doc = await self.get_by_id(document_id)
        if doc is None:
            return

        doc.status = status
        # 仅在显式传入时覆盖；保留 None 语义供成功状态清空之前的错误信息
        if error_message is not None or status != DocumentStatus.FAILED:
            doc.error_message = error_message

    async def list_paginated(
        self,
        page: int,
        page_size: int,
        *,
        status: DocumentStatus | None = None,
        permission_tags: list[str] | None = None,
    ) -> tuple[list[Document], int]:
        offset = (page - 1) * page_size
        items_stmt = (
            select(Document)
            .order_by(Document.created_at.desc())
            .offset(offset)
            .limit(page_size)
        )
        count_stmt = select(func.count()).select_from(Document)
        if status is not None:
            items_stmt = items_stmt.where(Document.status == status)
            count_stmt = count_stmt.where(Document.status == status)
        if permission_tags is not None:
            items_stmt = _apply_permission_filter(items_stmt, permission_tags)
            count_stmt = _apply_permission_filter(count_stmt, permission_tags)
        items = (await self.session.execute(items_stmt)).scalars().all()
        total = (await self.session.execute(count_stmt)).scalar_one()
        return list(items), int(total)

    async def delete(self, document: Document) -> None:
        """删除文档。chunks 走 ORM 级联删除（Document.chunks 配了 delete-orphan）。"""
        await self.session.delete(document)


def _apply_permission_filter(stmt, permission_tags: list[str]):
    """应用权限过滤：含 "*" 通配/空/None 则不加过滤，否则用 && 数组重叠匹配。"""
    perm_where = _permission_where(permission_tags)
    if perm_where is not None:
        stmt = stmt.where(perm_where)
    return stmt