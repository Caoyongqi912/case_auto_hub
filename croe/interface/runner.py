#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Time : 2026/1/21
# @Author : cyq
# @File : runner
# @Software: PyCharm
# @Desc: 接口执行器

import asyncio
from typing import Union, Optional, Tuple, Any, Dict, List

from app.mapper.interfaceApi.interfaceGlobalMapper import InterfaceGlobalHeaderMapper
from app.mapper.interfaceApi.interfaceMapper import InterfaceMapper
from app.mapper.interfaceApi.interfaceCaseMapper import InterfaceCaseMapper
from app.mapper.interfaceApi.interfaceGroupMapper import InterfaceGroupMapper
from app.mapper.interfaceApi.interfaceVarsMapper import InterfaceVarsMapper
from app.mapper.project.env import EnvMapper
from app.model.base.env import EnvModel
from app.model.interfaceAPIModel.interfaceGlobalModel import InterfaceGlobalHeader

from croe.interface.executor.context import CaseStepContext, ExecutionContext
from croe.interface.executor.interface_executor import InterfaceExecutor
from croe.interface.executor.step_content import get_step_strategy
from croe.a_manager import VariableManager
from croe.interface.writer import ResultWriter  # BUG-D1:模块级单例已废弃,改用 self.result_writer
from app.model.interfaceAPIModel.interfaceResultModel import InterfaceResult
from croe.interface.starter import APIStarter
from croe.play.starter import UIStarter
from croe.interface.observability import (
    set_trace_id,
    clear_trace_id,
    get_trace_id,
)
from utils import log


class InterfaceRunner:
    """接口执行入口类"""

    __slots__ = ("starter", "variable_manager", "interface_executor", "global_headers", "result_writer")

    def __init__(self, starter: Union[UIStarter, APIStarter]) -> None:
        """
        初始化接口执行器

        Args:
            starter: 启动器实例（UI或API）
        """
        self.starter = starter
        self.variable_manager = VariableManager()
        self.global_headers: List[InterfaceGlobalHeader] = []
        # 每个 runner 独立的 result_writer,避免并发时缓存互相污染 (BUG-D1)
        from croe.interface.writer import ResultWriter
        self.result_writer = ResultWriter()
        self.interface_executor = InterfaceExecutor(
            starter=self.starter,
            variable_manager=self.variable_manager,
            global_headers=self.global_headers,
        )

    async def try_interface(
            self,
            interface_id: int,
            env_id: int
    ) -> Dict[str, Any]:
        """
        执行单个接口请求调试

        Args:
            interface_id: 接口id
            env_id: 环境id

        Returns:
            接口执行结果
        """
        interface = await InterfaceMapper.get_by_id(ident=interface_id)
        env = await self._get_running_env(env=env_id)
        await self.init_global_headers()
        result = await self.interface_executor.execute(
            interface=interface, env=env
        )
        return result

    async def try_group(
            self,
            group_id: int,
            env_id: int
    ) -> list:
        """
        执行接口组

        Args:
            group_id: 组ID
            env_id: 环境ID

        Returns:
            接口执行结果列表
        """
        interfaces = await InterfaceGroupMapper.query_association_interfaces(
            group_id=group_id
        )

        await self.init_global_headers()
        env = await self._get_running_env(env=env_id)
        results = []
        for interface in interfaces:
            await self.starter.send(f"✍️✍️  Execute    {interface}")
            result = await self.interface_executor.execute(
                interface=interface, env=env
            )
            results.append(result)
        return results

    async def run_interface_case(
            self,
            interface_case_id: int,
            env: Union[int, Any],
            error_stop: bool,
            task_result: Optional[Any] = None
    ) -> Tuple[bool, Optional[Any]]:
        """
        执行接口业务流用例

        Args:
            interface_case_id: 接口用例id
            env: 环境id或者对象
            error_stop: 是否遇到错误停止执行
            task_result: 在任务中执行时，需要传递任务执行结果

        Returns:
            Tuple[是否成功, 用例结果对象]
        """
        # [OBS-2] 生成 trace_id 注入 ContextVar, 跨 async/log/DB/WS 一致
        # 8 字符够区分并发 (1M 量级), 短, 日志不抢眼
        trace_id = set_trace_id()
        interface_case = await InterfaceCaseMapper.get_by_id(
            ident=interface_case_id
        )
        log.info(f"[trace={trace_id}] 查询到业务流用例  {interface_case}")

        if not interface_case:
            await self.starter.send(
                f"未通过{interface_case_id} 找到 相关业务流用例"
            )
            # 不要直接 return await self.starter.over() —
            # starter.over() 当前返回 None,task 模式调用方
            # `success, _ = await runner.run_interface_case(...)` 会 TypeError。
            # 显式返回 (False, None) 让调用方可以安全 unpack。
            await self.starter.over()
            return False, None

        case_content_steps = await InterfaceCaseMapper.query_steps(
            case_id=interface_case.id
        )
        await self.starter.send(
            f"用例 {interface_case.case_title} 执行开始。"
            f"执行人 {self.starter.username}"
        )
        await self.starter.send(
            f"查询到关联Step x {len(case_content_steps)} ..."
        )

        if not case_content_steps:
            await self.starter.send("无可执行业务流步骤，结束执行")
            await self.starter.over()
            return False, None

        await self.init_interface_case_vars(interface_case_id)
        await self.init_global_headers()

        target_env = await self._get_running_env(env=env)
        case_success = True

        case_result = await self.result_writer.init_case_result(
            interface_case=interface_case,
            starter=self.starter,
            env=target_env,
            task_result=task_result
        )
        # BUG-OBS-6 修复: 显式 log case_result_id, 不靠 trace_id 间接关联。
        # trace_id 是跨多 case 时的 correlation, 但排查单 case 时直接 grep
        # case_result_id 更直接 (trace_id 还要查 map 才知道是哪个 case)。
        log.debug(
            f"[BUG-OBS-6] case_result 初始化完成: "
            f"case_id={interface_case_id} "
            f"case_result_id={getattr(case_result, 'id', None)} "
            f"task_result_id={getattr(task_result, 'id', None) if task_result else None}"
        )

        try:
            # BUG-F8 修复: 把 runner 自有 result_writer 注入上下文,
            # 否则 step_content 仍走模块单例的 cache, 永远不被 flush
            execution_context = ExecutionContext(
                interface_case=interface_case,
                env=target_env,
                case_result=case_result,
                result_writer=self.result_writer,
                task_result=task_result
            )

            total_steps = len(case_content_steps)
            for index, step_content in enumerate(case_content_steps, start=1):
                await self.starter.send(
                    f"✍️✍️ {'=' * 20} EXECUTE_STEP {index} ： "
                    f"{step_content} {'=' * 20}"
                )

                # enable 仅在调试模式下生效 任务执行默认开启
                if step_content.enable == 0 and not task_result:
                    await self.starter.send(
                        f"✍️✍️  EXECUTE_STEP {index} ： 调试禁用 跳过执行"
                    )
                    # BUG-F6 修复: 用 round(index/total*100, 2) 替代整除截断,
                    # 避免 total=4 index=3 仍算 75% 但用户读 int 字段看到 75.0 一致。
                    case_result.progress = round(index / total_steps * 100, 2)
                    await self.result_writer.update_case_progress(case_result)
                    continue

                # 执行步骤  
                step_context = CaseStepContext(
                    index=index,
                    content=step_content,
                    execution_context=execution_context,
                    starter=self.starter,
                    variable_manager=self.variable_manager,
                )

                strategy = get_step_strategy(
                    step_content.content_type,
                    self.interface_executor
                )
                step_success = await strategy.execute(step_context)

                case_success = case_success and step_success

                # BUG-F6 修复: 进度=已完成步数 / 总步数 * 100, 保留 2 位小数。
                # 失败停在第 N 步时 progress 表示"跑到 N 步失败停了"的真实进度
                # (F5 已修: 不再 force 100%)。
                case_result.progress = round(index / total_steps * 100, 2)

                # 用例执行失败 且 配置了错误停止
                if not case_success and error_stop:
                    # BUG-F5 修复: 不再 force 100%, 保留 (index*100)//total
                    # 表示"跑到 N 步失败停了"的真实进度; finalize 用这个值写库。
                    # 强制 100 会让前端误以为 case 跑完了。
                    await self.starter.send(
                        f"⏭️⏭️  SKIP_STEP {index} ： 遇到错误已停止 "
                        f"(progress={case_result.progress}%)"
                    )
                    break

                await self.starter.send(
                    f"✍️✍️  EXECUTE_STEP {index} ： FINISH"
                )

            await self.starter.send(
                f"用例 {interface_case.case_title} 执行结束"
            )
            await self.starter.send(f"{'====' * 20}")
            # 日志通过 finalize_case_result(logs=...) 写入 interface_log 列;
            # 不要在这里给 case_result.interfaceLog (camelCase) 赋值 ——
            # 那个名字不是列,只会在实例上挂一个不会被 flush 的野属性。
            await self.result_writer.finalize_case_result(
                case_result=case_result,
                logs="".join(self.starter.logs)
            )

            return case_success, case_result

        except Exception as e:
            log.exception(f"执行业务流用例异常: {e}")
            return False, case_result

        finally:
            # [OBS-2] 清掉 trace_id, 下次 case 重新设
            clear_trace_id()
            await self.variable_manager.clear()
            # BUG-D1 修复:清空本 runner 的缓存,避免后续 runner 误用
            self.result_writer.clear_cache()
            # BUG-E1 修复:释放 httpx 连接,避免长跑 / 多次执行时连接泄漏
            try:
                await self.interface_executor.aclose()
            except Exception:
                pass
            if case_result is not None:
                await self.starter.over(case_result.id)
            else:
                await self.starter.over()

    async def run_interface_by_task(
            self,
            interface: Any,
            task_result_id: int,
            retry: int = 0,
            retry_interval: int = 0,
            env: Optional[Any] = None
    ) -> bool:
        """
        执行接口任务

        Args:
            interface: 接口对象
            task_result_id: 接口任务结果对象
            retry: 重试次数
            retry_interval: 重试间隔
            env: 环境对象

        Returns:
            是否执行成功
        """
        # BUG-RB2 修复: 跟另外 3 个入口 (try_interface / try_group / run_interface_case)
        # 对齐, 调 init_global_headers 把全局 header 注入到 executor.g_headers。
        # 旧版漏调, 任务执行时 g_headers 永远为 [], 用户配的全局 header (Authorization /
        # X-Tenant-Id) 全部丢失, 业务流和任务模式行为不一致, 排查极难。
        await self.init_global_headers()

        for attempt in range(retry + 1):
            result = await self.interface_executor.execute(
                interface=interface,
                env=env
            )
            # BUG-E6 修复: 第二个返回值 (success) 没了, 从 result['result'] 拿
            success = result['result']

            if success:
                await self.result_writer.write_interface_result(
                    interface_result=InterfaceResult(**result,
                                                     task_result_id=task_result_id)
                )
                return True

            if attempt == retry:
                await self.result_writer.write_interface_result(
                    interface_result=InterfaceResult(**result,
                                                     task_result_id=task_result_id)
                )
                await self.starter.send(
                    f"接口 {interface} 执行结果 FALSE"
                )
                return False

            await self.starter.send(
                f"接口 {interface} 执行结果 FALSE 第 {attempt + 1} 次重试"
            )
            if retry_interval:
                await asyncio.sleep(retry_interval)

        return False

    async def init_interface_case_vars(self, interface_case_id: int) -> None:
        """
        初始化业务流用例变量

        Args:
            interface_case_id: 业务流用例id
        """
        try:
            interface_case_vars = await InterfaceVarsMapper.query_by(
                case_id=interface_case_id
            )
            if interface_case_vars:
                var_dict = {}
                for var in interface_case_vars:
                    var_dict[var.key] = await self.variable_manager.trans(
                        var.value
                    )
                await self.variable_manager.add_vars(var_dict)
                await self.starter.send(
                    f"🫳🫳 初始化业务用例变量 = "
                    f"{self.variable_manager.variables}"
                )
        except Exception:
            # BUG-F4 修复:原版用 log.error 不带 traceback,且不通知用户,
            # 后续步骤继续用空变量跑,断言静默失败。
            # 改为 log.exception 保留 traceback + starter.send 通知用户,
            # 但不向外抛(让调用方可以选择继续或中止)。
            log.exception(f"初始化业务流用例变量失败 (case_id={interface_case_id})")
            try:
                await self.starter.send(
                    f"⚠️ 初始化业务用例变量失败,后续步骤将使用空变量 "
                    f"(case_id={interface_case_id})"
                )
            except Exception:
                # starter.send 自己挂了就别再吞,直接放过
                pass

    async def init_global_headers(self) -> List[InterfaceGlobalHeader]:
        """
        加载全局请求头并应用到 executor。

        Returns:
            加载到的全局 header 列表(可能为空)
        """
        global_headers = await InterfaceGlobalHeaderMapper.query_all()
        if not global_headers:
            log.info("未配置全局 header")
            return []

        await self.starter.send(
            f"🫳🫳 全局Headers已加载: {len(global_headers)} 条"
        )
        # 真正生效:注入到 executor.g_headers
        # (旧版读 self.global_headers 实例字段做日志,恒为 0,造成显示与实际不一致)
        self.interface_executor.g_headers = list(global_headers)
        return global_headers

    async def _get_running_env(self, env: Union[int, EnvModel]) -> Optional[EnvModel]:
        """
        获取当前环境
        """
        if isinstance(env, int):
            target_env = await EnvMapper.get_by_id(ident=env)
        else:
            target_env = env
        await self.starter.send(f"✍️✍️ 使用环境 {target_env}")
        return target_env
