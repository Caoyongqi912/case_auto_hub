"""app/mapper/play/* Mapper 单元测试覆盖"""

import inspect

import pytest

# --------------------------------------------------------------------------- #
# playTaskMapper
# --------------------------------------------------------------------------- #

class TestPlayTaskMapper:
    """PlayTaskMapper 任务 mapper 测试。"""

    def test_class_exists_and_inherits_mapper(self):
        """PlayTaskMapper 应继承 Mapper 基类。"""
        from app.mapper.play.playTaskMapper import PlayTaskMapper
        from app.mapper import Mapper
        assert issubclass(PlayTaskMapper, Mapper)

    def test_model_is_play_task(self):
        """__model__ 应是 PlayTask。"""
        from app.mapper.play.playTaskMapper import PlayTaskMapper
        from app.model.playUI import PlayTask
        assert PlayTaskMapper.__model__ is PlayTask

    def test_query_case_method_exists(self):
        """query_case 应存在 (task_runner 依赖此方法)。"""
        from app.mapper.play.playTaskMapper import PlayTaskMapper
        assert hasattr(PlayTaskMapper, "query_case")
        # classmethod 走 descriptor, 需要用 __func__ 取原函数
        raw = PlayTaskMapper.query_case.__func__
        assert inspect.iscoroutinefunction(raw)

    def test_set_task_status_method_exists(self):
        """set_task_status 应存在 (writer 依赖此方法)。"""
        from app.mapper.play.playTaskMapper import PlayTaskMapper
        assert hasattr(PlayTaskMapper, "set_task_status")
        assert inspect.iscoroutinefunction(PlayTaskMapper.set_task_status.__func__)

    def test_query_case_signature_accepts_task_id(self):
        """query_case 签名应接受 taskId 参数 (业务约定)。"""
        from app.mapper.play.playTaskMapper import PlayTaskMapper
        sig = inspect.signature(PlayTaskMapper.query_case)
        # 必有 taskId 参数 (无论大小写, 业务用驼峰 taskId)
        params = list(sig.parameters.keys())
        assert "taskId" in params, f"query_case 应有 taskId 参数, 实际 {params}"

# --------------------------------------------------------------------------- #
# playCaseMapper
# --------------------------------------------------------------------------- #

class TestPlayCaseMapper:
    """PlayCaseMapper 用例 mapper 测试。"""

    def test_class_inherits_mapper(self):
        from app.mapper.play.playCaseMapper import PlayCaseMapper
        from app.mapper import Mapper
        assert issubclass(PlayCaseMapper, Mapper)

    def test_model_is_play_case(self):
        from app.mapper.play.playCaseMapper import PlayCaseMapper
        from app.model.playUI import PlayCase
        assert PlayCaseMapper.__model__ is PlayCase

    def test_query_content_steps_exists(self):
        """query_content_steps 应存在 (runner 依赖此方法拿 case 的步骤列表)。"""
        from app.mapper.play.playCaseMapper import PlayCaseMapper
        assert hasattr(PlayCaseMapper, "query_content_steps")
        assert inspect.iscoroutinefunction(PlayCaseMapper.query_content_steps.__func__)

    def test_init_case_result_exists(self):
        """init_case_result 应存在 (case_result_writer 依赖此方法)。

        实际定义在 PlayCaseResultMapper 而非 PlayCaseMapper, 因为 init 的是结果行而非用例行。
        """
        from app.mapper.play.playCaseMapper import PlayCaseResultMapper
        assert hasattr(PlayCaseResultMapper, "init_case_result")
        assert inspect.iscoroutinefunction(PlayCaseResultMapper.init_case_result.__func__)

    def test_set_case_result_exists(self):
        """set_case_result 应存在 (case_result_writer 依赖此方法写最终结果)。

        实际定义在 PlayCaseResultMapper, 落库最终 result 行。
        """
        from app.mapper.play.playCaseMapper import PlayCaseResultMapper
        assert hasattr(PlayCaseResultMapper, "set_case_result")
        assert inspect.iscoroutinefunction(PlayCaseResultMapper.set_case_result.__func__)

    def test_init_case_result_takes_user_param(self):
        """init_case_result 应接受 user 参数 (UIStarter)。"""
        from app.mapper.play.playCaseMapper import PlayCaseResultMapper
        sig = inspect.signature(PlayCaseResultMapper.init_case_result)
        params = list(sig.parameters.keys())
        # 第一参数 cls, 第二参数 play_case, 第三参数 user, 可选 task_result_id / vars_list
        assert "play_case" in params
        assert "user" in params
        assert "task_result_id" in params
        assert "vars_list" in params

    def test_query_content_steps_takes_case_id(self):
        """query_content_steps 应接受 case_id 参数。"""
        from app.mapper.play.playCaseMapper import PlayCaseMapper
        sig = inspect.signature(PlayCaseMapper.query_content_steps)
        params = list(sig.parameters.keys())
        assert "case_id" in params

# --------------------------------------------------------------------------- #
# playResultMapper
# --------------------------------------------------------------------------- #

class TestPlayResultMapper:
    """PlayResultMapper 结果 mapper 测试 (P-1-1 修复后无 raise e)。"""

    def test_class_inherits_mapper(self):
        from app.mapper.play.playResultMapper import PlayContentResultMapper
        from app.mapper import Mapper
        assert issubclass(PlayContentResultMapper, Mapper)

    def test_model_is_play_step_content_result(self):
        from app.mapper.play.playResultMapper import PlayContentResultMapper
        from app.model.playUI.PlayResult import PlayStepContentResult
        assert PlayContentResultMapper.__model__ is PlayStepContentResult

    def test_set_result_exists(self):
        """set_result 应存在 (add_content_result 走这条路径写单步结果)。"""
        from app.mapper.play.playResultMapper import PlayContentResultMapper
        assert hasattr(PlayContentResultMapper, "set_result")
        assert inspect.iscoroutinefunction(PlayContentResultMapper.set_result.__func__)

    def test_save_result_batch_exists(self):
        """save_result_batch 应存在 (ContentResultWriter.flush 依赖此批量写)。"""
        from app.mapper.play.playResultMapper import PlayContentResultMapper
        assert hasattr(PlayContentResultMapper, "save_result_batch")
        assert inspect.iscoroutinefunction(PlayContentResultMapper.save_result_batch.__func__)

    def test_no_bare_raise_e_p_1_1(self):
        """playResultMapper.py 不应有 `raise e`。"""
        with open("app/mapper/play/playResultMapper.py", "r", encoding="utf-8") as fp:
            src = fp.read()
        # 排除注释行
        code_only = "\n".join(
            ln for ln in src.splitlines()
            if ln.strip() and not ln.strip().startswith("#")
        )
        import re
        matches = re.findall(r"^\s+raise\s+e\s*$", code_only, re.MULTILINE)
        assert len(matches) == 0, (
            f"playResultMapper.py 仍有 {len(matches)} 处 `raise e`, 应改 bare `raise`"
        )

# --------------------------------------------------------------------------- #
# playStepGroupMapper
# --------------------------------------------------------------------------- #

class TestPlayStepGroupMapper:
    """PlayStepGroupMapper 步骤组 mapper 测试。"""

    def test_class_inherits_mapper(self):
        from app.mapper.play.playStepGroupMapper import PlayStepGroupMapper
        from app.mapper import Mapper
        assert issubclass(PlayStepGroupMapper, Mapper)

    def test_query_steps_by_group_id_exists(self):
        """query_steps_by_group_id 应存在 (group_strategy 依赖此方法拿组内步骤)。"""
        from app.mapper.play.playStepGroupMapper import PlayStepGroupMapper
        assert hasattr(PlayStepGroupMapper, "query_steps_by_group_id")
        assert inspect.iscoroutinefunction(PlayStepGroupMapper.query_steps_by_group_id.__func__)

# --------------------------------------------------------------------------- #
# playConditionMapper
# --------------------------------------------------------------------------- #

class TestPlayConditionMapper:
    """PlayConditionMapper 条件 mapper 测试。"""

    def test_class_inherits_mapper(self):
        from app.mapper.play.playConditionMapper import PlayConditionMapper
        from app.mapper import Mapper
        assert issubclass(PlayConditionMapper, Mapper)

    def test_get_condition_step_contents_exists(self):
        """get_condition_step_contents 应存在 (condition_strategy 拿子步骤用)。

        注意: 实际方法名是 get_condition_step_contents 而非 query_steps_by_condition_id,
        业务约定: condition_id 入参 -> List[PlayStepContent] 顺序返回。
        """
        from app.mapper.play.playConditionMapper import PlayConditionMapper
        assert hasattr(PlayConditionMapper, "get_condition_step_contents")
        raw = PlayConditionMapper.get_condition_step_contents.__func__
        assert inspect.iscoroutinefunction(raw)
        sig = inspect.signature(raw)
        assert "condition_id" in sig.parameters

# --------------------------------------------------------------------------- #
# playStepMapper
# --------------------------------------------------------------------------- #

class TestPlayStepMapper:
    """PlayStepMapper 步骤 mapper 测试。"""

    def test_class_inherits_mapper(self):
        from app.mapper.play.playStepMapper import PlayStepV2Mapper
        from app.mapper import Mapper
        assert issubclass(PlayStepV2Mapper, Mapper)

# --------------------------------------------------------------------------- #
# playConfigMapper
# --------------------------------------------------------------------------- #

class TestPlayConfigMapper:
    """PlayConfigMapper 配置 mapper 测试。"""

    def test_class_inherits_mapper(self):
        from app.mapper.play.playConfigMapper import PlayConfigMapper
        from app.mapper import Mapper
        assert issubclass(PlayConfigMapper, Mapper)
