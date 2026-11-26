"""Configure entirely from environment variables."""

import os

from darwin_logger import configure_logging, get_logger

os.environ["LOG_LEVEL"] = "DEBUG"
os.environ["LOG_FORMAT"] = "%(levelname)s %(name)s %(message)s"
os.environ["LOG_STDERR"] = "1"

configure_logging(use_color=False)

log = get_logger("env")
log.debug("level and format came from the environment")
