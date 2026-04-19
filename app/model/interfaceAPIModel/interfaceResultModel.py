#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Time : 2026/4/11
# @Author : cyq
# @Software: PyCharm
# @Desc: 接口执行结果模型

from datetime import datetime, date
from typing import Optional, Set

from sqlalchemy import Column, INTEGER, String, ForeignKey, Boolean, DATETIME, JSON, TEXT, Float, DATE
from sqlalchemy.orm import relationship

from app.model import BaseModel
from enums.CaseEnum import CaseStepContentType


def step_content_result_id_column():
    """子表主键生成器"""
    return Column(
        INTEGER,
        ForeignKey('interface_case_content_result.id', ondelete='CASCADE'),
        primary_key=True
    )


class InterfaceResult(BaseModel):
    """接口执行结果"""
    __tablename__ = "interface_result"


    interface_name = Column(String(50), comment="用例名称")
    interface_uid = Column(String(20), comment="用例Uid")
    interface_desc = Column(String(250), comment="用例描述")

    running_env_id = Column(INTEGER, nullable=True, comment="运行环境")
    running_env_name = Column(String(50), nullable=True, comment="运行环境名称")

    start_time = Column(DATETIME, default=datetime.now, comment="开始时间")
    use_time = Column(String(50), nullable=True, comment="用时")

    request_url = Column(String(250), nullable=True, comment="请求URL")
    request_headers = Column(JSON, nullable=True, comment="请求头")

    request_body_type = Column(INTEGER, nullable=True, comment="请求类型")
    request_json = Column(TEXT, nullable=True, comment="请求报文")
    request_data = Column(TEXT, nullable=True, comment="请求报文")

    request_params = Column(JSON, nullable=True, comment="请求参数")
    request_method = Column(String(10), nullable=True, comment="请求方法")

    response_text = Column(TEXT, nullable=True, comment="响应报文")
    response_status = Column(INTEGER, comment="响应Code")
    response_headers = Column(JSON, nullable=True, comment="响应头")

    extracts = Column(JSON, nullable=True, comment="提取变量")
    asserts = Column(JSON, nullable=True, comment="断言信息")

    starter_id = Column(INTEGER, comment="运行人ID")
    starter_name = Column(String(20), comment="运行人姓名")

    result = Column(Boolean, nullable=True, comment="运行结果")

    interface_id = Column(
        INTEGER, ForeignKey("interface.id", ondelete="CASCADE"), comment="所属用例"
    )

    content_result_id = Column(
        INTEGER,
        ForeignKey("interface_case_content_result.id", ondelete="CASCADE"),
        nullable=True,
        comment="所属步骤内容结果ID"
    )


    task_result_id = Column(
        INTEGER,
        ForeignKey("interface_task_result.id", ondelete="CASCADE"),
        nullable=True,
        comment="任务执行关联"
    )
    def __repr__(self):
        return (f"<InterfaceResult(id={self.id}, name={self.interface_name}, result={self.result})"
                f"content_result_id = {self.content_result_id}"
                f">")


class InterfaceCaseResult(BaseModel):
    """用例执行结果"""
    __tablename__ = "interface_case_result"

    interface_case_id = Column(
        INTEGER, ForeignKey("interface_case.id", ondelete="CASCADE"), comment="所属用例"
    )
    interface_case_name = Column(String(20), comment="用例名称")
    interface_case_uid = Column(String(20), comment="用例Uid")
    interface_case_desc = Column(String(50), comment="用例描述")

    project_id = Column(INTEGER, comment="所属项目")
    module_id = Column(INTEGER, comment="所属模块")

    interface_log = Column(TEXT, nullable=True, comment="运行日志")

    running_env_id = Column(INTEGER, nullable=True, comment="运行环境")
    running_env_name = Column(String(250), nullable=True, comment="运行环境")

    progress = Column(Float, default=0.0, comment="进度")
    start_time = Column(DATETIME, default=datetime.now, comment="开始时间")
    use_time = Column(String(20), nullable=True, comment="用时")

    total_num = Column(INTEGER, default=0, comment="总共数量")
    success_num = Column(INTEGER, default=0, comment="成功数量")
    fail_num = Column(INTEGER, default=0, comment="失败数量")

    starter_id = Column(INTEGER, comment="运行人ID")
    starter_name = Column(String(20), comment="运行人姓名")
    status = Column(String(10), nullable=True, comment="运行状态")
    result = Column(Boolean, nullable=True, comment="运行结果")

    interface_task_result_id = Column(
        INTEGER,
        ForeignKey("interface_task_result.id", ondelete="CASCADE"),
        nullable=True,
        comment="所属task result",
    )

    def __repr__(self):
        return f"<InterfaceCaseResult(id={self.id}, name={self.interface_case_name}, result={self.result})>"


class InterfaceTaskResult(BaseModel):
    """任务执行结果"""
    __tablename__ = "interface_task_result"
    status = Column(String(10), default="RUNNING", comment="状态")  # "RUNNING","DONE"
    result = Column(String(10), nullable=True, comment="运行结果")  # SUCCESS FAIL

    total_num = Column(INTEGER, default=0, comment="总运行数量")
    success_num = Column(INTEGER, default=0, comment="成功数量")
    fail_num = Column(INTEGER, default=0, comment="失败数量")

    start_by = Column(INTEGER, nullable=False, comment="1user 2robot 3...")
    starter_name = Column(String(20), nullable=True, comment="运行人名称")
    starter_id = Column(INTEGER, nullable=True, comment="运行人ID")

    total_use_time = Column(String(20), comment="运行时间")
    start_time = Column(
        DATETIME, default=datetime.now, nullable=True, comment="开始时间"
    )
    end_time = Column(DATETIME, nullable=True, comment="结束时间")

    task_id = Column(
        INTEGER, ForeignKey("interface_task.id", ondelete="CASCADE"), nullable=True
    )
    task_uid = Column(String(10), nullable=False, comment="task索引")
    task_name = Column(String(20), nullable=True, comment="任务名称")

    run_day = Column(DATE, default=date.today(), comment="运行日期")
    progress = Column(Float, default=0, comment="进度")

    running_env_id = Column(INTEGER, nullable=True, comment="运行环境")
    running_env_name = Column(String(250), nullable=True, comment="运行环境")

    project_id = Column(INTEGER, comment="所属项目")
    module_id = Column(INTEGER, comment="所属模块")

    def __repr__(self):
        return f"<InterfaceTaskResult(id={self.id}, task_name={self.task_name}, status={self.status})>"


class InterfaceCaseContentResult(BaseModel):
    """
    步骤内容结果基类 - Joined Table Inheritance

    设计说明：
    - 使用 SQLAlchemy Joined Table Inheritance 实现多态
    - 基类表存储公共字段，子类表存储特有字段
    - 通过 content_type 区分不同类型的执行结果
    """
    __tablename__ = "interface_case_content_result"
    __allow_unmapped__ = True

    case_result_id = Column(
        INTEGER,
        ForeignKey("interface_case_result.id", ondelete="CASCADE"),
        nullable=True,
        comment="所属case result"
    )

    task_result_id = Column(
        INTEGER,
        ForeignKey("interface_task_result.id", ondelete="CASCADE"),
        nullable=True,
        comment="所属task result"
    )

    content_id = Column(
        INTEGER,
        ForeignKey("interface_case_step_content.id", ondelete="SET NULL"),
        nullable=True,
        comment="步骤ID"
    )
    content_name = Column(String(250), nullable=True, comment="步骤名称")
    content_desc = Column(String(250), nullable=True, comment="步骤描述")
    content_step = Column(INTEGER, nullable=False, comment="步骤序号")
    content_type = Column(INTEGER, nullable=False, index=True, comment="步骤类型")

    result = Column(Boolean, nullable=True, comment="执行结果")
    start_time = Column(DATETIME, default=datetime.now, comment="开始时间")
    use_time = Column(String(50), nullable=True, comment="执行用时")
    status = Column(String(20), default="PENDING", comment="执行状态")

    __mapper_args__ = {
        'polymorphic_on': content_type,
        'polymorphic_identity': None,
        'with_polymorphic': '*',
    }

    def to_dict(self, exclude: Optional[Set[str]] = None) -> dict:
        """
        转换为结果字典 - 包含基类字段 + 子类字段

        Args:
            exclude: 要排除的字段集合

        Returns:
            包含完整结果的字典
        """
        result = {
            'id': self.id,
            'uid': self.uid,
            'content_type': self.content_type,
            'content_name': self.content_name,
            'content_desc': self.content_desc,
            'content_step': self.content_step,
            'result': self.result,
            'start_time': self.start_time.strftime("%Y-%m-%d %H:%M:%S") if self.start_time else None,
            'use_time': self.use_time,
            'status': self.status,
            'create_time': self.create_time.strftime("%Y-%m-%d %H:%M:%S") if self.create_time else None,
        }

        for mapper in self.__class__.__mapper__.self_and_descendants:
            if mapper.local_table.name != self.__tablename__:
                for col in mapper.local_table.columns:
                    if hasattr(self, col.name):
                        value = getattr(self, col.name)
                        if isinstance(value, datetime):
                            result[col.name] = value.strftime("%Y-%m-%d %H:%M:%S")
                        else:
                            result[col.name] = value

        if exclude:
            for key in exclude:
                result.pop(key, None)

        return result

    def __repr__(self):
        return f"<InterfaceCaseContentResult(id={self.id}, type={self.content_type}, result={self.result})>"


class APIStepContentResult(InterfaceCaseContentResult):
    """
    API步骤执行结果

    特点：1对1 关联 interface_result
    """
    __tablename__ = "interface_case_content_result_api"
    __mapper_args__ = {'polymorphic_identity': CaseStepContentType.STEP_API}

    result_id = step_content_result_id_column()

    interface_result_id = Column(
        INTEGER,
        ForeignKey("interface_result.id", ondelete="SET NULL"),
        nullable=True,
        comment="关联接口执行结果ID"
    )

    interface_result = relationship(
        InterfaceResult,
        foreign_keys=[interface_result_id],
        lazy="selectin"
    )
    #
    def to_dict(self, exclude: Optional[Set[str]] = None) -> dict:
        """返回完整的执行结果信息（包含 interface_result 详情）"""
        result = super().to_dict(exclude)
        result['data'] = [self.interface_result]
        return result

    def __repr__(self):
        return f"<APIStepContentResult(id={self.id}, interface_result_id={self.interface_result_id})>"


class GroupStepContentResult(InterfaceCaseContentResult):
    """
    API组步骤执行结果

    特点：1对多 关联 interface_result
    """
    __tablename__ = "interface_case_content_result_group"
    __mapper_args__ = {'polymorphic_identity': CaseStepContentType.STEP_API_GROUP}

    result_id = step_content_result_id_column()

    total_api_num = Column(INTEGER, default=0, comment="总接口数量")
    success_api_num = Column(INTEGER, default=0, comment="成功接口数量")
    fail_api_num = Column(INTEGER, default=0, comment="失败接口数量")

    interface_results = relationship(
        InterfaceResult,
        primaryjoin=result_id == InterfaceResult.content_result_id,
        foreign_keys=[InterfaceResult.content_result_id],
        lazy="selectin",
        viewonly=True
    )

    def to_dict(self, exclude: Optional[Set[str]] = None) -> dict:
        """返回组执行结果（interface_results 由查询层填充）"""
        result = super().to_dict(exclude)
        result['data'] = self.interface_results
        result['total_api_num'] = self.total_api_num
        result['fail_api_num'] = self.fail_api_num
        result['success_api_num'] = self.success_api_num
        return result

    def __repr__(self):
        return f"<GroupStepContentResult(id={self.id}, total={self.total_api_num}, success={self.success_api_num})>"


class ConditionStepContentResult(InterfaceCaseContentResult):
    """
    条件步骤执行结果

    特点：1对多 关联 interface_result + 断言信息
    """
    __tablename__ = "interface_case_content_result_condition"
    __mapper_args__ = {'polymorphic_identity': CaseStepContentType.STEP_API_CONDITION}

    result_id = step_content_result_id_column()

    condition_result = Column(Boolean, nullable=True, comment="条件判断结果")
    condition_key = Column(String(100), nullable=True, comment="条件键")
    condition_value = Column(String(100), nullable=True, comment="条件值")
    condition_operator = Column(INTEGER, nullable=True, comment="条件操作符")

    interface_results = relationship(
        InterfaceResult,
        primaryjoin=result_id == InterfaceResult.content_result_id,
        foreign_keys=[InterfaceResult.content_result_id],
        lazy="selectin",
        viewonly=True
    )

    assert_data = Column(JSON, nullable=True, comment="断言信息")
    extract_data = Column(JSON, nullable=True, comment="提取变量")

    def to_dict(self, exclude: Optional[Set[str]] = None) -> dict:
        """返回条件执行结果（interface_results 由查询层填充）"""
        result = super().to_dict(exclude)
        result['data'] = self.interface_results
        result['assert_data'] = self.assert_data
        result['extract_data'] = self.extract_data
        result["content_condition"] = {
            "key": self.condition_key,
            "value": self.condition_value,
            "operator": self.condition_operator,
            "result":self.condition_result
        }
        return result

    def __repr__(self):
        return f"<ConditionStepContentResult(id={self.id}, condition_result={self.condition_result})>"


class ScriptStepContentResult(InterfaceCaseContentResult):
    """
    脚本步骤执行结果

    特点：执行自定义脚本
    """
    __tablename__ = "interface_case_content_result_script"
    __mapper_args__ = {'polymorphic_identity': CaseStepContentType.STEP_API_SCRIPT}

    result_id = step_content_result_id_column()

    script_error = Column(TEXT, nullable=True, comment="脚本错误")
    script_vars = Column(JSON,nullable=True,comment="脚本变量")

    def to_dict(self, exclude: Optional[Set[str]] = None) -> dict:
        """返回条件执行结果（interface_results 由查询层填充）"""
        result = super().to_dict(exclude)
        result["script_error"] = self.script_error
        result["script_vars"] = self.script_vars
        return result

    def __repr__(self):
        return f"<ScriptStepContentResult(id={self.id}, result={self.result})>"


class DBStepContentResult(InterfaceCaseContentResult):
    """
    数据库步骤执行结果

    特点：执行数据库操作
    """
    __tablename__ = "interface_case_content_result_db"
    __mapper_args__ = {'polymorphic_identity': CaseStepContentType.STEP_API_DB}

    result_id = step_content_result_id_column()

    db_query_result = Column(JSON, nullable=True, comment="查询结果")



    def to_dict(self, exclude: Optional[Set[str]] = None) -> dict:
        """返回条件执行结果（interface_results 由查询层填充）"""
        result = super().to_dict(exclude)
        result['db_query_result'] = self.db_query_result
        return result
    def __repr__(self):
        return f"<DBStepContentResult(id={self.id},db_query_result={self.db_query_result})> )>"


class WaitStepContentResult(InterfaceCaseContentResult):
    """
    等待步骤执行结果

    特点：等待指定时间
    """
    __tablename__ = "interface_case_content_result_wait"
    __mapper_args__ = {'polymorphic_identity': CaseStepContentType.STEP_API_WAIT}

    result_id = step_content_result_id_column()

    wait_seconds = Column(INTEGER, default=0, comment="等待秒数")

    def to_dict(self, exclude: Optional[Set[str]] = None) -> dict:
        """返回条件执行结果（interface_results 由查询层填充）"""
        result = super().to_dict(exclude)
        result["wait_seconds"] = self.wait_seconds
        return result
    def __repr__(self):
        return f"<WaitStepContentResult(id={self.id}, wait_seconds={self.wait_seconds})>"


class AssertStepContentResult(InterfaceCaseContentResult):
    """
    断言步骤执行结果

    特点：执行断言验证
    """
    __tablename__ = "interface_case_content_result_assert"
    __mapper_args__ = {'polymorphic_identity': CaseStepContentType.STEP_API_ASSERT}

    result_id = step_content_result_id_column()

    assert_data = Column(JSON, nullable=True, comment="断言数据")
    assert_result = Column(Boolean, nullable=True, comment="断言结果")
    assert_error = Column(TEXT, nullable=True, comment="断言错误信息")


    def to_dict(self, exclude: Optional[Set[str]] = None) -> dict:
        """返回条件执行结果（interface_results 由查询层填充）"""
        result = super().to_dict(exclude)
        result["assert_data"] = self.assert_data
        result["assert_result"] = self.assert_result
        return result

    def __repr__(self):
        return f"<AssertStepContentResult(id={self.id}, assert_result={self.assert_result})>"


class LoopStepContentResult(InterfaceCaseContentResult):
    """
    循环步骤执行结果

    特点：按次数或条件循环执行
    """
    __tablename__ = "interface_case_content_result_loop"
    __mapper_args__ = {'polymorphic_identity': CaseStepContentType.STEP_LOOP}

    result_id = step_content_result_id_column()

    loop_count = Column(INTEGER, default=0, comment="循环次数")
    loop_type = Column(INTEGER, nullable=True, comment="循环类型")
    loop_items = Column(JSON, nullable=True, comment="循环数据项")

    success_count = Column(INTEGER, default=0, comment="成功次数")
    fail_count = Column(INTEGER, default=0, comment="失败次数")

    interface_results = relationship(
        InterfaceResult,
        primaryjoin=result_id == InterfaceResult.content_result_id,
        foreign_keys=[InterfaceResult.content_result_id],
        lazy="selectin",
        viewonly=True
    )
    def to_dict(self, exclude: Optional[Set[str]] = None) -> dict:
        """返回循环执行结果（interface_results 由查询层填充）"""
        result = super().to_dict(exclude)
        result["loop_count"] = self.loop_count
        result["loop_type"] = self.loop_type
        result["loop_items"] = self.loop_items
        result["success_count"] = self.success_count
        result["fail_count"] = self.fail_count
        result["data"] = self.interface_results
        return result

    def __repr__(self):
        return f"<LoopStepContentResult(id={self.id}, loop_count={self.loop_count})>"


__all__ = [
    "InterfaceResult",
    "InterfaceTaskResult",
    "InterfaceCaseResult",
    "LoopStepContentResult",
    "AssertStepContentResult",
    "WaitStepContentResult",
    "InterfaceCaseContentResult",
    "DBStepContentResult",
    "ScriptStepContentResult",
    "APIStepContentResult",
    "GroupStepContentResult",
    "ConditionStepContentResult"

]
