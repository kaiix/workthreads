from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
import os
import tomllib

from .errors import UsageError


REPO_CONFIG_FILENAME = "workthreads.toml"
LEGACY_REPO_CONFIG = Path(".workthreads") / "config.toml"


BUILTIN_CONFIG: dict[str, dict[str, object]] = {
    "defaults": {
        "worktreesDir": "../workthreads",
        "base": None,
        "fetch": False,
        "copyLocal": False,
        "deleteBranch": False,
    },
    "hooks": {
        "postCreate": None,
        "preDelete": None,
        "shell": None,
        "timeoutSeconds": 0,
    },
    "shell": {
        "cdAfterAdd": False,
    },
}


@dataclass
class Config:
    values: dict[str, object]
    repo_root: Path | None = None

    @property
    def repo_config_path(self) -> Path | None:
        if self.repo_root is None:
            return None
        return repo_config_path(self.repo_root)

    def get(self, key: str, default: object = None) -> object:
        try:
            return get_nested(self.values, key)
        except KeyError:
            return default

    def get_str(self, key: str) -> str | None:
        value = self.get(key)
        return value if isinstance(value, str) and value else None

    def get_bool(self, key: str) -> bool:
        return bool(self.get(key, False))

    def get_int(self, key: str) -> int:
        value = self.get(key, 0)
        return int(value) if isinstance(value, int | str) and str(value).isdigit() else 0


def global_config_path() -> Path:
    config_home = os.environ.get("XDG_CONFIG_HOME")
    if config_home:
        return Path(config_home) / "workthreads" / "config.toml"
    return Path.home() / ".config" / "workthreads" / "config.toml"


def load_config(repo_root: Path | None = None) -> Config:
    values = deepcopy(BUILTIN_CONFIG)
    repo_paths: tuple[Path | None, ...] = ()
    if repo_root:
        repo_paths = (legacy_repo_config_path(repo_root), repo_config_path(repo_root))
    for path in (global_config_path(), *repo_paths):
        if path is None or not path.exists():
            continue
        merge_dict(values, read_toml(path))
    return Config(values=values, repo_root=repo_root)


def repo_config_path(repo_root: Path) -> Path:
    return repo_root / REPO_CONFIG_FILENAME


def legacy_repo_config_path(repo_root: Path) -> Path:
    return repo_root / LEGACY_REPO_CONFIG


def read_toml(path: Path) -> dict[str, object]:
    with path.open("rb") as file:
        return tomllib.load(file)


def merge_dict(base: dict[str, object], override: dict[str, object]) -> None:
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            merge_dict(base[key], value)  # type: ignore[index]
        else:
            base[key] = value


def get_nested(values: dict[str, object], key: str) -> object:
    current: object = values
    for part in key.split("."):
        if not isinstance(current, dict) or part not in current:
            raise KeyError(key)
        current = current[part]
    return current


def set_nested(values: dict[str, object], key: str, value: object) -> None:
    current: dict[str, object] = values
    parts = key.split(".")
    for part in parts[:-1]:
        next_value = current.setdefault(part, {})
        if not isinstance(next_value, dict):
            raise UsageError(f"cannot set nested key under non-table value: {part}")
        current = next_value
    current[parts[-1]] = value


def unset_nested(values: dict[str, object], key: str) -> None:
    current: dict[str, object] = values
    parts = key.split(".")
    for part in parts[:-1]:
        next_value = current.get(part)
        if not isinstance(next_value, dict):
            raise UsageError(f"unknown config key: {key}")
        current = next_value
    if parts[-1] not in current:
        raise UsageError(f"unknown config key: {key}")
    del current[parts[-1]]


def parse_config_value(raw: str) -> object:
    lowered = raw.lower()
    if lowered == "true":
        return True
    if lowered == "false":
        return False
    if raw.isdigit():
        return int(raw)
    return raw


def write_config_file(path: Path, values: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(dump_toml(values), encoding="utf-8")


def dump_toml(values: dict[str, object]) -> str:
    lines: list[str] = []
    for section, section_values in values.items():
        if not isinstance(section_values, dict):
            continue
        visible_items = {key: value for key, value in section_values.items() if value is not None}
        if not visible_items:
            continue
        if lines:
            lines.append("")
        lines.append(f"[{section}]")
        for key, value in visible_items.items():
            lines.append(f"{key} = {format_toml_value(value)}")
    return "\n".join(lines) + "\n"


def format_toml_value(value: object) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    escaped = str(value).replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def writable_config_path(repo_root: Path | None) -> Path:
    if repo_root is not None:
        return repo_config_path(repo_root)
    return global_config_path()
