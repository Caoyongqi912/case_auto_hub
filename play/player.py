#!/usr/bin/env python# -*- coding:utf-8 -*-# @Time : 2024/6/8# @Author : cyq# @File : player# @Software: PyCharm# @Desc:import asyncioimport osfrom http.client import responsesfrom typing import List, Dict, Anyfrom playwright.async_api import Page, LocatorAssertionsfrom playwright._impl._errors import TimeoutError, TargetClosedErrorfrom app.exception import UIRuntimeErrorfrom app.mapper.project.env import EnvMapperfrom app.mapper.ui.uiCaseMapper import UICaseStepApiMapper, UICaseStepSQLMapperfrom app.mapper.ui.uiCaseResultMapper import UICaseResultMapperfrom app.mapper.ui.uiCaseStepGroupMapper import UICaseStepGroupMapperfrom app.mapper.ui.uiCaseVariableMapper import UICaseVariableMapperfrom app.mapper.ui.uiEnvMapper import UIEnvMapperfrom app.mapper.ui.uiSubStepMapper import SubStepMapperfrom app.model.base import User, EnvModelfrom app.model.ui import UICaseModel, UICaseStepsModel, UICaseTaskResultBaseModel, UIResultModel, \    UIStepAPIModel, UIEnvModel, UIStepSQLModel, UITaskModelfrom enums.CaseEnum import Statusfrom app.mapper.ui.uiCaseMapper import UICaseMapperfrom app.mapper.ui.uiTaskMapper import UITaskMapperfrom play.exception import APIAssertExceptionfrom play.execCondition import ExecConditionfrom play.methods.api_on import APIOnfrom play.browser_content import get_browser_context, BrowserContextSingletonfrom play.methods.customize_method import CustomizeMethodsfrom play.apiSender import APISenderfrom play.methods.expect_method import ExpectMethodfrom play.methods.keyboard_methods import KeyboardMethodsfrom play.methods.page_methods import PageMethodsfrom play.sqlSender import SqlSenderfrom utils import log, GenerateToolsfrom utils.io_sender import SocketSenderfrom utils.wrapper_ import lockfrom utils.report import ReportPushfrom play.methods.customize_method import CustomizeMethodfrom play.writer import Writerfrom play.logWriter import LogWriterfrom play.extract import ExtractManagerfrom config import Configimport jenkinsasync def format_error_info(step_index: int, step: UICaseStepsModel,                            e: Exception) -> Dict[str, str]:    """    格式化错误执行信息    :param step_index: 步骤索引    :param step: UICaseStepsModel    :param e:Exception    :return:    """    error_info = {        "ui_case_err_step": step_index,        "ui_case_err_step_title": step.name,        "ui_case_err_step_msg": str(e)    }    log.error(type(e))    if isinstance(e, LocatorAssertions):        msg = str(e).split("Call log:")[0]        error_info[            "ui_case_err_step_msg"] = f"{e.__class__.__name__}❌: {msg} << "    elif isinstance(e, TimeoutError):        error_info[            "ui_case_err_step_msg"] = (f"{e.__class__.__name__}❌: Timeout waiting for locator \n"                                       f">> '{step.locator}' << ")    elif isinstance(e, AssertionError):        msg = str(e).split("Call log:")[0]        error_info["ui_case_err_step_msg"] = (f"{e.__class__.__name__}❌: method >> '{step.method}' << \n"                                              f"{msg}")    elif isinstance(e, TargetClosedError):        error_info["ui_case_err_step_msg"] = f"🚀 {e.__class__.__name__}❌: {str(e)}"    return error_infoasync def run_Tasks(taskIds: List[int], userId: int, jobName: str = None):    """    run for jenkins    :param taskIds:    :param userId:    :param jobName:    :return:    """    try:        tasks = [Player().run_task(task, userId) for task in taskIds]        await asyncio.gather(*tasks)    except Exception as e:        log.error(e)    finally:        if jobName:            log.info(f'=========={jobName}')            server = jenkins.Jenkins(url=Config.JENKINS_URL,                                     username=Config.JENKINS_USERNAME,                                     password=Config.JENKINS_PASSWORD)            log.info(f'build=========={jobName}')            server.build_job(jobName)class Player:    """    UI自动化 处理与执行    """    io: SocketSender = None    page: Page    browser_context: BrowserContextSingleton    em: ExtractManager    sql: SqlSender    env: UIEnvModel    api: APISender    def __init__(self, st: User = None):        self.io = SocketSender(st)        self.em = ExtractManager()    @lock("UI_TASK")    async def run_task(self, taskId: int):        """        执行ui TASK        :param taskId 待运行TASK ID        """        # 查询任务        task = await UITaskMapper.get_by_id(taskId)        await self.io.send(f'执行ui TASK:{task}')        # 初始化任务结果        task_base_result = await Writer.init_task_base_result(            task=task,            starter=self.io.user        )        # 查询任务用例        task_cases: List[UICaseModel] = await UITaskMapper.query_cases_by_task_id(task.id)        # 重试次数        retry_num = task.retry        # 执行用例        await self.retry_case(retry_num, task_cases, task_base_result)        await self.io.send(f'ui TASK:{task} 执行完成')        # 写入结果        try:            await Writer.write_base_result(task_base_result)        except Exception as e:            log.exception(e)            raise e        # finally:        #     await Writer.write_task_status(task, Status.WAIT)        # if task.isSend:        #     await Report().ui2weChat(task, task_base_result)    async def retry_case(self, retry_num: int, task_cases: List[UICaseModel], task_result: UICaseTaskResultBaseModel):        """        任务 用例重试执行机制执行        :param retry_num: 重试次数        :param task_cases: 任务用例        :param task_result: 初始化的任务结果模型        :return:        """        # 遍历每个任务用例        for index, case in enumerate(task_cases, start=1):            # 初始化用例结果            init_case_result = await Writer.init_case_result(case, self.io.user, task_result.id)            try:                # 执行用例，允许重试的次数为 retryNum + 1                for i in range(retry_num + 1):                    # 发送当前用例执行的信息和次数                    await self.io.send(f'执行ui case :{case} 次数:{i}')                    # 如果重试次数为0 或者是最终执行 失败才进行截图处理                    retry = retry_num == 0 or i == retry_num                    try:                        # 执行用例并获取结果                        flag = await self.__execute_case(case, init_case_result, task_result, retry)                    except Exception as e:                        # 用例执行失败，发送错误信息                        await self.io.send(f'用例:{case} 执行失败，错误信息: {str(e)}')                        # 如果已经达到最大重试次数，增加失败计数并清除日志，然后跳出循环                        if i == retry_num:                            task_result.fail_number += 1                            await self.io.clear_logs()                            break                        # 否则，进行重试                        await self.io.send(f'用例:{case} 执行失败  进行{i + 1}重试')                        continue                    # 如果用例执行成功，但未通过（flag为False）                    if not flag:                        # 如果已经达到最大重试次数，发送失败信息，增加失败计数并清除日志，然后跳出循环                        if i == retry_num:                            await self.io.send(f'用例:{case} 执行失败  重试次数已用完')                            task_result.fail_number += 1                            await self.io.clear_logs()                            break                        # 否则，进行重试                        await self.io.send(f'用例:{case} 执行失败  进行{i + 1}重试')                        continue                    else:                        # 用例执行成功，增加成功计数，清除证据和日志，然后跳出循环                        task_result.success_number += 1                        await self.em.clear()                        await self.io.clear_logs()                        break            finally:                # 停止当前用例的执行                pass    async def run_case(self, caseId: int):        """        根据用例ID查询用例并准备执行。        :param caseId: 需要执行的用例ID，类型为int。        :return: 无返回值。        """        # 通过用例ID获取用例信息        case = await UICaseMapper.get_by_id(caseId)        await self.io.send(f"准备执行用例 :{case}")        # 初始化用例结果，        init_case_result = await UICaseResultMapper.init_case_result_model(case, self.io.user)        # 执行用例        await self.__execute_case(case, init_case_result)    async def __execute_case(self,                             case: UICaseModel,                             case_result: UIResultModel,                             task_result: UICaseTaskResultBaseModel = None,                             retry: bool = True):        """        case 执行        :param case: 待执行用例        :param case_result: 初始化的用例结果模型        :param task_result: 初始化的批量执行结果模型        :param retry: 重试逻辑        :return:        """        error_info = {}        success_flag = True        try:            # 执行准备            case_steps: List[UICaseStepsModel] = await UICaseMapper.query_steps_by_caseId(case.id)            await self.io.send(f"获取用例步骤 :{len(case_steps)}")            if not case_steps:                await self.io.send(f"无用例步骤⚠️ 运行结束")                await Writer.write_case_result(case_result, self.io.logs)                return success_flag            # 初始化变量            await self.__init_extracts(case)            # 初始化play            try:                await self.__init_play()            except Exception as e:                success_flag = False                error_info = {                    "ui_case_err_step": -1,                    "ui_case_err_step_title": "-",                    "ui_case_err_step_msg": f"Service Error {str(e)}"                }                return success_flag            # OPEN URL            env = await UIEnvMapper.get_by_id(case.env_id)            try:                await CustomizeMethod.to_goto(self.page, env.domain, self.io, self.em)            except Exception as e:                await self.io.send(f"打开URL失败: {str(e)}")                success_flag = False                error_info = {                    "ui_case_err_step": -1,                    "ui_case_err_step_title": "-",                    "ui_case_err_step_msg": f"Open URL Error {str(e)}"                }                return success_flag            # 步骤执行            for i, step in enumerate(case_steps, start=1):                try:                    await self.io.send(f'执行步骤 >> step[{i}] : {step}')                    #  条件执行                    await self.__condition_execute(step, case_result)                    # 子步骤 判断执行                    if step.has_condition:                        await self.__execute_condition(step)                except Exception as e:                    log.exception(e)                    await self.io.send(f'some error : {str(e)}')                    await self.io.send(f"步骤执行失败 >> {step}")                    # is_ignore true 忽略本次失败 、继续                    if step.is_ignore:                        await self.io.send('step is ignore, continue...')                        continue                    success_flag = False                    # 是否重试 、重试次数用完                    if retry:                        error_info = await format_error_info(i, step, e)                        # 页面关闭、 接口请求失败 、不截图                        if not isinstance(e, (TargetClosedError, APIAssertException)):                            errorPath = await self.to_screenshot()                            error_info['ui_case_err_step_pic_path'] = errorPath                    break        finally:            log.debug(error_info)            await self.io.send(f'执行完成 >> {case}, 结果: {success_flag}')            await Writer.write_case_result(case_result, self.io, error_info)            await self.browser_context.close_page(self.page)            return success_flag    async def __execute_condition(self, step: UICaseStepsModel):        flag = await ExecCondition.invoke(step, self.io, self.em)        if flag:            subSteps = await SubStepMapper.query_by_stepId(step.id)            if len(subSteps) > 0:                for subStep in subSteps:                    await self.io.send(f'执行子步骤 >> {subStep}'),                    await self.__execute_step(subStep)            else:                await self.io.send("无子步骤 ...")        else:            await self.io.send(f'条件执行失败 >> {step.condition}')    async def __condition_execute(self, step: UICaseStepsModel, case_result: UIResultModel):        """        根据条件执行测试步骤。此函数负责根据提供的步骤模型和测试结果模型，执行相关的API或SQL前置和后置动作，        并根据步骤类型执行单个步骤或步骤组。        :param step: UICaseStepsModel类型的实例，代表当前要执行的测试步骤。        :param case_result: UIResultModel类型的实例，用于存储测试结果。        :return: 无返回值。如果在执行过程中遇到异常，将抛出异常。        """        try:            # 获取与当前步骤关联的API和SQL信息，如果存在的话。            stepApi = await UICaseStepApiMapper.get_by(stepId=step.id)            stepSql = await UICaseStepSQLMapper.get_by(stepId=step.id)            async def execute_pre_actions():                """                执行前置动作。如果步骤关联的API或SQL被配置为前置动作（b_or_a为True），                则分别执行相应的API或SQL操作。                """                if stepApi and stepApi.b_or_a:                    await self.__execute_api(stepApi, step, case_result)                if stepSql and stepSql.b_or_a:                    await self.__execute_sql(stepSql)            async def execute_post_actions():                """                执行后置动作。如果步骤关联的API或SQL被配置为后置动作（b_or_a为False），                则分别执行相应的API或SQL操作。                """                if stepApi and not stepApi.b_or_a:                    await self.__execute_api(stepApi, step, case_result)                if stepSql and not stepSql.b_or_a:                    await self.__execute_sql(stepSql)            # 如果当前步骤有关联的API或SQL，则执行前置动作、步骤本身和后置动作。            if stepApi or stepSql:                await execute_pre_actions()                await self.__execute_step(step, case_result)                await execute_post_actions()            else:                # 如果没有关联的API或SQL，根据步骤是否为组类型，决定执行组步骤还是单个步骤。                if step.is_group:                    await self.__execute_group_step(step)                else:                    await self.__execute_step(step, case_result)        except Exception as e:            # 记录日志或进行其他异常处理            log.error(f"Error in __condition_execute: {e}")            raise    async def __execute_group_step(self, step: UICaseStepsModel):        """        步骤组执行        :param step:        :return:        """        g_steps = await UICaseStepGroupMapper.query_steps_by_groupId(groupId=step.group_Id)        await self.io.send("===== 开始执行步骤组")        for i, step in enumerate(g_steps, start=1):            await self.__execute_step(step)        await self.io.send("===== 执行步骤组结束")    async def __execute_sql(self, stepSQl: UIStepSQLModel):        """        oracle 执行        :param stepSQl:        :return:        """        title = "前置" if stepSQl.b_or_a else "后置"        await self.io.send(f'执行{title}SQL >> {stepSQl.desc}')        newSql = await self.em.transform_target(stepSQl.sql_str)        # await self.sql.send_sql(newSql)    async def __execute_api(self, stepApi: UIStepAPIModel,                            step: UICaseStepsModel,                            case_result: UIResultModel):        """        执行前后置API调用        :param stepApi:        :param step:        :param case_result:        :return:        """        api = APISender(self.io, self.em)        title = "前置" if stepApi.b_or_a else "后置"        await self.io.send(f'执行{title}接口 >> {stepApi}')        env: EnvModel = await EnvMapper.get_by_id(stepApi.env_id)        # 请求        await api.send(env=env.url, stepApi=stepApi)        # 提取变量        if stepApi.extracts:            await api.add_extracts(stepApi.extracts)        # 断言        if stepApi.asserts:            await api.do_assert(stepApi=stepApi,                                     step=step,                                     case_result=case_result)    async def __execute_step(self,                             step: UICaseStepsModel, case_result: UIResultModel = None):        """        执行单步骤        :param step: 包含步骤信息的UICaseStepsModel实例        :param case_result: UIResultModel        :return: None        """        # 检查是否为自定义方法        if step.method in CustomizeMethods:            return await CustomizeMethod.invoke(self.page, step, self.io, self.em)        # 使用字典映射方法前缀到对应的处理函数        method_map = {            "expect": ExpectMethod.invoke,  # 断言            "on": APIOn.invoke,  # API监听            "keyboard": KeyboardMethods.invoke  # 键盘事件        }        # 根据方法前缀调用相应的处理函数        for prefix, handler in method_map.items():            if step.method.startswith(prefix):                return await handler(page=self.page, step=step, io=self.io, em=self.em, case_result=case_result)        # 打开新页面        if step.new_page:            self.page = await PageMethods.new_page(self.page,                                                   step)            return        # 常规操作        return await PageMethods.play(            page=self.page,            step=step        )    async def __init_play(self):        """        初始化playwright        指定            headless True            slow_mo 1s            dev超时5s            pro超时10s        :return:        """        try:            self.browser_context = await get_browser_context()            self.page = await self.browser_context.get_page()        except Exception as e:            log.exception(e)            raise UIRuntimeError("初始化浏览器失败")    async def __init_extracts(self, case: UICaseModel):        """        初始化变量        :param case: UICaseModel        :return:        """        # 初始化变量        variables = await UICaseVariableMapper.query_by(case_id=case.id)        await self.em.initBeforeVars(variables)        await self.io.send(f"初始化变量 :{self.em.variables}")    async def to_screenshot(self):        """        截图        :return:        """        try:            fileDate = GenerateTools.getTime(2)            fileName = f"{GenerateTools.uid()}.jpeg"            path = os.path.join(Config.ROOT, "play", "play_error_shot", fileDate, fileName)            await self.page.screenshot(                path=str(path),                full_page=True)            await self.io.send("完成失败截图✅")            return path        except Exception as e:            log.error(e)            await self.io.send(f"截图失败❌ {str(e)}")