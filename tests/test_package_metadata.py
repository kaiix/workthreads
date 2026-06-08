import tomllib
from pathlib import Path

import workthreads


def test_package_versions_match() -> None:
    pyproject = tomllib.loads(Path("pyproject.toml").read_text())

    assert workthreads.__version__ == pyproject["project"]["version"]
