# BUG D4-V2 修复报告

**修复时间**: 2026-06-20
**HEAD**: 8066f70 → (本批 commit)
**回归测试**: 401 passed, 1 skipped, 3 deselected, 0 fail (+3 新)
**触发源**: 8066f70 后 D6 修 (FK 漂移 reconcile) 时, 发现 `backfill_content_result_id_fk` + `reconcile_fk_from_polymorphic` 的 partial commit 数据不变量破坏。

## 0. TL;DR

| BUG | 文件 | 现象 | 修法 |
|---|---|---|---|
| **D4-V2** | `app/mapper/interfaceApi/interfaceResultMapper.py:backfill_content_result_id_fk` + `reconcile_fk_from_polymorphic` | 用 `cls.session_scope(session) + await session.commit()`, 当 caller 传 session 进来 (bulk 业务流场景) 时, "中途提交" 把 caller 同一事务里的其他 INSERT 一起提前 commit, 破坏 bulk 事务边界, 数据不变量破坏 (FK 已回填但主表空) | 改用 `cls.transaction(session)`, 删显式 `await session.commit()`, 让 caller 控制事务边界 |

## 1. BUG-D4-V2 详情

### 1.1 根因

`backfill_content_result_id_fk` 旧代码 (line 235-243):
```python
try:
    async with cls.session_scope(session) as session:
        result = await session.execute(sql, ...)
        await session.commit()  # <-- 显式 commit
        return result.rowcount or 0
except Exception as e:
    log.error(f"backfill_content_result_id_fk error: {e}")
    raise
```

`reconcile_fk_from_polymorphic` 旧代码 (line 355-362) 同样问题。

`cls.session_scope` (D4 哲学): 只 yield session, 不自动 begin/commit/rollback。函数自己加 `await session.commit()` 解决 "session=None 时怎么 commit" 的问题。

### 1.2 后果 (D4 风格破坏)

调用方 A (业务流 bulk 场景):
```python
async with cls.transaction() as outer_session:  # 自管事务
    await cls.insert_content_result(session=outer_session, ...)  # 写入主表
    await InterfaceResultMapper.reconcile_fk_from_polymorphic(
        case_result_id=42, session=outer_session,
    )
    # ↑ 内部 await session.commit() 把 outer_session 里的 insert 一起 commit 了!
    await cls.insert_log(session=outer_session, ...)  # 这行如果失败, log 没写但 FK 已 commit
```

后果:
- FK 已回填 + 提交 (interface_result.content_result_id 指向 cr.id)
- 但 log 还在 outer_session 内存里没 flush
- 如果 outer_session 后面 raise, 整个事务回滚, FK 也回滚 — 但 log 没回滚 (因为是 logger, 不是 DB)
- 或者 outer_session 退出时正常 commit, 但 log 缺失 (因为 log 是 logger 输出, 不在事务里)

更阴的 case: `interface_log` 列可能引用了 case_result 的 content_result_id, 部分回滚会让 interface_log 指向不存在的 content_result_id。

### 1.3 修法

`backfill_content_result_id_fk` + `reconcile_fk_from_polymorphic` 改成:
```python
try:
    # BUG-D4-V2 修复: 用 cls.transaction(session) 替 session_scope(session) +
    # 显式 commit()。原因: 当 caller 传 session 进来 (bulk 业务流场景),
    # 显式 await session.commit() 会"中途提交", 把 caller 同一事务里的
    # 其他 INSERT 一起提前 commit, 破坏 bulk 事务边界, 数据不变量破坏
    # (FK 已回填但主表空)。改: transaction() 在 session=None 时
    # session.begin() 自动 commit, session 传进来时 caller 控制边界。
    async with cls.transaction(session) as session:
        result = await session.execute(sql, ...)
        return result.rowcount or 0
except Exception as e:
    log.error(f"backfill_content_result_id_fk error: {e}")
    raise
```

### 1.4 行为对比

| 场景 | 修前 | 修后 |
|---|---|---|
| `backfill(session=None)` 单独调 (result_writer.finalize_case_result 路径) | 显式 commit, OK | `transaction()` session.begin() 自动 commit, OK |
| `backfill(session=outer)` 在 bulk 业务流外层事务内调 | **显式 commit, 破坏事务边界 (BUG)** | `transaction()` yield outer_session, 不 commit, caller 控制 |
| `reconcile(session=None)` 单独调 | 显式 commit, OK | 同上, OK |
| `reconcile(session=outer)` 在 bulk 业务流内调 | **BUG** | OK |

### 1.5 为什么不改方案 B (transaction 全部走自管, caller 必须包外层)

业务上 `backfill_content_result_id_fk` 是 D6 加的 reconcile 工具, 跟 `recompute_case_result_nums` (D4 修过) 是同类 — D4 已经定了 "session 传进来复用, session=None 自管" 的契约。本批把 D6 的 2 个函数对齐到 D4 契约, 不破坏 D4 已定的 API。

### 1.6 锁住测试 (`tests/croe/interface/test_bug_d6_fk_invariant.py`)

- 旧 `test_bug_d6_reconcile_returns_rowcount` + `test_bug_d6_reconcile_handles_zero_fixes`: 之前 mock `session_scope` + 验 `mock_session.commit.assert_awaited_once()`, 锁的是 BUG。改 mock `transaction` + 验 `mock_session.commit.assert_not_awaited()`, 锁正确行为。
- 新 `test_bug_d4_v2_backfill_no_explicit_commit`: 用 `inspect.getsource` 锁源码, 验证:
  1. 代码行 (剥注释) 没有 `await session.commit()`
  2. 有 `cls.transaction(session)`
  3. 没有 `cls.session_scope(session)`
- 新 `test_bug_d4_v2_reconcile_no_explicit_commit`: 同上, 锁 `reconcile_fk_from_polymorphic`。
- 新 `test_bug_d4_v2_backfill_session_none_still_works`: end-to-end mock, 验证 session=None 时, `transaction()` 自管路径, 返 rowcount + 不手动 commit。

## 2. 周边影响

| 函数 | session 状态 | 修前 commit? | 修后 commit? |
|---|---|---|---|
| `backfill_content_result_id_fk` | None | ✅ 显式 | ✅ `transaction()` 自动 |
| `backfill_content_result_id_fk` | 传进来 | ⚠️ **破坏 caller 事务** | ✅ caller 控制 |
| `reconcile_fk_from_polymorphic` | None | ✅ 显式 | ✅ `transaction()` 自动 |
| `reconcile_fk_from_polymorphic` | 传进来 | ⚠️ **破坏 caller 事务** | ✅ caller 控制 |

`result_writer.finalize_case_result` 单独调 `backfill_content_result_id_fk(case_result_id=...)` (session=None) — 行为不变, 仍然 commit。

## 3. 测试覆盖

| 文件 | 测试 | 类型 |
|---|---|---|
| `tests/croe/interface/test_bug_d6_fk_invariant.py` | 15 旧 + 2 改写 + 3 新 = 18 (本批) | mock + 静态源码锁 |

D6 原 15 个测试 13 通过, 2 个 (锁了 BUG 行为) 改写后通过 + 3 个新测试 = 18 全过。

**全量回归**: 401 passed, 1 skipped, 3 deselected, 0 fail (398 基线 + 3 新)。

## 4. 不在本批范围 (留给下批)

5 个 P1:
- 魔法数字 200
- init_global_headers cache
- 错属性名
- 错误日志 redaction
- kwargs["id"] code smell

## 5. 关键约定 (沿用)

- 测试不加 DB, 用 `inspect.getsource()` + 正则 + mock 锁产品代码
- BUG_ID 必加 `_bug_ids.py`, commit msg + 测试 + 报告三处引用
- 修复注释格式: `# BUG-{ID} 修复: 一句话根因 + 一句话修法 + 为什么不修方案 B`
- 锁源码时去掉注释行, 避免误命中修复注释里描述"修了什么"的关键字
- mock `transaction` 而不是 `session_scope`, 锁正确行为 (caller 控制 commit 边界)
