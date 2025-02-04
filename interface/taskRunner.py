from typing import TypeVar, List

from app.mapper.interface import InterfaceTaskMapper
from app.model.base import User
from app.model.interface import InterfaceModel, InterFaceCaseModel, InterfaceTask, InterfaceTaskResultModel
from enums import InterfaceAPIResultEnum, StarterEnum
from utils import MyLoguru
from .io_sender import APISocketSender
from .runner import InterFaceRunner
from .starter import Starter
from .writer import InterfaceAPIWriter

log = MyLoguru().get_logger()
Interface = TypeVar('Interface', bound=InterfaceModel)
InterfaceCase = TypeVar('InterfaceCase', bound=InterFaceCaseModel)
Interfaces = List[Interface]
InterfaceCases = List[InterfaceCase]
InterfaceTaskResult = TypeVar('InterfaceTaskResult', bound=InterfaceTaskResultModel)


class TaskRunner:
    task: InterfaceTask
    result: str = InterfaceAPIResultEnum.SUCCESS

    def __init__(self,
                 starter: Starter | None,
                 io: APISocketSender | None):
        self.starter = starter
        self.io = io
        self.progress = 0

    async def runTask(self, taskId: int):
        """
        执行任务
        :param taskId: 任务Id
        :return:
        """
        self.task = await InterfaceTaskMapper.get_by_id(taskId)
        log.debug(f"running task {self.task} start by {self.starter.username}")

        task_result: InterfaceTaskResult = await InterfaceAPIWriter.init_interface_task(self.task,
                                                                                        starter=self.starter)
        try:
            apis: Interfaces = await InterfaceTaskMapper.query_apis(self.task.id)
            cases: InterfaceCases = await InterfaceTaskMapper.query_case(self.task.id)
            task_result.totalNumber = len(apis + cases)
            if apis:
                await self.__run_Apis(apis=apis, task_result=task_result)
            if cases:
                await self.__run_Cases(cases=cases, task_result=task_result)
        except Exception as e:
            log.exception(e)
            raise e
        finally:
            task_result.result = self.result
            log.debug(task_result.result)
            await InterfaceAPIWriter.write_interface_task_result(task_result)

    async def __run_Apis(self, apis: Interfaces, task_result: InterfaceTaskResult):
        """执行关联api"""
        for api in apis:
            flag: bool = await InterFaceRunner(self.starter, self.io).run_interface_by_task(
                interface=api,
                taskResult=task_result
            )
            log.debug(flag)
            await self.set_process(task_result)
            if flag:
                task_result.successNumber += 1
            else:
                self.result = InterfaceAPIResultEnum.ERROR
                task_result.failNumber += 1
            await self.io.clear_logs()

    async def __run_Cases(self, cases: InterfaceCases, task_result: InterfaceTaskResult):
        """执行关联case"""
        for case in cases:
            flag: bool = await InterFaceRunner(self.starter, self.io).run_interfaceCase_by_task(
                interfaceCase=case,
                taskResult=task_result
            )
            await self.set_process(task_result)
            if flag:
                task_result.successNumber += 1
                break
            else:
                task_result.result = InterfaceAPIResultEnum.ERROR
                task_result.failNumber += 1
            await self.io.clear_logs()

    async def set_process(self, task_result: InterfaceTaskResult):
        """写进度"""
        self.progress += 1
        task_result.progress = round(self.progress / task_result.totalNumber, 1) * 100
        return await InterfaceAPIWriter.write_task_process(task_result=task_result)
