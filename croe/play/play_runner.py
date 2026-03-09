import json
from typing import Optional

from app.mapper.play import PlayCaseMapper, PlayCaseVariablesMapper
from app.model.playUI import PlayCase, PlayTaskResult
from croe.a_manager.variable_manager import VariableManager
from croe.play.context import StepContentContext
from croe.play.executor import get_step_strategy
from croe.play.starter import UIStarter
from croe.play.writer import ContentResultWriter, PlayCaseResultWriter
from utils import log
from croe.play.browser import BrowserManagerFactory, PageManager, BrowserManager


class PlayRunner:

    def __init__(self, starter: UIStarter):
        self.starter = starter
        self.variable_manager = VariableManager()
        self.browser: Optional[BrowserManager] = None

    async def run_case(self, case_id: int, error_continue: bool = False):
        """

        :param case_id:
        :param error_continue: 错误继续
        :return:
        """
        try:
            play_case = await PlayCaseMapper.get_by_id(ident=case_id)
            log.info(f"查询到业务流用例  {play_case}")

            # 查询初始化变量
            await self.init_case_variables(play_case=play_case)

            # 初始化用例结果，
            case_result_writer = PlayCaseResultWriter(starter=self.starter)
            await case_result_writer.init_result(play_case=play_case, vars_info=self.variable_manager.variables)
            log.info(f"init case_result_writer = {case_result_writer}")

            # 执行用例
            await self.execute_case(play_case=play_case, case_result_writer=case_result_writer,
                                    error_continue=error_continue)
        except Exception as e:
            log.exception(e)
            raise e

    async def execute_case(self, play_case: PlayCase, case_result_writer: PlayCaseResultWriter,
                           task_result: PlayTaskResult = None,
                           error_continue: bool = False,
                           write_result_on_failure: bool = True) -> bool:
        """

        :param play_case:
        :param case_result_writer:
        :param task_result:
        :param error_continue: 错误继续 默认False
        :param write_result_on_failure: 失败时是否写入结果（重试场景下设为False）
        :return: bool - 用例执行是否成功
        """
        # 默认结果为成功
        page_manager = None
        case_success = True

        case_step_contents = await PlayCaseMapper.query_content_steps(case_id=play_case.id)
        case_step_content_length = len(case_step_contents)
        await self.starter.send(f"用例 {play_case.title} 执行开始。执行人 {self.starter.username}")
        await self.starter.send(f"查询到关联步骤 x {case_step_content_length} ...")

        if not case_step_contents:
            await self.starter.send("无可执行业务流步骤，结束执行")
            await self.starter.over()
            return case_success

        # 初始化。步骤结果写入器
        content_writer = ContentResultWriter(
            play_case_result_id=case_result_writer.play_case_result.id,
            play_task_result_id=task_result.id if task_result else None
        )
        try:
            page_manager = await self.__init_page()

            await self.starter.send(f"初始化页面成功")

            for index, step_content in enumerate(case_step_contents, start=1):
                await self.starter.send(
                    f"✍️✍️ {'=' * 10} 执行步骤 {index} ： {step_content} {'=' * 10}"
                )

                # 步骤开关 用例调试中使用 任务执行默认开启
                if step_content.enable == 0 and not task_result:
                    await self.starter.send(f"✍️✍️  执行步骤 {index} ： 调试禁用 跳过执行")
                    continue



                # 步骤 执行
                play_content_context = StepContentContext(
                    index=index,
                    page_manager=page_manager,
                    play_step_content=step_content,
                    variable_manager=self.variable_manager,
                    starter=self.starter,
                    play_step_result_writer=content_writer,
                    play_case_result_writer=case_result_writer
                )
                play_strategy = get_step_strategy(step_content.content_type)
                play_step_success = await play_strategy.execute(play_content_context)
                case_success &= play_step_success

                # 如果是失败 error_step true
                if not case_success and not error_continue:
                    break

        except Exception as e:
            log.exception(e)
            case_success = False  # 发生异常时标记为失败
            raise
        finally:
            await self.starter.send(f'执行完成 >> {play_case}, 结果: {case_success}')
            # 只有成功时 或者 允许失败写入时 才写入结果
            if case_success or write_result_on_failure:
                # 一次性写入 content results
                await content_writer.flush()
                await case_result_writer.write_result(case_success)
            await self.starter.over(case_result_writer.play_case_result.uid)
            await self.__clean(page_manager)
        return case_success

    async def __clean(self, page_manager: Optional[PageManager] = None):
        """
        清理资源
        """
        if page_manager:
            await page_manager.close()

        if self.browser:
            await self.browser.close_all()
        await self.variable_manager.clear()
        await self.starter.clear_logs()

    async def __init_page(self) -> PageManager:
        """
        初始化页面
        :return:
        """
        self.browser = await BrowserManagerFactory.get_instance()
        browser_context = await self.browser.get_browser()
        page = await browser_context.new_page()
        page_manager = PageManager()
        page_manager.set_page(page=page)
        return page_manager

    async def init_case_variables(self, play_case: PlayCase):
        """
        初始化变量
        :param play_case: UICaseModel
        :return:
        """
        try:
            if variables := await PlayCaseVariablesMapper.query_by(play_case_id=play_case.id):
                for case_var in variables:
                    _v = await self.variable_manager.trans(case_var.value)
                    await self.variable_manager.add_vars({case_var.key: _v})
                await self.starter.send(
                    f"🫳🫳 初始化用例变量 = {json.dumps(self.variable_manager.variables, ensure_ascii=False)}")
        except Exception as e:
            log.exception(e)
            raise e
