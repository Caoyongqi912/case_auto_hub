#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Time : 2024/6/6
# @Author : cyq
# @File : __init__.py
# @Software: PyCharm
# @Desc: Mapper基础类，提供通用的数据库操作方法
import json
from math import ceil
from typing import TypeVar, List, Type, Any, Optional, Generic, Dict

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, text, delete
from sqlalchemy.sql.functions import count

from app.exception import NotFind, CommonError
from app.model import async_session, BaseModel
from app.model.base import User
from utils import log


def pages(total, pageSize) -> int:
    """计算总页数"""
    if total == 0 or total is None:
        return 0
    return ceil(total / pageSize)


def set_creator(user: User, **kwargs):
    """设置创建人信息"""
    kwargs.update({"creator": user.id, "creatorName": user.username})
    return kwargs


def set_updater(user: User, **kwargs):
    """设置更新人信息"""
    kwargs.update({"updater": user.id, "updaterName": user.username})
    return kwargs


M = TypeVar('M', bound=BaseModel)


class Mapper(Generic[M]):
    """通用Mapper基类，提供标准的CRUD操作"""
    __model__: Type[M] | Any

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        if not hasattr(cls, '__model__'):
            raise TypeError(f"{cls.__name__} 必须定义 __model__ 类变量")

    @classmethod
    async def _execute_query(cls, stmt, session: Optional[AsyncSession] = None):
        """
        执行查询语句，自动处理会话管理
        :param stmt: 查询语句
        :param session: 可选的会话对象
        :return: 查询结果
        """
        if session is None:
            async with async_session() as session:
                return await session.execute(stmt)
        return await session.execute(stmt)

    @classmethod
    async def _get_by_field(cls, field_name: str, value: Any, session: Optional[AsyncSession] = None,
                            raise_error: bool = True, desc: str = '') -> M:
        """
        通过字段获取对象的通用方法
        :param field_name: 字段名
        :param value: 字段值
        :param session: 可选的会话对象
        :param raise_error: 是否抛出异常
        :param desc: 错误描述
        :return: 模型实例
        """
        try:
            field = getattr(cls.__model__, field_name)
            stmt = select(cls.__model__).where(field == value)
            result = await cls._execute_query(stmt, session)
            instance = result.scalar_one_or_none()

            if not instance and raise_error:
                error_msg = f"数据{desc}不存在或已经删除，{field_name}: {value}" if desc else f"数据不存在，{field_name}: {value}"
                raise NotFind(error_msg)
            return instance
        except NotFind:
            raise
        except Exception as e:
            log.error(f"获取{cls.__name__}对象失败，{field_name}: {value}, 错误: {e}")
            raise

    @classmethod
    async def insert(cls, model: M) -> M:
        """模型入库"""
        return await cls._manage_session(session=None, model=model)

    @classmethod
    async def save(cls, creator_user: User = None, session: AsyncSession = None, **kwargs) -> M:
        """
        保存模型实例到数据库，处理创建人信息并返回模型实例
        :param creator_user: 创建人
        :param session: 可选的会话对象
        :param kwargs: 模型字段
        :return: 模型实例
        """
        if creator_user:
            kwargs = set_creator(creator_user, **kwargs)

        try:
            model = cls.__model__(**kwargs)
            return await cls._manage_session(session, model)
        except Exception as e:
            log.error(f"保存{cls.__name__}失败: {e}")
            raise e

    @classmethod
    async def copy_one(cls, target_id: int | M, session: AsyncSession, user: User = None) -> M:
        """复制模型实例"""
        old_one = await cls.get_by_id(target_id, session)
        new_one = cls.__model__(**old_one.copy_map())
        if user:
            new_one.creator = user.id
            new_one.creatorName = user.username
        return await cls.add_flush_expunge(session, new_one)

    @classmethod
    async def get_by_id(cls, ident: int, session: AsyncSession = None, desc: str = '') -> M:
        """
        通过id获取对象
        :param ident: id
        :param session: 可选的会话对象
        :param desc: 错误描述
        :return: 模型实例
        """
        return await cls._get_by_field('id', ident, session, True, desc)

    @classmethod
    async def get_by_uid(cls, uid: str, session: AsyncSession = None, raise_error: bool = True) -> M:
        """
        通过uid获取对象
        :param uid: uid
        :param session: 可选的会话对象
        :param raise_error: 是否抛出异常
        :return: 模型实例
        """
        return await cls._get_by_field('uid', uid, session, raise_error)

    @classmethod
    async def update_by_id(cls, session: AsyncSession = None, updateUser: User = None, **kwargs) -> M:
        """
        通过id更新
        :param session: 可选的会话对象
        :param updateUser: 更新人
        :param kwargs: 更新字段（必须包含id）
        :return: 更新后的模型实例
        """
        try:
            ident = kwargs.pop("id", None)
            if ident is None:
                raise ValueError("id parameter is required")

            kwargs = set_updater(updateUser, **kwargs)

            if not session:
                async with async_session() as session:
                    target = await cls.get_by_id(ident, session)
                    await cls.update_cls(target, session, **kwargs)
                    await session.commit()
            else:
                target = await cls.get_by_id(ident, session)
                await cls.update_cls(target, session, **kwargs)
                await session.commit()
            return target
        except Exception as e:
            log.exception(e)
            raise

    @classmethod
    async def update_by_uid(cls, updateUser: User = None, **kwargs):
        """
        通过uid更新
        :param updateUser: 更新人
        :param kwargs: 更新字段（必须包含uid）
        :return: 更新后的模型实例
        """
        kwargs = set_updater(updateUser, **kwargs)

        try:
            async with async_session() as session:
                uid = kwargs.pop("uid")
                async with session.begin():
                    target = await cls.get_by_uid(uid, session)
                    return await cls.update_cls(target, session, **kwargs)
        except Exception as e:
            raise e

    @classmethod
    async def delete_by_uid(cls, uid: str):
        """
        通过uid删除
        :param uid: uid
        """
        try:
            async with async_session() as session:
                await session.execute(delete(cls.__model__).where(cls.__model__.uid == uid))
                await session.commit()
        except Exception as e:
            raise e

    @classmethod
    async def delete_by_id(cls, ident: int, session: AsyncSession = None):
        """
        通过id删除
        :param ident: id
        :param session: 可选的会话对象
        """
        stmt = delete(cls.__model__).where(cls.__model__.id == ident)
        try:
            if session:
                await session.execute(stmt)
                await session.commit()
            else:
                async with async_session() as session:
                    await session.execute(stmt)
                    await session.commit()
        except Exception as e:
            log.exception(e)
            raise

    @classmethod
    async def delete_by(cls, session: AsyncSession, **kwargs):
        """
        通过属性删除
        :param session: 会话对象
        :param kwargs: 查询条件
        """
        try:
            model = await cls.get_by(session, **kwargs)
            if model:
                await session.delete(model)
                await session.flush()
        except Exception as e:
            raise e

    @classmethod
    async def get_by(cls, session: AsyncSession = None, **kwargs) -> M:
        """
        通过字段获取对象
        :param session: 可选的会话对象
        :param kwargs: 查询条件
        :return: 模型实例
        """
        sql = select(cls.__model__).filter_by(**kwargs)
        try:
            if session is None:
                async with async_session() as session:
                    result = await session.scalars(sql)
            else:
                result = await session.scalars(sql)
            return result.first()
        except Exception as e:
            raise e

    @classmethod
    async def query_all(cls) -> List[M]:
        """查询所有数据"""
        try:
            async with async_session() as session:
                query = await session.scalars(select(cls.__model__))
                return query.all()
        except Exception as e:
            raise e

    @classmethod
    async def query_by(cls, session: AsyncSession = None, **kwargs):
        """
        通过字段查询（AND条件）
        :param kwargs: 查询条件
        :param session:
        :return: 查询结果列表
        """
        try:
            if session:
                query = await session.scalars(
                    select(cls.__model__).filter_by(**kwargs).order_by(cls.__model__.create_time))
            else:
                async with async_session() as session:
                    query = await session.scalars(
                        select(cls.__model__).filter_by(**kwargs).order_by(cls.__model__.create_time))
            return query.all()
        except Exception as e:
            raise e

    @classmethod
    async def query_by_in_clause(cls, target: str, list_: List[Any], session: AsyncSession = None):
        """
        根据指定字段和值列表查询数据（IN子句）
        :param target: 模型中的字段名
        :param list_: 用于IN子句的值列表
        :param session: 可选的会话对象
        :return: 查询结果列表
        """
        if not hasattr(cls.__model__, target):
            raise CommonError("Invalid field name")

        stmt = select(cls.__model__).where(getattr(cls.__model__, target).in_(list_))
        try:
            if session:
                query = await session.scalars(stmt)
                return query.all()
            else:
                async with async_session() as session:
                    query = await session.scalars(stmt)
                    return query.all()
        except Exception as e:
            raise e

    @staticmethod
    async def flush_expunge(session: AsyncSession, model: M):
        """
        刷新会话并分离模型
        :param session: 会话对象
        :param model: 模型实例
        """
        await session.flush()
        await session.refresh(model)
        session.expunge(model)

    @classmethod
    async def page_query(cls, current: int, pageSize: int, **kwargs):
        """
        分页查询
        :param current: 当前页码
        :param pageSize: 每页大小
        :param kwargs: 查询条件和排序
        :return: 分页结果
        """
        try:
            async with async_session() as session:
                conditions = await cls.search_conditions(**kwargs)
                base_query = select(cls.__model__).filter(and_(*conditions))
                base_query = await cls.sorted_search(base_query, kwargs.pop("sort", None))

                total_query = select(func.count()).select_from(cls.__model__).filter(*conditions)
                total = (await session.execute(total_query)).scalar()

                paginated_query = base_query.offset((current - 1) * pageSize).limit(pageSize)
                exe = await session.execute(paginated_query)
                data = exe.scalars().all()

                return await cls.map_page_data(data, total, pageSize, current)
        except Exception as e:
            raise e

    @classmethod
    async def get_creator(cls, creatorId: int, session: AsyncSession) -> User:
        """
        获取创建人信息
        :param creatorId: 创建人ID
        :param session: 会话对象
        :return: 用户对象
        """
        exe = await session.execute(select(User).where(User.id == creatorId))
        user = exe.scalar()
        if not user:
            raise NotFind("创建人信息不存在")
        return user

    @staticmethod
    async def add_flush_expunge(session: AsyncSession, model: M) -> M:
        """
        添加模型到会话，刷新并分离
        :param session: 会话对象
        :param model: 模型实例
        :return: 模型实例
        """
        session.add(model)
        await session.flush()
        session.expunge(model)
        return model

    @classmethod
    async def update_cls(cls, target: M, session: AsyncSession, **kw):
        """
        更新模型实例
        :param target: 目标模型实例
        :param session: 会话对象
        :param kw: 更新字段
        :return: 更新后的模型实例
        """
        try:
            valid_columns = set(cls.__model__.__table__.columns.keys())
            update_fields = {k: v for k, v in kw.items() if k in valid_columns}

            for field, value in update_fields.items():
                setattr(target, field, value)

            await session.flush()
            session.expunge(target)
            return target
        except Exception as e:
            raise e

    @classmethod
    async def sorted_search(cls, base_query, sortInfo: str | Dict = None):
        """
        排序查询（默认按创建时间倒序）
        :param base_query: 基础查询
        :param sortInfo: 排序信息，支持JSON字符串或字典
        :return: 排序后的查询
        """
        sort = None
        try:
            if isinstance(sortInfo, str):
                sort = json.loads(sortInfo)
                if not isinstance(sort, dict):
                    raise ValueError("Invalid JSON format")
            elif isinstance(sortInfo, dict):
                sort = sortInfo
        except (TypeError, json.JSONDecodeError, ValueError):
            pass

        if sort:
            for k, v in sort.items():
                if v == "descend":
                    base_query = base_query.order_by(getattr(cls.__model__, k).desc())
                else:
                    base_query = base_query.order_by(getattr(cls.__model__, k).asc())
        else:
            base_query = base_query.order_by(cls.__model__.create_time.desc())
        return base_query

    @classmethod
    async def search_conditions(cls, **kwargs) -> List:
        """
        构建查询条件
        支持的条件类型:
            - 范围查询: 使用列表或元组 [min, max]
            - 模糊查询: 字符串自动添加 % 通配符
            - 精确匹配: 数字、布尔值、None
        :param kwargs: 查询条件
        :return: 条件列表
        """
        conditions = []
        for k, v in kwargs.items():
            if v is None:
                conditions.append(getattr(cls.__model__, k) is None)
                continue
            if isinstance(v, (tuple, list)):
                conditions.append(and_(getattr(cls.__model__, k) >= v[0], getattr(cls.__model__, k) <= v[1]))
                continue
            if isinstance(v, str):
                conditions.append(getattr(cls.__model__, k).like(f"%{v}%"))
                continue
            if isinstance(v, (int, float, bool)):
                conditions.append(getattr(cls.__model__, k) == v)
                continue
        return conditions

    @classmethod
    async def map_page_data(cls, data: List, totalNum: int, pageSize: int, current: int):
        """
        构建分页数据
        :param data: 数据列表
        :param totalNum: 总记录数
        :param pageSize: 每页大小
        :param current: 当前页码
        :return: 分页结果字典
        """
        return {
            "items": data,
            "pageInfo": {
                "total": totalNum,
                "pages": pages(totalNum, pageSize),
                "page": current,
                "limit": pageSize
            }
        }

    @classmethod
    async def count_(cls) -> int:
        """统计记录数"""
        try:
            async with async_session() as session:
                sql = select(count()).select_from(cls.__model__)
                state = await session.execute(sql)
                return state.scalar()
        except Exception:
            return 0

    @classmethod
    async def tables(cls) -> List[str]:
        """获取数据库表名列表"""
        try:
            sql = """
                  SELECT TABLE_NAME AS table_name
                  FROM information_schema.TABLES
                  WHERE TABLE_SCHEMA = DATABASE() \
                  """
            async with async_session() as session:
                result = await session.execute(text(sql))
                return [row[0] for row in result.fetchall()]
        except Exception as e:
            log.error(e)
            return []

    @classmethod
    async def page_by_module(cls, current: int, pageSize: int, module_type: int,
                             module_id: int = None, **kwargs):
        """
        按模块分页查询
        :param current: 当前页码
        :param pageSize: 每页大小
        :param module_type: 模块类型
        :param module_id: 模块ID
        :param kwargs: 其他查询条件
        :return: 分页结果
        """
        attr = "module_id"
        try:
            async with async_session() as session:
                from app.mapper.project.moduleMapper import get_subtree_ids
                subtree_ids = await get_subtree_ids(session, module_id, module_type)

                base_query = select(cls.__model__).filter(getattr(cls.__model__, attr).in_(subtree_ids))
                conditions = await cls.search_conditions(**kwargs)
                base_query = base_query.filter(and_(*conditions))
                base_query = await cls.sorted_search(base_query, kwargs.pop("sort", None))

                total_query = select(func.count()).select_from(cls.__model__).filter(
                    getattr(cls.__model__, attr).in_(subtree_ids), *conditions)
                total = (await session.execute(total_query)).scalar()

                paginated_query = base_query.offset((current - 1) * pageSize).limit(pageSize)
                data = (await session.execute(paginated_query)).scalars().all()

                return await cls.map_page_data(data, total, pageSize, current)
        except Exception as e:
            log.error(e)
            return []

    @classmethod
    async def _manage_session(cls, session: Optional[AsyncSession], model: M) -> M:
        """
        管理会话，自动处理事务提交
        :param session: 可选的会话对象
        :param model: 模型实例
        :return: 模型实例
        """
        if session is None:
            async with async_session() as new_session:
                async with new_session.begin():
                    return await cls.add_flush_expunge(new_session, model)
        return await cls.add_flush_expunge(session, model)
