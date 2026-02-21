from croe.play.context import StepContentContext
from croe.play.executor.step_content_strategy._base import StepBaseStrategy


class PlayInterfaceContentStrategy(StepBaseStrategy):
    """
    执行接口策略类
    """


    async def execute(self, step_context: StepContentContext) -> bool:
        pass