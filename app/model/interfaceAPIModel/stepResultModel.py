#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Time : 2026/4/10
# @Author : cyq
# @File : stepResultModel
# @Software: PyCharm
# @Desc: 用例步骤执行结果模型 - Joined Table Inheritance

from datetime import datetime

from sqlalchemy import Column, INTEGER, String, TEXT, JSON, Float, BOOLEAN, DATETIME, ForeignKey
from sqlalchemy.orm import relationship

from app.model import BaseModel


class BaseStepResult(BaseModel):
    """
    步骤结果基类 - Joined Table Inheritance

    设计说明：
    - 使用 SQLAlchemy Joined Table Inheritance 实现多态
    - 基类表存储公共字段，子类表存储特有字段
    - 通过 polymorphic_on (content_type) 区分类型
    - 通过 parent_result_id 实现 GROUP/Condition/Loop 的嵌套结构
    """
    __tablename__ = "interface_step_result"
    __allow_unmapped__ = True

    case_result_id = Column(
        INTEGER,
        ForeignKey('interface_case_result.id', ondelete='CASCADE'),
        nullable=False,
        comment="所属用例结果ID"
    )

    task_result_id = Column(
        INTEGER,
        ForeignKey('interface_task_result.id', ondelete='CASCADE'),
        nullable=True,
        comment="所属任务结果ID"
    )

    content_id = Column(
        INTEGER,
        ForeignKey('interface_case_step_content.id', ondelete='SET NULL'),
        nullable=True,
        comment="步骤内容ID"
    )

    content_type = Column(INTEGER, nullable=False, index=True, comment="步骤类型")
    content_step = Column(INTEGER, nullable=False, default=0, comment="步骤序号")
    content_name = Column(String(250), nullable=True, comment="步骤名称")
    content_desc = Column(String(250), nullable=True, comment="步骤描述")

    content_result = Column(BOOLEAN, default=False, comment="执行结果")
    content_message = Column(TEXT, nullable=True, comment="结果信息/错误原因")

    start_time = Column(DATETIME, default=datetime.now, comment="开始时间")
    use_time = Column(String(50), nullable=True, comment="耗时")

    starter_id = Column(INTEGER, nullable=True, comment="运行人ID")
    starter_name = Column(String(20), nullable=True, comment="运行人姓名")

    parent_result_id = Column(
        INTEGER,
        ForeignKey('interface_step_result.id', ondelete='SET NULL'),
        nullable=True,
        comment="父步骤结果ID（用于 GROUP/Condition/Loop 嵌套）"
    )

    extracts = Column(JSON, nullable=True, comment="变量提取")
    asserts = Column(JSON, nullable=True, comment="断言信息")

    __mapper_args__ = {
        'polymorphic_on': content_type,
        'polymorphic_identity': None,
    }

    @property
    def api_results(self):
        """获取子结果列表（用于 GROUP/Condition/Loop 场景）"""
        from app.model import async_session
        from sqlalchemy import select
        from sqlalchemy.orm import selectinload

        async def _get_results():
            async with async_session() as session:
                stmt = select(self.__class__).where(
                    self.__class__.parent_result_id == self.id
                )
                result = await session.execute(stmt)
                return result.scalars().all()

        return _get_results()


class APIStepResult(BaseStepResult):
    """
    API 步骤结果

    存储单个 API 的执行详情
    """
    __tablename__ = "interface_step_result_api"

    target_result_id = Column(
        INTEGER,
        nullable=True,
        comment="指向 InterfaceResult 表的 ID"
    )

    request_method = Column(String(10), nullable=True, comment="请求方法")
    request_url = Column(String(500), nullable=True, comment="请求地址")
    request_headers = Column(JSON, nullable=True, comment="请求头")
    request_params = Column(JSON, nullable=True, comment="请求参数")
    request_body = Column(TEXT, nullable=True, comment="请求体")

    response_status = Column(INTEGER, nullable=True, comment="响应状态码")
    response_headers = Column(JSON, nullable=True, comment="响应头")
    response_body = Column(TEXT, nullable=True, comment="响应体")
    response_time = Column(Float, nullable=True, comment="响应时间(ms)")

    __mapper_args__ = {
        'polymorphic_identity': 1,
    }


class GroupStepResult(BaseStepResult):
    """
    步骤组 结果

    包含多个子步骤（通过 parent_result_id 关联）
    """
    __tablename__ = "interface_step_result_group"

    group_name = Column(String(100), nullable=True, comment="组名称")
    group_desc = Column(String(250), nullable=True, comment="组描述")

    __mapper_args__ = {
        'polymorphic_identity': 2,
    }


class ConditionStepResult(BaseStepResult):
    """
    条件步骤 结果

    包含条件表达式和判断结果，以及满足条件时执行的子步骤
    """
    __tablename__ = "interface_step_result_condition"

    condition_expression = Column(String(500), nullable=True, comment="条件表达式")
    condition_result = Column(BOOLEAN, nullable=True, comment="条件判断结果")
    condition_result_data = Column(JSON, nullable=True, comment="条件判断详情")

    __mapper_args__ = {
        'polymorphic_identity': 3,
    }


class LoopStepResult(BaseStepResult):
    """
    循环步骤 结果

    包含循环次数和循环体内执行的子步骤
    """
    __tablename__ = "interface_step_result_loop"

    loop_count = Column(INTEGER, default=0, comment="当前循环次数")
    loop_max = Column(INTEGER, nullable=True, comment="最大循环次数")
    loop_condition = Column(String(500), nullable=True, comment="循环退出条件")

    __mapper_args__ = {
        'polymorphic_identity': 4,
    }


class ScriptStepResult(BaseStepResult):
    """
    脚本步骤 结果

    存储脚本执行相关的信息
    """
    __tablename__ = "interface_step_result_script"

    script_type = Column(String(20), nullable=True, comment="脚本类型 python/js")
    script_content = Column(TEXT, nullable=True, comment="脚本内容")
    script_output = Column(TEXT, nullable=True, comment="脚本输出/日志")
    script_extracts = Column(JSON, nullable=True, comment="脚本提取的变量")

    __mapper_args__ = {
        'polymorphic_identity': 5,
    }


class DBStepResult(BaseStepResult):
    """
    数据库步骤 结果

    存储 SQL 执行相关的信息
    """
    __tablename__ = "interface_step_result_db"

    db_source = Column(String(100), nullable=True, comment="数据源名称")
    sql_type = Column(String(10), nullable=True, comment="SQL类型 SELECT/INSERT/UPDATE/DELETE")
    sql_content = Column(TEXT, nullable=True, comment="SQL语句")
    sql_params = Column(JSON, nullable=True, comment="SQL参数")
    sql_result = Column(JSON, nullable=True, comment="查询结果")
    sql_affected_rows = Column(INTEGER, nullable=True, comment="影响行数")

    __mapper_args__ = {
        'polymorphic_identity': 6,
    }


class WaitStepResult(BaseStepResult):
    """
    等待步骤 结果

    存储等待相关的信息
    """
    __tablename__ = "interface_step_result_wait"

    wait_type = Column(String(20), nullable=True, comment="等待类型 time/element")
    wait_duration = Column(Float, nullable=True, comment="等待时长(秒)")
    wait_condition = Column(String(250), nullable=True, comment="等待条件")

    __mapper_args__ = {
        'polymorphic_identity': 7,
    }


class AssertStepResult(BaseStepResult):
    """
    断言步骤 结果

    存储断言执行相关的信息
    """
    __tablename__ = "interface_step_result_assert"

    assert_type = Column(String(50), nullable=True, comment="断言类型")
    assert_expression = Column(String(500), nullable=True, comment="断言表达式")
    assert_data = Column(JSON, nullable=True, comment="断言详情")
    assert_passed = Column(BOOLEAN, nullable=True, comment="断言是否通过")

    __mapper_args__ = {
        'polymorphic_identity': 8,
    }


class WhileStepResult(BaseStepResult):
    """
    While 循环步骤 结果

    存储 While 循环相关的信息
    """
    __tablename__ = "interface_step_result_while"

    while_condition = Column(String(500), nullable=True, comment="循环条件表达式")
    while_result = Column(BOOLEAN, nullable=True, comment="循环条件判断结果")
    loop_count = Column(INTEGER, default=0, comment="循环次数")
    loop_max = Column(INTEGER, nullable=True, comment="最大循环次数")

    __mapper_args__ = {
        'polymorphic_identity': 9,
    }
