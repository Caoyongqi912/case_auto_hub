#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Time : 2024/6/6
# @Author : cyq
# @File : __init__.py
# @Software: PyCharm
# @Desc:
from fastapi import Header
from utils import MyLoguru
from app.mapper.user import UserMapper
from ..exception import AuthError

LOG = MyLoguru().get_logger()


class Authentication:
    """
    鉴权：管理admin
    """

    def __init__(self, isAdmin: bool = False):
        self.isAdmin = isAdmin

    async def __call__(self, Authorization: str = Header(None)):
        if not Authorization:
            raise AuthError("请先登录")
        current_user_dict = await UserMapper.parse_token(Authorization)

        # 要求admin。但是是普通用户
        if self.isAdmin is True and current_user_dict["isAdmin"] is False:
            raise AuthError("无权操作")
        current_user = await UserMapper.get_by_id(current_user_dict["id"], )
        LOG.info(f"current user {current_user}")
        return current_user


class JenkinsWebhookAuth:
    """Jenkins Webhook 鉴权依赖: 通过共享密钥验证请求, 不依赖用户登录态。

    用于 CI/CD 回调类路由, 例如 execute_by_jenkins / runTaskByJenkins.
    与 Authentication 不同, 该依赖不查用户表, 不发 token, 简单字符串比对。

    安全模型 (fail-closed):
    1. Config.JENKINS_WEBHOOK_TOKEN 未配置 (空字符串) → 抛 AuthError 401, 路由拒绝服务。
    2. 已配置但请求头 X-Jenkins-Token 缺失或不匹配 → 抛 AuthError 401。
    3. 配置且 header 匹配 → 放行, 路由正常执行业务逻辑。

    部署要点:
    - 在 .env / 环境变量中设置 JENKINS_WEBHOOK_TOKEN=<随机不可猜字符串>。
    - Jenkins 调用方在请求头 X-Jenkins-Token 中带入相同 token。
    - 不留空, 不复用 SECRET_KEY, 定期轮换。
    """

    async def __call__(self, x_jenkins_token: str = Header(None, alias="X-Jenkins-Token")):
        from config import Config
        expected = Config.JENKINS_WEBHOOK_TOKEN
        if not expected:
            LOG.error(
                "JENKINS_WEBHOOK_TOKEN 未配置, 拒绝 Jenkins webhook 调用。"
                "请在 .env 设置 JENKINS_WEBHOOK_TOKEN=<强随机字符串> 后重启服务。"
            )
            raise AuthError("Jenkins webhook 未启用, 请联系管理员配置 JENKINS_WEBHOOK_TOKEN")
        if not x_jenkins_token or x_jenkins_token != expected:
            LOG.warning(f"Jenkins webhook 鉴权失败: token 缺失或不匹配, client_token={x_jenkins_token!r}")
            raise AuthError("Jenkins webhook 鉴权失败")
        return True


from app.controller import file, statistics
from .project import project, db_config, module, push_config, aps_job
from .user import user, department
from .interface import (interfaceCaseController, interfaceGlobalController,
                        interfaceController, interfaceTaskController, interfaceResultController, interfaceGroupController)
from .play import play_case, play_step, play_config, play_step_group, play_task
from .test_case import requirements, test_case, mind_case, case_plan, case_config

RegisterRouterList = [
    mind_case,
    file,
    aps_job,
    push_config,
    db_config,
    statistics,
    project,
    module,
    user,
    department,
    interfaceTaskController,
    interfaceResultController,
    interfaceGlobalController,
    interfaceGroupController,
    interfaceCaseController,
    interfaceCaseController,
interfaceController,
    # interfaceRecord,
    play_case,
    play_step,
    play_config,
    play_step_group,
    play_task,
    case_plan,
    requirements,
    test_case,
    case_config
]