"""Minimal setup: configure once at the application entry point."""

from darwin_logger import configure_logging, get_logger

configure_logging(level="INFO", use_color=False, from_env=False)

log = get_logger("basic")
log.debug("debug messages are hidden by default")
log.info("application started")
log.warning("disk usage is high")
