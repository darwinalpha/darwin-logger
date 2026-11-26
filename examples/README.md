# Examples

[English](README.md) · [简体中文](README.cn.md)

All examples are runnable from the repository root:

```bash
uv run --no-project --python 3.12 --with darwin-logger python examples/01_basic.py
```

Or set `PYTHONPATH=src` when running without installation. Text examples write to stderr; the file-rotation example prints its generated filenames to stdout.

| Example | What it shows |
| --- | --- |
| `01_basic.py` | Minimal `configure_logging()` + `get_logger()` setup |
| `02_env.py` | Level and format from environment variables |
| `03_file_rotation.py` | Size-based rotation with `RotationConfig` |
| `04_json.py` | JSON output with `service`, `env`, context and `extra` |
| `05_context.py` | `bind_context()` / `clear_context()` in text logs |
| `06_cli.py` | A CLI entry point with a `--debug` switch |

`tests/integration/test_examples.py` executes every file and asserts a zero exit code.
