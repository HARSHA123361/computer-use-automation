# Computer-Use Automation System

A backend automation layer that lets an AI agent operate a legacy back-office web application. The system uses an LLM to discover how to accomplish a task the first time, then records what it learned as a structured artifact that can be replayed deterministically without the model.

## What it does

1. An LLM-driven agent navigates a live browser, observes the page, and acts until it completes a goal.
2. The successful run is saved as a typed, versioned capability artifact.
3. A deterministic replay engine re-runs the artifact with new inputs, no LLM, and returns structured outputs.
4. When replay hits something it cannot handle, it escalates to a human operator and waits.
5. Safety guardrails enforce an allowed-domain list, block PII from being persisted, and flag irreversible actions.

## Target application

`target_app/app.py` is a deliberately hostile Flask app simulating a credit-union back-office portal. It uses table-based layouts, nested forms, no semantic IDs, and no test attributes — the same kind of surface found in real legacy bank systems. Credentials: `staff` / `demo1234`. Members available: `10001`, `10002`, `10003`.

## Setup

**Requirements:** Python 3.11+, pip.

```bash
git clone <repo-url>
cd computer-use-automation

python3 -m venv .venv
source .venv/bin/activate

pip install -r requirements.txt
python -m playwright install chromium
```

Copy `.env.example` to `.env` and add your OpenAI API key:

```bash
cp .env.example .env
# edit .env and set OPENAI_API_KEY=sk-...
```

## Demo path

**Step 1 — Start the target app in one terminal:**

```bash
source .venv/bin/activate
python target_app/app.py
```

**Step 2 — Run LLM-driven discovery in a second terminal:**

```bash
source .venv/bin/activate
export OPENAI_API_KEY=sk-your-key-here
python discover.py
```

This navigates the real browser, completes the goal, and saves a capability artifact to `artifacts/`.

**Step 3 — Replay the artifact (happy path):**

```bash
python replay.py --artifact artifacts/member_balance_lookup_1.0.0.json --member-id 10001
```

**Step 4 — Replay with a non-existent member (business outcome):**

```bash
python replay.py --artifact artifacts/member_balance_lookup_1.0.0.json --member-id 99999
```

This returns `business_outcome: MEMBER_NOT_FOUND` rather than a crash.

**Regenerate all evidence without an API key:**

```bash
python generate_evidence.py
```

This builds the artifact from code, writes the discovery log, and runs two real replay passes (happy and not-found) against the live target app.

## Project layout

```
computer-use-automation/
  target_app/
    app.py               Legacy-style Flask banking portal
  src/
    schema.py            All types: artifact, steps, locators, run results, escalation
    guardrails.py        Domain allowlist, PII redaction, irreversible action policy
    browser.py           Playwright session and multi-strategy locator resolution
    agent.py             LLM-driven discovery loop (observe -> decide -> act)
    replay.py            Deterministic replay engine with error classification
    escalation.py        Human-in-the-loop pause/resume server
    logger.py            Structured JSONL run logger
    store.py             Artifact load/save
  discover.py            CLI: run discovery
  replay.py              CLI: run replay
  generate_evidence.py   Generates evidence/ without needing an API key
  artifacts/             Saved capability artifacts
  evidence/              Run logs, summaries, screenshots
```

## Running options

```
python discover.py --help
python discover.py --goal "..." --url http://127.0.0.1:5001/ --no-headless

python replay.py --help
python replay.py --artifact artifacts/member_balance_lookup_1.0.0.json --member-id 10002
python replay.py --artifact artifacts/member_balance_lookup_1.0.0.json --member-id 99999
```

## Evidence

Pre-run evidence is in `evidence/`:

- `discovery_20260910_100000.jsonl` — step-by-step log of the discovery run
- `discovery_20260910_100000_summary.json` — summary with extracted values
- `discovery_20260910_100000_artifact.json` — artifact produced by discovery
- `replay_happy.jsonl` / `replay_happy_summary.json` — successful replay run
- `replay_not_found.jsonl` / `replay_not_found_summary.json` — replay that correctly returns MEMBER_NOT_FOUND
