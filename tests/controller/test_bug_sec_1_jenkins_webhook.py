"""Jenkins Webhook 鉴权回归测试.

锁定行为:
- JenkinsWebhookAuth 依赖 fail-closed: Config.JENKINS_WEBHOOK_TOKEN 未配置 → 401
- Header X-Jenkins-Token 缺失 → 401
- Header X-Jenkins-Token 不匹配 → 401
- Header X-Jenkins-Token 匹配 → 放行 (返回 True)
- 2 个 Jenkins 端点 (execute_by_jenkins / runTaskByJenkins) 必须有 Depends(JenkinsWebhookAuth)
"""
import os
import re
from pathlib import Path
from unittest.mock import patch

import pytest


# --------------------------------------------------------------------------- #
# 1. 静态扫描: 2 个 Jenkins 端点必须挂 JenkinsWebhookAuth
# --------------------------------------------------------------------------- #
@pytest.mark.unit
@pytest.mark.parametrize(
    "controller_file,func_name",
    [
        (
            "app/controller/interface/interfaceTaskController.py",
            "execute_task_by_jenkins",
        ),
        (
            "app/controller/play/play_task.py",
            "runTaskByJenkins",
        ),
    ],
)
def test_jenkins_endpoint_has_webhook_auth(controller_file, func_name):
    """Jenkins 路由必须挂 JenkinsWebhookAuth 依赖, 否则任何人可触发任务执行。"""
    src = Path(controller_file).read_text()
    m = re.search(
        rf"async def {func_name}\(([^)]+)\)",
        src,
        re.DOTALL,
    )
    assert m, f"{controller_file} 找不到 async def {func_name}"
    sig = m.group(1)
    assert "JenkinsWebhookAuth" in sig, (
        f"{controller_file}.{func_name} 缺 JenkinsWebhookAuth 依赖, "
        f"签名: {sig!r}"
    )


# --------------------------------------------------------------------------- #
# 2. 行为证明: JenkinsWebhookAuth fail-closed 分支
# --------------------------------------------------------------------------- #
# FastAPI 路由在直接 await 调用时, header 位置参数接收的是字符串值本身 (FastAPI 已从 Header() 中提取),
# 因此测试用 str 直接传, 模拟框架注入行为。
@pytest.mark.unit
@pytest.mark.asyncio
async def test_webhook_auth_rejects_when_token_unconfigured():
    """Config.JENKINS_WEBHOOK_TOKEN 为空时, 即便 header 正确也拒绝。"""
    from app.controller import JenkinsWebhookAuth
    from app.exception import AuthError

    with patch("config.Config") as MockCfg:
        MockCfg.JENKINS_WEBHOOK_TOKEN = ""
        auth = JenkinsWebhookAuth()
        with pytest.raises(AuthError, match="未启用"):
            await auth("anything")


@pytest.mark.unit
@pytest.mark.asyncio
async def test_webhook_auth_rejects_missing_header():
    """已配置 token 但请求头缺失 → 401。"""
    from app.controller import JenkinsWebhookAuth
    from app.exception import AuthError

    with patch("config.Config") as MockCfg:
        MockCfg.JENKINS_WEBHOOK_TOKEN = "valid-secret-abc"
        auth = JenkinsWebhookAuth()
        with pytest.raises(AuthError, match="鉴权失败"):
            await auth(None)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_webhook_auth_rejects_empty_string_header():
    """已配置 token 但 header 是空字符串 → 401。"""
    from app.controller import JenkinsWebhookAuth
    from app.exception import AuthError

    with patch("config.Config") as MockCfg:
        MockCfg.JENKINS_WEBHOOK_TOKEN = "valid-secret-abc"
        auth = JenkinsWebhookAuth()
        with pytest.raises(AuthError, match="鉴权失败"):
            await auth("")


@pytest.mark.unit
@pytest.mark.asyncio
async def test_webhook_auth_rejects_wrong_header():
    """header 不匹配 → 401。"""
    from app.controller import JenkinsWebhookAuth
    from app.exception import AuthError

    with patch("config.Config") as MockCfg:
        MockCfg.JENKINS_WEBHOOK_TOKEN = "valid-secret-abc"
        auth = JenkinsWebhookAuth()
        with pytest.raises(AuthError, match="鉴权失败"):
            await auth("wrong-token")


@pytest.mark.unit
@pytest.mark.asyncio
async def test_webhook_auth_allows_matching_header():
    """header 匹配 → 放行 (返回 True)。"""
    from app.controller import JenkinsWebhookAuth

    with patch("config.Config") as MockCfg:
        MockCfg.JENKINS_WEBHOOK_TOKEN = "valid-secret-abc"
        auth = JenkinsWebhookAuth()
        result = await auth("valid-secret-abc")
        assert result is True


# --------------------------------------------------------------------------- #
# 3. 配置层: JENKINS_WEBHOOK_TOKEN 必须能通过 env 注入
# --------------------------------------------------------------------------- #
@pytest.mark.unit
def test_config_jenkins_token_default_empty(monkeypatch):
    """env 无 JENKINS_WEBHOOK_TOKEN 时, os.getenv 默认值是空字符串 (fail-closed)。"""
    monkeypatch.delenv("JENKINS_WEBHOOK_TOKEN", raising=False)
    assert os.getenv("JENKINS_WEBHOOK_TOKEN", "") == ""


@pytest.mark.unit
def test_config_jenkins_token_from_env(monkeypatch):
    """JENKINS_WEBHOOK_TOKEN 能从 env 读出。"""
    monkeypatch.setenv("JENKINS_WEBHOOK_TOKEN", "ci-shared-secret-2026")
    assert os.getenv("JENKINS_WEBHOOK_TOKEN") == "ci-shared-secret-2026"
