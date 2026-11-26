"""Bind task context and see it appended to text logs."""

from darwin_logger import bind_context, clear_context, configure_logging, get_logger

configure_logging(level="INFO", fmt="%(message)s", use_color=False, from_env=False)

log = get_logger("task")
token = bind_context(run_id="run-7", source="tushare")
try:
    log.info("fetch_started")
finally:
    clear_context(token)
log.info("fetch_finished")
