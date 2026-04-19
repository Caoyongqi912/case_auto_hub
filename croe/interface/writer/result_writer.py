#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Time : 2026/4/14
# @Author : cyq
# @File : result_writer.py
# @Software: PyCharm
# @Desc: 统一结果写入器

import time
from datetime import datetime
from typing import Optional, List, Dict, Any
from app.model.base import EnvModel

from app.mapper.interfaceApi.interfaceResultMapper import (
    InterfaceResultMapper,
    InterfaceCaseResultMapper,
    InterfaceTaskResultMapper,
    InterfaceContentStepResultMapper
)
from app.model.interfaceAPIModel.interfaceResultModel import (
    InterfaceResult,
    InterfaceCaseResult,
    InterfaceTaskResult,
    InterfaceCaseContentResult
)
from app.model.interfaceAPIModel.interfaceCaseModel import InterfaceCase
from enums import InterfaceAPIStatusEnum, InterfaceAPIResultEnum
from enums.CaseEnum import CaseStepContentType
from utils import GenerateTools, log
from croe.interface.starter import APIStarter


class ResultWriter:
    """
    统一结果写入器（优化版）

    设计说明：
    1. case_result 初始化 → 立即插入 DB
    2. 父步骤（GROUP/CONDITION/LOOP）content_result → 立即插入获取 ID
    3. 子步骤（API）api_result + content_result → 缓存
    4. 每个步骤执行完 → 立即更新 case_result.progress（对前端友好）
    5. case 执行完 → 缓存批量插入 + case_result 最终更新
    """

    PARENT_STEP_TYPES = {
        CaseStepContentType.STEP_API_GROUP,
        CaseStepContentType.STEP_API_CONDITION,
        CaseStepContentType.STEP_LOOP,
    }

    def __init__(self):
        self.api_result_cache: List[InterfaceResult] = []
        self.content_result_cache: List[Dict[str, Any]] = []
        self._progress_update_cache: Dict[int, Dict[str, Any]] = {}
        self._last_progress_time: Dict[int, float] = {}

    async def init_task_result(
            self,
            task,
            starter,
            env=None
    ) -> InterfaceTaskResult:
        """
        初始化任务结果

        Args:
            task: 任务对象
            starter: 启动器实例
            env: 环境配置实例（可选）

        Returns:
            InterfaceTaskResult: 创建的任务结果实例
        """
        task_result = InterfaceTaskResult(
            task_id=task.id,
            task_uid=task.uid,
            task_name=task.title,
            project_id=task.project_id,
            module_id=task.module_id,
            start_by=starter.startBy,
            starter_name=starter.username,
            starter_id=starter.userId,
        )

        if env:
            task_result.running_env_id = env.id
            task_result.running_env_name = env.name

        return await InterfaceTaskResultMapper.insert(task_result)

    async def init_case_result(
            self,
            interface_case: InterfaceCase,
            starter: APIStarter,
            env: EnvModel,
            task_result: Optional[InterfaceTaskResult] = None
    ) -> InterfaceCaseResult:
        """
        初始化用例结果

        Args:
            interface_case: 接口用例实例
            starter: 启动器实例
            env: 环境配置实例
            task_result: 任务结果实例（可选）

        Returns:
            InterfaceCaseResult: 创建的用例结果实例
        """
        case_result = InterfaceCaseResult()
        case_result.interface_case_id = interface_case.id
        case_result.interface_case_name = interface_case.case_title
        case_result.interface_case_uid = interface_case.uid
        case_result.interface_case_desc = interface_case.case_desc
        case_result.project_id = interface_case.project_id
        case_result.module_id = interface_case.module_id
        case_result.total_num = interface_case.case_api_num
        case_result.starter_id = starter.userId
        case_result.starter_name = starter.username
        case_result.status = InterfaceAPIStatusEnum.RUNNING
        case_result.running_env_id = env.id
        case_result.running_env_name = env.name

        case_result.start_time = datetime.now()
        case_result.success_num = 0
        case_result.fail_num = 0

        if task_result:
            case_result.task_result_id = task_result.id

        return await InterfaceCaseResultMapper.insert(case_result)

    async def write_interface_result(
            self,
            interface_result: InterfaceResult,
            content_result_id: Optional[int] = None,
            immediate: bool = False
    ) -> InterfaceResult:
        """
        写入接口结果

        Args:
            interface_result: 接口结果对象
            content_result_id: 关联的步骤内容结果ID
            immediate: 是否立即写入（父步骤下的 API 需要立即写入以获取 ID）

        Returns:
            InterfaceResult: 创建的接口结果实例
        """
        if content_result_id:
            interface_result.content_result_id = content_result_id

        if immediate:
            return await InterfaceResultMapper.insert(interface_result)
        else:
            self.api_result_cache.append(interface_result)
            return interface_result

    async def write_step_result(
            self,
            content_type: CaseStepContentType,
            case_result_id: int,
            task_result_id: Optional[int],
            content_id: Optional[int],
            content_name: str,
            content_desc: Optional[str],
            content_step: int,
            success: bool,
            start_time: datetime,
            use_time: str,
            **kwargs
    ) -> InterfaceCaseContentResult:
        """
        写入步骤结果

        设计说明：
        - 父步骤（GROUP/CONDITION/LOOP）：立即插入，获取 ID，供子步骤使用
        - 子步骤（API 等）：加入缓存，最后批量插入

        Args:
            content_type: 步骤类型
            case_result_id: 用例结果ID
            task_result_id: 任务结果ID
            content_id: 步骤内容ID
            content_name: 步骤名称
            content_desc: 步骤描述
            content_step: 步骤序号
            success: 是否成功
            start_time: 开始时间
            use_time: 用时
            **kwargs: 其他特有字段

        Returns:
            InterfaceCaseContentResult: 创建的步骤内容结果实例
        """
        is_parent_step = content_type in self.PARENT_STEP_TYPES

        result_data = {
            'content_type': content_type,
            'case_result_id': case_result_id,
            'task_result_id': task_result_id,
            'content_id': content_id,
            'content_name': content_name,
            'content_desc': content_desc,
            'content_step': content_step,
            'result': success,
            'status': "SUCCESS" if success else "FAIL",
            'start_time': start_time,
            'use_time': use_time,
            **kwargs
        }

        if is_parent_step:
            return await InterfaceContentStepResultMapper.insert_result(**result_data)
        else:
            self.content_result_cache.append(result_data)
            return None

    async def update_step_result(
            self,
            result_id: int,
            **kwargs
    ) -> InterfaceCaseContentResult:
        """
        更新步骤结果

        Args:
            result_id: 步骤内容结果ID
            **kwargs: 更新字段

        Returns:
            InterfaceCaseContentResult: 更新后的步骤内容结果实例
        """
        return await InterfaceContentStepResultMapper.update_result(
            result_id=result_id,
            **kwargs
        )

    async def update_case_progress(
            self,
            case_result: InterfaceCaseResult,
            force: bool = False
    ):
        """
        更新用例进度

        每个步骤执行完立即更新，对前端友好

        Args:
            case_result: 用例结果对象
            force: 是否强制更新（忽略节流）
        """
        current_time = time.time()
        last_time = self._last_progress_time.get(case_result.id, 0)

        if not force and (current_time - last_time < 0.5):
            return

        self._last_progress_time[case_result.id] = current_time

        await InterfaceCaseResultMapper.update_by_id(
            id=case_result.id,
            progress=case_result.progress,
            success_num=case_result.success_num,
            fail_num=case_result.fail_num,
            result=case_result.result,
        )

    async def finalize_case_result(
            self,
            case_result: InterfaceCaseResult,
            logs: str = ""
    ):
        """
        完成用例结果

        执行步骤：
        1. 批量插入缓存的 api_result
        2. 批量插入缓存的 content_result
        3. 更新 case_result 最终状态

        Args:
            case_result: 用例结果对象
            logs: 执行日志
        """
        await self._flush_cache()

        if case_result.fail_num == 0:
            case_result.result = InterfaceAPIResultEnum.SUCCESS
        else:
            case_result.result = InterfaceAPIResultEnum.ERROR

        case_result.use_time = GenerateTools.calculate_time_difference(
            case_result.map['start_time'],
        )
        case_result.status = InterfaceAPIStatusEnum.OVER

        if logs:
            case_result.interface_log = logs

        await InterfaceCaseResultMapper.update_by_id(
            id=case_result.id,
            use_time=case_result.use_time,
            status=case_result.status,
            result=case_result.result,
            progress=100.0,
            success_num=case_result.success_num,
            fail_num=case_result.fail_num,
            interface_log=case_result.interface_log if logs else None,
        )

    async def _flush_cache(self):
        """
        刷新缓存，批量插入数据

        重要：
        - content_result_cache 中存储的是字典，需要先转换成模型
        - api_result_cache 中存储的是 InterfaceResult 模型
        """
        if self.api_result_cache or self.content_result_cache:
            log.info(
                f"开始刷新缓存: api_result={len(self.api_result_cache)}, content_result={len(self.content_result_cache)}")

        if self.api_result_cache:
            await self._bulk_insert_api_results()

        if self.content_result_cache:
            await self._bulk_insert_content_results()

        self.api_result_cache.clear()
        self.content_result_cache.clear()

    async def _bulk_insert_api_results(self):
        """批量插入 API 结果"""
        items = []
        for result in self.api_result_cache:
            item = {
                'interface_id': result.interface_id,
                'interface_name': result.interface_name,
                'interface_uid': result.interface_uid,
                'interface_desc': result.interface_desc,
                'running_env_id': result.running_env_id,
                'running_env_name': result.running_env_name,
                'start_time': result.start_time,
                'use_time': result.use_time,
                'request_url': result.request_url,
                'request_headers': result.request_headers,
                'request_json': result.request_json,
                'request_data': result.request_data,
                "request_body_type":result.request_body_type,
                'request_params': result.request_params,
                'request_method': result.request_method,
                'response_text': result.response_text,
                'response_status': result.response_status,
                'response_headers': result.response_headers,
                'extracts': result.extracts,
                'asserts': result.asserts,
                'starter_id': result.starter_id,
                'starter_name': result.starter_name,
                'result': result.result,
                'content_result_id': result.content_result_id,
            }
            items.append(item)

        if items:
            await InterfaceResultMapper.bulk_insert(items)
            log.info(f"批量插入 api_result: {len(items)} 条")

    async def _bulk_insert_content_results(self):
        """批量插入步骤内容结果"""
        for result_data in self.content_result_cache:
            try:
                await InterfaceContentStepResultMapper.insert_result(**result_data)
            except Exception as e:
                log.error(f"批量插入 content_result 失败: {e}, data={result_data}")
                raise

        log.info(f"批量插入 content_result: {len(self.content_result_cache)} 条")

    async def update_task_progress(
            self,
            task_result: InterfaceTaskResult
    ):
        """
        更新任务进度

        Args:
            task_result: 任务结果对象
        """
        current_time = time.time()
        last_time = self._last_progress_time.get(task_result.id, 0)

        if current_time - last_time < 1.0:
            return

        self._last_progress_time[task_result.id] = current_time

        await InterfaceTaskResultMapper.update_by_id(
            id=task_result.id,
            progress=task_result.progress,
            success_num=task_result.success_num,
            fail_num=task_result.fail_num,
        )

    async def finalize_task_result(
            self,
            task_result: InterfaceTaskResult
    ):
        """
        完成任务结果

        Args:
            task_result: 任务结果对象
        """
        if task_result.fail_num == 0:
            task_result.result = InterfaceAPIResultEnum.SUCCESS
        else:
            task_result.result = InterfaceAPIResultEnum.ERROR

        task_result.progress = 100
        task_result.total_use_time = GenerateTools.calculate_time_difference(
            task_result.map['start_time']
        )
        task_result.status = InterfaceAPIStatusEnum.OVER
        task_result.end_time = datetime.now()

        await InterfaceTaskResultMapper.update_by_id(
            id=task_result.id,
            progress=task_result.progress,
            total_use_time=task_result.total_use_time,
            status=task_result.status,
            result=task_result.result,
            end_time=task_result.end_time,
            success_num=task_result.success_num,
            fail_num=task_result.fail_num,
        )

    def clear_cache(self):
        """清空缓存"""
        self.api_result_cache.clear()
        self.content_result_cache.clear()
        self._progress_update_cache.clear()
        self._last_progress_time.clear()

    async def flush(self):
        """公开的刷新接口"""
        await self._flush_cache()
