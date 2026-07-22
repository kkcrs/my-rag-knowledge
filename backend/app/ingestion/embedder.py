from app.core.config import settings
from app.core.exceptions import ConfigurationError

_embeddings: None = None


def get_embeddings():
    """延迟初始化 Embeddings 实例（langchain_openai 导入较慢，非首次请求不阻塞）。"""
    global _embeddings
    if _embeddings is not None:
        return _embeddings

    from langchain_core.embeddings import Embeddings
    from langchain_openai import OpenAIEmbeddings

    if not settings.embedding_api_key:
        raise ConfigurationError("Embedding API key 未配置，请在 .env 设置 EMBEDDING_API_KEY")

    _embeddings = OpenAIEmbeddings(
        model=settings.embedding_model,
        api_key=settings.embeddings_api_key,
        base_url=settings.embedding_base_url,
        dimensions=settings.embedding_dim,
        chunk_size=settings.embedding_batch_size,
        check_embedding_ctx_length=False,
    )
    return _embeddings