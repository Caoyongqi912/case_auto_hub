#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Time : 2026/3/20
# @Author : cyq
# @File : play_condition_strategy
# @Software: PyCharm
# @Desc:
import datetime

from app.mapper.play.playConditionMapper import PlayConditionMapper
from croe.play.context import StepContentContext
from croe.play.executor.step_content_strategy._base import StepBaseStrategy
from croe.a_manager import ConditionManager
from croe.play.executor.play_method.result_types import StepExecutionResult

from utils import GenerateTools


class PlayConditionContentStrategy(StepBaseStrategy):
    """
    UI条件判断步骤执行策略
    """

    async def execute(self, step_context: StepContentContext) -> bool:
        """
        执行条件判断步骤
        :param step_context: 步骤上下文
        :return: 执行是否成功
        """
        start_time = datetime.datetime.now()

        condition = await PlayConditionMapper.get_by_id(
            ident=step_context.play_step_content.target_id
        )

        if not condition:
            await step_context.starter.send("❌ 条件配置不存在")
            return False

        condition_manager = ConditionManager(variable=step_context.variable_manager)
        condition_passed, condition_data = await condition_manager.invoke(
            condition,
            step_context.starter
        )

        condition_container_result = StepExecutionResult(
            success=True,
            message=f"条件判断: {condition.condition_key} {condition_data.get('operator')} {condition.condition_value} -> {'通过' if condition_passed else '未通过'}",
            assert_data=condition_data
        )

        await self.write_result(
            result=condition_container_result,
            start_time=start_time,
            step_context=step_context
        )

        if condition_passed:
            await step_context.starter.send("✅ 条件判断通过,开始执行子步骤")

            child_step_contents = await PlayConditionMapper.get_condition_step_contents(condition.id)

            if not child_step_contents:
                await step_context.starter.send("⚠️ 条件下无子步骤")
                return True

            await step_context.starter.send(f"📦 条件下共有 {len(child_step_contents)} 个子步骤")

            all_success = True
            for i, child_step_content in enumerate(child_step_contents, start=1):
                await step_context.starter.send(f"✍️ 执行条件子步骤 {i}: {child_step_content.content_name}")

                child_step_context = StepContentContext(
                    index=i,
                    play_step_content=child_step_content,
                    page_manager=step_context.page_manager,
                    starter=step_context.starter,
                    variable_manager=step_context.variable_manager,
                    play_step_result_writer=step_context.play_step_result_writer,
                )
                from croe.play.executor import get_step_strategy
                strategy = get_step_strategy(child_step_content.content_type)
                step_start_time = datetime.datetime.now()
                success = await strategy.execute(child_step_context)

                if not success:
                    all_success = False
                    await step_context.starter.send(f"❌ 子步骤执行失败,停止执行")
                    break

            end_time = datetime.datetime.now()
            use_time = GenerateTools.timeDiff(start_time, end_time)

            await step_context.play_step_result_writer.update_content_result(
                step_index=step_context.index,
                success=all_success
            )

            await step_context.starter.send(f"📦 条件步骤执行完成，结果: {'成功' if all_success else '失败'}")
            await step_context.starter.send(f"📦 用时: {use_time}")

            return all_success
        else:
            await step_context.starter.send("⏭️ 条件判断未通过,跳过子步骤")
            return True
