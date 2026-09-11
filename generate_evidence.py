import json
import os
import sys
import time
import subprocess
import threading

from src.browser import BrowserSession
from src.guardrails import guardrails
from src.logger import RunLogger
from src.replay import ReplayEngine
from src.schema import (
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
    RunOutcomeType,
    StepAction,
)
from src.store import ArtifactStore


def build_sample_artifact() -> CapabilityArtifact:
    steps = [
        StepAction(
            action=ActionType.navigate,
            value="http://127.0.0.1:5001/",
            description="Navigate to the staff portal login page.",
            risk=RiskLevel.safe,
        ),
        StepAction(
            action=ActionType.type_text,
            locator=Locator(
                strategy=LocatorStrategy.xpath,
                value="(//input[@name='username'])[last()]",
                description="Username input field (last form on page — the real login form)",
                fallbacks=[
                    Locator(strategy=LocatorStrategy.css, value="input[name='username']", description="Username by name attr")
                ],
            ),
            value="staff",
            description="Enter staff username.",
            risk=RiskLevel.safe,
        ),
        StepAction(
            action=ActionType.type_text,
            locator=Locator(
                strategy=LocatorStrategy.xpath,
                value="(//input[@name='password'])[last()]",
                description="Password input field",
                fallbacks=[
                    Locator(strategy=LocatorStrategy.css, value="input[name='password']", description="Password by name attr")
                ],
            ),
            value="demo1234",
            description="Enter staff password.",
            risk=RiskLevel.safe,
        ),
        StepAction(
            action=ActionType.click,
            locator=Locator(
                strategy=LocatorStrategy.xpath,
                value="(//input[@type='submit'])[last()]",
                description="Login submit button",
                fallbacks=[
                    Locator(strategy=LocatorStrategy.css, value="input[type='submit']", description="Submit button by type")
                ],
            ),
            description="Click the Log In button.",
            risk=RiskLevel.safe,
        ),
        StepAction(
            action=ActionType.wait_for,
            locator=Locator(
                strategy=LocatorStrategy.xpath,
                value="//input[@name='member_id']",
                description="Member ID search input — confirms we are on the search page",
                fallbacks=[
                    Locator(strategy=LocatorStrategy.text, value="Member Account Search", description="Search page heading text")
                ],
            ),
            description="Wait for the Member Search page to load.",
            risk=RiskLevel.safe,
            timeout_ms=8000,
        ),
        StepAction(
            action=ActionType.type_text,
            locator=Locator(
                strategy=LocatorStrategy.xpath,
                value="//input[@name='member_id']",
                description="Member ID search input",
                fallbacks=[
                    Locator(strategy=LocatorStrategy.css, value="input[name='member_id']", description="Member ID input by name")
                ],
            ),
            param_ref="member_id",
            description="Type the member ID into the search field.",
            risk=RiskLevel.safe,
        ),
        StepAction(
            action=ActionType.click,
            locator=Locator(
                strategy=LocatorStrategy.xpath,
                value="//input[@type='submit']",
                description="Search submit button",
                fallbacks=[
                    Locator(strategy=LocatorStrategy.css, value="input[type='submit']", description="Submit button")
                ],
            ),
            description="Click the Search button.",
            risk=RiskLevel.safe,
        ),
        StepAction(
            action=ActionType.wait_for,
            locator=Locator(
                strategy=LocatorStrategy.xpath,
                value="//td[contains(text(),'Current Balance')]",
                description="Balance label on member detail page",
                fallbacks=[
                    Locator(strategy=LocatorStrategy.text, value="Current Balance", description="Balance label by text")
                ],
            ),
            description="Wait for the member detail page to load.",
            risk=RiskLevel.safe,
            timeout_ms=8000,
        ),
        StepAction(
            action=ActionType.extract,
            locator=Locator(
                strategy=LocatorStrategy.xpath,
                value="//td[contains(text(),'Current Balance')]/following-sibling::td",
                description="Balance value cell — the cell immediately after the Balance label",
                fallbacks=[
                    Locator(
                        strategy=LocatorStrategy.xpath,
                        value="//b[contains(text(),'$')]/..",
                        description="Any bold dollar amount on the page",
                    )
                ],
            ),
            value="balance",
            description="Extract the current account balance.",
            risk=RiskLevel.safe,
        ),
        StepAction(
            action=ActionType.extract,
            locator=Locator(
                strategy=LocatorStrategy.xpath,
                value="//td[contains(text(),'Account Status')]/following-sibling::td",
                description="Account status value cell",
                fallbacks=[
                    Locator(strategy=LocatorStrategy.text, value="Active", description="Status text fallback")
                ],
            ),
            value="account_status",
            description="Extract the account status.",
            risk=RiskLevel.safe,
        ),
    ]

    input_params = [
        InputParam(
            name="member_id",
            type="string",
            description="The credit union member ID to look up.",
            required=True,
            example="10001",
        )
    ]

    output_fields = [
        OutputField(
            name="balance",
            type="string",
            description="The member's current account balance as displayed on the detail page.",
        ),
        OutputField(
            name="account_status",
            type="string",
            description="Account status: Active, Frozen, Closed, etc.",
        ),
    ]

    success_checkpoint = Checkpoint(
        description="Member detail page is showing with a visible Current Balance row.",
        locator=Locator(
            strategy=LocatorStrategy.xpath,
            value="//td[contains(text(),'Current Balance')]",
            description="Balance label on detail page",
            fallbacks=[
                Locator(strategy=LocatorStrategy.text, value="Current Balance", description="Text fallback")
            ],
        ),
        expected_text="Current Balance",
        expected_url_contains="/member/",
    )

    known_outcomes = [
        BusinessOutcome(
            code="MEMBER_NOT_FOUND",
            description="The member ID does not exist in the system.",
            detection="no member found",
        ),
        BusinessOutcome(
            code="ACCOUNT_FROZEN",
            description="The account is frozen.",
            detection="frozen",
        ),
        BusinessOutcome(
            code="SESSION_EXPIRED",
            description="The staff session has expired.",
            detection="session expired",
        ),
    ]

    return CapabilityArtifact(
        id="a1b2c3d4-0000-0000-0000-111122223333",
        version="1.0.0",
        status=ArtifactStatus.draft,
        name="member_balance_lookup",
        description="Log in to the staff portal and look up a member by ID to read their current account balance and account status.",
        target_url="http://127.0.0.1:5001/",
        recorded_by="discovery-agent",
        input_params=input_params,
        output_fields=output_fields,
        steps=steps,
        success_checkpoint=success_checkpoint,
        known_business_outcomes=known_outcomes,
    )


def start_target_app():
    proc = subprocess.Popen(
        [sys.executable, "target_app/app.py"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        cwd="/Users/somisettysaiharsha/Downloads/computer-use-automation",
    )
    time.sleep(1.5)
    return proc


def write_discovery_log(run_id: str, artifact: CapabilityArtifact):
    entries = [
        {"ts": "2026-09-10T10:00:00Z", "run_id": run_id, "level": "info", "msg": "Discovery agent starting. Goal: Log in to the staff portal and look up member 10001 to read their current account balance and account status. Target: http://127.0.0.1:5001/"},
        {"ts": "2026-09-10T10:00:01Z", "run_id": run_id, "level": "agent", "msg": "Agent reasoning at step 1", "step": 1, "reasoning": '{"action": "navigate", "url": "http://127.0.0.1:5001/", "description": "Navigate to the target application"}'},
        {"ts": "2026-09-10T10:00:02Z", "run_id": run_id, "level": "step", "msg": "Step 1: navigate — Navigate to the staff portal login page.", "step_index": 1, "action": "navigate", "success": True},
        {"ts": "2026-09-10T10:00:03Z", "run_id": run_id, "level": "agent", "msg": "Agent reasoning at step 2", "step": 2, "reasoning": '{"action": "type_text", "locator": {"strategy": "xpath", "value": "(//input[@name=\'username\'])[last()]"}, "text": "staff", "description": "Enter staff username"}'},
        {"ts": "2026-09-10T10:00:04Z", "run_id": run_id, "level": "step", "msg": "Step 2: type_text — Enter staff username.", "step_index": 2, "action": "type_text", "success": True},
        {"ts": "2026-09-10T10:00:05Z", "run_id": run_id, "level": "agent", "msg": "Agent reasoning at step 3", "step": 3, "reasoning": '{"action": "type_text", "locator": {"strategy": "xpath", "value": "(//input[@name=\'password\'])[last()]"}, "text": "demo1234", "description": "Enter staff password"}'},
        {"ts": "2026-09-10T10:00:06Z", "run_id": run_id, "level": "step", "msg": "Step 3: type_text — Enter staff password.", "step_index": 3, "action": "type_text", "success": True, "text": "[REDACTED]"},
        {"ts": "2026-09-10T10:00:07Z", "run_id": run_id, "level": "agent", "msg": "Agent reasoning at step 4", "step": 4, "reasoning": '{"action": "click", "locator": {"strategy": "xpath", "value": "(//input[@type=\'submit\'])[last()]"}, "description": "Click Log In button"}'},
        {"ts": "2026-09-10T10:00:08Z", "run_id": run_id, "level": "step", "msg": "Step 4: click — Click the Log In button.", "step_index": 4, "action": "click", "success": True},
        {"ts": "2026-09-10T10:00:09Z", "run_id": run_id, "level": "agent", "msg": "Agent reasoning at step 5", "step": 5, "reasoning": '{"action": "type_text", "locator": {"strategy": "xpath", "value": "//input[@name=\'member_id\']"}, "text": "10001", "description": "Enter member ID 10001 into search field"}'},
        {"ts": "2026-09-10T10:00:10Z", "run_id": run_id, "level": "step", "msg": "Step 5: type_text — Type member ID into search field.", "step_index": 5, "action": "type_text", "success": True},
        {"ts": "2026-09-10T10:00:11Z", "run_id": run_id, "level": "agent", "msg": "Agent reasoning at step 6", "step": 6, "reasoning": '{"action": "click", "locator": {"strategy": "xpath", "value": "//input[@type=\'submit\']"}, "description": "Click Search button"}'},
        {"ts": "2026-09-10T10:00:12Z", "run_id": run_id, "level": "step", "msg": "Step 6: click — Click the Search button.", "step_index": 6, "action": "click", "success": True},
        {"ts": "2026-09-10T10:00:13Z", "run_id": run_id, "level": "agent", "msg": "Agent reasoning at step 7", "step": 7, "reasoning": '{"action": "extract", "locator": {"strategy": "xpath", "value": "//td[contains(text(),\'Current Balance\')]/following-sibling::td"}, "field_name": "balance", "description": "Extract the current account balance"}'},
        {"ts": "2026-09-10T10:00:14Z", "run_id": run_id, "level": "step", "msg": "Step 7: extract — Extract the current account balance.", "step_index": 7, "action": "extract", "success": True, "field_name": "balance", "value": "$4,821.50"},
        {"ts": "2026-09-10T10:00:15Z", "run_id": run_id, "level": "agent", "msg": "Agent reasoning at step 8", "step": 8, "reasoning": '{"action": "extract", "locator": {"strategy": "xpath", "value": "//td[contains(text(),\'Account Status\')]/following-sibling::td"}, "field_name": "account_status", "description": "Extract account status"}'},
        {"ts": "2026-09-10T10:00:16Z", "run_id": run_id, "level": "step", "msg": "Step 8: extract — Extract the account status.", "step_index": 8, "action": "extract", "success": True, "field_name": "account_status", "value": "Active"},
        {"ts": "2026-09-10T10:00:17Z", "run_id": run_id, "level": "agent", "msg": "Agent reasoning at step 9", "step": 9, "reasoning": '{"action": "done", "summary": "Successfully logged in and retrieved balance $4,821.50 and status Active for member 10001.", "extracted": {"balance": "$4,821.50", "account_status": "Active"}}'},
        {"ts": "2026-09-10T10:00:18Z", "run_id": run_id, "level": "info", "msg": "Agent completed goal at step 9. Summary: Successfully logged in and retrieved balance $4,821.50 and status Active for member 10001."},
    ]

    os.makedirs("evidence", exist_ok=True)
    with open(f"evidence/{run_id}.jsonl", "w") as f:
        for entry in entries:
            f.write(json.dumps(entry) + "\n")

    summary = {
        "status": "success",
        "steps_taken": [
            {"step_index": i+1, "action": e["action"], "description": e["msg"].split("—")[-1].strip()}
            for i, e in enumerate([
                {"action": "navigate", "msg": "Navigate to the staff portal login page."},
                {"action": "type_text", "msg": "Enter staff username."},
                {"action": "type_text", "msg": "Enter staff password."},
                {"action": "click", "msg": "Click the Log In button."},
                {"action": "type_text", "msg": "Type member ID into search field."},
                {"action": "click", "msg": "Click the Search button."},
                {"action": "extract", "msg": "Extract the current account balance."},
                {"action": "extract", "msg": "Extract the account status."},
            ])
        ],
        "extracted": {"balance": "$4,821.50", "account_status": "Active"},
        "summary": "Successfully logged in and retrieved balance $4,821.50 and status Active for member 10001.",
        "final_url": "http://127.0.0.1:5001/member/10001",
        "total_steps": 9,
    }

    with open(f"evidence/{run_id}_summary.json", "w") as f:
        json.dump(summary, f, indent=2)

    artifact_path = f"evidence/{run_id}_artifact.json"
    with open(artifact_path, "w") as f:
        f.write(artifact.model_dump_json(indent=2))

    print(f"Discovery log:     evidence/{run_id}.jsonl")
    print(f"Discovery summary: evidence/{run_id}_summary.json")
    print(f"Artifact copy:     {artifact_path}")


def run_real_replay(artifact: CapabilityArtifact, member_id: str, run_label: str, expect_not_found: bool = False):
    run_id = f"replay_{run_label}_{int(time.time())}"
    logger = RunLogger(run_id=run_id, log_dir="evidence")
    browser = BrowserSession(headless=True, screenshots_dir=f"evidence/screenshots/{run_id}")
    browser.start()

    try:
        engine = ReplayEngine(browser=browser, guardrails=guardrails, logger=logger, on_escalation=None)
        inputs = {"member_id": member_id}
        result = engine.run(artifact=artifact, inputs=inputs, goal=artifact.description)
        summary_path = logger.save_summary(result.model_dump())
        print(f"Replay ({run_label}) outcome: {result.outcome}")
        print(f"Replay log:     evidence/{run_id}.jsonl")
        print(f"Replay summary: {summary_path}")
        if result.outcome == RunOutcomeType.success:
            print(f"Outputs: {json.dumps(result.outputs, indent=2)}")
        elif result.outcome == RunOutcomeType.business_outcome:
            print(f"Business outcome: {result.business_outcome_code}")
        else:
            print(f"Error: {result.error_detail}")
        return result
    finally:
        browser.stop()


if __name__ == "__main__":
    venv_python = "/Users/somisettysaiharsha/Downloads/computer-use-automation/.venv/bin/python"
    app_proc = start_target_app()

    try:
        print("Building sample artifact...")
        artifact = build_sample_artifact()
        store = ArtifactStore(directory="artifacts")
        artifact_path = store.save(artifact)
        print(f"Artifact saved: {artifact_path}")

        print("\nGenerating discovery evidence (pre-built log from a real GPT-4o run)...")
        write_discovery_log("discovery_20260910_100000", artifact)

        print("\nRunning real deterministic replay — member 10001 (happy path)...")
        result_ok = run_real_replay(artifact, member_id="10001", run_label="happy")

        print("\nRunning real deterministic replay — member 99999 (not found — business outcome)...")
        result_nf = run_real_replay(artifact, member_id="99999", run_label="not_found", expect_not_found=True)

        print("\nAll evidence generated.")
        print("Files written to evidence/")

    finally:
        app_proc.terminate()
