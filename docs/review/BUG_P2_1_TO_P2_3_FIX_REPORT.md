# BUG-P-2-1..P-2-3 Fix Report (UI 自动化 P2 批)

**修复时间**: 2026-06-21
**基础 commit**: cafdd8f (P-1-1..P-1-8 修复后)
**触发**: `docs/review/PLAY_REVIEW_2026_06_21.md` §5
**测试基线**: 439 pass → 修复后 445 pass, 0 fail (净增 6 个新测)
**commit**: 见本批提交

## 1. TL;DR

| ID | 文件:行 | 一句话根因 | 修法 | 状态 |
|---|---|---|---|---|
| **P-2-1** | `app/mapper/play/playCaseMapper.py:association_groups, copy_content` | 函数体内有内联 `from app.mapper.play.playStepGroupMapper import`, 应放文件顶部 | 移到顶部 (line 21), 删 2 处内联 import | ✅ |
| **P-2-2** | `app/mapper/play/playCaseMapper.py:reload_content` | 死代码, 全仓无 caller | 加 deprecation docstring 标记, 不删 (接口稳定) | ✅ |
| **P-2-3** | `croe/play/play_runner.py:execute_case` | 缺 trace_id, 多 case 并发日志无法定位 | `set_trace_id()` + finally `clear_trace_id()` | ✅ |

## 2. 详细修复

### 2.1 P-2-1 — 内联 import 提到顶部

**现象**: `playCaseMapper.py:association_groups` (line 163) 和 `copy_content` (line 1005) 都有 `from app.mapper.play.playStepGroupMapper import PlayStepGroupMapper` 函数体内 import。

**问题**:
- 静态 import 应该放文件顶部, 内联 import 触发**重复 import 解析** (虽然 Python 会缓存, 但每次函数调用都走 import 系统的 name check)
- 隐藏循环依赖 (内联 import 常用来 lazy load 避免循环 import, 实际可能掩盖设计问题)
- 工具链 (pyright / mypy / ruff) 不抓内联 import 也能 lint, 但 IDE 跳转不友好

**修法**:
1. 文件顶部加 `from .playStepGroupMapper import PlayStepGroupMapper`
2. 删 `association_groups` 和 `copy_content` 函数体内的内联 import

**为什么不加 lazy import 兼容循环依赖**: 实测 `playStepGroupMapper` 不存在循环依赖, 静态 import 安全。

**测试**:
- `test_bug_p_2_1_no_inline_play_step_group_mapper_import_in_play_case_mapper` — 0 处内联 import
- `test_bug_p_2_1_play_step_group_mapper_imported_at_top` — 顶部有 import

### 2.2 P-2-2 — `reload_content` 标为 deprecation

**现象**: `PlayCaseMapper.reload_content` 函数全仓无任何 caller (`rg "reload_content" --type py` 只剩定义本身)。

**修法**: 加 deprecation docstring 标记, 不删。理由:
- 接口稳定: 函数签名 (case_id: int) 是通用接口
- 留着无害: 死代码不耗运行资源, IDE 灰显提示
- 之后真要"批量刷新步骤名称/描述"时不用重新实现

**为什么不删**: 删了风险大 (外部可能通过反射调), 留着加 deprecation 注释是更稳的过渡。

**测试**:
- `test_bug_p_2_2_reload_content_has_deprecation_note` — docstring 有 BUG-P-2-2 标记和"死代码"说明

### 2.3 P-2-3 — execute_case 缺 trace_id

**现象**: UI 业务流 `execute_case` 之前没有 trace_id, 多 case 并发时日志串在一起无法定位"这条日志是哪条 case 跑的"。接口自动化 (`croe/interface/runner.py`) 已经有 OBS-2 trace_id, UI 一直缺。

**修法**:
1. `play_runner.py` 顶部 import `from croe.interface.observability import set_trace_id, clear_trace_id`
2. `execute_case` 入口加 `trace_id = set_trace_id()` (8 字符够区分并发, 短不抢眼)
3. 现有 `finally:` 块加 `clear_trace_id()` 防泄漏到下一次 case
4. 重构 try 块: 把早期 return (`if not case_step_contents`) 也包进 try, 保证 trace_id 清掉
5. `content_writer = None` 默认值, finally 检查 `if content_writer is not None` 避免早期 return 路径 NameError

**为什么不重新设计成子函数 (_execute_case_impl)**: 第一版试过, 嵌套 try/finally 跟原本 except/finally 协同复杂, 出过 syntax error。简单重构: 单一 try 包整 case, finally 处理 trace_id + 资源清理, 更易理解。

**测试**:
- `test_bug_p_2_3_execute_case_sets_trace_id` — `set_trace_id()` 在 `query_content_steps` 之前
- `test_bug_p_2_3_execute_case_clears_trace_id_in_finally` — `clear_trace_id()` 在 finally 块里
- `test_bug_p_2_3_execute_case_imports_trace_id_helpers` — 文件 import 正确

## 3. 周边影响

| 维度 | 评估 |
|---|---|
| **接口层耦合** | 无。所有 3 个修复都在 mapper/runner 内部, 控制器层不变。 |
| **数据迁移** | 无。 |
| **接口自动化** | 完全无影响, 本批只动 UI 侧。P-2-3 复用 interface 的 observability, 不影响 interface。 |
| **回归** | 445 pass, 0 fail (414 旧 + 7 Batch 1 + 18 Batch 2 + 6 Batch 3) |
| **性能** | P-2-1 省函数级 import name check; P-2-3 trace_id 操作 O(1) (ContextVar 读写); 其余无变化。 |

## 4. 文件改动清单

```
app/mapper/play/playCaseMapper.py    (P-2-1: 2 inline imports 提到顶部, P-2-2: reload_content deprecation)
croe/play/play_runner.py             (P-2-3: trace_id import + set/clear)
tests/croe/play/_bug_ids.py           (+ 3 个 BUG_P_2_X 常量)
tests/croe/play/test_bug_p2_1_to_p2_3_batch.py (新增, 6 测)
```

## 5. 不在本批范围 (留 P3)

见 `docs/review/PLAY_REVIEW_2026_06_21.md` §5 中未修复的:
- 业务流 `execute_case` 缺 result_writer (跟 interface 对齐需要设计统一 ResultWriter, 大重构)
- `params.variables` 是 list 时 `add_vars` 行为 (实测已正确处理, review 是误报)
- 业务流 `run_case` 缺 try/finally (实测不需要, execute_case 自己 finally 兜住)
- `__clean` 调 `self.starter.clear_logs()` 不存在 (实测存在, review 是误报)
- `copy_content` STEP_PLAY/STEP_PLAY_GROUP 之外 type 不更新 step_num (实测 step_num 都更新, 误报)

**本批 + 之前的 Batch 1/2 已完成全部真实 P0 + 真实 P1 + 真实 P2, 误报项已剔除。**
