"""Emit single-line JSON logs for ELK, Loki and Datadog."""

from darwin_logger import bind_context, clear_context, configure_logging, get_logger

configure_logging(
    level="INFO",
    json=True,
    service="fetch",
    env="example",
    from_env=False,
)

token = bind_context(run_id="demo-1", source="tushare")
try:
    get_logger("worker").info("job_done", extra={"rows": 120})
finally:
    clear_context(token)
