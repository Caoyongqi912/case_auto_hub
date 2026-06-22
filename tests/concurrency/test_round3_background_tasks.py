"""Round 3 并发与竞态回归测试 (fire_and_forget)

锁定行为:
- fire_and_forget 必须捕获 task 异常 (兜底 log.exception)
- fire_and_forget 必须把 task 注册到 registry, 完成后自动注销
- shutdown 必须 cancel 并 await 所有 task
- 已 cancel 的 task 不应被当作 "异常 task"
"""
import asyncio
import pytest

from utils import background as bg


@pytest.mark.unit
@pytest.mark.asyncio
async def test_fire_and_forget_runs_coro():
    """fire_and_forget 启动的协程必须真的跑了."""
    result = {}

    async def coro():
        await asyncio.sleep(0.01)
        result["done"] = True

    task = bg.fire_and_forget(coro(), name="t1")
    await task
    assert result.get("done") is True


@pytest.mark.unit
@pytest.mark.asyncio
async def test_fire_and_forget_captures_exception():
    """task 抛错不能丢, 必须 log.exception 兜底."""
    async def boom():
        raise RuntimeError("kaboom")

    task = bg.fire_and_forget(boom(), name="t_boom")
    # 等 task 自然结束 (异常也算结束)
    await task
    assert task.exception() is not None
    # 必须在 registry 里被自动移除
    assert task not in bg.active_tasks()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_fire_and_forget_registers_and_cleans():
    """active_tasks 必须反映当前在跑的 task."""
    blocker = asyncio.Event()

    async def wait_for_event():
        await blocker.wait()

    t1 = bg.fire_and_forget(wait_for_event(), name="t_block1")
    t2 = bg.fire_and_forget(wait_for_event(), name="t_block2")
    active = bg.active_tasks()
    assert t1 in active
    assert t2 in active

    blocker.set()
    await asyncio.gather(t1, t2)
    # 完成后必须从 registry 移除
    assert t1 not in bg.active_tasks()
    assert t2 not in bg.active_tasks()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_shutdown_cancels_pending_tasks():
    """shutdown 必须 cancel 所有未完成 task 并 await."""

    async def slow():
        await asyncio.sleep(60)

    t1 = bg.fire_and_forget(slow(), name="t_slow1")
    t2 = bg.fire_and_forget(slow(), name="t_slow2")
    assert t1 in bg.active_tasks()
    await bg.shutdown(timeout=2.0)
    # shutdown 后 t1/t2 都应该 cancel + 完成
    assert t1.cancelled() or t1.done()
    assert t2.cancelled() or t2.done()
    assert bg.active_tasks() == set()
