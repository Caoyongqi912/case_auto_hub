from croe.play.context import StepContentContext
from croe.play.executor.step_content_strategy._base import StepBaseStrategy


class PlayAssertContentStrategy(StepBaseStrategy):
    """
    断言
    """

    async def execute(self, step_context: StepContentContext) -> bool:
        pass
