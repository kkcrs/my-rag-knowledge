"""应用配置：从根目录 .env 读取环境变量并暴露 settings 单例。"""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[3]

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_name: str = "rag-knowledge"
    log_level: str = "INFO"
    database_url: str = "postgresql+asyncpg://rag:rag@localhost:5432/rag_kb"
    cos_secret_id: str = ""
    cos_secret_key: str = ""
    cos_region: str = "ap-guangzhou"
    cos_bucket: str = ""
    cors_origins: str = "http://localhost:5173"
    # ==== Embedding (DashScope OpenAI 兼容协议) ====
    embedding_base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    embedding_api_key: str = ""
    embedding_model: str = "text-embedding-v3"
    # 维度需与 alembic 迁移中 Vector(N) 保持一致；改维度需要重建表
    embedding_dim: int = 1024
    embedding_batch_size: int = 10

    # ==== 文档上传与切分 ====
    upload_max_size_mb: int = 50
    chunk_size: int = 600
    chunk_overlap: int = 60

    # ==== Chat 模型（DashScope OpenAI 兼容协议） ====
    # 默认与 embedding同base_url
    chat_base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    chat_api_key: str = ""
    chat_model: str = "qwen-plus"
    # 相同输入固定采样种子，降低路由、生成和校验结果漂移。
    chat_seed: int = 42

    # ===== 检索与问答 =====
    # 检索 Top-K：交给 LLM 的候选 chunk 数量
    retrieval_top_k: int = 5
    # 拒答阈值：cosine similarity (= 1 - cosine_distance) 的下限
    # Top-K 中最高分仍低于此值，直接拒答，不调 LLM
    retrieval_min_score: float = 0.6
    # 多轮窗口：load_context 节点取最近多少轮塞进 prompt
    chat_history_window: int = 5
    # ===== query优化 =====
    # 关掉后route_query节点强制走original，方便对比有/无路由的效果
    query_route_enabled: bool = True
    # Multi_Query 策略生成的子查询数量，过大会增加embedding成本
    query_multi_query_count: int = 3

    # ===== 混合检索 =====
    # 每路（向量/关键词) 召回数量，设计文档建议候选20-50
    # 取20兼顾召回率与RRF融合开销
    retrieval_recalltop_k: int = 20
    # RRF平滑常数，业界一般用60，越小越偏向高排名条目
    rrf_k: int = 60

    # ===== Agentic RAG =====
    # 关掉后图退化为单轮检索，作为单轮vs agent 循环的对比开关
    agent_loop_enabled: bool = True
    # 最大检索轮次（含首轮）。LLM决策最多触发max_rounds-1次再检索，避免循环调用
    agent_max_rounds: int = 3

    # ===== Reranker (DashScope qwen3-rerank, 第 8 章) =====
    # 关掉后 rerank 节点直接透传，作为有/无精排的对比开关
    rerank_enabled: bool = True
    # DashScope rerank 端点，不是标准 OpenAI API
    rerank_base_url: str = (
        "https://dashscope.aliyuncs.com/compatible-api/v1/reranks"
    )

    rerank_model: str = "qwen3-rerank"
    # 留空时复用 chat_api_key (同一份 DashScope key，避免重复配置)
    rerank_api_key: str = ""
    # rerank Top1 相关度阈值；低于此值视为“上下文不足”由 judge_context 触发拒答
    # qwen3-rerank 输出 relevance_score ∈ [0, 1], 0.3 是经验值
    rerank_min_score: float = 0.3
    # 请求超时 (秒)，rerank 是同步调用主链路，超时要短一点避免拖慢回答
    rerank_timeout: float = 8.0

    # ===== 答案校验 (第 8 章) =====
    # 关掉后跳过 verify_answer 调用，方便对比有/无引用支撑校验的效果
    # ===== LangSmith 可观测性 =====
    langsmith_tracing: bool = False
    langsmith_api_key: str = ""
    langsmith_project: str = "rag-knowledge-base"
    langsmith_endpoint: str = "https://api.smith.langchain.com"
    langsmith_run_url_prefix: str = ""

    verify_answer_enabled: bool = True

    @property
    def effective_rerank_api_key(self) -> str:
        return self.rerank_api_key or self.chat_api_key

    @property
    def observability_enabled(self) -> bool:
        """LangSmith 实际生效条件：开关打开 + key 已配置。"""
        return bool(self.langsmith_tracing and self.langsmith_api_key)

    @property
    def cos_configured(self) -> bool:
        return all((self.cos_secret_id, self.cos_secret_key, self.cos_region, self.cos_bucket))

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()

settings = get_settings()
