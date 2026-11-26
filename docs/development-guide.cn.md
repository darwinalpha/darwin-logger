# darwin-logger 开发指南

English · [简体中文](development-guide.cn.md)

版本：0.1.0 · Python ≥ 3.12

---

## 1. 范围

`darwin-logger` 是**配置层**，不是标准库 `logging` 的替代品。它负责：

- root logger 配置（handler、级别、formatter 选择）
- stderr 与 UTF-8 文件输出，支持文件大小/时间轮转
- 基于占位符着色的控制台 formatter，以及上下文后缀
- 面向日志采集系统的单行 JSON formatter
- 基于 `contextvars` 的可选任务上下文

它刻意**不负责**：

- 自定义 logger 类——`get_logger()` 返回的就是 `logging.Logger`
- 结构化事件字典——用 `extra=` 与 `bind_context()` 代替
- 异步队列 handler——长驻服务才需要，CLI/数据脚本场景暂不做
- `.env` 加载——进程环境由调用方控制

---

## 2. 包结构

```text
src/darwin_logger/
├── __init__.py       # 公共 API 与版本
├── core.py           # 配置状态、环境变量解析、配置/重置 API
├── formatters.py     # ConsoleFormatter、JsonFormatter、颜色判定
├── sinks.py          # handler 工厂与 RotationConfig
├── context.py        # contextvars 绑定
├── exceptions.py     # 异常体系
└── py.typed          # PEP 561 标记
```

依赖方向单向：`core` 导入 `formatters`、`sinks`、`context`；`formatters` 导入 `context`；`sinks` 导入 `exceptions`。没有任何第三方导入。

---

## 3. 状态机

```text
                configure_logging()（首次调用）
    UNCONFIGURED ─────────────────────────────────► CONFIGURED
         ▲                                              │
         │                                              │ reconfigure_logging()
         │ reset_logging()                              │ 或 configure_logging(force=True)
         └──────────────────────────────────────────────┘
```

`configure_logging()` 有三个关键性质：

1. **默认幂等**：已有配置时直接返回当前 `LoggingConfig`，即使传了新参数也不生效。避免库模块导入时意外做局部修改。
2. **显式重建**：`reconfigure_logging(**kwargs)` 等价于 `configure_logging(force=True, **kwargs)`。安装新 handler 前会移除并关闭本库创建的 handler。
3. **handler 所有权**：重建/重置只移除本库创建的 handler。传 `replace_existing=True` 时，会把原有 root handler 暂存，并在重置时恢复。

所有状态变更由模块级 `threading.RLock()` 保护。

---

## 4. 配置解析

```text
环境变量 ──► LoggingConfig ──► 显式参数覆盖 ──► _install()
```

`config_from_env()` 读取所有支持的环境变量并立即校验：

- `LOG_LEVEL` 通过 `normalize_level()`：名称先查 `logging` 属性，再查 `logging.getLevelName()`；非法值抛 `InvalidLevelError`，不再静默回退 `INFO`。
- 布尔值接受 `1/true/yes/on` 与 `0/false/no/off`（忽略大小写）；其他值抛 `ConfigurationError`。
- `LOG_MAX_BYTES` 支持 `B/KB/MB/GB` 后缀并转换为字节。
- `LOG_FORMAT=""` 被当作空格式串保留，不再回退默认值。
- `use_color` 不在 `core` 里读环境变量；由 formatter 按 `NO_COLOR`、`FORCE_COLOR`、`DARWIN_COLOR` 与 `isatty()` 决定。

`LoggingConfig` 是不可变 dataclass。`to_dict()` 用 `dataclasses.asdict()` 返回可 JSON 序列化的快照，包含嵌套的 `RotationConfig`。

---

## 5. Formatter

### 5.1 ConsoleFormatter

默认文本格式：

```python
"%(log_color)s%(asctime)s [%(levelname)s] %(name)s%(reset)s: %(message)s"
```

颜色通过临时设置 `record.log_color` / `record.reset`，调用父类 `format()` 后再删除实现。这样不做格式化后字符串替换，自定义格式不含颜色占位符时也不会出错。

颜色判定顺序：

1. 显式 `use_color`
2. `NO_COLOR`——只要存在就禁用
3. `FORCE_COLOR`——真值启用
4. `DARWIN_COLOR`——旧变量，真值相同
5. 流的 `isatty()`

上下文字段以 ` key=value` 追加。关闭颜色时，即使格式串仍保留占位符，输出也不会有 ANSI 码。

### 5.2 JsonFormatter

每条记录变成一个 JSON 对象：

| 字段 | 来源 |
| --- | --- |
| `@timestamp` | `record.created`，UTC，毫秒精度，`Z` 结尾 |
| `level` | `record.levelname` |
| `logger` | `record.name` |
| `message` | `record.getMessage()` |
| `service` / `env` | `LOG_SERVICE` / `LOG_ENV` 或显式参数 |
| 上下文字段 | `get_context()` |
| 扩展字段 | `LogRecord` 上的自定义属性 |
| `exception` / `stack` | 格式化后的异常/栈信息 |

保留字段不能被 `extra` 或上下文覆盖。不可序列化值用 `default=str` 转换。JSON 输出永远不含 ANSI 码。

---

## 6. Sink

`create_console_handler(stream, formatter)` 包装 `logging.StreamHandler`。库在配置时绑定 `sys.stderr`，因此使用 `capsys` 的测试应断言 `captured.err`。

`create_file_handler(path, rotation)`：

- 自动创建父目录
- 未设置轮转时使用 `FileHandler`
- `kind="size"` 使用 `RotatingFileHandler`
- `kind="time"` 使用 `TimedRotatingFileHandler`
- 配置非法或文件系统错误时抛 `SinkError`

文件 handler 使用 UTF-8。重建时先关闭旧 handler 再打开新 handler。

---

## 7. 上下文

`bind_context(**fields)` 把字段写入 `ContextVar` 并返回重置 token。`clear_context(token)` 恢复上一层映射；`clear_context()` 直接清空。

两个 formatter 在格式化时读取上下文，因此：

- 文本日志追加 `run_id=... source=...`
- JSON 日志把同样字段提升为顶层 key

这是 asyncio 安全的：每个任务看到自己的上下文映射。

---

## 8. 公共 API 契约

从 `darwin_logger` 导出：

- 配置：`configure_logging`、`reconfigure_logging`、`reset_logging`、`is_configured`、`config_from_env`
- logger：`get_logger`、`set_log_level`、`set_logger_level`
- 自省：`get_logging_config`、`get_logger_config`
- 上下文：`bind_context`、`clear_context`、`get_context`
- 类型：`LoggingConfig`、`RotationConfig`、`ConsoleFormatter`、`JsonFormatter`
- 辅助：`normalize_level`
- 异常：`DarwinLoggerError`、`ConfigurationError`、`InvalidLevelError`、`SinkError`

`setup_logger` 等旧符号刻意不保留。契约测试同时断言导出列表存在与已删除符号不存在。

---

## 9. 测试

```bash
uv run --extra test python -m pytest tests -q
```

| 目录 | 覆盖 |
| --- | --- |
| `tests/unit/` | 级别校验、状态机、环境变量解析、formatter、sink、上下文 |
| `tests/integration/` | stderr 输出、JSON 解析、文件轮转、重配置、示例执行 |
| `tests/contract/` | 零第三方导入、导出列表、双语文档 |

共享的 `clean_logging` fixture 是 autouse，每个测试前后都调用 `reset_logging()`。`clean_env` fixture 会正确删除测试中新增的变量——不像旧实现那样把 `LOG_FILE` 泄漏给后续用例。

---

## 10. 迁移说明

不提供兼容层。与旧 `darwin_common.logging` 的关键差异：

| 旧行为 | 新行为 |
| --- | --- |
| `get_logger()` 自动配置 root | `get_logger()` 是纯函数；入口显式 `configure_logging()` |
| 第二次 `configure_logging()` 只改级别 | 第二次调用无操作；改用 `reconfigure_logging()` |
| `setup_logger` 别名 | 已删除 |
| 非法级别静默变 `INFO` | 抛 `InvalidLevelError` |
| `NO_COLOR` 按值判断 | 存在即禁用 |
| 总是 `StreamHandler(sys.stderr)` | 可用 `LOG_STDERR=0` 关闭 |
| 单个 `FileHandler`，无轮转 | 支持大小/时间轮转 |
| 无结构化输出 | `LOG_JSON=1` 开启采集友好的 JSON |
| 清空所有 root handler | 默认只移除本库创建的 handler |
