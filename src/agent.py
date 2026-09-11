from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from openai import OpenAI

from .browser import BrowserSession
from .guardrails import GuardrailsEngine, PolicyViolation
from .logger import RunLogger
from .schema import (
    ActionType,
    ArtifactStatus,
    BusinessOutcome,
    CapabilityArtifact,
    Checkpoint,
    InputParam,
    Locator,
    LocatorStrategy,
    OutputField,
    RiskLevel,
    StepAction,
)

MAX_STEPS = 25
MAX_CONSECUTIVE_ERRORS = 3

SYSTEM_PROMPT = """You are a browser automation agent. Your job is to accomplish a goal on a web application by observing the current page and deciding what action to take next.

You will receive the current page's accessibility snapshot and visible text. Based on what you see, you must output a JSON action.

Available actions:
- navigate: go to a URL  {"action": "navigate", "url": "..."}
- click: click an element  {"action": "click", "locator": {"strategy": "...", "value": "..."}, "description": "..."}
- type_text: fill in a field  {"action": "type_text", "locator": {"strategy": "...", "value": "..."}, "text": "...", "description": "..."}
- extract: read a value from the page  {"action": "extract", "locator": {"strategy": "...", "value": "..."}, "field_name": "...", "description": "..."}
- wait_for: wait for element to appear  {"action": "wait_for", "locator": {"strategy": "...", "value": "..."}, "description": "..."}
- done: goal is complete  {"action": "done", "summary": "...", "extracted": {...}}
- stuck: cannot proceed  {"action": "stuck", "reason": "..."}

Locator strategies available: css, xpath, text, label, role, accessibility
For legacy pages with no IDs, prefer xpath or text strategies.

IMPORTANT rules:
- Only act on what you can see. Do not guess elements that are not in the snapshot.
- Prefer text-based locators for legacy pages with no semantic markup.
- When filling forms, use the input element's position relative to its label text.
- Always extract the data the goal asks for before calling done.
- If you are on a login page and need credentials, use username=staff and password=demo1234.
- Output ONLY a JSON object. No explanation, no markdown, just the JSON.
"""


class DiscoveryAgent:
    def __init__(
        self,
        openai_api_key: str,
        browser: BrowserSession,
        guardrails: GuardrailsEngine,
        logger: RunLogger,
        model: str = "gpt-4o",
    ):
        self.client = OpenAI(api_key=openai_api_key)
        self.browser = browser
        self.guardrails = guardrails
        self.logger = logger
        self.model = model
        self._steps_taken: List[Dict[str, Any]] = []
        self._extracted_data: Dict[str, Any] = {}

    def _observe(self) -> str:
        url = self.browser.current_url()
        page_text = self.browser.get_page_text()[:3000]
        snapshot = self.browser.get_accessibility_snapshot()
        snapshot_str = json.dumps(snapshot, indent=1)[:3000]
        return (
            f"Current URL: {url}\n\n"
            f"Page text (truncated):\n{page_text}\n\n"
            f"Accessibility snapshot (truncated):\n{snapshot_str}"
        )

    def _decide(self, goal: str, observation: str, history: List[Dict]) -> Dict[str, Any]:
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
        ]
        for h in history[-6:]:
            messages.append({"role": "user", "content": h["observation"]})
            messages.append({"role": "assistant", "content": json.dumps(h["action"])})

        messages.append({
            "role": "user",
            "content": f"Goal: {goal}\n\nCurrent state:\n{observation}\n\nWhat is your next action?"
        })

        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=0.0,
            max_tokens=512,
            response_format={"type": "json_object"},
        )
        raw = response.choices[0].message.content
        return json.loads(raw)

    def _execute_action(self, action_dict: Dict[str, Any], step_index: int) -> bool:
        action = action_dict.get("action")
        description = action_dict.get("description", action)

        self.logger.agent_reasoning(step_index, json.dumps(action_dict))

        try:
            if action == "navigate":
                url = action_dict["url"]
                self.guardrails.check_url(url)
                self.browser.navigate(url)
                screenshot_path = self.browser.take_screenshot(f"step{step_index}_navigate")
                self._record_step(step_index, "navigate", description, url=url, screenshot_path=screenshot_path)
                self.logger.step(step_index, "navigate", description, True, url=url)
                return True

            elif action == "click":
                loc = self._parse_locator(action_dict["locator"])
                step = StepAction(action=ActionType.click, locator=loc, description=description, risk=RiskLevel.safe)
                self.guardrails.check_action(step)
                self.browser.click(loc)
                screenshot_path = self.browser.take_screenshot(f"step{step_index}_click")
                self._record_step(step_index, "click", description, locator=action_dict["locator"], screenshot_path=screenshot_path)
                self.logger.step(step_index, "click", description, True)
                return True

            elif action == "type_text":
                loc = self._parse_locator(action_dict["locator"])
                text = action_dict.get("text", "")
                step = StepAction(action=ActionType.type_text, locator=loc, description=description, risk=RiskLevel.safe)
                self.guardrails.check_action(step)
                self.browser.type_text(loc, text)
                safe_text = "[REDACTED]" if not self.guardrails.is_safe_to_record(text) else text
                self._record_step(step_index, "type_text", description, locator=action_dict["locator"], text=safe_text)
                self.logger.step(step_index, "type_text", description, True, text=safe_text)
                return True

            elif action == "extract":
                loc = self._parse_locator(action_dict["locator"])
                field_name = action_dict.get("field_name", "extracted")
                value = self.browser.extract_text(loc)
                self._extracted_data[field_name] = value
                self._record_step(step_index, "extract", description, locator=action_dict["locator"], field_name=field_name)
                self.logger.step(step_index, "extract", description, True, field_name=field_name, value=value)
                return True

            elif action == "wait_for":
                loc = self._parse_locator(action_dict["locator"])
                self.browser.wait_for(loc, timeout_ms=8000)
                self._record_step(step_index, "wait_for", description, locator=action_dict["locator"])
                self.logger.step(step_index, "wait_for", description, True)
                return True

            elif action in ("done", "stuck"):
                return True

            else:
                self.logger.warn(f"Unknown action '{action}' at step {step_index}")
                return False

        except PolicyViolation as e:
            self.logger.error(f"Policy violation at step {step_index}: {e}")
            raise
        except Exception as e:
            screenshot_path = self.browser.take_screenshot(f"step{step_index}_error")
            self.logger.error(f"Action failed at step {step_index}: {e}", screenshot_path=screenshot_path)
            raise

    def _parse_locator(self, loc_dict: Dict[str, Any]) -> Locator:
        strategy = loc_dict.get("strategy", "xpath")
        value = loc_dict.get("value", "")
        fallbacks_raw = loc_dict.get("fallbacks", [])
        fallbacks = [self._parse_locator(f) for f in fallbacks_raw]
        description = loc_dict.get("description", "")
        return Locator(strategy=strategy, value=value, fallbacks=fallbacks, description=description)

    def _record_step(self, index: int, action: str, description: str, **kwargs) -> None:
        self._steps_taken.append({
            "step_index": index,
            "action": action,
            "description": description,
            **kwargs,
        })

    def run(self, goal: str, target_url: str) -> Dict[str, Any]:
        self.logger.info(f"Discovery agent starting. Goal: {goal}. Target: {target_url}")
        self.guardrails.check_url(target_url)
        self.browser.navigate(target_url)

        history: List[Dict] = []
        consecutive_errors = 0

        for step_index in range(1, MAX_STEPS + 1):
            observation = self._observe()
            action_dict = self._decide(goal, observation, history)

            history.append({"observation": observation, "action": action_dict})

            action = action_dict.get("action")

            if action == "done":
                summary = action_dict.get("summary", "")
                extracted = action_dict.get("extracted", {})
                self._extracted_data.update(extracted)
                self.logger.info(f"Agent completed goal at step {step_index}. Summary: {summary}")
                screenshot_path = self.browser.take_screenshot("final_success")
                return {
                    "status": "success",
                    "steps_taken": self._steps_taken,
                    "extracted": self._extracted_data,
                    "summary": summary,
                    "final_url": self.browser.current_url(),
                    "final_screenshot": screenshot_path,
                    "total_steps": step_index,
                }

            if action == "stuck":
                reason = action_dict.get("reason", "Unknown reason")
                self.logger.warn(f"Agent stuck at step {step_index}: {reason}")
                screenshot_path = self.browser.take_screenshot("stuck")
                return {
                    "status": "stuck",
                    "reason": reason,
                    "steps_taken": self._steps_taken,
                    "extracted": self._extracted_data,
                    "final_url": self.browser.current_url(),
                    "final_screenshot": screenshot_path,
                    "total_steps": step_index,
                }

            try:
                self._execute_action(action_dict, step_index)
                consecutive_errors = 0
            except PolicyViolation as e:
                self.logger.error(f"Policy violation — aborting: {e}")
                return {
                    "status": "policy_violation",
                    "reason": str(e),
                    "steps_taken": self._steps_taken,
                    "extracted": self._extracted_data,
                    "total_steps": step_index,
                }
            except Exception as e:
                consecutive_errors += 1
                self.logger.error(f"Step {step_index} error ({consecutive_errors}/{MAX_CONSECUTIVE_ERRORS}): {e}")
                if consecutive_errors >= MAX_CONSECUTIVE_ERRORS:
                    screenshot_path = self.browser.take_screenshot("max_errors")
                    return {
                        "status": "stuck",
                        "reason": f"Too many consecutive errors: {e}",
                        "steps_taken": self._steps_taken,
                        "extracted": self._extracted_data,
                        "final_url": self.browser.current_url(),
                        "final_screenshot": screenshot_path,
                        "total_steps": step_index,
                    }

        self.logger.warn("Reached max steps without completing goal.")
        screenshot_path = self.browser.take_screenshot("max_steps")
        return {
            "status": "stuck",
            "reason": "Reached maximum step limit.",
            "steps_taken": self._steps_taken,
            "extracted": self._extracted_data,
            "final_url": self.browser.current_url(),
            "final_screenshot": screenshot_path,
            "total_steps": MAX_STEPS,
        }

    def build_artifact(
        self,
        run_result: Dict[str, Any],
        goal: str,
        target_url: str,
        capability_name: str,
        input_params: List[InputParam],
        output_fields: List[OutputField],
        success_checkpoint: Checkpoint,
        known_outcomes: Optional[List[BusinessOutcome]] = None,
    ) -> CapabilityArtifact:
        steps = []
        for raw in run_result.get("steps_taken", []):
            action_str = raw["action"]
            description = raw.get("description", "")
            risk = RiskLevel.safe

            if action_str in ("submit", "transfer", "confirm"):
                risk = RiskLevel.irreversible

            locator = None
            if "locator" in raw:
                loc_data = raw["locator"]
                if isinstance(loc_data, dict):
                    locator = self._parse_locator(loc_data)

            param_ref = None
            text = raw.get("text")
            if text and text.startswith("{{") and text.endswith("}}"):
                param_ref = text[2:-2].strip()
                text = None

            value = raw.get("url") or text

            step = StepAction(
                action=ActionType(action_str),
                locator=locator,
                value=value,
                param_ref=param_ref,
                description=description,
                risk=risk,
            )
            steps.append(step)

        artifact = CapabilityArtifact(
            name=capability_name,
            description=goal,
            target_url=target_url,
            input_params=input_params,
            output_fields=output_fields,
            steps=steps,
            success_checkpoint=success_checkpoint,
            known_business_outcomes=known_outcomes or [],
            status=ArtifactStatus.draft,
        )
        return artifact
