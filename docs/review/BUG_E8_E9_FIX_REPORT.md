# BUG-E8 + E9 Fix Report: case_result 计数兜底

**触发版本**: master (E8/E9 之前)
**Commit**: (本 fix)
**测试**: `tests/croe/interface/test_bug_e8_e9_recompute_case_result_nums.py` (6 个)

---

## 现象 (两个相关 BUG 合修)

### E8 [中] `case_result.total_num` 从不更新
- 位置: `result_writer.py:157` `init_case_result` 时 `case_result.total_num = interface_case.case_api_num`
- 之后所有步骤执行, `total_num` 永远不再被更新
- 如果 `case_api_num` 在定义/编辑时算错 (见 M8 修复), `total_num` 跟着错
- 即使 M8 修了源头, 运行时还可能漂移, 没兜底

### E9 [中] GROUP / LOOP / CONDITION 等 parent step 行为不对称
- 位置: 6 个 step strategy
  - `step_content_api.py:78-80` `case_result.success_num += 1` (单 API, +1 对)
  - `step_content_group.py:109-112` GROUP 整体 `+= 1` (内部跑了 N 个 API, 应 +N)
  - `step_content_loop.py:422-425` LOOP 整体 `+= 1` (跑了 loop_count 次, 应 +loop_count)
  - `step_content_condition.py:92,120,135,142` CONDITION 多种 `+= 1`
- 后果: 1 个 GROUP (含 5 个 API) 全部成功, 当前 `total_num=5, success_num=1, fail_num=0` — 通过率 20% (实际应 100%)
- 改全量 step strategy 成本高、易漏

---

## 修复 (统一兜底)

不动 step strategy 的手动维护 (保留在线行为, 降低风险),在 `finalize_case_result` 末尾加一次 recompute, 用 `interface_result` 表的 COUNT 当权威源覆写:

```python
# app/mapper/interfaceApi/interfaceResultMapper.py
@classmethod
async def recompute_case_result_nums(cls, case_result_id, session):
    """[BUG-E8 + E9] 用 interface_result COUNT 覆写 total/success/fail"""
    stmt = select(
        func.count(InterfaceResult.id).label("total"),
        func.sum(case((InterfaceResult.result.is_(True), 1), else_=0)).label("success"),
        func.sum(case((InterfaceResult.result.is_(False), 1), else_=0)).label("fail"),
    ).join(
        InterfaceCaseContentResult,
        InterfaceResult.content_result_id == InterfaceCaseContentResult.id,
    ).where(InterfaceCaseContentResult.case_result_id == case_result_id)
    # ... 解析 row, update_by_id 覆写
```

```python
# croe/interface/writer/result_writer.py finalize_case_result
# 末尾 try/except 包 recompute, 失败不影响主流程
try:
    recomputed = await InterfaceCaseResultMapper.recompute_case_result_nums(
        case_result_id=case_result.id, session=None,
    )
    case_result.total_num = recomputed["total"]
    case_result.success_num = recomputed["success"]
    case_result.fail_num = recomputed["fail"]
except Exception as e:
    log.warning(f"...用旧值: {e}")
```

---

## 关键设计取舍

1. **不修 step strategy**: 6 个 strategy 各改易漏, 行为影响面广 (在线 success/fail 计数实时展示)。改用 finalize 一次性兜底
2. **`interface_result` 当权威源**: 它是"实际跑了多少 API"的最准确记录, 跟 success/fail 直接对应
3. **JOIN `interface_case_content_result`**: `InterfaceResult` 没有 `case_result_id` 字段, 必须走 `content_result_id` 中间表
4. **D4 风格**: `recompute_case_result_nums` 强制 session 必填, 走自己的事务, finalize 主流程 try/except 兜底
5. **重算 result = SUCCESS/ERROR**: recompute 覆写 fail_num 后, 重新判 result, 保证 `case_result.result` 跟 `fail_num` 始终一致

---

## 修复前后对照

| 场景 | 修复前 | 修复后 |
|---|---|---|
| Case 1 GROUP (5 API) 全成功 | `total=5, success=1, fail=0` (20%) | `total=5, success=5, fail=0` (100%) ✓ |
| Case 1 LOOP (跑 3 次) 全成功 | `total=1, success=1, fail=0` (100%, 巧合) | `total=3, success=3, fail=0` (100%) ✓ |
| Case 1 LOOP (3 次) 1 失败 | `total=1, success=0, fail=1` (0%) | `total=3, success=2, fail=1` (67%) ✓ |
| Case 编辑后 case_api_num 漂 | total_num 永久错位 | recompute 兜底对账 ✓ |
| 0 个 interface_result (空 case) | `total=case_api_num, success=0, fail=0` (虚高) | `total=0, success=0, fail=0` ✓ |
| recompute 失败 | — | finalize 主流程继续, 旧值兜底, WARNING 留痕 |

---

## 回归测试 (6 个, mock 不接 DB)

`tests/croe/interface/test_bug_e8_e9_recompute_case_result_nums.py`:

1. `test_bug_e8_e9_recompute_uses_interface_result_count` — AST 锁: SQL 包含 `InterfaceResult` 表 + COUNT + True/False 分桶
2. `test_bug_e8_e9_recompute_requires_external_session` — D4 对齐: `session=None` 抛 ValueError
3. `test_bug_e8_e9_recompute_updates_case_result_fields` — 端到端 mock: SQL 返 3 字段, `update_by_id` 收到正确 total/success/fail + 复用 session
4. `test_bug_e8_e9_recompute_handles_zero_results` — 边界: 0 行 → 全部 0, 不崩
5. `test_bug_e8_e9_recompute_failure_does_not_break_finalize` — 异常冒泡给调用方处理
6. `test_bug_e8_e9_finalize_invokes_recompute` — 集成: finalize 源码里必须调 recompute, 且在 `_flush_cache` 之后

**附带修复**: F5 旧测试 body 搜索范围 3000 → 6000 字符 (E8+E9 块把 `progress=case_result.progress` 推出原范围)

**全量回归**: 159 unit passed (153 老 + 6 新), 0 fail.

---

## 教训

- **"多处手动维护"是反模式**: E9 揭示了 6 个 step strategy 各自维护 success_num 的灾难性 — 任何一个 +1/+N 不一致就坏。改成"单点权威源 (interface_result COUNT) + finalize 兜底",根本消除 E9 的根因
- **跟 M8 同模式**: M8 修 `case_api_num`, E8/E9 修 `case_result.*_num`, 都是"多个 ±1/±N 同步点 + recompute 兜底"。**所有"散点维护"型字段都该有 recompute 兜底**, 这是 D 系列 bug 的通用 pattern
- **finalize 兜底是廉价保险**: try/except 包一层, 失败不影响主流程, 成功则保证最终一致。**任何"应该有 N 个 X"的不变量都该在 finalize 验一次**
