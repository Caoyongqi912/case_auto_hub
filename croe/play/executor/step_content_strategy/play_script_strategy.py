import datetime
import json

from croe.play.executor.play_method.result_types import StepExecutionResult
from croe._manager import ScriptManager, ScriptSecurityError
from croe.play.executor.step_content_strategy._base import StepBaseStrategy
from croe.play.context import StepContentContext
from enums import ExtractTargetVariablesEnum
from utils import log


class PlayScriptContentStrategy(StepBaseStrategy):

    async def execute(self, step_context: StepContentContext):
        """执行脚本步骤"""

        script_text = step_context.play_step_content.script_text
        start_time = datetime.datetime.now()
        script_vars = None
        try:
            if script_text:
                try:
                    script_manager = ScriptManager()
                    _extracted_vars = script_manager.execute(script_text)
                    await step_context.variable_manager.add_vars(_extracted_vars)
                    await step_context.starter.send(f"🫳🫳  脚本变量 = {json.dumps(_extracted_vars, ensure_ascii=False)}")
                    script_vars = [{
                        ExtractTargetVariablesEnum.KEY: k,
                        ExtractTargetVariablesEnum.VALUE: v,
                        ExtractTargetVariablesEnum.Target: ExtractTargetVariablesEnum.StepScript
                    } for k, v in _extracted_vars.items()]
                except ScriptSecurityError as e:
                    await step_context.starter.send(f"脚本执行安全错误: {e}")
                    return False

            log.info(f'play step script. write {script_vars}')
            await self.write_result(
                result=StepExecutionResult(success=True,
                                           extract_data=script_vars
                                           ),
                start_time=start_time,
                step_content=step_context
            )

            return True

        except Exception as e:
            await step_context.starter.send(f"❌ 脚本执行失败: {e}")
            return False
