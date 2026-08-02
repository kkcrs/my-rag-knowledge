from typing import Annotated
from uuid import UUID

from fastapi import Depends, Header
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import PermissionError, UnauthorizedError
from app.core.rate_limiter import get_rate_limiter
from app.core.security import decode_access_token
from app.db.models import User, UserStatus
from app.db.repositories.user_repo import UserRepository
from app.db.session import get_session
from app.services.permission_service import is_admin

DbSession = Annotated[AsyncSession, Depends(get_session)]


def _parse_bearer_token(authorization: str | None) -> str:
    if not authorization:
        raise UnauthorizedError("请先登录")
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise UnauthorizedError("无效的访问凭证")
    return token


async def get_current_user(
    session: Annotated[AsyncSession, Depends(get_session)],
    authorization: Annotated[str | None, Header(alias="Authorization")] = None,
) -> User:
    """解析 Bearer token，查表拿到 User。"""
    token = _parse_bearer_token(authorization)
    subject = decode_access_token(token)

    try:
        user_id = UUID(subject)
    except (ValueError, TypeError) as exc:
        raise UnauthorizedError("无效的访问凭证") from exc

    user = await UserRepository(session).get_by_id(user_id)
    if user is None:
        raise UnauthorizedError("用户不存在或已被删除")
    if user.status != UserStatus.ACTIVE:
        raise UnauthorizedError("账号已被禁用")
    return user


async def get_current_admin(
    user: Annotated[User, Depends(get_current_user)],
) -> User:
    if not is_admin(user):
        raise PermissionError("仅管理员可访问")
    return user


async def _resolve_user_for_download(
    session: AsyncSession,
    authorization: str | None,
    token: str,
) -> User:
    """从 header 或 query token 解析用户，供 download 端点使用。"""
    effective = authorization or (f"Bearer {token}" if token else None)
    if not effective:
        raise UnauthorizedError("请先登录")
    raw_token = _parse_bearer_token(effective)
    subject = decode_access_token(raw_token)
    try:
        user_id = UUID(subject)
    except (ValueError, TypeError) as exc:
        raise UnauthorizedError("无效的访问凭证") from exc
    user = await UserRepository(session).get_by_id(user_id)
    if user is None or user.status != UserStatus.ACTIVE:
        raise UnauthorizedError("用户不存在或已被禁用")
    return user

CurrentUser = Annotated[User, Depends(get_current_user)]
CurrentAdmin = Annotated[User, Depends(get_current_admin)]
CurrentViewer = CurrentUser
async def enforce_rate_limit(
    user: Annotated[User, Depends(get_current_user)],
) -> None:
    if not settings.rate_limit_enabled:
        return
    await get_rate_limiter().check(f"user:{user.id}")


RateLimited = Annotated[None, Depends(enforce_rate_limit)]
