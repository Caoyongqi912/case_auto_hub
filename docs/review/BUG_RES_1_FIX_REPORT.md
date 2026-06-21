# Round 2 资源泄漏审计修复报告 (BUG-RES-1)

**Commit**: (本次)
**基线**: 1005 → 1010 passed, 0 failed, 1 xfailed
**主题**: DB session / Redis / 文件 / httpx / 子进程 / 协程等资源释放审计

---

## 风险摘要

| ID | 等级 | 位置 | 风险 |
|---|---|---|---|
| BUG-RES-1 | **P0** | `croe/play/executor/step_content_strategy/play_interface_strategy.py` | httpx 连接池泄漏: 每次执行泄漏一份 |
| BUG-RES-2 | P2 | `croe/a_manager/script_manager.py` | `multiprocessing.Process` 用完没 `proc.close()`, Queue 没 close (低频) |
| BUG-RES-3 | P2 | `asyncio.create_task` 多个调用点 | 不存 handle, 无法 cancel / 状态查询 (FastAPI 自动 wait, 风险低) |
| BUG-RES-4 | P3 | `app/model/__init__.py` 的 `async_scoped_session` | task scope 模式下, 短任务切换 OK, 长任务累积可能持有多个 session (待监控) |

本轮只修 BUG-RES-1 (高频 + 资源会持续增长);其他风险低,留待后续按需处理。

---

## BUG-RES-1: PlayInterfaceContentStrategy 泄漏 httpx 连接池

### 根因
原代码:
```python
try:
    interface_executor = InterfaceExecutor(starter=step_context.starter,
                                           variable_manager=step_context.variable_manager)
    interface = await InterfaceMapper.get_by_id(...)
    result, success = await interface_executor.execute(interface=interface)
    interface_result = await rw.write_interface_result(...)
    ...
except Exception as e:
    log.exception(...)
    return False
```

`InterfaceExecutor` 内部 `HttpxClient` 是延迟初始化的,首次访问 `self.http` 才创建 `AsyncClient`(包含连接池)。代码里:
- 正常路径: 没调 `await interface_executor.aclose()` → httpx 连接池一直挂着
- 异常路径: `execute` 抛错 → 直接进 except → 同样不 close

后果: 每个 UI case 跑完, 一个 httpx 连接池滞留; 长跑 / 反复执行 → 句柄 / FD 泄漏 → eventually `OSError: Too many open files`。

### 修法

**1. InterfaceExecutor 加 async with 支持** (`croe/interface/executor/interface_executor.py`)

```python
async def aclose(self) -> None:
    if getattr(self, "http", None) is not None:
        await self.http.close()
        self.http = None  # BUG-RES-1 修复: 幂等, 二次调用安全

async def __aenter__(self) -> "InterfaceExecutor":
    return self

async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
    await self.aclose()
```

**2. play_interface_strategy 用 async with**

```python
async with InterfaceExecutor(starter=..., variable_manager=...) as interface_executor:
    interface = await InterfaceMapper.get_by_id(...)
    result, success = await interface_executor.execute(interface=interface)
    interface_result = await rw.write_interface_result(...)
# 退出块: httpx 连接池自动 close, 异常路径也走 __aexit__
```

### 兼容
- 已有 `runner.py` 调用 `await self.interface_executor.aclose()` 的 4 处不需要改,继续工作 (aclose 幂等)
- 旧的 `InterfaceExecutor(...)` 不带 `async with` 的用法仍然合法,但会保留原泄漏风险, 后续逐步迁移

---

## 测试覆盖

`tests/resource/test_round2_resource_leak_fixes.py` 新增 5 个用例:

| 用例 | 锁定行为 |
|---|---|
| `test_interface_executor_supports_async_with` | `__aenter__/__aexit__` 存在且是 coroutine |
| `test_interface_executor_async_with_closes_httpx` | `async with` 退出时 `http.close()` 被调 |
| `test_interface_executor_aclose_is_idempotent` | aclose 多次调用安全, close 只调一次 |
| `test_interface_executor_async_with_closes_on_exception` | 块内抛错时也走 `__aexit__` |
| `test_play_interface_strategy_uses_async_with` | 源码必须用 `async with`, 不能再有裸 `InterfaceExecutor(...)` 赋值 |

旧测试 `tests/croe/interface/test_interface_executor_coverage.py::test_aclose_calls_http_close` 同步更新, 适应 `http = None` 的新行为, 并新增幂等性断言。

---

## 下一轮

进入 **Round 3: 并发与竞态** (race condition, 锁粒度, 任务取消传播)。
