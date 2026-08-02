"""Celery 任务定义。"""

from uuid import UUID

from app.celery_app import celery_app
from app.ingestion.pipeline import run_ingest_sync, run_reindex_sync


@celery_app.task(name="ingest_document", bind=True)
def ingest_document_task(self, document_id: str, task_id: str) -> None:
    run_ingest_sync(UUID(document_id), UUID(task_id))


@celery_app.task(name="reindex_document", bind=True)
def reindex_document_task(self, document_id: str, task_id: str) -> None:
    run_reindex_sync(UUID(document_id), UUID(task_id))


@celery_app.task(name="execute_evaluation", bind=True)
def execute_evaluation_task(self, run_id: str) -> None:
    import asyncio
    from app.services.evaluation_service import execute_evaluation_run

    asyncio.run(execute_evaluation_run(UUID(run_id)))
