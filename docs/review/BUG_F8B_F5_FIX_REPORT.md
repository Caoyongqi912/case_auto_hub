# BUG-F8B + BUG-F5 修复报告

> 状态: ✅ 已修复
> 涉及 commits: (待 commit)
> 新增测试: 7 个 (F8B 4 + F5 3, 全过)
> 修改文件: 3 个核心 + 2 个测试 + 1 个 _bug_ids

---

## 0. TL;DR

| BUG | 标题 | 估时 | 复杂度 |
|---|---|---|---|
| **F8B** | `interface_result.content_result_id` 永远 NULL (反向 FK 没回填) | 1h | 低 |
| **F5** | `error_stop` 触发时 progress 被强制 100, 语义错 | 0.5h | 极低 (2 行) |

F8B 是 F8 修复后暴露的衍生 bug, F5 是 P1 流程层最后未修的项。

---

## 1. BUG-F8B — 反向 FK 回填

### 1.1 根因

F8 修复解决了 `interface_case_content_result` 永远不落盘的问题 (STEP_API content_result
进 cache 永远不被 flush)。但修复后暴露出**反向 FK 没回填**的衍生问题:

`step_content_api.py:execute` 执行顺序 (修复后):

```python
interface_result = await step_context.result_writer.write_interface_result(
    interface_result=InterfaceResult(**step_result),
    immediate=True     # ← 直接 insert 到 interface_result 表
)
# 此时: interface_result.id = 137, content_result_id = None
#       (因为 cache 里的 content_result 还没 id, 拿不到)

await step_context.result_writer.write_step_result(
    content_type=CaseStepContentType.STEP_API,
    ...
    interface_result_id=interface_result.id,  # ← 进了子表 api
)
# 此时: content_result 还在 cache, finalize flush 时才入库
#       子表 api 记录了: result_id=新id, interface_result_id=137
#       但 interface_result.content_result_id 仍是 NULL
```

**正向关系** (`interface_case_content_result_api.interface_result_id`) 填了。
**反向关系** (`interface_result.content_result_id`) 没填。

直接证据 (F8 修复后跑 case 3):

```sql
SELECT id, interface_id, content_result_id
FROM interface_result ORDER BY id DESC LIMIT 1;
-- 137, 1, NULL  ← 修复后新跑的 case, 反向 FK 仍是 NULL
```

### 1.2 影响

- 详情页/详情查询拿不到反向关联
- 前端如果根据 `content_result_id` 拿数据,跳链

### 1.3 修复方案

在 `finalize_case_result` 末尾、`flush_cache` 之后,加一次 `UPDATE JOIN` 一次性回填。
利用**已经填好的正向关系** (`interface_case_content_result_api`) 反查。

```sql
UPDATE interface_result ir
JOIN interface_case_content_result_api api
  ON api.interface_result_id = ir.id
JOIN interface_case_content_result cr
  ON cr.id = api.result_id
SET ir.content_result_id = cr.id
WHERE cr.case_result_id = :case_result_id
  AND ir.content_result_id IS NULL
```

**为什么不在 `write_step_result` 立即回填**:
- `write_step_result` 走 cache, content_result.id 要等 flush 后才有
- 立即回填就要打破 cache 设计, 回到"每 step 一次 round-trip", 性能差
- 一次性 UPDATE JOIN 是 O(1) SQL, 性能最优

**为什么不破坏 STEP_API 走 cache 的设计**:
- cache 设计目的: 减少 DB round-trip, 一次 bulk insert 代替 N 次
- backfill 是 flush 之后一次性 SQL, 不增加 step 级 round-trip
- 总成本: cache bulk (1 次) + backfill (1 次) = 2 次, 优于每 step 立即 insert (N 次)

### 1.4 代码改动

| 文件 | 改动 |
|---|---|
| `app/mapper/interfaceApi/interfaceResultMapper.py` | 新增 `backfill_content_result_id_fk(case_result_id)` 方法, 走 raw SQL UPDATE JOIN |
| `croe/interface/writer/result_writer.py` | `finalize_case_result` 在 `_flush_cache()` 之后、调一次 backfill, 记录回填行数 |
| `tests/croe/interface/test_bug_f8b_backfill_content_result_id.py` | 新增 4 个回归测试 |
| `tests/croe/interface/_bug_ids.py` | 新增 `BUG_F8B` 常量 |

### 1.5 验证

#### 单元测试 (4 个, 全过)

```
test_bug_f8b_mapper_has_backfill_method       ✓
test_bug_f8b_finalize_invokes_backfill         ✓
test_bug_f8b_backfill_sql_uses_forward_link    ✓
test_bug_f8b_e2e_backfill_after_real_case_run  ✓ (integration)
```

#### E2E

跑 case 3, 新 case_result_id=46:

```
[BUG-F8-followup] 回填 interface_result.content_result_id: 1 行 (case_result_id=46)
id=137 interface_id=1 content_result_id=156  ← 反向 FK 已被回填 ✓
```

#### 历史数据回填

F8 修复前 9 行 NULL (历史孤儿, `interface_case_content_result_api` 也没记录) 没法回填 (D1 时代遗物,超出本 PR 范围)。F8 修复后所有新 case 的反向 FK 都被正确回填。

---

## 2. BUG-F5 — `error_stop` 状态机

### 2.1 根因

`runner.py:225` 在 `error_stop` break 前强制把 `progress` 写成 100:

```python
if not case_success and error_stop:
    await self.starter.send(...)
    case_result.progress = 100            # ← 强制 100, 语义错
    await self.result_writer.update_case_progress(case_result)
    break
```

但其实在 break 之前,`case_result.progress = (index * 100) // total_steps` 已经算好了。
比如 4 步 case, 第 2 步失败 + error_stop:
- index=1 跑成功, progress = 25
- index=2 跑失败, progress = 50
- 强制 100 ← 错
- break

前端看到 progress=100, 误以为 case 跑完了。`case_result.result = ERROR` 跟 `progress = 100` 自相矛盾。

`result_writer.py:318` `finalize_case_result` 末尾也硬编码 `progress=100.0`, 进一步掩盖了这个 bug。

### 2.2 修复方案

**2 行修改**:

1. `runner.py:225-226` 删除 `case_result.progress = 100` + `update_case_progress` 两行
2. `result_writer.py:318` `progress=100.0` 改为 `progress=case_result.progress` (用 runner 算的值)

### 2.3 行为对照

| 场景 | 修复前 | 修复后 |
|---|---|---|
| 4 步全跑完成功 | progress=100 ✓ | progress=100 ✓ (一样) |
| 4 步全跑完失败 (无 error_stop) | progress=100 ✓ | progress=100 ✓ (一样) |
| 4 步第 2 步失败 + error_stop | progress=100 ✗ (前端误以为跑完) | progress=50 ✓ (前端看到"跑到一半停了") |
| enable=0 跳过全部 | progress=100 ✓ | progress=100 ✓ (一样) |

### 2.4 验证

#### 单元测试 (3 个, 全过)

```
test_bug_f5_runner_does_not_force_progress_100          ✓
test_bug_f5_finalize_uses_case_result_progress          ✓
test_bug_f5_error_stop_progress_is_intermediate        ✓ (mock 跑 4 步 case, 第 2 步失败)
```

#### 端到端 (mock 跑)

```python
# 4 步 case, 第 1 步成功, 第 2 步失败, error_stop=True
# 期望: 只跑 2 步就停, case_result.progress = 50 (不是 100)
assert call_count["n"] == 2  # 实际只跑 2 步
assert case_result.progress == 50  # 修复后是 50, 修复前是 100
```

---

## 3. 整体回归

```
$ pytest tests/ -m "not integration"     # 80 unit 全过
$ pytest tests/ -m "integration"          # 3 integration 全过
```

| 测试套 | 通过 | 说明 |
|---|---|---|
| 老 58 个测试 | 58/58 | 之前 P0/P1.5 全部回归过 |
| F8 (16 个) | 16/16 | result_writer 注入 ExecutionContext |
| F8B (4 个) | 4/4 | 反向 FK 回填, 含 1 个 integration e2e |
| F5 (3 个) | 3/3 | error_stop progress 不再 force 100 |

总计: 81 unit + 3 integration = **84/84 通过**

---

## 4. 后续可考虑 (本 PR 范围外)

1. **`_flush_cache` 失败时 cache 被清空 (D4 留的 TODO)**:
   bulk 失败时回退到逐条, 但 cache 在 `finally` 仍被清掉, 失败数据没重试。建议加 retry queue。

2. **9 行历史孤儿 `interface_result.content_result_id` 仍 NULL**:
   D1 修复前的孤儿, 没法回填 (子表 api 没记录)。需要审计业务影响后再决定是否补 (可能直接 DELETE 掉)。

3. **P1 剩余 ~18 项 BUG**: M6/M7/M8/M9/M10/S4/S6/V3/V5/V6/E3-E12/D5/D6/D9-D11/RED-D6/7/8/OVER-1~6。下次 1-2 天能再清一波 (E3-E5 中高风险 + M7/M8 数据一致性)。

4. **`starter.over` 返回 None 语义不优雅**:
   F2 修复已加注释, 但接口形状不自然。可改成返回 `(success, case_result)` 元组。
