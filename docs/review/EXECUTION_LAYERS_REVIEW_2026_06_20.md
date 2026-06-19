# 接口自动化执行深度 review - 4 入口 × 3 层

**review 时间**: 2026-06-20
**review 范围**: 4 个执行入口 (单接口/组/业务流/任务) × 3 层 (model / mapper / executor)
**基础 commit**: 378e868 (D4-V2 修完)
**触发**: 用户 "重新review 接口自动化执行...model 层 mapper 层。核心代码执行层"

## 0. TL;DR - 发现 2 个 P0 + 3 个 P1

| 严重度 | 编号 | 文件:行 | 现象 | 修法 |
|---|---|---|---|---|
| **P0** | **T1** | `croe/interface/task.py:_init_task_variables` | 函数名说"init task variables"但实际只 log.info 一行, 任务级 `params.variables` 永远不会注入到 VariableManager, 用户传的任务变量静默丢失 | 真正调 `variable_manager.add_vars(trans(variables))` |
| **P0** | **T2** | `croe/interface/runner.py:run_interface_by_task` | 没有 try/finally cleanup: 不调 `aclose()` (httpx 连接泄漏) / 不调 `clear_trace_id()` / 不 `variable_manager.clear()` / 不 `result_writer.clear_cache()`。一个 task 跑 N 个 interface, httpx 连接池永远不释放, 跨 task 累积, 跟 `run_interface_case` 的清理风格不一致 | 加 try/finally 调 4 个清理 |
| P1 | 1 | `croe/interface/executor/interface_executor.py:442` | 硬编码 `status_code == 200`, 同文件 363 行用 `InterfaceResponseStatusCodeEnum.SUCCESS`, 风格不一致 | 改用 `InterfaceResponseStatusCodeEnum.SUCCESS` |
| P1 | 2 | `croe/interface/runner.py:__slots__` | `global_headers` 实例字段在 `init_global_headers` 里不被更新 (只更新 `executor.g_headers`), 字段名误导, 读取方拿到 stale 空 list | 删 `global_headers` 字段, 只保留 `executor.g_headers` 单一来源 |
| P1 | 3 | `app/mapper/interfaceApi/interfaceCaseMapper.py:78` + `interfaceMapper.py:81` | `kwargs["id"] = case_id; await cls.update_by_id(**kwargs)` — 跟 `update_by_id(id=...)` 签名多一层 mutation, code smell | 改 `await cls.update_by_id(id=case_id, **kwargs)` |

## 1. 4 个执行入口对照

| 入口 | 文件:行 | try/finally | aclose() | clear_trace_id | vm.clear() | rw.clear_cache() |
|---|---|---|---|---|---|---|
| `try_interface` | runner.py:62 | ❌ | ❌ | ❌ | ❌ | ❌ |
| `try_group` | runner.py:91 | ❌ | ❌ | ❌ | ❌ | ❌ |
| `run_interface_case` | runner.py:169 | ✅ | ✅ finally | ✅ finally | ✅ finally | ✅ finally |
| `run_interface_by_task` | runner.py:298 | ❌ **P0** | ❌ **P0** | ❌ **P0** | ❌ **P0** | ❌ **P0** |

`run_interface_case` 是唯一正确的 (RB2 修时没顺便加清理, 只加了 init_global_headers)。

## 2. P0-T1 详情: `_init_task_variables` 假函数

### 2.1 根因

`croe/interface/task.py:_init_task_variables` 当前实现 (line 277-289):
```python
async def _init_task_variables(self, variables: Any) -> None:
    """
    初始化任务变量
    """
    try:
        await self.starter.send(
            f"🫳🫳 初始化任务变量 = {variables}"
        )
    except Exception as e:
        log.error(f"初始化任务变量失败: {e}")
```

只往 starter 发一条 log, 没有真正调 `variable_manager.add_vars(...)` 注入到 VariableManager。`TaskParams.variables` 字段存在, 调用方传进来, 函数签名也接收, 但永远没生效。

### 2.2 后果

- 任务级变量覆盖完全失效
- 用户传了 `TaskParams(variables={"base_url": "https://staging.api.com"})` 期望覆盖环境变量, 实际没生效
- 排查时难定位 (log 显示 "初始化任务变量" 但实际没初始化)

### 2.3 修法

`task.py` 当前没有 `VariableManager` 引用 (`TaskRunner` 没注入), 也不在 `InterfaceRunner` 里。修法选项:
- **选项 A (推荐)**: 在 `TaskRunner.execute_task` 里把 `params.variables` 传下去给 `InterfaceRunner`, 由 `InterfaceRunner` 走 `variable_manager.add_vars(trans(...))`
- **选项 B**: 在 `TaskRunner` 里维护一个临时 `VariableManager` 实例, 在 `_execute_api_steps` / `_execute_case_steps` 传给 `InterfaceRunner`

为了不破坏现有架构 (InterfaceRunner 自有 VariableManager), 选 B: 在 TaskRunner 里加一个 `self.variable_manager = VariableManager()`, `params.variables` 时 `add_vars` 一次, 然后把 `self.variable_manager` 注入给每个 `InterfaceRunner`。

### 2.4 锁住测试

新建 `tests/croe/interface/test_bug_t1_init_task_variables.py`, 锁源码 + 行为:
- `inspect.getsource` 验 `_init_task_variables` 调 `variable_manager.add_vars(...)`, 不是只 log
- mock 端到端, 传 `TaskParams(variables={"key": "value"})`, 验 InterfaceRunner 的 VariableManager 有 `{"key": "value"}`

## 3. P0-T2 详情: `run_interface_by_task` 没 cleanup

### 3.1 根因

`runner.py:298-353` 当前实现:
```python
async def run_interface_by_task(
    self, interface, task_result_id, retry=0, retry_interval=0, env=None,
) -> bool:
    await self.init_global_headers()  # RB2 修
    for attempt in range(retry + 1):
        result = await self.interface_executor.execute(interface=interface, env=env)
        success = result['result']
        if success:
            await self.result_writer.write_interface_result(...)
            return True
        if attempt == retry:
            await self.result_writer.write_interface_result(...)
            await self.starter.send(f"接口 {interface} 执行结果 FALSE")
            return False
        await self.starter.send(...)
        if retry_interval:
            await asyncio.sleep(retry_interval)
    return False
```

跟 `run_interface_case` 比, 缺:
- `try/finally` 包裹, finally 调:
  - `clear_trace_id()` (OBS-2 跨并发 case 隔离)
  - `self.variable_manager.clear()` (业务流变量清空, 防下一次跑残留)
  - `self.result_writer.clear_cache()` (D1 修过, 跨 case 不残留)
  - `self.interface_executor.aclose()` (E1 修过, httpx 连接释放)

### 3.2 后果

- **httpx 连接泄漏**: `InterfaceExecutor.http` 是 `HttpxClient`, 持 connection pool。task 跑完整个 task 的 interfaces 后, pool 不释放, 长跑 / 多 task 累积。
- **trace_id 跨 case 污染**: `set_trace_id()` 在 `run_interface_case` 设了, 但 `run_interface_by_task` 不设不 clear。如果 `_execute_api_steps` 中只有 `run_interface_by_task` 调用 (无 `run_interface_case`), trace_id 一直是 "-"; 一旦中间调一次 `run_interface_case` 设了 trace_id, 后续的 `run_interface_by_task` log 全带这个 trace_id, 排查时串号。
- **variable 残留**: `run_interface_by_task` 失败时不 `vm.clear()`, 下一个 task 用同一个 runner 实例时, 上一次失败时提取的变量还在, 串号。
- **result_writer 缓存泄漏**: 同 variable。

### 3.3 修法

`run_interface_by_task` 加 try/finally 包裹整个 retry loop, finally 跟 `run_interface_case` 风格一致:
```python
async def run_interface_by_task(...):
    await self.init_global_headers()
    try:
        for attempt in range(retry + 1):
            result = await self.interface_executor.execute(...)
            ...
    finally:
        # 跟 run_interface_case 清理风格对齐
        try:
            await self.interface_executor.aclose()
        except Exception:
            pass
        self.result_writer.clear_cache()
        await self.variable_manager.clear()
```

不调 `clear_trace_id()` 因为 `run_interface_by_task` 自己不设 trace_id (那是 `run_interface_case` 的事); 设了清会反而把外层 trace_id 误清。

不调 `starter.over()` 因为 `_execute_api_steps` 在外层, task 整体结束才 over (跟 `run_interface_case` 一样 — `run_interface_case` finally 调 `starter.over(case_result.id)` 是因为 `run_interface_case` 是 "一个 case 一 over", 业务流结束就 over; `run_interface_by_task` 是 "一个 interface 一 over", 但实际上 task.py 已经在外层 `finally: await self.starter.over(task_result.id)`, 重复 over 会让前端收到 N+1 个 over 事件)。

### 3.4 锁住测试

新建 `tests/croe/interface/test_bug_t2_task_cleanup.py`:
- `inspect.getsource` 验 `run_interface_by_task` 函数体有 `try/finally` 包裹 retry 循环
- 验 finally 调 `self.interface_executor.aclose()` + `self.result_writer.clear_cache()` + `self.variable_manager.clear()`

## 4. P1-1 详情: 硬编码 200

### 4.1 根因

`croe/interface/executor/interface_executor.py:442`:
```python
is_success = ctx.response.status_code == 200
```

同文件 363 行 (提取变量前判断 status):
```python
if response.status_code != InterfaceResponseStatusCodeEnum.SUCCESS:
    return []
```

风格不一致, 200 是魔法数字。

### 4.2 修法

改用 `InterfaceResponseStatusCodeEnum.SUCCESS`, 跟 363 行对齐。

## 5. P1-2 详情: `__slots__` `global_headers` 字段 stale

### 5.1 根因

`runner.py:44-52`:
```python
def __init__(self, starter):
    self.starter = starter
    self.variable_manager = VariableManager()
    self.global_headers: List[InterfaceGlobalHeader] = []  # 实例字段
    self.result_writer = ResultWriter()
    self.interface_executor = InterfaceExecutor(
        starter=self.starter,
        variable_manager=self.variable_manager,
        global_headers=self.global_headers,  # 引用同一个 list
    )
```

`init_global_headers` (line 387-402):
```python
self.interface_executor.g_headers = list(global_headers)
```

`self.interface_executor.g_headers` 重新指向新 list, 但 `self.global_headers` 仍是初始空 list。读 `runner.global_headers` 拿到 stale 数据。

### 5.2 修法

`__slots__` 删 `global_headers`, `__init__` 删 self.global_headers = [], executor 改 `global_headers=None` (由 init_global_headers 注入)。保留 `self.interface_executor.g_headers` 单一来源。

## 6. P1-3 详情: `kwargs["id"]` 模式 code smell

### 6.1 根因

`interfaceCaseMapper.py:78`:
```python
kwargs["id"] = case_id
async with cls.transaction() as session:
    ...
    new_case = await cls.update_by_id(
        session=session, ...,
        **kwargs,
    )
```

`update_by_id` 签名是 `update_by_id(id, **kwargs)`, 直接 spread kwargs 即可, 不需要 mutation 一下。

### 6.2 修法

```python
new_case = await cls.update_by_id(
    session=session, id=case_id, ...,
    **kwargs,
)
```

## 7. 不在本批范围 (留给下批)

- 其它 `kwargs["id"]` 散落点
- `try_interface` / `try_group` 缺清理 (跟 T2 同性质, 但单接口/组是 UI 调试入口, 影响小)
- 业务流 `run_interface_case` 的 `try/except Exception` 范围太大, 抓所有异常可能掩盖 BUG
- `InterfaceResult.interface_result` 双向 FK 在 cache flush 后批量 reconcile 性能 (D6 修了语义, 性能另算)
- `InterfaceRunner` 没有 lock 并发安全 (高并发 case 共享 runner 时的 race)

## 8. 关键约定 (沿用)

- 测试不加 DB, 用 `inspect.getsource()` + 正则 + mock 锁产品代码
- BUG_ID 必加 `_bug_ids.py`, commit msg + 测试 + 报告三处引用
- 修复注释格式: `# BUG-{ID} 修复: 一句话根因 + 一句话修法 + 为什么不修方案 B`
- 锁 4 个入口风格统一时, 优先跟 `run_interface_case` (最完善的) 对齐
