# Interface Case Runner P0 加固计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 2 周内消除 11 个 P0 级别 BUG,这些 BUG 会导致**数据丢失 / 静默失败 / 安全沙箱可绕过 / 资源泄漏**,全部已在 V2 深度审查中确认。

**Architecture:** 走 TDD 流程,先写失败的回归测试,再写最小修复,再 commit。每个 BUG 独立 commit,独立 PR,确保任意一步回滚不会牵连其他修复。

**Tech Stack:** Python 3.13 / SQLAlchemy 2.0 async / pytest 9.0.1 / pytest-asyncio / httpx / SQLAlchemy polymorphic inheritance。

**关联文档:**
- 深度审查报告:[run_interface_case_deep_review.md](/Users/fanyuxuan/cyq_code/case_auto_hub/docs/review/run_interface_case_deep_review.md) (V2)
- 第一版审查报告:[run_interface_case_review.md](/Users/fanyuxuan/cyq_code/case_auto_hub/docs/review/run_interface_case_review.md) (V1)

---

## 〇、策略(Strategy)

### 0.1 修复原则

1. **测试先行**:每个修复必须先有一个失败的测试,证明 BUG 真实存在;修复后测试变绿,确保 BUG 不复发。
2. **最小变更**:一次 PR 只修一个 BUG,不夹带 refactor / 优化。
3. **可回滚**:每个 commit 独立,紧急回滚只 `git revert` 即可,不影响其他修复。
4. **保留向后兼容**:在迁移脚本 / 数据校验脚本落地前,**不删除字段**,只新增或改名。
5. **不动业务行为**:本计划只修"明显错误",**不**借此优化执行顺序、改写算法或重命名。

### 0.2 优先级矩阵

P0 选择标准 = `影响广度 × 修复成本` 之比,优先做"修一行顶十个"的:

| BUG | 描述 | 影响广度 | 修复成本 | 风险 | 选 P0 理由 |
| --- | --- | --- | --- | --- | --- |
| **M1** | target_id 是 ClassVar | 全模型序列化 | 低 | 低 | 静默丢数据 |
| **M2** | case_title 长度截断 | 所有长标题 case | 低 | 低 | 静默报错 |
| **M3** | BaseModel 不识别 JTI | 全步骤结果 | 中 | 中 | 修复影响面广 |
| **F1** | interfaceLog 字段名错 | 所有 case 日志 | 极低 | 极低 | 一行修复 |
| **F2** | 早返 None 触发 unpack 崩溃 | task 模式全 case | 低 | 低 | 隐性崩溃 |
| **D1** | result_writer 单例 | 并发全污染 | 中 | 中 | 数据正确性 |
| **E1** | HttpxClient 资源泄漏 | 每个 case 一次 | 中 | 中 | 连接池耗尽 |
| **S1** | Script 沙箱可逃逸 | **安全** | 中 | 中 | RCE 风险 |
| **S2** | 允许 import 任意模块 | **安全** | 低 | 中 | RCE 风险 |
| **S3** | SCRIPT_TIMEOUT 未生效 | **拒绝服务** | 中 | 中 | 阻塞 worker |
| **V1** | name mangling 爆 | 继承时 | 极低 | 低 | 立刻爆 |

P1/P2 暂不在本计划范围内,见第十二章"后续计划"。

### 0.3 实施顺序(why this order)

按"前置依赖 → 解锁更多问题 → 风险递增"排列:

1. **Phase 0 基础设施** (Task 1-2) — 没有测试无法验证修复
2. **Phase 1 模型层** (Task 3-6) — 模型是地基,先修能让后续测试更可靠(测试 setup 时不再有 None 干扰)
3. **Phase 2 流程层** (Task 7-9) — 流程层修复需要模型稳定才能复现
4. **Phase 3 资源管理** (Task 10-11) — 影响运行时,但与代码逻辑解耦,可以独立验证
5. **Phase 4 安全** (Task 12-14) — 沙箱是 worker 进程级别的,改完要立即验证
6. **Phase 5 变量系统** (Task 15) — 修复成本最低,放最后顺手收尾

### 0.4 并行化机会(可在不同分支同时开发)

| 分支 | Phase | 任务 | 预计冲突 |
| --- | --- | --- | --- |
| `codex/fix-p0-model` | 1 | Task 3-6 | 几乎无,各自改不同模型文件 |
| `codex/fix-p0-runner` | 2 | Task 7-9 | Task 7 改 `runner.py`,Task 8-9 也改 `runner.py`,顺序串行 |
| `codex/fix-p0-resource` | 3 | Task 10-11 | Task 10 改 `writer/`,Task 11 改 `common/`,无冲突 |
| `codex/fix-p0-security` | 4 | Task 12-14 | 全部改 `script_manager.py`,串行 |
| `codex/fix-p0-vars` | 5 | Task 15 | 改 `utils/variableTrans.py`,独立 |

合并顺序建议:model → runner → resource → vars → security (security 最后,因沙箱是兜底防线)。

### 0.5 风险登记(Risk Register)

| 风险 | 触发条件 | 缓解策略 |
| --- | --- | --- |
| 字段长度变更导致老数据截断 | M2 修复后老 case 标题 > 20 字符 | 加 migration 步骤,把 `interface_case_name` 改为 64,**默认值兼容老数据**;生产环境先跑一次 `SELECT LENGTH(case_title) > 20` 评估影响 |
| BaseModel 改动影响其他模块 | M3 修复后,play 模块的 CaseModel 也走 to_dict | 测试覆盖 `app/model/caseHub/` 下所有用到 `to_dict` 的地方;`git grep "to_dict"` 验证 |
| ScriptManager 沙箱过严导致老脚本失效 | S1/S2 修复后老脚本用了 `getattr` | 提供 `hub_getattr(obj, name)` 内置函数替代;在 release notes 列出"被禁用的语法" |
| HttpxClient 关闭逻辑改变行为 | E1 修复后请求并发时连接池行为变化 | 灰度策略:先在测试环境跑 24h,对比 QPS / 错误率 |
| pytest-asyncio 与现有 async 代码兼容 | 0.1 引入后某些测试 skip | 用 `pytest-asyncio` 的 `auto` 模式 + 显式 fixture 隔离 |

### 0.6 测试策略

- **覆盖目标**:每个 P0 BUG 对应至少 1 个回归测试。
- **测试分层**:
  - **单元测试** (90%):用 `unittest.mock` mock DB / HTTP,跑得快(秒级),无外部依赖。
  - **集成测试** (10%):在 `tests/integration/` 下,标记 `@pytest.mark.integration`,需要 MySQL + Redis 启动,跑前手动或 CI 钩子。
- **Mock 模式**:
  - DB session:`unittest.mock.AsyncMock(spec=AsyncSession)`
  - httpx:`pytest-httpx` 或 `respx`
  - WebSocket 推送:`AsyncMock` 替换 `starter.send`
- **覆盖率**:P0 修复后,目标 `croe/interface/runner.py` 整体覆盖率达 50% 以上(本计划结束后)。

### 0.7 发布策略

1. **PR 阶段**:每个 Phase 一个 PR,走正常 review。
2. **合并到 `codex/fix-p0-all` 集成分支**:全部 P0 修完后,在 staging 跑完整回归。
3. **生产灰度**:先在内部小流量跑 1 天,再全量。
4. **回滚预案**:每个 PR 独立 revert;若沙箱修复引入问题,可通过配置 `SCRIPT_SANDBOX_ENABLED=False` 临时回退(safety hatch,见 Task 12-Step 4)。

### 0.8 度量指标

修复成功的标志:
- 0 个 P0 BUG 残留(用 V2 报告逐条 check)。
- `croe/interface/runner.py` 的回归测试全绿。
- `pytest --cov=croe/interface/runner.py` 覆盖率 ≥ 50%。
- 现有 e2e 流程(运行一个简单 case)无回归。
- 沙箱在脚本里尝试 `getattr("", "__class__")` 被拦截(新增 1 个集成测试)。

### 0.9 不在本计划范围内

以下问题暂不修(见 V2 报告):

- BUG-F3/F4/F5/F6/F7(流程层 P1)
- BUG-M4-M11(模型层 P1/P2)
- BUG-D2-D11(Mapper 层)
- BUG-E2-E12(执行器 P1)
- BUG-V2-V6(变量系统 P1)
- BUG-S4-S7(安全 P1)
- OBS-*、PERF-*、TEST-*

会在下一个 P1 计划中处理。

---

## 一、Phase 0 - 测试基础设施(2 个任务)

### Task 1: 初始化 pytest 配置

**Files:**
- Create: `pytest.ini`
- Create: `tests/__init__.py`
- Create: `tests/conftest.py`

- [ ] **Step 1: 创建 `pytest.ini`**

```ini
[pytest]
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
asyncio_mode = auto
addopts = -v --tb=short --strict-markers
markers =
    integration: 需要真实 MySQL/Redis 的集成测试
    unit: 纯单元测试(默认)
    security: 安全相关测试
```

- [ ] **Step 2: 创建 `tests/__init__.py`**

```python
"""测试包根目录。"""
```

- [ ] **Step 3: 创建 `tests/conftest.py`**

```python
"""
全局 pytest fixtures。

约定:
- unit 测试不需要 DB,完全 mock
- integration 测试需要真实的 MySQL + Redis
"""
import os
import sys
from pathlib import Path

# 把项目根加入 sys.path,确保 `import croe` 等能找到
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


# 默认环境:单元测试不连真实 DB
os.environ.setdefault("CONFIG", "test")


import pytest
from unittest.mock import AsyncMock, MagicMock


@pytest.fixture
def mock_session():
    """返回一个 AsyncMock 的 SQLAlchemy AsyncSession。"""
    session = AsyncMock()
    session.__aenter__ = AsyncMock(return_value=session)
    session.__aexit__ = AsyncMock(return_value=None)
    return session


@pytest.fixture
def mock_starter():
    """Mock APIStarter,send/over 都是 AsyncMock。"""
    starter = MagicMock()
    starter.send = AsyncMock()
    starter.over = AsyncMock()
    starter.logs = []
    starter.userId = 1
    starter.username = "tester"
    starter.uid = "test-uid"
    starter.startBy = 1
    return starter
```

- [ ] **Step 4: 运行 pytest 验证(应能运行但无测试)**

Run: `pytest`
Expected: 看到 "no tests ran" 或 "0 passed",**不能报错**。

- [ ] **Step 5: Commit**

```bash
git add pytest.ini tests/__init__.py tests/conftest.py
git commit -m "test: 初始化 pytest 配置与全局 fixtures"
```

---

### Task 2: 建立 V2 审查 BUG 编号的常量文件

**Files:**
- Create: `tests/croe/interface/__init__.py`
- Create: `tests/croe/interface/_bug_ids.py`

- [ ] **Step 1: 创建 `tests/croe/__init__.py` 和 `tests/croe/interface/__init__.py`**

```python
# tests/croe/__init__.py
"""croe 模块的测试包。"""
```

```python
# tests/croe/interface/__init__.py
"""croe.interface 模块的测试包。"""
```

- [ ] **Step 2: 创建 `tests/croe/interface/_bug_ids.py`(测试辅助常量)**

```python
"""
V2 审查报告中的 BUG 编号常量。

目的:让回归测试和审查报告交叉引用,任何一个回归测试都能直接对应到 V2 报告的某个 BUG 编号。
"""

# 模型层
BUG_M1 = "M1"  # target_id ClassVar
BUG_M2 = "M2"  # case_title 长度
BUG_M3 = "M3"  # BaseModel JTI

# 流程层
BUG_F1 = "F1"  # interfaceLog 字段名
BUG_F2 = "F2"  # 早返 None
BUG_F3 = "F3"  # init_global_headers 错位
BUG_F4 = "F4"  # init_interface_case_vars 静默
BUG_F5 = "F5"  # error_stop 状态机

# Mapper 层
BUG_D1 = "D1"  # result_writer 单例

# 执行器
BUG_E1 = "E1"  # HttpxClient 资源

# 安全
BUG_S1 = "S1"  # getattr 沙箱逃逸
BUG_S2 = "S2"  # import 沙箱逃逸
BUG_S3 = "S3"  # SCRIPT_TIMEOUT 未生效

# 变量
BUG_V1 = "V1"  # name mangling
```

- [ ] **Step 3: Commit**

```bash
git add tests/croe/__init__.py tests/croe/interface/__init__.py tests/croe/interface/_bug_ids.py
git commit -m "test: 添加 BUG 编号常量,便于回归测试交叉引用"
```

---

## 二、Phase 1 - 模型层 P0(4 个任务)

### Task 3 (BUG-M1): 修复 `target_id` ClassVar 假字段

**问题摘要:**[interfaceCaseContentsModel.py:43](/Users/fanyuxuan/cyq_code/case_auto_hub/app/model/interfaceAPIModel/contents/interfaceCaseContentsModel.py) 把 `target_id` 声明为 `ClassVar`,子类的 `target_id` Column 在 `to_dict` 中会被覆盖为 `None`。

**Files:**
- Modify: `app/model/interfaceAPIModel/contents/interfaceCaseContentsModel.py:43-49`
- Create: `tests/croe/interface/test_bug_m1_target_id.py`

- [ ] **Step 1: 写失败测试**

```python
# tests/croe/interface/test_bug_m1_target_id.py
"""
BUG-M1 回归测试:target_id 不应是 ClassVar。
"""
import pytest
from app.model.interfaceAPIModel.contents import APIStepContent
from tests.croe.interface._bug_ids import BUG_M1


@pytest.mark.security
@pytest.mark.unit
def test_bug_m1_api_step_content_to_dict_contains_target_id(bug_m1_marker):
    """BUG-M1: APIStepContent.to_dict() 应包含 target_id 的真实值,而非 None。"""
    # Arrange:直接构造一个内存中的 APIStepContent
    content = APIStepContent(
        target_id=42,
        content_name="测试API",
        content_type=1,
    )
    # Act
    result = content.to_dict()

    # Assert
    assert result.get("target_id") == 42, (
        f"[{BUG_M1}] to_dict 应当返回 target_id=42,实际得到 {result.get('target_id')!r}"
    )


@pytest.fixture
def bug_m1_marker():
    """标记当前测试对应的 BUG 编号,方便报告。"""
    return BUG_M1
```

- [ ] **Step 2: 运行测试,确认失败**

Run: `pytest tests/croe/interface/test_bug_m1_target_id.py -v`
Expected: FAIL,断言信息 `to_dict 应当返回 target_id=42,实际得到 None`。

- [ ] **Step 3: 修复 `interfaceCaseContentsModel.py`**

修改 [app/model/interfaceAPIModel/contents/interfaceCaseContentsModel.py:43](/Users/fanyuxuan/cyq_code/case_auto_hub/app/model/interfaceAPIModel/contents/interfaceCaseContentsModel.py):

**修改前**:
```python
target_id: ClassVar[int | None] = None
```

**修改后**(整段删除这一行):
```python
# (删除 target_id: ClassVar[int | None] = None 这一行)
# target_id 由各子类自己定义为 Column
```

同时清理 import:

**修改前**:
```python
from typing import ClassVar, Optional, Set
```

**修改后**:
```python
from typing import Optional, Set
```

- [ ] **Step 4: 重新跑测试,确认通过**

Run: `pytest tests/croe/interface/test_bug_m1_target_id.py -v`
Expected: PASS

- [ ] **Step 5: 检查 `to_dict` 父类不会覆盖子类字段**

打开 [interfaceCaseContentsModel.py:67-105](/Users/fanyuxuan/cyq_code/case_auto_hub/app/model/interfaceAPIModel/contents/interfaceCaseContentsModel.py) 的 `to_dict`,确认子类 mapper 字段合并时不显式写 `target_id` 到 dict(看代码,目前确实没写),但 `result` dict 初始化处要确认:

**修改前**(若存在):
```python
result = {
    'content_type': self.content_type,
    'target_id': self.target_id,  # ← 这行如果是写死的,会拿 None
    ...
}
```

**修改后**:
```python
result = {
    'content_type': self.content_type,
    # target_id 由子类 mapper 遍历时填充
    ...
}
```

- [ ] **Step 6: 再跑一次全部 M1 测试**

Run: `pytest tests/croe/interface/test_bug_m1_target_id.py -v`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add app/model/interfaceAPIModel/contents/interfaceCaseContentsModel.py
git add tests/croe/interface/test_bug_m1_target_id.py
git commit -m "fix(model): 修复 InterfaceCaseContents.target_id ClassVar 导致 to_dict 永远为 None (BUG-M1)"
```

---

### Task 4 (BUG-M2): 对齐 `case_title` 与 `interface_case_name` 长度

**问题摘要:**[interfaceCaseModel.py:20](/Users/fanyuxuan/cyq_code/case_auto_hub/app/model/interfaceAPIModel/interfaceCaseModel.py) `case_title=String(40)`;[interfaceResultModel.py:95](/Users/fanyuxuan/cyq_code/case_auto_hub/app/model/interfaceAPIModel/interfaceResultModel.py) `interface_case_name=String(20)`。长 case 标题插入 case_result 时 `Data too long`。

**Files:**
- Modify: `app/model/interfaceAPIModel/interfaceResultModel.py:95`
- Create: `tests/croe/interface/test_bug_m2_case_title_length.py`

- [ ] **Step 1: 写失败测试**

```python
# tests/croe/interface/test_bug_m2_case_title_length.py
"""
BUG-M2 回归测试:interface_case_name 应能容纳完整 case_title。
"""
import pytest
from sqlalchemy import String
from app.model.interfaceAPIModel.interfaceResultModel import InterfaceCaseResult
from app.model.interfaceAPIModel.interfaceCaseModel import InterfaceCase
from tests.croe.interface._bug_ids import BUG_M2


@pytest.mark.unit
def test_bug_m2_case_result_name_length_supports_case_title():
    """[BUG-M2] interface_case_name 长度应 >= case_title 长度。"""
    case_title_col = InterfaceCase.__table__.columns["case_title"]
    case_result_name_col = InterfaceCaseResult.__table__.columns["interface_case_name"]

    assert isinstance(case_title_col.type, String)
    assert isinstance(case_result_name_col.type, String)

    case_title_len = case_title_col.type.length
    case_result_len = case_result_name_col.type.length

    assert case_result_len >= case_title_len, (
        f"[{BUG_M2}] interface_case_name 长度 ({case_result_len}) "
        f"必须 >= case_title 长度 ({case_title_len}),否则长标题会 Data too long"
    )
```

- [ ] **Step 2: 跑测试,确认失败**

Run: `pytest tests/croe/interface/test_bug_m2_case_title_length.py -v`
Expected: FAIL,断言长度比较失败。

- [ ] **Step 3: 修复模型**

修改 [app/model/interfaceAPIModel/interfaceResultModel.py:95](/Users/fanyuxuan/cyq_code/case_auto_hub/app/model/interfaceAPIModel/interfaceResultModel.py):

**修改前**:
```python
interface_case_name = Column(String(20), comment="用例名称")
```

**修改后**:
```python
interface_case_name = Column(String(64), comment="用例名称")
```

> 说明:不直接对齐 40 是为了给未来预留扩展空间;64 是 40 的 1.6 倍,够用。

- [ ] **Step 4: 跑测试,确认通过**

Run: `pytest tests/croe/interface/test_bug_m2_case_title_length.py -v`
Expected: PASS

- [ ] **Step 5: 同时检查 `interface_case_desc` (50 字符) 是否够用**

读取 [interfaceResultModel.py:97](/Users/fanyuxuan/cyq_code/case_auto_hub/app/model/interfaceAPIModel/interfaceResultModel.py) `interface_case_desc = Column(String(50))`,对比 [interfaceCaseModel.py:21](/Users/fanyuxuan/cyq_code/case_auto_hub/app/model/interfaceAPIModel/interfaceCaseModel.py) `case_desc = Column(String(200))`。**同样存在截断风险**,但 desc 通常比 title 短,作为本次修复的副产物也建议调整:

修改:
```python
# 修改前
interface_case_desc = Column(String(50), comment="用例描述")
# 修改后
interface_case_desc = Column(String(255), comment="用例描述")
```

并在 Step 1 的测试中追加:
```python
case_desc_col = InterfaceCase.__table__.columns["case_desc"]
case_result_desc_col = InterfaceCaseResult.__table__.columns["interface_case_desc"]
assert case_result_desc_col.type.length >= case_desc_col.type.length, \
    f"[{BUG_M2}] interface_case_desc 长度必须 >= case_desc"
```

- [ ] **Step 6: 再跑测试**

Run: `pytest tests/croe/interface/test_bug_m2_case_title_length.py -v`
Expected: PASS

- [ ] **Step 7: 生成 alembic 迁移(如果项目用 alembic)**

Run: 检查项目是否用 alembic:

```bash
ls alembic/ 2>/dev/null || ls migrations/ 2>/dev/null
```

- 如果有 alembic,生成迁移:`alembic revision --autogenerate -m "fix: align interface_case_name length to 64"`
- 如果没有 alembic,在 doc 章节加 `MANUAL_MIGRATION.md`,记录需要在生产跑 `ALTER TABLE interface_case_result MODIFY interface_case_name VARCHAR(64);` 类似的 SQL。

- [ ] **Step 8: Commit**

```bash
git add app/model/interfaceAPIModel/interfaceResultModel.py tests/croe/interface/test_bug_m2_case_title_length.py
[ -f alembic/versions/*.py ] && git add alembic/versions/
git commit -m "fix(model): 修复 interface_case_name 长度不足导致长标题 Data too long (BUG-M2)"
```

---

### Task 5 (BUG-M3): 修复 `BaseModel.to_dict` / `map` 不识别 JTI 子类字段

**问题摘要:**[basic.py:38-65](/Users/fanyuxuan/cyq_code/case_auto_hub/app/model/basic.py) `to_dict` / `map` 只遍历 `self.__table__.columns`,Joined Table Inheritance 子类字段会被遗漏。

**Files:**
- Modify: `app/model/basic.py:38-65`
- Create: `tests/croe/interface/test_bug_m3_base_dict_jti.py`

- [ ] **Step 1: 写失败测试**

```python
# tests/croe/interface/test_bug_m3_base_dict_jti.py
"""
BUG-M3 回归测试:BaseModel 的 to_dict/map 应能输出 JTI 子类字段。
"""
import pytest
from app.model.interfaceAPIModel.interfaceResultModel import (
    APIStepContentResult, GroupStepContentResult, LoopStepContentResult
)
from tests.croe.interface._bug_ids import BUG_M3


@pytest.mark.unit
def test_bug_m3_api_step_content_result_to_dict_includes_subclass_field():
    """[BUG-M3] APIStepContentResult(子类).to_dict() 应包含 interface_result_id。"""
    obj = APIStepContentResult(
        case_result_id=1,
        task_result_id=2,
        content_id=3,
        content_name="t",
        content_step=1,
        content_type=1,  # STEP_API
        interface_result_id=999,  # 子类字段
    )
    result = obj.to_dict()
    assert result.get("interface_result_id") == 999, (
        f"[{BUG_M3}] to_dict 应包含子类字段 interface_result_id=999,实际 {result.get('interface_result_id')!r}"
    )


@pytest.mark.unit
def test_bug_m3_group_step_content_result_to_dict_includes_subclass_fields():
    """[BUG-M3] GroupStepContentResult.to_dict() 应包含 total_api_num/success_api_num/fail_api_num。"""
    obj = GroupStepContentResult(
        case_result_id=1,
        content_id=2,
        content_name="g",
        content_step=1,
        content_type=2,  # STEP_API_GROUP
        total_api_num=10,
        success_api_num=8,
        fail_api_num=2,
    )
    result = obj.to_dict()
    for key, expected in [
        ("total_api_num", 10),
        ("success_api_num", 8),
        ("fail_api_num", 2),
    ]:
        assert result.get(key) == expected, (
            f"[{BUG-M3}] to_dict 应包含 {key}={expected},实际 {result.get(key)!r}"
        )
```

- [ ] **Step 2: 跑测试,确认失败**

Run: `pytest tests/croe/interface/test_bug_m3_base_dict_jti.py -v`
Expected: FAIL,断言子类字段缺失。

- [ ] **Step 3: 重写 `BaseModel.to_dict` / `map`**

修改 [app/model/basic.py:38-65](/Users/fanyuxuan/cyq_code/case_auto_hub/app/model/basic.py):

**修改前**:
```python
@property
def map(self) -> dict:
    _ = dict()
    for c in self.__table__.columns:
        v = getattr(self, c.name)
        if isinstance(v, datetime):
            _[c.name] = v.strftime("%Y-%m-%d %H:%M:%S")
        else:
            _[c.name] = v
    return _

def to_dict(self, exclude: Optional[Set[str]] = None):
    _ = dict()
    for c in self.__table__.columns:
        if exclude and c.name in exclude:
            continue
        v = getattr(self, c.name)
        if isinstance(v, datetime):
            _[c.name] = v.strftime("%Y-%m-%d %H:%M:%S")
        else:
            _[c.name] = v
    return _
```

**修改后**(用 `inspect` 获取完整 mapper.columns,含继承的):
```python
from sqlalchemy import inspect as sa_inspect

@property
def map(self) -> dict:
    return self._to_dict_impl(exclude=None)

def to_dict(self, exclude: Optional[Set[str]] = None):
    return self._to_dict_impl(exclude=exclude)

def _to_dict_impl(self, exclude: Optional[Set[str]] = None) -> dict:
    """
    统一序列化方法,兼容 JTI(Joined Table Inheritance)。

    使用 SQLAlchemy inspect 拿到当前实例 mapper 的所有 columns,
    包括从父类继承来的字段,避免子表字段丢失。
    """
    _ = {}
    mapper = sa_inspect(self.__class__)
    for c in mapper.columns:
        if exclude and c.key in exclude:
            continue
        v = getattr(self, c.key, None)
        if isinstance(v, datetime):
            _[c.key] = v.strftime("%Y-%m-%d %H:%M:%S")
        else:
            _[c.key] = v
    return _
```

- [ ] **Step 4: 跑测试,确认通过**

Run: `pytest tests/croe/interface/test_bug_m3_base_dict_jti.py -v`
Expected: PASS

- [ ] **Step 5: 运行所有现存的 to_dict 使用方,确认无回归**

Run: `grep -rn "\.to_dict(" app/ croe/ --include="*.py" | grep -v test_`
手动检查每处调用:它们期望的字段是否在新的 to_dict 输出中?如果有任何调用方**依赖旧行为**(比如期望 `to_dict` 不含子类字段),需要在该处单独调整。

预期:由于旧实现漏字段,**大部分调用方本来就会出错**,所以"修正后反而出错"的情况极少。

- [ ] **Step 6: 跑全量测试套件**

Run: `pytest -m unit -q`
Expected: 全部已存在的测试 PASS;之前因为 M1/M2 写过的测试也 PASS。

- [ ] **Step 7: Commit**

```bash
git add app/model/basic.py tests/croe/interface/test_bug_m3_base_dict_jti.py
git commit -m "fix(model): BaseModel.to_dict/map 使用 SQLAlchemy inspect 兼容 JTI 子类字段 (BUG-M3)"
```

---

### Task 6 (BUG-M11): 修复 `interface_uid` 长度截断

**问题摘要:**[interfaceResultModel.py:33](/Users/fanyuxuan/cyq_code/case_auto_hub/app/model/interfaceAPIModel/interfaceResultModel.py) `interface_uid = Column(String(20))`,而 `BaseModel.uid` 是 50 字符,`InterfaceCaseResult.interface_case_uid` 也是 20 字符。需统一到 50。

**Files:**
- Modify: `app/model/interfaceAPIModel/interfaceResultModel.py:33, 96`
- Create: `tests/croe/interface/test_bug_m11_uid_length.py`

- [ ] **Step 1: 写失败测试**

```python
# tests/croe/interface/test_bug_m11_uid_length.py
"""
BUG-M11 回归测试:*_uid 字段长度应与 BaseModel.uid(50) 一致。
"""
import pytest
from sqlalchemy import String
from app.model.interfaceAPIModel.interfaceResultModel import (
    InterfaceResult, InterfaceCaseResult, InterfaceTaskResult
)
from app.model.basic import BaseModel
from tests.croe.interface._bug_ids import BUG_M3  # 复用编号,M 类


@pytest.mark.unit
def test_bug_m11_uid_columns_at_least_base_uid_length():
    """[BUG-M11] 所有 *_uid 列长度应 >= BaseModel.uid 长度(50)。"""
    base_uid_len = BaseModel.__table__.columns["uid"].type.length
    assert base_uid_len == 50

    for model, col in [
        (InterfaceResult, "interface_uid"),
        (InterfaceCaseResult, "interface_case_uid"),
        (InterfaceTaskResult, "task_uid"),
    ]:
        col_obj = model.__table__.columns.get(col)
        if col_obj is None:
            continue
        col_len = col_obj.type.length
        assert col_len >= base_uid_len, (
            f"[{BUG_M11}] {model.__name__}.{col} 长度 ({col_len}) "
            f"必须 >= BaseModel.uid 长度 ({base_uid_len})"
        )
```

- [ ] **Step 2: 跑测试,确认失败**

Run: `pytest tests/croe/interface/test_bug_m11_uid_length.py -v`
Expected: FAIL(若 `InterfaceResult.interface_uid=20` 触发)

- [ ] **Step 3: 修复模型**

修改 [app/model/interfaceAPIModel/interfaceResultModel.py](/Users/fanyuxuan/cyq_code/case_auto_hub/app/model/interfaceAPIModel/interfaceResultModel.py):

**修改前**:
```python
interface_uid = Column(String(20), comment="用例Uid")  # line 33
...
interface_case_uid = Column(String(20), comment="用例Uid")  # line 96
...
task_uid = Column(String(10), nullable=False, comment="task索引")  # task_result
```

**修改后**:
```python
interface_uid = Column(String(50), comment="用例Uid")
...
interface_case_uid = Column(String(50), comment="用例Uid")
...
task_uid = Column(String(50), nullable=False, comment="task索引")
```

- [ ] **Step 4: 跑测试,确认通过**

Run: `pytest tests/croe/interface/test_bug_m11_uid_length.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/model/interfaceAPIModel/interfaceResultModel.py tests/croe/interface/test_bug_m11_uid_length.py
git commit -m "fix(model): 对齐 *_uid 字段长度为 BaseModel.uid 长度 50 (BUG-M11)"
```

---

## 三、Phase 2 - 流程层 P0(3 个任务)

### Task 7 (BUG-F1): 修复 `interfaceLog` 字段名错位

**问题摘要:**[runner.py:225](/Users/fanyuxuan/cyq_code/case_auto_hub/croe/interface/runner.py) 写 `case_result.interfaceLog`(camelCase),但模型字段是 `interface_log`(snake_case)。日志从未落库。

**Files:**
- Modify: `croe/interface/runner.py:225`
- Create: `tests/croe/interface/test_bug_f1_interface_log.py`

- [ ] **Step 1: 写失败测试**

```python
# tests/croe/interface/test_bug_f1_interface_log.py
"""
BUG-F1 回归测试:runner 应写 case_result.interface_log,不是 interfaceLog。
"""
import pytest
from unittest.mock import MagicMock, AsyncMock
from app.model.interfaceAPIModel.interfaceResultModel import InterfaceCaseResult
from croe.interface.writer import result_writer
from tests.croe.interface._bug_ids import BUG_F1


@pytest.mark.unit
@pytest.mark.asyncio
async def test_bug_f1_interface_log_field_assignment():
    """[BUG-F1] runner 应在 case_result.interface_log 上写日志(不是 interfaceLog)。"""
    case_result = InterfaceCaseResult(
        interface_case_id=1,
        interface_case_name="test",
        interface_case_uid="u-1",
        project_id=1,
        module_id=1,
    )

    # 模拟 starter.logs
    starter = MagicMock()
    starter.logs = ["step1 done\n", "step2 done\n"]
    starter.send = AsyncMock()
    starter.over = AsyncMock()
    starter.username = "u"
    starter.userId = 1

    # 直接调 finalize_case_result 模拟最终落库
    await result_writer.finalize_case_result(case_result=case_result, logs="".join(starter.logs))

    # 关键断言:界面 case_result 的 interface_log 字段被设置
    assert case_result.interface_log == "step1 done\nstep2 done\n", (
        f"[{BUG_F1}] case_result.interface_log 应为日志,实际 {case_result.interface_log!r}"
    )
    # 反向断言:不应该有 interfaceLog 属性(代表 camelCase 写法)
    assert not hasattr(case_result, "interfaceLog") or getattr(case_result, "interfaceLog", None) is None, (
        f"[{BUG_F1}] case_result 不应有 interfaceLog (camelCase) 属性"
    )
```

- [ ] **Step 2: 跑测试,确认失败**

Run: `pytest tests/croe/interface/test_bug_f1_interface_log.py -v`
Expected: FAIL,断言 `interface_log` 没被写入。

- [ ] **Step 3: 修复 `runner.py`**

修改 [croe/interface/runner.py:225](/Users/fanyuxuan/cyq_code/case_auto_hub/croe/interface/runner.py):

**修改前**:
```python
case_result.interfaceLog = "".join(self.starter.logs)
await result_writer.finalize_case_result(
    case_result=case_result,
    logs="".join(self.starter.logs)
)
```

**修改后**(删除 camelCase 的赋值,只通过 logs= 参数传):
```python
# 不再单独给 case_result.interfaceLog 赋值
# 日志会由 finalize_case_result 内部通过 logs 参数写入 interface_log 字段
await result_writer.finalize_case_result(
    case_result=case_result,
    logs="".join(self.starter.logs)
)
```

- [ ] **Step 4: 跑测试,确认通过**

Run: `pytest tests/croe/interface/test_bug_f1_interface_log.py -v`
Expected: PASS

- [ ] **Step 5: 全项目 grep 还有没有 `interfaceLog` 的写法**

Run: `grep -rn "interfaceLog" app/ croe/ --include="*.py"`
Expected: 0 结果(除注释/字符串外)。

如果有遗留,全部改为 `interface_log`。

- [ ] **Step 6: Commit**

```bash
git add croe/interface/runner.py tests/croe/interface/test_bug_f1_interface_log.py
git commit -m "fix(runner): 移除 case_result.interfaceLog 错误赋值,日志通过 finalize 接口写入 (BUG-F1)"
```

---

### Task 8 (BUG-F2): 修复早返 `None` 触发 unpack 崩溃

**问题摘要:**[runner.py:134, 149](/Users/fanyuxuan/cyq_code/case_auto_hub/croe/interface/runner.py) 两处 `return await self.starter.over()` 返回 `None`,但签名是 `Tuple[bool, Optional[Any]]`,task 模式调用方 `success, _ = await ...` 会 `TypeError`。

**Files:**
- Modify: `croe/interface/runner.py:130-150`
- Create: `tests/croe/interface/test_bug_f2_early_return.py`

- [ ] **Step 1: 写失败测试**

```python
# tests/croe/interface/test_bug_f2_early_return.py
"""
BUG-F2 回归测试:runner 在用例不存在或步骤为空时,应返回 (False, None) 而不是 None。
"""
import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from app.model.interfaceAPIModel.interfaceCaseModel import InterfaceCase
from croe.interface.runner import InterfaceRunner
from tests.croe.interface._bug_ids import BUG_F2


@pytest.mark.unit
@pytest.mark.asyncio
async def test_bug_f2_early_return_when_case_not_found():
    """[BUG-F2] case 不存在时,run_interface_case 应返回 (False, None)。"""
    starter = MagicMock()
    starter.send = AsyncMock()
    starter.over = AsyncMock()
    starter.username = "u"
    starter.userId = 1
    starter.uid = "u1"

    runner = InterfaceRunner(starter=starter)

    # 关键断言:必须返回二元组,不能返回 None
    with patch(
        "app.mapper.interfaceApi.interfaceCaseMapper.InterfaceCaseMapper.get_by_id",
        new=AsyncMock(return_value=None),
    ):
        result = await runner.run_interface_case(
            interface_case_id=999,
            env=1,
            error_stop=False,
        )

    assert result is not None, f"[{BUG_F2}] 早返路径不能返回 None"
    assert isinstance(result, tuple) and len(result) == 2, (
        f"[{BUG_F2}] 早返应是 (bool, Optional[Any]) 二元组,实际 {type(result)!r}"
    )
    assert result[0] is False, f"[{BUG_F2}] 早返 success 应为 False"
    assert result[1] is None, f"[{BUG_F2}] 早返 case_result 应为 None"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_bug_f2_early_return_when_no_steps():
    """[BUG-F2] 用例存在但无步骤时,也应返回 (False, None)。"""
    starter = MagicMock()
    starter.send = AsyncMock()
    starter.over = AsyncMock()
    starter.username = "u"
    starter.userId = 1
    starter.uid = "u1"

    runner = InterfaceRunner(starter=starter)

    case = InterfaceCase(id=1, case_title="x", case_uid="u-1", project_id=1, module_id=1)

    async def fake_get_by_id(ident, **_):
        if ident == 1:
            return case
        return None

    with patch(
        "app.mapper.interfaceApi.interfaceCaseMapper.InterfaceCaseMapper.get_by_id",
        new=AsyncMock(side_effect=fake_get_by_id),
    ), patch(
        "app.mapper.interfaceApi.interfaceCaseMapper.InterfaceCaseMapper.query_steps",
        new=AsyncMock(return_value=[]),
    ):
        result = await runner.run_interface_case(
            interface_case_id=1,
            env=1,
            error_stop=False,
        )

    assert result is not None
    assert isinstance(result, tuple) and len(result) == 2
    assert result[0] is False
    assert result[1] is None
```

- [ ] **Step 2: 跑测试,确认失败**

Run: `pytest tests/croe/interface/test_bug_f2_early_return.py -v`
Expected: FAIL(`cannot unpack non-iterable NoneType` 或类似)。

- [ ] **Step 3: 修复 `runner.py`**

修改 [croe/interface/runner.py:130-150](/Users/fanyuxuan/cyq_code/case_auto_hub/croe/interface/runner.py):

**修改前**:
```python
if not interface_case:
    await self.starter.send(
        f"未通过{interface_case_id} 找到 相关业务流用例"
    )
    return await self.starter.over()
...
if not case_content_steps:
    await self.starter.send("无可执行业务流步骤,结束执行")
    return await self.starter.over()
```

**修改后**:
```python
if not interface_case:
    await self.starter.send(
        f"未通过{interface_case_id} 找到 相关业务流用例"
    )
    await self.starter.over()
    return False, None
...
if not case_content_steps:
    await self.starter.send("无可执行业务流步骤,结束执行")
    await self.starter.over()
    return False, None
```

- [ ] **Step 4: 跑测试,确认通过**

Run: `pytest tests/croe/interface/test_bug_f2_early_return.py -v`
Expected: PASS

- [ ] **Step 5: 跑全量测试**

Run: `pytest -m unit -q`
Expected: 全 PASS,无回归。

- [ ] **Step 6: Commit**

```bash
git add croe/interface/runner.py tests/croe/interface/test_bug_f2_early_return.py
git commit -m "fix(runner): 早返路径返回 (False, None) 而非 None,避免 task 模式 unpack 崩溃 (BUG-F2)"
```

---

### Task 9 (BUG-F3): 修复 `init_global_headers` 静默错位

**问题摘要:**[runner.py:318-331](/Users/fanyuxuan/cyq_code/case_auto_hub/croe/interface/runner.py) 的 `init_global_headers` 成功分支没有 return,`self.global_headers`(实例字段)从未被任何代码读取,实际生效的是 `self.interface_executor.g_headers`,造成两个字段不一致;且成功时 `or []` 永远走不到。

**Files:**
- Modify: `croe/interface/runner.py:46-50, 318-331`
- Create: `tests/croe/interface/test_bug_f3_global_headers.py`

- [ ] **Step 1: 写失败测试**

```python
# tests/croe/interface/test_bug_f3_global_headers.py
"""
BUG-F3 回归测试:init_global_headers 应真正把全局 header 注入到 executor.g_headers。
"""
import pytest
from unittest.mock import MagicMock, AsyncMock
from app.model.interfaceAPIModel.interfaceGlobalModel import InterfaceGlobalHeader
from croe.interface.runner import InterfaceRunner
from tests.croe.interface._bug_ids import BUG_F3


@pytest.mark.unit
@pytest.mark.asyncio
async def test_bug_f3_global_headers_actually_applied_to_executor():
    """[BUG-F3] init_global_headers 加载后,executor.g_headers 应当有值。"""
    starter = MagicMock()
    starter.send = AsyncMock()
    starter.username = "u"
    starter.userId = 1

    runner = InterfaceRunner(starter=starter)

    # 准备 2 个全局 header
    h1 = InterfaceGlobalHeader(id=1, key="X-Token", value="abc", project_id=1)
    h2 = InterfaceGlobalHeader(id=2, key="X-App", value="case_hub", project_id=1)

    with patch(
        "app.mapper.interfaceApi.interfaceGlobalMapper.InterfaceGlobalHeaderMapper.query_all",
        new=AsyncMock(return_value=[h1, h2]),
    ):
        await runner.init_global_headers()

    # 关键断言:executor.g_headers 应有这 2 个 header
    assert len(runner.interface_executor.g_headers) == 2, (
        f"[{BUG_F3}] executor.g_headers 应有 2 个全局 header,实际 {len(runner.interface_executor.g_headers)}"
    )
    keys = {h.key for h in runner.interface_executor.g_headers}
    assert keys == {"X-Token", "X-App"}


@pytest.mark.unit
@pytest.mark.asyncio
async def test_bug_f3_global_headers_empty():
    """[BUG-F3] 全局 header 为空时,executor.g_headers 应为空列表(不报错)。"""
    starter = MagicMock()
    starter.send = AsyncMock()
    starter.username = "u"
    starter.userId = 1

    runner = InterfaceRunner(starter=starter)

    with patch(
        "app.mapper.interfaceApi.interfaceGlobalMapper.InterfaceGlobalHeaderMapper.query_all",
        new=AsyncMock(return_value=[]),
    ):
        await runner.init_global_headers()

    assert runner.interface_executor.g_headers == []
```

- [ ] **Step 2: 跑测试,确认失败**

Run: `pytest tests/croe/interface/test_bug_f3_global_headers.py -v`
Expected: FAIL(`executor.g_headers` 为空,因为 `self.interface_executor.g_headers = global_headers or []` 这行没被执行)。

- [ ] **Step 3: 修复 `runner.py`**

修改 [croe/interface/runner.py:318-331](/Users/fanyuxuan/cyq_code/case_auto_hub/croe/interface/runner.py):

**修改前**:
```python
async def init_global_headers(self) -> Optional[List[InterfaceGlobalHeader]]:
    """
    初始化g headers
    """
    # 添加全局请求头
    global_headers = await InterfaceGlobalHeaderMapper.query_all()
    if not global_headers:
        log.info(f"use global_headers {global_headers}")
        return None
    if global_headers:
        await self.starter.send(
            f"🫳🫳 全局Headers已加载: {len(self.global_headers)} 条"
        )
        self.interface_executor.g_headers = global_headers or []
```

**修改后**:
```python
async def init_global_headers(self) -> List[InterfaceGlobalHeader]:
    """
    加载全局请求头并应用到 executor。

    Returns:
        加载到的全局 header 列表(可能为空)
    """
    global_headers = await InterfaceGlobalHeaderMapper.query_all()
    if not global_headers:
        log.info("未配置全局 header")
        return []

    await self.starter.send(
        f"🫳🫳 全局Headers已加载: {len(global_headers)} 条"
    )
    # 真正生效:注入到 executor.g_headers
    self.interface_executor.g_headers = list(global_headers)
    return global_headers
```

- [ ] **Step 4: 同步修复 `__init__` 中 `self.global_headers` 的不一致**

修改 [croe/interface/runner.py:35, 46](/Users/fanyuxuan/cyq_code/case_auto_hub/croe/interface/runner.py):

**修改前**:
```python
__slots__ = ("starter", "variable_manager", "interface_executor", "global_headers")
...
self.global_headers: List[InterfaceGlobalHeader] = []
self.interface_executor = InterfaceExecutor(
    starter=self.starter,
    variable_manager=self.variable_manager,
    global_headers=self.global_headers,
)
```

**修改后**:
```python
__slots__ = ("starter", "variable_manager", "interface_executor", "_g_headers")
...
self._g_headers: List[InterfaceGlobalHeader] = []
self.interface_executor = InterfaceExecutor(
    starter=self.starter,
    variable_manager=self.variable_manager,
    global_headers=self._g_headers,
)
```

- [ ] **Step 5: 跑测试,确认通过**

Run: `pytest tests/croe/interface/test_bug_f3_global_headers.py -v`
Expected: PASS

- [ ] **Step 6: 全项目 grep 还有没有 `self.global_headers` 的引用**

Run: `grep -rn "self.global_headers" croe/ app/ --include="*.py"`
Expected: 0 结果(若仍有,改成 `self._g_headers` 或 `self.interface_executor.g_headers`)。

- [ ] **Step 7: 跑全量测试**

Run: `pytest -m unit -q`
Expected: 全 PASS。

- [ ] **Step 8: Commit**

```bash
git add croe/interface/runner.py tests/croe/interface/test_bug_f3_global_headers.py
git commit -m "fix(runner): 修正 init_global_headers,真正注入到 executor 并修复返回类型 (BUG-F3)"
```

---

## 四、Phase 3 - 资源管理 P0(2 个任务)

### Task 10 (BUG-D1): 把 `result_writer` 改为 `InterfaceRunner` 持有的实例

**问题摘要:**[writer/__init__.py:11](/Users/fanyuxuan/cyq_code/case_auto_hub/croe/interface/writer/__init__.py) `result_writer = ResultWriter()` 模块单例,所有 `InterfaceRunner` 共享 `api_result_cache` / `content_result_cache`,并发时互相污染。

**Files:**
- Modify: `croe/interface/writer/__init__.py`
- Modify: `croe/interface/writer/result_writer.py`(增加 `clear_cache` 自动调用)
- Modify: `croe/interface/runner.py`(在 `__init__` 注入,在 `finally` 调用 `clear_cache`)
- Create: `tests/croe/interface/test_bug_d1_result_writer_isolation.py`

- [ ] **Step 1: 写失败测试**

```python
# tests/croe/interface/test_bug_d1_result_writer_isolation.py
"""
BUG-D1 回归测试:每个 InterfaceRunner 应当持有独立的 ResultWriter 实例。
"""
import pytest
from unittest.mock import MagicMock, AsyncMock
from croe.interface.runner import InterfaceRunner
from tests.croe.interface._bug_ids import BUG_D1


@pytest.mark.unit
def test_bug_d1_two_runners_have_independent_result_writers():
    """[BUG-D1] 两个 InterfaceRunner 应当有不同的 result_writer 实例。"""
    starter = MagicMock()
    starter.send = AsyncMock()
    starter.username = "u"
    starter.userId = 1

    r1 = InterfaceRunner(starter=starter)
    r2 = InterfaceRunner(starter=starter)

    assert r1.result_writer is not r2.result_writer, (
        f"[{BUG_D1}] 两个 runner 的 result_writer 必须是不同实例,否则并发会污染缓存"
    )
    assert r1.result_writer.api_result_cache is not r2.result_writer.api_result_cache
```

- [ ] **Step 2: 跑测试,确认失败**

Run: `pytest tests/croe/interface/test_bug_d1_result_writer_isolation.py -v`
Expected: FAIL(`r1.result_writer` 报错 AttributeError,因为当前没这个属性)。

- [ ] **Step 3: 保留 `result_writer` 兼容层,但不再被业务代码引用**

修改 [croe/interface/writer/__init__.py](/Users/fanyuxuan/cyq_code/case_auto_hub/croe/interface/writer/__init__.py):

**修改前**:
```python
from .result_writer import ResultWriter
result_writer = ResultWriter()
__all__ = ['ResultWriter', 'result_writer']
```

**修改后**:
```python
from .result_writer import ResultWriter

# 保留 result_writer 别名仅为兼容老的导入,
# 业务代码应使用 InterfaceRunner.result_writer(每个实例独立)
# 不推荐新代码直接引用本模块级单例
result_writer = ResultWriter()

__all__ = ['ResultWriter', 'result_writer']
```

- [ ] **Step 4: 在 `InterfaceRunner.__init__` 中注入独立实例**

修改 [croe/interface/runner.py:32-51](/Users/fanyuxuan/cyq_code/case_auto_hub/croe/interface/runner.py):

**修改前**:
```python
class InterfaceRunner:
    """接口执行入口类"""

    __slots__ = ("starter", "variable_manager", "interface_executor", "_g_headers")

    def __init__(self, starter: Union[UIStarter, APIStarter]) -> None:
        ...
        self.starter = starter
        self.variable_manager = VariableManager()
        self._g_headers: List[InterfaceGlobalHeader] = []
        self.interface_executor = InterfaceExecutor(
            starter=self.starter,
            variable_manager=self.variable_manager,
            global_headers=self._g_headers,
        )
```

**修改后**:
```python
class InterfaceRunner:
    """接口执行入口类"""

    __slots__ = (
        "starter", "variable_manager", "interface_executor",
        "_g_headers", "result_writer",
    )

    def __init__(self, starter: Union[UIStarter, APIStarter]) -> None:
        ...
        self.starter = starter
        self.variable_manager = VariableManager()
        self._g_headers: List[InterfaceGlobalHeader] = []
        # 每个 runner 独立的 result_writer,避免并发时缓存污染 (BUG-D1)
        from croe.interface.writer import ResultWriter
        self.result_writer = ResultWriter()
        self.interface_executor = InterfaceExecutor(
            starter=self.starter,
            variable_manager=self.variable_manager,
            global_headers=self._g_headers,
        )
```

- [ ] **Step 5: 在 `run_interface_case` 的 finally 中调用 `clear_cache`**

修改 [croe/interface/runner.py:237-239](/Users/fanyuxuan/cyq_code/case_auto_hub/croe/interface/runner.py):

**修改前**:
```python
finally:
    await self.variable_manager.clear()
    await self.starter.over(case_result.id)
```

**修改后**:
```python
finally:
    await self.variable_manager.clear()
    self.result_writer.clear_cache()  # BUG-D1 修复:释放当前 runner 的缓存
    if case_result is not None:
        await self.starter.over(case_result.id)
    else:
        await self.starter.over()
```

- [ ] **Step 6: 替换 `run_interface_case` 内对模块单例 `result_writer` 的引用**

全文搜索 `runner.py` 中所有 `result_writer.` 引用(排除 `self.result_writer.`):

Run: `grep -n "result_writer\." croe/interface/runner.py | grep -v "self.result_writer"`

如果存在 `result_writer.update_case_progress(...)` / `result_writer.finalize_case_result(...)` / `result_writer.write_interface_result(...)` / `result_writer.write_step_result(...)` / `result_writer.update_step_result(...)` 等,全部改为 `self.result_writer.xxx(...)`。

打开文件,逐行修改(预计 5-8 处)。`result_writer.init_case_result` 那一行也要改。

- [ ] **Step 7: 跑 P0 测试,确认通过**

Run: `pytest tests/croe/interface/test_bug_d1_result_writer_isolation.py -v`
Expected: PASS

- [ ] **Step 8: 跑全量测试**

Run: `pytest -m unit -q`
Expected: 全 PASS。

- [ ] **Step 9: Commit**

```bash
git add croe/interface/writer/__init__.py croe/interface/writer/result_writer.py croe/interface/runner.py tests/croe/interface/test_bug_d1_result_writer_isolation.py
git commit -m "fix(runner): 每个 InterfaceRunner 持有独立 ResultWriter 实例,finally 中清理缓存 (BUG-D1)"
```

---

### Task 11 (BUG-E1): 修复 `HttpxClient` 资源泄漏 + timeout 状态共享

**问题摘要:**[httpxClient.py](/Users/fanyuxuan/cyq_code/case_auto_hub/common/httpxClient.py) `_client` 懒初始化但永不关闭;`self.client.timeout = Timeout(...)` 每次请求**修改共享 client 状态**,并发时会互相覆盖。

**Files:**
- Modify: `common/httpxClient.py`
- Create: `tests/common/test_bug_e1_httpx_client.py`

- [ ] **Step 1: 写失败测试**

```python
# tests/common/test_bug_e1_httpx_client.py
"""
BUG-E1 回归测试:HttpxClient 应当能正确关闭,且 timeout 应当按请求传参(不修改 client 状态)。
"""
import pytest
from unittest.mock import MagicMock, AsyncMock
from common.httpxClient import HttpxClient
from tests.croe.interface._bug_ids import BUG_E1


@pytest.mark.unit
@pytest.mark.asyncio
async def test_bug_e1_client_close_releases_resource():
    """[BUG-E1] close() 应当真正调用底层 client.aclose()。"""
    client = HttpxClient()
    # 触发懒初始化
    _ = client.client
    # mock aclose
    client._client.aclose = AsyncMock()

    await client.close()

    client._client.aclose.assert_awaited_once()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_bug_e1_timeout_passed_per_request_not_mutate_client():
    """[BUG-E1] __call__ 不应直接修改 self.client.timeout。"""
    client = HttpxClient()
    _ = client.client
    original_timeout = client._client.timeout

    with patch.object(client._client, "request", new=AsyncMock(return_value=MagicMock())) as mock_req:
        await client(method="GET", url="http://x", read=3, connect=2)

    # 关键断言:client.timeout 保持原样(不修改)
    assert client._client.timeout is original_timeout, (
        f"[{BUG_E1}] __call__ 不应修改 self.client.timeout"
    )
    # 关键断言:request 被以 timeout 参数调用
    call_kwargs = mock_req.call_args.kwargs
    assert "timeout" in call_kwargs, "[BUG-E1] request 应接收 timeout 形参"
```

- [ ] **Step 2: 跑测试,确认失败**

Run: `pytest tests/common/test_bug_e1_httpx_client.py -v`
Expected: FAIL(`close()` 不会调 aclose,`client.timeout` 被修改)。

- [ ] **Step 3: 修复 `httpxClient.py`**

修改 [common/httpxClient.py:50-95](/Users/fanyuxuan/cyq_code/case_auto_hub/common/httpxClient.py):

**修改前**:
```python
async def __call__(
        self,
        method: str,
        url: str,
        **kwargs
) -> Response:
    self.client.timeout = Timeout(
        None,
        connect=kwargs.pop("connect", self.default_timeout),
        read=kwargs.pop("read", self.default_timeout)
    )
    return await self._request(
        method=method.lower(),
        url=url,
        **kwargs
    )
```

**修改后**(timeout 作为参数传给 request,不修改 client 状态):
```python
async def __call__(
        self,
        method: str,
        url: str,
        **kwargs
) -> Response:
    connect = kwargs.pop("connect", self.default_timeout)
    read = kwargs.pop("read", self.default_timeout)
    # 临时 timeout,不修改 self.client.timeout (BUG-E1)
    kwargs.setdefault("timeout", Timeout(connect=connect, read=read))
    return await self._request(
        method=method.lower(),
        url=url,
        **kwargs
    )
```

并确保 `close()` 已存在(原文件已经有,只需保证 `aclose` 被调用):
```python
async def close(self) -> None:
    """关闭客户端"""
    if self._client is not None:
        await self._client.aclose()
        self._client = None
```

> 若原 `close()` 已经存在,本步无需修改;只需保证测试通过即可。

- [ ] **Step 4: 在 `InterfaceExecutor` 中支持 `aclose`**

修改 [croe/interface/executor/interface_executor.py:78](/Users/fanyuxuan/cyq_code/case_auto_hub/croe/interface/executor/interface_executor.py),在 `__init__` 末尾增加:

```python
self.http: HttpxClient = HttpxClient(logger=self.starter.send)
self.g_headers: List[InterfaceGlobalHeader] = global_headers or []
```

并在文件末尾增加 `aclose`:
```python
async def aclose(self) -> None:
    """释放底层 httpx 客户端资源。"""
    await self.http.close()
```

- [ ] **Step 5: 在 `InterfaceRunner` 增加 `aclose` 并在 `run_interface_case` finally 中调用**

修改 [croe/interface/runner.py](/Users/fanyuxuan/cyq_code/case_auto_hub/croe/interface/runner.py),在 `__init__` 之后增加方法:
```python
async def aclose(self) -> None:
    """释放 runner 持有的资源(httpx client)。"""
    await self.interface_executor.aclose()
```

在 `run_interface_case` 的 `finally` 块中:
```python
finally:
    await self.variable_manager.clear()
    self.result_writer.clear_cache()
    await self.interface_executor.aclose()  # BUG-E1 修复:释放连接
    if case_result is not None:
        await self.starter.over(case_result.id)
    else:
        await self.starter.over()
```

- [ ] **Step 6: 跑测试,确认通过**

Run: `pytest tests/common/test_bug_e1_httpx_client.py -v`
Expected: PASS

- [ ] **Step 7: 跑全量测试**

Run: `pytest -m unit -q`
Expected: 全 PASS,无回归。

- [ ] **Step 8: Commit**

```bash
git add common/httpxClient.py croe/interface/executor/interface_executor.py croe/interface/runner.py tests/common/test_bug_e1_httpx_client.py
git commit -m "fix(http): HttpxClient.request 临时传 timeout 不修改 client 状态,InterfaceRunner 释放连接 (BUG-E1)"
```

---

## 五、Phase 4 - 安全 P0(3 个任务)

### Task 12 (BUG-S1): 拦截 `getattr` 沙箱逃逸

**问题摘要:**[script_manager.py:111-115](/Users/fanyuxuan/cyq_code/case_auto_hub/croe/a_manager/script_manager.py) 的 `ast.Call` 检查只对 `ast.Name` 形式生效,`getattr(obj, "__class__")` 会绕过。

**Files:**
- Modify: `croe/a_manager/script_manager.py:80-115, 28-73`
- Create: `tests/croe/a_manager/__init__.py`
- Create: `tests/croe/a_manager/test_bug_s1_sandbox.py`

- [ ] **Step 1: 写失败测试**

```python
# tests/croe/a_manager/test_bug_s1_sandbox.py
"""
BUG-S1 回归测试:ScriptManager 应当拦截 getattr 沙箱逃逸。
"""
import pytest
from croe.a_manager.script_manager import ScriptManager, ScriptSecurityError
from tests.croe.interface._bug_ids import BUG_S1


@pytest.mark.security
@pytest.mark.unit
def test_bug_s1_getattr_call_to_dunder_blocked():
    """[BUG-S1] getattr(obj, '__class__') 应被拦截。"""
    sm = ScriptManager()
    payload = 'x = getattr("", "__class__")'
    with pytest.raises(ScriptSecurityError):
        sm.execute(payload)


@pytest.mark.security
@pytest.mark.unit
def test_bug_s1_setattr_call_blocked():
    """[BUG-S1] setattr 也应被拦截(防止修改内置对象属性)。"""
    sm = ScriptManager()
    payload = 'setattr(str, "x", 1)'
    with pytest.raises(ScriptSecurityError):
        sm.execute(payload)


@pytest.mark.security
@pytest.mark.unit
def test_bug_s1_attribute_access_to_dunder_blocked():
    """[BUG-S1] 直接 obj.__class__ 也应被拦截(原来就有,这里确保未被破坏)。"""
    sm = ScriptManager()
    payload = 'x = "".__class__'
    with pytest.raises(ScriptSecurityError):
        sm.execute(payload)
```

- [ ] **Step 2: 跑测试,确认失败**

Run: `pytest tests/croe/a_manager/test_bug_s1_sandbox.py -v`
Expected: 至少 `test_bug_s1_getattr_call_to_dunder_blocked` 和 `test_bug_s1_setattr_call_blocked` FAIL。

- [ ] **Step 3: 扩展 AST 验证,覆盖 `ast.Call` 的所有形式**

修改 [croe/a_manager/script_manager.py:84-115](/Users/fanyuxuan/cyq_code/case_auto_hub/croe/a_manager/script_manager.py):

**修改前**:
```python
def _validate_ast(node: ast.AST) -> None:
    EXCLUDED_CTX_TYPES = (ast.Store, ast.Load, ast.Del)
    for child in ast.walk(node):
        if isinstance(child, EXCLUDED_CTX_TYPES):
            continue
        if type(child) not in ALLOWED_NODE_TYPES:
            raise ScriptSecurityError(f"不允许的节点类型: {type(child).__name__}")
        if isinstance(child, ast.Attribute):
            if child.attr in DISALLOWED_ATTRS:
                raise ScriptSecurityError(f"不允许的属性访问: {child.attr}")
        if isinstance(child, ast.Call):
            if isinstance(child.func, ast.Name):
                if child.func.id in DISALLOWED_ATTRS:
                    raise ScriptSecurityError(f"不允许的函数调用: {child.func.id}")
```

**修改后**:
```python
def _validate_ast(node: ast.AST) -> None:
    EXCLUDED_CTX_TYPES = (ast.Store, ast.Load, ast.Del)
    for child in ast.walk(node):
        if isinstance(child, EXCLUDED_CTX_TYPES):
            continue
        if type(child) not in ALLOWED_NODE_TYPES:
            raise ScriptSecurityError(f"不允许的节点类型: {type(child).__name__}")

        # 拦截属性访问:任何以 __ 开头或 _ 开头或出现在 DISALLOWED_ATTRS 的属性
        if isinstance(child, ast.Attribute):
            if child.attr in DISALLOWED_ATTRS or child.attr.startswith("__"):
                raise ScriptSecurityError(f"不允许的属性访问: {child.attr}")

        # 拦截函数调用:无论函数名是 Name 还是 Attribute,
        # 都不允许调用 DISALLOWED_ATTRS 列表中的名字 (BUG-S1)
        if isinstance(child, ast.Call):
            if isinstance(child.func, ast.Name):
                if child.func.id in DISALLOWED_ATTRS:
                    raise ScriptSecurityError(f"不允许的函数调用: {child.func.id}")
            elif isinstance(child.func, ast.Attribute):
                # 链式调用,如 os.system, getattr(obj, ...).xxx
                if child.func.attr in DISALLOWED_ATTRS:
                    raise ScriptSecurityError(f"不允许的链式调用: {child.func.attr}")
```

- [ ] **Step 4: 跑测试,确认通过**

Run: `pytest tests/croe/a_manager/test_bug_s1_sandbox.py -v`
Expected: PASS

- [ ] **Step 5: 跑老的安全测试,确保未误伤合法代码**

Run: `pytest tests/croe/a_manager/ -v -k "sandbox or script or security"`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add croe/a_manager/script_manager.py tests/croe/a_manager/test_bug_s1_sandbox.py tests/croe/a_manager/__init__.py
git commit -m "fix(security): ScriptManager 拦截 getattr/setattr/链式调用等沙箱逃逸 (BUG-S1)"
```

---

### Task 13 (BUG-S2): 移除 `import` 节点

**问题摘要:**[script_manager.py:42-43](/Users/fanyuxuan/cyq_code/case_auto_hub/croe/a_manager/script_manager.py) `ALLOWED_NODE_TYPES` 包含 `ast.Import` / `ast.ImportFrom`,允许任意 `import`,虽然 `exec` 时没有 `os`/`subprocess` 这些内置,但攻击者可通过 `getattr(builtins, '__import__')('os')` 绕过(虽然 `getattr` 已被 Task 12 拦截,但更彻底是禁 import)。

**Files:**
- Modify: `croe/a_manager/script_manager.py:28-45`
- Create: `tests/croe/a_manager/test_bug_s2_no_import.py`

- [ ] **Step 1: 写失败测试**

```python
# tests/croe/a_manager/test_bug_s2_no_import.py
"""
BUG-S2 回归测试:ScriptManager 不应允许 import 节点。
"""
import pytest
from croe.a_manager.script_manager import ScriptManager, ScriptSecurityError
from tests.croe.interface._bug_ids import BUG_S2


@pytest.mark.security
@pytest.mark.unit
def test_bug_s2_import_blocked():
    """[BUG-S2] import os 应被拦截。"""
    sm = ScriptManager()
    with pytest.raises(ScriptSecurityError):
        sm.execute("import os")


@pytest.mark.security
@pytest.mark.unit
def test_bug_s2_from_import_blocked():
    """[BUG-S2] from os import system 应被拦截。"""
    sm = ScriptManager()
    with pytest.raises(ScriptSecurityError):
        sm.execute("from os import system")
```

- [ ] **Step 2: 跑测试,确认失败**

Run: `pytest tests/croe/a_manager/test_bug_s2_no_import.py -v`
Expected: FAIL(`import os` 成功执行,没抛异常)。

- [ ] **Step 3: 移除 `Import` / `ImportFrom`**

修改 [croe/a_manager/script_manager.py:28-45](/Users/fanyuxuan/cyq_code/case_auto_hub/croe/a_manager/script_manager.py):

**修改前**:
```python
ALLOWED_NODE_TYPES = {
    ast.Module, ast.FunctionDef, ast.AsyncFunctionDef,
    ast.Expr, ast.Name, ast.Constant, ast.Num, ast.Str,
    ast.List, ast.Dict, ast.Tuple, ast.Set,
    ast.BinOp, ast.UnaryOp, ast.Compare,
    ast.BoolOp, ast.And, ast.Or, ast.Not,
    ast.Add, ast.Sub, ast.Mult, ast.Div, ast.FloorDiv, ast.Mod, ast.Pow,
    ast.Eq, ast.NotEq, ast.Lt, ast.LtE, ast.Gt, ast.GtE,
    ast.In, ast.NotIn, ast.Is, ast.IsNot,
    ast.If, ast.For, ast.While,
    ast.Break, ast.Continue, ast.Pass,
    ast.Return, ast.Assign, ast.AugAssign,
    ast.AnnAssign, ast.Subscript, ast.Attribute,
    ast.Call, ast.keyword,
    ast.Import, ast.ImportFrom, ast.alias,    # ← 删除
    ast.Starred, ast.ListComp, ast.DictComp, ast.SetComp, ast.GeneratorExp,
}
```

**修改后**:
```python
ALLOWED_NODE_TYPES = {
    ast.Module, ast.FunctionDef, ast.AsyncFunctionDef,
    ast.Expr, ast.Name, ast.Constant, ast.Num, ast.Str,
    ast.List, ast.Dict, ast.Tuple, ast.Set,
    ast.BinOp, ast.UnaryOp, ast.Compare,
    ast.BoolOp, ast.And, ast.Or, ast.Not,
    ast.Add, ast.Sub, ast.Mult, ast.Div, ast.FloorDiv, ast.Mod, ast.Pow,
    ast.Eq, ast.NotEq, ast.Lt, ast.LtE, ast.Gt, ast.GtE,
    ast.In, ast.NotIn, ast.Is, ast.IsNot,
    ast.If, ast.For, ast.While,
    ast.Break, ast.Continue, ast.Pass,
    ast.Return, ast.Assign, ast.AugAssign,
    ast.AnnAssign, ast.Subscript, ast.Attribute,
    ast.Call, ast.keyword,
    # BUG-S2: 禁止 import,杜绝通过内置 import 加载 os/subprocess 等
    # ast.Import, ast.ImportFrom, ast.alias  ← 已删除
    ast.Starred, ast.ListComp, ast.DictComp, ast.SetComp, ast.GeneratorExp,
}
```

- [ ] **Step 4: 跑测试,确认通过**

Run: `pytest tests/croe/a_manager/test_bug_s2_no_import.py -v`
Expected: PASS

- [ ] **Step 5: 跑全量安全相关测试,确保无回归**

Run: `pytest tests/croe/a_manager/ -v`
Expected: 全 PASS。

- [ ] **Step 6: Commit**

```bash
git add croe/a_manager/script_manager.py tests/croe/a_manager/test_bug_s2_no_import.py
git commit -m "fix(security): ScriptManager 禁用 import 节点,杜绝 import 任意模块 (BUG-S2)"
```

---

### Task 14 (BUG-S3): 实施 `SCRIPT_TIMEOUT` 强制超时

**问题摘要:**[script_manager.py:26](/Users/fanyuxuan/cyq_code/case_auto_hub/croe/a_manager/script_manager.py) `SCRIPT_TIMEOUT = 5` 定义了但从未生效;`exec()` 同步执行死循环会永久阻塞 worker。

**Files:**
- Modify: `croe/a_manager/script_manager.py:141-181`
- Create: `tests/croe/a_manager/test_bug_s3_timeout.py`

- [ ] **Step 1: 写失败测试**

```python
# tests/croe/a_manager/test_bug_s3_timeout.py
"""
BUG-S3 回归测试:死循环脚本应在 SCRIPT_TIMEOUT 秒内被终止。
"""
import time
import pytest
from croe.a_manager.script_manager import ScriptManager
from tests.croe.interface._bug_ids import BUG_S3


@pytest.mark.security
@pytest.mark.unit
def test_bug_s3_infinite_loop_terminates_within_timeout():
    """[BUG-S3] while True: pass 应当在 ~SCRIPT_TIMEOUT 秒内抛错或终止。"""
    sm = ScriptManager()
    start = time.time()
    with pytest.raises(Exception):  # TimeoutError 或 ScriptSecurityError
        sm.execute("while True: pass")
    elapsed = time.time() - start
    # 给 1 秒 buffer,因为是子进程/signal 终止会有延迟
    assert elapsed < (sm.SCRIPT_TIMEOUT + 1), (
        f"[{BUG_S3}] 死循环应在 SCRIPT_TIMEOUT ({sm.SCRIPT_TIMEOUT}s) 内终止,实际 {elapsed:.2f}s"
    )
```

- [ ] **Step 2: 跑测试,确认失败**

Run: `pytest tests/croe/a_manager/test_bug_s3_timeout.py -v`
Expected: **测试会卡住 60+ 秒然后因为超时被 pytest 杀**,或者在 SCRIPT_TIMEOUT 测试配置下 timeout。手动 Ctrl+C 中断后看到 hang。

- [ ] **Step 3: 用 `concurrent.futures` + `Process` 实现真超时**

修改 [croe/a_manager/script_manager.py:141-181](/Users/fanyuxuan/cyq_code/case_auto_hub/croe/a_manager/script_manager.py):

**修改前**:
```python
def execute(self, script_content: str) -> Dict[str, Any]:
    ...
    try:
        exec(compile(tree, '<string>', 'exec'), exec_globals, local_vars)
    except Exception as e:
        log.exception(f"执行脚本失败: {e}")
        raise
    return self._collect_results(local_vars)
```

**修改后**(在子进程中跑,通过 `multiprocessing` 隔离):
```python
import multiprocessing
import pickle

def _exec_in_subprocess(script_bytes, exec_globals_bytes, timeout, q):
    """子进程入口:执行脚本并把结果放进队列。"""
    try:
        import ast
        tree = ast.parse(script_bytes)
        exec_globals = pickle.loads(exec_globals_bytes)
        local_vars = {}
        exec(compile(tree, '<string>', 'exec'), exec_globals, local_vars)
        q.put(("ok", local_vars))
    except Exception as e:
        q.put(("err", e))

class ScriptManager:
    ...
    def execute(self, script_content: str) -> Dict[str, Any]:
        ...
        # 1. AST 安全检查
        tree = ast.parse(script_content)
        _validate_ast(tree)

        # 2. 在子进程跑脚本,真超时
        q = multiprocessing.Queue()
        proc = multiprocessing.Process(
            target=_exec_in_subprocess,
            args=(
                script_content,
                pickle.dumps(exec_globals, protocol=pickle.HIGHEST_PROTOCOL),
                self.SCRIPT_TIMEOUT,
                q,
            ),
        )
        proc.start()
        proc.join(timeout=self.SCRIPT_TIMEOUT)

        if proc.is_alive():
            proc.terminate()
            proc.join(timeout=2)
            if proc.is_alive():
                proc.kill()
            raise ScriptSecurityError(f"脚本执行超时 ({self.SCRIPT_TIMEOUT}s)")

        if proc.exitcode != 0:
            raise ScriptSecurityError(f"脚本执行异常,exitcode={proc.exitcode}")

        if q.empty():
            raise ScriptSecurityError("脚本未产生结果")

        status, payload = q.get()
        if status == "err":
            raise payload
        local_vars = payload
        return self._collect_results(local_vars)
```

> 注意:`multiprocessing` 在 Windows 上需要 `if __name__ == "__main__":` 保护;在 Linux/macOS 上 spawn 默认即可。如果项目用 gunicorn,Process 默认 fork 即可。

- [ ] **Step 4: 跑测试,确认通过**

Run: `pytest tests/croe/a_manager/test_bug_s3_timeout.py -v`
Expected: PASS(应在 ~5 秒内完成,不是 60+ 秒)。

- [ ] **Step 5: 跑全量安全测试,确保其他沙箱测试仍 PASS**

Run: `pytest tests/croe/a_manager/ -v`
Expected: 全 PASS。

- [ ] **Step 6: 跑全量测试套件,确保无回归**

Run: `pytest -m unit -q`
Expected: 全 PASS。

- [ ] **Step 7: Commit**

```bash
git add croe/a_manager/script_manager.py tests/croe/a_manager/test_bug_s3_timeout.py
git commit -m "fix(security): ScriptManager 用 multiprocessing 强制 SCRIPT_TIMEOUT,死循环不再阻塞 worker (BUG-S3)"
```

---

## 六、Phase 5 - 变量系统 P0(1 个任务)

### Task 15 (BUG-V1): 修复 `__find_g_vars` name mangling

**问题摘要:**[variableTrans.py:160](/Users/fanyuxuan/cyq_code/case_auto_hub/utils/variableTrans.py) `__find_g_vars` 双下划线触发 name mangling,继承/重写/外部引用会爆。

**Files:**
- Modify: `utils/variableTrans.py:10, 96, 106, 160`
- Create: `tests/utils/test_bug_v1_name_mangling.py`

- [ ] **Step 1: 写失败测试**

```python
# tests/utils/test_bug_v1_name_mangling.py
"""
BUG-V1 回归测试:VariableTrans 子类应能正确调用 _find_g_vars,不应被 name mangling 影响。
"""
import pytest
from utils.variableTrans import VariableTrans
from tests.croe.interface._bug_ids import BUG_V1


@pytest.mark.unit
@pytest.mark.asyncio
async def test_bug_v1_subclass_can_override_find_g_vars():
    """[BUG-V1] 子类应能继承并重写 _find_g_vars 而不爆。"""
    class MyVT(VariableTrans):
        async def _find_g_vars(self, name):  # ← 如果原方法名是 __find_g_vars,这里重写不会生效
            return "mocked"

    vt = MyVT()
    # 调用 _resolve_vars(走 _find_g_vars 路径)
    result = await vt.trans("{{$g_xxx}}")
    # $g_ 前缀会走 _find_g_vars
    assert result == "mocked", (
        f"[{BUG_V1}] 子类 _find_g_vars 应被调到,实际 {result!r}"
    )
```

- [ ] **Step 2: 跑测试,确认失败**

Run: `pytest tests/utils/test_bug_v1_name_mangling.py -v`
Expected: FAIL(子类的 `_find_g_vars` 不会被原方法调用,因为原方法名是 `__find_g_vars`,name mangled 为 `_VariableTrans__find_g_vars`)。

- [ ] **Step 3: 重命名为单下划线**

修改 [utils/variableTrans.py:160](/Users/fanyuxuan/cyq_code/case_auto_hub/utils/variableTrans.py):

**修改前**:
```python
@staticmethod
async def __find_g_vars(script: str) -> Any:
    log.info(f"g var = {script}")
    script = script.split("g_")[-1]
    g_vars = await GlobalVariableMapper.fetch_by_key(script)
    if g_vars:
        return g_vars.value
```

**修改后**:
```python
@staticmethod
async def _find_g_vars(script: str) -> Any:
    """根据变量名从全局变量表中查值。"""
    log.info(f"g var = {script}")
    script = script.split("g_")[-1]
    g_vars = await GlobalVariableMapper.fetch_by_key(script)
    if g_vars:
        return g_vars.value
```

修改 [utils/variableTrans.py:106](/Users/fanyuxuan/cyq_code/case_auto_hub/utils/variableTrans.py):

**修改前**:
```python
return await self.__find_g_vars(var_name[1:])
```

**修改后**:
```python
return await self._find_g_vars(var_name[1:])
```

- [ ] **Step 4: 跑测试,确认通过**

Run: `pytest tests/utils/test_bug_v1_name_mangling.py -v`
Expected: PASS

- [ ] **Step 5: 全项目 grep 还有没有 `__find_g_vars` 的引用**

Run: `grep -rn "__find_g_vars" app/ croe/ utils/ --include="*.py"`
Expected: 0 结果。

- [ ] **Step 6: 跑全量测试**

Run: `pytest -m unit -q`
Expected: 全 PASS。

- [ ] **Step 7: Commit**

```bash
git add utils/variableTrans.py tests/utils/test_bug_v1_name_mangling.py
git commit -m "fix(var): VariableTrans.__find_g_vars 改名为 _find_g_vars,避免 name mangling (BUG-V1)"
```

---

## 七、Phase 6 - 集成验证

### Task 16: 跑全量回归 + 写综合集成测试

**Files:**
- Create: `tests/integration/test_run_interface_case_smoke.py`
- Modify: `pytest.ini`(加 integration 路径)

- [ ] **Step 1: 创建 `tests/integration/__init__.py`**

```python
"""集成测试包。需要真实 MySQL/Redis,默认不在 unit 模式跑。"""
```

- [ ] **Step 2: 写 smoke 测试骨架**

```python
# tests/integration/test_run_interface_case_smoke.py
"""
烟雾测试:跑通 run_interface_case 主流程(不接真实业务,只验证骨架)。
需要 integration marker。
"""
import pytest
from unittest.mock import MagicMock, AsyncMock, patch


@pytest.mark.integration
@pytest.mark.asyncio
async def test_smoke_run_interface_case_happy_path_with_mocks():
    """烟雾测试:用 mock 跑通 run_interface_case 完整流程。"""
    # 此测试的 mock 数量多,本文件只作为骨架,具体 mock 在每个 BUG 测试里已经覆盖
    # 这里主要验证:从入参到 (False/True, case_result) 完整 return,不抛异常
    from croe.interface.runner import InterfaceRunner
    starter = MagicMock()
    starter.send = AsyncMock()
    starter.over = AsyncMock()
    starter.username = "u"
    starter.userId = 1
    starter.uid = "u1"
    starter.logs = []

    runner = InterfaceRunner(starter=starter)

    # 期望:case 不存在时,返回 (False, None) 而非 None
    with patch(
        "app.mapper.interfaceApi.interfaceCaseMapper.InterfaceCaseMapper.get_by_id",
        new=AsyncMock(return_value=None),
    ):
        result = await runner.run_interface_case(
            interface_case_id=999,
            env=1,
            error_stop=False,
        )

    assert result == (False, None) or result == (False, None,)  # 容忍 tuple 形态
```

- [ ] **Step 3: 跑全量 unit 测试**

Run: `pytest -m unit -q --tb=short`
Expected: 全部 P0 测试 + 已有测试 PASS,失败 0。

- [ ] **Step 4: 跑全量测试**

Run: `pytest -q --tb=short`
Expected: unit 全部 PASS,integration 全部 skip(因为没真实 DB)。

- [ ] **Step 5: 统计覆盖率**

Run: `pytest -m unit --cov=croe/interface/runner.py --cov=croe/interface/executor --cov=croe/a_manager/script_manager.py --cov=common/httpxClient.py --cov=app/model --cov-report=term-missing`
Expected: 至少 `croe/interface/runner.py` 覆盖率 ≥ 50%。

- [ ] **Step 6: 写完成报告**

把覆盖率数字、跑通测试数、修复 BUG 列表,更新到:
- `docs/review/P0_FIX_REPORT.md`(新建)

并向 V2 报告添加"已修复 BUG 清单"。

- [ ] **Step 7: Commit**

```bash
git add tests/integration/ pytest.ini docs/review/P0_FIX_REPORT.md
git commit -m "test: 添加烟雾测试,完成 P0 修复集成验证"
```

---

## 八、整体验证 checklist

修复全部完成后,逐项打勾:

- [ ] V2 报告中 P0 级别 11 个 BUG 全部有对应 commit
- [ ] 每个 BUG 都有 1 个失败 → 修复 → 通过的 commit
- [ ] `pytest -m unit` 全部 PASS
- [ ] `pytest -m unit --cov=croe/interface/runner.py` 覆盖率 ≥ 50%
- [ ] 全项目 grep:`interfaceLog`、`self.global_headers` (除 `_g_headers`)、`__find_g_vars`、`result_writer` 模块级单例引用 0 结果
- [ ] 沙箱测试:`getattr("", "__class__")` / `import os` / `while True` 都被拦截
- [ ] 文档:`docs/review/P0_FIX_REPORT.md` 已生成

---

## 九、回滚预案

如果某个 PR 引入回归:

1. **单 BUG 回滚**:`git revert <commit-hash>`,只回滚该 BUG,不影响其他修复。
2. **沙箱回退(若 S1/S2/S3 误伤合法脚本)**:
   - 临时方案:在 `Config` 加 `SCRIPT_SANDBOX_ENABLED = False`,`_validate_ast` 跳过。
   - 长期方案:基于用户反馈调整白名单。
3. **字段长度回滚(M2/M11)**:如果老数据丢失,执行 SQL:
   ```sql
   -- 回滚 M2
   ALTER TABLE interface_case_result MODIFY interface_case_name VARCHAR(20);
   -- 回滚 M11
   ALTER TABLE interface_case_result MODIFY interface_case_uid VARCHAR(20);
   ALTER TABLE interface_result MODIFY interface_uid VARCHAR(20);
   ```
   但因为只是"扩大",**没有数据丢失风险**,无需回滚。

---

## 十、相关文件索引

修复涉及的文件:

| Phase | 文件 |
| --- | --- |
| 0 | `pytest.ini`(新建),`tests/conftest.py`(新建),`tests/croe/...` |
| 1 | `app/model/interfaceAPIModel/contents/interfaceCaseContentsModel.py`,`app/model/interfaceAPIModel/interfaceResultModel.py`,`app/model/basic.py` |
| 2 | `croe/interface/runner.py` |
| 3 | `croe/interface/writer/__init__.py`,`croe/interface/writer/result_writer.py`,`common/httpxClient.py`,`croe/interface/executor/interface_executor.py` |
| 4 | `croe/a_manager/script_manager.py` |
| 5 | `utils/variableTrans.py` |

涉及但**未修改**的(仅观察):
- `croe/interface/executor/step_content/*.py`
- `croe/interface/builder/*.py`
- `app/mapper/interfaceApi/*`(除了 writer)

---

## 十一、时间线估算

| 任务 | 预计工时 | 累计 |
| --- | --- | --- |
| Task 1-2(基础设施) | 1h | 1h |
| Task 3-6(模型层 P0) | 4h | 5h |
| Task 7-9(流程层 P0) | 3h | 8h |
| Task 10-11(资源管理) | 4h | 12h |
| Task 12-14(安全) | 6h | 18h |
| Task 15(变量) | 1h | 19h |
| Task 16(集成验证) | 2h | 21h |

**合计:约 21 小时 ≈ 3 个工作日**(单人 8h/天)。

---

## 十二、后续计划(非本计划范围)

完成 P0 后,下一个计划应当处理:

### P1 改进(预计 4 周,见 V2 报告 BUG-F3/F4/F5/M4-M8/D2-D6/E3-E9/V2/V4/V6/S4/OBS-1/OBS-2/OBS-3/PERF-1/PERF-2)

大致按以下顺序:
1. **观测性**:加 trace_id,结构化日志(OBS-1, OBS-2)
2. **执行器健壮性**:`total_num` 维护(E8, E9),URL builder 统一(E4)
3. **Mapper 性能**:`with_polymorphic` 改按需(M6),`bulk_insert` 显式事务(D4)
4. **变量系统硬化**:`hub_api_request` 改异步或删(V4),`get_var` 未定义返回显式错误(V6)
5. **安全加固**:SSRF 白名单(S4)
6. **测试覆盖**:补 runner / executor / script_manager 单测到 80%

### P2 清理(预计 2 月+)

- 字段命名统一化(移除 camelCase / snake_case 混用)
- 重写 8 个 step 子策略,统一行为
- 全面 JTI 字段 / 状态机 / 日志协议标准化
- 性能优化:`HttpxClient` 改连接池配置,`Mapper.bulk_insert_models` 改 `COPY`

---

## 十三、Self-Review(交付前自查)

按 writing-plans 技能要求做最后一次自查:

### 13.1 Spec 覆盖度

V2 报告 P0 级别 BUG 11 个:
- [x] BUG-M1 — Task 3
- [x] BUG-M2 — Task 4
- [x] BUG-M3 — Task 5
- [x] BUG-F1 — Task 7
- [x] BUG-F2 — Task 8
- [x] BUG-D1 — Task 10
- [x] BUG-E1 — Task 11
- [x] BUG-S1 — Task 12
- [x] BUG-S2 — Task 13
- [x] BUG-S3 — Task 14
- [x] BUG-V1 — Task 15
- [x] BUG-M11 — Task 6(同 Phase 1,顺手修了 P0 边界的 M11)

**100% 覆盖**。

### 13.2 占位符扫描

`grep -n "TODO\|TBD\|fill in\|implement later\|appropriate\|similar to"` 计划文档:
- 任务级别:0 个占位符。
- 步骤级别:0 个占位符;所有"写代码"步骤都有具体代码块;所有"跑测试"步骤都有具体命令和预期输出。
- 第七章"整体验证 checklist"是显式的"完成时打勾",不是占位符。

### 13.3 类型 / API 一致性

- `InterfaceRunner.result_writer` 在 Task 10 Step 4 引入,所有后续任务引用一致。
- `InterfaceRunner._g_headers` 在 Task 9 引入,Task 10 引用 `self._g_headers` 一致。
- `aclose()` 在 Task 11 Step 4-5 引入 `InterfaceExecutor.aclose` / `InterfaceRunner` 调用,签名一致。
- `self.interface_executor.aclose()` 在 Task 11 Step 5 finally 中调用,与 Step 4 引入的方法签名一致。
- 测试 fixture `mock_starter` 在 Task 1 引入,后续所有测试使用一致(没有重新定义)。

### 13.4 依赖与时序

- Task 3(M1) → Task 4(M2) → Task 5(M3) → Task 6(M11):线性,模型层不互相影响,但顺序保留以便 review 时按章看。
- Task 7(F1) 依赖 Task 6(M11) 在前:**实际上 F1 不依赖 M11**,但放 Phase 2 而不是 Phase 1 是因为 Phase 1 改完模型才能做后续测试。本计划里 F1 的测试独立,可以并入 Phase 1。
- Task 10(D1) 依赖 `result_writer` 的存在(已有),不依赖其他任务。
- Task 11(E1) 独立。
- Task 12/13/14(S1/S2/S3)线性,S3 强依赖 S1+S2 提供的"沙箱更严"基础。
- Task 15(V1) 独立。

整体顺序合理,可以并行开发(见 0.4)。

### 13.5 风险缓解

- 沙箱误伤:已写入 0.5 风险登记,提供 safety hatch 思路。
- 字段长度迁移:已在 Task 4 Step 7 提示生成 alembic migration。
- HttpxClient 并发:Task 11 已用临时 timeout 传参解决。
- M3 改动可能影响其他模块:Task 5 Step 5 要求 grep + 手工 review。

---

## 十四、执行方式选择

本计划已完成,共 16 个任务,预计 21 小时。

**两种执行方式:**

1. **Subagent-Driven(推荐)** — 我用 subagent-driven-development 技能,每个 Task 派一个新 subagent 去做,Task 之间我做两阶段 review。这种方式:
   - 每个 subagent 上下文干净,不容易遗漏细节。
   - Task 1 出错不影响 Task 2 的 subagent。
   - 总耗时约 25-30 小时(含 review)。

2. **Inline Execution** — 我在当前会话用 executing-plans 技能,按 Task 顺序批量执行,每 3-4 个 Task 一次 checkpoint。这种方式:
   - 上下文连续,跨 Task 关联容易发现。
   - 但当前会话 token 消耗大,可能中途需要 compact。
   - 总耗时约 21 小时。

**你想用哪种方式?**
