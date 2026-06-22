import datetime

from app.mapper.play.playStepGroupMapper import PlayStepGroupMapper
from utils import GenerateTools
from ._base import StepBaseStrategy
from ..play_method.result_types import StepExecutionResult
from ...context import StepContentContext, StepContext


class PlayGroupContentStrategy(StepBaseStrategy):
    """
    STEP GROUP
    """

    async def execute(self, step_context: StepContentContext) -> bool:
        """
        UI  步骤组执行
        :param step_context:
        :return:
        """
        groups = await PlayStepGroupMapper.query_steps_by_group_id(group_id=step_context.targetId)
        await step_context.starter.send(f"📦 组内共有 {len(groups)} 个步骤")
        if not groups:
            await step_context.starter.send(f"⚠️⚠️ 步骤组为空")
            return True
        
        start_time = datetime.datetime.now()
        
        GROUP_SUCCESS = True # 容器本身默成功
        # 为步骤组创建一个容器结果记录（作为组的标识） 子步骤执行完后更新写入
        group_container_result = StepExecutionResult(
            success=GROUP_SUCCESS, 
            message=f"步骤组: {step_context.play_step_content.content_name} Length: {len(groups)}"
        )
        # 暂存步骤组容器结果
        await self.write_result(
            start_time = start_time,
            result =group_container_result,
            step_context=step_context,
        )

        # 步骤组执行开始
        await step_context.starter.send(f"📦 开始执行步骤组: {step_context.play_step_content.content_name}")

        # 执行步骤组内的子步骤
        for i, group_step in enumerate(groups, start=1):
            await step_context.starter.send(f"✍️✍️  EXECUTE GROUP STEP {i} : {group_step.name}")
            # 创建临时的 PlayStepContent 用于子步骤
            from app.model.playUI.playStepContent import PlayStepContent
            from enums.CaseEnum import PlayStepContentType
            
            temp_step_content = PlayStepContent(
                content_name=group_step.name,
                content_desc=group_step.description,
                content_type=PlayStepContentType.STEP_PLAY,
                target_id=group_step.id
            )
            group_step_context = StepContentContext(
                index=i,
                play_step_content=temp_step_content,
                page_manager=step_context.page_manager,
                starter=step_context.starter,
                variable_manager=step_context.variable_manager,
                play_step_result_writer=step_context.play_step_result_writer,
                play_case_result_writer=step_context.play_case_result_writer,
            )
            
            # 创建子步骤上下文
            group_child_step_context = StepContext(
                step=group_step,
                page_manager=step_context.page_manager,
                starter=step_context.starter,
                variable_manager=step_context.variable_manager
            )
            
            step_start_time = datetime.datetime.now()
            result = await self.play_executor.execute(group_child_step_context)
            GROUP_SUCCESS &= result.success

            # 暂存子步骤结果
            await self.write_child_result(
                parent_index=step_context.index,
                start_time = step_start_time,
                result =result,
                step_context=group_step_context,
            )
            if not GROUP_SUCCESS:
                break
            


        # 步骤组执行完成
        end_time = datetime.datetime.now()
        use_time = GenerateTools.timeDiff(start_time, end_time)


        # 更新组结果
        await step_context.play_step_result_writer.update_content_result(
            step_index=step_context.index,
            success=GROUP_SUCCESS,
        )
    
        
        await step_context.starter.send(f"📦 步骤组执行完成，结果: {'成功' if  GROUP_SUCCESS else '失败'}")
        await step_context.starter.send(f"📦 用时: {use_time}")
        
        return GROUP_SUCCESS
        
        