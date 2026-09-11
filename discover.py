import json
import os
import sys

from src.agent import DiscoveryAgent
from src.browser import BrowserSession
from src.escalation import EscalationServer
from src.guardrails import guardrails
from src.logger import RunLogger
from src.schema import (
    BusinessOutcome,
    Checkpoint,
    InputParam,
    Locator,
    LocatorStrategy,
    OutputField,
)
from src.store import ArtifactStore


def build_member_lookup_contract():
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
            description="The member's current account balance as displayed.",
            selector=Locator(
                strategy=LocatorStrategy.xpath,
                value="//td[contains(text(),'Current Balance')]/following-sibling::td",
                description="Balance cell in the member detail table",
            ),
        ),
        OutputField(
            name="account_status",
            type="string",
            description="Active, Frozen, Closed, etc.",
            selector=Locator(
                strategy=LocatorStrategy.xpath,
                value="//td[contains(text(),'Account Status')]/following-sibling::td",
                description="Status cell in the member detail table",
            ),
        ),
    ]

    success_checkpoint = Checkpoint(
        description="Member detail page is visible showing member name and balance.",
        locator=Locator(
            strategy=LocatorStrategy.xpath,
            value="//td[contains(text(),'Current Balance')]",
            description="Balance label on member detail page",
            fallbacks=[
                Locator(
                    strategy=LocatorStrategy.text,
                    value="Current Balance",
                    description="Balance label by text",
                )
            ],
        ),
        expected_text="Current Balance",
    )

    known_outcomes = [
        BusinessOutcome(
            code="MEMBER_NOT_FOUND",
            description="The member ID does not exist in the system.",
            detection="no member found",
        ),
        BusinessOutcome(
            code="ACCOUNT_FROZEN",
            description="The member account is frozen.",
            detection="frozen",
        ),
        BusinessOutcome(
            code="SESSION_EXPIRED",
            description="Staff session timed out.",
            detection="session expired",
        ),
    ]

    return input_params, output_fields, success_checkpoint, known_outcomes


def run_discovery(goal: str, target_url: str, headless: bool = True):
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        print("Error: OPENAI_API_KEY environment variable not set.")
        sys.exit(1)

    run_id = f"discovery_{int(__import__('time').time())}"
    logger = RunLogger(run_id=run_id, log_dir="evidence")
    store = ArtifactStore(directory="artifacts")

    browser = BrowserSession(headless=headless, screenshots_dir=f"evidence/screenshots/{run_id}")
    browser.start()

    try:
        agent = DiscoveryAgent(
            openai_api_key=api_key,
            browser=browser,
            guardrails=guardrails,
            logger=logger,
        )

        logger.info(f"Starting discovery. Goal: {goal}. URL: {target_url}")
        run_result = agent.run(goal=goal, target_url=target_url)

        logger.info(f"Discovery run finished with status: {run_result['status']}")

        summary_path = logger.save_summary(run_result)
        print(f"\nRun log:     evidence/{run_id}.jsonl")
        print(f"Run summary: {summary_path}")
        print(f"Status:      {run_result['status']}")

        if run_result["status"] == "success":
            input_params, output_fields, success_checkpoint, known_outcomes = build_member_lookup_contract()

            artifact = agent.build_artifact(
                run_result=run_result,
                goal=goal,
                target_url=target_url,
                capability_name="member_balance_lookup",
                input_params=input_params,
                output_fields=output_fields,
                success_checkpoint=success_checkpoint,
                known_outcomes=known_outcomes,
            )

            artifact_path = store.save(artifact)
            print(f"Artifact:    {artifact_path}")
            print(f"Artifact ID: {artifact.id}")

            evidence_artifact_path = f"evidence/{run_id}_artifact.json"
            with open(evidence_artifact_path, "w") as f:
                f.write(artifact.model_dump_json(indent=2))
            print(f"Evidence artifact copy: {evidence_artifact_path}")

            return artifact

        else:
            print(f"Discovery did not complete successfully: {run_result.get('reason')}")
            if run_result.get("status") == "stuck":
                print("The agent was stuck. Consider running again or adjusting the goal.")
            return None

    finally:
        browser.stop()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Run LLM-driven discovery on a target application.")
    parser.add_argument("--goal", default="Log in to the staff portal and look up member 10001 to read their current account balance and account status.", help="Natural language goal.")
    parser.add_argument("--url", default="http://127.0.0.1:5001/", help="Target application URL.")
    parser.add_argument("--no-headless", action="store_true", help="Show browser window.")
    args = parser.parse_args()

    artifact = run_discovery(
        goal=args.goal,
        target_url=args.url,
        headless=not args.no_headless,
    )

    if artifact:
        print(f"\nDiscovery succeeded. Artifact saved.")
        print(f"Run replay with:  python replay.py --artifact artifacts/{artifact.name}_{artifact.version}.json --member-id 10001")
    else:
        print("\nDiscovery failed or agent was stuck.")
        sys.exit(1)
