#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Time : 2024/6/7
# @Author : cyq
# @File : myLoguru
# @Software: PyCharm
# @Desc:
import os
import sys

from loguru import logger
import re
import uuid
from contextvars import ContextVar
from typing import Any, Optional, Tuple


_project_path = os.path.split(os.path.dirname(__file__))[0]
_Logs_path = os.path.join(_project_path, 'logs')


class MyLoguru:
    """
    日志记录器

    特性:
    - 根据时间和文件大小自动切割日志
    - 分离不同级别的日志到不同文件
    - 支持自定义日志格式和保留策略
    - 线程和进程安全
    - 自动创建日志目录

    使用示例:
    >>> log = MyLoguru().get_logger()
    >>> log.info("This is an info message")
    >>> log.error("This is an error message")
    """

    def __init__(self, max_size=30, retention='7 days', debug=False):
        self.log_dir = _Logs_path
        self.max_size = max_size
        self.retention = retention
        self.logger = logger
        self.debug = debug
        self._configure_logger()

    def _configure_logger(self):
        """配置日志记录器"""
        self.logger.remove()

        # 创建日志目录
        os.makedirs(self.log_dir, exist_ok=True)

        # 基础日志格式: 加 {extra[trace_id]} 字段 (OBS-2)
        # 没用 ContextVar 设 trace_id 时显示 '-'
        base_format = (
            "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
            "<blue>{process.name}</blue> | "
            "<blue>{thread.name}</blue> | "
            "<cyan>{file}</cyan>.<cyan>{module}</cyan>.<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
            "<cyan>trace={extra[trace_id]}</cyan> | "
            "<level>{level: <8}</level> | "
            "<level>{message}</level>"
        )
        # 错误日志格式(包含堆栈跟踪)
        error_format = base_format + "\n{exception}"
        # 普通日志文件配置
        self.logger.add(
            sink=f"{self.log_dir}/access-{{time:YYYY-MM-DD}}.log",
            rotation=self.max_size,
            retention=self.retention,
            level="INFO",
            format=base_format,
            enqueue=True,
            compression="zip"  # 可选的日志压缩
        )

        # 错误日志单独记录
        self.logger.add(
            sink=f"{self.log_dir}/error-{{time:YYYY-MM-DD}}.log",
            rotation=self.max_size,
            retention=self.retention,
            level="ERROR",
            format=error_format,
            enqueue=True,
            backtrace=True,  # 错误日志总是记录堆栈
            diagnose=True  # 错误日志总是记录变量值
        )
        # 控制台输出配置
        self.logger.add(
            sink=sys.stdout,
            level="DEBUG",
            format=base_format,
            enqueue=True,  # 确保线程安全
            colorize=True,  # 启用颜色
            backtrace=self.debug,  # 调试模式下显示完整堆栈
            diagnose=self.debug  # 调试模式下显示变量值
        )

        # [OBS-1 + OBS-3] 装 patcher: 注入 trace_id + redact 敏感字段
        # 必须最后调, 之后 add 的 sink 也会用 combined_patcher
        install_patchers(self.logger)

    def get_logger(self):
        return self.logger





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
    """ 把 ContextVar 里的 trace_id 注入到 record['extra']['trace_id']。"""
    record["extra"].setdefault("trace_id", get_trace_id() or "-")


def _redact_patcher(record: dict) -> None:
    """ redact message 里的敏感字段 + extra 里的 dict / list。"""
    msg = record.get("message")
    if msg:
        record["message"] = _redact_message(msg)
    # extra 里 dict / list 也 redact (跟 message 互补, log.info(xxx=secret) 走这里)
    for k, v in list(record["extra"].items()):
        if isinstance(v, (dict, list, tuple)):
            record["extra"][k] = redact_dict(v)


def install_patchers(logger) -> None:
    """

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
