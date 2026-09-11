from src.schema import CapabilityArtifact
from src.store import ArtifactStore
from src.guardrails import guardrails, PolicyViolation
from src.logger import RunLogger
from src.browser import BrowserSession
from src.agent import DiscoveryAgent
from src.replay import ReplayEngine
from src.escalation import EscalationServer

store = ArtifactStore()
artifact = store.load("artifacts/member_balance_lookup_1.0.0.json")
print(f"Artifact: {artifact.name} v{artifact.version} [{artifact.status}]")
print(f"Steps: {len(artifact.steps)}")
print(f"Inputs: {[p.name for p in artifact.input_params]}")
print(f"Outputs: {[f.name for f in artifact.output_fields]}")
print(f"Known outcomes: {[o.code for o in artifact.known_business_outcomes]}")

url_ok = True
try:
    guardrails.check_url("http://evil.com/steal")
    url_ok = False
except PolicyViolation:
    pass
print(f"Domain blocklist works: {url_ok}")

redacted = guardrails.redact("SSN is 123-45-6789 and password: secret123")
print(f"PII redacted: {redacted}")
print("All checks passed.")
