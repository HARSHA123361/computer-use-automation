from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Literal, Optional, Union

from pydantic import BaseModel, Field


class ActionType(str, Enum):
    navigate = "navigate"
    click = "click"
    type_text = "type_text"
    select = "select"
    wait_for = "wait_for"
    extract = "extract"
    assert_checkpoint = "assert_checkpoint"
    screenshot = "screenshot"


class LocatorStrategy(str, Enum):
    css = "css"
    xpath = "xpath"
    text = "text"
    label = "label"
    role = "role"
    accessibility = "accessibility"
    coordinates = "coordinates"


class RiskLevel(str, Enum):
    safe = "safe"
    moderate = "moderate"
    irreversible = "irreversible"


class Locator(BaseModel):
    strategy: LocatorStrategy
    value: str
    fallbacks: List["Locator"] = Field(default_factory=list)
    description: str = ""

    model_config = {"use_enum_values": True}


class InputParam(BaseModel):
    name: str
    type: Literal["string", "integer", "number", "boolean"]
    description: str
    required: bool = True
    example: Optional[Any] = None


class OutputField(BaseModel):
    name: str
    type: Literal["string", "integer", "number", "boolean", "object"]
    description: str
    selector: Optional[Locator] = None


class Checkpoint(BaseModel):
    description: str
    locator: Locator
    expected_text: Optional[str] = None
    expected_url_contains: Optional[str] = None


class StepAction(BaseModel):
    action: ActionType
    locator: Optional[Locator] = None
    value: Optional[str] = None
    param_ref: Optional[str] = None
    timeout_ms: int = 5000
    risk: RiskLevel = RiskLevel.safe
    description: str = ""
    checkpoint_after: Optional[Checkpoint] = None

    model_config = {"use_enum_values": True}


class BusinessOutcome(BaseModel):
    code: str
    description: str
    detection: str


class ArtifactStatus(str, Enum):
    draft = "draft"
    approved = "approved"
    deprecated = "deprecated"


class CapabilityArtifact(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    version: str = "1.0.0"
    status: ArtifactStatus = ArtifactStatus.draft
    name: str
    description: str
    target_url: str
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    recorded_by: str = "discovery-agent"

    input_params: List[InputParam]
    output_fields: List[OutputField]

    steps: List[StepAction]

    success_checkpoint: Checkpoint

    known_business_outcomes: List[BusinessOutcome] = Field(default_factory=list)

    model_config = {"use_enum_values": True}


class RunOutcomeType(str, Enum):
    success = "success"
    business_outcome = "business_outcome"
    recoverable_error = "recoverable_error"
    hard_failure = "hard_failure"
    escalated = "escalated"


class StepResult(BaseModel):
    step_index: int
    action: str
    description: str
    success: bool
    error: Optional[str] = None
    screenshot_path: Optional[str] = None
    extracted_value: Optional[str] = None
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class RunResult(BaseModel):
    run_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    artifact_id: str
    artifact_version: str
    outcome: RunOutcomeType
    inputs: Dict[str, Any]
    outputs: Dict[str, Any] = Field(default_factory=dict)
    business_outcome_code: Optional[str] = None
    steps_completed: int = 0
    total_steps: int = 0
    failed_step: Optional[int] = None
    error_detail: Optional[str] = None
    expected_state: Optional[str] = None
    observed_state: Optional[str] = None
    step_results: List[StepResult] = Field(default_factory=list)
    escalation_id: Optional[str] = None
    started_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    finished_at: Optional[str] = None

    model_config = {"use_enum_values": True}


class EscalationStatus(str, Enum):
    pending = "pending"
    human_in_control = "human_in_control"
    resolved = "resolved"
    abandoned = "abandoned"


class EscalationRequest(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    run_id: str
    artifact_id: str
    capability_name: str
    goal: str
    current_step: int
    reason: str
    screenshot_path: Optional[str] = None
    current_url: Optional[str] = None
    status: EscalationStatus = EscalationStatus.pending
    human_actions: List[Dict[str, Any]] = Field(default_factory=list)
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    resolved_at: Optional[str] = None

    model_config = {"use_enum_values": True}
