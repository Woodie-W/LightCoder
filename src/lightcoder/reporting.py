from __future__ import annotations

from collections import Counter
from datetime import datetime
import json
from pathlib import Path
from typing import Any

from .evaluation import evaluation_summary
from .store import StateStore


def build_run_report(store: StateStore) -> dict[str, Any]:
    state = store.load()
    evidence = store.evidence()
    commands = [item for item in evidence if item.kind == "command"]
    work_statuses = Counter(item.status for item in state.work_items)
    mandatory = [item for item in state.work_items if item.mandatory]
    created = datetime.fromisoformat(state.created_at)
    updated = datetime.fromisoformat(state.updated_at)
    usage: Counter[str] = Counter()
    successful_model_responses = 0
    managed_config = state.runtime_config.get("managed_evaluation", {})
    managed_evaluation = (
        evaluation_summary(
            Path(state.workspace), Path(str(managed_config["store"]))
        )
        if isinstance(managed_config, dict)
        and managed_config.get("enabled")
        and managed_config.get("store")
        else None
    )
    if store.transcript_path.is_file():
        for line in store.transcript_path.read_text(
            encoding="utf-8", errors="replace"
        ).splitlines():
            try:
                value = json.loads(line)
            except json.JSONDecodeError:
                continue
            metadata = value.get("metadata", {})
            response_usage = metadata.get("usage", {})
            if value.get("role") != "assistant" or not isinstance(response_usage, dict):
                continue
            successful_model_responses += 1
            for key, amount in response_usage.items():
                if isinstance(amount, int):
                    usage[str(key)] += amount
    return {
        "schema_version": 1,
        "run_id": state.run_id,
        "status": state.status,
        "phase": state.phase,
        "objective": state.objective,
        "execution_regime": state.profile.execution_regime if state.profile else None,
        "primary_playbook": state.profile.primary_playbook if state.profile else None,
        "control_mode": "flat"
        if state.profile and state.profile.execution_regime == "long_horizon"
        else "work_graph",
        "ablations": state.runtime_config.get("ablations", []),
        "elapsed_seconds": max(0.0, (updated - created).total_seconds()),
        "configured_wall_time_seconds": state.deadline.wall_time_seconds,
        "model_calls": state.counters.get("model_calls", 0),
        "successful_model_responses": successful_model_responses,
        "token_usage": dict(sorted(usage.items())),
        "invalid_actions": state.counters.get("invalid_actions", 0),
        "context_episodes": len(state.episodes),
        "context_rotations": max(0, len(state.episodes) - 1),
        "work_items": dict(sorted(work_statuses.items())),
        "mandatory_total": len(mandatory),
        "mandatory_accepted": sum(item.status == "accepted" for item in mandatory),
        "attempts": sum(item.attempt_count for item in state.work_items),
        "failure_signatures": sum(
            len(item.failure_signatures) for item in state.work_items
        ),
        "evidence_records": len(evidence),
        "commands": len(commands),
        "commands_passed": sum(item.exit_code == 0 for item in commands),
        "commands_failed": sum(item.exit_code not in {0, None} for item in commands),
        "command_duration_seconds": sum(item.duration_seconds for item in commands),
        "best_checkpoint_id": state.best_checkpoint_id,
        "managed_evaluation": managed_evaluation,
        "final": state.final,
    }
