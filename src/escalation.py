from __future__ import annotations

import json
import os
import threading
import time
import uuid
import webbrowser
from datetime import datetime, timezone
from typing import Dict, Optional

from .schema import EscalationRequest, EscalationStatus

ESCALATION_STORE: Dict[str, EscalationRequest] = {}

OPERATOR_PAGE = """
<!DOCTYPE html>
<html>
<head>
<title>Operator Console - Human Intervention Required</title>
<style>
  body {{ font-family: Arial, sans-serif; background: #f5f5f5; padding: 20px; }}
  .card {{ background: white; border: 2px solid #cc0000; border-radius: 6px; padding: 24px; max-width: 700px; margin: auto; }}
  h2 {{ color: #cc0000; margin-top: 0; }}
  .field {{ margin: 10px 0; }}
  .label {{ font-weight: bold; color: #333; }}
  .value {{ color: #555; }}
  .screenshot {{ margin: 16px 0; }}
  .screenshot img {{ max-width: 100%; border: 1px solid #ccc; }}
  .actions {{ margin-top: 24px; }}
  button {{ padding: 10px 24px; font-size: 15px; border: none; border-radius: 4px; cursor: pointer; margin-right: 12px; }}
  .btn-resolve {{ background: #006600; color: white; }}
  .btn-abandon {{ background: #cc0000; color: white; }}
  .status-box {{ margin-top: 16px; padding: 12px; border-radius: 4px; background: #e8ffe8; border: 1px solid #006600; display: none; }}
  pre {{ background: #f0f0f0; padding: 10px; border-radius: 4px; font-size: 12px; overflow-x: auto; }}
</style>
</head>
<body>
<div class="card">
  <h2>Human Intervention Required</h2>
  <div class="field"><span class="label">Escalation ID:</span> <span class="value">{escalation_id}</span></div>
  <div class="field"><span class="label">Capability:</span> <span class="value">{capability_name}</span></div>
  <div class="field"><span class="label">Goal:</span> <span class="value">{goal}</span></div>
  <div class="field"><span class="label">Stopped at step:</span> <span class="value">{current_step}</span></div>
  <div class="field"><span class="label">Reason:</span> <span class="value">{reason}</span></div>
  <div class="field"><span class="label">Current URL:</span> <span class="value"><a href="{current_url}" target="_blank">{current_url}</a></span></div>
  <div class="field"><span class="label">Status:</span> <span class="value" id="status-text">{status}</span></div>
  {screenshot_block}
  <div class="actions">
    <button class="btn-resolve" onclick="resolve()">Mark Resolved — Hand Control Back</button>
    <button class="btn-abandon" onclick="abandon()">Abandon Run</button>
  </div>
  <div class="status-box" id="status-box">
    <b>Done.</b> You can close this window. The automation will resume.
  </div>
  <p style="font-size:12px;color:#999;margin-top:24px;">
    Open the browser session at the URL above to take manual control. When finished, click "Mark Resolved."
  </p>
</div>
<script>
  function resolve() {{
    fetch('/escalation/{escalation_id}/resolve', {{method: 'POST'}})
      .then(r => r.json())
      .then(() => {{
        document.getElementById('status-text').textContent = 'resolved';
        document.getElementById('status-box').style.display = 'block';
      }});
  }}
  function abandon() {{
    fetch('/escalation/{escalation_id}/abandon', {{method: 'POST'}})
      .then(r => r.json())
      .then(() => {{
        document.getElementById('status-text').textContent = 'abandoned';
        document.getElementById('status-box').style.display = 'block';
      }});
  }}
</script>
</body>
</html>
"""


class EscalationServer:
    def __init__(self, port: int = 8765):
        self.port = port
        self._server_thread: Optional[threading.Thread] = None
        self._app = None
        self._started = False

    def _create_app(self):
        from flask import Flask, jsonify, abort

        app = Flask("escalation_console")

        @app.route("/escalation/<esc_id>")
        def operator_page(esc_id):
            esc = ESCALATION_STORE.get(esc_id)
            if not esc:
                abort(404)
            screenshot_block = ""
            if esc.screenshot_path and os.path.exists(esc.screenshot_path):
                screenshot_block = f'<div class="screenshot"><p><b>Screenshot at time of escalation:</b></p><img src="/screenshot/{esc_id}"></div>'
            html = OPERATOR_PAGE.format(
                escalation_id=esc.id,
                capability_name=esc.capability_name,
                goal=esc.goal,
                current_step=esc.current_step,
                reason=esc.reason,
                current_url=esc.current_url or "",
                status=esc.status,
                screenshot_block=screenshot_block,
            )
            return html

        @app.route("/screenshot/<esc_id>")
        def serve_screenshot(esc_id):
            from flask import send_file
            esc = ESCALATION_STORE.get(esc_id)
            if not esc or not esc.screenshot_path:
                abort(404)
            return send_file(esc.screenshot_path, mimetype="image/png")

        @app.route("/escalation/<esc_id>/resolve", methods=["POST"])
        def resolve_escalation(esc_id):
            esc = ESCALATION_STORE.get(esc_id)
            if not esc:
                abort(404)
            esc.status = EscalationStatus.resolved
            esc.resolved_at = datetime.now(timezone.utc).isoformat()
            return jsonify({"status": "resolved"})

        @app.route("/escalation/<esc_id>/abandon", methods=["POST"])
        def abandon_escalation(esc_id):
            esc = ESCALATION_STORE.get(esc_id)
            if not esc:
                abort(404)
            esc.status = EscalationStatus.abandoned
            esc.resolved_at = datetime.now(timezone.utc).isoformat()
            return jsonify({"status": "abandoned"})

        @app.route("/escalation/<esc_id>/status")
        def escalation_status(esc_id):
            esc = ESCALATION_STORE.get(esc_id)
            if not esc:
                abort(404)
            return jsonify({"status": esc.status, "resolved_at": esc.resolved_at})

        self._app = app
        return app

    def start(self):
        if self._started:
            return
        app = self._create_app()

        def run_server():
            import logging
            log = logging.getLogger("werkzeug")
            log.setLevel(logging.ERROR)
            app.run(host="127.0.0.1", port=self.port, debug=False, use_reloader=False)

        self._server_thread = threading.Thread(target=run_server, daemon=True)
        self._server_thread.start()
        self._started = True
        time.sleep(0.8)

    def handle_escalation(self, escalation: EscalationRequest, timeout_seconds: int = 300) -> EscalationRequest:
        ESCALATION_STORE[escalation.id] = escalation
        url = f"http://127.0.0.1:{self.port}/escalation/{escalation.id}"
        print(f"\n[ESCALATION] Human intervention required.")
        print(f"[ESCALATION] Open operator console: {url}")
        print(f"[ESCALATION] Reason: {escalation.reason}")
        print(f"[ESCALATION] Waiting up to {timeout_seconds}s for human to resolve...\n")

        try:
            webbrowser.open(url)
        except Exception:
            pass

        deadline = time.time() + timeout_seconds
        while time.time() < deadline:
            esc = ESCALATION_STORE.get(escalation.id)
            if esc and esc.status in (EscalationStatus.resolved, EscalationStatus.abandoned):
                print(f"[ESCALATION] Status updated to: {esc.status}")
                return esc
            time.sleep(2)

        print("[ESCALATION] Timeout waiting for human. Marking as abandoned.")
        escalation.status = EscalationStatus.abandoned
        return escalation
