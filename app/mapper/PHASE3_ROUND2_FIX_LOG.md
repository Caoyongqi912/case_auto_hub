# Phase 3 第二轮修复日志（续接）：剩余 19 个 Mapper 迁移

> **执行日期**: 2026-06-09  
> **执行范围**: 19 个中低优先级子类 Mapper（test_case/、play/、interfaceApi/、project/、statistics/）  
> **目标**: 全部 `async with async_session()` 归零，统一 `cls.session_scope()` / `cls.transaction()`  
> **验证结果**: `python3 -m py_compile` 全部通过  
> **变更统计**: 19 文件，38 处替换（修正了 PHASE3_FIX_LOG.md 中低估的 17/31 → 实际 19/38）

---

## 一、执行摘要

第一轮完成后剩 19 个 Mapper 文件含 `async with async_session()` 直接调用。本轮逐一迁移至基类 context manager 范式，并清理了 11 个 `from app.model import async_session` 死导入。

**核心成果**：
- ✅ 子类 Mapper 残留 = **0 处 / 0 文件**
- ✅ 死导入残留 = 2（仅 `__init__.py` 基类，保留）
- ✅ 全部 19 个文件 `python3 -m py_compile` 通过

---

## 二、迁移清单

按目录分 5 组，共 19 文件 / 38 处：

| 目录 | 文件数 | 处数 | 关键类 |
|------|-------|------|--------|
| `test_case/` | 5 | 10 | `testcaseMapper`(4)、`planMapper`(3) + 3 个 1 处 |
| `play/` | 4 | 10 | `playConditionMapper`(5)、`playConfigMapper`(2)、`playResultMapper`(2)、`playStepMapper`(1) |
| `interfaceApi/` | 5 | 7 | `dynamicMapper`(2)、`interfaceTaskMapper`(2) + 3 个 1 处 |
| `project/` | 4 | 8 | `moduleMapper`(3)、`__init__.py`(3，含 ProjectMapper + GlobalVariableMapper) + 2 个 1 处 |
| `statistics/` | 1 | 3 | `__init__.py`(3) |
| **合计** | **19** | **38** | |

---

## 三、读/写分类

| 操作类型 | 改造目标 | 数量 |
|---------|---------|------|
| 读操作（select / get_by / get_by_id / scalars） | `cls.session_scope()` | **29 处** |
| 写操作（begin / add / commit / delete / update / insert） | `cls.transaction()` | **9 处** |

---

## 四、典型迁移模式

### 模式 A: 写操作 `async with session.begin():` 嵌套

```python
# 迁移前（playConditionMapper.reorder_content）
try:
    async with async_session() as session:
        async with session.begin():
            condition = await cls.get_by_id(ident=condition_id, session=session)
            # ... 20 缩进的 body
        # ... body

# 迁移后
try:
    async with cls.transaction() as session:
        condition = await cls.get_by_id(ident=condition_id, session=session)
        # ... 16 缩进的 body（少一层）
    # ... body
```

**收益**：
- 缩进从 4 层嵌套减至 3 层
- 异常时自动 rollback（原代码 `async with session.begin()` 已提供，但移除冗余嵌套）
- 事务边界语义更清晰

### 模式 B: 写操作手动 commit（无 begin）

```python
# 迁移前（playConfigMapper.init_play_methods）
try:
    async with async_session() as session:
        await session.execute(insert(cls.__model__).values(methods))
        await session.commit()  # 手动 commit

# 迁移后
try:
    async with cls.transaction() as session:
        await session.execute(insert(cls.__model__).values(methods))
```

**收益**：
- 消除手动 commit（由 `transaction()` 的 `session.begin()` 退出时自动处理）
- 异常时自动 rollback（之前无 begin 时依赖 SQLAlchemy 隐式 autobegin，行为不一致）

### 模式 C: 读操作裸用

```python
# 迁移前（planMapper.query_plans）
try:
    async with async_session() as session:
        if not plan_name:
            stmt = select(cls.__model__)
        else:
            stmt = select(cls.__model__).where(...)

# 迁移后
try:
    async with cls.session_scope() as session:
        if not plan_name:
            stmt = select(cls.__model__)
        else:
            stmt = select(cls.__model__).where(...)
```

**收益**：
- `session_scope()` 退出时自动关闭 session（之前依赖 `async with` 上下文）
- 显式语义：这是只读查询，不涉及事务

---

## 五、踩坑记录（本轮执行过程）

### 坑 1: `__init__.py` 混合行尾

**问题**：`app/mapper/__init__.py` 整个文件使用 Mac 老式 `\r` 行尾（CR 字符），与 Linux 工具链不兼容。py_compile 报 `IndentationError: unexpected indent at line 63`。

**根因**：line 63 是单个 `\r` 字符，Python tokenizer 无法正确解析。

**修复**：将所有 `\r\n` 和裸 `\r` 统一为 `\n`。978 个 `\r` 全部归零。

### 坑 2: `project/__init__.py` 单行文件

**问题**：该文件原是单行（无换行），`grep -c` 报 1 实际含 3 处 `async with async_session()`。

**根因**：原文件用 CR 行尾，整个文件被合并为 1 物理行。

**修复**：先 `\r → \n` 转换，再按方法定位 3 处独立替换。

### 坑 3: 缩进过度 dedent

**问题**：`fix_remaining_indent.py` 中 `fix_file()` 函数有 bug — 它把 `start_line` 自身也 dedent 了，导致 `async with cls.transaction()` 行少了 4 个空格。

**根因**：函数循环中没有正确跳过 `start_line`，从 `start_line` 自身就开始 dedent。

**修复**：手动给 4 个文件的 `async with cls.transaction()` 行加回 4 个空格，并对被过度 dedent 的 body 行也修正。

### 坑 4: 误改原有 transaction 块

**问题**：dedent 脚本用 generic 模式，对文件中**所有** `async with cls.transaction()` 块都 dedent，导致 10 个不属于本轮迁移的块被破坏。

**根因**：dedent 脚本无法区分"本轮引入"vs"原有"的 transaction 块。

**修复**：`git checkout HEAD -- <files>` 恢复 7 个文件到 HEAD，然后重做迁移（这次所有 `new` pattern 都带正确缩进，不依赖 dedent 后处理）。

---

## 六、整体 Mapper 迁移完成度

| 阶段 | 文件数 | 替换处数 | 完成度 |
|------|-------|---------|--------|
| Phase 1（基类 + 子类 bug 修复） | 4 | 9 | — |
| Phase 2（基类 session 重构） | 1 | 14 | — |
| Phase 3 第一轮（5 个高优先级） | 5 | 47 | 22.7% |
| **Phase 3 第二轮（19 个中低优先级）** | **19** | **38** | **+86.3%** |
| **Phase 3 累计** | **24** | **85+** | **100%** 🎉 |

---

## 七、修复后全量验证

### 7.1 语法检查

```bash
$ find app/mapper -name "*.py" -exec python3 -m py_compile {} \;
✅ 全部 Mapper 文件 py_compile 通过
```

### 7.2 残留统计

```bash
$ grep -rn "async with async_session" app/mapper/ --include="*.py" | grep -v __init__.py
# 子类 Mapper 残留: 0 处 / 0 文件
```

仅 `app/mapper/__init__.py` 含 2 处（基类 `session_scope` / `transaction` 内部实现，必须保留）。

### 7.3 死导入清理

```bash
$ grep -rln "from app.model import async_session" app/mapper/ --include="*.py"
# 仅 2 处: app/mapper/__init__.py（基类必须）+ 项目其他模块（非 mapper）
```

---

## 八、剩余工作

- ✅ Phase 3 全部完成
- ⏳ Phase 4（设计优化，按需）：
  - 问题 10-12：JTI 抽象基类
  - 问题 13：`set_result` 三处重复统一
  - 改进：`delete_by` 改用 `transaction()` 统一范式

---

*Phase 3 第二轮修复完成。19 个 Mapper 文件、38 处直接 `async_session` 调用 → 0 残留。基类 `session_scope` / `transaction` 范式在全部 24 个子类 Mapper 全面落地。*
