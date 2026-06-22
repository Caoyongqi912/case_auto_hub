"""后台任务辅助

直接 asyncio.create_task 启后台任务有两个隐患:
1. 异常不会传播, 任务抛错只在 gc 时打印 Task exception was never retrieved
2. 没存 handle, 任务没在 shutdown 时被 await / cancel

本模块提供:
- fire_and_forget(coro, name=None): 异常会通过 log.exception 记录, handle 进 registry
- shutdown(timeout=10): cancel 所有未完成 task 并 await
"""
import asyncio
from typing import Optional
from utils import log

_TASKS = set()


def fire_and_forget(coro, *, name=None):
    """启后台任务, 异常会 log.exception 记录, task 自动从 registry 注销."""
    task = asyncio.create_task(coro, name=name)
    _TASKS.add(task)

    def _done(t):
        _TASKS.discard(t)
        if not t.cancelled() and t.exception() is not None:
            log.exception(
                f"background task {t.get_name()} 异常: {t.exception()!r}",
                exc_info=t.exception(),
            )

    task.add_done_callback(_done)
    return task


def active_tasks():
    """当前在跑的 background tasks (调试 / 监控用)"""
    return set(_TASKS)


async def shutdown(timeout=10.0):
    """服务关闭时调用: cancel 所有 background task 并 await."""
    if not _TASKS:
        return
    log.info(f"shutdown: cancel {len(_TASKS)} background tasks")
    for t in list(_TASKS):
        t.cancel()
    await asyncio.wait_for(
        asyncio.gather(*_TASKS, return_exceptions=True),
        timeout=timeout,
    )
    _TASKS.clear()
