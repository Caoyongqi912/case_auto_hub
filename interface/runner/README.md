# Interface Runner 重构说明

## 文件结构

```
interface/runner/
├── __init__.py                    # 入口，导出 InterfaceRunner
├── interface_runner.py           # 主运行器 (重构后的 InterFaceRunner)
├── interface_executor.py         # 接口执行器 (负责单个接口的执行)
├── variable_manager.py           # 变量管理器 (封装 VariableTrans)
├── url_builder.py                # URL 构建器 (处理自定义/环境URL)
├── context.py                    # 执行上下文 (ExecutionContext, StepContext)
├── middleware.py                 # HttpxMiddleware (复用原代码)
│
├── step/                         # 步骤执行策略
│   ├── __init__.py              # 步骤策略工厂
│   ├── base.py                  # StepStrategy 基类
│   ├── api_step.py              # 单接口步骤
│   ├── api_group_step.py        # 接口组步骤
│   ├── condition_step.py        # 条件判断步骤
│   ├── sql_step.py              # SQL执行步骤
│   ├── script_step.py           # 脚本执行步骤
│   ├── wait_step.py             # 等待步骤
│   ├── assert_step.py           # 断言步骤
│   └── loop_step.py            # 循环步骤
│
└── loop/                         # 循环执行器
    ├── __init__.py              # 循环执行器工厂
    ├── base.py                  # LoopExecutor 基类
    ├── loop_times.py            # 次数循环
    ├── loop_items.py            # 遍历循环
    └── loop_condition.py        # 条件循环
```

## 重构要点

### 1. 职责分离

| 原文件 | 新文件 | 职责 |
|--------|--------|------|
| `InterFaceRunner` | `InterfaceRunner` | 用例执行流程控制 |
| - | `InterfaceExecutor` | 单接口执行、断言、变量提取 |
| - | `VariableManager` | 变量管理 |
| - | `UrlBuilder` | URL构建 |
| - | `StepStrategy` 系列 | 各类型步骤执行 |
| - | `LoopExecutor` 系列 | 各类型循环执行 |

### 2. 策略模式

- **步骤策略**: `get_step_strategy(step_type)` 返回对应的策略类
- **循环策略**: `get_loop_executor(loop_type)` 返回对应的执行器

### 3. 上下文对象

- `ExecutionContext`: 用例执行上下文，包含用例、环境、结果、进度等
- `StepContext`: 步骤执行上下文，包含步骤信息、变量管理器等

### 4. 依赖注入

```python
# 步骤策略接收 interface_executor
class ApiStepStrategy(StepStrategy):
    def __init__(self, interface_executor):
        self.interface_executor = interface_executor

# 循环执行器接收 starter, variable_manager, interface_executor
class LoopTimesExecutor(LoopExecutor):
    def __init__(self, starter, variable_manager, interface_executor):
        ...
```

## 使用方法

```python
# 原有代码保持兼容
from interface.runner import InterfaceRunner

# 替换原有的
# from interface.runner import InterFaceRunner

# 使用方式不变
runner = InterfaceRunner(starter)
await runner.run_interface_case(case_id, env_id, error_stop)
```

## 优势

1. **单一职责**: 每个类只负责一种功能
2. **易扩展**: 新增步骤类型只需新增策略类
3. **易测试**: 各组件可独立测试
4. **代码复用**: 公共逻辑抽取到基类
5. **可读性**: 文件结构清晰，易于理解

## 迁移说明

- 原 `interface/runner.py` 保留，可作为参考
- 逐步将调用处切换到新的 `InterfaceRunner`
- 测试通过后可删除旧文件
