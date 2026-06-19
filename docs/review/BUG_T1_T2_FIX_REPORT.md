# BUG T1 + T2 修复报告

**修复时间**: 2026-06-20
**HEAD**: 378e868 → (本批 commit)
**回归测试**: 408 passed, 1 skipped, 3 deselected, 0 fail (+7 新)
**触发源**: EXECUTION_LAYERS_REVIEW_2026_06_20 (4 入口 × 3 层 review) 发现的 2 个 P0。

## 0. TL;DR

| BUG | 文件 | 现象 | 修法 |
|---|---|---|---|
| **T1** | `croe/interface/task.py:_init_task_variables` | 函数名说"init task variables"但只 log.info 一行, `params.variables` 永远不注入 VariableManager, 用户传的任务级变量静默丢失 | TaskRunner 自管 `self._shared_vm`, params.variables 走 trans 后 add_vars, 后续 InterfaceRunner 共享这个 vm |
| **T2** | `croe/interface/runner.py:run_interface_by_task` | 没 try/finally, 跑完 task 后 httpx 连接池不释放 (E1 漏修到这条路径), variable / rw 缓存跨 case 残留 (D1 / OBS-2 漏修), 跨 task 累积泄漏 / 串号 | 加 try/finally 跟 `run_interface_case` 清理风格对齐: aclose → rw.clear_cache → vm.clear |

## 1. BUG-T1 详情

### 1.1 根因

`croe/interface/task.py:_init_task_variables` 旧代码 (line 277-289):
```python
async def _init_task_variables(self, variables: Any) -> None:
    try:
        await self.starter.send(
            f"🫳🫳 初始化任务变量 = {variables}"
        )
    except Exception as e:
        log.error(f"初始化任务变量失败: {e}")
```

只往 starter 发一条 log, **没有调 `variable_manager.add_vars(...)` 真正注入**。`TaskParams.variables` 字段存在, 调用方传进来, 函数签名也接收, 但永远不生效。

### 1.2 后果

- 任务级变量覆盖完全失效。
- 用户传 `TaskParams(variables={"base_url": "https://staging.api.com"})` 期望覆盖, 实际没生效。
- 排查难: log 显示 "初始化任务变量" 但实际没初始化。

### 1.3 修法

`TaskRunner` 持有 `self._shared_vm = VariableManager()`, `params.variables` 时:
1. 走 trans 做变量替换 (variables 自身可能含 ${xxx} 引用)
2. add_vars 注入到 `self._shared_vm`
3. 把 `self._shared_vm` 通过 `InterfaceRunner(starter, variable_manager=self._shared_vm)` 注入到每个 InterfaceRunner

`InterfaceRunner.__init__` 加 optional `variable_manager` 参数, None 时回退到新建, 不破坏现有调用方 (try_interface / try_group / run_interface_case 都走 None 路径)。

### 1.4 为什么不改方案 B (在 TaskParams 传 transed dict)

业务上 `params.variables` 可能含 `${xxx}` 引用, 需要 trans 替换。`VariableManager.trans` 是 async 的, 必须在 runner 里调。直接传 transed dict 的话, 调用方要承担 trans 责任, 违反 "caller 不需要知道细节" 原则。

### 1.5 锁住测试

`tests/croe/interface/test_bug_t1_t2_task_batch.py`:
- `test_bug_t1_init_task_variables_actually_adds_to_vm`: 静态源码锁, 验 `add_vars` + `_shared_vm` 引用 + add_vars 必须在 starter.send 之前。
- `test_bug_t1_init_task_variables_end_to_end`: 端到端 mock, 传 `{"base_url": "..."}`, 验 `_shared_vm.variables["base_url"]` 等于传入值。
- `test_bug_t1_init_task_variables_none_noop`: 传 None 不崩, vm 仍空。
- `test_bug_t1_interface_runner_accepts_optional_variable_manager`: `inspect.signature` 锁 `InterfaceRunner.__init__` 有 `variable_manager` 参数, default=None。

## 2. BUG-T2 详情

### 2.1 根因

`runner.py:run_interface_by_task` 旧代码 (line 298-353):
```python
async def run_interface_by_task(self, interface, task_result_id, retry=0, retry_interval=0, env=None) -> bool:
    await self.init_global_headers()  # RB2 修
    for attempt in range(retry + 1):
        result = await self.interface_executor.execute(...)
        ...
```

跟 `run_interface_case` 比, 缺 try/finally 包裹 + 4 个清理:
- `clear_trace_id()` (OBS-2)
- `self.variable_manager.clear()` (D1 防残留)
- `self.result_writer.clear_cache()` (D1 防残留)
- `self.interface_executor.aclose()` (E1 httpx 连接释放)

### 2.2 后果

- **httpx 连接泄漏**: task 跑 N 个 interface 后连接池不释放, 跨 task 累积。
- **trace_id 跨 case 污染**: 跟 `run_interface_case` 混用时, `_execute_api_steps` 用 `run_interface_by_task` 不设不 clear trace_id, 后续的 `run_interface_case` 拿到旧 trace_id 串号。
- **variable 残留**: 失败时 vm 不 clear, 下一个 task 串号。
- **rw 缓存泄漏**: 同 variable。

### 2.3 修法

加 try/finally 包裹整个 retry 循环, finally 跟 `run_interface_case` 清理顺序对齐:
```python
try:
    for attempt in range(retry + 1):
        ...
finally:
    try:
        await self.interface_executor.aclose()
    except Exception:
        pass
    self.result_writer.clear_cache()
    await self.variable_manager.clear()
```

不调 `starter.over()`: 外层 `_execute_api_steps` finally 统一调, 重复调会让前端收到 N+1 个 over 事件。

不调 `clear_trace_id()`: 本函数自己不设 trace_id (那是 `run_interface_case` 的事), 清会误伤外层。

### 2.4 为什么不改方案 B (在 _execute_api_steps 外层 finally 调清理)

外层不知道 runner 内部状态, 没法做精细清理。`run_interface_case` 的清理就是自己的 finally, 风格统一优先。

### 2.5 锁住测试

- `test_bug_t2_run_interface_by_task_has_try_finally`: 静态源码锁, 验有 try/finally, try 在 for 之前, finally 在 for 之后。
- `test_bug_t2_finally_cleans_three_things`: regex 提取 finally 块 (剥注释), 验含 3 个清理调用 + 不含 `starter.over` / `clear_trace_id`。
- `test_bug_t2_finally_runs_even_on_exception`: 端到端 mock, `executor.execute` 抛 RuntimeError, finally 仍跑 3 个清理 (aclose / rw.clear_cache / vm.clear)。

## 3. 4 入口清理风格对齐

| 入口 | 文件:行 | aclose | rw.clear_cache | vm.clear | 备注 |
|---|---|---|---|---|---|
| `try_interface` | runner.py:62 | ❌ | ❌ | ❌ | 单次使用, 短跑, 影响小 |
| `try_group` | runner.py:91 | ❌ | ❌ | ❌ | 同上 |
| `run_interface_case` | runner.py:169 | ✅ finally | ✅ finally | ✅ finally | RB2 修后已对齐 |
| `run_interface_by_task` | runner.py:298 | ✅ **本批 T2** | ✅ **本批 T2** | ✅ **本批 T2** | 修后跟 case 对齐 |

P1 留给下批: `try_interface` / `try_group` 也加 finally 清理 (UI 调试入口, 影响小)。

## 4. 测试覆盖

| 文件 | 测试 | 类型 |
|---|---|---|
| `tests/croe/interface/test_bug_t1_t2_task_batch.py` | 7 个 (本批新增) | 静态源码锁 + mock 端到端 |

**全量回归**: 408 passed, 1 skipped, 3 deselected, 0 fail (401 基线 + 7 新)。

## 5. 不在本批范围 (留给下批)

- `try_interface` / `try_group` 加 finally 清理 (P1)
- 硬编码 200 (P1) — `interface_executor.py:442` 改 `InterfaceResponseStatusCodeEnum.SUCCESS`
- `__slots__` `global_headers` stale (P1) — 删字段, 只保留 executor.g_headers
- `kwargs["id"]` 模式 (P1) — 改 `update_by_id(id=case_id, **kwargs)` 直接传
- 业务流 `run_interface_case` 的 `try/except Exception` 范围太大 (P1)

## 6. 关键约定 (沿用)

- 测试不加 DB, 用 `inspect.getsource()` + 正则 + mock 锁产品代码
- BUG_ID 必加 `_bug_ids.py`, commit msg + 测试 + 报告三处引用
- 修复注释格式: `# BUG-{ID} 修复: 一句话根因 + 一句话修法 + 为什么不修方案 B`
- 锁 4 个入口风格统一时, 优先跟 `run_interface_case` (最完善的) 对齐
- 锁源码时去掉注释行, 避免误命中修复注释里描述"不调什么"的引用
