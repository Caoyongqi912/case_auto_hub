# BUG-D6 Fix Report: InterfaceResult <-> APIStepContentResult 双向 FK 漂移检测 + reconcile

**触发版本**: master (D6 之前)
**Commit**: (本 fix)
**测试**: `tests/croe/interface/test_bug_d6_fk_invariant.py` (15 个)

---

## 现象 (双向 FK 漂移)

`InterfaceResult.content_result_id` (denormalized 缓存) 跟 `APIStepContentResult.interface_result_id` (ORM 创建时的 source of truth) 是同一 1:1 关系的两个方向, 应该始终指向同一对 id。任何一边漏更新就漂, 一漂就出现:

1. **`ir_missing_fk`**: `ir.content_result_id IS NULL`, `api.interface_result_id IS NOT NULL` — 子类表已建, 反向 FK 没回填。F8B 已修, 但只在 finalize 调一次, 不全面
2. **`mismatch`**: 两边都不为 NULL, 但 `ir.content_result_id != api.interface_result_id` — F8B 漏掉 (WHERE 条件只 `IS NULL`)
3. **`api_missing_fk`**: `ir.content_result_id IS NOT NULL`, `api.interface_result_id IS NULL` — 反向 FK 写了, 但子类表没记录 (子步骤被删除?)

后果: 任何 join 查询 (`InterfaceResult JOIN InterfaceCaseContentResult`) 都会拿空行 / 错行, 前端 `data: []` (D7 现象) + `step_result_id` 错位 + 报表统计失真。

---

## 修复 (invariant 检查 + reconcile 兜底)

**不删 FK (大改 schema 风险高)**, 加 2 个 mapper 方法, 一查一修:

### `find_fk_inconsistencies(case_result_id, session)`

扫出 3 种 mismatch_reason, 用 `CASE WHEN` 标 reason + LEFT JOIN 让 `api_missing_fk` 也能识别:

```sql
SELECT ir.id AS interface_result_id,
       ir.content_result_id AS ir_content_result_id,
       api.interface_result_id AS api_interface_result_id,
       CASE
         WHEN ir.content_result_id IS NULL AND api.interface_result_id IS NOT NULL
           THEN 'ir_missing_fk'
         WHEN ir.content_result_id IS NOT NULL AND api.interface_result_id IS NULL
           THEN 'api_missing_fk'
         WHEN ir.content_result_id != api.interface_result_id
           THEN 'mismatch'
         ELSE 'ok'
       END AS mismatch_reason
FROM interface_result ir
LEFT JOIN interface_case_content_result_api api
  ON api.interface_result_id = ir.id
WHERE (ir.content_result_id IS NULL OR api.interface_result_id IS NULL
       OR ir.content_result_id != api.interface_result_id)
  AND (:case_result_id IS NULL OR ir.id IN (
      SELECT ir2.id FROM interface_result ir2
      JOIN interface_case_content_result cr ON cr.id = ir2.content_result_id
      WHERE cr.case_result_id = :case_result_id
  ))
```

### `reconcile_fk_from_polymorphic(case_result_id, session)`

用 polymorphic 子类 `interface_result_id` 覆写 `IR.content_result_id`:

```sql
UPDATE interface_result ir
JOIN interface_case_content_result_api api
  ON api.interface_result_id = ir.id
SET ir.content_result_id = api.interface_result_id
WHERE (ir.content_result_id IS NULL
       OR ir.content_result_id != api.interface_result_id)
  AND (:case_result_id IS NULL OR ir.id IN (
      SELECT ir2.id FROM interface_result ir2
      JOIN interface_case_content_result cr ON cr.id = ir2.content_result_id
      WHERE cr.case_result_id = :case_result_id
  ))
```

返回 `rowcount` (修复的行数), 可被 CI / cron / 运维一次性脚本调。

---

## 关键设计取舍

1. **不删 FK**: 删 / 加双向 FK 是破坏性 schema 变更, 影响所有现存行 + ORM mapping + 迁移脚本。D6 走"加 invariant 检查 + reconcile 兜底", 风险最低, 立刻可见效
2. **D4 风格**: 两个方法都强制 `session` 必填, 拒绝隐式 commit。`find` 用 `session.execute` (调用方事务), `reconcile` 用 `session_scope` 自管事务 (一次性运维脚本不需要外部事务)
3. **`interface_case_content_result_api` 当 source of truth**: 它是 polymorphic 子类表, ORM 在 `INSERT content_result` 时就建好, 是真实"创建顺序"的源头。`interface_result.content_result_id` 是 denormalized 缓存, 漂移时以子类为准
4. **LEFT JOIN 而非 INNER**: 必须 LEFT, 否则 `api_missing_fk` 永远不出现 (INNER JOIN 会过滤掉 api 那边为 NULL 的行)
5. **`:case_result_id IS NULL` 兜底**: 允许 None=全表扫 (运维), int=精确过滤 (CI)
6. **`reconcile_fk_from_polymorphic` 处理 `ir_missing_fk` + `mismatch` 两种**: 跟 F8B 的 `backfill_content_result_id_fk` 不冲突, F8B 旧 backfill 保留 (D6 是补充, 不删), 见 `test_bug_d6_f8b_backfill_still_exists`

---

## 修复前后对照

| 场景 | 修复前 | 修复后 |
|---|---|---|
| 漂移检测能力 | F8B 只查 `ir_missing_fk` (一种) | 3 种 mismatch_reason 全识别 (`ir_missing_fk` / `api_missing_fk` / `mismatch`) ✓ |
| 漂移修复能力 | F8B `backfill_content_result_id_fk` 只修 `IS NULL` 情况 (WHERE `ir.content_result_id IS NULL`) | 修 `IS NULL` + `!=` 两种情况 (WHERE `IS NULL OR !=`) ✓ |
| 单 case vs 全表 | F8B 必须传 case_result_id (UPDATE JOIN 受 row count 影响) | `case_result_id=None` 走全表, CI 用 int 过滤 ✓ |
| 异常路径 | F8B `try/except log.error` 静默吞 | D6 让异常往外冒, 运维脚本能 fail-fast ✓ |
| 跟前端查询的协同 | D7 单独修 `data: []` (查询侧) | D6 修数据本身 (写入侧), D7 + D6 双管齐下 ✓ |
| 跟 M6 协同 | query_steps 不读 polymorphic 子类列 | D6 显式 LEFT JOIN polymorphic 子类, 跟 M6 不冲突 ✓ |

---

## 回归测试 (15 个, mock 不接 DB)

`tests/croe/interface/test_bug_d6_fk_invariant.py`:

**session 强制 (2)**:
1. `test_bug_d6_find_fk_inconsistencies_requires_session` — D4 对齐: `session=None` 抛 ValueError
2. `test_bug_d6_reconcile_fk_requires_session` — D4 对齐

**SQL 形状锁住 (6)**:
3. `test_bug_d6_find_sql_has_three_mismatch_reasons` — `CASE WHEN` 必须含 `ir_missing_fk` / `api_missing_fk` / `mismatch` / `ok`
4. `test_bug_d6_find_sql_joins_polymorphic_subtype` — `LEFT JOIN interface_case_content_result_api`
5. `test_bug_d6_find_sql_returns_dict_with_4_fields` — SELECT 4 字段 (`interface_result_id` / `ir_content_result_id` / `api_interface_result_id` / `mismatch_reason`)
6. `test_bug_d6_find_sql_case_result_id_filter_with_is_null_escape` — `:case_result_id IS NULL` 兜底
7. `test_bug_d6_reconcile_sql_is_update_join` — `UPDATE ... JOIN ... SET ir.content_result_id = api.interface_result_id`
8. `test_bug_d6_reconcile_sql_case_result_id_filter` — 同上 IS NULL 兜底

**端到端 mock (4)**:
9. `test_bug_d6_find_returns_list_of_dicts` — session.execute 返 3 行 → 3 种 reason 都被识别, `case_result_id=42` 传入
10. `test_bug_d6_find_returns_empty_list_when_no_drift` — 没漂移返空 list
11. `test_bug_d6_reconcile_returns_rowcount` — 修复 5 行返 5, commit 调
12. `test_bug_d6_reconcile_handles_zero_fixes` — 修复 0 行不崩

**异常路径 (2)**:
13. `test_bug_d6_find_propagates_db_errors` — `connection lost` 冒泡
14. `test_bug_d6_reconcile_propagates_db_errors` — `boom` 冒泡

**回归兼容 (1)**:
15. `test_bug_d6_f8b_backfill_still_exists` — F8B 旧 backfill 仍在 (D6 是补充)

**全量回归**: 174 unit passed (159 老 + 15 新), 0 fail.

---

## 教训

- **双向 FK 是反模式**: `ir.content_result_id` + `api.interface_result_id` 描述同一关系, 任何一边漏更新就漂。**所有"1:1 关系用两个 FK 描述"的设计都是埋雷**, 应该用唯一的外键 + ORM relationship, 或者干脆 NoSQL/Json
- **invariant 检查是廉价的兜底**: 加 `find_*` + `reconcile_*` 两个方法 (40 行 SQL), 就能彻底消除一类 bug。比修"为什么漏更新"成本低 10x
- **跟 F8B 协同而非替换**: D6 是 F8B 的 super-set (修 `IS NULL` + `!=`), 旧 F8B 保留 (不影响在线), 一次性 reconcile 兜底漂移
- **跟 D7 协同**: D7 修查询侧 (joinedload 漏掉 Loop), D6 修数据侧 (FK 漂移), 任何一方独立修都不够, 必须双管齐下
- **D 系列通用 pattern**: "散点维护"型字段 (case_api_num / case_result.*_num / IR.content_result_id) 都该有 invariant 检查 + 兜底, 这是 D 系列 bug 的根因模式
