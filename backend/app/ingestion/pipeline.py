import asyncio
from uuid import UUID

from app.core.config import settings
from app.core.logging import get_logger
from app.db.models import DocumentChunk, DocumentStatus
from app.db.repositories.chunk_repo import DocumentChunkRepository
from app.db.repositories.document_repo import DocumentRepository
from app.db.repositories.ingestion_task_repository import IngestionTaskRepository
from app.db.session import AsyncSessionLocal
from app.ingestion import embedder, parser, splitter
from app.storage.file_service import get_file_service

logger = get_logger(__name__)


async def _set_status(
    document_id: UUID,
    status: DocumentStatus,
    *,
    error_message: str | None = None,
) -> None:
    async with AsyncSessionLocal() as session:
        repo = DocumentRepository(session)
        await repo.update_status(document_id, status, error_message=error_message)
        await session.commit()


async def _mark_task(task_id: UUID, *, running: bool = False) -> None:
    async with AsyncSessionLocal() as session:
        repo = IngestionTaskRepository(session)
        if running:
            await repo.mark_running(task_id)
        await session.commit()


async def _mark_task_failed(task_id: UUID, error_message: str) -> None:
    async with AsyncSessionLocal() as session:
        repo = IngestionTaskRepository(session)
        await repo.mark_failed(task_id, error_message)
        await session.commit()


async def _mark_task_success(task_id: UUID) -> None:
    async with AsyncSessionLocal() as session:
        repo = IngestionTaskRepository(session)
        await repo.mark_success(task_id)
        await session.commit()


async def _set_task_total(task_id: UUID, total: int) -> None:
    async with AsyncSessionLocal() as session:
        repo = IngestionTaskRepository(session)
        await repo.set_progress_total(task_id, total)
        await session.commit()


async def _increment_task_progress(task_id: UUID, delta: int) -> None:
    async with AsyncSessionLocal() as session:
        repo = IngestionTaskRepository(session)
        await repo.increment_progress(task_id, delta)
        await session.commit()


async def _embed_with_progress(
    texts: list[str], task_id: UUID
) -> list[list[float]]:
    if not texts:
        return []
    embeddings_client = embedder.get_embeddings()
    batch_size = max(1, settings.embedding_batch_size)
    results: list[list[float]] = []
    for start in range(0, len(texts), batch_size):
        batch = texts[start: start + batch_size]
        vectors = await embeddings_client.aembed_documents(batch)
        results.extend(vectors)
        await _increment_task_progress(task_id, len(batch))
    return results


def _make_chunk(
    document_id: UUID, chunk, embedding: list[float]
) -> DocumentChunk:
    return DocumentChunk(
        document_id=document_id,
        content=chunk.page_content,
        embedding=embedding,
        page_no=chunk.metadata.get("page_no"),
        section_path=chunk.metadata.get("section_path"),
        chunk_index=chunk.metadata["chunk_index"],
        chunk_hash=chunk.metadata["chunk_hash"],
        extra_metadata=chunk.metadata,
    )


async def _run_ingest(document_id: UUID, task_id: UUID) -> None:
    logger.info("ingest start: document_id=%s task_id=%s", document_id, task_id)
    await _mark_task(task_id, running=True)

    try:
        async with AsyncSessionLocal() as session:
            document = await DocumentRepository(session).get_by_id(document_id)
            if document is None:
                await _mark_task_failed(task_id, "文档不存在")
                return
            object_key = document.cos_object_key
            filename = document.name

        await _set_status(document_id, DocumentStatus.PARSING)
        content = await get_file_service().download(object_key)
        parsed = await parser.parse(filename, content)

        await _set_status(document_id, DocumentStatus.INDEXING)
        chunks = splitter.split(parsed)
        if not chunks:
            raise ValueError("切分后无有效 chunk，请检查文档内容")

        await _set_task_total(task_id, len(chunks))
        embeddings = await _embed_with_progress(
            [c.page_content for c in chunks], task_id
        )

        async with AsyncSessionLocal() as session:
            await DocumentChunkRepository(session).bulk_add(
                [_make_chunk(document_id, c, vec)
                 for c, vec in zip(chunks, embeddings, strict=True)]
            )
            await session.commit()

        await _set_status(document_id, DocumentStatus.READY, error_message=None)
        await _mark_task_success(task_id)
        logger.info("ingest done: document_id=%s chunks=%d", document_id, len(chunks))

    except Exception as exc:
        logger.exception("ingest failed: document_id=%s", document_id)
        message = str(exc)[:500] or exc.__class__.__name__
        await _set_status(document_id, DocumentStatus.FAILED, error_message=message)
        await _mark_task_failed(task_id, message)


def run_ingest_sync(document_id: UUID, task_id: UUID) -> None:
    asyncio.run(_run_ingest(document_id, task_id))


async def ingest_document(document_id: UUID) -> None:
    """保留旧签名兼容：原 BackgroundTasks 入口。"""
    async with AsyncSessionLocal() as session:
        repo = IngestionTaskRepository(session)
        task = await repo.create(document_id, "ingest")
        await session.commit()
    await _run_ingest(document_id, task.id)


async def _run_reindex(document_id: UUID, task_id: UUID) -> None:
    logger.info("reindex start: document_id=%s task_id=%s", document_id, task_id)
    await _mark_task(task_id, running=True)

    try:
        async with AsyncSessionLocal() as session:
            document = await DocumentRepository(session).get_by_id(document_id)
            if document is None:
                await _mark_task_failed(task_id, "文档不存在")
                return
            chunk_repo = DocumentChunkRepository(session)
            old_chunks = await chunk_repo.list_all_by_document(document_id)
            object_key = document.cos_object_key
            filename = document.name

        await _set_status(document_id, DocumentStatus.PARSING)
        content = await get_file_service().download(object_key)
        parsed = await parser.parse(filename, content)

        await _set_status(document_id, DocumentStatus.INDEXING)
        new_chunks = splitter.split(parsed)
        if not new_chunks:
            raise ValueError("切分后无有效 chunk")

        await _set_task_total(task_id, len(new_chunks))

        if _has_duplicate_hashes(new_chunks):
            logger.warning(
                "hash collision detected, fall back to full rebuild: document_id=%s",
                document_id,
            )
            await _run_full_rebuild(document_id, task_id, new_chunks)
        else:
            await _run_incremental(document_id, task_id, old_chunks, new_chunks)

        await _set_status(document_id, DocumentStatus.READY, error_message=None)
        await _mark_task_success(task_id)
        logger.info("reindex done: document_id=%s", document_id)

    except Exception as exc:
        logger.exception("reindex failed: document_id=%s", document_id)
        message = str(exc)[:500] or exc.__class__.__name__
        await _set_status(document_id, DocumentStatus.FAILED, error_message=message)
        await _mark_task_failed(task_id, message)


def _has_duplicate_hashes(chunks) -> bool:
    seen: set[str] = set()
    for c in chunks:
        h = c.metadata["chunk_hash"]
        if h in seen:
            return True
        seen.add(h)
    return False


async def _run_incremental(
    document_id: UUID,
    task_id: UUID,
    old_chunks,
    new_chunks,
) -> None:
    old_by_hash = {c.chunk_hash: c for c in old_chunks}
    new_hashes = {c.metadata["chunk_hash"] for c in new_chunks}

    to_delete_ids: list[UUID] = [
        c.id for c in old_chunks if c.chunk_hash not in new_hashes
    ]
    to_insert = []
    to_update = []

    for nc in new_chunks:
        h = nc.metadata["chunk_hash"]
        existing = old_by_hash.get(h)
        if existing is None:
            to_insert.append(nc)
        else:
            to_update.append((existing, nc))

    await _set_task_total(task_id, len(to_insert))
    new_embeddings = await _embed_with_progress(
        [c.page_content for c in to_insert], task_id
    )

    async with AsyncSessionLocal() as session:
        chunk_repo = DocumentChunkRepository(session)
        await chunk_repo.delete_by_ids(to_delete_ids)

        for old, nc in to_update:
            old.chunk_index = nc.metadata["chunk_index"]
            old.page_no = nc.metadata.get("page_no")
            old.section_path = nc.metadata.get("section_path")
            old.extra_metadata = nc.metadata

        await chunk_repo.bulk_add(
            [
                _make_chunk(document_id, c, vec)
                for c, vec in zip(to_insert, new_embeddings, strict=True)
            ]
        )
        await session.commit()


async def _run_full_rebuild(
    document_id: UUID,
    task_id: UUID,
    new_chunks,
) -> None:
    await _set_task_total(task_id, len(new_chunks))
    embeddings = await _embed_with_progress(
        [c.page_content for c in new_chunks], task_id
    )
    async with AsyncSessionLocal() as session:
        chunk_repo = DocumentChunkRepository(session)
        await chunk_repo.delete_by_document(document_id)
        await chunk_repo.bulk_add(
            [
                _make_chunk(document_id, c, vec)
                for c, vec in zip(new_chunks, embeddings, strict=True)
            ]
        )
        await session.commit()


def run_reindex_sync(document_id: UUID, task_id: UUID) -> None:
    asyncio.run(_run_reindex(document_id, task_id))
