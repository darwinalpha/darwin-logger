"""Write UTF-8 log files with size-based rotation."""

import tempfile
from pathlib import Path

from darwin_logger import RotationConfig, configure_logging, get_logger, reset_logging

with tempfile.TemporaryDirectory() as directory:
    target = Path(directory) / "app.log"
    configure_logging(
        level="INFO",
        fmt="%(message)s",
        file=target,
        rotation=RotationConfig(kind="size", max_bytes=200, backup_count=2),
        stderr=False,
        from_env=False,
    )
    for index in range(20):
        get_logger("rotate").info("record-%03d-payload", index)

    names = sorted(path.name for path in Path(directory).glob("app.log*"))
    reset_logging()
    print("rotated files:", ", ".join(names))
