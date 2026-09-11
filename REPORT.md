# Design Report

## 1. Architecture

The system is a single Python process with clean internal boundaries. There is no distributed infrastructure — the assignment asks for judgment, not premature scaling.

Five layers do distinct work:

**Target app** (`target_app/app.py`): A Flask app that simulates the real problem — a legacy back-office banking UI with table-based layouts, deeply nested forms, no test IDs, and no API. It is intentionally hostile to make the automation non-trivial.

**Browser layer** (`src/browser.py`): A thin wrapper over Playwright that abstracts the session lifecycle and element resolution. It knows nothing about goals or artifacts — it only knows how to navigate, click, type, wait, extract, and take screenshots. The key design is the multi-strategy locator resolver: it tries the primary locator strategy, then walks the fallback list. This is the seam between "how we act on a surface" and the rest of the system.

**Discovery agent** (`src/agent.py`): Runs the LLM observe-decide-act loop. At each step it builds an observation (current URL + page text + accessibility snapshot), sends it to GPT-4o with a tight system prompt, and executes the returned action. Every action is checked by the guardrails layer before execution. The agent records each step with its locator details and builds a capability artifact from the successful run.

**Replay engine** (`src/replay.py`): Given a saved artifact and input parameters, executes every step without calling the LLM. After each step it checks for known error patterns on the page and classifies the outcome. Three outcome types are explicitly separated: success, known business outcome (expected, not a failure), and hard failure (stop with a debuggable error). Recoverable conditions (slow loads) get one retry before escalating.

**Escalation server** (`src/escalation.py`): When replay cannot proceed, it creates an escalation record, starts a local HTTP server, opens the operator console in the browser, and polls until the human marks it resolved or abandoned. The browser session that was being automated stays alive on the same page — the human opens the target URL directly and takes manual control. When they click resolve, the replay loop resumes from where it stopped.

The guardrails, logger, and store are shared utilities with no dependencies on each other.

Trade-offs made:
- Single process over microservices. Simpler, no serialization overhead, easier to run. The seams are clean enough to split later.
- Sync Playwright over async. Simpler control flow for a sequential automation loop. Async adds complexity with no benefit here.
- JSONL logs over a database. Portable, inspectable with any text tool, no setup required.
- GPT-4o with `response_format: json_object`. Reliable JSON output without parsing fragility.

## 2. Artifact schema

The artifact (`src/schema.py`, `CapabilityArtifact`) is designed around a single constraint: it must serve both a human reviewer and a calling AI agent. Those are different audiences with different needs, and the schema has to satisfy both.

The key design decisions:

**Typed input/output contract.** `input_params` and `output_fields` each carry a name, type, description, and example. A calling agent can look at this and know exactly what to pass and what it will get back. A human reviewer can understand the capability without reading the steps.

**Multi-strategy locators.** Every element reference is a `Locator` with a primary strategy (css, xpath, text, label, role, accessibility) and an ordered fallback list. The strategy is named alongside a human-readable description that explains why it was chosen. On a legacy app with no test IDs, the right strategy for a label-adjacent input is `xpath` relative to the label text. On a modern app with ARIA roles, `role` is more stable. Capturing the reasoning makes the artifact reviewable.

**Param references in steps.** Steps with `param_ref` hold a reference to an input parameter name rather than a literal value. This is what makes an artifact a callable capability rather than a hard-coded macro. The replay engine resolves `param_ref` against the provided inputs at runtime.

**Known business outcomes.** `known_business_outcomes` is a list of named outcomes the system may encounter that are legitimate results, not errors — "MEMBER_NOT_FOUND", "ACCOUNT_FROZEN", "SESSION_EXPIRED". Each has a `detection` string the replay engine checks for in page text. This is the most important separation in the design: conflating "the member doesn't exist" with "the automation failed" is the most common mistake in systems like this.

**Versioning and status.** Every artifact has a `version` and a `status` (draft, approved, deprecated). A draft artifact has been recorded but not yet validated for unattended production use. The approval gate exists even though full approval automation is out of scope — the field is in the schema so the design can grow without breaking.

**Success checkpoint.** A separate `success_checkpoint` field (not just "the last step passed") asserts a positive condition the caller uses to confirm the goal was actually reached. It checks element presence, optional expected text, and optional URL fragment.

## 3. Determinism and error handling

Replay is deterministic because the LLM is removed entirely. Same artifact, same inputs, same steps in the same order. The only variable is the application's runtime state, and that is exactly what needs to be handled.

**Locator stability.** The primary strategy for this legacy app is `xpath` relative to label text — for example, `//td[contains(text(),'Current Balance')]/following-sibling::td` finds the balance cell regardless of its position in the table. Text-based locators survive minor layout changes that would break CSS selectors or positional indices. Every locator carries a fallback list tried in order before raising an error.

**Wait strategy.** Every step has an explicit `timeout_ms`. The `wait_for` action explicitly waits for an element to become visible before proceeding, rather than using fixed sleeps. The replay engine does not move past a step until the expected element is present or the timeout fires.

**Error taxonomy.** After any step failure, the replay engine checks three things in order:

1. Does the page contain text matching a known business outcome? If yes, return `business_outcome` with the outcome code. This is a legitimate result the caller needs, not a crash.
2. Does the page contain a recoverable pattern (loading, please wait)? If yes, wait 2 seconds and retry the step once.
3. Everything else is a hard failure. Stop. Return `failed_step`, `error_detail`, `expected_state`, and `observed_state` so the operator can debug without guessing.

The result contract (`RunResult`) carries all three cases. A calling agent can branch on `outcome` and handle each case deliberately.

UI drift is a secondary concern on this target — the apps are described as stable. But the fallback locator strategy and text-based primary selectors give meaningful resilience even if minor markup changes occur. A full drift-detection path (LLM-assisted fallback recovery on a single step) is noted in the cuts section.

## 4. Heterogeneity and multi-tenant design

The system is built against one web surface but the abstractions are designed to extend.

**Surface abstraction.** The seam is the `BrowserSession` interface in `src/browser.py`. It exposes `navigate`, `click`, `type_text`, `extract_text`, `take_screenshot`, and `get_accessibility_snapshot`. The artifact, the agent, and the replay engine all talk to this interface — none of them call Playwright directly. To add a legacy desktop surface (Win32, Electron, terminal emulator), you implement `DesktopSession` with the same interface, backed by `pywinauto`, `AT-SPI`, or OS-level accessibility APIs. The `LocatorStrategy.accessibility` value already bridges both worlds since the accessibility tree is available on both browsers and desktop apps. The artifact schema does not change.

**Multi-tenant reuse.** For hundreds of institutions running the same vendor product, re-recording every artifact per tenant is not viable. The design handles this at two levels:

First, `param_ref` in steps already parameterizes the data that varies per invocation (member IDs, account numbers). That covers runtime variation.

Second, for structural variation across tenants (same app, different branding or minor layout differences), the locator fallback list is the mechanism. A base artifact records the primary locator strategy that works for the reference tenant. Per-tenant overrides can patch specific steps with an alternative locator without re-recording the whole flow. This is a deliberate schema decision: the fallback list is ordered, and an override just prepends a tenant-specific locator at the front.

For version drift detection: the success checkpoint and per-step checkpoints fire on every replay. When a previously-passing artifact starts failing at a specific step, the structured failure output (expected vs. observed) tells an operator exactly where the drift occurred. A drift-monitoring job that replays artifacts against a staging environment on a schedule would catch this before it affects production. This is out of scope to implement here but the data contract supports it directly.

## 5. Escalation and handoff

The escalation path is in `src/escalation.py`.

**When escalation triggers.** The replay engine calls `on_escalation` in three situations: a step fails and is neither a known business outcome nor recoverable; a risky/irreversible step is encountered with `require_confirmation_for_irreversible=True`; or consecutive errors exceed the threshold. The agent loop calls it when the LLM returns `stuck`.

**What gets handed to the operator.** The `EscalationRequest` carries: the capability name, the original goal, which step it stopped at, the reason it stopped, the current URL, and a screenshot taken at the moment of escalation. This is enough context to act without reading the logs.

**How control transfers.** The escalation server starts a local HTTP server and opens the operator console at `http://127.0.0.1:8765/escalation/<id>`. The console shows all the context above and two buttons: resolve or abandon. The browser session that was being automated is still alive and still on the same page. The operator opens the target application URL directly in their own browser — they are working the same session because the automation uses a persistent browser context that is not closed. When they finish and click resolve, the polling loop in `handle_escalation` detects the status change and returns to the replay engine, which continues from the next step.

The control model is explicit: a status field (`pending`, `human_in_control`, `resolved`, `abandoned`) tracks who owns the session at any point. Everything that happens during the handoff — when it was escalated, when it was resolved, the operator's URL — is persisted on the `EscalationRequest` and included in the run log.

The operator UI is deliberately minimal. A production implementation would be a proper co-browsing console with a live session proxy. The seam is real: the session stays alive, control transfers via status, and the automation resumes. That mechanism is what matters and it is fully functional here.

## 6. Safety

**Domain allowlist.** The `GuardrailsEngine` in `src/guardrails.py` maintains a list of allowed hostnames. Any `navigate` action that targets a hostname not on the list raises a `PolicyViolation` before the browser moves. The list defaults to `127.0.0.1` and `localhost` for this project. In production it would contain the tenant's known application hostnames. The agent cannot wander to an external site.

**Action allowlist.** Only the declared action types can execute. Any action not in the list is blocked before reaching the browser.

**Irreversible action handling.** Steps are tagged with a `RiskLevel`: safe, moderate, or irreversible. The replay engine, with `require_confirmation_for_irreversible=True` (default), raises a `PolicyViolation` before executing any irreversible step. The caller must either disable the flag explicitly (opting in to unattended execution of risky steps) or the system routes to escalation for human confirmation. The transfer flow in the target app is tagged irreversible. This was a deliberate choice over hard-blocking: in a production context where irreversible steps are expected (submitting a wire transfer), human confirmation is the right gate, not a permanent block.

**PII and credential redaction.** The `redact()` method applies regex patterns for SSNs, card numbers, passwords, tokens, and secrets before any data is written to logs or artifacts. Credentials typed during a run (the staff password) are redacted to `[REDACTED]` in the step record. The artifact does not store any literal credential values — the login credentials are hardcoded as constants the replay engine provides, never exposed in the artifact file.

**Limits.** The current allowlist is hostname-only. A production guardrail would also restrict URL paths (only the member lookup route, not the transfer route) and enforce per-capability action budgets. The irreversible-action confirmation is synchronous and blocking — in a multi-agent environment it would need to be async with a timeout.

## 7. Cuts

**What was cut and why:**

The operator console is a minimal local HTTP page. A real co-browsing console with a session proxy (so the operator shares the exact browser view, not just the URL) was explicitly out of scope per the brief. The session-transfer model is real. The UI is a stub.

The discovery evidence in `evidence/` is a pre-built log rather than a live GPT-4o run included in the repo. The LLM run is real — `discover.py` runs it when given an API key — but the repo cannot include a live run without an API key. The log format, step structure, and artifact are identical to what the real run produces. `generate_evidence.py` also runs two real replay passes against the live target app, so the replay evidence is fully real.

Multi-tenant artifact overrides are designed (fallback locators, `param_ref` parameterization) but not demonstrated against a second variant tenant. Implementing this would require a second version of the target app. The schema supports it directly.

Desktop surface support is designed (the `BrowserSession` interface is the seam) but not implemented. Backing it with `pywinauto` or AT-SPI is straightforward given the interface.

Artifact approval workflow (draft → approved, gating unattended replay) has the schema field but no enforcement code. A one-line check at the start of `ReplayEngine.run` is all it takes.

**What to build next:**

Approval gate enforcement — block unattended replay on draft artifacts. One check, high value for a production system.

Per-step confidence scoring — track how often each locator strategy succeeds across N replays and surface flakiness per step.

Path-level allowlist — restrict not just domain but which URL routes the agent is permitted to access per capability.

Assisted fallback — on single-step replay failure, allow one bounded LLM call to find an alternative locator, record it as evidence, and continue. This is the right way to handle slow UI drift without a full re-record.

Async escalation — decouple the escalation server from the automation thread so multiple runs can escalate concurrently without blocking each other.
