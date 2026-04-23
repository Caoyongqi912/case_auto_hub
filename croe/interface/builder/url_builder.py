#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Time : 2026/1/21
# @Author : cyq
# @File : url_builder
# @Software: PyCharm
# @Desc: URL构建器

from typing import Optional, TYPE_CHECKING

from app.model.interfaceAPIModel.interfaceModel import Interface
from app.model.base import EnvModel
from utils import log

if TYPE_CHECKING:
    pass


class UrlBuilder:
    """URL构建器"""

    CUSTOM_ENV_ID = 99999

    @staticmethod
    async def build(
        interface: Interface,
        env: Optional[EnvModel] = None
    ) -> str:
        """
        构建请求URL

        Args:
            interface: 接口对象
            env: 环境配置

        Returns:
            完整的请求URL

        Raises:
            ValueError: 未提供环境配置时抛出
        """
        if interface.env_id == UrlBuilder.CUSTOM_ENV_ID:
            log.info(f"使用自定义环境URL: {interface.interface_url}")
            return interface.interface_url

        if env is None:
            raise ValueError(
                f"未提供环境配置，interface_id={interface.id}, "
                f"env_id={interface.env_id}"
            )

        base_url = env.url.rstrip('/')
        path = interface.interface_url.lstrip('/')

        url = f"{base_url}/{path}"
        log.info(f"构建请求URL: {url}")

        return url
