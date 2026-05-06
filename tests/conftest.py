from __future__ import annotations

from pathlib import Path
import os
import subprocess
import sys

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def run_command(args: list[str], *, cwd: Path, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        cwd=cwd,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def run_git(args: list[str], *, cwd: Path) -> subprocess.CompletedProcess[str]:
    result = run_command(["git", *args], cwd=cwd)
    assert result.returncode == 0, result.stderr
    return result


def init_repo(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    result = run_command(["git", "init", "-b", "main", str(path)], cwd=path.parent)
    if result.returncode != 0:
        result = run_command(["git", "init", str(path)], cwd=path.parent)
        assert result.returncode == 0, result.stderr
    run_git(["config", "user.email", "test@example.com"], cwd=path)
    run_git(["config", "user.name", "Test User"], cwd=path)
    (path / "README.md").write_text("# test repo\n", encoding="utf-8")
    run_git(["add", "README.md"], cwd=path)
    run_git(["commit", "-m", "initial"], cwd=path)
    return path


@pytest.fixture
def wt_env(tmp_path: Path) -> dict[str, str]:
    return {
        "PATH": os.environ.get("PATH", ""),
        "HOME": str(tmp_path / "home"),
        "PYTHONPATH": str(PROJECT_ROOT / "src"),
        "XDG_CONFIG_HOME": str(tmp_path / "xdg"),
    }


def run_wt(
    args: list[str],
    *,
    cwd: Path,
    env: dict[str, str],
) -> subprocess.CompletedProcess[str]:
    return run_command([sys.executable, "-m", "workthreads.cli", *args], cwd=cwd, env=env)
