"""
AetherTest Pydantic Data Models
All core data structures used across the platform.
"""

from __future__ import annotations
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field, field_validator
import uuid
from datetime import datetime, timezone


# ── Enums ─────────────────────────────────────────────────────────────────────

class ComponentType(str, Enum):
    API_ENDPOINT = "api_endpoint"
    UI_PAGE = "ui_page"
    SERVICE = "service"
    DATABASE = "database"


class AssignmentStatus(str, Enum):
    PENDING = "pending"
    DISPATCHED = "dispatched"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMED_OUT = "timed_out"


class ExecutionStatus(str, Enum):
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SELF_HEALING = "self_healing"


class FailureType(str, Enum):
    GENUINE_DEFECT = "genuine_defect"
    ENV_NOISE = "env_noise"
    AUT_CHANGE = "aut_change"


class Priority(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class CoverageTarget(str, Enum):
    FULL = "full"
    SMOKE = "smoke"
    REGRESSION = "regression"


class TriggeringEvent(str, Enum):
    CICD = "cicd"
    MANUAL = "manual"
    SELF_HEAL = "self_heal"


# ── AUT Component Graph ───────────────────────────────────────────────────────

class AUTComponent(BaseModel):
    component_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    component_type: ComponentType
    dependencies: list[str] = Field(default_factory=list)
    api_surface: list[str] = Field(default_factory=list)
    ui_entry_points: list[str] = Field(default_factory=list)
    metadata: dict = Field(default_factory=dict)

    model_config = {"extra": "allow"}


class AUTComponentGraph(BaseModel):
    graph_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    aut_id: str
    version: str
    tenant_id: str
    components: list[AUTComponent]
    analyzed_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    schema_version: str = "1.0"

    model_config = {"extra": "allow"}


# ── Risk Score ────────────────────────────────────────────────────────────────

class RiskScoreRecord(BaseModel):
    component_id: str
    risk_score: float = Field(ge=0.0, le=100.0)
    is_uncharacterized: bool = False
    change_weight: float = Field(default=0.0, ge=0.0, le=1.0)
    defect_weight: float = Field(default=0.0, ge=0.0, le=1.0)
    deployment_weight: float = Field(default=0.0, ge=0.0, le=1.0)
    computed_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    model_config = {"extra": "allow"}


# ── Test Strategy ─────────────────────────────────────────────────────────────

class ComponentCoverage(BaseModel):
    component_id: str
    risk_score: float = Field(ge=0.0, le=100.0)
    priority: Priority
    assigned_agent_types: list[str]
    coverage_target: CoverageTarget

    model_config = {"extra": "allow"}


class TestStrategy(BaseModel):
    strategy_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    tenant_id: str
    aut_id: str
    aut_version: str
    version: int = 1
    created_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    execution_environment: str
    coverage: list[ComponentCoverage]
    estimated_duration_seconds: int
    s3_key: str = ""
    triggering_event: TriggeringEvent = TriggeringEvent.MANUAL

    model_config = {"extra": "allow"}


# ── Execution State ───────────────────────────────────────────────────────────

class AgentAssignment(BaseModel):
    assignment_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    agent_type: str
    agent_id: str
    component_ids: list[str]
    status: AssignmentStatus = AssignmentStatus.PENDING
    dispatched_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    completed_at: Optional[str] = None
    retry_count: int = 0
    result_s3_key: Optional[str] = None

    model_config = {"extra": "allow"}


class ExecutionState(BaseModel):
    execution_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    strategy_id: str
    tenant_id: str
    step_functions_arn: str = ""
    status: ExecutionStatus = ExecutionStatus.RUNNING
    assignments: list[AgentAssignment] = Field(default_factory=list)
    started_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    completed_at: Optional[str] = None
    defect_count: int = 0
    warnings: list[str] = Field(default_factory=list)

    model_config = {"extra": "ignore"}  # unknown fields captured in warnings


# ── Defect Pattern ────────────────────────────────────────────────────────────

class DefectPattern(BaseModel):
    pattern_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    tenant_id: str
    component_id: str
    execution_id: str
    failure_type: FailureType
    failure_evidence_s3_key: str = ""
    risk_score_at_failure: float = Field(ge=0.0, le=100.0)
    consecutive_failure_count: int = 1
    recorded_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    model_config = {"extra": "allow"}
