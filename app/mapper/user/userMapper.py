#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Time : 2024/6/6
# @Author : cyq
# @File : userMapper
# @Software: PyCharm
# @Desc:
import time
from typing import List

import jwt
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio.session import AsyncSession

from app.exception import AuthError
from app.schema.base.user import AddOrUpdateUserVars
from config import Config
from werkzeug.security import generate_password_hash, check_password_hash
from app.mapper import Mapper
from app.model.base import User, UserVars
from enums import GenderEnum
from utils import MyLoguru

log = MyLoguru().get_logger()


class UserMapper(Mapper[User]):
    __model__ = User

    @classmethod
    async def set_pwd(cls, old_password: str, new_password: str, user: User):
        """
        更新用户密码。

        使用 transaction() 自动管理 session 和事务边界。
        """
        try:
            # 统一使用 transaction() 替代 async_session() + session.begin()
            # 自动创建 session + begin，退出时自动 commit/rollback
            async with cls.transaction() as session:
                if await cls.check_password(user.password, old_password):
                    user.password = await cls.set_password(new_password)
                else:
                    raise AuthError("密码错误")
        except Exception as e:
            raise e



    @classmethod
    async def get_avatar(cls, uid: str):
        """
        根据 uid 获取用户头像。

        使用 session_scope() 自动管理 session 生命周期（只读查询）。
        """
        try:
            # 统一使用 session_scope() 替代直接 async_session()
            async with cls.session_scope() as session:
                user = await cls.get_by_uid(uid, session)
                return user.avatar
        except Exception as e:
            raise e

    @classmethod
    async def filter_user_by_username(cls, username: str | None) -> List[User]:
        """
        根据用户名模糊查询用户列表。

        使用 session_scope() 自动管理 session 生命周期（只读查询）。

        Args:
            username: 用户名关键字（支持模糊匹配），为 None 时查询全部

        Returns:
            List[User]: 用户列表
        """
        try:
            # 统一使用 session_scope() 替代直接 async_session()
            async with cls.session_scope() as session:
                if not username:
                    sql = select(User)
                else:
                    sql = select(User).where(User.username.like(f"%{username}%"))
                exec = await session.execute(sql)
                data = exec.scalars().all()
                return data

        except Exception as e:
            log.error(f"filter_user_by_username error: {e}")
            raise e

    @classmethod
    async def register(cls,
                       username: str,
                       gender: GenderEnum,
                       phone: str,
                       isAdmin: bool = False,
                       tagName: str = None):
        """
        注册用户。

        使用 transaction() 自动管理 session 和事务边界。

        Args:
            username: 用户名
            gender: 性别
            phone: 手机号
            isAdmin: 是否为管理员
            tagName: 标签名
        """
        try:
            # 统一使用 transaction() 替代 async_session() + session.begin()
            # 自动创建 session + begin，异常时自动 rollback
            async with cls.transaction() as session:
                email = username + "@hub.com"
                user = await cls.get_by(session=session, email=email, phone=phone)
                if user:
                    raise AuthError(f"用户 {username} 已存在")
                pwd_hash = await cls.set_password(username)
                session.add(User(username=username,
                                 password=pwd_hash,
                                 email=email,
                                 phone=phone,
                                 gender=gender,
                                 isAdmin=isAdmin,
                                 tagName=tagName,
                                 # departmentName=depart.name,
                                 # departmentID=depart.id
                                 ))

        except Exception as e:
            raise e

    @classmethod
    async def register_admin(cls,
                             username: str, phone="99999999999"):
        """
        注册管理员账号。

        使用 transaction() 自动管理 session 和事务边界。

        Args:
            username: 用户名
            phone: 手机号

        Returns:
            int: 新创建的管理员 ID
        """
        try:
            # 统一使用 transaction() 替代 async_session() + manual commit
            # 自动创建 session + begin，退出时自动 commit
            async with cls.transaction() as session:
                _pwd_hash = await cls.set_password(username)
                admin = User(username=username,
                             email=username + "@hub.com",
                             password=_pwd_hash,
                             phone=phone,
                             gender=GenderEnum.MALE,
                             isAdmin=True,
                             tagName="ADMIN",
                             )

                session.add(admin)
                await session.flush()
                return admin.id

        except Exception as e:
            raise e

    @classmethod
    async def login(cls, username: str, password: str):
        """
        用户登录验证。

        使用 session_scope() 自动管理 session 生命周期（只读查询）。

        Args:
            username: 用户名
            password: 明文密码

        Returns:
            str: JWT token

        Raises:
            AuthError: 用户不存在或密码错误时抛出
        """
        try:
            # 统一使用 session_scope() 替代直接 async_session()
            async with cls.session_scope() as session:
                user = await cls.get_by(session=session, username=username)
                if user:
                    if await cls.check_password(user.password, password):
                        return await cls.generate_token(user)
                    else:
                        raise AuthError("密码错误")
                else:
                    raise AuthError("用户不存在")
        except Exception as e:
            raise e

    @staticmethod
    async def set_password(password: str) -> str:
        """hash 密码"""
        return generate_password_hash(password)

    @staticmethod
    async def check_password(password_hash: str, password: str) -> bool:
        """校验密码"""
        return check_password_hash(password_hash, password)

    @staticmethod
    async def generate_token(user: User, expires_time: int = 3600 * 24 * 2) -> str:
        """
        生成token
        param user 当前用户
        param expires_time 超时时间
        """
        token = {"id": user.id,
                 "isAdmin": user.isAdmin,
                 "expires_time": time.time() + expires_time}
        try:
            return jwt.encode(token, Config.SECRET_KEY, algorithm="HS256")
        except Exception:
            raise AuthError("登录状态校验失败, 请重新登录")

    @staticmethod
    async def parse_token(token: str) -> dict:
        """
        解析token
        :param token:
        :return:
        """
        try:
            return jwt.decode(token, Config.SECRET_KEY, algorithms=["HS256"])
        except Exception:
            raise AuthError("请重新登陆")


class UserVarsMapper(Mapper[UserVars]):
    __model__ = UserVars

    @classmethod
    async def add_or_update(cls, user: User, varInfo: AddOrUpdateUserVars):
        """
        更新或者添加
        """
        if varInfo.id:
            await cls.update_by_id(update_user=user,
                                   **varInfo.model_dump(exclude_unset=True,
                                                        exclude_none=True))
        else:
            userInfo = {"user_id": user.id, "user_name": user.username}
            await cls.save(creator_user=user, **varInfo.model_dump(exclude_unset=True,
                                                                  exclude_none=True),
                           **userInfo)
