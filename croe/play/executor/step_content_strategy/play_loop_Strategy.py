from croe.play.context import StepContentContext
from croe.play.executor.step_content_strategy._base import StepBaseStrategy


class PlayLoopContentStrategy(StepBaseStrategy):
    """
    循环
    """
    async def execute(self, step_context: StepContentContext) -> bool:
        pass
