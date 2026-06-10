# P1 级别 BUG 修复记录

> **修复日期**: 2026-06-10
> **修复范围**: 代码审查报告中标记为 P1 的 10 个问题

---

## 修复概览

| # | 文件 | 问题 | 修复方式 |
|---|------|------|---------|
| 1 | `interfaceConditionMapper.py` | 先删接口再查条件存在 | 先查条件，不存在直接 return |
| 2 | `interfaceLoopMapper.py` | 先删接口再查 loop 存在 | 先查 loop，不存在直接 return |
| 3 | `interfaceGroupMapper.py` | 先删接口再查组存在 | 先查组，不存在直接 return |
| 4 | `__init__.py:627` | `search_conditions` list 用 `and_` | 改为 `field.in_(value)` |
| 5 | `__init__.py:770` | `page_by_module` 异常返回 `[]` | 改为返回正确的分页 dict |
| 6 | `statistics/__init__.py:119` | `fetchone()` 返回 None 直接访问属性 | 增加 `apis and apis.xxx` 判空 |
| 7 | `testcaseMapper.py:561` | `remove_case` 只删部分关联 | 补全级联删除（步骤、动态、需求关联、计划关联、用例本体） |
| 8 | `file/fileMapper.py:23` | 物理文件在 DB commit 前删除 | 把文件删除移到事务之外 |
| 9 | `__init__.py:24` | `calc_total_pages` None 检查顺序 | `total == 0 or total is None` → `total is None or total == 0` |
| 10 | `interfaceMapper.py:361` | `_get_or_create_module` 条件错误 | `parent_id` → `project_id` |

---

## 详细修复说明

### 1-3. 先查存在再删关联（3 个文件）

**问题**: `delete_condition`、`delete_loop`、`remove_group` 都是先执行 `DELETE Interface` 再查父实体是否存在。如果父实体不存在，接口已经被误删且无法恢复。

**修复**: 调整执行顺序为：先查父实体 → 不存在则 return → 存在则删关联接口 → 删父实体。

```python
# 修复前（condition 为例）
await session.execute(delete(Interface).where(...))  # ← 先删接口
condition = await cls.get_by_id(ident=condition_id)   # ← 再查条件
if not condition:
    return False  # 接口已丢

# 修复后
condition = await cls.get_by_id(ident=condition_id)   # ← 先查条件
if not condition:
    return False  # 安全返回，什么都没删
await session.execute(delete(Interface).where(...))  # ← 再删接口
```

---

### 4. `__init__.py:627` — search_conditions list 永假

**问题**: `field=[1,2,3]` 被转成 `field=1 AND field=2 AND field=3`，永远为 False。

**修复**:
```python
# 之前
conditions.append(and_(*[field == v for v in value]))

# 之后
conditions.append(field.in_(value))
```

---

### 5. `__init__.py:770` — page_by_module 异常返回类型不一致

**问题**: 正常返回 `{"items": [...], "pageInfo": {...}}`，异常返回 `[]`，调用方解包时崩溃。

**修复**:
```python
# 之前
return []  # TypeError: list indices must be integers or slices, not str

# 之后
return {"items": [], "pageInfo": {"total": 0, "pages": 0, "page": 0, "limit": page_size}}
```

---

### 6. `statistics/__init__.py:119` — fetchone() None

**问题**: `fetchone()` 当日无记录时返回 None，直接访问 `apis.date` 触发 `AttributeError`。

**修复**: 所有访问点增加 `apis and apis.xxx` 判空。

---

### 7. `testcaseMapper.py:561` — remove_case 级联删除

**问题**: 原代码分支逻辑错误：
- 公共用例 → 只删需求关联，不删用例本体 → 孤儿用例
- 非公共用例 → 只删用例本体，不清理步骤/动态/关联 → 孤儿记录

**修复**: 统一走完整级联删除：
1. 删 `CaseStepDynamic`（步骤动态）
2. 删 `TestCaseStep`（用例步骤）
3. 删 `RequirementCaseAssociation` + 更新需求计数
4. 删 `PlanCaseAssociation`（计划关联）
5. 删 `TestCase`（用例本体）

---

### 8. `file/fileMapper.py:23` — 文件删除顺序

**问题**: `FileManager.delFile(path)` 在 `session.begin()` 事务内执行。如果文件删除成功但 DB 事务回滚，文件永久丢失且 DB 仍有记录。

**修复**: 把 `path` 提取到事务外，DB commit 完成后再删物理文件。

```python
path = None
async with cls.session_scope(session=session) as session:
    async with session.begin():
        file = await cls.get_by_uid(...)
        if file:
            path = file.file_path
            await session.delete(file)
# DB 已 commit
if path:
    FileManager.delFile(path)
```

---

### 9. `__init__.py:24` — calc_total_pages None 检查

**问题**: `total == 0 or total is None` 中，`total=None` 时 `total==0` 为 False，走入 `ceil(None/page_size)` 抛 `TypeError`。

**修复**:
```python
# 之前
if total == 0 or total is None:

# 之后
if total is None or total == 0:
```

---

### 10. `interfaceMapper.py:361` — _get_or_create_module 查询条件

**问题**: 查询条件用了 `Module.project_id == parent_id`，但方法参数中 `parent_id` 是父模块 ID，`project_id` 才是项目 ID。导致重复创建同名模块。

**修复**:
```python
# 之前
Module.project_id == parent_id

# 之后
Module.project_id == project_id
```

---

## 验证结果

```bash
python3 -m py_compile __init__.py interfaceConditionMapper.py interfaceLoopMapper.py interfaceGroupMapper.py interfaceMapper.py statistics/__init__.py testcaseMapper.py file/fileMapper.py
# 输出: SYNTAX_OK
```

---

*修复完毕，建议继续处理 P2 级别问题。*
