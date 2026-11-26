"""Integration tests that execute every shipped example."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
EXAMPLES = sorted((ROOT / "examples").glob("*.py"))
ENV_KEYS = [
    "LOG_LEVEL", "LOG_FORMAT", "LOG_DATE_FORMAT", "LOG_JSON", "LOG_STDERR", "LOG_FILE",
    "LOG_ROTATE", "LOG_MAX_BYTES", "LOG_BACKUP_COUNT", "LOG_ROTATE_WHEN",
    "LOG_ROTATE_INTERVAL", "LOG_SERVICE", "LOG_ENV", "NO_COLOR", "FORCE_COLOR", "DARWIN_COLOR",
]


@pytest.mark.parametrize("example", EXAMPLES, ids=lambda path: path.name)
def test_example_runs(example: Path) -> None:
    env = {key: value for key, value in os.environ.items() if key not in ENV_KEYS}
    env["PYTHONPATH"] = str(ROOT / "src")
    result = subprocess.run(
        [sys.executable, str(example)],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout or result.stderr
