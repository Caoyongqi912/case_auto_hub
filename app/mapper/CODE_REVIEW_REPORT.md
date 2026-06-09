# Mapper 基类及子类代码审查报告

> **审查范围**: `app/mapper/__init__.py`（Mapper 基类）及所有子类 Mapper
> **审查日期**: 2026-06-09
> **审查方式**: 9 角度独立扫描 + 交叉验证（max effort）
> **最近提交**: `e04cc02` fix(mapper): 修复 session_scope 写入操作缺少显式事务的问题

---

## 一、审查概览

| 类别 | 数量 | 说明 |
|------|------|------|
| **Critical（严重）** | 1 | 事务边界被破坏，导致数据不一致 |
| **High（高）** | 7 | 事务不一致、接口不兼容、输入校验缺失 |
| **Medium（中）** | 6 | 代码重复、设计缺陷、行为不一致 |
| **Low（低）** | 1 | 冗余代码，可统一为基类方法 |

---

## 二、严重问题（Critical）

### 1. `delete_by_id` 外部 session 时仍调用 `session.commit()`，破坏调用方事务边界

- **文件**: `app/mapper/__init__.py`
- **行号**: 265-267
- **代码**:
  ```python
  if session:
      await session.execute(stmt)
      await session.commit()   # ← 问题在这里
  ```
- **问题分析**:
  当调用方传入外部 session（例如在 `cls.transaction()` 上下文内），`delete_by_id` 会在执行后**立即 commit**，导致调用方事务被提前结束。如果调用方后续还有其他操作（如插入日志、更新关联表），这些操作将无法回滚，破坏原子性。
- **触发场景**:
  ```python
  async with cls.transaction() as session:
      await SomeMapper.save(session=session, ...)     # 操作A
      await cls.delete_by_id(1, session=session)       # 这里提前commit！
      await OtherMapper.save(session=session, ...)     # 操作B — 如果失败，A无法回滚
  ```
- **修复建议**:
  外部传入的 session 不应 commit，仅由 session 的创建者控制事务边界：
  ```python
  if session:
      await session.execute(stmt)
      await session.flush()   # 仅 flush，不 commit
  ```

---

## 三、高风险问题（High）

### 2. `delete_by_uid` 使用手动 `session.commit()` 而非事务块

- **文件**: `app/mapper/__init__.py`
- **行号**: 248-250
- **代码**:
  ```python
  async with async_session() as session:
      await session.execute(delete(model).where(model.uid == uid))
      await session.commit()
  ```
- **问题分析**:
  与 `delete_by`（已修复为 `session.begin()`）不一致，`delete_by_uid` 仍使用手动 commit。异常时无法自动回滚。
- **修复建议**:
  ```python
  async with async_session() as session:
      async with session.begin():
          await session.execute(delete(model).where(model.uid == uid))
  ```

### 3. `bulk_update` 无 session 分支使用手动 commit

- **文件**: `app/mapper/__init__.py`
- **行号**: 781-789
- **问题分析**:
  `bulk_update` 在无 session 时使用 `async_session() + manual commit`，与 `bulk_insert`（使用 `cls.transaction()`）不一致。批量更新中途中断会导致部分更新已提交。
- **修复建议**:
  统一使用 `cls.transaction()`。

### 4. `bulk_delete` 无 session 分支使用手动 commit

- **文件**: `app/mapper/__init__.py`
- **行号**: 814-816
- **问题分析**:
  与 `bulk_update` 相同的问题，无 session 时手动 commit，无事务保护。
- **修复建议**:
  统一使用 `cls.transaction()`。

### 5. `search_conditions` 对字段名无校验，非法输入导致 500

- **文件**: `app/mapper/__init__.py`
- **行号**: 522, 549
- **代码**:
  ```python
  field = getattr(model, field_name)   # 无校验
  ```
- **问题分析**:
  `kwargs` 来自客户端输入，`field_name` 可能是任意字符串。`getattr` 对不存在的属性抛出 `AttributeError`，直接 500 暴露内部细节。
- **触发场景**:
  ```python
  kwargs = {"hacked_field__gt": 5}
  # getattr(model, "hacked_field") → AttributeError
  ```
- **修复建议**:
  ```python
  if not hasattr(model, field_name):
      raise CommonError(f"Invalid field name: {field_name}")
  field = getattr(model, field_name)
  ```

### 6. `sorted_search` 对排序字段无校验

- **文件**: `app/mapper/__init__.py`
- **行号**: 486
- **代码**:
  ```python
  field = getattr(model, k)   # 无校验
  ```
- **问题分析**:
  `sortInfo` 来自客户端 JSON，排序字段名可被篡改。非法字段导致 `AttributeError`。
- **修复建议**:
  同 `search_conditions`，添加 `hasattr` 校验。

### 7. `InterfaceCaseContentMapper.get_by_id` 重写签名与基类不兼容

- **文件**: `app/mapper/interfaceApi/interfaceCaseContentMapper.py`
- **行号**: 55
- **基类签名**:
  ```python
  async def get_by_id(cls, ident: int, session: AsyncSession = None, desc: str = '') -> M:
  ```
- **子类签名**:
  ```python
  async def get_by_id(cls, ident: int, session: AsyncSession, with_relations: bool = False) -> InterfaceCaseContents:
  ```
- **问题分析**:
  - 子类 `session` 变为**必填**（基类是可选）
  - 缺少 `desc` 参数
  - 新增 `with_relations` 参数
  - 按基类方式调用（如 `mapper.get_by_id(1, desc="步骤")`）会抛 `TypeError`
- **修复建议**:
  保持基类签名兼容，新增参数使用默认值：
  ```python
  async def get_by_id(cls, ident: int, session: AsyncSession = None, desc: str = '', with_relations: bool = False):
  ```

### 8. `InterfaceVarsMapper.query_by` 完全重写基类方法，签名不兼容

- **文件**: `app/mapper/interfaceApi/interfaceVarsMapper.py`
- **行号**: 81
- **基类签名**:
  ```python
  async def query_by(cls, session: AsyncSession = None, **kwargs) -> List[M]:
  ```
- **子类签名**:
  ```python
  async def query_by(cls, case_id: Optional[int] = None, key: Optional[str] = None, uid: Optional[str] = None) -> List[InterfaceCaseVars]:
  ```
- **问题分析**:
  - 子类完全丢弃了 `session` 参数（内部硬编码 `async_session()`）
  - 将通用 `**kwargs` 查询替换为固定的三个参数
  - 调用方按基类方式传入 `session` 或其他字段时被忽略
  - 手动构建 SQL 条件，未复用基类 `search_conditions`
- **修复建议**:
  重命名为 `query_vars` 等专用方法，保留基类 `query_by` 不被覆盖；或正确重写并保持签名兼容。

---

## 四、中风险问题（Medium）

### 9. `update_by_id` 有无 session 时行为不一致

- **文件**: `app/mapper/__init__.py`
- **行号**: 208-215
- **代码**:
  ```python
  if session is None:
      async with cls.transaction() as session:
          target = await cls.get_by_id(ident, session)
          return await cls.update_cls(target, session, **kwargs)
  else:
      target = await cls.get_by_id(ident, session)
      await cls.update_cls(target, session, **kwargs)
      return target
  ```
- **问题分析**:
  - `session=None`：使用 `cls.transaction()`，**自动 commit**
  - `session=xxx`：仅 `flush`，**不 commit**
  调用方从"不传 session"切换到"传 session 控制事务"时，同一方法的行为突变，极易造成"以为已保存实际未 commit"的 bug。
- **修复建议**:
  外部 session 分支也应明确文档化（"调用方负责 commit"），或在方法签名中增加 `auto_commit: bool` 参数显式控制。

### 10. `delete_by` 的修复是局部补丁，`session_scope` 本身仍无写保护

- **文件**: `app/mapper/__init__.py`
- **行号**: 55, 285
- **代码**:
  ```python
  async with cls.session_scope(session) as session:
      async with session.begin():
          await session.execute(...)
  ```
- **问题分析**:
  最近提交 `e04cc02` 在 `delete_by` 中增加了 `session.begin()`，但 `session_scope` 本身仍然只是 `yield session`（读操作安全）。其他写方法（如 `_manage_session` 已正确处理）如果新开发者直接使用 `session_scope` 做写入，仍可能忘记加 `session.begin()`。
- **修复建议**:
  考虑将 `session_scope` 拆分为 `read_scope` 和 `write_scope`，或在文档中明确标注 `session_scope` 不自动开启事务。

### 11. `update_model` 与基类 `update_cls` 逻辑重复，未抽象 JTI 通用能力

- **文件**: `app/mapper/interfaceApi/interfaceCaseContentMapper.py`
- **行号**: 227
- **代码**:
  ```python
  base_columns = set(InterfaceCaseContents.__table__.columns.keys())
  child_columns = set(target.__class__.__table__.columns.keys())
  valid_columns = base_columns | child_columns
  ```
- **问题分析**:
  基类 `update_cls` 已有列校验逻辑（`model.__table__.columns.keys()`），但 JTI 场景需要合并基类和子类列。`update_model` 重复了 `update_cls` 的大部分代码，只多了 `| child_columns` 一行。
- **修复建议**:
  在基类 `update_cls` 中增加 JTI 支持（检测 `target.__class__.__table__` 是否不同于 `model.__table__`），或提取 JTI 列合并为通用工具方法。

### 12. `InterfaceContentStepResultMapper._do_update` 重复 JTI 列合并逻辑

- **文件**: `app/mapper/interfaceApi/interfaceResultMapper.py`
- **行号**: 384-398
- **问题分析**:
  与 `interfaceCaseContentMapper.update_model` 完全相同的 JTI 列合并逻辑再次实现，确认缺少抽象。
- **修复建议**:
  同上，统一抽象。

### 13. 两个 JTI Mapper 独立实现相同模式，无共享抽象

- **文件**:
  - `app/mapper/interfaceApi/interfaceCaseContentMapper.py`（行 42）
  - `app/mapper/interfaceApi/interfaceResultMapper.py`（行 144）
- **问题分析**:
  两者都实现了：
  - `CONTENT_TYPE_MAP` / `RESULT_TYPE_MAP`（类型映射）
  - `insert_content` / `insert_result`（多态插入）
  - `get_by_id`（多态查询）
  - `update_model` / `_do_update`（JTI 列合并更新）
  - `copy_content` / `update_result`（业务操作）

  新增步骤类型时，必须同时修改两个 Mapper 的类型映射表，遗漏会导致运行时失败。
- **修复建议**:
  提取 `JTIBaseMapper` 抽象基类，封装类型映射、多态查询/插入/更新等通用逻辑。

### 14. `copy_one` 直接调用 `old_one.copy_map()` 未检查方法存在性

- **文件**: `app/mapper/__init__.py`
- **行号**: 147
- **代码**:
  ```python
  new_one = cls.__model__(**old_one.copy_map())
  ```
- **问题分析**:
  如果传入的 `target` 是 `BaseModel` 实例但未实现 `copy_map()`（或 `BaseModel` 本身没有该方法），将抛出 `AttributeError`。
- **修复建议**:
  ```python
  if not hasattr(old_one, 'copy_map'):
      raise CommonError(f"{type(old_one).__name__} 不支持复制操作")
  ```

---

## 五、低风险问题（Low）

### 15. 三个 Result Mapper 定义几乎相同的 `set_result`/`set_result_field` 方法

- **文件**: `app/mapper/interfaceApi/interfaceResultMapper.py`
- **行号**: 66, 80, 123
- **代码重复**:
  ```python
  # InterfaceCaseResultMapper.set_result_field
  async with cls.transaction() as session:
      await cls.add_flush_expunge(session, caseResult)

  # InterfaceResultMapper.set_result
  async with cls.transaction() as session:
      await cls.add_flush_expunge(session, result)

  # InterfaceTaskResultMapper.set_result_field
  async with cls.transaction() as session:
      await cls.add_flush_expunge(session, caseResult)
  ```
- **问题分析**:
  三个方法逻辑完全一致，只是参数名不同。应在基类统一为 `save_or_flush(model)` 方法。
- **修复建议**:
  在 `Mapper` 基类增加：
  ```python
  @classmethod
  async def save_flush(cls, model: M) -> M:
      async with cls.transaction() as session:
          return await cls.add_flush_expunge(session, model)
  ```

---

## 六、子类方法重写统计

通过 AST 静态分析，以下子类重写了基类 `Mapper` 的方法：

| 子类 | 重写方法 | 问题 |
|------|---------|------|
| `InterfaceCaseContentMapper` | `get_by_id` | 签名不兼容（缺少 `desc`, `raise_error`） |
| `InterfaceVarsMapper` | `query_by` | 签名完全改变，破坏里氏替换 |
| `InterfaceContentStepResultMapper` | `get_by_id` | 签名不兼容（缺少 `desc`） |
| `PlayCaseVariablesMapper` | `insert`, `update_by_id` | 正常重写（有 `super()` 调用） |

另有大量子类**未重写但直接调用**基类方法，主要问题集中在：
- 子类中混用 `async_session()`、`cls.transaction()`、`cls.session_scope()` 三种模式
- 部分子类（如 `PlayMethodMapper`、`PlayLocatorMapper`、`ProjectMapper`）仍使用手动 `session.commit()`

---

## 七、修复优先级建议

| 优先级 | 问题编号 | 预计工作量 |
|--------|---------|-----------|
| P0 | 1 (delete_by_id 破坏事务) | 5 分钟 |
| P0 | 5, 6 (search_conditions/sorted_search 无校验) | 10 分钟 |
| P1 | 2, 3, 4 (手动 commit 改事务块) | 15 分钟 |
| P1 | 7, 8 (子类签名兼容) | 30 分钟 |
| P2 | 11, 12, 13 (JTI 逻辑抽象) | 2-4 小时 |
| P2 | 9 (update_by_id 行为统一) | 30 分钟 |
| P3 | 15 (冗余方法统一) | 20 分钟 |

---

## 八、附录：JSON 格式原始数据

```json
[
  {"severity": "critical", "file": "app/mapper/__init__.py", "line": 265, "summary": "delete_by_id 在外部传入 session 时仍调用 session.commit()，破坏调用方事务边界", "failure_scenario": "调用方在 transaction() 内执行 delete_by_id(ident=1, session=shared_session) → 外部 session 被提前 commit，导致调用方事务中原子性被破坏"},
  {"severity": "high", "file": "app/mapper/__init__.py", "line": 250, "summary": "delete_by_uid 使用手动 session.commit() 而非 session.begin() 事务块", "failure_scenario": "调用 delete_by_uid(uid='xxx') → 发生异常时无法自动回滚，与 delete_by 的事务行为不一致"},
  {"severity": "high", "file": "app/mapper/__init__.py", "line": 789, "summary": "bulk_update 无 session 分支使用手动 session.commit() 而非 cls.transaction()", "failure_scenario": "调用 bulk_update(updates=[...]) → 手动 commit 无事务保护，异常时部分更新已提交无法回滚"},
  {"severity": "high", "file": "app/mapper/__init__.py", "line": 816, "summary": "bulk_delete 无 session 分支使用手动 session.commit() 而非 cls.transaction()", "failure_scenario": "调用 bulk_delete(ids=[1,2,3]) → 手动 commit 无事务保护，异常时部分删除已提交无法回滚"},
  {"severity": "high", "file": "app/mapper/__init__.py", "line": 522, "summary": "search_conditions 对字段名直接使用 getattr 无校验，非法字段名导致 AttributeError 暴露到客户端", "failure_scenario": "kwargs={'hacked_field__gt': 5} → getattr(model, 'hacked_field') 抛出 AttributeError，500 错误暴露内部实现细节"},
  {"severity": "high", "file": "app/mapper/__init__.py", "line": 486, "summary": "sorted_search 对排序字段直接使用 getattr 无校验，非法排序字段导致 AttributeError", "failure_scenario": "sortInfo='{\"hacked_field\": \"descend\"}' → getattr(model, 'hacked_field') 抛出 AttributeError，请求直接 500"},
  {"severity": "high", "file": "app/mapper/interfaceApi/interfaceCaseContentMapper.py", "line": 55, "summary": "InterfaceCaseContentMapper.get_by_id 重写后签名与基类不兼容，缺少 desc/raise_error 参数", "failure_scenario": "多态调用 mapper.get_by_id(ident=1, desc='步骤', raise_error=False) 时 → 子类抛出 TypeError: unexpected keyword argument"},
  {"severity": "high", "file": "app/mapper/interfaceApi/interfaceVarsMapper.py", "line": 81, "summary": "InterfaceVarsMapper.query_by 完全重写基类方法，签名从 (session, **kwargs) 变为 (case_id, key, uid)", "failure_scenario": "调用方按基类签名调用 query_by(session=s, project_id=1) → 子类将 project_id 忽略，返回错误结果集"},
  {"severity": "medium", "file": "app/mapper/__init__.py", "line": 208, "summary": "update_by_id 有无 session 时行为不一致：无 session 时自动 commit，有 session 时仅 flush", "failure_scenario": "调用方从 session=None 切换到传入 session 控制事务 → 同一方法突然不再提交，调用方以为数据已持久化但实际未 commit"},
  {"severity": "medium", "file": "app/mapper/__init__.py", "line": 285, "summary": "delete_by 的修复仅在局部加 session.begin()，session_scope 本身仍对写操作无自动事务保护", "failure_scenario": "新开发者使用 session_scope 写数据但未加 session.begin() → 本地测试通过但生产环境因事务隔离级别不同导致数据未实际持久化"},
  {"severity": "medium", "file": "app/mapper/interfaceApi/interfaceCaseContentMapper.py", "line": 227, "summary": "update_model 与基类 update_cls 几乎相同，仅多了 JTI 子表列合并逻辑，未抽象为通用 JTI 更新能力", "failure_scenario": "新增 JTI Mapper 时必须重复实现 base_columns | child_columns 逻辑"},
  {"severity": "medium", "file": "app/mapper/interfaceApi/interfaceResultMapper.py", "line": 384, "summary": "InterfaceContentStepResultMapper._do_update 重复实现 JTI 列合并逻辑", "failure_scenario": "基类表新增字段时需同时修改 _do_update 和 update_model 两处，维护成本高且容易遗漏"},
  {"severity": "medium", "file": "app/mapper/interfaceApi/interfaceCaseContentMapper.py", "line": 42, "summary": "InterfaceCaseContentMapper 与 InterfaceContentStepResultMapper 独立实现相同的 JTI 模式，无共享抽象", "failure_scenario": "新增步骤类型时需在 CONTENT_TYPE_MAP 和 RESULT_TYPE_MAP 分别注册，遗漏任一方会导致运行时 insert_result 失败"},
  {"severity": "medium", "file": "app/mapper/__init__.py", "line": 147, "summary": "copy_one 直接调用 old_one.copy_map() 未检查方法是否存在", "failure_scenario": "传入未实现 copy_map() 的模型 → AttributeError，复制操作崩溃"},
  {"severity": "low", "file": "app/mapper/interfaceApi/interfaceResultMapper.py", "line": 66, "summary": "三个 Result Mapper 定义几乎相同的 set_result/set_result_field 方法，可统一为基类方法", "failure_scenario": "修改事务行为需分别修改 InterfaceCaseResultMapper/InterfaceResultMapper/InterfaceTaskResultMapper 三处"}
]
```

---

*报告生成完毕。共识别 15 项问题，其中 1 项严重、7 项高风险、6 项中风险、1 项低风险。*
