from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from typing import Any, Dict, Optional


class RunLogger:
    def __init__(self, run_id: str, log_dir: str = "evidence"):
        self.run_id = run_id
        self.log_dir = log_dir
        os.makedirs(log_dir, exist_ok=True)
        self.log_path = os.path.join(log_dir, f"{run_id}.jsonl")
        self._entries: list = []

    def _write(self, entry: Dict[str, Any]) -> None:
        entry["ts"] = datetime.now(timezone.utc).isoformat()
        entry["run_id"] = self.run_id
        self._entries.append(entry)
        with open(self.log_path, "a") as f:
            f.write(json.dumps(entry) + "\n")
        level = entry.get("level", "info").upper()
        msg = entry.get("msg", "")
        print(f"[{entry['ts']}] [{level}] {msg}", file=sys.stderr)

    def info(self, msg: str, **extra) -> None:
        self._write({"level": "info", "msg": msg, **extra})

    def warn(self, msg: str, **extra) -> None:
        self._write({"level": "warn", "msg": msg, **extra})

    def error(self, msg: str, **extra) -> None:
        self._write({"level": "error", "msg": msg, **extra})

    def step(self, index: int, action: str, description: str, success: bool, **extra) -> None:
        self._write({
            "level": "step",
            "msg": f"Step {index}: {action} — {description}",
            "step_index": index,
            "action": action,
            "description": description,
            "success": success,
            **extra,
        })

    def agent_reasoning(self, step: int, reasoning: str) -> None:
        self._write({
            "level": "agent",
            "msg": f"Agent reasoning at step {step}",
            "step": step,
            "reasoning": reasoning,
        })

    def escalation(self, escalation_id: str, reason: str) -> None:
        self._write({
            "level": "escalation",
            "msg": f"Escalation raised: {reason}",
            "escalation_id": escalation_id,
            "reason": reason,
        })

    def get_all(self) -> list:
        return list(self._entries)

    def save_summary(self, result: Dict[str, Any]) -> str:
        summary_path = os.path.join(self.log_dir, f"{self.run_id}_summary.json")
        with open(summary_path, "w") as f:
            json.dump(result, f, indent=2)
        return summary_path
