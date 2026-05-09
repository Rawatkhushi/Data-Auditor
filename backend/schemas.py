
from pydantic import BaseModel
from typing import Any, Optional


class DimensionScores(BaseModel):
    completeness: float
    validity: float
    consistency: float
    uniqueness: float
    anomaly: float


class ScoreResult(BaseModel):
    score: float
    grade: str
    verdict: str
    total_deduction: float
    dimension_scores: DimensionScores
    deductions: list[dict[str, Any]]


class IssueSummary(BaseModel):
    total: int
    by_severity: dict[str, int]
    by_source: dict[str, int]
    by_type: dict[str, int]


class AuditResponse(BaseModel):
    filename: str
    rows: int
    columns: int
    column_names: list[str]
    schema: dict[str, str]
    profile: list[dict[str, Any]]
    issues: list[dict[str, Any]]
    issue_stats: IssueSummary
    anomalies: dict[str, Any]
    score: ScoreResult
    ai_report: Optional[str] = None