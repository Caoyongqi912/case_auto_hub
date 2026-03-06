import datetime

from typing_extensions import assert_type

from croe.a_manager import AssertManager
from croe.play.context import StepContentContext
from croe.play.executor.play_method.result_types import StepExecutionResult
from croe.play.executor.step_content_strategy._base import StepBaseStrategy
from utils import log


class PlayAssertContentStrategy(StepBaseStrategy):
    """
    断言
    """

    async def execute(self, step_context: StepContentContext) -> bool:
        start_time = datetime.datetime.now()

        try:
            _assert_exec = AssertManager(variables=step_context.variable_manager.variables)
            assert_list = step_context.play_step_content.assert_list
            if not assert_list:
                await step_context.starter.send(
                    f"🆚🆚 断言:  ⚠️⚠️ 未配置断言"
                )
                return False
            assert_list_info, assert_success = await _assert_exec.assert_content_list(assert_list)

            result = StepExecutionResult(
                success=assert_success,
                error_type='assertion_failed',
                assert_data=assert_list_info,
            )
            await self.write_result(
                result=result,
                step_context=step_context,
                start_time=start_time,
            )

            return assert_success
        except Exception as e:
            log.exception(f"PlayAssertContentStrategy Error {e}")
            await step_context.starter.send(f"❌ 断言执行失败: {e}")
            return False
