"""Project paths and configuration loading."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]


class ConfigError(RuntimeError):
    """Raised when configuration files are missing or invalid."""


@dataclass(frozen=True)
class Paths:
    """All filesystem locations used by the pipeline."""

    root: Path = PROJECT_ROOT

    @property
    def raw(self) -> Path:
        return self.root / "data" / "raw"

    @property
    def processed(self) -> Path:
        return self.root / "data" / "processed"

    @property
    def dashboard_data(self) -> Path:
        return self.root / "data" / "dashboard"

    @property
    def config(self) -> Path:
        return self.root / "config"


@dataclass
class Settings:
    """Typed accessor around ``config/settings.json``."""

    raw: dict[str, Any]
    countries: dict[str, str | None]
    bowler_types: dict[tuple[str, str], str] = field(default_factory=dict)

    def __getitem__(self, key: str) -> Any:
        return self.raw[key]

    @property
    def genders(self) -> dict[str, dict[str, str]]:
        return self.raw["genders"]

    @property
    def phases(self) -> dict[str, dict[str, Any]]:
        return self.raw["phases"]

    @property
    def credited_kinds(self) -> set[str]:
        return {k.lower() for k in self.raw["dismissals"]["bowler_credited"]}

    @property
    def not_out_kinds(self) -> set[str]:
        return {k.lower() for k in self.raw["dismissals"]["not_out_kinds"]}

    def phase_of_over(self, over: int) -> str:
        for key, spec in self.phases.items():
            if spec["first_over"] <= over <= spec["last_over"]:
                return key
        return "death" if over > 20 else "powerplay"

    def position_group(self, pos: int) -> str:
        for key, spec in self.raw["position_groups"].items():
            if pos in spec["positions"]:
                return key
        return "lower"


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise ConfigError(f"Missing configuration file: {path}")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:  # pragma: no cover - defensive
        raise ConfigError(f"Invalid JSON in {path}: {exc}") from exc


def load_settings(paths: Paths | None = None) -> Settings:
    """Load settings, the national-team list and optional bowler types."""
    paths = paths or Paths()
    raw = _read_json(paths.config / "settings.json")
    countries = {k: v for k, v in _read_json(paths.config / "countries.json").items() if not k.startswith("_")}
    bowler_types: dict[tuple[str, str], str] = {}
    bt_path = paths.config / "bowler_types.csv"
    if bt_path.exists():
        import csv

        with bt_path.open(encoding="utf-8-sig", newline="") as fh:
            for row in csv.DictReader(fh):
                g, p, t = (row.get("gender") or "").strip(), (row.get("player") or "").strip(), (row.get("bowling_type") or "").strip().lower()
                if g and p and t in {"spin", "pace"}:
                    bowler_types[(g, p)] = t
    return Settings(raw=raw, countries=countries, bowler_types=bowler_types)
