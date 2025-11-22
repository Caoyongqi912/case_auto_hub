import asyncio
import time
from typing import TypeVar, List

from app.mapper.interface import InterfaceTaskMapper
from app.mapper.project.env import EnvMapper
from app.mapper.project.pushMapper import PushMapper
from app.model.base import EnvModel
from app.model.interface import InterfaceModel, InterFaceCaseModel, InterfaceTask, InterfaceTaskResultModel
from enums import InterfaceAPIResultEnum
from utils import MyLoguru
from utils.report import ReportPush
from .starter import APIStarter
from .runner import InterFaceRunner
from .writer import InterfaceAPIWriter

log = MyLoguru().get_logger()
Interface = TypeVar('Interface', bound=InterfaceModel)
InterfaceCase = TypeVar('InterfaceCase', bound=InterFaceCaseModel)
Interfaces = List[Interface]
InterfaceCases = List[InterfaceCase]
InterfaceTaskResult = TypeVar('InterfaceTaskResult', bound=InterfaceTaskResultModel)
InterfaceEnv = TypeVar("InterfaceEnv", bound=EnvModel)

CASE = "CASE"
API = "API"


class TaskRunner:
    task: InterfaceTask

    def __init__(self, starter: APIStarter):
        self.starter = starter
        self.progress = 0
        self._last_progress_update = 0  # 记录上次更新进度的时间
        self._progress_update_interval = 0.5  # 最小更新间隔（秒）

    async def set_process(self, task_result: InterfaceTaskResult):
        """写进度"""
        self.progress += 1

        current_time = time.time()
        # 只有超过间隔时间或进度完成时才更新
        if (current_time - self._last_progress_update >= self._progress_update_interval or
                self.progress >= task_result.totalNumber):
            task_result.progress = round((self.progress / task_result.totalNumber) * 100, 1)
            await InterfaceAPIWriter.write_task_process(task_result=task_result)
            self._last_progress_update = current_time

    async def write_process_result(self, flag: bool, task_result: InterfaceTaskResult):
        await self.set_process(task_result)
        if flag:
            task_result.successNumber += 1
        else:
            task_result.failNumber += 1

    async def runTask(self, taskId: int, env_id: int = None, options: List[str] = None):
        """
        执行任务
        :param taskId: 任务Id
        :param env_id: 环境
        :param options [API,CASE]
        :return:
        """
        env: InterfaceEnv = None
        self.task = await InterfaceTaskMapper.get_by_id(taskId)
        log.debug(f"running task {self.task} start by {self.starter.username}")
        if env_id:
            env: InterfaceEnv = await EnvMapper.get_by_id(env_id)

        task_result: InterfaceTaskResult = await InterfaceAPIWriter.init_interface_task(self.task,
                                                                                        starter=self.starter)

        try:
            task_result.totalNumber = 0
            if API in options:
                apis: Interfaces = await InterfaceTaskMapper.query_apis(self.task.id)
                if apis:
                    task_result.totalNumber += len(apis)
                    await self.__run_Apis(apis=apis, task_result=task_result, env=env)
            if CASE in options:
                cases: InterfaceCases = await InterfaceTaskMapper.query_case(self.task.id)
                if cases:
                    task_result.totalNumber += len(cases)
                    await self.__run_Cases(cases=cases, task_result=task_result, env=env)
        except Exception as e:
            log.exception(e)
            raise e
        finally:
            if task_result.failNumber > 0:
                task_result.result = InterfaceAPIResultEnum.ERROR
            else:
                task_result.result = InterfaceAPIResultEnum.SUCCESS
            log.debug(task_result.result)
            await InterfaceAPIWriter.write_interface_task_result(task_result)
            if self.task.push_id:
                push = await PushMapper.get_by_id(self.task.push_id)
                rp = ReportPush(push_type=push.push_type, push_value=push.push_value)
                await rp.push(self.task, task_result)

    async def __run_Apis(self, apis: Interfaces, task_result: InterfaceTaskResult, env: InterfaceEnv = None):
        """执行关联api"""
        parallel = self.task.parallel
        # 顺序执行
        if parallel == 0:
            return await self.__run_api_by_sequential_execution(apis, task_result, env)

        semaphore = asyncio.Semaphore(parallel)  # 限制并行数量为 parallel
        await self.starter.send(f"并行数量 {parallel}")
        lock = asyncio.Lock()  # 保护共享资源
        tasks = []
        for api in apis:
            task = asyncio.create_task(
                self.__run_single_api_with_semaphore_and_lock(api, task_result, semaphore, lock, env)
            )
            tasks.append(task)
        await asyncio.gather(*tasks)

    async def __run_api_by_sequential_execution(self,
                                                apis: Interfaces,
                                                task_result: InterfaceTaskResult,
                                                env: InterfaceEnv = None):
        """
        顺序执行
        :param apis
        :param task_result
        :param env
        """
        for api in apis:
            flag: bool = await InterFaceRunner(self.starter).run_interface_by_task(
                interface=api,
                taskResult=task_result,
                env=env
            )
            await self.write_process_result(flag, task_result)
            await self.starter.clear_logs()

    async def __run_single_api_with_semaphore_and_lock(self,
                                                       api: Interface,
                                                       task_result: InterfaceTaskResult,
                                                       semaphore: asyncio.Semaphore,
                                                       lock: asyncio.Lock,
                                                       env: InterfaceEnv = None):
        """
        执行单个 API，限制并行数量，并保护共享资源
        :param api 待执行API
        :param task_result 任务结果
        :param semaphore 信号
        :param lock 锁
        :param env 执行环境
        """
        async with semaphore:  # 限制并行数量
            flag: bool = await InterFaceRunner(self.starter).run_interface_by_task(
                interface=api,
                taskResult=task_result,
                env=env
            )

            # 使用锁保护共享资源的修改
            async with lock:
                await self.write_process_result(flag, task_result)
            await self.starter.clear_logs()

    async def __run_Cases(self, cases: InterfaceCases, task_result: InterfaceTaskResult, env: InterfaceEnv = None):
        """执行关联case"""
        for case in cases:
            flag: bool = await InterFaceRunner(self.starter).run_interCase(
                interfaceCaseId=case.id,
                task=task_result,
                env_id=env,
                error_stop=True #任务执行默认True
            )
            await self.set_process(task_result)
            if flag:
                task_result.successNumber += 1
            else:
                task_result.failNumber += 1
            await self.starter.clear_logs()
