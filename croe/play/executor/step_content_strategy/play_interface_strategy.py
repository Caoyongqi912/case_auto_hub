import datetime

from app.mapper.interface import InterfaceMapper
from croe.interface.executor.interface_executor import InterfaceExecutor
from croe.interface.writer import write_interface_result
from croe.play.context import StepContentContext
from croe.play.executor.play_method.result_types import StepExecutionResult
from croe.play.executor.step_content_strategy._base import StepBaseStrategy
from utils import log


class PlayInterfaceContentStrategy(StepBaseStrategy):
    """
    执行接口策略类
    """

    async def execute(self, step_context: StepContentContext) -> bool:
        start_time = datetime.datetime.now()

        try:
            interface_executor = InterfaceExecutor(starter=step_context.starter,
                                                   variable_manager=step_context.variable_manager)

            interface = await InterfaceMapper.get_by_id(ident=step_context.play_step_content.target_id)
            result, success = await interface_executor.execute(interface=interface)

            interface_result = await write_interface_result(
                **result,
            )

            log.debug(f"interface_result {interface_result}")
            await self.write_result(
                result = StepExecutionResult(
                    success=success,
                    content_target_result_id=interface_result.id,

                ),
                start_time=start_time,
                step_context=step_context
            )

            return success
        except Exception as e:
            log.exception(f"PlayInterfaceContentStrategy {e}")
            return False
