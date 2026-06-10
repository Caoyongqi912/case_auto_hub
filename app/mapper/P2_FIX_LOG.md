# P2 级别修复记录

> **修复日期**: 2026-06-10
> **修复范围**: 代码审查报告中标记为 P2 的问题

---

## 修复概览

| # | 文件 | 问题 | 修复方式 |
|---|------|------|---------|
| 1 | `interfaceCaseContentMapper.py` | 多余的 `get_by_id` 重写（与基类功能完全相同） | 删除重写，直接使用基类 |
| 2 | `interfaceResultMapper.py` | 多余的 `get_by_id` 重写，且把 `NotFind` 改成 `ValueError` | 删除重写，恢复基类行为 |
| 3 | `testcaseMapper.py` | `delete_batch_cases` docstring 声称手动删关联，实际靠数据库级联 | 修正 docstring，说明数据库 ON DELETE CASCADE |
| 4 | `testcaseMapper.py` | `_build_new_cases` 显式设置 `test_case_id=None`（flush 前 id 为 None） | 移除显式设置，由 SQLAlchemy relationship 自动填充 |

---

## 详细说明

### 1-2. 删除多余的 `get_by_id` 重写

**问题**: `InterfaceCaseContentMapper` 和 `InterfaceContentStepResultMapper` 各自重写了 `get_by_id`，但逻辑与基类 `Mapper.get_by_id` 完全相同：`session.get(model, ident)` + 不存在时抛异常。

- `InterfaceCaseContentMapper` 的版本：异常类型正确（`NotFind`），但 30+ 行 docstring 完全多余
- `InterfaceContentStepResultMapper` 的版本：异常类型错误（`ValueError` 而非 `NotFind`），破坏调用方一致性

**修复**: 直接删除两个重写，使用基类方法。

```python
# 删除前（interfaceResultMapper.py）
@classmethod
async def get_by_id(cls, ident: int, session: AsyncSession = None):
    ...
    if not result:
        raise ValueError(f"步骤内容结果不存在，id: {ident}")  # ← 错误类型
    ...

# 删除后：直接使用基类 Mapper.get_by_id
# 基类行为：session.get(cls.__model__, ident) + raise NotFind
```

---

### 3. `delete_batch_cases` docstring 修正

**问题**: docstring 声称会"单次 DELETE 删除关联表记录"，但代码中只执行了 `delete(TestCase)`，没有手动 DELETE 子表。

**确认**: 数据库已配置 `ON DELETE CASCADE`：
- `case_sub_step.test_case_id` → `ondelete="cascade"`
- `case_step_dynamic.test_case_id` → `ondelete="cascade"`
- `requirement_case_association.case_id` → `ondelete="CASCADE"`
- `plan_case_association.case_id` → `ondelete="CASCADE"`

因此数据库会自动级联删除，代码无需手动处理。

**修复**: 修正 docstring，明确说明依赖数据库级联。

---

### 4. `_build_new_cases` 移除显式 `test_case_id`

**问题**: 代码中显式设置 `test_case_id=new_case_model.id`，但此时 `new_case_model` 尚未 flush，`id` 为 None。

**分析**: `TestCaseStep.test_case_id` 是 `nullable=False`，但 SQLAlchemy 的 relationship (`case_sub_steps` / `case` back_populates) 会在 flush 前自动填充外键。显式设为 None 虽然会被 SQLAlchemy 覆盖，但会造成困惑。

**修复**: 移除显式 `test_case_id` 设置，让 SQLAlchemy 通过 relationship 自动处理。

```python
# 之前
new_case_model.case_sub_steps = [
    TestCaseStep(
        **{
            **step.copy_map(),
            "test_case_id": new_case_model.id,  # ← None
            ...
        }
    )
]

# 之后
new_case_model.case_sub_steps = [
    TestCaseStep(
        **{
            **step.copy_map(),
            # test_case_id 由 SQLAlchemy 在 flush 时自动填充
            ...
        }
    )
]
```

---

## 验证结果

```bash
python3 -m py_compile interfaceCaseContentMapper.py interfaceResultMapper.py testcaseMapper.py
# 输出: SYNTAX_OK
```
