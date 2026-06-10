# P0 级别 BUG 修复记录

> **修复日期**: 2026-06-10
> **修复范围**: 代码审查报告中标记为 P0 的 5 个运行时崩溃/数据损坏问题

---

## 修复概览

| # | 文件 | 问题 | 修复方式 |
|---|------|------|---------|
| 1 | `interfaceApi/interfaceCaseContentMapper.py` | `NotFind` 未导入 | 补充导入 |
| 2 | `interfaceApi/interfaceCaseContentMapper.py` | `user.creatorName` 不存在 | 改为 `user.username` |
| 3 | `interfaceApi/interfaceMapper.py` | `asyncio.gather` 吞异常 + 并发共享 session | 改为串行执行 |
| 4 | `play/playConditionMapper.py` | `else` 附在 `for` 而非 `if quote` | 调整缩进，抽离公共逻辑 |

---

## 详细修复说明

### 1. interfaceCaseContentMapper.py — 补充 NotFind 导入

**问题**: 第 84 行 `raise NotFind(...)` 但文件头部未导入 `NotFind`，运行时触发 `NameError`。

**修复**:
```python
# 之前
from app.mapper.interfaceApi.interfaceConditionMapper import InterfaceConditionMapper
from app.model.base import User

# 之后
from app.mapper.interfaceApi.interfaceConditionMapper import InterfaceConditionMapper
from app.exception import NotFind
from app.model.base import User
```

---

### 2. interfaceCaseContentMapper.py — creatorName 属性修正

**问题**: 第 178 行 `creatorName=user.creatorName`，但 `User` 模型没有 `creatorName` 属性，只有 `username`。

**修复**:
```python
# 之前
creatorName=user.creatorName,

# 之后
creatorName=user.username,  # User 模型只有 username，没有 creatorName
```

---

### 3. interfaceMapper.py — 串行执行替代并发 gather

**问题**: `upload()` 方法使用 `asyncio.gather(*tasks, return_exceptions=True)` 批量插入接口：
- `return_exceptions=True` 导致异常被静默丢弃，数据部分写入却无报错
- 多个协程共享同一个 `AsyncSession` 并发调用 `session.add()`，SQLAlchemy session 非协程安全，会损坏 identity map

**修复**: 改为串行循环，逐个调用 `_batch_insert_apis`。

```python
# 之前
tasks = [
    cls._batch_insert_apis(session, ...)
    for idx, api in enumerate(apis)
]
await asyncio.gather(*tasks, return_exceptions=True)

# 之后
# 串行执行，避免多个协程共享同一个 AsyncSession
# AsyncSession 不是协程安全的，并发 add() 会损坏内部状态
for idx, api in enumerate(apis):
    await cls._batch_insert_apis(session, ...)
```

---

### 4. playConditionMapper.py — else 缩进修正 + 公共逻辑抽离

**问题**: `choice_common_steps` 中 `else:` 缩进和 `for` 同级，形成 Python 的 `for...else` 语法。导致 `quote=True` 时：
1. 先执行 `for` 循环（引用步骤）
2. 循环正常结束后执行 `else` 块（复制步骤）
3. 步骤被重复处理，且 `last_index` 等公共逻辑只在 `if quote:` 内部执行

**修复**:
- 把 `else:` 缩进改为和 `if quote:` 同级
- 把 `last_index`、插入关联等公共逻辑移出 `if`/`else`，确保 `quote=True/False` 都走同一段排序+关联代码

```python
# 修复前（有问题的缩进）
if quote:
    for play_step_id in play_step_id_list:
        ...
    else:  # ← 这是 for...else，不是 if...else！
        # 复制逻辑（quote=True 时也会执行）
    last_index = ...  # 只在 quote=True 时执行

# 修复后
if quote:
    for play_step_id in play_step_id_list:
        ...
else:
    # quote=False：复制步骤
    copy_jobs = []
    ...

# 公共逻辑：排序并插入关联（quote=True/False 都走这里）
last_index = await cls._get_last_step_order(condition_id, session)
content_ids = [content.id for content in case_step_content_play_step_list]
...
```

---

## 验证结果

```bash
python3 -m py_compile interfaceCaseContentMapper.py interfaceMapper.py playConditionMapper.py
# 输出: SYNTAX_OK
```

---

*修复完毕，建议按 P1 → P2 → P3 顺序继续处理剩余问题。*
