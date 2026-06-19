# BUG-P-R1..P-R5 Fix Report (UI 自动化 5 P0 一锅端)

**修复时间**: 2026-06-21
**基础 commit**: 499ca47
**触发**: `docs/review/PLAY_REVIEW_2026_06_21.md` 的 5 个 P0
**测试基线**: 414 pass, 0 fail → 修复后 421 pass, 0 fail (净增 7 个新测)
**commit**: 见本批提交

## 1. TL;DR

| ID | 文件:行 | 一句话根因 | 修法 | 状态 |
|---|---|---|---|---|
| **P-R1** | `croe/play/play_runner.py:execute_case` (except 块) | `except: raise` 让任务级 retry 看不到 case 失败, 整个 task 挂掉, 进度统计失败 | except 只 `case_success=False`, 不 raise; finally 仍写结果 | ✅ |
| **P-R2** | `croe/play/task_runner.py:execute_task` L36-37 | 同一 `query_case` 调了 2 次, 第一次结果被覆盖 | 删第一次 query | ✅ |
| **P-R3** | `croe/play/task_runner.py:__execute_case` retry loop | `init_case_variables` 跑在 retry 里面, 每次重试从 DB 拉 vars 重复 add, 前一次失败变量污染下一次 | 提到 retry 外, 每个 case 跑前一次性 init | ✅ |
| **P-R4** | `croe/play/task_runner.py:__execute_case` | `error_continue` 参数有定义但从不透传, 写死 False, 重试用例无法继续 | `PlayTaskExecuteParams` 加 `error_continue`, 透传 | ✅ |
| **P-R5** | `croe/play/executor/step_content_strategy/_base.py:write_result` | `if not result.success and not ignore: set_error_step_info` — 步骤 ignored=True 时失败信息 (msg/screenshot) 全部丢失 | ignore 时也写截图/msg, 不标 case 失败 | ✅ |

## 2. 详细修复

### 2.1 P-R1 — execute_case 重试黑洞

**现象**: `execute_case` 在 except 块 `raise` 把异常抛回调用方 (`__execute_case` 的 retry for 循环), task_runner 看到的是 Exception, 不是 case_success=False, 整个 task 在第一次 case 失败就挂, 后续 case 不跑, 进度统计 (success_number/fail_number) 永远不准。

**为什么 P0**: 这是 UI 任务级 retry 失效的根因, 整个 retry 机制对 UI 自动化形同虚设; CI 上一次失败整个任务红掉, 拿不到实际通过/失败数。

**修法**: `except` 块只设 `case_success=False`, 不 `raise`; `finally` 仍照常写入结果, 进度统计有数据。

**为什么不 try-finally-re-raise**: 重抛让外层 catch (task_runner) 拿到 Exception 直接挂, 跟现状一样。保持 except 不 raise + finally 写结果, 是最小改动 + 不影响现有写结果流程。

**测试**: `test_pr1_execute_case_swallows_exception` — mock execute_case 内步骤, 强制抛 Exception, assert 返回 False 而非 raise。

### 2.2 P-R2 — 重复 query_case

**现象**: `execute_task` 同一个 `play_cases = await PlayTaskMapper.query_case(taskId=task.id)` 调了 2 次, 第一次结果完全没用到, 多 1 次 DB roundtrip + 一次内存分配。

**修法**: 删 L36-37 的第一次 query, 保留 L46-48 的 (那个是 `if not play_cases` 之后才用到的, 之前先做 `starter.send`, 删了不影响逻辑)。

**为什么 P0**: 性能 + 代码冗余, 在大型任务 (几十个 case) 翻倍 DB 查询。

**测试**: `test_pr2_query_case_called_once` — 用 `unittest.mock.patch` 包装 `PlayTaskMapper.query_case`, 统计调用次数, assert == 1。

### 2.3 P-R3 — init_case_variables 提到 retry 外

**现象**: retry loop 内部每次重试都调 `init_case_variables` (从 DB 拉 case 关联的 `PlayCaseVar` 表, 再 add 到 vm)。问题:
1. 重复 DB 查询 (retry 多少次查多少次)
2. vm 不清, 前一次失败 (e.g. 步骤把 var 改了) 污染下一次
3. 参数 `params.variables` 也被重复 add

**修法**: `init_case_variables` 调用从 retry loop 内部提到外层, 每个 case 跑前一次性 init; retry 循环内只调 `execute_case` 本身。

**测试**: `test_pr3_init_case_variables_called_once_per_case` — mock `init_case_variables`, 在 `retry=2` 的情况下, 跑 1 个 case, assert 调用次数 == 1。

### 2.4 P-R4 — error_continue 透传

**现象**: `PlayTaskExecuteParams` 没有 `error_continue` 字段, `__execute_case` 调 `execute_case` 时也不传, 写死 False。结果: 重试用例 (retry > 0) 想 error_continue 也做不到, 必须 case 完全成功才继续。

**修法**:
1. `PlayTaskExecuteParams` 加 `error_continue: bool = False` 字段
2. `__execute_case` 透传: `case_success = await play_runner.execute_case(play_case=..., error_continue=params.error_continue, ...)`

**为什么 P0**: 没有 error_continue 透传, 任务级 retry 配 error_continue 等于没配, 用户配置被默默吞掉。

**测试**: `test_pr4_error_continue_propagates` — `PlayTaskExecuteParams(error_continue=True)`, mock `execute_case`, assert 收到的 `error_continue` 是 True。

### 2.5 P-R5 — ignore 步骤失败信息丢失

**现象**: 步骤 `ignore=True` 时, 失败 `if not result.success and not ignore: set_error_step_info` 条件不满足, msg/screenshot 全部不进 `case_result`, 用户想看 ignored 步骤为什么失败无线索。

**修法**: 把 `and not ignore` 删掉, `if not result.success` 即可; ignore 标志保留 (语义是 "步骤失败不标 case 失败"), 失败信息照写。

**为什么不删 ignore 标志**: ignore 步骤的语义是 "步骤失败不标 case 失败", 删 ignore 会破坏这个语义; 保留 ignore 标志, 但失败信息照写, 既不破坏语义又保留排查线索。

**测试**: `test_pr5_ignored_step_writes_error_info` — mock write_result 传入 success=False + ignore=True, assert `set_error_step_info` 仍被调用。

## 3. 周边影响

| 维度 | 评估 |
|---|---|
| **接口层耦合** | 无。P-R1/P-R2/P-R3/P-R4 都改 task_runner/play_runner 内部, 控制器层 (`PlayController`) 不变。 |
| **数据迁移** | 无。P-R4 加字段 `error_continue` 走 Pydantic 默认值, 老请求不带也能跑。 |
| **接口自动化** | 完全无影响, 本批只动 `croe/play/*` 和 `croe/play/executor/step_content_strategy/*` |
| **回归** | 421 pass, 0 fail (414 旧 + 7 新) |
| **性能** | P-R2 省 1 次 query / task; P-R3 省 N 次 query / case (N=retry); 其余 3 个是行为修正, 无性能变化 |

## 4. 关键约定 (本批遵循)

- **BUG_ID 在 _bug_ids.py**: `tests/croe/play/_bug_ids.py` 集中放常量, 后续测试 / commit msg / 报告 三处引用一致
- **修复注释格式**: `# BUG-{ID} 修复: 一句话根因 + 一句话修法 + 为什么方案 B 不行`
- **测试加 BUG_ID 引用**: 每个测试函数 docstring 头部 `BUG-ID: P-R1` 等, 方便 `pytest --collect-only` 反查
- **测试不加 DB**: 用 `inspect.getsource()` + 正则 + mock 锁产品代码, 不依赖真实 MySQL

## 5. 下批 (P1-1..P1-8, 见 `PLAY_REVIEW_2026_06_21.md` §0)

8 个 P1 高 ROI: mapper 吞 traceback / 模型大写 I 错属性 / rate_number 类型错 / 写结果参数大写 / __repr__ 末尾双 `> />` / write_content_result 行为不一致 / name mangling / init_case_vars 失败 raise 等。
