# Mapper Session 管理模式集中审查与重构方案

> **审查范围**: `app/mapper/__init__.py` 及全部子类 Mapper 的 session 管理模式
> **核心问题**: `session_scope` 设计正确但几乎未被使用；`transaction()` 有设计缺陷；37 个方法重复 `if session` 分支

---

## 一、当前全景数据

### 1.1 三种 session 管理模式的使用统计

| 模式 | 使用次数 | 位置 | 问题 |
|------|---------|------|------|
| `async_session() 直接创建` | **120+** | 基类 17 + playCaseMapper 17 + playTaskMapper 10 + interfaceCaseMapper 14 + ... | **最大问题**：绕过 `session_scope`，同一请求可能创建多个 session |
| `cls.transaction()` | **130+** | 子类大量使用（planCaseMapper 21、interfaceCaseMapper 14、testcaseMapper 10...） | **设计缺陷**：不支持外部 session 传入 |
| `cls.session_scope(session)` | **~15** | 基类 3 + 零星子类 | **使用不足**：设计正确但没人用 |

### 1.2 `session=None` 参数的方法统计

- **37 个方法**声明了 `session: AsyncSession = None`
- **21 处** `if session / if session is None` 分支
- 每个分支都在重复同样的逻辑："有就复用，没有就创建"

---

## 二、`session_scope` 正确性分析

### 2.1 当前实现

```python
@classmethod
@asynccontextmanager
async def session_scope(cls, session: AsyncSession = None) -> AsyncGenerator[AsyncSession, None]:
    if session:
        yield session
    else:
        async with async_session() as s:
            yield s
```

### 2.2 设计正确性判定

| 场景 | 行为 | 是否正确 |
|------|------|---------|
| 传入外部 session | `yield session`，退出时不 close | ✅ **正确** — 生命周期由调用方管理 |
| 未传入 session | 创建新 session，`async with` 退出时 close | ✅ **正确** — 生命周期由 context manager 管理 |
| `session` 参数名 | `session` 与 yield 变量同名 | ⚠️ **有风险** — 外部 session 被 yield 后，内层代码操作的是同一个对象引用，没问题；但如果内部重新赋值会有问题 |

### 2.3 结论

**`session_scope` 的设计本身是正确的。** 问题不在于它的设计，而在于：

1. **几乎没人使用它** — 120+ 处代码直接 `async_session()`，绕过了它
2. **`transaction()` 不支持外部 session** — 导致写操作无法统一用它
3. **基类方法内部重复实现** — 37 个方法自己写 `if session`，而不是委托给 `session_scope`

---

## 三、核心问题诊断

### 问题 1：`transaction()` 不支持外部 session（设计缺陷）

```python
# 当前实现
transaction(cls) -> AsyncGenerator[AsyncSession, None]:
    async with async_session() as session:   # ← 总是创建新 session
        async with session.begin():
            yield session
```

**后果**:
- 调用方想在已有事务中执行多个操作时，无法把自己的 session 传给 `transaction()`
- 例如：子类中常见模式
  ```python
  async with async_session() as session:     # 子类自己创建
      await cls.get_by_id(..., session=session)   # 传给基类读方法
      await cls.update_by_id(..., session=session) # 传给基类写方法（但只 flush）
      await session.commit()                      # 子类自己 commit
  ```
- 如果 `transaction()` 支持外部 session，上面的代码可以简化为：
  ```python
  async with cls.transaction() as session:
      await cls.get_by_id(..., session=session)
      await cls.update_by_id(..., session=session)
      # 无需手动 commit
  ```

### 问题 2：基类方法内部重复 `if session` 分支（代码重复）

以 `query_by_in_clause` 为例：

```python
async def query_by_in_clause(cls, target, list_, session=None):
    ...
    if session:
        query = await session.scalars(stmt)
        return query.all()
    else:
        async with async_session() as session:
            query = await session.scalars(stmt)
            return query.all()
```

这段代码的 4 行中有 3 行完全重复，只是 session 来源不同。

**优化后**：
```python
async def query_by_in_clause(cls, target, list_, session=None):
    ...
    async with cls.session_scope(session) as session:
        query = await session.scalars(stmt)
        return query.all()
```

从 6 行减少到 2 行，且逻辑更清晰。

### 问题 3：子类大面积直接 `async_session()`（规范缺失）

例如 `PlayCaseMapper` 17 处、`PlayTaskMapper` 10 处直接 `async with async_session() as session:`。

这些代码：
- 不检查是否已有可用 session（`async_scoped_session` 在同一 task 内复用，但 `async with` 创建新上下文）
- 如果上层调用方已经创建了 session，会创建第二个 session，导致事务隔离
- 写操作后手动 `session.commit()`，与基类的 `transaction()` 行为不一致

---

## 四、重构方案

### 4.1 第一步：改进 `transaction()` 支持外部 session

```python
@classmethod
@asynccontextmanager
async def transaction(cls, session: AsyncSession = None) -> AsyncGenerator[AsyncSession, None]:
    """
    事务上下文管理器。

    - 如果传入外部 session：复用它，由调用方控制事务（不自动 begin/commit）
    - 如果没有传入：创建新 session + 自动 begin/commit/rollback

    典型用法：
        # 自管理事务（适用于简单写操作）
        async with cls.transaction() as session:
            await session.execute(...)

        # 在已有事务中复用（适用于复杂业务链）
        async with cls.transaction() as outer_session:
            await cls.save(session=outer_session, ...)
            await cls.update_by_id(session=outer_session, ...)
    """
    if session is not None:
        yield session
    else:
        async with async_session() as session:
            async with session.begin():
                yield session
```

**兼容性保证**:
- 所有现有 `cls.transaction()` 调用（不传参数）行为**完全一致**
- 新增能力：支持 `cls.transaction(session=xxx)` 复用外部 session

### 4.2 第二步：基类方法消除 `if session` 分支

全部改为统一使用 `session_scope(session)` 或 `transaction(session)`。

**读方法**（查询类）— 用 `session_scope`:

| 方法 | 当前行数 | 优化后行数 | 改动 |
|------|---------|-----------|------|
| `_execute_query` | 6 | 3 | `if session is None` → `session_scope(session)` |
| `get_by_id` | 12 | 5 | `if session` + `session_scope` → 统一用 `session_scope` |
| `get_by_uid` | 3 | 2 | 委托给 `_get_by_field`，后者优化 |
| `_get_by_field` | 16 | 8 | `if session` → `session_scope(session)` |
| `get_by` | 10 | 4 | `if session is None` → `session_scope(session)` |
| `query_all` | 8 | 4 | `async_session()` → `session_scope()` |
| `query_by` | 12 | 4 | `if session` → `session_scope(session)` |
| `query_by_in_clause` | 14 | 6 | `if session` → `session_scope(session)` |
| `page_query` | 18 | 10 | `async_session()` → `session_scope()` |
| `count_` | 10 | 4 | `async_session()` → `session_scope()` |
| `tables` | 10 | 4 | `async_session()` → `session_scope()` |

**写方法**（修改类）— 用 `transaction`:

| 方法 | 当前行数 | 优化后行数 | 改动 |
|------|---------|-----------|------|
| `delete_by_uid` | 8 | 4 | `async_session() + commit` → `transaction()` |
| `delete_by_id` | 12 | 4 | `if session + commit` → `transaction(session)` |
| `delete_by` | 10 | 4 | `session_scope + begin` → `transaction(session)` |
| `update_by_id` | 18 | 8 | `if session + transaction` → `transaction(session)` |
| `update_by_uid` | 12 | 5 | `async_session() + begin` → `transaction()` |
| `_manage_session` | 8 | 5 | `async_session() + begin` → `transaction(session)` |
| `bulk_insert` | 18 | 8 | `if session + transaction` → `transaction(session)` |
| `bulk_insert_models` | 16 | 6 | `if session + transaction` → `transaction(session)` |
| `bulk_update` | 24 | 8 | `if session + commit` → `transaction(session)` |
| `bulk_delete` | 22 | 6 | `if session + commit` → `transaction(session)` |

### 4.3 第三步：子类迁移策略

**不要一次性全部重构**，采用渐进式策略：

```
Phase 1（基类，30 分钟）:
  - 改进 transaction() 支持外部 session
  - 重构基类所有方法的 session 管理
  - 所有现有测试必须通过

Phase 2（子类新增代码，持续）:
  - 新写的子类方法统一使用 session_scope / transaction
  - 不再写 if session 分支
  - 不再直接 async_session()

Phase 3（子类旧代码，按需）:
  - 修改子类时顺手迁移 nearby 代码
  - 优先迁移 playCaseMapper（17 处）、playTaskMapper（10 处）等高使用文件
```

---

## 五、优化后基类代码（关键方法）

### 5.1 改进后的 `session_scope` 和 `transaction`

```python
@classmethod
@asynccontextmanager
async def session_scope(cls, session: AsyncSession = None) -> AsyncGenerator[AsyncSession, None]:
    """
    Session 上下文管理器 — 仅提供 session 生命周期管理，不管理事务。

    - 外部传入 session：复用它，不管理生命周期（调用方负责 close）
    - 无外部 session：创建新 session，退出时自动 close

    适用于：查询操作、或调用方已管理事务的写操作
    """
    if session is not None:
        yield session
    else:
        async with async_session() as s:
            yield s

@classmethod
@asynccontextmanager
async def transaction(cls, session: AsyncSession = None) -> AsyncGenerator[AsyncSession, None]:
    """
    事务上下文管理器 — 提供 session + 事务管理。

    - 外部传入 session：复用它，不自动 begin/commit（调用方负责事务）
    - 无外部 session：创建新 session + 自动 begin/commit/rollback

    适用于：需要事务保证的写操作
    """
    if session is not None:
        yield session
    else:
        async with async_session() as session:
            async with session.begin():
                yield session
```

### 5.2 读方法重构示例

```python
# 优化前
def get_by(self, session=None, **kwargs):
    model = self.__model__
    sql = select(model).filter_by(**kwargs)
    if session is None:
        async with async_session() as session:
            result = await session.scalars(sql)
    else:
        result = await session.scalars(sql)
    return result.first()

# 优化后
def get_by(self, session=None, **kwargs):
    model = self.__model__
    sql = select(model).filter_by(**kwargs)
    async with self.session_scope(session) as session:
        result = await session.scalars(sql)
        return result.first()
```

### 5.3 写方法重构示例

```python
# 优化前
def delete_by_id(self, ident, session=None):
    model = self.__model__
    stmt = delete(model).where(model.id == ident)
    if session:
        await session.execute(stmt)
        await session.commit()
    else:
        async with async_session() as session:
            await session.execute(stmt)
            await session.commit()

# 优化后
def delete_by_id(self, ident, session=None):
    model = self.__model__
    stmt = delete(model).where(model.id == ident)
    async with self.transaction(session) as session:
        await session.execute(stmt)
        if session.in_transaction():
            await session.flush()
```

> 注意：外部传入 session 时，`transaction()` 只 yield 不复用 begin，调用方自己控制 commit。内部创建 session 时自动 begin，退出时自动 commit。

---

## 六、兼容性风险评估

| 改动 | 影响面 | 风险 | 验证方式 |
|------|--------|------|---------|
| `transaction()` 支持外部 session | 所有 `cls.transaction()` 调用 | **零风险** — 不传参数时行为完全一致 | 现有测试 |
| 基类读方法改 `session_scope` | 所有读方法 | **低风险** — `session_scope(None)` 等价于原 `async_session()` | 读接口回归测试 |
| 基类写方法改 `transaction` | 所有写方法 | **低风险** — `transaction(None)` 等价于原 `async_session() + begin` | 写接口回归测试 |
| 子类迁移（渐进式） | 按文件 | **可控** — 每次只改一个文件，测试通过后再下一个 | 单元测试 |

---

## 七、执行计划

```
Step 1（5 分钟）: 改进 transaction() 支持外部 session
  - 文件: app/mapper/__init__.py
  - 修改: transaction() 方法添加 session 参数
  - 验证: 所有现有测试通过

Step 2（30 分钟）: 重构基类所有方法的 session 管理
  - 文件: app/mapper/__init__.py
  - 读方法: 统一改为 session_scope(session)
  - 写方法: 统一改为 transaction(session)
  - 删除所有 if session / if session is None 分支
  - 验证: 所有现有测试通过

Step 3（持续）: 子类代码规范
  - 新增子类方法使用 session_scope / transaction
  - 旧代码在修改时顺手迁移
  - 高优先级: playCaseMapper(17)、playTaskMapper(10)、interfaceCaseMapper(14)
```

---

## 八、关键结论

1. **`session_scope 设计正确`** — 不需要修改它的核心逻辑，只需要让它被用起来
2. **`transaction() 需要改进`** — 添加外部 session 支持，消除子类自己管理事务的需求
3. **`if session 分支是代码坏味道`** — 37 个方法、21 处分支，全部是重复逻辑，应委托给 session_scope / transaction
4. **子类直接 `async_session()` 需要逐步清理** — 这是最大的规范问题，但采用渐进式迁移，避免大爆炸式重构
