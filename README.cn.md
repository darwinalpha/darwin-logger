# darwin-logger

[English](https://github.com/darwinalpha/darwin-logger/blob/main/README.md) · 简体中文

面向 Darwin CLI 工具与数据脚本的零依赖结构化日志库。它是在 Python 标准库 `logging` 之上的一层很薄的配置层：你拿到的仍是标准 `logging.Logger`，但初始化、颜色、文件轮转与 JSON 输出都集中在一处处理。

- **核心零依赖**：只用标准库；`pytest` 是 test extra
- **默认写 stderr**：脚本、容器、cron 场景都安全
- **默认文本，JSON 可开**：一个环境变量即可让日志被 ELK、Loki、Datadog 消费
- **重配置语义明确**：`configure_logging()` 可重复调用；`reconfigure_logging()` 显式重建
- **导入零副作用**：`get_logger()` 只返回 logger，不改 root
- **内置轮转与上下文**：文件大小/时间轮转，以及基于 `contextvars` 的任务上下文

Python ≥ 3.12。

```bash
pip install darwin-logger              # 核心
pip install 'darwin-logger[test]'      # 含 pytest
pip install 'darwin-logger[color]'     # Windows ANSI 可选支持
```

---

## 1. 快速开始

```python
from darwin_logger import configure_logging, get_logger

configure_logging(level="INFO", use_color=False)

log = get_logger("demo")
log.debug("默认不输出")
log.info("application started")
```

输出写入 **stderr**：

```text
2026-11-26 13:40:00 [INFO] demo: application started
```

`get_logger()` 是纯函数。应用入口调用一次 `configure_logging()`；库模块可在导入时安全地写 `get_logger(__name__)`，不会改变全局状态。

---

## 2. 面向可观测性的 JSON 日志

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

每条日志一行 JSON：

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

字段刻意保持扁平通用：Loki/Promtail 可直接解析，Elasticsearch/OpenSearch 无需 grok 模式，Datadog 直接识别 `level` / `message` / `service` / `@timestamp`。可用 `extra=` 或 `bind_context()` 追加自己的字段。

---

## 3. 文件输出与轮转

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

`kind="time"` 使用标准库 `TimedRotatingFileHandler`：

```python
RotationConfig(kind="time", when="midnight", interval=1, backup_count=7)
```

父目录会自动创建。`reconfigure_logging()` 与 `reset_logging()` 会关闭并替换本库创建的 handler。

---

## 4. 环境变量

| 变量 | 默认值 | 含义 |
| --- | --- | --- |
| `LOG_LEVEL` | `INFO` | root 级别，支持名称或整数；非法值抛 `InvalidLevelError` |
| `LOG_FORMAT` | 内置文本格式 | 文本输出的 `%` 风格格式串 |
| `LOG_DATE_FORMAT` | `%Y-%m-%d %H:%M:%S` | 文本输出日期格式 |
| `LOG_JSON` | `0` | `1/true/yes/on` 开启 JSON 输出 |
| `LOG_STDERR` | `1` | `0/false/no/off` 关闭 stderr handler |
| `LOG_FILE` | 未设置 | 启用该路径的 UTF-8 文件 handler |
| `LOG_ROTATE` | 未设置 | `size` 或 `time` |
| `LOG_MAX_BYTES` | `10MB` | `LOG_ROTATE=size` 时的大小阈值 |
| `LOG_BACKUP_COUNT` | `5` | 保留的轮转文件数 |
| `LOG_ROTATE_WHEN` | `midnight` | `LOG_ROTATE=time` 时可选 `S/M/H/D/W0..W6/MIDNIGHT` |
| `LOG_ROTATE_INTERVAL` | `1` | `LOG_ROTATE=time` 时的间隔 |
| `LOG_SERVICE` | 未设置 | JSON 中追加 `service` 字段 |
| `LOG_ENV` | 未设置 | JSON 中追加 `env` 字段 |
| `NO_COLOR` | 未设置 | 只要存在就禁用颜色 |
| `FORCE_COLOR` | 未设置 | 强制颜色；`NO_COLOR` 仍优先 |
| `DARWIN_COLOR` | 未设置 | 兼容旧变量，真值为 `1/true/yes/on` |

显式参数优先于环境变量。已生效的配置保持不变，除非传 `force=True` 或调用 `reconfigure_logging()`。

---

## 5. API 一览

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

| 函数 | 作用 |
| --- | --- |
| `configure_logging(**kwargs)` | 首次配置；重复调用默认不生效，除非 `force=True` |
| `reconfigure_logging(**kwargs)` | 重建 handler 并替换当前配置 |
| `reset_logging()` | 恢复 root / 命名 logger 级别并关闭自有 handler |
| `get_logger(name="")` | 返回标准 `logging.Logger`，无副作用 |
| `set_log_level(level)` | 运行期改 root 级别 |
| `set_logger_level(name, level)` | 改单个 logger，`reset_logging()` 可恢复 |
| `bind_context(**fields)` | 给当前异步任务绑定上下文字段 |
| `get_logging_config()` | 以字典形式查看当前配置 |

非法级别抛 `InvalidLevelError`；非法布尔/轮转配置抛 `ConfigurationError`；文件 sink 失败抛 `SinkError`。它们都继承 `DarwinLoggerError`。

---

## 6. 颜色

文本格式支持两个可选占位符：

```python
"%(log_color)s%(levelname)s%(reset)s %(message)s"
```

关闭颜色时两个占位符展开为空串。颜色判定顺序：显式 `use_color` > `NO_COLOR` > `FORCE_COLOR` > `DARWIN_COLOR` > 流的 `isatty()`。JSON 输出永远不含 ANSI 码。

---

## 7. 测试

```bash
uv run --extra test python -m pytest tests -q
```

测试覆盖单元行为、stderr/文件/JSON 集成、示例执行、零第三方导入、稳定导出与双语文档。架构细节见 `docs/development-guide.md`，可运行示例见 `examples/`。

---

## 8. 许可证

MIT，见 [LICENSE](LICENSE)。
