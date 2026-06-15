# 代码审查报告：用例导出 / M1 M2 导入导回链路

- **审查日期**：2026-06-15
- **审查范围**：以工作树未提交 diff（`app/service/m2ImportService.py` 事务重构）为核心，覆盖相关导出/导入 M1/M2 链路代码
  - `app/service/m2ImportService.py`
  - `app/service/m2PlanImportService.py`
  - `app/service/exportCaseService.py`
  - `app/mapper/test_case/testcaseMapper.py`
  - `app/controller/test_case/test_case.py`
- **审查目标**：
  1. 发现潜在 BUG
  2. 发现冗余/重复实现
  3. 发现性能优化空间

---

## 发现总览

共识别 **15 条 finding**，按严重程度排序：

| 优先级 | 数量 | 类别 |
|--------|------|------|
| P0 - 立即修复 | 5 | 关键 BUG |
| P1 - 尽快修复 | 4 | 事务/一致性问题 |
| P2 - 建议优化 | 4 | 性能/冗余 |
| P3 - 关注 | 2 | 可维护性/边界风险 |

---

## 详细发现列表

### P0 - 关键 BUG

#### 1. `app/controller/test_case/test_case.py:459`

**问题**：`import_preview` 缓存 `valid_cases=[]`，但 M2 commit 读 `valid_cases` 字段

**详细说明**：
`import_preview` 调用 `_cache_service.save_preview` 时把解析后的有效行存到 `valid_rows`，而 `valid_cases=[]`（注释写"老字段，导回不用"）。但 `M2ImportService._validate_m2_template` 取的是 `preview.get("valid_cases")`，导致该字段为空。

**触发场景**：用户走 `/import/preview` + `/import/commit` 路径时，commit 阶段直接抛出"没有可入库的有效用例"，M2 导回流程完全不可用。

**修复建议**：统一字段名，或在 `_validate_m2_template` 中兼容 `valid_rows` 作为 fallback。

---

#### 2. `app/service/exportCaseService.py:128`

**问题**：falsy-zero 检查 `group_key or -1` 把 ID=0 的根节点当作缺失

**详细说明**：
```python
group_key = (
    case.get("plan_module_id") if self.scope_type == "plan" else case.get("module_id")
)
group_path = self.group_path_map.get(group_key or -1, "")
```
当 `module_id=0` 或 `plan_module_id=0` 时，`group_key or -1` 因 0 为 falsy 而回退到 -1，`group_path_map` 中无 -1，返回空字符串。

**触发场景**：根节点 ID 为 0 的用例导出时"所属分组"列显示空白；再导入时这些用例被当作未分组/走 root 兜底，破坏目录结构。

**修复建议**：显式判断 `None`：`group_path_map.get(group_key) if group_key is not None else ""`。

---

#### 3. `app/service/m2ImportService.py:298`

**问题**：`_split_known_new` 用 `cid == 0` 判断，漏掉字符串 `"0"`

**详细说明**：
```python
if cid is None or cid == "" or cid == 0:
    new_cases.append(c)
else:
    known_cases.append(c)
```
Excel 中的 `case_id` 若被解析为字符串 `"0"`，上述条件均不成立，该行走 known 路径。

**触发场景**：commit 阶段 `int("0") = 0` 找不到对应 case，整批回滚。

**修复建议**：统一先 `int(cid)` 再判断，或增加 `cid == "0"` 分支。

---

#### 4. `app/mapper/test_case/testcaseMapper.py:564`

**问题**：循环内 `cases.index(case_data)` 既 O(n²) 又对重复 dict 返回首匹配索引

**详细说明**：
```python
for case_data in cases:
    mid = case_module_map.get(cases.index(case_data), module_id)
```
`list.index()` 使用 `==` 比较 dict，时间复杂度 O(n)，且对内容相同的 dict 永远返回第一个匹配位置。

**触发场景**：导入多条数据完全相同的用例时，第二条及以后拿到第一条的索引，`case_module_map` 返回错误的 `module_id`，导致后续重复用例被错误归类到另一个目录。

**修复建议**：改用 `enumerate(cases)` 获取真实索引。

---

#### 5. `app/mapper/test_case/testcaseMapper.py:583`

**问题**：`on_duplicate=skip` 的查重与主插入分属两个 transaction，存在 TOCTOU 竞态

**详细说明**：
```python
async with cls.transaction() as session:
    rows = (await session.execute(dup_stmt)).all()
# ... 后续又开一个 transaction ...
async with cls.transaction() as session:
    # 主插入逻辑
```

**触发场景**：并发导入相同 `(module_id, case_name)` 的两请求都通过独立事务的重复检查，随后各自在主事务中插入，最终产生本应运跳过的重复用例。

**修复建议**：将查重与插入放入同一个 transaction；或添加数据库唯一约束兜底。

---

### P1 - 事务/一致性问题

#### 6. `app/service/m2ImportService.py:220`

**问题**：DB commit 与 Redis `mark_committed` 非原子，Redis 失败后可重入导致重复插入

**详细说明**：
```python
await session.commit()
# ...
await self.cache.mark_committed(file_md5, user.id)
```
DB 事务成功后，Redis 标记在事务外执行。

**触发场景**：Redis 故障/网络抖动时 `mark_committed` 失败，用户看到错误并重试；第二次 commit 重新 INSERT 所有 new cases，造成重复 TestCase 数据。

**修复建议**：采用"先标记 Redis 为处理中，再提交 DB，最后确认 Redis"的两阶段模式；或在 DB 层增加幂等/唯一约束。

---

#### 7. `app/service/m2PlanImportService.py:369`

**问题**：plan 路径同样存在 DB commit 与 Redis `mark_committed` 非原子

**触发场景**：Redis 标记失败导致重试时，已插入的 library TestCase、PlanCaseAssociation、case_dynamic 被再次创建，plan 下出现重复关联与重复审计记录。

**修复建议**：与 finding 6 一致，增加幂等机制。

---

#### 8. `app/service/m2PlanImportService.py:121`

**问题**：new case 存在时 plan 存在性检查移到主事务外的 `pre_session`

**详细说明**：
```python
async with async_session() as pre_session:
    plan = await PlanMapper.get_by_id(ident=plan_id, session=pre_session)
    if plan is None:
        raise CommonError(...)
    project_id = plan.project_id
```

**触发场景**：plan 在 pre-read 与主事务之间被删除，代码仍使用 stale `project_id`，为已删除的 plan 创建 `plan_root`、`PlanCaseAssociation`、`case_dynamic` 等孤儿数据。

**修复建议**：在主事务内重新校验 plan 存在性，或把 plan 查询合并进主事务。

---

#### 9. `app/service/m2ImportService.py:156`

**问题**：`group_path -> module_id` 解析被提到主事务外，校验与插入不在同一事务视图

**详细说明**：
```python
case_module_map = await self._resolve_module_ids(new_cases, project_id)
```
该调用在 `async with async_session() as session:` 之前执行。

**触发场景**：目录在主事务外校验成功后被删除或移动，主事务内仍用旧的 `module_id` 插入，触发 FK 约束失败或产生 `module_id` 指向不存在目录的孤儿 TestCase。

**修复建议**：根本解法是修复 `ModuleMapper.find_path` 使其接受外部 session 参数，让解析能在同一事务内完成。

---

#### 10. `app/service/m2ImportService.py:176`

**问题**：手写 `async_session() + begin/commit/rollback` 绕过 `Mapper.transaction`

**详细说明**：
```python
async with async_session() as session:
    try:
        await session.begin()
        # ...
        await session.commit()
    except Exception:
        await session.rollback()
        raise
```

**触发场景**：后续维护者在 `commit()` 内新增 mapper 调用时若忘记显式传 `session=session`，mapper 会走 `session_scope()` 开启新的 scoped session，写操作落到另一个事务；外层回滚时内层已提交，破坏单事务原子性。

**修复建议**：在 `Mapper.transaction()` / `session_scope()` 底层修复 scoped_session 生命周期问题，而不是在每个调用方手写事务。

---

### P2 - 性能优化

#### 11. `app/service/m2ImportService.py:397`

**问题**：`_apply_known_case` 在 `_fetch_old_cases` 已批量加载后仍逐条 `get_by_id`

**详细说明**：
```python
old_map = await M2ImportService._fetch_old_cases(known_ids, session)
# ...
case_obj = await TestCaseMapper.get_by_id(ident=case_id, session=session)
```

**触发场景**：N 条 known case 产生 N 次额外 SELECT；大文件高并发导入时显著增加 DB round-trip 与延迟，且 `_fetch_old_cases` 已持有这些对象，完全可复用。

**修复建议**：从 `old_map` 直接取已加载的 ORM 对象，避免再次 `get_by_id`。

---

#### 12. `app/service/m2PlanImportService.py:181`

**问题**：known 与 new 路径各自查询 `max(order)`，可合并为一次 GROUP BY

**详细说明**：文件第 181 行附近和第 259 行附近分别执行结构相同的聚合查询。

**触发场景**：同一次 commit 同时含 known 和 new case 时，对 `PlanCaseAssociation.order` 执行两次聚合查询，浪费一次 DB round-trip。

**修复建议**：在确定所有 `target_module_ids` 后只查询一次。

---

#### 13. `app/service/m2PlanImportService.py:349` / `app/service/m2ImportService.py:200`

**问题**：每新增一条用例单独调用 `CaseDynamicMapper.new_dynamic`，形成 N+1 INSERT

**详细说明**：
```python
for case_obj in case_objects:
    await CaseDynamicMapper.new_dynamic(
        cr=user, test_case=case_obj, session=session,
    )
```

**触发场景**：N 条 new case 产生 N 次独立的 INSERT/flush round-trip；应像 `update_batch_cases` 一样批量构造 `CaseStepDynamic` 后 `session.add_all()`，减少为一次 flush。

**修复建议**：批量构造动态记录后统一 `add_all()`。

---

### P3 - 冗余/可维护性/边界风险

#### 14. `app/service/m2ImportService.py:49`

**问题**：`_parse_steps_from_m2` 与 `testcaseMapper._parse_steps` 核心逻辑重复

**详细说明**：两者都负责把步骤 cell 拆分为步骤列表，字段映射、清洗逻辑高度重合。

**触发场景**：两套步骤解析并行维护，M1/M2 清洗规则不同步；已发现 `None/None` 时 M1 返回 `[{None,None}]` 而 M2 返回 `[]`，同一数据经不同路径导入产生不一致的步骤记录。

**修复建议**：抽取公共步骤解析函数，通过 `clean_mode` 参数区分 M1/M2 的清洗强度。

---

#### 15. `app/controller/test_case/test_case.py:571`

**问题**：`/upload` 一次性 `await file.read()` 无大小限制，存在 OOM 风险

**详细说明**：
```python
content = await file.read()
```

**触发场景**：用户上传超大 Excel 时，整个文件被读入内存；在内存受限或服务并发场景下可能触发 OOM。

**修复建议**：先校验 `Content-Length` 或 `UploadFile.size`，超过阈值直接拒绝；大文件考虑流式解析。

---

## 修复优先级建议

1. **P0（本周内）**：finding 1、2、3、4、5 —— 直接影响功能正确性或数据完整性。
2. **P1（两周内）**：finding 6、7、8、9、10 —— 事务与一致性风险，需设计修复方案。
3. **P2/P3（排期优化）**：finding 11~15 —— 性能与代码质量改进。

---

## 备注

- 本次审查基于 `git diff HEAD`（未提交修改）及相关链路代码。
- 一个 simplification angle 因 token 配额抖动返回 429，其余 8 个 finder angles 已完成，并通过主会话对关键行进行了二次验证。
