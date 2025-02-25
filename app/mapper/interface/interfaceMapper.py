#!/usr/bin/env python# -*- coding:utf-8 -*-# @Time : 2024/11/20# @Author : cyq# @File : interfaceMapper# @Software: PyCharm# @Desc:import asynciofrom typing import List, Type, Sequence, Dict, Anyfrom sqlalchemy import select, insert, and_, delete, updatefrom sqlalchemy.ext.asyncio import AsyncSessionfrom app.mapper import Mapper, Tfrom app.mapper.interface.interfaceGroupMapper import InterfaceGroupMapperfrom app.mapper.project.projectPart import ProjectPartMapperfrom app.model import async_sessionfrom app.model.base import User, CasePartfrom app.model.interface import InterfaceModel, InterFaceCaseModel, inter_case_association, InterfaceGroupModel, \    api_task_associationfrom app.model.interface.interfaceScriptDescModel import InterfaceScriptDescfrom interface.recoder import Recordfrom utils import MyLogurulog = MyLoguru().get_logger()__all__ = ['InterfaceMapper', 'InterfaceCaseMapper', 'InterfaceScriptMapper']class InterfaceMapper(Mapper):    __model__ = InterfaceModel    @classmethod    async def set_interfaces_parts(cls, part_id: int, interfaces: List[int]):        """        设置接口 所属模块        """        try:            async with async_session() as session:                async with session.begin():                    stmts = [                        update(InterfaceModel).where(                            InterfaceModel.id == interface                        ).values(                            part_id=part_id                        )                        for interface in interfaces]                    await asyncio.gather(*[session.execute(stmt) for stmt in stmts])        except Exception as e:            raise e    @classmethod    async def upload(cls, apis: List[Dict[str, Any]], project_id: str, part_id: str, env_id: str, creator: User):        """        批量上传 API 数据并插入到数据库。        :param apis: API 数据列表        :param project_id: 项目 ID        :param part_id: 父级 Part ID        :param env_id: 环境 ID        :param creator: 创建者用户对象        :return: None        """        try:            async with async_session() as session:                async with session.begin():                    # 提取并插入 Part                    part_names = [api.pop("part") for api in apis]                    parts = []                    for name in set(part_names):                        parts.append(await cls.insert_part(name, session, int(part_id), int(project_id), creator))                    # 插入 API 数据                    api_tasks = [                        cls.insert_inter_with_semaphore(session,                                                        int(project_id),                                                        int(env_id),                                                        parts[index], creator, api["data"])                        for index, api in enumerate(apis)                    ]                    await asyncio.gather(*api_tasks, return_exceptions=True)        except Exception as e:            log.error(f"Error in upload method: {e}")            raise    @staticmethod    async def insert_inter_with_semaphore(            session: AsyncSession, project_id: int, env_id: int, part_id: int, creator: User, data: List[Dict[str, Any]]    ):        """        插入 API 数据到数据库，使用 Semaphore 控制并发度。        :param session: 数据库会话        :param project_id: 项目 ID        :param env_id: 环境 ID        :param part_id: Part ID        :param creator: 创建者用户对象        :param data: API 数据列表        """        semaphore = asyncio.Semaphore(5)  # 同时最多允许5个并发任务        async with semaphore:            try:                for api_data in data:                    api_data.update({                        "project_id": project_id,                        "env_id": env_id,                        "part_id": part_id,                        "creator": creator.id,                        "creatorName": creator.username,                        "status": "DEBUG",                        "level": "P1",                    })                    api = InterfaceModel(**api_data)                    session.add(api)            except Exception as e:                log.error(f"Error in insert_inter_with_semaphore: {e}")                raise    @staticmethod    async def insert_part(            part_name: str, session: AsyncSession, parent_id: int, project_id: int, creator: User    ) -> int:        """        :param part_name: Part 名称        :param session: 数据库会话        :param parent_id: 父级 Part ID        :param project_id: 项目 ID        :param creator: 创建者用户对象        :return: 插入的 Part ID        """        try:            # 获取父级 Part 和子 Part 是否存在            parent_part = await ProjectPartMapper.get_by_id(parent_id, session)            _exist = await  session.execute(                select(CasePart).where(                    and_(                        CasePart.parentID == parent_id,                        CasePart.title == part_name                    )                )            )            existing_part: CasePart = _exist.scalar_one_or_none()            if existing_part and part_name == existing_part.title:                log.debug(f"子 Part '{part_name}' 已存在")                return existing_part.id            # 创建新的 Part            child_part = CasePart(                title=part_name,                projectID=project_id,                parentID=parent_part.id,                isRoot=False,                creator=creator.id,                creatorName=creator.username,                rootID=parent_part.rootID if parent_part.isRoot else parent_part.rootID            )            session.add(child_part)            await session.flush()            return child_part.id        except Exception as e:            log.error(f"Error in insert_part_with_semaphore: {e}")            raise    @classmethod    async def remove(cls, interId: int):        """            删除api接口            关联删除处理            api task association            api group association            api case association        """        try:            async with async_session() as session:                async with session.begin():                    api = await cls.get_by_id(interId, session)                    from .interfaceTaskMapper import InterfaceTaskMapper                    await InterfaceTaskMapper.set_task_when_api_remove(session, interId)                    await InterfaceGroupMapper.set_group_when_api_remove(session, interId)                    await InterfaceCaseMapper.set_case_when_api_remove(session, interId)                    await session.delete(api)                    await session.flush()        except Exception as e:            raise e    @staticmethod    async def copy_record_2_api(recordId: str, creator: User):        """        录制转API        """        try:            recordInfos = await Record.query_record(creator.uid)            if not recordInfos:                raise Exception("未查询到录制信息")            for record in recordInfos:                if record.get("uid") == recordId:                    kwargs = {                        "env_id": -1,                        "url": record['url'],                        "desc": record['url'],                        "method": record['method'],                        "headers": record['headers'],                        "params": record['params'],                        "data": record['data'],                        "body": record['body'],                        "body_type": record['body_type']                    }                    return kwargs        except Exception as e:            raise e    @classmethod    async def save_record(cls, creatorUser: User, recordId: str, **kwargs):        """        录制转API        """        try:            record = await cls.copy_record_2_api(recordId, creatorUser)            kwargs.update(record)            return await cls.save(creatorUser=creatorUser, **kwargs)        except Exception as e:            raise    @classmethod    async def insert_api(cls, part_id: int, **kwargs) -> InterfaceModel:        try:            async with async_session() as session:                async with session.begin():                    part: CasePart = await ProjectPartMapper.get_by_id(ident=part_id)                    if not part.isRoot:                        kwargs['part_root_id'] = part.rootID                    else:                        kwargs['part_root_id'] = part.id                    model = cls.__model__(**kwargs)                    await cls.add_flush_expunge(session, model)                    return model        except Exception as e:            raise e    @classmethod    async def copy_api(cls, apiId: int, creator: User, session: AsyncSession = None,                       is_copy_name: bool = False, is_common: bool = False) -> "InterfaceModel":        """        复制API        :param apiId: 待复制API        :param creator: 创建人        :param session: session        :param is_copy_name: 复制api name        :param is_common: 复制api  common        """        try:            # 封装为一个内部函数，减少重复代码            async def copy_api_logic(session: AsyncSession):                target_api = await cls.get_by_id(ident=apiId, session=session)                target_api_map = target_api.copy_map                if not is_copy_name:                    target_api_map['name'] = target_api_map['name'] + "(副本)"                new_api = cls.__model__(                    **target_api_map,                    creator=creator.id,                    creatorName=creator.username                )                new_api.is_common = is_common                await cls.add_flush_expunge(session, new_api)                return new_api            # 使用一个session上下文管理器，如果没有传入session则创建一个            if session is None:                async with async_session() as session:                    async with session.begin():                        return await copy_api_logic(session)            else:                # 如果传入了session，直接使用它                return await copy_api_logic(session)        except Exception as e:            raise e    @classmethod    async def query_added(cls, beginTime: str, endTime: str):        """查询新增"""        try:            async with async_session() as session:                sql = select(InterfaceModel).join(CasePart,                                                  InterfaceModel.part_id == CasePart.id                                                  ).where(                    and_(                        InterfaceModel.create_time >= beginTime,                        InterfaceModel.create_time <= endTime                    )                )                sca = await session.scalars(sql)                data = sca.all()                return data        except Exception as e:            raise e    @staticmethod    async def new_api_2_group(session: AsyncSession, group: InterfaceGroupModel) -> InterfaceModel:        try:            api = InterfaceModel(                name=group.name,                description=group.description,                project_id=group.project_id,                part_id=group.part_id,                is_common=False,                is_group=True,                group_id=group.id,                method="GROUP",                status="DEBUG",                level="P2",                url="-",                body_type=0            )            await InterfaceMapper.add_flush_expunge(session, api)            return api        except Exception as e:            raise eclass InterfaceCaseMapper(Mapper):    __model__ = InterFaceCaseModel    @classmethod    async def append_record(cls, creatorUser: User, recordId: str, caseId: int):        """        录制 append 用例        """        try:            case = await cls.get_by_id(ident=caseId)            if not case:                raise Exception("用例不存在")            recordApi = await InterfaceMapper.copy_record_2_api(recordId, creatorUser)            recordApi['name'] = recordApi['url'][:5] + '...'            recordApi['desc'] = f"{recordApi['method']} : {recordApi['url']} "            recordApi['is_common'] = 0            recordApi['status'] = "DEBUG"            recordApi['level'] = "P2"            recordApi['project_id'] = case.project_id            recordApi['part_id'] = case.part_id            api = await InterfaceMapper.save(creatorUser=creatorUser, **recordApi)            return await cls.add_api(                caseId=case.id,                apiId=api.id            )        except Exception as e:            raise e    @classmethod    async def remove_api(cls, caseId: int, apiId: int):        """        删除关联的api        if common 解除关联        """        try:            async with async_session() as session:                async with session.begin():                    caseApi: InterFaceCaseModel = await cls.get_by_id(ident=caseId, session=session)                    api: InterfaceModel = await InterfaceMapper.get_by_id(ident=apiId, session=session)                    # 删除关联表数据                    await session.execute(inter_case_association.delete().where(                        inter_case_association.c.inter_case_id == caseId,                        inter_case_association.c.interface_id == apiId                    ))                    # 非公共用例直接删除                    if not api.is_common:                        await session.delete(api)                    # 中间表重新排序                    apis = await session.execute(                        select(InterfaceModel).join(                            inter_case_association,                            inter_case_association.c.interface_id == InterfaceModel.id                        ).where(                            inter_case_association.c.inter_case_id == caseId                        ).order_by(                            inter_case_association.c.step_order                        )                    )                    apis = apis.scalars().all()                    caseApi.apiNum = len(apis)                    for index, api in enumerate(apis, start=1):                        sql = inter_case_association.update().where(                            (inter_case_association.c.inter_case_id == caseId) &                            (inter_case_association.c.interface_id == api.id)                        ).values(step_order=index)                        await session.execute(sql)        except Exception as e:            raise e    @classmethod    async def reorder_apis(cls, caseId: int, apiIds: List[int]):        """        关联api 重新排序        """        try:            async with async_session() as session:                async with session.begin():                    for index, api in enumerate(apiIds, start=1):                        sql = inter_case_association.update().where(                            (inter_case_association.c.inter_case_id == caseId) &                            (inter_case_association.c.interface_id == api)                        ).values(step_order=index)                        await session.execute(sql)        except Exception as e:            raise e    @classmethod    async def query_interface_by_caseId(cls, caseId: int) -> List[InterfaceModel]:        """        根据接口id查询        """        try:            async with async_session() as session:                apis = await session.scalars(                    select(InterfaceModel).join(                        inter_case_association,                        inter_case_association.c.interface_id == InterfaceModel.id                    ).where(                        inter_case_association.c.inter_case_id == caseId                    ).order_by(                        inter_case_association.c.step_order                    )                )                return apis.all()        except Exception as e:            log.exception(e)            raise e    @classmethod    async def add_api(cls, caseId: int, apiId: int):        """        case 添加单个 api        """        try:            async with async_session() as session:                async with session.begin():                    api_case = await cls.get_by_id(ident=caseId, session=session)                    api_case.apiNum += 1                    last_step_index = await cls.get_last_index(session, caseId)                    await session.execute((insert(inter_case_association).values(                        dict(                            interface_id=apiId,                            inter_case_id=caseId,                            step_order=last_step_index + 1                        )                    )))        except Exception as e:            log.error(e)            raise e    @classmethod    async def add_common_apis(cls, caseId: int, commonApis: List[int]):        try:            async with async_session() as session:                async with session.begin():                    api_case = await cls.get_by_id(ident=caseId, session=session)                    api_case.apiNum += len(commonApis)                    last_step_index = await cls.get_last_index(session, caseId)                    log.debug(f"last_step = {last_step_index}")                    for index, apiId in enumerate(commonApis, start=last_step_index + 1):                        log.debug(f"index = {index} apiId = {apiId}")                        await session.execute((insert(inter_case_association).values(                            dict(                                interface_id=apiId,                                inter_case_id=caseId,                                step_order=index                            )                        )))        except Exception as e:            raise e    @classmethod    async def copy_case(cls, caseId: int, creator: User):        """        复制用例        """        try:            async with async_session() as session:                async with session.begin():                    targe_case: InterFaceCaseModel = await cls.get_by_id(ident=caseId, session=session)                    target_api_map = targe_case.copy_map                    target_api_map['title'] = target_api_map['title'] + "(副本)"                    new_case = InterFaceCaseModel(                        **target_api_map,                        creator=creator.id,                        creatorName=creator.username                    )                    await cls.add_flush_expunge(session, new_case)                    apiIds = await session.scalars(select(inter_case_association).where(                        inter_case_association.c.inter_case_id == caseId                    ).order_by(inter_case_association.c.step_order.desc()))                    apiIds = apiIds.all()                    if apiIds:                        new_apis = []                        for ident in apiIds:                            new_api: InterfaceModel = await InterfaceMapper.copy_api(ident,                                                                                     session=session,                                                                                     is_copy_name=True,                                                                                     creator=creator)                            new_apis.append(new_api)                        for index, api in enumerate(new_apis, start=1):                            await session.execute(insert(inter_case_association).values(                                dict(                                    interface_id=api.id,                                    inter_case_id=new_case.id,                                    step_order=index                                )))                        await session.flush()        except Exception as e:            log.error(e)            raise e    @classmethod    async def copy_case_api(cls, caseId: int, apiId: int, copyer: User):        """        复制用例中api 关联添加到底部        """        try:            async with async_session() as session:                async with session.begin():                    case = await cls.get_by_id(ident=caseId, session=session)                    case.apiNum += 1                    new_api = await InterfaceMapper.copy_api(apiId=apiId, creator=copyer,                                                             session=session)                    last_step_index = await cls.get_last_index(session, caseId)                    await session.execute((insert(inter_case_association).values(                        dict(                            interface_id=new_api.id,                            inter_case_id=caseId,                            step_order=last_step_index + 1                        )                    )))        except Exception as e:            raise e    @staticmethod    async def get_last_index(session: AsyncSession, caseId: int) -> int:        try:            sql = (                select(inter_case_association.c.step_order).where(                    inter_case_association.c.inter_case_id == caseId                ).order_by(inter_case_association.c.step_order.desc()).limit(1)            )            # Execute the query            log.debug(sql)            result = await session.execute(sql)            last_step_order = result.scalar()  # Fetch the first (and only) result            return last_step_order or 0        except Exception as e:            raise e    @classmethod    async def add_group_step(cls, caseId: int, groupIds: List[int]):        """        添加分组        """        try:            async with async_session() as session:                async with session.begin():                    case: InterFaceCaseModel = await cls.get_by_id(ident=caseId, session=session)                    case.apiNum += len(groupIds)                    last_step_index = await cls.get_last_index(session, caseId)                    for index, groupId in enumerate(groupIds, start=last_step_index + 1):                        group = await InterfaceGroupMapper.get_by_id(session=session, ident=groupId)                        # 需要创建一个 api 关联 group                        api = await InterfaceMapper.new_api_2_group(session, group=group)                        await session.execute((insert(inter_case_association).values(                            dict(                                interface_id=api.id,                                inter_case_id=caseId,                                step_order=index                            )                        )))        except Exception as e:            raise e    @classmethod    async def remove_case(cls, caseId: int):        """        逻辑删除        删除关联 非公共api        删除关联 group        :param caseId:        :return:        """        try:            async with async_session() as session:                async with session.begin():                    case = await cls.get_by_id(ident=caseId, session=session)                    query_api = await session.execute(                        select(InterfaceModel).join(                            inter_case_association,                            inter_case_association.c.inter_case_id == caseId                        )                    )                    apis = query_api.scalars().all()                    log.debug(apis)                    # if task  task case_num -1                    from app.mapper.interface import InterfaceTaskMapper                    await  InterfaceTaskMapper.set_task_when_case_remove(session, caseId)                    # 删除所有关联                    await session.execute(                        delete(inter_case_association).where(                            inter_case_association.c.inter_case_id == caseId                        )                    )                    # 删除所有非公共API                    private_apis = [api for api in apis if not api.is_common]                    for api in private_apis:                        await session.delete(api)                    await session.delete(case)        except Exception as e:            raise e    @staticmethod    async def set_case_when_api_remove(session: AsyncSession, apiId: int):        try:            query = await session.scalars(select(InterFaceCaseModel).join(                inter_case_association,                inter_case_association.c.inter_case_id == InterFaceCaseModel.id            ).where(                inter_case_association.c.interface_id == apiId            ))            cases: Sequence[InterFaceCaseModel] = query.all()            log.debug(cases)            if cases:                for case in cases:                    case.apiNum -= 1        except Exception as e:            raise eclass InterfaceScriptMapper(Mapper):    __model__ = InterfaceScriptDescclass InterfaceFuncMapper(Mapper):    __model__ = InterfaceScriptDesc