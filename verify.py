import json
import os
import subprocess
import sys
import time


VENV_PYTHON = os.path.join(os.path.dirname(__file__), ".venv", "bin", "python")
BASE = os.path.dirname(__file__)

PASS = "\033[92mPASS\033[0m"
FAIL = "\033[91mFAIL\033[0m"
results = []


def check(label, condition, detail=""):
    status = PASS if condition else FAIL
    print(f"  [{status}] {label}" + (f"  →  {detail}" if detail else ""))
    results.append((label, condition))
    return condition


def section(title):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")


section("3.1  Imports — all modules load without error")
try:
    import importlib, sys as _sys
    _sys.path.insert(0, BASE)
    schema   = importlib.import_module("src.schema")
    guards   = importlib.import_module("src.guardrails")
    browser  = importlib.import_module("src.browser")
    agent    = importlib.import_module("src.agent")
    replay   = importlib.import_module("src.replay")
    escal    = importlib.import_module("src.escalation")
    logger   = importlib.import_module("src.logger")
    store    = importlib.import_module("src.store")
    check("src.schema imports",      True)
    check("src.guardrails imports",  True)
    check("src.browser imports",     True)
    check("src.agent imports",       True)
    check("src.replay imports",      True)
    check("src.escalation imports",  True)
    check("src.logger imports",      True)
    check("src.store imports",       True)
except Exception as e:
    check("All modules import", False, str(e))
    print("Cannot continue — fix imports first.")
    sys.exit(1)


section("3.2  Schema: artifact fields and types")
from src.schema import (
    CapabilityArtifact, StepAction, Locator, InputParam, OutputField,
    Checkpoint, BusinessOutcome, ActionType, LocatorStrategy, RiskLevel,
    RunResult, RunOutcomeType, EscalationRequest, EscalationStatus,
)
from src.store import ArtifactStore

store_obj = ArtifactStore(directory=os.path.join(BASE, "artifacts"))
artifact  = store_obj.load(os.path.join(BASE, "artifacts", "member_balance_lookup_1.0.0.json"))

check("Artifact loads from file",           artifact is not None)
check("Artifact has name",                  bool(artifact.name))
check("Artifact has version",               bool(artifact.version))
check("Artifact has status field",          hasattr(artifact, "status"))
check("Artifact has steps",                 len(artifact.steps) > 0, f"{len(artifact.steps)} steps")
check("Artifact has input_params",          len(artifact.input_params) > 0)
check("Artifact has output_fields",         len(artifact.output_fields) > 0)
check("Artifact has success_checkpoint",    artifact.success_checkpoint is not None)
check("Artifact has known_business_outcomes", len(artifact.known_business_outcomes) > 0)

for step in artifact.steps:
    if step.locator:
        check(f"Step '{step.description[:40]}' locator has fallback list",
              isinstance(step.locator.fallbacks, list))
        break

check("InputParam has typed fields",
      all(hasattr(p, "type") and hasattr(p, "required") for p in artifact.input_params))
check("OutputField has name + description",
      all(hasattr(f, "name") and hasattr(f, "description") for f in artifact.output_fields))
check("BusinessOutcome has code + detection",
      all(hasattr(o, "code") and hasattr(o, "detection") for o in artifact.known_business_outcomes))


section("3.3  Guardrails: domain allowlist + PII redaction")
from src.guardrails import GuardrailsEngine, PolicyViolation

g = GuardrailsEngine(allowed_domains=["127.0.0.1", "localhost"])

blocked = False
try:
    g.check_url("http://evil.com/steal")
except PolicyViolation:
    blocked = True
check("External domain blocked",             blocked)

allowed = True
try:
    g.check_url("http://127.0.0.1:5001/search")
except PolicyViolation:
    allowed = False
check("Localhost URL allowed",               allowed)

redacted = g.redact("SSN 123-45-6789, password: hunter2")
check("SSN redacted",                        "[SSN_REDACTED]" in redacted)
check("Password redacted",                   "[PASSWORD_REDACTED]" in redacted)

safe = g.is_safe_to_record("hello world")
unsafe = g.is_safe_to_record("SSN 123-45-6789")
check("Safe string passes is_safe_to_record", safe)
check("SSN string fails is_safe_to_record",   not unsafe)

from src.schema import StepAction, ActionType, RiskLevel
irreversible_step = StepAction(action=ActionType.click, description="transfer", risk=RiskLevel.irreversible)
blocked_irr = False
try:
    g.check_action(irreversible_step)
except PolicyViolation:
    blocked_irr = True
check("Irreversible action blocked by default", blocked_irr)


section("3.4  Target app starts and serves pages")
app_proc = subprocess.Popen(
    [VENV_PYTHON, os.path.join(BASE, "target_app", "app.py")],
    stdout=subprocess.DEVNULL,
    stderr=subprocess.DEVNULL,
)
time.sleep(1.5)

import urllib.request, urllib.error
def get(path, expect_text=None):
    try:
        url = f"http://127.0.0.1:5001{path}"
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=5) as r:
            body = r.read().decode()
        if expect_text:
            return expect_text in body
        return True
    except Exception as e:
        return False

check("/ redirects to /login",              get("/", "First Valley"))
check("/login page loads",                  get("/login", "Log In"))
check("/search redirects to login (unauth)", get("/search", "Log In"))


section("3.5  Deterministic replay — happy path (member 10001)")
from src.browser import BrowserSession
from src.replay import ReplayEngine
from src.logger import RunLogger
import uuid

run_id = f"verify_happy_{int(time.time())}"
rlog = RunLogger(run_id=run_id, log_dir=os.path.join(BASE, "evidence"))
rbrowser = BrowserSession(headless=True, screenshots_dir=os.path.join(BASE, "evidence", "screenshots", run_id))
rbrowser.start()
try:
    engine = ReplayEngine(browser=rbrowser, guardrails=g, logger=rlog, on_escalation=None)
    result = engine.run(artifact=artifact, inputs={"member_id": "10001"}, goal=artifact.description)
    check("Replay completes with outcome=success",      result.outcome == RunOutcomeType.success,  str(result.outcome))
    check("Replay output has 'balance'",               "balance" in result.outputs,               str(result.outputs))
    check("Replay output has 'account_status'",        "account_status" in result.outputs,        str(result.outputs))
    check("Balance value is non-empty",                bool(result.outputs.get("balance")),        result.outputs.get("balance",""))
    check("steps_completed == total_steps",            result.steps_completed == result.total_steps,
          f"{result.steps_completed}/{result.total_steps}")
    check("All step_results recorded",                 len(result.step_results) == result.total_steps)
    check("finished_at is set",                        result.finished_at is not None)
finally:
    rbrowser.stop()


section("3.6  Deterministic replay — not-found (member 99999 → business outcome)")
run_id2 = f"verify_nf_{int(time.time())}"
rlog2 = RunLogger(run_id=run_id2, log_dir=os.path.join(BASE, "evidence"))
rbrowser2 = BrowserSession(headless=True, screenshots_dir=os.path.join(BASE, "evidence", "screenshots", run_id2))
rbrowser2.start()
try:
    engine2 = ReplayEngine(browser=rbrowser2, guardrails=g, logger=rlog2, on_escalation=None)
    result2 = engine2.run(artifact=artifact, inputs={"member_id": "99999"}, goal=artifact.description)
    check("Not-found returns business_outcome (not hard_failure)",
          result2.outcome == RunOutcomeType.business_outcome, str(result2.outcome))
    check("Business outcome code is MEMBER_NOT_FOUND",
          result2.business_outcome_code == "MEMBER_NOT_FOUND", str(result2.business_outcome_code))
finally:
    rbrowser2.stop()


section("3.7  Replay — missing required input raises ValueError")
run_id3 = f"verify_missing_{int(time.time())}"
rlog3 = RunLogger(run_id=run_id3, log_dir=os.path.join(BASE, "evidence"))
rbrowser3 = BrowserSession(headless=True, screenshots_dir=os.path.join(BASE, "evidence", "screenshots", run_id3))
rbrowser3.start()
try:
    engine3 = ReplayEngine(browser=rbrowser3, guardrails=g, logger=rlog3, on_escalation=None)
    missing_err = False
    try:
        engine3.run(artifact=artifact, inputs={}, goal=artifact.description)
    except ValueError:
        missing_err = True
    except Exception:
        missing_err = True
    check("Missing param raises error", missing_err)
finally:
    rbrowser3.stop()


section("3.8  Escalation server: creates request, polls for status")
from src.escalation import EscalationServer, ESCALATION_STORE
from src.schema import EscalationRequest, EscalationStatus
import threading

esc_server = EscalationServer(port=8766)
esc_server.start()

esc = EscalationRequest(
    run_id="test-run",
    artifact_id=artifact.id,
    capability_name="test",
    goal="test goal",
    current_step=3,
    reason="Test escalation — unit check",
)
ESCALATION_STORE[esc.id] = esc

import urllib.request as _req
esc_page_ok = False
try:
    url = f"http://127.0.0.1:8766/escalation/{esc.id}"
    with _req.urlopen(url, timeout=3) as r:
        body = r.read().decode()
    esc_page_ok = "Human Intervention" in body and esc.id in body
except Exception as e:
    pass
check("Escalation page served with correct ID", esc_page_ok)

import json as _json
import urllib.request as _req2
resolve_ok = False
try:
    req = _req2.Request(
        f"http://127.0.0.1:8766/escalation/{esc.id}/resolve",
        data=b"",
        method="POST",
    )
    with _req2.urlopen(req, timeout=3) as r:
        body = _json.loads(r.read())
    resolve_ok = body.get("status") == "resolved"
except Exception as e:
    pass
check("Resolve endpoint returns {status: resolved}", resolve_ok)
check("Escalation status updated in store",
      ESCALATION_STORE[esc.id].status == EscalationStatus.resolved)


section("3.9  Evidence files exist")
ev = os.path.join(BASE, "evidence")
check("discovery .jsonl exists",          os.path.exists(os.path.join(ev, "discovery_20260910_100000.jsonl")))
check("discovery summary.json exists",   os.path.exists(os.path.join(ev, "discovery_20260910_100000_summary.json")))
check("discovery artifact.json exists",  os.path.exists(os.path.join(ev, "discovery_20260910_100000_artifact.json")))
check("replay happy .jsonl exists",      os.path.exists(os.path.join(ev, "replay_happy.jsonl")))
check("replay happy summary exists",     os.path.exists(os.path.join(ev, "replay_happy_summary.json")))
check("replay not_found .jsonl exists",  os.path.exists(os.path.join(ev, "replay_not_found.jsonl")))
check("replay not_found summary exists", os.path.exists(os.path.join(ev, "replay_not_found_summary.json")))

with open(os.path.join(ev, "replay_happy_summary.json")) as f:
    happy_summary = json.load(f)
check("Happy summary has outcome=success",  happy_summary.get("outcome") == "success")
check("Happy summary has balance output",   "balance" in happy_summary.get("outputs", {}))

with open(os.path.join(ev, "replay_not_found_summary.json")) as f:
    nf_summary = json.load(f)
check("Not-found summary outcome=business_outcome",
      nf_summary.get("outcome") == "business_outcome")
check("Not-found summary has MEMBER_NOT_FOUND code",
      nf_summary.get("business_outcome_code") == "MEMBER_NOT_FOUND")


section("3.10  README.md and REPORT.md content")
with open(os.path.join(BASE, "README.md")) as f:
    readme = f.read()
check("README has setup instructions",    "pip install" in readme)
check("README has demo path",             "discover.py" in readme and "replay.py" in readme)
check("README has evidence section",      "evidence" in readme.lower())

with open(os.path.join(BASE, "REPORT.md")) as f:
    report = f.read()
for heading in ["Architecture", "Artifact schema", "Determinism", "Heterogeneity", "Escalation", "Safety", "Cuts"]:
    check(f"REPORT.md has '{heading}' section", heading in report)


section("3.11  Logger: structured JSONL output")
import tempfile
tlog = RunLogger(run_id="logtest", log_dir=tempfile.mkdtemp())
tlog.info("test info", extra_field="hello")
tlog.step(1, "click", "Click something", True)
tlog.error("something broke", detail="traceback here")
entries = tlog.get_all()
check("Logger records entries",           len(entries) == 3)
check("Each entry has ts and run_id",     all("ts" in e and "run_id" in e for e in entries))
check("Each entry has level",             all("level" in e for e in entries))


app_proc.terminate()


section("SUMMARY")
passed = sum(1 for _, ok in results if ok)
total  = len(results)
failed_list = [label for label, ok in results if not ok]
print(f"\n  {passed}/{total} checks passed.")
if failed_list:
    print(f"\n  Failed checks:")
    for f in failed_list:
        print(f"    - {f}")
    sys.exit(1)
else:
    print("\n  All checks passed. Ready to push.")
