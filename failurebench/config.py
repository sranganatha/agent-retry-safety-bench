"""Load deterministic benchmark fixtures."""

from __future__ import annotations

import json
import math
import sys
from dataclasses import dataclass
from pathlib import Path


class ConfigError(ValueError):
    """Raised when benchmark fixtures do not match the supported contract."""


@dataclass(frozen=True, slots=True)
class Equipment:
    id: str
    temperature_c: float
    alarms: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class BenchmarkConfig:
    version: int
    equipment: tuple[Equipment, ...]


def _equipment_from(raw: object) -> Equipment:
    if not isinstance(raw, dict) or set(raw) != {"id", "temperature_c", "alarms"}:
        raise ConfigError("equipment must contain id, temperature_c, and alarms")

    equipment_id = raw["id"]
    temperature = raw["temperature_c"]
    alarms = raw["alarms"]
    if not isinstance(equipment_id, str) or not equipment_id.strip():
        raise ConfigError("equipment id must be a non-empty string")
    if (
        isinstance(temperature, bool)
        or not isinstance(temperature, (int, float))
        or not math.isfinite(temperature)
    ):
        raise ConfigError("equipment temperature_c must be a finite number")
    if (
        not isinstance(alarms, list)
        or any(not isinstance(alarm, str) or not alarm.strip() for alarm in alarms)
        or len(alarms) != len(set(alarms))
    ):
        raise ConfigError("equipment alarms must be unique non-empty strings")

    return Equipment(equipment_id, float(temperature), tuple(alarms))


def parse_config(raw: object) -> BenchmarkConfig:
    if not isinstance(raw, dict) or set(raw) != {"version", "equipment"}:
        raise ConfigError("config must contain version and equipment")
    if raw["version"] != 1:
        raise ConfigError("unsupported config version")
    if not isinstance(raw["equipment"], list) or not raw["equipment"]:
        raise ConfigError("config equipment must be a non-empty list")

    equipment = tuple(_equipment_from(item) for item in raw["equipment"])
    equipment_ids = [item.id for item in equipment]
    if len(equipment_ids) != len(set(equipment_ids)):
        raise ConfigError("duplicate equipment id")
    return BenchmarkConfig(version=1, equipment=equipment)


def load_config(path: str | Path) -> BenchmarkConfig:
    try:
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ConfigError(f"invalid fixture file: {error}") from error
    return parse_config(raw)


def main() -> None:
    path = sys.argv[1] if len(sys.argv) > 1 else "config/demo.json"
    config = load_config(path)
    print(f"loaded fixture v{config.version}: {len(config.equipment)} equipment records")


if __name__ == "__main__":
    main()
