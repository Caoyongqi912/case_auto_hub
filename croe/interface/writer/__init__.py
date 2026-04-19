#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Time : 2026/1/21
# @Author : cyq
# @File : __init__.py
# @Software: PyCharm
# @Desc: 接口执行结果写入器

import warnings
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
from enums import InterfaceAPIStatusEnum, InterfaceAPIResultEnum
from croe.interface.starter import APIStarter, log
from utils import GenerateTools

from app.model.interfaceAPIModel.interfaceCaseModel import InterfaceCase
from app.model.interfaceAPIModel.interfaceTaskModel import InterfaceTask
from app.model.base import EnvModel

from .result_writer import ResultWriter

result_writer = ResultWriter()


async def write_interface_result(**kwargs) -> InterfaceResult:
    """
    写入API结果
    
    .. deprecated:: 2.0
        请使用 result_writer.write_interface_result() 代替
    
    Args:
        **kwargs: 接口结果参数
    
    Returns:
        InterfaceResult: 接口结果实例
    """
    warnings.warn(
        "write_interface_result() 已废弃，请使用 result_writer.write_interface_result()",
        DeprecationWarning,
        stacklevel=2
    )
    return await InterfaceResultMapper.set_result(**kwargs)


async def write_task_process(
    task_result: InterfaceTaskResult
) -> InterfaceTaskResult:
    """
    写入任务进度
    
    .. deprecated:: 2.0
        请使用 result_writer.update_task_progress() 代替
    
    Args:
        task_result: 任务结果实例
    
    Returns:
        InterfaceTaskResult: 更新后的任务结果实例
    """
    warnings.warn(
        "write_task_process() 已废弃，请使用 result_writer.update_task_progress()",
        DeprecationWarning,
        stacklevel=2
    )
    return await InterfaceTaskResultMapper.set_result_field(task_result)


async def write_interface_case_result(
    case_result: InterfaceCaseResult
) -> InterfaceCaseResult:
    """
    写入用例最终结果
    
    .. deprecated:: 2.0
        请使用 result_writer.finalize_case_result() 代替
    
    Args:
        case_result: 用例结果实例
    
    Returns:
        InterfaceCaseResult: 更新后的用例结果实例
    """
    warnings.warn(
        "write_interface_case_result() 已废弃，请使用 result_writer.finalize_case_result()",
        DeprecationWarning,
        stacklevel=2
    )
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
    
    .. deprecated:: 2.0
        请使用 result_writer.init_case_result() 代替
    
    Args:
        starter: API启动器实例
        interface_case: 接口用例实例
        env: 环境配置实例
        task_result: 任务结果实例（可选）
    
    Returns:
        InterfaceCaseResult: 创建的用例结果实例
    """
    warnings.warn(
        "init_interface_case_result() 已废弃，请使用 result_writer.init_case_result()",
        DeprecationWarning,
        stacklevel=2
    )
    case_result = InterfaceCaseResult(
        interface_case_id=interface_case.id,
        interface_case_name=interface_case.case_title,
        interface_case_uid=interface_case.uid,
        interface_case_desc=interface_case.case_desc,
        project_id=interface_case.project_id,
        module_id=interface_case.module_id,
        total_num=interface_case.case_api_num,
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
    
    .. deprecated:: 2.0
        请使用 result_writer.init_task_result() 代替
    
    Args:
        interface_task: 接口任务实例
        starter: API启动器实例
        env: 环境配置实例（可选）
    
    Returns:
        InterfaceTaskResult: 创建的任务结果实例
    """
    warnings.warn(
        "init_interface_task_result() 已废弃，请使用 result_writer.init_task_result()",
        DeprecationWarning,
        stacklevel=2
    )
    init_task = InterfaceTaskResult(
        task_id=interface_task.id,
        task_uid=interface_task.uid,
        task_name=interface_task.interface_task_title,
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
    
    .. deprecated:: 2.0
        请使用 result_writer.finalize_task_result() 代替
    
    Args:
        task_result: 任务结果实例
    
    Returns:
        InterfaceTaskResult: 更新后的任务结果实例
    """
    warnings.warn(
        "write_interface_task_result() 已废弃，请使用 result_writer.finalize_task_result()",
        DeprecationWarning,
        stacklevel=2
    )
    task_result.progress = 100
    task_result.totalUseTime = GenerateTools.calculate_time_difference(
        task_result.map['start_time']
    )
    task_result.status = InterfaceAPIStatusEnum.OVER
    task_result.end_time = datetime.now()

    return await InterfaceTaskResultMapper.set_result_field(task_result)


__all__ = [
    'ResultWriter',
    'result_writer',
    'write_interface_result',
    'write_task_process',
    'write_interface_case_result',
    'init_interface_case_result',
    'init_interface_task_result',
    'write_interface_task_result',
]
