# 日志分析技能

用于分析 `/var/log` 中近期异常，识别错误模式和潜在风险。

## 检查范围

- `/var/log/syslog`
- `/var/log/system.log`
- `/var/log/messages`
- `/var/log/*.log`
- 项目或服务明确指定的日志路径

## 关键词

重点检索：

- `error`
- `failed`
- `exception`
- `panic`
- `fatal`
- `timeout`
- `oom`
- `segfault`
- `denied`

## 输出格式

每个异常模式按以下格式整理：

- 现象：日志中出现了什么
- 证据：关键日志片段或计数
- 影响：可能影响哪些服务
- 建议：下一步排查或处理动作

## 安全要求

- 不要输出包含密钥、token、webhook、cookie 的完整日志行。
- 只分析必要时间窗口，避免一次性读取超大日志。
- 默认只读，不删除、不截断、不压缩日志。
