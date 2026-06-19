"""
[BUG-P-1-1 + P-1-2 + P-1-3 + P-1-4 + P-1-5 + P-1-6 + P-1-7 + P-1-8]
8 个 P1 高 ROI 隐藏问题一锅端, 来自 PLAY_REVIEW_2026_06_21。

BUG-P-1-1: app/mapper/play/*.py 32 处 `except Exception as e: ...; raise e`
        吞 traceback。修: 全部改 `raise` (bare re-raise, 保留 traceback);
        4 处 `log.error(e)` 改 `log.exception(...)` 把 traceback 写进日志。

BUG-P-1-2: app/model/playUI/playCase.py:PlayCaseResult.ui_case_Id 大写 I
        错属性名。修: 加 ui_case_id property (read+write) 兼容; mapper 和
        schema 改用 ui_case_id (schema 用 alias 兼容 ui_case_Id 入参)。

BUG-P-1-3: app/model/playUI/playTask.py:PlayTaskResult.rate_number 之前
        Column(INTEGER) 但 writer 用 round(..., 2) 写 float, MySQL 静默截断。
        修: 改 Column(Float) 保留小数, 已有部署需手动跑迁移。

BUG-P-1-4: croe/play/writer.py:PlayCaseResultWriter.write_result 参数 SUCCESS
        (大写) 违反 PEP 8。修: 改 success (snake_case)。

BUG-P-1-5: croe/play/writer.py:ContentResultWriter.__repr__ 末尾双 `> />`
        拼写错误。修: 改单 `/>` 收尾。

BUG-P-1-6: croe/play/writer.py:ContentResultWriter.update_content_result 之前
        只更新 content_result 字段, use_time 是占位时的初值。修: 重算
        use_time = now - start_time。

BUG-P-1-7: croe/play/play_runner.py:__clean / __init_page 双下划线触发 name
        mangling, 子类化/mock 拿不到。修: 改 _clean / _init_page (单下划线)。

BUG-P-1-8: croe/play/play_runner.py:init_case_variables 之前失败 raise e,
        跟 error_continue 语义冲突。修: 失败只 log + warning, 不 raise。
"""
import inspect
import re

import pytest

from tests.croe.play._bug_ids import (
    BUG_P_1_1, BUG_P_1_2, BUG_P_1_3, BUG_P_1_4, BUG_P_1_5,
    BUG_P_1_6, BUG_P_1_7, BUG_P_1_8,
)


# --------------------------------------------------------------------------- #
# BUG-P-1-1: mapper 全局无 raise e
# --------------------------------------------------------------------------- #

# 32 处应该全部从 raise e 改成 raise (bare re-raise)。
MAPPER_FILES_WITH_RAISE_E = [
    "app/mapper/play/playResultMapper.py",
    "app/mapper/play/playTaskMapper.py",
    "app/mapper/play/playConditionMapper.py",
    "app/mapper/play/playStepMapper.py",
    "app/mapper/play/playStepGroupMapper.py",
    "app/mapper/play/playConfigMapper.py",
    "app/mapper/play/playCaseMapper.py",
]


@pytest.mark.parametrize("mapper_file", MAPPER_FILES_WITH_RAISE_E)
def test_bug_p_1_1_no_bare_raise_e_in_mapper(mapper_file):
    """[BUG-P-1-1] mapper 不应有 `raise e` (会丢 traceback), 改 `raise`。"""
    with open(mapper_file, "r", encoding="utf-8") as fp:
        src = fp.read()
    # 排除注释行 (注释里允许说 "raise e 之前是什么样" 的描述)
    code_lines = [
        ln for ln in src.splitlines()
        if ln.strip() and not ln.strip().startswith("#")
    ]
    code_only = "\n".join(code_lines)
    matches = re.findall(r"^\s+raise\s+e\s*$", code_only, re.MULTILINE)
    assert len(matches) == 0, (
        f"[{BUG_P_1_1}] {mapper_file} 还有 {len(matches)} 处 `raise e`, "
        f"应改 bare `raise` 保留 traceback。\n匹配:\n{matches}"
    )


def test_bug_p_1_1_log_error_e_replaced_with_log_exception():
    """[BUG-P-1-1] 4 处 `log.error(e)` 应改 `log.exception(...)` 把 traceback
    写进日志, 否则排错时只有错误字符串没有堆栈。"""
    for mapper_file in MAPPER_FILES_WITH_RAISE_E:
        with open(mapper_file, "r", encoding="utf-8") as fp:
            src = fp.read()
        # 排除注释行
        code_only = "\n".join(
            ln for ln in src.splitlines()
            if ln.strip() and not ln.strip().startswith("#")
        )
        bare_log_error_e = re.findall(r"^\s+log\.error\(e\)\s*$", code_only, re.MULTILINE)
        assert len(bare_log_error_e) == 0, (
            f"[{BUG_P_1_1}] {mapper_file} 仍有 {len(bare_log_error_e)} 处 "
            f"`log.error(e)` (不写 traceback), 应改 `log.exception(...)`"
        )


# --------------------------------------------------------------------------- #
# BUG-P-1-2: ui_case_id property + mapper 改 snake_case
# --------------------------------------------------------------------------- #

def test_bug_p_1_2_model_has_ui_case_id_property():
    """[BUG-P-1-2] PlayCaseResult 必须有 ui_case_id property (read+write)
    兼容到 ui_case_Id 字段。"""
    from app.model.playUI.playCase import PlayCaseResult

    # property 存在
    assert hasattr(PlayCaseResult, "ui_case_id"), (
        f"[{BUG_P_1_2}] PlayCaseResult 缺 ui_case_id property"
    )
    desc = getattr(PlayCaseResult.ui_case_id, "fget", None)
    assert desc is not None, f"[{BUG_P_1_2}] ui_case_id 不是 property (缺 fget)"

    # setter 也存在 (避免只能读不能写)
    setter = getattr(PlayCaseResult.ui_case_id, "fset", None)
    assert setter is not None, f"[{BUG_P_1_2}] ui_case_id property 缺 setter"


def test_bug_p_1_2_mapper_uses_ui_case_id_not_ui_case_Id():
    """[BUG-P-1-2] playCaseMapper.py 应使用 ui_case_id (snake_case),
    不再写 ui_case_Id (大写 I)。"""
    with open("app/mapper/play/playCaseMapper.py", "r", encoding="utf-8") as fp:
        src = fp.read()
    code_only = "\n".join(
        ln for ln in src.splitlines()
        if ln.strip() and not ln.strip().startswith("#")
    )
    matches = re.findall(r"ui_case_Id", code_only)
    assert len(matches) == 0, (
        f"[{BUG_P_1_2}] playCaseMapper.py 还有 {len(matches)} 处 ui_case_Id "
        f"(大写 I), 应改 ui_case_id (snake_case)"
    )


def test_bug_p_1_2_schema_has_ui_case_id_alias():
    """[BUG-P-1-2] PagePlayCaseResultSchema 暴露 ui_case_id 字段,
    用 alias 兼容旧客户端传 ui_case_Id。"""
    with open("app/schema/play/playCaseSchema.py", "r", encoding="utf-8") as fp:
        src = fp.read()
    assert "ui_case_id" in src, (
        f"[{BUG_P_1_2}] playCaseSchema.py 缺 ui_case_id 字段"
    )
    # alias 兼容
    assert 'alias="ui_case_Id"' in src, (
        f"[{BUG_P_1_2}] playCaseSchema.py 缺 alias='ui_case_Id' 兼容旧客户端"
    )


# --------------------------------------------------------------------------- #
# BUG-P-1-3: rate_number Column(Float) 而非 INTEGER
# --------------------------------------------------------------------------- #

def test_bug_p_1_3_rate_number_is_float_column():
    """[BUG-P-1-3] PlayTaskResult.rate_number 应是 Float 列, 不是 INTEGER。
    writer 用 round(..., 2) 写 float, INTEGER 会静默截断丢精度。"""
    from sqlalchemy import Float

    from app.model.playUI.playTask import PlayTaskResult

    col = PlayTaskResult.__table__.columns.get("rate_number")
    assert col is not None, f"[{BUG_P_1_3}] PlayTaskResult 缺 rate_number 列"
    assert isinstance(col.type, Float), (
        f"[{BUG_P_1_3}] rate_number 期望 Float, 实际 {type(col.type).__name__}。"
        f" writer 用 round(..., 2) 写 85.5, INTEGER 会静默变成 85, 丢 1 位小数"
    )


# --------------------------------------------------------------------------- #
# BUG-P-1-4: write_result 参数 success 而非 SUCCESS
# --------------------------------------------------------------------------- #

def test_bug_p_1_4_write_result_uses_snake_case_param():
    """[BUG-P-1-4] PlayCaseResultWriter.write_result 参数应 success (snake_case),
    不是 SUCCESS (大写, 违反 PEP 8)。"""
    from croe.play.writer import PlayCaseResultWriter

    sig = inspect.signature(PlayCaseResultWriter.write_result)
    params = list(sig.parameters.keys())
    # 第一个参数是 self
    assert "SUCCESS" not in params, (
        f"[{BUG_P_1_4}] write_result 还有 SUCCESS 参数 (大写, 违反 PEP 8)"
    )
    assert "success" in params, (
        f"[{BUG_P_1_4}] write_result 缺 success 参数 (snake_case)"
    )


# --------------------------------------------------------------------------- #
# BUG-P-1-5: ContentResultWriter.__repr__ 不应有双 `> />`
# --------------------------------------------------------------------------- #

def test_bug_p_1_5_content_result_writer_repr_no_double_gt():
    """[BUG-P-1-5] ContentResultWriter.__repr__ 末尾不应有 `> />` 双符号
    拼写错误。"""
    from croe.play.writer import ContentResultWriter

    src = inspect.getsource(ContentResultWriter.__repr__)
    # 应只有 1 个 `/>` 在末尾 (允许格式像 `<... task_result_id=... results=... />`)
    assert " />" in src or "/>" in src, f"[{BUG_P_1_5}] __repr__ 缺 /> 收尾"
    # 不应有 `> />` (双符号)
    assert "> />" not in src, (
        f"[{BUG_P_1_5}] __repr__ 仍有 `> />` 双符号拼写错误, 应改单 `/>`"
    )


# --------------------------------------------------------------------------- #
# BUG-P-1-6: update_content_result 重算 use_time
# --------------------------------------------------------------------------- #

def test_bug_p_1_6_update_content_result_recomputes_use_time():
    """[BUG-P-1-6] update_content_result 应重算 use_time (now - start_time),
    不只是更新 content_result 字段。步骤组耗时反映真实执行时间。"""
    from croe.play.writer import ContentResultWriter

    src = inspect.getsource(ContentResultWriter.update_content_result)
    # 应有 use_time = (重算)
    assert "use_time" in src, (
        f"[{BUG_P_1_6}] update_content_result 没设 use_time, 步骤组耗时 = 0"
    )
    # 应有 timeDiff 调用 (use_time = GenerateTools.timeDiff(...))
    assert "timeDiff" in src, (
        f"[{BUG_P_1_6}] update_content_result 没调 GenerateTools.timeDiff 重算"
    )
    # 应有 start_time 引用
    assert "start_time" in src, (
        f"[{BUG_P_1_6}] update_content_result 没引用 start_time 算 use_time"
    )


# --------------------------------------------------------------------------- #
# BUG-P-1-7: __clean / __init_page → _clean / _init_page
# --------------------------------------------------------------------------- #

def test_bug_p_1_7_no_double_underscore_methods_in_play_runner():
    """[BUG-P-1-7] play_runner.py 不应有 __clean / __init_page 双下划线方法
    (触发 name mangling, 子类化/mock 拿不到)。改 _clean / _init_page。"""
    from croe.play import play_runner

    src = inspect.getsource(play_runner.PlayRunner)
    # 排除注释行
    code_only = "\n".join(
        ln for ln in src.splitlines()
        if ln.strip() and not ln.strip().startswith("#")
    )
    # 找双下划线 def (跳过 __init__/__repr__ 等 dunder)
    # 我们关心的私有方法 (不是 dunder)
    bad_methods = re.findall(
        r"^\s+async def (__[a-z_]+)\(self", code_only, re.MULTILINE
    )
    # __init__ 之类 dunder 是 OK 的, 我们关心 __clean / __init_page
    interesting = [m for m in bad_methods if m not in ("__init__",)]
    assert len(interesting) == 0, (
        f"[{BUG_P_1_7}] PlayRunner 还有双下划线方法 {interesting}, "
        f"会触发 name mangling (`self._PlayRunner__clean` 这种), "
        f"子类化和 mock 拿不到。改单下划线 `_clean` / `_init_page`"
    )


def test_bug_p_1_7_clean_and_init_page_renamed_to_single_underscore():
    """[BUG-P_1_7] play_runner 必须有 _clean 和 _init_page 方法 (单下划线)。"""
    from croe.play import play_runner

    assert hasattr(play_runner.PlayRunner, "_clean"), (
        f"[{BUG_P_1_7}] PlayRunner 缺 _clean 方法 (单下划线)"
    )
    assert hasattr(play_runner.PlayRunner, "_init_page"), (
        f"[{BUG_P_1_7}] PlayRunner 缺 _init_page 方法 (单下划线)"
    )


# --------------------------------------------------------------------------- #
# BUG-P-1-8: init_case_variables 失败不 raise
# --------------------------------------------------------------------------- #

def test_bug_p_1_8_init_case_variables_does_not_raise():
    """[BUG-P-1-8] init_case_variables 失败不应 raise, 否则跟 error_continue
    语义冲突 (error_continue=True 仍被 raise 中断)。修: 失败只 log + warning。"""
    from croe.play.play_runner import PlayRunner

    src = inspect.getsource(PlayRunner.init_case_variables)

    # 找 except 块
    except_m = re.search(
        r"except Exception[^:]*:\s*\n(.*?)(?=\n        finally|\n    async def|\Z)",
        src, re.DOTALL
    )
    assert except_m, f"[{BUG_P_1_8}] 找不到 except 块"
    except_block = "\n".join(
        ln for ln in except_m.group(1).splitlines()
        if ln.strip() and not ln.strip().startswith("#")
    )

    # except 块不应有 raise
    assert "raise" not in except_block, (
        f"[{BUG_P_1_8}] init_case_variables except 块还有 `raise`, "
        f"跟 error_continue 语义冲突。修: 失败只 log + warning。\n"
        f"当前 except 块:\n{except_block}"
    )
    # 应有 log.exception (记录 traceback)
    assert "log.exception" in except_block, (
        f"[{BUG_P_1_8}] init_case_variables 失败应 log.exception (留 traceback)"
    )
