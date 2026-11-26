"""A small CLI entry point with a --debug switch."""

import argparse

from darwin_logger import configure_logging, get_logger, set_log_level

parser = argparse.ArgumentParser(description="darwin-logger CLI example")
parser.add_argument("--debug", action="store_true", help="enable debug output")
args = parser.parse_args()

configure_logging(
    level="INFO",
    fmt="%(levelname)s %(name)s %(message)s",
    use_color=False,
    from_env=False,
)
log = get_logger("cli")

if args.debug:
    set_log_level("DEBUG")

log.info("command started")
log.debug("debug details")
