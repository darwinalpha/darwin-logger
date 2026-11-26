# darwin-logger development guide

[English](development-guide.md) · [简体中文](development-guide.cn.md)

Version: 0.1.0 · Python >= 3.12

---

## 1. Scope

`darwin-logger` is a **configuration layer**, not a replacement for the standard library `logging` module. It owns:

- the root logger setup (handlers, level, formatter selection)
- stderr and UTF-8 file sinks, with optional size/time rotation
- a console formatter with placeholder-based colors and context suffix
- a single-line JSON formatter for log collectors
- optional task context via `contextvars`

It deliberately does **not** own:

- a custom logger class — `get_logger()` returns `logging.Logger`
- structured event dictionaries — use `extra=` and `bind_context()` instead
- async queue handlers — useful for long-running services, out of scope for CLI/data scripts
- `.env` loading — the caller controls the process environment

---

## 2. Package layout

```text
src/darwin_logger/
├── __init__.py       # public API and version
├── core.py           # config state, env parsing, setup/reset API
├── formatters.py     # ConsoleFormatter, JsonFormatter, color resolution
├── sinks.py          # handler factories and RotationConfig
├── context.py        # contextvars bindings
├── exceptions.py     # exception hierarchy
└── py.typed          # PEP 561 marker
```

Dependency direction is one-way: `core` imports `formatters`, `sinks` and `context`; `formatters` imports `context`; `sinks` imports `exceptions`. There are no third-party imports.

---

## 3. State machine

```text
                configure_logging()  (first call)
    UNCONFIGURED ─────────────────────────────────► CONFIGURED
         ▲                                              │
         │                                              │ reconfigure_logging()
         │ reset_logging()                              │ or configure_logging(force=True)
         └──────────────────────────────────────────────┘
```

`configure_logging()` has three important properties:

1. **Idempotent by default.** If a configuration exists, the active `LoggingConfig` is returned unchanged. Even explicit arguments are ignored. This prevents accidental partial updates from library imports.
2. **Explicit rebuild.** `reconfigure_logging(**kwargs)` is exactly `configure_logging(force=True, **kwargs)`. Handlers owned by the library are removed and closed before the new ones are installed.
3. **Handler ownership.** Only handlers created by this library are removed on rebuild/reset. If `replace_existing=True` is passed, unrelated root handlers are displaced and restored on reset.

`reset_logging()` restores the root level captured before the first setup and restores any levels changed through `set_logger_level()`. It does not clear `manager.loggerDict` and does not touch handlers attached directly to named loggers.

All mutations are guarded by a module-level `threading.RLock()`.

---

## 4. Configuration resolution

```text
environment variables ──► LoggingConfig ──► explicit kwargs override ──► _install()
```

`config_from_env()` reads all supported variables and validates them immediately:

- `LOG_LEVEL` uses `normalize_level()`: a name is looked up via `logging` attributes and `logging.getLevelName()`; invalid values raise `InvalidLevelError` instead of silently falling back to `INFO`.
- Boolean flags accept `1/true/yes/on` and `0/false/no/off` (case-insensitive); anything else raises `ConfigurationError`.
- `LOG_MAX_BYTES` accepts `B/KB/MB/GB` suffixes and converts to bytes.
- `LOG_FORMAT=""` is respected as an empty format instead of falling back to the default.
- `use_color` is never read from the environment in `core`; the formatter resolves it from `NO_COLOR`, `FORCE_COLOR`, `DARWIN_COLOR` and `isatty()`.

`LoggingConfig` is a frozen dataclass. `to_dict()` uses `dataclasses.asdict()` and returns a JSON-serializable snapshot, including nested `RotationConfig`.

---

## 5. Formatters

### 5.1 ConsoleFormatter

The default text format is:

```python
"%(log_color)s%(asctime)s [%(levelname)s] %(name)s%(reset)s: %(message)s"
```

Colors are injected by temporarily setting `record.log_color` and `record.reset` before calling `logging.Formatter.format()`, then removing the temporary attributes. This avoids rewriting the formatted string and is safe for custom formats that do not include the color placeholders.

Color resolution order:

1. explicit `use_color`
2. `NO_COLOR` — presence alone disables colors
3. `FORCE_COLOR` — truthy value enables colors
4. `DARWIN_COLOR` — legacy alias with the same truthy values
5. `stream.isatty()`

Context fields are appended as ` key=value` pairs. With colors off, the output contains no ANSI sequences even when the placeholders remain in the format string.

### 5.2 JsonFormatter

Each record becomes one JSON object:

| Field | Source |
| --- | --- |
| `@timestamp` | `record.created`, UTC, millisecond precision, `Z` suffix |
| `level` | `record.levelname` |
| `logger` | `record.name` |
| `message` | `record.getMessage()` |
| `service` / `env` | `LOG_SERVICE` / `LOG_ENV` or explicit kwargs |
| context fields | `get_context()` |
| extra fields | custom attributes on the `LogRecord` |
| `exception` / `stack` | formatted traceback / stack info |

Reserved keys cannot be overridden by `extra` or context. Non-serializable values are converted with `default=str`. ANSI codes are never emitted.

---

## 6. Sinks

`create_console_handler(stream, formatter)` wraps `logging.StreamHandler`. The library binds `sys.stderr` at configuration time, so tests using `capsys` should assert on `captured.err`.

`create_file_handler(path, rotation)`:

- creates parent directories automatically
- uses `FileHandler` when `rotation` is unset
- uses `RotatingFileHandler` for `kind="size"`
- uses `TimedRotatingFileHandler` for `kind="time"`
- raises `SinkError` on invalid configuration or filesystem errors

File handlers use UTF-8 encoding. Rebuilding closes the old handler before opening the new one.

---

## 7. Context

`bind_context(**fields)` stores fields in a `ContextVar` and returns a reset token. `clear_context(token)` restores the previous mapping; `clear_context()` clears it outright.

The context is read by both formatters at formatting time, so:

- text logs append `run_id=... source=...`
- JSON logs promote the same fields to top-level keys

This is asyncio-safe: each task sees its own context mapping.

---

## 8. Public API contract

Exported from `darwin_logger`:

- setup: `configure_logging`, `reconfigure_logging`, `reset_logging`, `is_configured`, `config_from_env`
- loggers: `get_logger`, `set_log_level`, `set_logger_level`
- introspection: `get_logging_config`, `get_logger_config`
- context: `bind_context`, `clear_context`, `get_context`
- types: `LoggingConfig`, `RotationConfig`, `ConsoleFormatter`, `JsonFormatter`
- helpers: `normalize_level`
- exceptions: `DarwinLoggerError`, `ConfigurationError`, `InvalidLevelError`, `SinkError`

`setup_logger` and other legacy names are intentionally absent. Contract tests assert both the presence of the export list and the absence of removed symbols.

---

## 9. Testing

```bash
uv run --extra test python -m pytest tests -q
```

| Directory | Purpose |
| --- | --- |
| `tests/unit/` | level validation, state machine, env parsing, formatters, sinks, context |
| `tests/integration/` | stderr output, JSON parsing, file rotation, reconfiguration, executed examples |
| `tests/contract/` | zero third-party imports, export list, bilingual documentation |

The shared `clean_logging` fixture is autouse and calls `reset_logging()` before and after every test. The `clean_env` fixture properly removes variables that were introduced during a test — unlike the old implementation that leaked `LOG_FILE` into later cases.

---

## 10. Migration notes

There is no compatibility layer. Key differences from the old `darwin_common.logging` module:

| Old behavior | New behavior |
| --- | --- |
| `get_logger()` auto-configured the root logger | `get_logger()` is pure; call `configure_logging()` in the entry point |
| Second `configure_logging()` only changed the level | Second call is a no-op; use `reconfigure_logging()` |
| `setup_logger` alias | Removed |
| Invalid level silently became `INFO` | `InvalidLevelError` is raised |
| `NO_COLOR` presence enabled/disabled by value | Presence alone disables colors |
| Always `StreamHandler(sys.stderr)` | stderr can be disabled with `LOG_STDERR=0` |
| Single `FileHandler`, no rotation | Size/time rotation supported |
| No structured output | `LOG_JSON=1` enables collector-friendly JSON |
| Cleared all root handlers | Only library-owned handlers are removed by default |
