#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Time : 2026/1/21
# @Author : cyq
# @File : __init__.py
# @Software: PyCharm
# @Desc: 接口执行结果写入器

from datetime import datetime
from typing import Union, Optional, Any, TYPE_CHECKING


from app.mapper.interfaceApi.interfaceResultMapper import (
    InterfaceResultMapper,
    InterfaceCaseResultMapper,
    InterfaceTaskResultMapper
)

from app.model.interfaceAPIModel.interfaceResultModel import (
    InterfaceResult,
    InterfaceTaskResult,
    InterfaceCaseResult
)
from app.mapper.interfaceApi.interfaceResultMapper import InterfaceResultMapper

from enums import InterfaceAPIStatusEnum, InterfaceAPIResultEnum
from croe.interface.starter import APIStarter, log
from utils import GenerateTools

if TYPE_CHECKING:
    from app.model.interface import InterfaceCase, InterfaceTask
    from app.model.base import EnvModel


async def write_interface_result(**kwargs) -> InterfaceResult:
    """
    写入API结果

    Args:
        **kwargs: 接口结果参数

    Returns:
        InterfaceResult: 接口结果实例
    """
    return await InterfaceResultMapper.set_result(**kwargs)


async def write_case_result(
    case_result: InterfaceCaseResult
) -> InterfaceCaseResult:
    """
    写入用例进度

    Args:
        case_result: 用例结果实例

    Returns:
        InterfaceCaseResult: 更新后的用例结果实例
    """
    return await InterfaceCaseResultMapper.set_result_field(case_result)


async def write_task_process(
    task_result: InterfaceTaskResult
) -> InterfaceTaskResult:
    """
    写入任务进度

    Args:
        task_result: 任务结果实例

    Returns:
        InterfaceTaskResult: 更新后的任务结果实例
    """
    return await InterfaceTaskResultMapper.set_result_field(task_result)


async def write_interface_case_result(
    case_result: InterfaceCaseResult
) -> InterfaceCaseResult:
    """
    写入用例最终结果

    Args:
        case_result: 用例结果实例

    Returns:
        InterfaceCaseResult: 更新后的用例结果实例
    """
    if case_result.fail_num == 0:
        case_result.result = InterfaceAPIResultEnum.SUCCESS
    else:
        case_result.result = InterfaceAPIResultEnum.ERROR

    case_result.useTime = GenerateTools.calculate_time_difference(
        case_result.map['startTime']
    )
    case_result.status = InterfaceAPIStatusEnum.OVER

    return await InterfaceCaseResultMapper.set_result_field(case_result)


async def init_interface_case_result(
    starter: APIStarter,
    interface_case: "InterfaceCase",
    env: "EnvModel",
    task_result: Optional["InterfaceTaskResult"] = None
) -> InterfaceCaseResult:
    """
    初始化业务流结果对象

    Args:
        starter: API启动器实例
        interface_case: 接口用例实例
        env: 环境配置实例
        task_result: 任务结果实例（可选）

    Returns:
        InterfaceCaseResult: 创建的用例结果实例
    """
    case_result = InterfaceCaseResult(
        interface_case_id=interface_case.id,
        interface_case_name=interface_case.title,
        interface_case_uid=interface_case.uid,
        interface_case_desc=interface_case.desc,
        project_id=interface_case.project_id,
        module_id=interface_case.module_id,
        total_num=interface_case.apiNum,
        starter_id=starter.userId,
        starter_name=starter.username,
        status=InterfaceAPIStatusEnum.RUNNING,
        running_env_id=env.id,
        running_env_name=env.name
    )

    if task_result:
        case_result.task_result_id = task_result.id

    case_result = await InterfaceCaseResultMapper.insert(case_result)
    log.info(
        f"{interface_case} 初始化用例结果对象 = {case_result}"
    )

    return case_result


async def init_interface_task_result(
    interface_task: "InterfaceTask",
    starter: APIStarter,
    env: Optional["EnvModel"] = None
) -> InterfaceTaskResult:
    """
    初始化接口测试任务

    该异步静态方法用于初始化一个接口测试任务，并将任务相关信息以及启动者信息
    组织成一个字典，最后通过 InterfaceTaskResultMapper.init() 方法初始化并返回
    接口测试任务结果模型。

    Args:
        interface_task: 接口任务实例
        starter: API启动器实例
        env: 环境配置实例（可选）

    Returns:
        InterfaceTaskResult: 创建的任务结果实例
    """
    init_task = InterfaceTaskResult(
        task_id=interface_task.id,
        task_uid=interface_task.uid,
        task_name=interface_task.title,
        project_id=interface_task.project_id,
        module_id=interface_task.module_id
    )

    init_task.start_by = starter.startBy
    init_task.starter_name = starter.username
    init_task.starter_id = starter.userId

    if env:
        init_task.running_env_id = env.id
        init_task.running_env_name = env.name

    return await InterfaceTaskResultMapper.insert(init_task)


async def write_interface_task_result(
    task_result: InterfaceTaskResult
) -> InterfaceTaskResult:
    """
    写入任务最终结果

    Args:
        task_result: 任务结果实例

    Returns:
        InterfaceTaskResult: 更新后的任务结果实例
    """
    task_result.progress = 100
    task_result.totalUseTime = GenerateTools.calculate_time_difference(
        task_result.map['start_time']
    )
    task_result.status = InterfaceAPIStatusEnum.OVER
    task_result.end_time = datetime.now()

    return await InterfaceTaskResultMapper.set_result_field(task_result)
