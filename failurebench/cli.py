"""Command-line entry point for the deterministic baseline."""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from tempfile import TemporaryDirectory

from failurebench.checkpoints import SQLiteCheckpointStore
from failurebench.config import load_config
from failurebench.ledger import SQLiteTicketLedger
from failurebench.models import WorkflowResult
from failurebench.recovery import run_with_recovery
from failurebench.scenarios import load_scenario
from failurebench.tools import DeterministicTools


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
