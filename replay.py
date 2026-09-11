import json
import os
import sys

from src.browser import BrowserSession
from src.escalation import EscalationServer
from src.guardrails import guardrails
from src.logger import RunLogger
from src.replay import ReplayEngine
from src.schema import EscalationRequest, EscalationStatus, RunOutcomeType
from src.store import ArtifactStore


def run_replay(artifact_path: str, inputs: dict, headless: bool = True, with_escalation: bool = True):
    store = ArtifactStore()
    artifact = store.load(artifact_path)

    run_id = f"replay_{int(__import__('time').time())}"
    logger = RunLogger(run_id=run_id, log_dir="evidence")
    browser = BrowserSession(headless=headless, screenshots_dir=f"evidence/screenshots/{run_id}")

    escalation_server = None
    on_escalation = None

    if with_escalation:
        escalation_server = EscalationServer(port=8765)
        escalation_server.start()

        def on_escalation(esc: EscalationRequest) -> EscalationRequest:
            return escalation_server.handle_escalation(esc, timeout_seconds=120)

    browser.start()

    try:
        engine = ReplayEngine(
            browser=browser,
            guardrails=guardrails,
            logger=logger,
            on_escalation=on_escalation,
        )

        logger.info(f"Starting replay. Artifact: {artifact.name} v{artifact.version}. Inputs: {list(inputs.keys())}")

        result = engine.run(artifact=artifact, inputs=inputs, goal=artifact.description)

        summary_path = logger.save_summary(result.model_dump())
        print(f"\nRun log:     evidence/{run_id}.jsonl")
        print(f"Run summary: {summary_path}")
        print(f"Outcome:     {result.outcome}")

        if result.outcome == RunOutcomeType.success:
            print(f"Outputs:     {json.dumps(result.outputs, indent=2)}")

        elif result.outcome == RunOutcomeType.business_outcome:
            print(f"Business outcome code: {result.business_outcome_code}")
            print("This is an expected result, not a system failure.")

        elif result.outcome == RunOutcomeType.hard_failure:
            print(f"Failed at step:  {result.failed_step}/{result.total_steps}")
            print(f"Error detail:    {result.error_detail}")
            print(f"Expected state:  {result.expected_state}")
            print(f"Observed state:  {(result.observed_state or '')[:200]}")

        elif result.outcome == RunOutcomeType.escalated:
            print(f"Run was escalated. Escalation ID: {result.escalation_id}")

        return result

    finally:
        browser.stop()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Replay a saved capability artifact.")
    parser.add_argument("--artifact", required=True, help="Path to the artifact JSON file.")
    parser.add_argument("--member-id", default="10001", help="Member ID to look up.")
    parser.add_argument("--no-headless", action="store_true", help="Show browser window.")
    parser.add_argument("--no-escalation", action="store_true", help="Disable escalation server.")
    args = parser.parse_args()

    inputs = {"member_id": args.member_id}

    result = run_replay(
        artifact_path=args.artifact,
        inputs=inputs,
        headless=not args.no_headless,
        with_escalation=not args.no_escalation,
    )

    if result.outcome == RunOutcomeType.success:
        print("\nReplay passed.")
    elif result.outcome == RunOutcomeType.business_outcome:
        print(f"\nBusiness outcome: {result.business_outcome_code}")
    else:
        print("\nReplay did not succeed.")
        sys.exit(1)
