#!/usr/bin/env python# -*- coding:utf-8 -*-# @Time : 2024/6/6# @Author : cyq# @File : __init__.py# @Software: PyCharm# @Desc:import jsonfrom math import ceilfrom sqlalchemy.ext.asyncio import AsyncSessionfrom sqlalchemy import select, func, and_from app.exception import DBErrorfrom model import async_sessionfrom model.basic import BaseModelfrom model.base.user import Userfrom typing import TypeVar, List, Type, NoReturn, Dictfrom utils import logT = TypeVar('T', bound='BaseModel')class Page:    DESC = 'descend'    ASC = "ascend"class Mapper:    __model__: Type[BaseModel]    @classmethod    async def save(cls: Type[T], **kwargs) -> T:        """        插入数据        :param kwargs:        :return:        """        try:            async with async_session() as session:                async with session.begin():                    model = cls.__model__(**kwargs)                    await cls.add_flush_expunge(session, model)                    return model        except Exception as e:            raise e    @classmethod    async def save_with_creator(cls: Type[T], creator: int, **kwargs) -> T:        """        插入数据        :param creator 写入创建人        :param kwargs:        :return:        """        try:            async with async_session() as session:                async with session.begin():                    user = Mapper.get_by_id(creator, session)                    if not user:                        raise DBError("创建人信息不存在")                    kwargs.update({"creator": creator, "creatorName": user.username})                    model = cls.__model__(**kwargs)                    await cls.add_flush_expunge(session, model)                    return model        except Exception as e:            log.error(e)            raise DBError("service err")    @classmethod    async def insert(cls: Type[T], **kwargs):        """        插入数据        :param kwargs: cls.field        :return: none        """        try:            async with async_session() as session:                model = cls.__model__(**kwargs)                session.add(model)                await session.commit()        except Exception as e:            raise e    @classmethod    async def get_by_id(cls: Type[T], ident: int, session: AsyncSession = None, desc: str = '') -> T:        """        通过id获取对象        :param ident: id        :param session: AsyncSession        :param desc: 错误描述        :return:mapper_model        """        try:            sql = select(cls.__model__).where(cls.__model__.id == ident)            if session is None:                async with async_session() as session:                    exe = await session.execute(sql)            else:                exe = await session.execute(sql)            model = exe.scalar()            if not model:                raise DBError(f"数据{desc}不存在或已经删除")            return model        except Exception as e:            raise e    @classmethod    async def get_by_uid(cls: Type[T], uid: str, session: AsyncSession = None) -> T:        """        通过uid获取对象        :param uid: model field uid        :param session:AsyncSession        :return: model        """        try:            sql = select(cls.__model__).where(cls.__model__.uid == uid)            if session is None:                async with async_session() as session:                    exe = await session.execute(sql)            else:                exe = await session.execute(sql)            model = exe.scalar_one_or_none()            if not model:                raise DBError(f"数据不存在或已经删除")            return model        except Exception as e:            raise e    @classmethod    async def update_by_id(cls: Type[T], session: AsyncSession = None, **kwargs):        """        通过id更新        :param session        :param kwargs:        """        try:            if not session:                async with async_session() as session:                    _id = kwargs.pop("id")                    async with session.begin():                        target = await cls.get_by_id(_id, session)                        # target = await Mapper.setUpdaterInfo(session,                        #                                      target,                        #                                      kwargs.get("updater", None))                        update_fields = {k: v for k, v in kwargs.items() if k in                                         cls.__model__.__table__.columns}                        for field, value in update_fields.items():                            setattr(target, field, value)                        await session.flush()        except Exception as e:            raise e    @classmethod    async def update_by_uid(cls: Type[T], **kwargs):        """        通过uid更新        :param kwargs:        """        try:            async with async_session() as session:                uid = kwargs.pop("uid")                async with session.begin():                    target = await cls.get_by_uid(uid, session)                    # target = await Mapper.setUpdaterInfo(session,                    #                                      target,                    #                                      kwargs.get("updater", None))                    update_fields = {k: v for k, v in kwargs.items() if k in                                     cls.__model__.__table__.columns}                    for field, value in update_fields.items():                        setattr(target, field, value)                    await session.flush()        except Exception as e:            raise e    @classmethod    async def delete_by_uid(cls: Type[T], uid: str):        """        通过uid删除        :param uid:        """        try:            async with async_session() as session:                async with session.begin():                    targe = await cls.get_by_uid(uid, session)                    await session.delete(targe)        except Exception as e:            raise e    @classmethod    async def delete_by_id(cls: Type[T], ident: int):        """        通过id删除        :param ident:        """        try:            async with async_session() as session:                async with session.begin():                    targe = await cls.get_by_id(ident, session)                    await session.delete(targe)                    await session.flush()        except Exception as e:            raise e    @classmethod    async def get_by(cls: Type[T], session: AsyncSession = None, **kwargs) -> T:        """        通过field获取对象        :param session        :return: mapper_model        """        sql = select(cls.__model__).filter_by(**kwargs)        try:            if session is None:                async with async_session() as session:                    result = await session.scalars(sql)            else:                result = await session.scalars(sql)            return result.first()        except Exception as e:            raise e    @classmethod    async def query_all(cls: Type[T]) -> List[T]:        """        查询所有        :return:mapper_model        """        try:            async with async_session() as session:                query = await session.scalars(select(cls.__model__))                return query.all()        except Exception as e:            raise e    @classmethod    async def query_by(cls: Type[T], **kwargs):        """        通过字段查询        :param kwargs: {xx:xx }        :return:        """        try:            sql = select(cls.__model__).filter_by(**kwargs)            async with async_session() as session:                query = await session.scalars(sql.order_by(cls.__model__.create_time))                return query.all()        except Exception as e:            raise e    @staticmethod    async def flush_expunge(session: AsyncSession, model: T) -> NoReturn:        """        此方法用于确保数据库中的数据与会话中的对象状态同步。它首先强制会话提交所有未提交的更改，        然后刷新指定模型实例，以从数据库中重新加载其状态。最后，它从会话中移除该实例，断开        其与会话的关联。        参数:        - session: AsyncSession类型的参数，表示当前的异步数据库会话。        - model: 模型类的实例，表示需要刷新和从会话中移除的对象。        :param session:        :param model:        :return:        """        await session.flush()        await session.refresh(model)        session.expunge(model)    @classmethod    async def page_query(cls: Type[T], current: int, pageSize: int, **kwargs):        """        分页        :param current:        :param pageSize:        :param kwargs:        :return:        """        try:            async with async_session() as session:                # 处理条件                conditions = await cls.search_conditions(**kwargs)                # 查询                base_query = select(cls.__model__).filter(and_(*conditions))                # 排序                base_query = await cls.sorted_search(base_query, kwargs.pop("sort", None))                base = select(func.count()).select_from(cls.__model__)                # Get total count                total_query = base.filter(*conditions)                total = (await session.execute(total_query)).scalar()                # Paginate and execute                paginated_query = base_query.offset((current - 1) * pageSize).limit(pageSize)                exe = await session.execute(paginated_query)                data = exe.scalars().all()                return await cls.map_page_data(data,                                               total,                                               pageSize,                                               current)        except Exception as e:            raise e    @classmethod    async def get_creator(cls, creatorId: int, session: AsyncSession) -> User:        """        获取创建人信息        :param creatorId:        :param session:        :return:        """        exe = await session.execute(            select(User).where(User.id == creatorId)        )        user = exe.scalar()        if not user:            raise DBError("创建人信息不存在")        return user    @staticmethod    async def add_flush_expunge(session: AsyncSession, model: T):        """        异步将模型添加到数据库会话中，刷新并分离模型。        此函数执行以下操作：        1. 将模型添加到数据库会话中。        2. 刷新会话，将此会话中的更改同步到数据库。        3. 从会话中分离模型，使其成为一个独立的对象，可以重新附加到其他会话。        参数：        - session: AsyncSession - 异步数据库会话。        - model: T - 要添加到会话中的模型对象，类型为泛型 T。        注意：此函数不会提交更改到数据库，它只是将更改暂存并准备模型以进行后续操作。        """        # 将模型添加到会话中        session.add(model)        # 刷新会话，将更改同步到数据库但不提交        await session.flush()        # 从会话中分离模型，使其成为独立对象        session.expunge(model)    @classmethod    async def sorted_search(cls, base_query, sortInfo: Dict = None):        """        排序 默认倒叙        :param base_query        :param sortInfo: 查询条件        :return:        """        sort = None        try:            if sortInfo:                sort = json.loads(sortInfo)                log.info(f"sort info = {sort}")        except (TypeError, json.JSONDecodeError) as e:            log.warning(f"Error parsing sort {e}")        # 排序        if sort:            for k, v in sort.items():                if v == Page.DESC:                    base_query = base_query.order_by(getattr(cls.__model__, k).desc())                else:                    base_query = base_query.order_by(getattr(cls.__model__, k).asc())        else:            base_query = base_query.order_by(cls.__model__.create_time.desc())        log.debug(base_query)        return base_query    @classmethod    async def search_conditions(cls, **kwargs) -> List:        """        查询条件        :param cls:        :param kwargs:        :return:        """        # 条件        conditions = []        for k, v in kwargs.items():            # v is [] -> between            if isinstance(v, list):                conditions.append(                    and_(                        getattr(cls.__model__, k) >= v[0],                        getattr(cls.__model__, k) <= v[1]                    )                )            elif isinstance(v, str):                conditions.append(                    getattr(cls.__model__, k).like(f"{v}%")                )            elif isinstance(v, int):                conditions.append(                    getattr(cls.__model__, k) == v                )            else:                log.warning(f"{k}:{v} is not support")                continue        return conditions    @classmethod    async def map_page_data(cls, data: List, totalNum: int, pageSize: int, current: int):        results = {            "items": data,            "pageInfo": {                "total": totalNum,                "pages": pages(totalNum, pageSize),                "page": current,                "limit": pageSize            }        }        return resultsdef pages(total, pageSize) -> int:    """The total number of pages."""    if total == 0 or total is None:        return 0    return ceil(total / pageSize)