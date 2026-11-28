# darwin-logger

[English](https://github.com/darwinalpha/darwin-logger/blob/main/README.md) · [简体中文](https://github.com/darwinalpha/darwin-logger/blob/main/README.cn.md)

Zero-dependency structured logging for Darwin CLI tools and data scripts. It is a small configuration layer on top of the Python standard library `logging`: you still get ordinary `logging.Logger` objects, but setup, colors, file rotation and JSON output are handled in one place.

- **Zero core dependencies** — standard library only; `pytest` is a test extra
- **stderr by default** — safe for scripts, containers and cron jobs
- **Text by default, JSON on demand** — one environment flag makes logs ingestible by ELK, Loki and Datadog
- **Explicit reconfiguration** — `configure_logging()` is safe to call repeatedly; `reconfigure_logging()` rebuilds it
- **No import side effects** — `get_logger()` only returns a logger, it never mutates the root logger
- **Rotation and context built in** — size/time rotation and `contextvars`-based task context

Python >= 3.12.

```bash
pip install darwin-logger              # core
pip install 'darwin-logger[test]'      # with pytest
pip install 'darwin-logger[color]'     # optional Windows ANSI support
```

---

## 1. Quick start

```python
from darwin_logger import configure_logging, get_logger

configure_logging(level="INFO", use_color=False)

log = get_logger("demo")
log.debug("hidden by default")
log.info("application started")
```

Output goes to **stderr**:

```text
2026-11-26 13:40:00 [INFO] demo: application started
```

`get_logger()` is a pure function. Call `configure_logging()` once in your application entry point; library modules may call `get_logger(__name__)` at import time without changing global state.

---

## 2. JSON logs for observability

```bash
export LOG_JSON=1
export LOG_SERVICE=fetch
export LOG_ENV=prod
```

```python
from darwin_logger import bind_context, clear_context, configure_logging, get_logger

configure_logging()

token = bind_context(run_id="run-42", source="tushare")
try:
    get_logger("worker").info("job_done", extra={"rows": 120})
finally:
    clear_context(token)
```

One line per event:

```json
{
  "@timestamp": "2026-11-26T05:40:00.123Z",
  "level": "INFO",
  "logger": "worker",
  "message": "job_done",
  "service": "fetch",
  "env": "prod",
  "run_id": "run-42",
  "source": "tushare",
  "rows": 120
}
```

The field names are intentionally flat and generic: Loki/Promtail can parse the line as-is, Elasticsearch/OpenSearch can index it without a custom grok pattern, and Datadog accepts `level`, `message`, `service` and `@timestamp` directly. Add your own fields with `extra=` or `bind_context()`.

---

## 3. File output and rotation

```python
from pathlib import Path

from darwin_logger import RotationConfig, configure_logging, get_logger

configure_logging(
    level="INFO",
    file=Path("logs/app.log"),
    rotation=RotationConfig(kind="size", max_bytes=10 * 1024 ** 2, backup_count=5),
    stderr=False,
    from_env=False,
)

get_logger("file").info("persisted")
```

`kind="time"` uses the standard library `TimedRotatingFileHandler`:

```python
RotationConfig(kind="time", when="midnight", interval=1, backup_count=7)
```

The parent directory is created automatically. Handlers created by this library are closed and replaced on `reconfigure_logging()` and `reset_logging()`.

---

## 4. Environment variables

| Variable | Default | Meaning |
| --- | --- | --- |
| `LOG_LEVEL` | `INFO` | Root level; names or integers. Invalid values raise `InvalidLevelError` |
| `LOG_FORMAT` | built-in text format | `%`-style format for text output |
| `LOG_DATE_FORMAT` | `%Y-%m-%d %H:%M:%S` | Date format for text output |
| `LOG_JSON` | `0` | `1/true/yes/on` enables JSON output |
| `LOG_STDERR` | `1` | `0/false/no/off` disables the stderr handler |
| `LOG_FILE` | unset | Enable a UTF-8 file handler at this path |
| `LOG_ROTATE` | unset | `size` or `time` |
| `LOG_MAX_BYTES` | `10MB` | Size threshold when `LOG_ROTATE=size` |
| `LOG_BACKUP_COUNT` | `5` | Number of rotated files to keep |
| `LOG_ROTATE_WHEN` | `midnight` | `S/M/H/D/W0..W6/MIDNIGHT` when `LOG_ROTATE=time` |
| `LOG_ROTATE_INTERVAL` | `1` | Rotation interval when `LOG_ROTATE=time` |
| `LOG_SERVICE` | unset | Adds `service` to JSON output |
| `LOG_ENV` | unset | Adds `env` to JSON output |
| `NO_COLOR` | unset | Disable colors regardless of value |
| `FORCE_COLOR` | unset | Force colors; `NO_COLOR` still wins |
| `DARWIN_COLOR` | unset | Legacy alias with truthy values `1/true/yes/on` |

Explicit arguments override environment variables. An already-active configuration is returned unchanged unless you pass `force=True` or call `reconfigure_logging()`.

---

## 5. API at a glance

```python
from darwin_logger import (
    configure_logging,
    reconfigure_logging,
    reset_logging,
    is_configured,
    config_from_env,
    get_logger,
    set_log_level,
    set_logger_level,
    get_logging_config,
    get_logger_config,
    bind_context,
    clear_context,
    get_context,
    ConsoleFormatter,
    JsonFormatter,
    LoggingConfig,
    RotationConfig,
)
```

| Function | Purpose |
| --- | --- |
| `configure_logging(**kwargs)` | Initial setup; repeat calls are no-ops unless `force=True` |
| `reconfigure_logging(**kwargs)` | Rebuild handlers and replace the active configuration |
| `reset_logging()` | Restore root/named logger levels and close owned handlers |
| `get_logger(name="")` | Return a standard `logging.Logger`; no side effects |
| `set_log_level(level)` | Change the root level at runtime |
| `set_logger_level(name, level)` | Change one named logger; restored by `reset_logging()` |
| `bind_context(**fields)` | Bind context fields to the current async task |
| `get_logging_config()` | Inspect the active setup as a dictionary |

Invalid levels raise `InvalidLevelError`; invalid boolean or rotation settings raise `ConfigurationError`; file sink failures raise `SinkError`. All derive from `DarwinLoggerError`.

---

## 6. Colors

Text format supports two optional placeholders:

```python
"%(log_color)s%(levelname)s%(reset)s %(message)s"
```

When colors are off, both placeholders expand to empty strings. Color resolution order is: explicit `use_color` > `NO_COLOR` > `FORCE_COLOR` > `DARWIN_COLOR` > stream `isatty()`. JSON output never contains ANSI codes.

---

## 7. Testing

```bash
uv run --extra test python -m pytest tests -q
```

The suite covers unit behavior, stderr/file/JSON integration, executed examples, zero third-party imports, stable exports and bilingual documentation. See `docs/development-guide.md` for architecture details and `examples/` for runnable scripts.

---

## 8. License

MIT. See [LICENSE](LICENSE).
