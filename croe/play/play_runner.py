import json
from typing import Sequence

from playwright.async_api import Page

from app.mapper.play import PlayCaseMapper, PlayCaseResultMapper, PlayCaseVariablesMapper, PlayStepContentMapper
from app.model.playUI import PlayCase, PlayCaseResult, PlayTaskResult
from croe.interface.manager.variable_manager import VariableManager
from croe.play.context import PlayExecutionContext, StepContentContext
from croe.play.executor import get_step_strategy
from croe.play.starter import UIStarter
from croe.play.writer import Writer
from utils import log
from croe.play.browser import BrowserManagerFactory


class PlayRunner:

    def __init__(self, starter: UIStarter):
        self.starter = starter
        self.variable_manager = VariableManager()

    async def run_case(self, case_id: int, error_stop: bool = True):
        """

        :param case_id:
        :param error_stop:
        :return:
        """

        play_case = await PlayCaseMapper.get_by_id(ident=case_id)
        await self.starter.send(f"准备执行用例 :{play_case}")

        # 初始化用例结果，
        case_result = await PlayCaseResultMapper.init_case_result(play_case=play_case,
                                                                  user=self.starter)

    async def execute_case(self, play_case: PlayCase, case_result: PlayCaseResult, task_result: PlayTaskResult,
                           error_stop: bool = True):
        """

        :param play_case:
        :param case_result:
        :param task_result:
        :param error_stop:
        :return:
        """
        # 默认结果为成功
        CASE_SUCCESS = True
        try:
            # todo query_contents
            case_step_contents = await PlayCaseMapper.query_content_steps(case_id=play_case.id)

            case_step_content_length = len(case_step_contents)

            await self.starter.send(f"用例 {play_case.title} 执行开始。执行人 {self.starter.username}")
            await self.starter.send(f"查询到关联Step x {case_step_content_length} ...")

            page = await self.__init_page()
            await self.starter.send(f"初始化页面成功")

            if not case_step_contents:
                await self.starter.send("无可执行业务流步骤，结束执行")
                return await self.starter.over()

            #   初始化 前置变量
            await self.init_case_variables(play_case=play_case, case_result=case_result)

            play_execute_context = PlayExecutionContext(
                play_case=play_case,
                starter=self.starter,
                case_result=case_result,
                task_result=task_result
            )
            for index, step_content in enumerate(case_step_contents, start=1):
                await self.starter.send(
                    f"✍️✍️ {'=' * 20} EXECUTE_STEP {index} ： {step_content} {'=' * 20}"
                )
                # todo progress
                case_result.progress = round(index / case_step_content_length, 2) * 100

                # 步骤开关 用例调试中使用 任务执行默认开启
                if step_content.enable == 0 and not task_result:
                    await self.starter.send(f"✍️✍️  EXECUTE_STEP {index} ： 调试禁用 跳过执行")
                    continue

                # 如果 CASE_SUCCESS 已经是 False 且需要错误停止，则跳过后续步骤
                if not CASE_SUCCESS and error_stop:
                    await self.starter.send(f"⏭️⏭️  SKIP_STEP {index} ： 遇到错误已停止")
                    continue

                play_content_context = StepContentContext(
                    index=index,
                    page=page,
                    play_step_content=step_content,
                    execution_context=play_execute_context,
                    variable_manager=self.variable_manager
                )
                play_strategy = get_step_strategy(step_content.content_type)
                play_step_success = await play_strategy.execute(play_content_context)
                CASE_SUCCESS &= play_step_success

                if not CASE_SUCCESS and error_stop:
                    case_result.progress = 100
                    break



        except Exception as e:
            log.exception(e)
            raise e

    @staticmethod
    async def __init_page() -> Page:
        """
        初始化页面
        :return:
        """
        browser = await BrowserManagerFactory.get_instance()
        browser_context = await browser.get_browser()
        page = await browser_context.new_page()
        return page

    async def init_case_variables(self, play_case: PlayCase, case_result: PlayCaseResult):
        """
        初始化变量
        :param play_case: UICaseModel
        :param case_result
        :return:
        """
        try:
            if variables := await PlayCaseVariablesMapper.query_by(play_case_id=play_case.id):
                for case_var in variables:
                    _v = await self.variable_manager.trans(case_var.value)
                    await self.variable_manager.add_vars({case_var.key: _v})
                await Writer.write_vars_info(case_result=case_result, extract_method="INIT", step_name="INIT",
                                             varsInfo=self.variable_manager.variables)
                await self.starter.send(
                    f"🫳🫳 初始化用例变量 = {json.dumps(self.variable_manager.variables, ensure_ascii=False)}")
        except Exception as e:
            log.exception(e)
            raise e
