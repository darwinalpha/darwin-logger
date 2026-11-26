# 示例

English · [简体中文](README.cn.md)

所有示例都可从仓库根目录直接运行：

```bash
uv run --no-project --python 3.12 --with darwin-logger python examples/01_basic.py
```

未安装时也可以设置 `PYTHONPATH=src` 运行。文本示例写入 stderr；文件轮转示例把生成的文件名打印到 stdout。

| 示例 | 演示内容 |
| --- | --- |
| `01_basic.py` | 最小 `configure_logging()` + `get_logger()` 用法 |
| `02_env.py` | 从环境变量读取级别与格式 |
| `03_file_rotation.py` | 用 `RotationConfig` 做文件大小轮转 |
| `04_json.py` | 带 `service`、`env`、上下文与 `extra` 的 JSON 输出 |
| `05_context.py` | 文本日志中的 `bind_context()` / `clear_context()` |
| `06_cli.py` | 带 `--debug` 开关的 CLI 入口 |

`tests/integration/test_examples.py` 会执行每个文件并断言退出码为 0。
