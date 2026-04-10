# Case Result 模型使用示例

## 数据结构概览

```
TaskStepResult (任务结果)
└── CaseStepResult (用例结果)
    ├── InterfaceResult (API执行详情，通过 target_result_id 关联)
    └── BaseStepResult (步骤结果，多态子类)
        ├── APIStepResult (content_type=1)
        ├── GroupStepResult (content_type=2)
        ├── ConditionStepResult (content_type=3)
        ├── LoopStepResult (content_type=4)
        ├── ScriptStepResult (content_type=5)
        ├── DBStepResult (content_type=6)
        ├── WaitStepResult (content_type=7)
        ├── AssertStepResult (content_type=8)
        └── WhileStepResult (content_type=9)
```

---

## 1. 写入示例

### 1.1 基本 CaseResult + 多个 StepResults

```python
from app.model import async_session
from app.model.interfaceAPIModel import (
    CaseStepResult,
    APIStepResult,
    GroupStepResult,
    ConditionStepResult,
    LoopStepResult,
    InterfaceResult,
)

async def create_case_result_with_steps():
    async with async_session() as session:
        # 1. 创建 CaseStepResult
        case_result = CaseStepResult(
            case_id=1,
            case_title="用户登录流程",
            case_desc="测试用户名密码登录",
            case_level="P0",
            task_result_id=1,
            total_steps=5,
            success_steps=0,
            fail_steps=0,
            status="RUNNING",
            starter_id=100,
            starter_name="test_user",
            env_id=1,
            env_name="测试环境",
        )
        session.add(case_result)
        await session.flush()  # 获取 case_result.id

        # 2. 创建 APIStepResult (API类型)
        api_step = APIStepResult(
            case_result_id=case_result.id,
            content_type=1,  # API 类型
            content_step=1,
            content_name="获取验证码",
            content_result=True,
            starter_id=100,
            starter_name="test_user",
            use_time="120ms",
        )
        session.add(api_step)
        await session.flush()

        # 3. 创建 InterfaceResult (API执行详情)
        interface_result = InterfaceResult(
            api_id=10,
            api_name="获取验证码API",
            api_uid="API001",
            request_method="POST",
            request_url="https://api.example.com/captcha",
            request_headers={"Content-Type": "application/json"},
            request_body='{"mobile": "13800138000"}',
            response_status=200,
            response_body='{"code": 0, "data": {"captcha_id": "xxx"}}',
            response_time=120.5,
            extracts={"captcha_id": "xxx123"},
            asserts=[{"type": "equals", "expected": 0, "actual": 0}],
            result="SUCCESS",
            case_result_id=case_result.id,
            starter_id=100,
            starter_name="test_user",
        )
        session.add(interface_result)
        await session.flush()

        # 4. 将 InterfaceResult 关联到 APIStepResult
        api_step.target_result_id = interface_result.id

        # 5. 创建 GroupStepResult (步骤组)
        group_step = GroupStepResult(
            case_result_id=case_result.id,
            content_type=2,  # GROUP 类型
            content_step=2,
            content_name="登录步骤组",
            group_name="用户登录",
            content_result=True,
            starter_id=100,
            starter_name="test_user",
        )
        session.add(group_step)
        await session.flush()

        # 6. 在 Group 下创建子步骤 (通过 parent_result_id)
        # 子步骤1: 获取token
        child_step1 = APIStepResult(
            case_result_id=case_result.id,
            content_type=1,
            content_step=1,
            content_name="获取Token",
            parent_result_id=group_step.id,  # 关联父步骤
            content_result=True,
        )
        session.add(child_step1)

        # 子步骤2: 验证token
        child_step2 = APIStepResult(
            case_result_id=case_result.id,
            content_type=1,
            content_step=2,
            content_name="验证Token",
            parent_result_id=group_step.id,  # 关联父步骤
            content_result=True,
        )
        session.add(child_step2)

        # 7. 创建 ConditionStepResult (条件)
        condition_step = ConditionStepResult(
            case_result_id=case_result.id,
            content_type=3,  # CONDITION 类型
            content_step=3,
            content_name="判断用户状态",
            condition_expression="user.status == 'active'",
            condition_result=True,
            content_result=True,
        )
        session.add(condition_step)

        # 8. 创建 LoopStepResult (循环)
        loop_step = LoopStepResult(
            case_result_id=case_result.id,
            content_type=4,  # LOOP 类型
            content_step=4,
            content_name="重试步骤",
            loop_count=3,
            loop_max=5,
            loop_condition="retry < 5",
            content_result=True,
        )
        session.add(loop_step)

        await session.commit()
        return case_result
```

---

### 1.2 写入不同类型的 StepResult

```python
from app.model import async_session
from app.model.interfaceAPIModel import (
    ScriptStepResult,
    DBStepResult,
    WaitStepResult,
    AssertStepResult,
    WhileStepResult,
)

async def create_various_step_results(case_result_id: int):
    async with async_session() as session:

        # ScriptStepResult (脚本)
        script_step = ScriptStepResult(
            case_result_id=case_result_id,
            content_type=5,
            content_step=1,
            content_name="执行Python脚本",
            script_type="python",
            script_content="print('hello')",
            script_output="hello\nworld",
            script_extracts={"key": "value"},
            content_result=True,
            starter_id=100,
        )
        session.add(script_step)

        # DBStepResult (数据库)
        db_step = DBStepResult(
            case_result_id=case_result_id,
            content_type=6,
            content_step=2,
            content_name="查询用户信息",
            db_source="mysql_primary",
            sql_type="SELECT",
            sql_content="SELECT * FROM users WHERE id = ?",
            sql_params={"id": 1},
            sql_result=[{"id": 1, "name": "张三", "email": "zhangsan@example.com"}],
            sql_affected_rows=1,
            content_result=True,
        )
        session.add(db_step)

        # WaitStepResult (等待)
        wait_step = WaitStepResult(
            case_result_id=case_result_id,
            content_type=7,
            content_step=3,
            content_name="等待接口响应",
            wait_type="time",
            wait_duration=2.5,
            content_result=True,
        )
        session.add(wait_step)

        # AssertStepResult (断言)
        assert_step = AssertStepResult(
            case_result_id=case_result_id,
            content_type=8,
            content_step=4,
            content_name="验证响应状态码",
            assert_type="equals",
            assert_expression="response.status == 200",
            assert_data={"expected": 200, "actual": 200},
            assert_passed=True,
            content_result=True,
        )
        session.add(assert_step)

        # WhileStepResult (While循环)
        while_step = WhileStepResult(
            case_result_id=case_result_id,
            content_type=9,
            content_step=5,
            content_name="循环获取数据",
            while_condition="has_more_data == true",
            while_result=True,
            loop_count=3,
            loop_max=10,
            content_result=True,
        )
        session.add(while_step)

        await session.commit()
```

---

## 2. 查询示例

### 2.1 通过 Case ID 查询 CaseResult 及所有步骤

```python
from app.model import async_session
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from app.model.interfaceAPIModel import CaseStepResult, BaseStepResult

async def get_case_result_with_steps(case_result_id: int):
    async with async_session() as session:
        stmt = (
            select(CaseStepResult)
            .options(selectinload(CaseStepResult.step_results))
            .where(CaseStepResult.id == case_result_id)
        )
        result = await session.execute(stmt)
        case_result = result.scalar_one_or_none()

        if case_result:
            print(f"Case Result: {case_result.case_title}")
            print(f"Total Steps: {case_result.total_steps}")
            print(f"Success: {case_result.success_steps}, Fail: {case_result.fail_steps}")
            print("\n步骤列表:")
            for step in case_result.step_results:
                print(f"  - [{step.content_type}] {step.content_name}: {step.content_result}")

        return case_result
```

### 2.2 查询 CaseResult + InterfaceResult (API详情)

```python
from app.model import async_session
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from app.model.interfaceAPIModel import CaseStepResult, InterfaceResult

async def get_case_result_with_api_details(case_result_id: int):
    async with async_session() as session:
        stmt = (
            select(CaseStepResult)
            .options(selectinload(CaseStepResult.interface_results))
            .where(CaseStepResult.id == case_result_id)
        )
        result = await session.execute(stmt)
        case_result = result.scalar_one_or_none()

        if case_result:
            print(f"Case Result: {case_result.case_title}")
            print("\nAPI 执行详情:")
            for ir in case_result.interface_results:
                print(f"  - {ir.api_name}: {ir.request_method} {ir.request_url}")
                print(f"    Status: {ir.response_status}, Time: {ir.response_time}ms")
                print(f"    Extracts: {ir.extracts}")
                print(f"    Asserts: {ir.asserts}")

        return case_result
```

### 2.3 查询 GROUP 下的子步骤

```python
from app.model import async_session
from sqlalchemy import select
from app.model.interfaceAPIModel import GroupStepResult, APIStepResult

async def get_group_children(group_result_id: int):
    async with async_session() as session:
        # 查询 GROUP 步骤本身
        stmt = select(GroupStepResult).where(GroupStepResult.id == group_result_id)
        result = await session.execute(stmt)
        group_step = result.scalar_one_or_none()

        if group_step:
            print(f"Group: {group_step.content_name}")

            # 查询该 GROUP 下的所有子步骤
            children_stmt = select(APIStepResult).where(
                APIStepResult.parent_result_id == group_result_id
            )
            children_result = await session.execute(children_stmt)
            children = children_result.scalars().all()

            print(f"子步骤数量: {len(children)}")
            for child in children:
                print(f"  - {child.content_name}: {child.content_result}")

        return group_step
```

### 2.4 查询完整的层级结构

```python
from app.model import async_session
from sqlalchemy import select
from app.model.interfaceAPIModel import CaseStepResult

async def get_full_hierarchy(case_result_id: int):
    async with async_session() as session:
        stmt = select(CaseStepResult).where(CaseStepResult.id == case_result_id)
        result = await session.execute(stmt)
        case_result = result.scalar_one_or_none()

        if not case_result:
            return None

        # 手动构建层级结构
        hierarchy = {
            "id": case_result.id,
            "case_title": case_result.case_title,
            "status": case_result.status,
            "result": case_result.result,
            "steps": []
        }

        # 查询所有顶层步骤 (parent_result_id is null)
        top_level_stmt = select(BaseStepResult).where(
            BaseStepResult.case_result_id == case_result_id,
            BaseStepResult.parent_result_id.is_(None)
        )
        top_level_result = await session.execute(top_level_stmt)
        top_steps = top_level_result.scalars().all()

        for step in top_steps:
            step_dict = {
                "id": step.id,
                "content_type": step.content_type,
                "content_name": step.content_name,
                "content_result": step.content_result,
                "children": []
            }

            # 如果是容器类型(GROUP/CONDITION/LOOP),递归查询子步骤
            if step.content_type in [2, 3, 4, 9]:  # GROUP/CONDITION/LOOP/WHILE
                children_stmt = select(BaseStepResult).where(
                    BaseStepResult.parent_result_id == step.id
                )
                children_result = await session.execute(children_stmt)
                children = children_result.scalars().all()

                for child in children:
                    step_dict["children"].append({
                        "id": child.id,
                        "content_type": child.content_type,
                        "content_name": child.content_name,
                        "content_result": child.content_result,
                        "target_result_id": getattr(child, 'target_result_id', None)
                    })

            hierarchy["steps"].append(step_dict)

        return hierarchy
```

### 2.5 查询 APIStepResult 及其关联的 InterfaceResult

```python
from app.model import async_session
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from app.model.interfaceAPIModel import APIStepResult, InterfaceResult

async def get_api_step_with_detail(api_step_id: int):
    async with async_session() as session:
        # 先查询 APIStepResult
        stmt = select(APIStepResult).where(APIStepResult.id == api_step_id)
        result = await session.execute(stmt)
        api_step = result.scalar_one_or_none()

        if api_step and api_step.target_result_id:
            # 再查询关联的 InterfaceResult
            detail_stmt = select(InterfaceResult).where(
                InterfaceResult.id == api_step.target_result_id
            )
            detail_result = await session.execute(detail_stmt)
            interface_result = detail_result.scalar_one_or_none()

            print(f"Step: {api_step.content_name}")
            print(f"API: {interface_result.api_name}")
            print(f"Request: {interface_result.request_method} {interface_result.request_url}")
            print(f"Response: {interface_result.response_status} - {interface_result.response_time}ms")

            return {
                "step": api_step,
                "interface_result": interface_result
            }

        return None
```

---

## 3. Content Type 对照表

| Type | 值 | 类名 | 说明 |
|------|-----|------|------|
| API | 1 | APIStepResult | API请求 |
| GROUP | 2 | GroupStepResult | 步骤组 |
| CONDITION | 3 | ConditionStepResult | 条件判断 |
| LOOP | 4 | LoopStepResult | 循环 |
| SCRIPT | 5 | ScriptStepResult | 脚本 |
| DB | 6 | DBStepResult | 数据库 |
| WAIT | 7 | WaitStepResult | 等待 |
| ASSERT | 8 | AssertStepResult | 断言 |
| WHILE | 9 | WhileStepResult | While循环 |

---

## 4. 注意事项

1. **外键约束**: 所有 StepResult 必须指定 `case_result_id`
2. **多态标识**: 子类必须指定正确的 `polymorphic_identity` 值
3. **父子关系**: GROUP/CONDITION/LOOP/WHILE 类型需要通过 `parent_result_id` 关联子步骤
4. **InterfaceResult**: 由 `APIStepResult.target_result_id` 关联，不是通过外键直接关联
