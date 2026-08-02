import hashlib
import json
from dataclasses import dataclass
from functools import lru_cache

from redisvl.extensions.cache.llm import SemanticCache
from redisvl.query.filter import Tag
from redisvl.utils.vectorize import CustomVectorizer

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

CACHE_NAME = "rag_semantic_cache"
SCOPE_FIELD = "permission_scope"


@lru_cache(maxsize=1024)
def _scope_key(permission_tags: tuple[str, ...]) -> str:
    """把权限列表序列化成排序后 SHA-256，确保集合相同时匹配。"""
    canonical = "|".join(sorted(set(permission_tags)))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _stub_embed(_text: str, **__: object) -> list[float]:
    """占位向量器：仅用于索引创建时的维度验证，实际检索通过 vector= 传入。"""
    return [0.0] * settings.embedding_dim


@dataclass(frozen=True)
class CachedAnswer:
    answer: str
    citations: list[dict]
    cached_question: str


class SemanticCacheService:
    def __init__(self) -> None:
        self._cache = SemanticCache(
            name=CACHE_NAME,
            redis_url=settings.redis_url,
            distance_threshold=1.0 - settings.semantic_cache_min_similarity,
            ttl=settings.semantic_cache_ttl_seconds,
            vectorizer=CustomVectorizer(_stub_embed),
            filterable_fields=[{"name": SCOPE_FIELD, "type": "tag"}],
            overwrite=False,
        )

    async def lookup(
        self,
        query_embedding: list[float],
        permission_scope: list[str],
    ) -> CachedAnswer | None:
        """Redis KNN 召回 + Tag 过滤。"""
        scope = _scope_key(tuple(permission_scope))
        try:
            hits = await self._cache.acheck(
                prompt="",  # 向量检索不需要 prompt 文本
                vector=query_embedding,
                filter_expression=Tag(SCOPE_FIELD) == scope,
                num_results=1,
                return_fields=["prompt", "response", "metadata"],
            )
        except Exception:
            logger.exception("semantic cache lookup failed, treat as miss")
            return None

        if not hits:
            return None

        hit = hits[0]
        metadata = hit.get("metadata") or {}
        if isinstance(metadata, str):
            try:
                metadata = json.loads(metadata)
            except json.JSONDecodeError:
                metadata = {}
        return CachedAnswer(
            answer=hit.get("response", ""),
            citations=metadata.get("citations", []),
            cached_question=hit.get("prompt", ""),
        )

    async def save(
        self,
        *,
        question: str,
        query_embedding: list[float],
        answer: str,
        citations: list[dict],
        permission_scope: list[str],
    ) -> None:
        try:
            await self._cache.astore(
                prompt=question,
                response=answer,
                vector=query_embedding,
                metadata={"citations": citations},
                filters={SCOPE_FIELD: _scope_key(tuple(permission_scope))},
            )
        except Exception:
            logger.exception("semantic cache save failed, skip")


@lru_cache(maxsize=1)
def get_semantic_cache() -> SemanticCacheService:
    return SemanticCacheService()
