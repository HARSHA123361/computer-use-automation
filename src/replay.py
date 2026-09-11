from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Callable, Dict, Optional

from .browser import BrowserSession
from .guardrails import GuardrailsEngine, PolicyViolation
from .logger import RunLogger
from .schema import (
    ActionType,
    CapabilityArtifact,
    EscalationRequest,
    EscalationStatus,
    RiskLevel,
    RunOutcomeType,
    RunResult,
    StepAction,
    StepResult,
)

KNOWN_ERROR_TEXTS = [
    "no member found",
    "record not found",
    "not found",
    "invalid",
    "error",
    "permission denied",
    "access denied",
    "session expired",
    "timeout",
    "unavailable",
]

RECOVERABLE_TEXTS = [
    "loading",
    "please wait",
    "processing",
]


class ReplayEngine:
    def __init__(
        self,
        browser: BrowserSession,
        guardrails: GuardrailsEngine,
        logger: RunLogger,
        on_escalation: Optional[Callable[[EscalationRequest], Optional[EscalationRequest]]] = None,
    ):
        self.browser = browser
        self.guardrails = guardrails
        self.logger = logger
        self.on_escalation = on_escalation

    def _resolve_value(self, value: Optional[str], param_ref: Optional[str], inputs: Dict[str, Any]) -> Optional[str]:
        if param_ref:
            resolved = inputs.get(param_ref)
            if resolved is None:
                raise ValueError(f"Required input parameter '{param_ref}' was not provided.")
            return str(resolved)
        return value

    def _check_page_for_errors(self) -> Optional[str]:
        page_text = self.browser.get_page_text().lower()
        for phrase in KNOWN_ERROR_TEXTS:
            if phrase in page_text:
                return phrase
        return None

    def _check_recoverable(self) -> bool:
        page_text = self.browser.get_page_text().lower()
        for phrase in RECOVERABLE_TEXTS:
            if phrase in page_text:
                return True
        return False

    def _classify_business_outcome(self, artifact: CapabilityArtifact, page_text: str) -> Optional[str]:
        lower = page_text.lower()
        for outcome in artifact.known_business_outcomes:
            if outcome.detection.lower() in lower:
                return outcome.code
        return None

    def _execute_step(
        self,
        step: StepAction,
        step_index: int,
        inputs: Dict[str, Any],
        outputs: Dict[str, Any],
    ) -> StepResult:
        action = step.action
        description = step.description or str(action)
        value = self._resolve_value(step.value, step.param_ref, inputs)

        try:
            self.guardrails.check_action(step)

            if action == ActionType.navigate:
                url = value or ""
                self.guardrails.check_url(url)
                self.browser.navigate(url, timeout_ms=step.timeout_ms)
                screenshot_path = self.browser.take_screenshot(f"replay_step{step_index}_navigate")
                self.logger.step(step_index, "navigate", description, True, url=url)
                return StepResult(step_index=step_index, action="navigate", description=description, success=True, screenshot_path=screenshot_path)

            elif action == ActionType.click:
                self.browser.click(step.locator, timeout_ms=step.timeout_ms)
                screenshot_path = self.browser.take_screenshot(f"replay_step{step_index}_click")
                self.logger.step(step_index, "click", description, True)
                return StepResult(step_index=step_index, action="click", description=description, success=True, screenshot_path=screenshot_path)

            elif action == ActionType.type_text:
                text = value or ""
                self.browser.type_text(step.locator, text, timeout_ms=step.timeout_ms)
                self.logger.step(step_index, "type_text", description, True)
                return StepResult(step_index=step_index, action="type_text", description=description, success=True)

            elif action == ActionType.select:
                self.browser.select_option(step.locator, value or "", timeout_ms=step.timeout_ms)
                self.logger.step(step_index, "select", description, True)
                return StepResult(step_index=step_index, action="select", description=description, success=True)

            elif action == ActionType.wait_for:
                self.browser.wait_for(step.locator, timeout_ms=step.timeout_ms)
                self.logger.step(step_index, "wait_for", description, True)
                return StepResult(step_index=step_index, action="wait_for", description=description, success=True)

            elif action == ActionType.extract:
                extracted = self.browser.extract_text(step.locator, timeout_ms=step.timeout_ms)
                field_name = step.value or "extracted"
                outputs[field_name] = extracted
                self.logger.step(step_index, "extract", description, True, field_name=field_name, value=extracted)
                return StepResult(step_index=step_index, action="extract", description=description, success=True, extracted_value=extracted)

            elif action == ActionType.assert_checkpoint:
                if step.locator:
                    ok, actual = self.browser.check_text_present(
                        step.locator, step.checkpoint_after.expected_text if step.checkpoint_after else None, timeout_ms=step.timeout_ms
                    )
                    if not ok:
                        screenshot_path = self.browser.take_screenshot(f"replay_step{step_index}_assert_fail")
                        self.logger.error(f"Checkpoint failed at step {step_index}. Expected presence of '{step.checkpoint_after}', got '{actual}'")
                        return StepResult(step_index=step_index, action="assert_checkpoint", description=description, success=False, error=f"Expected '{step.checkpoint_after}', observed '{actual}'", screenshot_path=screenshot_path)
                self.logger.step(step_index, "assert_checkpoint", description, True)
                return StepResult(step_index=step_index, action="assert_checkpoint", description=description, success=True)

            elif action == ActionType.screenshot:
                screenshot_path = self.browser.take_screenshot(f"replay_step{step_index}_snapshot")
                self.logger.step(step_index, "screenshot", description, True, screenshot_path=screenshot_path)
                return StepResult(step_index=step_index, action="screenshot", description=description, success=True, screenshot_path=screenshot_path)

            else:
                return StepResult(step_index=step_index, action=str(action), description=description, success=False, error=f"Unknown action type: {action}")

        except PolicyViolation as e:
            screenshot_path = self.browser.take_screenshot(f"replay_step{step_index}_policy")
            self.logger.error(f"Policy violation at step {step_index}: {e}")
            return StepResult(step_index=step_index, action=str(action), description=description, success=False, error=f"Policy violation: {e}", screenshot_path=screenshot_path)

        except Exception as e:
            screenshot_path = self.browser.take_screenshot(f"replay_step{step_index}_fail")
            self.logger.error(f"Step {step_index} failed: {e}", screenshot_path=screenshot_path)
            return StepResult(step_index=step_index, action=str(action), description=description, success=False, error=str(e), screenshot_path=screenshot_path)

    def run(
        self,
        artifact: CapabilityArtifact,
        inputs: Dict[str, Any],
        goal: str = "",
    ) -> RunResult:
        run_id = str(uuid.uuid4())
        self.logger.info(f"Replay starting. Artifact: {artifact.name} v{artifact.version}. Inputs: {list(inputs.keys())}")

        result = RunResult(
            run_id=run_id,
            artifact_id=artifact.id,
            artifact_version=artifact.version,
            outcome=RunOutcomeType.hard_failure,
            inputs=self.guardrails.redact_dict(inputs),
            total_steps=len(artifact.steps),
        )

        outputs: Dict[str, Any] = {}

        for step_index, step in enumerate(artifact.steps, start=1):
            step_result = self._execute_step(step, step_index, inputs, outputs)
            result.step_results.append(step_result)
            result.steps_completed = step_index

            if not step_result.success:
                page_text = self.browser.get_page_text()

                business_code = self._classify_business_outcome(artifact, page_text)
                if business_code:
                    self.logger.info(f"Known business outcome detected: {business_code}")
                    result.outcome = RunOutcomeType.business_outcome
                    result.business_outcome_code = business_code
                    result.outputs = outputs
                    result.failed_step = step_index
                    result.finished_at = datetime.now(timezone.utc).isoformat()
                    return result

                if self._check_recoverable():
                    self.logger.warn(f"Recoverable condition at step {step_index}. Retrying once.")
                    import time
                    time.sleep(2)
                    step_result2 = self._execute_step(step, step_index, inputs, outputs)
                    if step_result2.success:
                        result.step_results[-1] = step_result2
                        continue

                escalation = self._maybe_escalate(artifact, result, step_index, goal, step_result.error or "Step failed")
                if escalation and escalation.status == EscalationStatus.resolved:
                    self.logger.info(f"Escalation {escalation.id} resolved by human. Continuing.")
                    result.escalation_id = escalation.id
                    continue

                result.outcome = RunOutcomeType.hard_failure
                result.failed_step = step_index
                result.error_detail = step_result.error
                result.expected_state = step.description
                result.observed_state = self.browser.get_page_text()[:500]
                result.finished_at = datetime.now(timezone.utc).isoformat()
                self.logger.error(f"Hard failure at step {step_index}: {step_result.error}")
                return result

            if step.checkpoint_after:
                chk = step.checkpoint_after
                ok, actual = self.browser.check_text_present(chk.locator, chk.expected_text)
                if not ok:
                    result.outcome = RunOutcomeType.hard_failure
                    result.failed_step = step_index
                    result.error_detail = f"Checkpoint failed: expected '{chk.expected_text}', got '{actual}'"
                    result.expected_state = chk.description
                    result.observed_state = actual
                    result.finished_at = datetime.now(timezone.utc).isoformat()
                    self.logger.error(f"Checkpoint failed at step {step_index}.")
                    return result

        chk = artifact.success_checkpoint
        ok, actual = self.browser.check_text_present(chk.locator, chk.expected_text)
        url_ok = True
        if chk.expected_url_contains:
            url_ok = self.browser.check_url_contains(chk.expected_url_contains)

        if not ok or not url_ok:
            result.outcome = RunOutcomeType.hard_failure
            result.error_detail = f"Final checkpoint failed: expected '{chk.expected_text}' but got '{actual}'"
            result.expected_state = chk.description
            result.observed_state = actual
            result.finished_at = datetime.now(timezone.utc).isoformat()
            self.logger.error(f"Final success checkpoint failed.")
            return result

        screenshot_path = self.browser.take_screenshot("replay_success")
        result.outcome = RunOutcomeType.success
        result.outputs = outputs
        result.finished_at = datetime.now(timezone.utc).isoformat()
        self.logger.info(f"Replay completed successfully. Outputs: {list(outputs.keys())}")
        return result

    def _maybe_escalate(
        self,
        artifact: CapabilityArtifact,
        run_result: RunResult,
        step_index: int,
        goal: str,
        reason: str,
    ) -> Optional[EscalationRequest]:
        if self.on_escalation is None:
            return None

        screenshot_path = self.browser.take_screenshot(f"escalation_step{step_index}")
        escalation = EscalationRequest(
            run_id=run_result.run_id,
            artifact_id=artifact.id,
            capability_name=artifact.name,
            goal=goal or artifact.description,
            current_step=step_index,
            reason=reason,
            screenshot_path=screenshot_path,
            current_url=self.browser.current_url(),
        )
        self.logger.escalation(escalation.id, reason)
        resolved = self.on_escalation(escalation)
        return resolved
