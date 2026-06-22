"""
2026-06-22 Round 2 - 修复

触发: 端点 GET /interfaceResult/queryStepResult?case_result_id=67
 500 Internal Server Error, 堆栈:
 TypeError: Object of type StepStatusEnum is not JSON serializable

回归: tests/croe/interface/test_bug_result_enum_serialize_fix.py

覆盖:
- jsonable_encoder 认 enum.Enum, 返回 .value (str)
- jsonable_encoder 对 int 值 Enum 也返 .value (跟之前 int 兜底语义一致)
- 嵌套结构 (list of enum) 也能序列化
- 端到端: queryStepResult controller 路径不再 500
"""
import enum
import inspect
import re

import pytest

from app.response._response import jsonable_encoder
from tests.croe.interface._bug_ids import BUG_RESULT_ENUM_SERIALIZE


# 用于测试的样例 enum
class _StrEnum(enum.Enum):
    SUCCESS = "SUCCESS"
    FAIL = "FAIL"
    PENDING = "PENDING"


class _IntEnum(enum.Enum):
    A = 1
    B = 2


# ============================================================
# jsonable_encoder 认 enum.Enum
# ============================================================
class TestBugResultEnumSerialize:
    """jsonable_encoder 必须能序列化 enum.Enum (str 值 和 int 值)"""

    def test_str_enum_serializes_to_value(self):
        """str 值 Enum 必须 .value 化"""
        data = {"status": _StrEnum.SUCCESS}
        out = jsonable_encoder(data)
        assert out == {"status": "SUCCESS"}, (
            f"[{BUG_RESULT_ENUM_SERIALIZE}] str 值 enum 序列化错, "
            f"期望 {{'status': 'SUCCESS'}}, 实际: {out}"
        )
        assert isinstance(out["status"], str), (
            f"[{BUG_RESULT_ENUM_SERIALIZE}] 序列化后必须是 str, 实际: {type(out['status'])}"
        )

    def test_int_enum_serializes_to_value(self):
        """int 值 Enum 也必须 .value 化 (跟之前 int 兜底语义一致)"""
        data = {"type": _IntEnum.A}
        out = jsonable_encoder(data)
        assert out == {"type": 1}, (
            f"[{BUG_RESULT_ENUM_SERIALIZE}] int 值 enum 序列化错, "
            f"期望 {{'type': 1}}, 实际: {out}"
        )

    def test_real_step_status_enum_serializes(self):
        """真实的 StepStatusEnum 也能序列化"""
        from enums.InterfaceEnum import StepStatusEnum
        data = {"status": StepStatusEnum.SUCCESS, "tag": StepStatusEnum.PENDING}
        out = jsonable_encoder(data)
        assert out == {"status": "SUCCESS", "tag": "PENDING"}, (
            f"[{BUG_RESULT_ENUM_SERIALIZE}] 真实 StepStatusEnum 序列化错, 实际: {out}"
        )

    def test_real_case_step_content_type_enum_serializes(self):
        """真实 CaseStepContentType (int 值) 也 .value 化"""
        from enums.CaseEnum import CaseStepContentType
        data = {"content_type": CaseStepContentType.STEP_API}
        out = jsonable_encoder(data)
        assert out == {"content_type": 1}, (
            f"[{BUG_RESULT_ENUM_SERIALIZE}] CaseStepContentType 序列化错, 实际: {out}"
        )

    def test_nested_list_of_enum_serializes(self):
        """嵌套 list of enum 也能序列化"""
        data = {"tags": [_StrEnum.SUCCESS, _StrEnum.FAIL, _StrEnum.PENDING]}
        out = jsonable_encoder(data)
        assert out == {"tags": ["SUCCESS", "FAIL", "PENDING"]}, (
            f"[{BUG_RESULT_ENUM_SERIALIZE}] list 嵌套 enum 序列化错, 实际: {out}"
        )

    def test_nested_dict_with_enum_value(self):
        """嵌套 dict value 是 enum 也能序列化"""
        data = {"outer": {"inner": _StrEnum.SUCCESS, "name": "test"}}
        out = jsonable_encoder(data)
        assert out == {"outer": {"inner": "SUCCESS", "name": "test"}}, (
            f"[{BUG_RESULT_ENUM_SERIALIZE}] 嵌套 dict+enum 序列化错, 实际: {out}"
        )

    def test_mixed_primitives_and_enum(self):
        """enum 跟其他类型混在一起"""
        data = {
            "status": _StrEnum.SUCCESS,
            "name": "test",
            "count": 42,
            "rate": 3.14,
            "tags": None,
        }
        out = jsonable_encoder(data)
        assert out == {
            "status": "SUCCESS",
            "name": "test",
            "count": 42,
            "rate": 3.14,
            "tags": None,
        }, f"[{BUG_RESULT_ENUM_SERIALIZE}] 混合类型序列化错, 实际: {out}"


# ============================================================
# 源码层锁
# ============================================================
class TestBugResultEnumSerializeSource:
    """源码必须显式 import enum + 加 isinstance(obj, enum.Enum) 分支"""

    def test_response_module_imports_enum(self):
        """app/response/_response.py 必须 import enum"""
        with open("app/response/_response.py") as f:
            src = f.read()
        assert re.search(r"^import enum\b|^from enum\b", src, re.MULTILINE), (
            f"[{BUG_RESULT_ENUM_SERIALIZE}] app/response/_response.py 必须 import enum"
        )

    def test_response_jsonable_encoder_has_enum_check(self):
        """jsonable_encoder 必须有 isinstance(obj, enum.Enum) 分支"""
        with open("app/response/_response.py") as f:
            src = f.read()
        assert "isinstance(obj, enum.Enum)" in src, (
            f"[{BUG_RESULT_ENUM_SERIALIZE}] jsonable_encoder 缺 isinstance(obj, enum.Enum) 分支"
        )
 # 必须 return obj.value
 # 找 isinstance(obj, enum.Enum): return obj.value 这条
        assert re.search(
            r"isinstance\(obj,\s*enum\.Enum\)\s*:\s*\n\s*return\s+obj\.value",
            src,
        ), (
            f"[{BUG_RESULT_ENUM_SERIALIZE}] jsonable_encoder 的 enum.Enum 分支必须 return obj.value"
        )

    def test_enum_check_before_primitive_check(self):
        """enum.Enum 检查必须在 (str, int, float, NoneType) 之前

 原因: int 值 Enum 在 Py3.11 默认继承 int, 如果 enum 检查在 int 检查之后,
 int 值 Enum 会被 int 分支先接住, str 值 Enum 才轮到 enum 分支, 但语义
 仍正确 (int 分支 return obj, 等于 obj.value 因为 enum 本身是 int)。
 不过这样会留一个"int 值 Enum 不走 .value 显式路径"的尾巴。
 把 enum 检查放最前, 统一 .value, 行为可预测。
 """
        with open("app/response/_response.py") as f:
            src = f.read()
        enum_idx = src.find("isinstance(obj, enum.Enum)")
        int_idx = src.find("isinstance(obj, (str, int, float, type(None)))")
        assert enum_idx > 0, "enum check not found"
        assert int_idx > 0, "int check not found"
        assert enum_idx < int_idx, (
            f"[{BUG_RESULT_ENUM_SERIALIZE}] isinstance(obj, enum.Enum) 必须在 "
            f"(str, int, float, NoneType) 检查之前, 当前顺序: "
            f"enum at {enum_idx}, int at {int_idx}"
        )


# ============================================================
# 端到端 - controller 路径不再 500
# ============================================================
class TestBugResultEnumSerializeEndpoint:
    """端到端: queryStepResult 端点不能因为 enum 序列化爆"""

    def test_response_success_does_not_raise_on_enum_dict(self):
        """Response.success({...含 enum...}) 不再 raise"""
        from app.response import Response
 # 模拟 to_dict 后含 enum 的结果
        data = {
            "id": 160,
            "content_type": _IntEnum.A,  # 模拟 CaseStepContentType
            "status": _StrEnum.SUCCESS,  # 模拟 StepStatusEnum
            "result": True,
            "use_time": "100ms",
        }
        out = Response.success(data)
        assert out["code"] == 0
        assert out["data"]["status"] == "SUCCESS", (
            f"[{BUG_RESULT_ENUM_SERIALIZE}] 端到端 status 仍不是 string, "
            f"实际: {out['data']['status']}"
        )
        assert out["data"]["content_type"] == 1

    def test_response_success_on_list_of_dicts_with_enum(self):
        """Response.success([{...含 enum...}, ...]) 不再 raise"""
        from app.response import Response
        data = [
            {"id": 1, "status": _StrEnum.SUCCESS, "content_type": _IntEnum.A},
            {"id": 2, "status": _StrEnum.FAIL, "content_type": _IntEnum.B},
            {"id": 3, "status": _StrEnum.PENDING, "content_type": _IntEnum.A},
        ]
        out = Response.success(data)
        assert out["code"] == 0
        assert out["data"][0]["status"] == "SUCCESS"
        assert out["data"][1]["status"] == "FAIL"
        assert out["data"][2]["status"] == "PENDING"
        assert out["data"][0]["content_type"] == 1
