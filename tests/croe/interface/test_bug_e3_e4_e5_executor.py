"""执行器层 3 个 easy win 一锅端。"""

import ast
import inspect
import asyncio
import pytest
from pathlib import Path

from tests.croe.interface._bug_ids import BUG_E3, BUG_E4, BUG_E5

REPO = Path(__file__).resolve().parents[3]

@pytest.fixture
def bug_e3_marker():
    return BUG_E3

@pytest.fixture
def bug_e4_marker():
    return BUG_E4

@pytest.fixture
def bug_e5_marker():
    return BUG_E5

# ---------- E3: 不再有 asyncio.TaskGroup ----------

def test_bug_e3_request_builder_no_task_group(bug_e3_marker):
    """request_builder.py 不能用 asyncio.TaskGroup (3.11+)"""
    p = REPO / "croe" / "interface" / "builder" / "request_builder.py"
    src = p.read_text(encoding="utf-8")
    # 用 AST 检查 (排除注释/docstring 里的提及)
    import ast as _ast
    try:
        tree = _ast.parse(src)
    except SyntaxError as e:
        pytest.fail(f"[{BUG_E3}] 语法错误: {e}")
    for node in _ast.walk(tree):
        if isinstance(node, _ast.AsyncWith):
            # 找 `async with asyncio.TaskGroup() as tg` 模式
            for item in node.items:
                ctx = item.context_expr
                # asyncio.TaskGroup() 是 Call(Attribute(Name('asyncio'), 'TaskGroup'), [])
                if (
                    isinstance(ctx, _ast.Call)
                    and isinstance(ctx.func, _ast.Attribute)
                    and ctx.func.attr == "TaskGroup"
                ):
                    pytest.fail(
                        f"[{BUG_E3}] request_builder.py 仍在用 asyncio.TaskGroup "
                        f"(行 {node.lineno}), Python 3.10 上会 AttributeError"
                    )

def test_bug_e3_request_builder_no_gather_or_task_group(bug_e3_marker):
    """request_builder.py 已同步化, 不再用 asyncio.gather / TaskGroup。"""
    src = (REPO / "croe" / "interface" / "builder" / "request_builder.py").read_text(
        encoding="utf-8"
    )
    assert "asyncio.gather" not in src, (
        f"[{BUG_E3}] _transform_request_data 已同步化, 不应再用 asyncio.gather"
    )
    assert "asyncio.TaskGroup" not in src, (
        f"[{BUG_E3}] 不应使用 asyncio.TaskGroup (Python 3.10 不兼容)"
    )
    # 同步化后应直接调用 self.variables.trans
    assert "self.variables.trans(value)" in src, (
        f"[{BUG_E3}] 应直接同步调用 self.variables.trans(value)"
    )

def test_bug_e3_transform_request_data_signature_unchanged(bug_e3_marker):
    """_transform_request_data 签名不能改 (会被外部调用)"""
    from croe.interface.builder.request_builder import RequestBuilder
    sig = inspect.signature(RequestBuilder._transform_request_data)
    params = list(sig.parameters.keys())
    assert params == ["self", "request_data"], (
        f"[{BUG_E3}] _transform_request_data 签名变了: {params}"
    )

# ---------- E4: _parse_url 死代码已删, EnvMapper import 已删 ----------

def test_bug_e4_parse_url_removed(bug_e4_marker):
    """interface_executor._parse_url 是死代码, 删掉避免和 UrlBuilder 不一致"""
    from croe.interface.executor.interface_executor import InterfaceExecutor
    assert not hasattr(InterfaceExecutor, "_parse_url"), (
        f"[{BUG_E4}] _parse_url 还在, 跟 UrlBuilder.build 逻辑不一致, "
        f"应删除"
    )

def test_bug_e4_env_mapper_import_removed(bug_e4_marker):
    """EnvMapper 在 interface_executor.py 里只剩 _parse_url 用, 删方法后 import 也该删"""
    src = (REPO / "croe/interface/executor/interface_executor.py").read_text(
        encoding="utf-8"
    )
    assert "from app.mapper.project.env import EnvMapper" not in src, (
        f"[{BUG_E4}] EnvMapper 悬空 import 没清, 留下死依赖"
    )

# ---------- E5: 显式 None 防御 ----------

def test_bug_e5_before_sql_uses_explicit_none_guard(bug_e5_marker):
    """_execute_before_sql 改用 sql_text = ... or "" 显式处理 None"""
    src = (REPO / "croe/interface/executor/interface_executor.py").read_text(
        encoding="utf-8"
    )
    # 直接 .strip() 在 ORM 字段上
    assert "interface.interface_before_sql.strip()" not in src, (
        f"[{BUG_E5}] 还在 interface.interface_before_sql.strip() 直接调, "
        f"读起来像修改字段; 应改成 sql_text = ... or \"\" 显式模式"
    )
    # 有 sql_text 中间变量
    assert "sql_text = interface.interface_before_sql or \"\"" in src, (
        f"[{BUG_E5}] 缺 sql_text = interface.interface_before_sql or \"\" 防御"
    )

# ---------- 端到端: _transform_request_data 真能跑 ----------

@pytest.mark.asyncio
async def test_bug_e3_transform_data_e2e(bug_e3_marker):
    """_transform_request_data 在真 asyncio loop 下能跑通 (3.10 兼容路径)"""
    from unittest.mock import MagicMock
    from croe.interface.builder.request_builder import RequestBuilder, KEY_HEADERS, KEY_PARAMS

    # mock 一个 variable_manager, trans 递归返回值加上 'X' 后缀
    var_mgr = MagicMock()
    def fake_trans(value):
        if value is None:
            return None
        if isinstance(value, dict):
            return {k: fake_trans(v) for k, v in value.items()}
        return f"{value}-X"
    var_mgr.trans = fake_trans

    rb = RequestBuilder(variables=var_mgr, global_headers=[])

    data = {
        KEY_HEADERS: {"X-Api": "v1"},
        KEY_PARAMS: {"q": "hello"},
        "read": 15,
        "connect": 5,
        "follow_redirects": True,
    }
    rb._transform_request_data(data)

    # 数据字段被替换
    assert data[KEY_HEADERS] == {"X-Api": "v1-X"}
    assert data[KEY_PARAMS] == {"q": "hello-X"}
    # httpx 配置字段不被替换，保持原值
    assert data["read"] == 15
    assert data["connect"] == 5
    assert data["follow_redirects"] is True


@pytest.mark.asyncio
async def test_bug_e3_transform_data_empty(bug_e3_marker):
    """空 dict / 全 None 也不崩"""
    from unittest.mock import MagicMock
    from croe.interface.builder.request_builder import RequestBuilder

    var_mgr = MagicMock()
    def fake_trans(value):
        return value
    var_mgr.trans = fake_trans

    rb = RequestBuilder(variables=var_mgr, global_headers=[])

    # 空
    data = {}
    rb._transform_request_data(data)
    assert data == {}

    # 非数据字段为 None
    data = {"read": None, "connect": None}
    rb._transform_request_data(data)
    assert data == {"read": None, "connect": None}
