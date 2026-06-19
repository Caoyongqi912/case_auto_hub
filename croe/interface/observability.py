"""
[OBS-1 + OBS-2 + OBS-3] 可观测性基础设施。

- OBS-1 失败链路 trace 不可达: 失败 case 的 step_result 经常不落库 (InterfaceExecutor
  except 把错吞了)。本模块不直接修这个 (那是 InterfaceExecutor 改造), 但提供
  trace_id 帮定位"这条日志是哪条 case 跑的"。
- OBS-2 缺 correlation id: interface_case_id / case_result_id / task_result_id
  在多 case 并发时, 光看日志无法拼出"这条日志是哪条 case 跑的"。用 contextvars
  注入 trace_id, 跨 async / log / DB / WS 一致。
- OBS-3 缺 log 脱敏: URL/变量写进 log, 可能含 token / 密钥 / cookie。
  用 patcher 在 loguru 输出前 redact 敏感字段 (Authorization / Set-Cookie /
  Password / Token / api_key / secret 等)。

设计取舍:
- 8 字符 trace_id (uuid4 hex[:8]): 够区分并发 (1M 量级不撞), 短, 日志不抢眼
- contextvars 而非 threading.local: 跨 asyncio.Task 边界自动传递, 跟
  Python 3.7+ 的 asyncio 集成最自然
- loguru patcher 而非自定义 sink: 保留 MyLoguru 的所有现有配置 (文件切割 /
  颜色 / enqueue / backtrace), 只在 emit 时多走一层
- 默认 "-" 表示无 trace_id: 单测 / 脚本场景不强制设
- redact 是 best-effort, 不挡业务: 拼错的 key 不会 redact (没误伤), 真敏感
  字段没识别会原样输出 (兜底靠用户别往 log 写密钥)
"""
import re
import uuid
from contextvars import ContextVar
from typing import Any, List, Optional, Tuple

# ---- OBS-2: ContextVar 跨 async 边界传 trace_id ----
trace_id_var: ContextVar[Optional[str]] = ContextVar("case_trace_id", default=None)


def new_trace_id() -> str:
    """生成 8 字符 trace_id (uuid4 hex[:8])。"""
    return uuid.uuid4().hex[:8]


def set_trace_id(tid: Optional[str] = None) -> str:
    """设置 trace_id (默认生成新), 返回 tid。"""
    tid = tid or new_trace_id()
    trace_id_var.set(tid)
    return tid


def get_trace_id() -> Optional[str]:
    return trace_id_var.get()


def clear_trace_id() -> None:
    trace_id_var.set(None)


# ---- OBS-3: 敏感字段定义 + redact ----
# 模式匹配: key 名 (大小写不敏感, 子串匹配)
SENSITIVE_KEY_PATTERNS: Tuple[re.Pattern, ...] = (
    re.compile(r"(?i)authorization"),
    re.compile(r"(?i)set-?cookie"),
    re.compile(r"(?i)cookie"),
    re.compile(r"(?i)password"),
    re.compile(r"(?i)passwd"),
    re.compile(r"(?i)pass_word"),
    re.compile(r"(?i)token"),
    re.compile(r"(?i)api[_-]?key"),
    re.compile(r"(?i)access[_-]?key"),
    re.compile(r"(?i)secret"),
)

REDACTED: str = "***REDACTED***"


def _is_sensitive_key(key: Any) -> bool:
    """判断 key 名是否对应敏感字段。"""
    if not isinstance(key, str):
        return False
    for pat in SENSITIVE_KEY_PATTERNS:
        if pat.search(key):
            return True
    return False


def redact_dict(obj: Any) -> Any:
    """深拷贝 obj, 把敏感字段值替换为 ***REDACTED***。

    递归处理 dict / list / tuple; 其他类型原样返回。
    """
    if isinstance(obj, dict):
        return {
            k: (REDACTED if _is_sensitive_key(k) else redact_dict(v))
            for k, v in obj.items()
        }
    if isinstance(obj, list):
        return [redact_dict(x) for x in obj]
    if isinstance(obj, tuple):
        return tuple(redact_dict(x) for x in obj)
    return obj


# 匹配 'key=value' / 'key:value' / '"key": "value"' / "'key': 'value'"
# 支持 3 种常见格式:
#   1) key=value            (bareword, value=非空白非分隔符)
#   2) key: value           (bareword, value=非空白)
#   3) "key": "value with"  (JSON, value=可含空格直到引号)
# group 1: key 的开引号 (optional)
# group 2: key
# group 3: key 的闭引号 (must match 1)
# group 4: separator (= or :)
# group 5: value 的开引号 (optional)
# group 6: value (无引号: 非空白非分隔符; 有引号: 可含空格直到引号)
# 支持 3 种常见格式:
#   1) key=value            (bareword, value=非空白非分隔符)
#   2) key: value           (bareword, value=非空白)
#   3) "key": "value with"  (JSON, value=可含空格直到引号)
# group 1: key 的开引号 (optional, 不要求 backref match — \\1 跟 optional 配合在 Python 里不可靠)
# group 2: key
# group 3: separator (= or :)
# group 4: value 的开引号 (quoted 路径, optional)
# group 5: value 文本 (quoted 路径)
# group 6: bareword value (非引号路径)
_MESSAGE_KV_PATTERN = re.compile(
    r"""([\'"])?([A-Za-z_][A-Za-z0-9_-]*)['"]?\s*([:=])\s*"""
    r"""(?:([\'"])([^\'"]*)\4|([^\s,;\'"}{)]+))""",
    re.IGNORECASE,
)


def _redact_message(msg: Any) -> Any:
    """扫字符串里的 'key=value' / 'key: value' / '"key": "value"' 模式, 把敏感值替换。

    不识别 / 拼错的格式会原样保留 (best-effort, 不挡业务)。
    """
    if not isinstance(msg, str):
        return msg

    def repl(m: re.Match) -> str:
        key = m.group(2)
        if not _is_sensitive_key(key):
            return m.group(0)
        # 重建原 match 字符串, 只把 value 换成 REDACTED
        key_quote = m.group(1) or ""
        sep = m.group(3)
        # quoted 路径: group 4/5; bareword 路径: group 6
        if m.group(4) is not None:
            value_quote = m.group(4)
            return f"{key_quote}{key}{key_quote}{sep}{value_quote}{REDACTED}{value_quote}"
        return f"{key_quote}{key}{key_quote}{sep}{REDACTED}"

    return _MESSAGE_KV_PATTERN.sub(repl, msg)


# ---- OBS-1 + OBS-3: loguru patchers ----
def _trace_id_patcher(record: dict) -> None:
    """[OBS-2] 把 ContextVar 里的 trace_id 注入到 record['extra']['trace_id']。"""
    record["extra"].setdefault("trace_id", get_trace_id() or "-")


def _redact_patcher(record: dict) -> None:
    """[OBS-3] redact message 里的敏感字段 + extra 里的 dict / list。"""
    msg = record.get("message")
    if msg:
        record["message"] = _redact_message(msg)
    # extra 里 dict / list 也 redact (跟 message 互补, log.info(xxx=secret) 走这里)
    for k, v in list(record["extra"].items()):
        if isinstance(v, (dict, list, tuple)):
            record["extra"][k] = redact_dict(v)


def install_patchers(logger) -> None:
    """[OBS-1 + OBS-3] 给 loguru 装 trace_id + redact patcher (幂等, 可多次调)。

    装完后, 每条日志 emit 前会自动:
      1. record['extra']['trace_id'] = 当前 ContextVar 值 (默认 '-')
      2. message 里 'Authorization=xxx' 自动变 'Authorization=***REDACTED***'
      3. extra 里 dict / list 的敏感字段自动 redact

    用法: 在 MyLoguru 构造时调一次即可。
    """
    def combined_patcher(record: dict) -> None:
        _trace_id_patcher(record)
        _redact_patcher(record)

    logger.configure(patcher=combined_patcher)


# ---- Context manager: 自动 set + clear ----
class _TraceIdContext:
    """context manager: 进入时 set_trace_id, 退出时清掉。

    用法:
        with _TraceIdContext() as tid:
            log.info("xxx")  # extra.trace_id = tid
        # 退出后 ContextVar 恢复
    """

    def __init__(self, tid: Optional[str] = None) -> None:
        self._tid = tid
        self._token = None

    def __enter__(self) -> str:
        self._tid = set_trace_id(self._tid)
        return self._tid

    def __exit__(self, *exc) -> None:
        clear_trace_id()
