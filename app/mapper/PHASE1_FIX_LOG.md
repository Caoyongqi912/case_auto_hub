# Phase 1 修复日志

> **执行日期**: 2026-06-09  
> **执行范围**: `app/mapper/__init__.py` + 2 个子类 Mapper + 1 个调用方  
> **验证结果**: `python3 -m py_compile` 全部通过

---

## 修改文件清单

| 文件 | 修改行数 | 说明 |
|------|---------|------|
| `app/mapper/__init__.py` | +115 / -43 | transaction() + delete_by_id + delete_by_uid + bulk_update + bulk_delete + search_conditions + sorted_search |
| `app/mapper/interfaceApi/interfaceCaseContentMapper.py` | +18 / -10 | get_by_id 恢复基类签名 |
| `app/mapper/interfaceApi/interfaceVarsMapper.py` | +16 / -7 | query_by 重命名为 query_vars |
| `app/controller/interface/interfaceCaseController.py` | +3 / -1 | 调用方同步修改 |

---

## 逐项修改记录

### 1. `transaction()` 支持外部 session

**位置**: `app/mapper/__init__.py:824`  
**问题**: transaction() 总是创建新 session，不支持外部传入，导致子类被迫自行管理事务  
**修改**: 添加 `session: AsyncSession = None` 参数，传入时复用，未传入时自动创建 + begin

```python
# 修改前
async def transaction(cls) -> AsyncGenerator[AsyncSession, None]:
    async with async_session() as session:
        async with session.begin():
            yield session

# 修改后
async def transaction(cls, session: AsyncSession = None) -> AsyncGenerator[AsyncSession, None]:
    if session is not None:
        yield session
    else:
        async with async_session() as session:
            async with session.begin():
                yield session
```

**兼容性**: 所有现有 `cls.transaction()` 调用（不传参）行为完全一致

---

### 2. `delete_by_id` — 外部 session 不擅自 commit

**位置**: `app/mapper/__init__.py:265`  
**问题**: Critical — 外部传入 session 时仍调用 `session.commit()`，破坏调用方事务原子性  
**验证**: 全局搜索确认无任何调用方传 session，但修复后语义正确

```python
# 修改前
if session:
    await session.execute(stmt)
    await session.commit()
else:
    async with async_session() as session:
        await session.execute(stmt)
        await session.commit()

# 修改后
if session is not None:
    await session.execute(stmt)
    await session.flush()
else:
    async with cls.transaction() as session:
        await session.execute(stmt)
```

---

### 3. `delete_by_uid` — 改为 `transaction()` 统一管理

**位置**: `app/mapper/__init__.py:250`  
**问题**: High — 手动 `async_session() + commit`，异常时无法回滚  
**修改**: 统一使用 `cls.transaction()`

---

### 4. `bulk_update` — 消除 `if session` 分支

**位置**: `app/mapper/__init__.py:789`  
**问题**: High — 手动 commit，无事务保护；`if session` 分支重复代码  
**修改**: 统一用 `cls.transaction(session)`，减少 ~12 行重复代码

---

### 5. `bulk_delete` — 消除 `if session` 分支

**位置**: `app/mapper/__init__.py:816`  
**问题**: High — 同上  
**修改**: 统一用 `cls.transaction(session)`，减少 ~10 行重复代码

---

### 6. `search_conditions` — 字段名校验

**位置**: `app/mapper/__init__.py:522`  
**问题**: High — `getattr(model, field_name)` 无校验，非法字段导致 500  
**修改**: 使用 `model.__table__.columns` 进行 O(1) 字典校验

```python
if field_name not in model.__table__.columns:
    raise CommonError(f"Invalid field name: {field_name}")
```

---

### 7. `sorted_search` — 排序字段校验

**位置**: `app/mapper/__init__.py:486`  
**问题**: High — 同上  
**修改**: 同上，校验排序字段名

---

### 8. `InterfaceCaseContentMapper.get_by_id` — 恢复基类签名

**位置**: `app/mapper/interfaceApi/interfaceCaseContentMapper.py:55`  
**问题**: High — 重写后签名不兼容（session 变必填、缺少 desc、with_relations 未使用）  
**修改**:
- `session` 恢复为 `session: AsyncSession = None`
- 删除未使用的 `with_relations` 参数
- 新增 `desc: str = ''` 保持与基类兼容
- 使用 `cls.session_scope(session)` 处理 session
- 异常从 `ValueError` 改为 `NotFind`（与基类对齐）

---

### 9. `InterfaceVarsMapper.query_by` → `query_vars`

**位置**: `app/mapper/interfaceApi/interfaceVarsMapper.py:81`  
**问题**: High — 完全重写基类签名，破坏里氏替换  
**修改**:
- 方法重命名为 `query_vars`
- 改用 `cls.session_scope()` 替代直接 `async_session()`
- 调用方 `interfaceCaseController.py:464` 同步修改

---

## 修复后验证

```bash
$ python3 -m py_compile app/mapper/__init__.py app/mapper/interfaceApi/interfaceCaseContentMapper.py app/mapper/interfaceApi/interfaceVarsMapper.py app/controller/interface/interfaceCaseController.py
✅ 所有文件语法检查通过
```

---

*Phase 1 修复完成。共修复 9 项问题，涉及 4 个文件。*
