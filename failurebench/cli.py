"""Command-line entry point for the deterministic baseline."""

from __future__ import annotations

import json
from dataclasses import asdict

from failurebench.config import load_config
from failurebench.models import IncidentRequest, WorkflowResult
from failurebench.tools import DeterministicTools
from failurebench.workflow import MaintenanceWorkflow


def run_baseline() -> WorkflowResult:
    tools = DeterministicTools(load_config("config/demo.json"))
    request = IncidentRequest(
        workflow_id="wf-123",
        equipment_id="etch-101",
        alarm_code="TEMP_HIGH",
        idempotency_key="wf-123:create-ticket",
    )
    return MaintenanceWorkflow(tools).run(request)


def main() -> None:
    print(json.dumps(asdict(run_baseline()), indent=2))


if __name__ == "__main__":
    main()
