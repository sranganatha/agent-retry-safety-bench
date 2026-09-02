"""Command-line entry point for the deterministic baseline."""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from tempfile import TemporaryDirectory

from agent_retry_safety_bench.checkpoints import SQLiteCheckpointStore
from agent_retry_safety_bench.config import load_config
from agent_retry_safety_bench.ledger import SQLiteTicketLedger
from agent_retry_safety_bench.models import WorkflowResult
from agent_retry_safety_bench.recovery import run_with_recovery
from agent_retry_safety_bench.scenarios import load_scenario
from agent_retry_safety_bench.tools import DeterministicTools


def run_baseline() -> WorkflowResult:
    scenario = load_scenario("scenarios/baseline.yaml")
    with TemporaryDirectory() as directory:
        database_directory = Path(directory)
        checkpoints = SQLiteCheckpointStore(database_directory / "checkpoints.db")
        tools = DeterministicTools(
            load_config("config/demo.json"),
            SQLiteTicketLedger(database_directory / "tickets.db"),
        )
        return run_with_recovery(scenario, tools, checkpoints)


def main() -> None:
    print(json.dumps(asdict(run_baseline()), indent=2))


if __name__ == "__main__":
    main()
