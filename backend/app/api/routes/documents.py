import json
from urllib.parse import quote
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, File, Form, Header, Query, Response, UploadFile

from app.api.deps import CurrentAdmin, CurrentViewer, DbSession
from app.api.schemas.documents import (
    DocumentChunkDetail,
    DocumentChunkListResponse,
    DocumentChunkRead,
    DocumentChunkStats,
    DocumentListResponse,
    DocumentPermissionTagsUpdate,
    DocumentRead,
    DocumentStatusValue,
)
from app.db.models import DocumentStatus
from app.services.permission_service import compute_user_permission_tags, is_admin

router = APIRouter(prefix="/documents", tags=["documents"])


def _viewer_tags(user) -> list[str] | None:
    """admin 返回 None（不做过滤）；普通用户返回合并后的有效标签。"""
    return None if is_admin(user) else compute_user_permission_tags(user)


def _get_document_service(session: DbSession):
    from app.services.document_service import DocumentService

    return DocumentService(session)


# ─── 读接口（CurrentViewer）─────────────────────────────────

@router.get("", response_model=DocumentListResponse, operation_id="listDocuments")
async def list_documents(
    user: CurrentViewer,
    session: DbSession,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: DocumentStatusValue | None = Query(None),
) -> DocumentListResponse:
    service = _get_document_service(session)
    status_filter: DocumentStatus | None = None
    if status is not None:
        try:
            status_filter = DocumentStatus(status)
        except ValueError:
            pass
    items, total = await service.list_documents(
        page, page_size, status=status_filter,
        permission_tags=_viewer_tags(user),
    )
    return DocumentListResponse(
        items=[DocumentRead.model_validate(d) for d in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{document_id}", response_model=DocumentRead, operation_id="getDocument")
async def get_document(
    user: CurrentViewer,
    document_id: UUID,
    session: DbSession,
) -> DocumentRead:
    service = _get_document_service(session)
    doc = await service.get(document_id, permission_tags=_viewer_tags(user))
    return DocumentRead.model_validate(doc)


@router.get(
    "/{document_id}/chunks",
    response_model=DocumentChunkListResponse,
    operation_id="listDocumentChunks",
)
async def list_document_chunks(
    user: CurrentViewer,
    document_id: UUID,
    session: DbSession,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> DocumentChunkListResponse:
    service = _get_document_service(session)
    items, total, stats = await service.list_chunks(
        document_id, page, page_size,
        permission_tags=_viewer_tags(user),
    )
    return DocumentChunkListResponse(
        items=[DocumentChunkRead.model_validate(c) for c in items],
        total=total,
        page=page,
        page_size=page_size,
        stats=DocumentChunkStats(
            total=stats.total,
            avg_length=stats.avg_length,
            min_length=stats.min_length,
            max_length=stats.max_length,
        ) if stats else None,
    )


@router.get(
    "/{document_id}/chunks/{chunk_id}",
    response_model=DocumentChunkDetail,
    operation_id="getDocumentChunk",
)
async def get_document_chunk(
    user: CurrentViewer,
    document_id: UUID,
    chunk_id: UUID,
    session: DbSession,
) -> DocumentChunkDetail:
    service = _get_document_service(session)
    chunk = await service.get_chunk(
        document_id, chunk_id, permission_tags=_viewer_tags(user),
    )
    return DocumentChunkDetail.model_validate(chunk)


@router.get("/{document_id}/file", operation_id="downloadDocument")
async def download_document(
    document_id: UUID,
    session: DbSession,
    download: bool = Query(False, description="true 为下载，false 为预览"),
    token: str = Query("", description="Bearer token"),
    authorization: str | None = Header(None, alias="Authorization"),
) -> Response:
    from app.api.deps import _resolve_user_for_download

    effective_auth = authorization or (f"Bearer {token}" if token else None)
    user = await _resolve_user_for_download(session, authorization, token)

    service = _get_document_service(session)
    doc = await service.get(document_id, permission_tags=_viewer_tags(user))
    content = await service.file_service.download(doc.cos_object_key)

    filename = quote(doc.name)
    disposition = (
        f"attachment; filename*=UTF-8''{filename}"
        if download
        else f"inline; filename*=UTF-8''{filename}"
    )
    return Response(
        content=content,
        media_type=doc.mime_type or "application/octet-stream",
        headers={"Content-Disposition": disposition},
    )


# ─── 写接口（CurrentAdmin）─────────────────────────────────

@router.post("", response_model=DocumentRead, status_code=201, operation_id="uploadDocument")
async def upload_document(
    admin: CurrentAdmin,
    session: DbSession,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(..., description="上传文件"),
    permission_tags: str | None = Form(
        default=None,
        description='JSON 数组字符串，例如 ["public","hr"]',
    ),
) -> DocumentRead:
    tags: list[str] = []
    if permission_tags:
        try:
            parsed = json.loads(permission_tags)
            if isinstance(parsed, list):
                tags = [str(t) for t in parsed]
        except json.JSONDecodeError:
            pass

    service = _get_document_service(session)
    document = await service.upload(
        file, background_tasks,
        created_by=admin.id, permission_tags=tags,
    )
    return DocumentRead.model_validate(document)


@router.delete("/{document_id}", status_code=204, operation_id="deleteDocument")
async def delete_document(
    _: CurrentAdmin,
    document_id: UUID,
    session: DbSession,
) -> Response:
    service = _get_document_service(session)
    await service.delete(document_id)
    return Response(status_code=204)


@router.post(
    "/{document_id}/retry",
    response_model=DocumentRead,
    operation_id="retryDocument",
)
async def retry_document(
    _: CurrentAdmin,
    document_id: UUID,
    session: DbSession,
    background_tasks: BackgroundTasks,
) -> DocumentRead:
    service = _get_document_service(session)
    doc = await service.retry(document_id, background_tasks)
    return DocumentRead.model_validate(doc)


@router.patch(
    "/{document_id}/permission-tags",
    response_model=DocumentRead,
    operation_id="updateDocumentPermissionTags",
)
async def update_permission_tags(
    _: CurrentAdmin,
    document_id: UUID,
    session: DbSession,
    payload: DocumentPermissionTagsUpdate,
) -> DocumentRead:
    service = _get_document_service(session)
    document = await service.update_permission_tags(
        document_id, payload.permission_tags
    )
    return DocumentRead.model_validate(document)
