# Play Method 返回值规范

## 📋 返回值设计

所有 `play_method` 目录下的方法统一返回：`tuple[bool, Optional[InfoDict]]`

- **第一个值（bool）**：表示执行成功或失败
- **第二个值（Optional[InfoDict]）**：包含详细信息
  - 成功且无需额外信息：返回 `None`
  - 断言方法：返回断言详情（成功或失败都返回）
  - 失败：返回错误信息

---

## 🎯 三种返回场景

### 1. 普通操作成功（无额外信息）

```python
async def execute(self, locator: Locator, context: StepContext) -> tuple[bool, Optional[InfoDict]]:
    try:
        await locator.click()
        await context.log(f"点击元素 ✅")
        return True, None  # ✅ 成功，无需额外信息
    except Exception as e:
        # ... 错误处理
```

### 2. 断言方法（总是返回详情）

```python
async def execute(self, locator: Locator, context: StepContext) -> tuple[bool, InfoDict]:
    # 注意：断言方法第二个参数不是 Optional，总是返回 InfoDict
    assert_info = create_assert_info(
        assert_name=context.step.name,
        assert_opt="=",
        assert_expect=True,
        assert_actual=None,
        assert_result=False,
        id=GenerateTools.getTime(3),
        desc=context.step.description,
        type="UI",
        assert_script=context.step.method,
    )

    try:
        expect(locator).to_be_checked()
        assert_info["assert_actual"] = True
        assert_info["assert_result"] = True
        return True, assert_info  # ✅ 断言成功，返回详情
    except Exception as e:
        log.error(f"[AssertIsCheckedMethod] execute error: {e}")
        assert_info["assert_actual"] = False
        return False, assert_info  # ❌ 断言失败，返回详情
```

### 3. 操作失败（返回错误信息）

```python
async def execute(self, locator: Locator, context: StepContext) -> tuple[bool, Optional[InfoDict]]:
    try:
        await locator.click()
        return True, None
    except PlaywrightTimeoutError as e:
        log.error(f"[ClickMethod] 元素定位超时: {e}")
        return False, create_error_info(
            error_type="timeout",
            message=str(e),
            selector=context.selector
        )  # ❌ 失败，返回错误详情
    except Exception as e:
        log.error(f"[ClickMethod] click error: {e}")
        return False, create_error_info(
            error_type="interaction_failed",
            message=str(e),
            selector=context.selector
        )  # ❌ 失败，返回错误详情
```

---

## 🛠️ 工具函数使用

### create_error_info - 创建错误信息

```python
from .result_types import create_error_info

# 基本用法
error_info = create_error_info(
    error_type="timeout",           # 错误类型
    message="Element not found",    # 错误消息
    selector="#button"              # 选择器（可选）
)

# 返回结构：
{
    "error_type": "timeout",
    "message": "Element not found",
    "selector": "#button"
}

# 支持的错误类型：
# - "timeout": 超时
# - "element_not_found": 元素未找到
# - "assertion_failed": 断言失败
# - "interaction_failed": 交互失败
# - "unknown": 未知错误
```

### create_assert_info - 创建断言信息

```python
from .result_types import create_assert_info

assert_info = create_assert_info(
    assert_name="检查按钮是否可用",
    assert_opt="=",
    assert_expect=True,
    assert_actual=True,
    assert_result=True,
    # 可选的额外字段
    id=GenerateTools.getTime(3),
    desc="验证提交按钮状态",
    type="UI",
    assert_script="expect.to_be_enabled"
)

# 返回结构：
{
    "assert_name": "检查按钮是否可用",
    "assert_opt": "=",
    "assert_expect": True,
    "assert_actual": True,
    "assert_result": True,
    "id": "...",
    "desc": "验证提交按钮状态",
    "type": "UI",
    "assert_script": "expect.to_be_enabled"
}
```

---

## 📝 完整示例

### 动作方法示例

```python
from playwright.async_api import Locator, TimeoutError as PlaywrightTimeoutError
from .result_types import InfoDict, create_error_info

class ClickMethod(BaseMethods):
    """点击元素"""
    method_name = "click"

    async def execute(self, locator: Locator, context: StepContext) -> tuple[bool, Optional[InfoDict]]:
        try:
            await locator.click()
            await context.log(f"点击元素 ✅ : {context.selector}")
            return True, None

        except PlaywrightTimeoutError as e:
            log.error(f"[ClickMethod] 元素定位超时: {e}")
            return False, create_error_info("timeout", str(e), context.selector)

        except Exception as e:
            log.error(f"[ClickMethod] click error: {e}")
            return False, create_error_info("interaction_failed", str(e), context.selector)
```

### 断言方法示例

```python
from playwright.async_api import Locator, expect
from .result_types import InfoDict, create_assert_info

class AssertIsCheckedMethod(BaseMethods):
    """断言元素被勾选"""
    method_name = "expect.to_be_checked"

    async def execute(self, locator: Locator, context: StepContext) -> tuple[bool, InfoDict]:
        # 注意：断言方法返回类型是 tuple[bool, InfoDict]，不是 Optional[InfoDict]
        assert_info = create_assert_info(
            assert_name=context.step.name,
            assert_opt="=",
            assert_expect=True,
            assert_actual=None,
            assert_result=False,
            id=GenerateTools.getTime(3),
            desc=context.step.description,
            type="UI",
            assert_script=context.step.method,
        )

        try:
            expect(locator).to_be_checked()
            assert_info["assert_actual"] = True
            assert_info["assert_result"] = True
            return True, assert_info

        except Exception as e:
            log.error(f"[AssertIsCheckedMethod] execute error: {e}")
            assert_info["assert_actual"] = False
            return False, assert_info
```

### 数据提取方法示例

```python
class GetInnerTextMethod(BaseMethods):
    """获取元素内部文本"""
    method_name = "get_inner_text"

    async def execute(self, locator: Locator, context: StepContext) -> tuple[bool, Optional[InfoDict]]:
        try:
            key = context.key
            value = await locator.inner_text()
            await context.variable_manager.add_var(key, value)
            await context.log(f"提取文本 ✅ : {key} = {value}")
            return True, None  # 成功，无需额外信息

        except PlaywrightTimeoutError as e:
            log.error(f"[GetInnerTextMethod] 元素定位超时: {e}")
            return False, create_error_info("timeout", str(e), context.selector)

        except Exception as e:
            log.error(f"[GetInnerTextMethod] get inner text error: {e}")
            return False, create_error_info("unknown", str(e), context.selector)
```

---

## 🔍 执行器如何使用返回值

```python
# play_executor.py
SUCCESS, INFO = await method_chain.handle(locator=locator, context=step_context)

if SUCCESS:
    if INFO:
        # 断言成功，记录断言详情
        await Writer.write_assert_info(case_result, INFO)
    else:
        # 普通操作成功，无需额外处理
        pass
else:
    if INFO and "assert_info" in INFO:
        # 断言失败，记录断言详情
        await Writer.write_assert_info(case_result, INFO)
    elif INFO and "error_type" in INFO:
        # 操作失败，记录错误信息
        await Writer.write_error_info(case_result, INFO)
    else:
        # 未知失败
        log.error("执行失败但无详细信息")
```

---

## ✅ 最佳实践总结

1. **动作方法**：成功返回 `(True, None)`，失败返回 `(False, error_info)`
2. **断言方法**：总是返回详情，成功 `(True, assert_info)`，失败 `(False, assert_info)`
3. **使用工具函数**：统一使用 `create_error_info` 和 `create_assert_info`
4. **区分异常类型**：捕获 `PlaywrightTimeoutError` 等特定异常，提供更准确的错误类型
5. **记录日志**：失败时记录详细日志，便于调试

---

## 🚫 避免的做法

❌ **不要返回不一致的结构**
```python
# 错误示例
return False, {"message": "error"}  # 缺少 error_type
return False, None  # 失败但没有错误信息
```

✅ **正确做法**
```python
return False, create_error_info("unknown", "error message", context.selector)
```

❌ **不要在断言方法中返回 None**
```python
# 错误示例
async def execute(...) -> tuple[bool, Optional[InfoDict]]:
    return True, None  # 断言方法应该总是返回详情
```

✅ **正确做法**
```python
async def execute(...) -> tuple[bool, InfoDict]:  # 注意不是 Optional
    return True, assert_info
```
