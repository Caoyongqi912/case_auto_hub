# BUG P1-1 + P1-2 + P1-4 修复报告 (高 ROI P1 一锅端)

**修复时间**: 2026-06-20
**HEAD**: 343693b → (本批 commit)
**回归测试**: 414 passed, 1 skipped, 3 deselected, 0 fail (+6 新)
**触发源**: EXECUTION_LAYERS_REVIEW_2026_06_20 找出的 3 个高 ROI P1 一锅端。

## 0. TL;DR

| BUG | 文件 | 现象 | 修法 |
|---|---|---|---|
| **P1-1** | `croe/interface/executor/interface_executor.py:_build_result` | 硬编码 `status_code == 200`, 同文件 363 行用 `InterfaceResponseStatusCodeEnum.SUCCESS`, 风格不一致 | 改用 enum |
| **P1-2** | `croe/interface/runner.py:InterfaceRunner.__slots__` | `__slots__` 含 `global_headers` 字段, `__init__` 设 `self.global_headers = []`, 但 `init_global_headers` 只更新 `self.interface_executor.g_headers` (新 list), 旧 `self.global_headers` 永为 stale 空 list | 删 `global_headers` 字段, 单一来源 `executor.g_headers` |
| **P1-4** | `croe/interface/runner.py:try_interface + try_group` | 没有 try/finally, UI 调试入口用完不释放 httpx 连接, 跟 `run_interface_case` / `run_interface_by_task` 风格不一致 | 加 try/finally 调 aclose, 4 个入口清理风格统一 |

**不修本批**: P1-3 `kwargs["id"]` 模式 (touch 5+ 文件, ROI 低), P1-5 `interfaceLog` 错属性名 (已修, runner.py:269-270 注释), P1-6 业务流 try/except 范围太大 (跟 R-2 风格有关, 等独立 review)。

## 1. BUG-P1-1 详情

### 1.1 根因

`interface_executor.py:442` 旧代码:
```python
is_success = ctx.response.status_code == 200
```

同文件 363 行用 enum:
```python
if response.status_code != InterfaceResponseStatusCodeEnum.SUCCESS:
    return []
```

风格不一致, 200 是魔法数字。后续如果状态码常量改 (e.g. 200 → "2xx"), 一处改即可的 enum 路径要同时手动改 2 处。

### 1.2 修法

`_build_result` 改:
```python
# BUG-P1-1 修复: 改用 InterfaceResponseStatusCodeEnum.SUCCESS (== "200"),
# 跟同文件 363 行的提取前判断风格一致, 避免魔法数字散落。
is_success = ctx.response.status_code == InterfaceResponseStatusCodeEnum.SUCCESS
```

### 1.3 锁住测试

`test_bug_p1_1_no_magic_200_in_build_result`: 静态源码锁 (剥注释), 验:
1. `_build_result` 代码行不含 `== 200`
2. 含 `InterfaceResponseStatusCodeEnum.SUCCESS`

## 2. BUG-P1-2 详情

### 2.1 根因

`runner.py:InterfaceRunner.__slots__` 含 `"global_headers"`, `__init__` 设 `self.global_headers = []` 后, 把同一个 list 引用传给 `InterfaceExecutor(global_headers=self.global_headers)`。`init_global_headers` 后续做:

```python
self.interface_executor.g_headers = list(global_headers)
```

**重新赋值新 list**, 但 `self.global_headers` 实例字段仍指向初始空 list。读 `runner.global_headers` 拿到 stale 数据, 跟 `runner.interface_executor.g_headers` 失同步。

### 2.2 后果

- 任何读 `self.global_headers` 的代码拿到 stale 空 list。
- 调试时跟 executor 的 g_headers 行为不一致, 排查难。
- 字段名误导 (暗示 "这是全局 header 列表", 实际不是)。

### 2.3 修法

`__slots__` 删 `"global_headers"`, `__init__` 删 `self.global_headers = []`, 单一来源 `self.interface_executor.g_headers`。
`InterfaceExecutor(global_headers=...)` 入参保留 (传初始空 list, `init_global_headers` 时注入)。

### 2.4 锁住测试

`test_bug_p1_2_slots_no_global_headers`: regex 锁源码:
1. `__slots__` 块不含 `"global_headers"`
2. `__init__` 函数体不含 `self.global_headers` (剥注释)

## 3. BUG-P1-4 详情

### 3.1 根因

`runner.py:try_interface + try_group` 之前没有 try/finally, UI 调试入口用完不释放 httpx 连接。`run_interface_case` 和 `run_interface_by_task` (T2 修后) 都有 finally 调 aclose, 4 个入口清理风格不一致。

### 3.2 后果

- UI 调试多开几个 tab 跑, httpx 连接池累积不释放
- 跟 case / task 入口行为不一致, 容易复制粘贴错

### 3.3 修法

`try_interface` + `try_group` 加 try/finally 调 aclose:

```python
try:
    return await self.interface_executor.execute(...)
finally:
    try:
        await self.interface_executor.aclose()
    except Exception:
        pass
```

UI 调试入口是短跑, 不需要清 vm / rw (T2 那两个跨 case 残留对调试入口影响小); 只需要释放 httpx 连接 (E1 一致性)。

### 3.4 锁住测试

- `test_bug_p1_4_try_interface_has_try_finally`: 静态源码锁, finally 块含 `interface_executor.aclose`
- `test_bug_p1_4_try_group_has_try_finally`: 同上
- `test_bug_p1_4_try_interface_finally_runs_on_exception`: 端到端 mock, execute 抛异常, finally 仍 aclose
- `test_bug_p1_4_try_group_finally_runs_on_exception`: 同上

## 4. 4 入口清理风格对齐 (P1-4 修后)

| 入口 | aclose | rw.clear_cache | vm.clear | 备注 |
|---|---|---|---|---|
| `try_interface` | ✅ **本批** | ❌ (UI 调试短跑) | ❌ (UI 调试短跑) | 修后只调 aclose |
| `try_group` | ✅ **本批** | ❌ (UI 调试短跑) | ❌ (UI 调试短跑) | 修后只调 aclose |
| `run_interface_case` | ✅ finally | ✅ finally | ✅ finally | RB2 修后已对齐 |
| `run_interface_by_task` | ✅ finally (T2) | ✅ finally (T2) | ✅ finally (T2) | T2 修后对齐 |

UI 调试入口 (try_interface / try_group) 故意不调 rw.clear_cache / vm.clear, 因为:
1. UI 调试是短跑, 单次执行, 不存在跨 case 残留
2. 调试时变量提取的中间状态可能对用户调试有用, 清了反而打断
3. 跟 `run_interface_case` 区分, UI 调试跟自动化执行是不同生命周期

## 5. 测试覆盖

| 文件 | 测试 | 类型 |
|---|---|---|
| `tests/croe/interface/test_bug_p1_1_2_4_cleanup_batch.py` | 6 个 (本批新增) | 静态源码锁 + mock 端到端 |

**全量回归**: 414 passed, 1 skipped, 3 deselected, 0 fail (408 基线 + 6 新)。

## 6. 不在本批范围 (留给下批)

- P1-3 `kwargs["id"]` 模式 (5+ 文件, ROI 低)
- P1-5 业务流 `run_interface_case` 的 `try/except Exception` 范围太大 (抓所有异常可能掩盖 BUG, 需独立 review)
- `__slots__` 在 `__init__` 后 `interface_executor.g_headers` 改 list 时, 旧 `self.global_headers` 引用问题 (P1-2 修后字段已删, 此问题根除)
- `init_global_headers` 每次都查 DB, 可加 60s cache (P1, 低 ROI)

## 7. 关键约定 (沿用)

- 测试不加 DB, 用 `inspect.getsource()` + 正则 + mock 锁产品代码
- BUG_ID 必加 `_bug_ids.py`, commit msg + 测试 + 报告三处引用
- 修复注释格式: `# BUG-{ID} 修复: 一句话根因 + 一句话修法 + 为什么不修方案 B`
- 锁 4 个入口风格统一时, UI 调试入口 (try_interface/try_group) 跟自动化执行入口 (run_interface_case/run_interface_by_task) 区分生命周期, 不强求完全一致
