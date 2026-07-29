from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


EvaluationStatusValue = Literal["running", "completed", "failed"]

BadCaseCategoryValue = Literal[
    "document_parse_failed",
    "chunk_split_bad",
    "embedding_recall_miss",
    "keyword_recall_miss",
    "rrf_fusion_error",
    "rerank_order_error",
    "context_judge_too_loose",
    "context_judge_too_strict",
    "prompt_constraint_weak",
    "generation_off_context",
    "citation_parse_failed",
    "permission_filter_error",
    "other",
]


class EvaluationRunCreate(BaseModel):
    name: str = Field(min_length=1, max_length=256)
    dataset_name: str = Field(min_length=1, max_length=128)


class EvaluationRunRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    dataset_name: str
    dataset_size: int
    status: EvaluationStatusValue
    progress_total: int
    progress_completed: int
    progress_failed: int

    faithfulness: float | None = None
    answer_relevancy: float | None = None
    context_precision: float | None = None
    context_recall: float | None = None
    citation_hit_rate: float | None = None
    refusal_accuracy: float | None = None

    avg_latency_ms: float | None = None
    avg_first_token_latency_ms: float | None = None

    error_message: str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    created_at: datetime


class EvaluationRunListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    dataset_name: str
    dataset_size: int
    status: EvaluationStatusValue
    progress_total: int
    progress_completed: int
    progress_failed: int
    faithfulness: float | None = None
    answer_relevancy: float | None = None
    context_precision: float | None = None
    context_recall: float | None = None
    citation_hit_rate: float | None = None
    refusal_accuracy: float | None = None
    avg_latency_ms: float | None = None
    avg_first_token_latency_ms: float | None = None
    created_at: datetime


class EvaluationRunPage(BaseModel):
    items: list[EvaluationRunListItem]
    total: int
    page: int
    page_size: int


class EvaluationItemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    run_id: UUID
    case_id: str
    question: str
    expected_answer: str
    expected_document_names: list[str] = Field(default_factory=list)
    expected_keywords: list[str] = Field(default_factory=list)
    should_refuse: bool
    tags: list[str] = Field(default_factory=list)

    actual_answer: str
    actual_refused: bool
    citations: list[dict] = Field(default_factory=list)
    retrieved_chunks_meta: list[dict] = Field(default_factory=list)
    query_route: dict | None = None
    agent_steps: list[dict] | None = None
    verify_result: dict | None = None
    trace_id: str | None = None
    latency_ms: int
    first_token_latency_ms: int | None = None
    error_message: str | None = None

    faithfulness: float | None = None
    answer_relevancy: float | None = None
    context_precision: float | None = None
    context_recall: float | None = None
    citation_hit: bool | None = None
    refusal_correct: bool

    is_bad_case: bool
    bad_case_category: BadCaseCategoryValue | None = None
    bad_case_note: str | None = None
    created_at: datetime


class EvaluationItemPage(BaseModel):
    items: list[EvaluationItemRead]
    total: int
    page: int
    page_size: int


class EvaluationItemUpdate(BaseModel):
    bad_case_category: BadCaseCategoryValue | None = None
    bad_case_note: str | None = None
    is_bad_case: bool | None = None


class DatasetInfo(BaseModel):
    name: str
    size: int


class DatasetListResponse(BaseModel):
    items: list[DatasetInfo]
