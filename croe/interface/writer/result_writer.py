#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Time : 2026/4/14
# @Author : cyq
# @File : result_writer.py
# @Software: PyCharm
# @Desc: 统一结果写入器

from datetime import datetime
from typing import Optional, List, Dict, Any

from sqlalchemy.ext.asyncio import AsyncSession
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
from app.model.interfaceAPIModel.interfaceTaskModel import InterfaceTask
from enums import InterfaceAPIStatusEnum, InterfaceAPIResultEnum, StepStatusEnum
from enums.CaseEnum import CaseStepContentType
from utils import GenerateTools, log
from croe.interface.starter import APIStarter

def _result_flag_to_bool(value: Any) -> bool:
    """

    背景: InterfaceAPIResultEnum.SUCCESS=True / .ERROR=False (bool),
    旧 InterfaceCaseResultEnum.SUCCESS="SUCCESS" / .ERROR="ERROR" (str)
    同名不同值, 写 Boolean 列时 bool("ERROR")=True 会静默写反。
    M7 已删 InterfaceCaseResultEnum, 这个 helper 留作防御:
    - bool: 原样返回
    - str: ERROR/FAIL/false/0/no -> False, 其它非空 -> True
    - None: False (保守, 不污染历史数据)
    - 其它: bool() 兜底
    """
    if value is None:
        return False
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in ("error", "fail", "false", "0", "no", "n"):
            return False
        return bool(lowered)
    return bool(value)

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

    MAX_CACHE_SIZE = 1000

    def __init__(self):
        self.api_result_cache: List[InterfaceResult] = []
        self.content_result_cache: List[Dict[str, Any]] = []

    def clear_cache(self) -> None:
        """
        清空所有缓存,run_interface_case 在 finally 调用以释放内存。

        之前用的是模块级单例 result_writer,缓存不会自动清,
        长跑 / 并发 case 会让 api_result_cache 越来越大、还会
        把别人的数据 flush 走。
        """
        self.api_result_cache.clear()
        self.content_result_cache.clear()

    async def init_task_result(
            self,
            task:InterfaceTask,
            starter:APIStarter,
            env:EnvModel=None
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
            task_name=task.interface_task_title,
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
            case_result.interface_task_result_id = task_result.id
            # 二是只 str(obj) 调试信息为零。case_result 还没 insert, 此刻日志没价值;
            # 等 insert 完再 log 更靠谱。

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
            if len(self.api_result_cache) >= self.MAX_CACHE_SIZE:
                await self._flush_cache()
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
            'status': StepStatusEnum.SUCCESS if success else StepStatusEnum.FAIL,
            'start_time': start_time,
            'use_time': use_time,
            **kwargs
        }

        if is_parent_step:
            return await InterfaceContentStepResultMapper.insert_result(**result_data)
        else:
            self.content_result_cache.append(result_data)
            if len(self.content_result_cache) >= self.MAX_CACHE_SIZE:
                await self._flush_cache()
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
            case_result: InterfaceCaseResult
    ):
        """
        更新用例进度

        每个步骤执行完立即更新，对前端友好

        Args:
            case_result: 用例结果对象
        """
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

        # 回填反向 FK: immediate 写入时 content_result_id 还是 NULL
        backfilled = await InterfaceResultMapper.backfill_content_result_id_fk(
            case_result_id=case_result.id
        )
        if backfilled:
            log.info(
                f"[BUG-F8-followup] 回填 interface_result.content_result_id: "
                f"{backfilled} 行 (case_result_id={case_result.id})"
            )

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

        try:
            recomputed = await InterfaceCaseResultMapper.recompute_case_result_nums(
                case_result_id=case_result.id,
                session=None,  # 走自己的事务, 不影响 finalize 主流程
            )
            log.info(
                f"[BUG-E8+E9] recompute case_result_nums: "
                f"total={recomputed['total']} success={recomputed['success']} "
                f"fail={recomputed['fail']} (case_result_id={case_result.id})"
            )
            # 同步内存对象 (后面 update_by_id 不带 total_num)
            case_result.total_num = recomputed["total"]
            case_result.success_num = recomputed["success"]
            case_result.fail_num = recomputed["fail"]
            if case_result.fail_num == 0:
                case_result.result = InterfaceAPIResultEnum.SUCCESS
            else:
                case_result.result = InterfaceAPIResultEnum.ERROR
        except Exception as e:
            # recompute 失败不影响 finalize 主流程, 保留旧值
            log.warning(f"[BUG-E8+E9] recompute_case_result_nums 失败, 用旧值: {e}")

        await InterfaceCaseResultMapper.update_by_id(
            id=case_result.id,
            use_time=case_result.use_time,
            status=case_result.status,
            result=case_result.result,
            progress=case_result.progress,
            success_num=case_result.success_num,
            fail_num=case_result.fail_num,
            interface_log=case_result.interface_log if logs else None,
        )

    async def _flush_cache(self):
        """
        刷新缓存，批量插入数据 。

        事务策略：
        - 单一事务包住 api_result + content_result 两次 bulk, 任一失败整体回滚
        - 事务路径失败 -> 进入降级路径, 降级自己再开一个事务逐条 commit
        - 缓存清空只在最后做, 失败时不丢缓存(其实也丢, 因为 retry 不在当前设计里;
          留 TODO: 把缓存重试也做掉)

        重要：
        - content_result_cache 中存储的是字典，需要先转换成模型
        - api_result_cache 中存储的是 InterfaceResult 模型
        """
        if self.api_result_cache or self.content_result_cache:
            log.info(
                f"开始刷新缓存: api_result={len(self.api_result_cache)}, "
                f"content_result={len(self.content_result_cache)}"
            )

        # 1. 主路径: 单事务批量
        bulk_ok = False
        try:
            async with InterfaceResultMapper.transaction() as session:
                if self.api_result_cache:
                    await self._bulk_insert_api_results(session=session)
                if self.content_result_cache:
                    await self._bulk_insert_content_results(session=session)
            bulk_ok = True
        except Exception as e:
            log.error(
                f"BUG-D4 路径: 批量事务失败, 整批回滚, 转入逐条降级: {e}"
            )

        # 2. 降级路径: 自管事务, 逐条 commit, 不被前面半写污染
        if not bulk_ok:
            await self._fallback_insert_api_results()
            await self._fallback_insert_content_results()

        self.api_result_cache.clear()
        self.content_result_cache.clear()

    async def _bulk_insert_api_results(self, session: AsyncSession) -> None:
        """
        批量插入 API 结果 。

        - 直接使用模型实例列表调用 bulk_insert_models
        - 缓存中已存储 InterfaceResult 模型实例
        """
        if not self.api_result_cache:
            return

        count = await InterfaceResultMapper.bulk_insert_models(
            self.api_result_cache, session=session
        )
        log.info(f"批量插入 api_result: {count} 条")

    async def _bulk_insert_content_results(self, session: AsyncSession) -> None:
        """
        批量插入步骤内容结果 。

        - 使用 InterfaceContentStepResultMapper.bulk_insert_results 方法
        - 该方法支持 Joined Table Inheritance，按 content_type 分组后批量插入
        - SQLAlchemy 自动处理基类表和子类表的插入
        """
        if not self.content_result_cache:
            return

        # skipped 由 mapper 内部统一 WARNING 输出,这里只记 inserted
        inserted, skipped = await InterfaceContentStepResultMapper.bulk_insert_results(
            self.content_result_cache, session=session
        )
        if skipped:
            log.warning(
                f"批量插入 content_result: inserted={inserted}, "
                f"skipped={skipped} (已由 mapper 落盘 WARNING, 见上方)"
            )
        else:
            log.info(f"批量插入 content_result: {inserted} 条")

    async def _fallback_insert_api_results(self):
        """
        逐条插入 API 结果（降级方案）

        当批量插入失败时，尝试逐条插入以确保数据不丢失
        """
        success_count = 0
        fail_count = 0

        for api_result in self.api_result_cache:
            try:
                await InterfaceResultMapper.insert(api_result)
                success_count += 1
            except Exception as e:
                fail_count += 1
                log.error(f"逐条插入 api_result 失败: {e}, api_name={getattr(api_result, 'api_name', 'unknown')}")

        log.info(f"逐条插入 api_result 完成: 成功={success_count}, 失败={fail_count}")

    async def _fallback_insert_content_results(self):
        """
        逐条插入步骤内容结果（降级方案）

        当批量插入失败时，尝试逐条插入以确保数据不丢失
        """
        success_count = 0
        fail_count = 0

        for result_data in self.content_result_cache:
            try:
                await InterfaceContentStepResultMapper.insert_result(**result_data)
                success_count += 1
            except Exception as e:
                fail_count += 1
                log.error(f"逐条插入 content_result 失败: {e}, content_name={result_data.get('content_name', 'unknown')}")

        log.info(f"逐条插入 content_result 完成: 成功={success_count}, 失败={fail_count}")

    async def update_task_progress(
            self,
            task_result: InterfaceTaskResult
    ):
        """
        更新任务进度

        Args:
            task_result: 任务结果对象
        """
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
        await self._flush_cache()

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

    async def flush(self):
        """公开的刷新接口"""
        await self._flush_cache()
