# `run_interface_case` 深度代码审查报告(V2)

> 本报告是第一版报告的**超集**,在原有"流程/冗余/过度设计"基础上,补充:
> - **数据模型层**(`BaseModel` / `InterfaceCase` / `InterfaceResult` / `InterfaceCaseContentResult` / 步骤内容子类)
> - **Mapper 层**(`InterfaceCaseMapper` / `InterfaceResultMapper` / `InterfaceContentStepResultMapper` / `bulk_insert_*` / JTI 多态)
> - **执行器 & 子策略**(`InterfaceExecutor` / `step_content_*` / `RequestBuilder` / `UrlBuilder`)
> - **基础设施**(`HttpxClient` / `VariableTrans` / `ScriptManager` / `SocketSender`)
> - **安全性**(Script 沙箱、SSRF、并发资源、SQL 注入)
> - **可观测性、性能、可测试性**

| 项 | 内容 |
| --- | --- |
| 审查目标 | `croe/interface/runner.py` 的 `run_interface_case` 全链路 |
| 关联模块 | runner / executor / step_content / builder / manager / writer / starter / VariableTrans / ScriptManager / HttpxClient / Mapper / Model / BaseModel |
| 审查日期 | 2026-06-18 |
| 报告版本 | V2 - Deep Review |

---

## 〇、TL;DR(总览)

代码经过多轮迭代,核心流程能跑通,但整体存在 4 个系统性问题:

1. **数据建模有"假字段"**:`InterfaceCaseContents.target_id` 在基类里被声明为 `ClassVar`(Python 类变量,不是 SQLAlchemy Column),所有走 `to_dict` 的逻辑都会拿到 `None`,而真正存数据的字段是各子类的 `target_id` Column。这导致模型层的 `target_id` 看似存在,实则在统一序列化时丢失。
2. **模块级单例 + 共享可变状态**:`result_writer` 是模块级 `ResultWriter()` 单例,内部有 `api_result_cache` / `content_result_cache`,**所有并发的 `InterfaceRunner` 实例共享同一份缓存**。同时 `ScriptManager` 的 `self._variables` 跨脚本累积。
3. **ScriptManager 沙箱可绕过**:`ALLOWED_NODE_TYPES` 包含 `Import`/`ImportFrom`;`getattr` 等内置函数未拦截,经典 `getattr(obj, '__class__')` 逃逸路径未堵;`SCRIPT_TIMEOUT` 常量定义了但从未生效;`hub_api_request` 是同步 `httpx.Client`,会在事件循环中阻塞。
4. **HttpxClient 资源泄漏**:`_client` 懒初始化但**永远不会被关闭**,且 `self.client.timeout = Timeout(...)` 在每次请求时**直接修改共享 client 的状态**,并发时互相覆盖。

下文按"BUG / 冗余 / 过度设计 / 安全 / 性能 / 可观测性 / 可测试性"分类,逐项给出可定位到行号的修改建议。

---

## 一、流程层 BUG(第一版报告所有项仍成立,这里只列新增)

### BUG-F1 [严重] `interfaceLog` 字段名错位(本应 `interface_log`)
**位置**:
- 写:[runner.py:225](/Users/fanyuxuan/cyq_code/case_auto_hub/croe/interface/runner.py) `case_result.interfaceLog = "".join(self.starter.logs)`
- 模型:[interfaceResultModel.py:102](/Users/fanyuxuan/cyq_code/case_auto_hub/app/model/interfaceAPIModel/interfaceResultModel.py) `interface_log = Column(TEXT, ...)`
- 读:[result_writer.py:296-307](/Users/fanyuxuan/cyq_code/case_auto_hub/croe/interface/writer/result_writer.py) `case_result.interface_log = logs`

模型字段叫 `interface_log`(snake_case),runner 写的是 `interfaceLog`(camelCase)。SQLAlchemy 默认不会做大小写归一,这条赋值**默默失败**,日志从未被持久化。

### BUG-F2 [严重] 早返 `return await self.starter.over()` 与 `Tuple[bool, Optional[Any]]` 签名不一致
**位置**:
- [runner.py:134, 149](/Users/fanyuxuan/cyq_code/case_auto_hub/croe/interface/runner.py) `return await self.starter.over()`
- [runner.py:112](/Users/fanyuxuan/cyq_code/case_auto_hub/croe/interface/runner.py) `-> Tuple[bool, Optional[Any]]`
- 调用方:[task.py:253](/Users/fanyuxuan/cyq_code/case_auto_hub/croe/interface/task.py) `success, _ = await ...`

`starter.over()` 返回 `None`(`SocketSender.over` 无 return),所以这两个早返路径实际返回 `None`,而注解要求 `Tuple[bool, Optional[Any]]`。
- 类型注解层面:会被 mypy 抓住。
- 运行时层面:`success, _ = await None` 在 `task.py:253` 立即抛 `TypeError: cannot unpack non-iterable NoneType`,任务统计直接被截断,后续 case 全部不再执行。

### BUG-F3 [中高] `init_global_headers` 静默错位
**位置**:[runner.py:318-331](/Users/fanyuxuan/cyq_code/case_auto_hub/croe/interface/runner.py)

```python
async def init_global_headers(self) -> Optional[List[InterfaceGlobalHeader]]:
    global_headers = await InterfaceGlobalHeaderMapper.query_all()
    if not global_headers:
        log.info(f"use global_headers {global_headers}")
        return None
    if global_headers:                              # 永远 True(因为上面 return 了 False 分支)
        await self.starter.send(...)
        self.interface_executor.g_headers = global_headers or []   # `or []` 永远走不到
```

- 函数声明返回 `Optional[List[...]]`,但成功分支没 `return`,PyLance/mypy 必报。
- `self.global_headers`(实例字段)从未被任何代码读取——死字段;真正使用的是 `self.interface_executor.g_headers`,造成两个字段的指向永久不一致。
- 用户配置了全局 header 但**事实上不生效**——这是最严重的隐性 BUG,因为接口跑通了用户不会想到是 header 没生效。

### BUG-F4 [中高] `init_interface_case_vars` 静默吞错
**位置**:[runner.py:293-316](/Users/fanyuxuan/cyq_code/case_auto_hub/croe/interface/runner.py)

整个方法被 `try/except Exception as e: log.error(...)` 包住。变量加载失败时,后续步骤会用空变量执行,断言静默失败。建议至少 `log.exception` + 通知用户,且 `init_global_headers` 同理。

### BUG-F5 [中] `error_stop` 状态机不统一
**位置**:[runner.py:204-215](/Users/fanyuxuan/cyq_code/case_auto_hub/croe/interface/runner.py)

```python
case_success = case_success and step_success
case_result.progress = (index * 100) // total_steps
if not case_success and error_stop:
    ...
    case_result.progress = 100                    # 强制 100
    await result_writer.update_case_progress(case_result)
    break
```

- "按比例进度"和"强制 100" 两套语义混在同一字段。
- 失败步骤的 `case_result.result` 是在子策略中置为 `ERROR`,但 `case_result.interfaceLog` 在 break 之后没有重置,继续执行到 `case_result.interfaceLog = "".join(self.starter.logs)` 时把 `interfaceLog` 写到 `case_result` 上(同 BUG-F1,实际写错字段)。

### BUG-F6 [中] `progress` int 截断语义不一致
`(index * 100) // total_steps` 在 `total_steps=4, index=3` 时为 75,`index=4` 才 100。如果用户在第 3 步中途点击"停止",前端看 75% 是符合直觉的;但 `error_stop` 路径直接置 100,前端看 100% 以为跑完了。语义没对齐。

### BUG-F7 [低] `init_case_result` 内部 log 错误且冗余
**位置**:[result_writer.py:131-133](/Users/fanyuxuan/cyq_code/case_auto_hub/croe/interface/writer/result_writer.py)

```python
log.info("task_result {}".format(case_result))   # 标签写"task_result"但变量是 case_result
log.info("task_result {}".format(task_result))   # 这个才是 task_result
```
两条都只是 `log.info(obj)`,只输出对象 str;真要调试时,这两行帮不上忙,反而误导。

---

## 二、模型层 BUG(`BaseModel` / `InterfaceCase` / `InterfaceResult` / 步骤内容)

### BUG-M1 [严重] `InterfaceCaseContents.target_id` 是 `ClassVar` 不是 Column
**位置**:[interfaceCaseContentsModel.py:43](/Users/fanyuxuan/cyq_code/case_auto_hub/app/model/interfaceAPIModel/contents/interfaceCaseContentsModel.py)

```python
class InterfaceCaseContents(BaseModel):
    ...
    target_id: ClassVar[int | None] = None    # ← Python 类变量,SQLAlchemy 不识别
    __mapper_args__ = {
        'polymorphic_on': content_type,
        ...
    }
```

`ClassVar` 是 `typing.ClassVar`,在 SQLAlchemy 0.x / 1.x 默认是被忽略的注解类型(BaseModel 用 `declarative_base()`)。子类的 `target_id` 才是真正的 Column:

```python
class APIStepContent(InterfaceCaseContents):
    step_content_id = step_content_id_column()
    target_id = Column(INTEGER, ForeignKey('interface.id', ...))  # ← 真正的字段
```

后果:
- 在 `InterfaceCaseContents.to_dict()` 里 `result['target_id'] = self.target_id` 永远拿到 `None`(类变量),因为 `self_and_descendants` mapper 遍历时 `target_id` 不在基类表里。
- 实际每个子类的 `target_id` 也写不进 dict(基类 `to_dict` 后再叠加子类 mapper 字段时,字典里直接覆盖成了 `None`)。
- 任何调用方 `interface_case_content.target_id` 拿到的是**当前实例的子类的 Column 值**;但 `to_dict()` 出来变成 `None`。**序列化失真**。

**修复建议**:删除基类的 `target_id: ClassVar[int | None] = None`,改用 `@declared_attr` 让每个子类各自声明 `target_id` Column;或者在 `to_dict` 里**不要覆盖子类字段**(从子类 mapper 拿当前行 `__table__.columns` 时,跳过 `target_id` 已存在的键)。

### BUG-M2 [严重] `InterfaceCase.interface_case_name` 字段长度不够
**位置**:
- 模型:[interfaceResultModel.py:95](/Users/fanyuxuan/cyq_code/case_auto_hub/app/model/interfaceAPIModel/interfaceResultModel.py) `interface_case_name = Column(String(20), ...)`
- 来源:[result_writer.py:114](/Users/fanyuxuan/cyq_code/case_auto_hub/croe/interface/writer/result_writer.py) `case_result.interface_case_name = interface_case.case_title`
- 来源定义:[interfaceCaseModel.py:20](/Users/fanyuxuan/cyq_code/case_auto_hub/app/model/interfaceAPIModel/interfaceCaseModel.py) `case_title = Column(String(40), nullable=True, ...)`

`case_title` 是 40 字符,`interface_case_name` 是 20 字符。**长于 20 字符的 case 标题在 MySQL strict mode 下会报 `Data too long`,整个 case_result 插入失败**,但 result_writer 没做长度检查,异常会冒泡到 `run_interface_case` 的 except 分支(同第一版 BUG-1,只 log 不写回状态)。

**类似隐患**:
- `InterfaceResult.interface_name` 是 `String(50)`,`Interface.interface_name` 是 `String(100)` —— 一旦单接口名超 50 同样爆炸。
- `InterfaceTaskResult.task_uid` 是 `String(10)`,`task_name` 是 `String(20)`,`InterfaceTask.interface_task_title` 是 `String(20)` —— task 名 20/20 平齐,勉强够,但 task_uid 10 字符对于 uid 生成规则(`GenerateTools.uid`)是否够,要看生成实现。

### BUG-M3 [严重] `BaseModel.map` / `to_dict` 不识别 JTI 子类字段
**位置**:[basic.py:30-65](/Users/fanyuxuan/cyq_code/case_auto_hub/app/model/basic.py)

```python
@property
def map(self) -> dict:
    _ = dict()
    for c in self.__table__.columns:    # ← 只遍历当前表(基类)
        v = getattr(self, c.name)
        ...
```

`BaseModel` 用 `self.__table__.columns` 遍历,对于 Joined Table Inheritance 的基类,`self.__table__` 是 `interface_case_step_content` 或 `interface_case_content_result` 的**基类表**,**永远不会**包含子类字段(如 `interface_result_id`、`total_api_num`、`loop_count` 等)。

后果:
- `case_result.map['start_time']` 能拿到(基类字段),但 `case_result.map['total_api_num']`(子类字段)就拿不到。
- `result_writer.py:292` 用 `case_result.map['start_time']` 算时长,刚好用到基类字段,逃过一劫;但 `finalize_task_result` 同理用 `task_result.map['start_time']` 也凑巧能跑。
- 一旦有人用 `case_result.map['interface_result_id']` 就会 KeyError,或者更阴险地返回 None 还不报错。

**修复建议**:要么在 `BaseModel.map` / `to_dict` 里迭代 `self.__class__.__table__.columns`(只当前类的表),要么用 SQLAlchemy 的 `inspect(self).mapper.columns` 来获取全部(包括继承来的)。

### BUG-M4 [中高] `InterfaceCaseContentResult.to_dict` 的 mapper 遍历可能重复
**位置**:[interfaceResultModel.py:218-256](/Users/fanyuxuan/cyq_code/case_auto_hub/app/model/interfaceAPIModel/interfaceResultModel.py)

```python
for mapper in self.__class__.__mapper__.self_and_descendants:
    if mapper.local_table.name != self.__tablename__:
        for col in mapper.local_table.columns:
            if hasattr(self, col.name):
                value = getattr(self, col.name)
                ...
                result[col.name] = value
```

`self_and_descendants` 会包含基类;但代码用 `if mapper.local_table.name != self.__tablename__` 跳过**当前类对应的表**。然而 `self.__tablename__` 永远是**基类的表名**(`interface_case_content_result`),而 `self.__class__` 如果是 `APIStepContentResult`,其 `local_table` 是 `interface_case_content_result_api`,不等于基类名,所以会处理——OK。但反过来,如果有人不小心调了 `InterfaceCaseContentResult(...).to_dict()`(基类实例,content_type=NULL),`self.__tablename__` == `interface_case_content_result`,会被跳过,**结果字典里完全没有子类字段**(虽然基类也没子类字段,但 step_id/cid/case_result_id 这些会漏)。

实际触发点:`Mapper.get_by_id` 返回多态实例,不太可能拿到基类实例,所以这条不太容易触发,但代码意图不清。

### BUG-M5 [中高] `polymorphic_on` 用 enum 整数值,枚举重排会破坏数据
**位置**:
- [interfaceCaseContentsModel.py:46](/Users/fanyuxuan/cyq_code/case_auto_hub/app/model/interfaceAPIModel/contents/interfaceCaseContentsModel.py) `'polymorphic_on': content_type`
- [interfaceResultModel.py:213](/Users/fanyuxuan/cyq_code/case_auto_hub/app/model/interfaceAPIModel/interfaceResultModel.py) `'polymorphic_on': content_type`

`content_type` 是 `INTEGER`,值是 `CaseStepContentType` 枚举的整数值。如果**有人重排枚举值的顺序**(比如把 `STEP_API` 从 1 改成 3,或者插入新值到中间),所有数据库里的 `content_type` 字段立刻指错类型。
- 修复建议:用 `String` 类型 + 枚举名(`'STEP_API'`),或者在 migration 里把 `content_type` 改为字符串。

### BUG-M6 [中] `with_polymorphic: '*'` 的笛卡尔积风险
**位置**:
- [interfaceCaseContentsModel.py:48](/Users/fanyuxuan/cyq_code/case_auto_hub/app/model/interfaceAPIModel/contents/interfaceCaseContentsModel.py) `'with_polymorphic': '*'`
- [interfaceResultModel.py:215](/Users/fanyuxuan/cyq_code/case_auto_hub/app/model/interfaceAPIModel/interfaceResultModel.py) `'with_polymorphic': '*'`

`*` 意味着**所有子类表 LEFT OUTER JOIN**。如果某次 `query_steps` 一次查 50 个步骤,每个步骤最多 1 行(每个子类表),JOIN 出 50×8 = 400 行(去重后回到 50,但行变大 8 倍)。在 Postgres / MySQL 上对于大用例,网络字节数会膨胀。

**修复建议**:默认改成 `with_polymorphic` 不带 `*`,只在需要子类字段时显式指定 `with_polymorphic=[APIStepContentResult, ...]`。

### BUG-M7 [中] `case_result.fail_num == 0` 判定结果
**位置**:[result_writer.py:286-289](/Users/fanyuxuan/cyq_code/case_auto_hub/croe/interface/writer/result_writer.py)

```python
if case_result.fail_num == 0:
    case_result.result = InterfaceAPIResultEnum.SUCCESS
else:
    case_result.result = InterfaceAPIResultEnum.ERROR
```

`result` 字段是 `Boolean` (模型),`InterfaceAPIResultEnum` 是枚举。把 `enum` 直接赋值给 `Boolean` 列,在 SQLAlchemy 里能否写入取决于 `__str__` 行为或 `TypeDecorator` 配置。看起来能跑通是因为 SQLAlchemy 对未识别类型做了字符串化,但语义不清晰。

类似问题在 [task.py:274-277](/Users/fanyuxuan/cyq_code/case_auto_hub/croe/interface/task.py) 和 [step_content_api.py:78](/Users/fanyuxuan/cyq_code/case_auto_hub/croe/interface/executor/step_content/step_content_api.py)。

### BUG-M8 [中] `case_api_num` 与实际步骤数可能不一致
**位置**:
- 模型:[interfaceCaseModel.py:24](/Users/fanyuxuan/cyq_code/case_auto_hub/app/model/interfaceAPIModel/interfaceCaseModel.py) `case_api_num = Column(INTEGER, default=0, comment="接口数量")`
- 增加:[interfaceCaseMapper.py:191-194](/Users/fanyuxuan/cyq_code/case_auto_hub/app/mapper/interfaceApi/interfaceCaseMapper.py) `+ len(interface_ids_to_add)`
- 减少:[interfaceCaseMapper.py:677-681](/Users/fanyuxuan/cyq_code/case_auto_hub/app/mapper/interfaceApi/interfaceCaseMapper.py) `- 1`

`case_api_num` 字段名是"接口数量",但同步逻辑里:
- 关联 API 时 `+ N`(N 是新增步骤数)
- 移除步骤时 `- 1`(写死了 1,如果一次批量移除就不准)
- **移除条件/循环/分组/等待/断言/脚本步骤时,`case_api_num` 不会减少**。

`copy_case` / `copy_content` 时也没看到这个字段的更新逻辑。结果:`case_api_num` 和实际 API 步骤数对不上,前端展示和统计会偏差。

### BUG-M9 [低] `InterfaceCase.case_status` / `interface_status` 是 `String(10)`,但无枚举约束
业务层经常用 `'WAIT' / 'RUNNING' / 'OVER' / 'DONE' / 'SUCCESS' / 'FAIL'` 等,长度刚好 10,但不区分大小写、空格,纯字符串字段会让 typo 直接写进库。建议改用 SQLAlchemy `Enum` 类型。

### BUG-M10 [低] `InterfaceCaseContentResult.__allow_unmapped__ = True` 含义不明
**位置**:
- [interfaceResultModel.py:180](/Users/fanyuxuan/cyq_code/case_auto_hub/app/model/interfaceAPIModel/interfaceResultModel.py)
- [interfaceCaseContentsModel.py:37](/Users/fanyuxuan/cyq_code/case_auto_hub/app/model/interfaceAPIModel/contents/interfaceCaseContentsModel.py)

`__allow_unmapped__` 在 SQLAlchemy 2.0 是"允许未映射的 dataclass-style 基类"的开关。如果这里**不**用 dataclass,而是 declarative class,加这个标志会跳过类型注解到 Column 的自动转换。**目前没有看到任何 dataclass 装饰器**,这个标志反而是反作用——可能曾经是 dataclass,后来改回了 declarative,但没清理标志位。

### BUG-M11 [低] `InterfaceResult.interface_name` / `interface_desc` 是结果表字段,但**没有任何地方写入**
**位置**:
- 字段:[interfaceResultModel.py:32-34](/Users/fanyuxuan/cyq_code/case_auto_hub/app/model/interfaceAPIModel/interfaceResultModel.py)
- 写入处:[interface_executor.py:427-428](/Users/fanyuxuan/cyq_code/case_auto_hub/croe/interface/executor/interface_executor.py) `result['interface_name'] = ctx.interface.interface_name`

写入走的是 dict,后续 `InterfaceResult(**result)` 才转成 ORM,这一步是 OK 的。但 `interface_desc` 写入时是 250 长度,模型里也是 250,刚好对齐——这没问题。
问题在于 `interface_uid` 字段是 `String(20)`,而 `BaseModel.uid` 是 `String(50)`。所以 `interface_uid` 存的是截断后的 20 字符,**生成 uid 时如果超过 20 字符就截断**——而 uid 一般用于精确比对,截断后碰撞概率上升。

---

## 三、Mapper 层 BUG / 设计问题

### BUG-D1 [严重] `result_writer` 模块级单例 + 共享可变缓存,会污染并发
**位置**:
- [writer/__init__.py:11](/Users/fanyuxuan/cyq_code/case_auto_hub/croe/interface/writer/__init__.py) `result_writer = ResultWriter()`
- [result_writer.py:53-56](/Users/fanyuxuan/cyq_code/case_auto_hub/croe/interface/writer/result_writer.py) `self.api_result_cache: List[InterfaceResult] = []; self.content_result_cache: List[Dict[str, Any]] = []`

`ResultWriter` 是普通类,但在 `__init__.py` 里做了模块级单例。当 controller 同时(或 gunicorn worker 之间串行)发起的两个 case 执行时:
- 缓存互相覆盖,flush 时一次性把别人未完成的数据写库。
- 缓存和"属于谁"无法对上,极易出现 case A 的 step 结果挂在 case B 头上。
- `_progress_update_cache` 创建了但**从未被读或写**——死字段。

**修复建议**:`ResultWriter` 改为**每个 `InterfaceRunner` 实例持有一个**,由 DI 注入;或者按 `case_result_id` 做 key 分片。

### BUG-D2 [严重] `bulk_insert_results` 的异常处理吞掉了部分结果
**位置**:[interfaceResultMapper.py:516-582](/Users/fanyuxuan/cyq_code/case_auto_hub/app/mapper/interfaceApi/interfaceResultMapper.py)

```python
for content_type, type_items in grouped_items.items():
    result_model = cls.RESULT_TYPE_MAP.get(content_type)
    if not result_model:
        log.error(f"bulk_insert_results: 不支持的 content_type: {content_type}")
        continue                                   # ← 静默跳过!
    ...
```

- 任何未知 `content_type` 直接跳过,**不抛错**,调用方无法发现数据丢失。
- `bulk_insert_models` 在 `Mapper` 父类里也是 `add_all + flush`,不会自动回滚到逐条插入——而 `result_writer._fallback_insert_*` 又自己写了一遍(逐条降级)。这里存在"调用方不知道有降级方案"的歧义。

### BUG-D3 [中高] `_do_update` 重复 `refresh`
**位置**:
- [interfaceResultMapper.py:368-369](/Users/fanyuxuan/cyq_code/case_auto_hub/app/mapper/interfaceApi/interfaceResultMapper.py) `target = await cls.get_by_id(result_id, session); await session.refresh(target)`
- [interfaceCaseContentMapper.py:230-231](/Users/fanyuxuan/cyq_code/case_auto_hub/app/mapper/interfaceApi/interfaceCaseContentMapper.py) `await session.flush(); session.expunge(target)`

`get_by_id` 之后立刻 `refresh`——`get_by_id` 内部已经做了 `flush_expunge`/`refresh`,再 refresh 一遍纯属浪费 IO。

### BUG-D4 [中高] `Mapper.bulk_insert_models` 自动 `commit` 是不安全的
**位置**:[mapper/__init__.py:838-869](/Users/fanyuxuan/cyq_code/case_auto_hub/app/mapper/__init__.py)

```python
async with cls.transaction(session) as session:
    session.add_all(models)
    await session.flush()
    return len(models)
```

注释说"未传入 session:自动创建 session + 事务,add_all 后自动 commit"。问题:
- 如果调用方**忘了传 session**,每个 `bulk_insert_models` 内部自开自 commit,**多张表的批量操作不在同一事务**——`finalize_case_result` 里如果先 bulk api_result(自带 commit)再 finalize_task_result(再 commit),任何一步失败,前一步已经落地,无法回滚。
- 写库与"写日志"分离:批量 insert 成功 + 单条 update 失败,数据半写。

**修复建议**:bulk_insert 系列强制要求传入 session(从外部事务),杜绝隐式 commit。

### BUG-D5 [中高] `query_steps` 多 `joinedload` 笛卡尔积
**位置**:[interfaceCaseMapper.py:704-724](/Users/fanyuxuan/cyq_code/case_auto_hub/app/mapper/interfaceApi/interfaceCaseMapper.py)

```python
.options(
    joinedload(APIStepContent.interface_api),
    joinedload(ConditionStepContent.interface_condition),
    joinedload(LoopStepContent.interface_loop),
    joinedload(GroupStepContent.interface_group),
    joinedload(DBStepContent.db_execute),
)
.where(...)
.order_by(...)
```

JTI 模型中 8 个子类(API/GROUP/CONDITION/LOOP/DB/WAIT/SCRIPT/ASSERT),每个 `joinedload` 是对**当前 row 的子类表** LEFT JOIN。SQLAlchemy 会对一个 row 同时 LEFT JOIN 5 个相关子表,如果某个步骤(比如 API 步骤)其实只对应 1 个子类表,join 出来 5 张空表——**对每个步骤 row 多 LEFT JOIN 5 次**。

建议改 `selectinload` 或每个子类独立 `joinedload` 仅在该类存在时。

### BUG-D6 [中] `InterfaceResult` 在 `case_content_result` 之外不通过多态关系
**位置**:
- 模型:[interfaceResultModel.py:68-73](/Users/fanyuxuan/cyq_code/case_auto_hub/app/model/interfaceAPIModel/interfaceResultModel.py) `content_result_id = Column(INTEGER, ForeignKey("interface_case_content_result.id", ...))`
- 关联类 `APIStepContentResult` 也有自己的 `interface_result_id` FK 到 `interface_result.id`

存在**双向 FK**:`InterfaceResult.content_result_id` 指向 `interface_case_content_result.id`;`APIStepContentResult.interface_result_id` 指向 `interface_result.id`。两个字段存储**冗余的关联信息**,且都 `nullable=True`——任何一边忘记更新就会不一致。

**修复建议**:把 `InterfaceResult.content_result_id` 改为只读(在子类 result 写完后由 mapper 自动同步),或者干脆去掉这层 FK,只保留多态子类里的 FK。

### BUG-D7 [中] `InterfaceGroupMapper.copy_interface` 有死代码
**位置**:[interfaceGroupMapper.py:73-100](/Users/fanyuxuan/cyq_code/case_auto_hub/app/mapper/interfaceApi/interfaceGroupMapper.py) `last_index` 重新查询但若 group 不存在直接 raise——和前面的 `get_by_id` 判断重复。

### BUG-D8 [中] `InterfaceCaseContentMapper.copy_content` 注释错误
**位置**:
- [interfaceCaseContentMapper.py:148-149](/Users/fanyuxuan/cyq_code/case_auto_hub/app/mapper/interfaceApi/interfaceCaseContentMapper.py) `creatorName=user.username,  # User 模型只有 username,没有 creatorName`

注释自己说 "User 模型只有 username,没有 creatorName",但赋值的字段名是 `creatorName`,看起来在用 `username` 填 `creatorName` 字段——合理但表意混乱,应直接 `username=...`。

### BUG-D9 [中] `InterfaceCaseResultMapper` 大量占位方法
**位置**:
- [interfaceResultMapper.py:39-46](/Users/fanyuxuan/cyq_code/case_auto_hub/app/mapper/interfaceApi/interfaceResultMapper.py) `page_case_results` / `query_case_result` 都是 `pass`

`pass` 的占位方法是"以后会实现",但没有任何 `NotImplementedError` 或 TODO 标记,后续维护者无法分辨"忘写了"还是"故意占位"。

### BUG-D10 [中] `dynamicMapper` `append_dynamic` 时机不对
**位置**:
- `update_interface_case` / `update_interface` 都在 `update_by_id` 后 `old_info = old.to_dict()` 和 `new_info = new.to_dict()`——但 `update_by_id` 内部如果走了 `expunge`,这里的 `new.to_dict()` 还能拿到字段,但所有 `lazy='selectin'` 的关系会**不命中**(因为已分离)。

### BUG-D11 [低] `InterfaceGroupAPIAssociation` 没有 proper cascade
接口被删除时(`Interface.is_common=0`,私有接口),`group` 的关联表 `interface_group_api_association` 的 FK 行为没有 `ON DELETE CASCADE`,会留死引用。`Interface.interface_url` 修改也没看到关联触发更新逻辑。

---

## 四、执行器 / 策略层 BUG

### BUG-E1 [严重] `HttpxClient` 资源泄漏
**位置**:
- [httpxClient.py:30-38](/Users/fanyuxuan/cyq_code/case_auto_hub/common/httpxClient.py) `_client = None  # 延迟初始化`
- [httpxClient.py:60-66](/Users/fanyuxuan/cyq_code/case_auto_hub/common/httpxClient.py) `self.client.timeout = Timeout(None, connect=..., read=...)`
- [interface_executor.py:78](/Users/fanyuxuan/cyq_code/case_auto_hub/croe/interface/executor/interface_executor.py) `self.http = HttpxClient(logger=self.starter.send)`

- 整个项目**没有任何地方调用 `HttpxClient.close` 或 `aclose`**。每次 `InterfaceRunner` 跑完都泄漏一个 `AsyncClient`(内部有连接池)。
- `self.client.timeout = Timeout(...)` 每次请求**直接修改共享 client 的状态**。如果两个 `InterfaceExecutor` 实例同时调 `self.http(...)`,timeout 会互相覆盖。
- 没有 `__init__` 中创建 client(懒初始化是好设计),但缺 `__aenter__/__aexit__` 的实际使用,`InterfaceRunner` 不是 context manager。

**修复建议**:`InterfaceRunner` 改为 `async with InterfaceRunner(...) as runner:`,在 `__aexit__` 里 `await self.http.close()`;`self.client.timeout` 改为 `await self.client.request(..., timeout=Timeout(...))` 临时传参,不要修改 client 状态。

### BUG-E2 [严重] `HttpxClient` 默认 user-agent 写死
**位置**:[httpxClient.py:14](/Users/fanyuxuan/cyq_code/case_auto_hub/common/httpxClient.py) `DEFAULT_HEADERS = {"user-agent": "case_Hub_http/v0.1"}`

固定的 user-agent 在内网里往往没问题,但有些目标服务会基于 user-agent 做限流或返回不同响应。建议读取 `Interface.interface_headers` 允许覆盖。

### BUG-E3 [中高] `RequestBuilder._transform_request_data` 用 `TaskGroup` 在 Python 3.10 上崩溃
**位置**:[request_builder.py:402-407](/Users/fanyuxuan/cyq_code/case_auto_hub/croe/interface/builder/request_builder.py)

```python
async with asyncio.TaskGroup() as tg:
    tasks = {
        tg.create_task(self.variables.trans(value)): key
        ...
    }
```

`asyncio.TaskGroup` 是 **Python 3.11+** 才有的。如果 `.venv` 里 `python3.13` 没问题,但生产部署如果有 3.10 立刻 `AttributeError`。`VariableTrans.trans` 里同样的注释被注释掉了:`# async with asyncio.TaskGroup() as tg:`——说明作者意识到兼容性,但**只在 VariableTrans 注释了**,在 RequestBuilder 里依然用 TaskGroup。

### BUG-E4 [中高] `UrlBuilder` `env.url.rstrip('/')` 后用 `/` 再拼
**位置**:
- [url_builder.py:52-55](/Users/fanyuxuan/cyq_code/case_auto_hub/croe/interface/builder/url_builder.py)
- `_parse_url` 解析了 host/port,UrlBuilder 没用——同一个文件里 `interface_executor._parse_url` 和 `UrlBuilder.build` 逻辑不统一,容易跑出双斜杠。

### BUG-E5 [中高] `interface_executor._execute_before_sql` 用 `interface_before_sql.strip()` 而非复制变量
**位置**:
- [interface_executor.py:300](/Users/fanyuxuan/cyq_code/case_auto_hub/croe/interface/executor/interface_executor.py) `db_script = await self.variable_manager.trans(interface.interface_before_sql.strip())`

`interface.interface_before_sql` 是 ORM 字段,`strip()` 在原对象上调用?在 SQLAlchemy 2.0 里这是安全的(返回新 str),但代码读起来像是在修改字段。最好显式 `sql_text = interface.interface_before_sql or ""; cleaned = sql_text.strip()`。

### BUG-E6 [中] `InterfaceExecutor._build_result` 把 `success` 字段混在 `Boolean` 和 `dict`
**位置**:
- [interface_executor.py:478-481](/Users/fanyuxuan/cyq_code/case_auto_hub/croe/interface/executor/interface_executor.py) `result['result'] = ctx.success; result['start_time'] = ctx.start_time; return result, ctx.success`

`return result, ctx.success` 第二次返回 `ctx.success`,是 dict 里 `result['result']` 的镜像。两次来源相同,但 `ctx.error` 失败路径下 `ctx.success` 被覆盖为 False,字典里同时设了 `result=False` 和 `use_time='0'`——一切都是 0 字符串而非数字,做分析时容易踩坑。

### BUG-E7 [中] `InterfaceExecutor` 的 `extracts` / `asserts` 字段在 `_build_result` 里默认 `[]` 但子策略可能传 `None`
**位置**:
- [interface_executor.py:440-441](/Users/fanyuxuan/cyq_code/case_auto_hub/croe/interface/executor/interface_executor.py) `'extracts': ctx.extracted_vars or [], 'asserts': ctx.asserts or []`

`ctx.extracted_vars` 是 list(初始 `[]`),`ctx.asserts` 是 `Optional[List]`(初始 `None`)。`asserts` 这里用 `or []` 解决了,但调用方如果传 `asserts=[None]`,会保存 `[None]`,后续 JSON 序列化失败。

### BUG-E8 [中] `step_content_api.py` `total_num` 没用到
**位置**:
- [step_content_api.py:73-80](/Users/fanyuxuan/cyq_code/case_auto_hub/croe/interface/executor/step_content/step_content_api.py) `case_result = step_context.execution_context.case_result; if success: case_result.success_num += 1; else: case_result.fail_num += 1; case_result.result = InterfaceAPIResultEnum.ERROR`

`case_result.total_num`(在 `init_case_result` 里赋为 `interface_case.case_api_num`)在 API 步骤中**从未被更新**;如果 case 添加/删除步骤后 `case_api_num` 不准(见 BUG-M8),`total_num` 也会不准,而且**只有初始化时设置,不再随 steps 实际数变化**。

### BUG-E9 [中] `step_content_group` 与 `step_content_api` 行为不对称
**位置**:
- [step_content_api.py:73-80](/Users/fanyuxuan/cyq_code/case_auto_hub/croe/interface/executor/step_content/step_content_api.py) `case_result.success_num += 1; case_result.fail_num += 1`
- [step_content_group.py:105-111](/Users/fanyuxuan/cyq_code/case_auto_hub/croe/interface/executor/step_content/step_content_group.py) `case_result.success_num += 1; case_result.fail_num += 1`

`step_content_group` 在 `all_success` 时 `success_num += 1`,失败时 `fail_num += 1`。**`total_num` 都不加**。意味着一个 case 有 1 个 GROUP 步骤(内部跑了 5 个 API),`total_num=1`(只算 step 不算 API 实际数),`success_num=1`,5 个 API 结果写到了 `interface_result` 表里但 `total_num` 还是 1。

### BUG-E10 [中] `step_content_db` / `step_content_script` 的变量提取可能抛错未捕获
**位置**:
- [step_content_db.py] / [step_content_script.py] 调用方都是 `await ...` 但异常处理不完整

需要逐文件验证。

### BUG-E11 [低] `condition_manager` 没用 `assert_data` 的 `condition_result` 字段
**位置**:
- [condition_manager.py:63-80](/Users/fanyuxuan/cyq_code/case_auto_hub/croe/interface/manager/condition_manager.py) `assert_data = {...}` 然后设置 `assert_data["condition_result"]`

但 [result_writer] 里没把 `assert_data` 写进 `condition_step_result.assert_data`,需要核对写入逻辑(在 ConditionStepContentResult 模型里有 `assert_data = Column(JSON)`,但写入路径需要确认)。

### BUG-E12 [低] `extract_manager` 静默吞错
**位置**:
- [extract_manager.py:69-73](/Users/fanyuxuan/cyq_code/case_auto_hub/croe/interface/manager/extract_manager.py) `except KeyError as e: log.error(...); except Exception as e: log.error(...)`

提取失败时**仅 log**,`extract['value']` 没有被设置,继续往下走——但调用方 (`InterfaceExecutor._execute_extract`) 在没有 value 的情况下也把 `vars_list` 推给 `variable_manager.add_vars(vars_list)`,**`add_vars` 会把 `None` 存进变量表**,后续用这个变量时(`{{var}}`)得到字符串 `"None"`。

---

## 五、变量系统 BUG

### BUG-V1 [严重] `VariableTrans.__find_g_vars` 是 `staticmethod`,被 `self.__find_g_vars` 调用会失败
**位置**:
- [variableTrans.py:160](/Users/fanyuxuan/cyq_code/case_auto_hub/utils/variableTrans.py) `@staticmethod async def __find_g_vars(script: str)`
- [variableTrans.py:106](/Users/fanyuxuan/cyq_code/case_auto_hub/utils/variableTrans.py) `return await self.__find_g_vars(var_name[1:])`

Python 的双下划线方法会做 name mangling,在类外变成 `_VariableTrans__find_g_vars`,**类内** `self.__find_g_vars` 等同于 `self._VariableTrans__find_g_vars`,能正常调用——但 **继承/重写/直接调 `cls.__find_g_vars` 时会爆**。`__init_subclass__`/`__class__` 拿到的不是 mangled 名。

**修复建议**:改单下划线 `_find_g_vars`,避免 name mangling。

### BUG-V2 [中高] `VariableTrans` 的 `add_vars(list)` 隐式 `list2dict` 行为可能丢字段
**位置**:
- [variableTrans.py:60-69](/Users/fanyuxuan/cyq_code/case_auto_hub/utils/variableTrans.py) `elif isinstance(data, list): data = GenerateTools.list2dict(data); self._vars.update(**data)`

`GenerateTools.list2dict` 通常把 `[{'key': 'a', 'value': 1}, {'key': 'a', 'value': 2}]` 转成 `{a: 2}`(后者覆盖)。**如果某个步骤添加的变量 list 里有重复 key,前序步骤的提取变量会被覆盖**。这是隐性 BUG,排查极难。

### BUG-V3 [中高] `ScriptManager._variables` 跨脚本累积(全局状态)
**位置**:
- [script_manager.py:124-125](/Users/fanyuxuan/cyq_code/case_auto_hub/croe/a_manager/script_manager.py) `self._variables: Dict[str, Any] = {}`
- [script_manager.py:188-198](/Users/fanyuxuan/cyq_code/case_auto_hub/croe/a_manager/script_manager.py) `_collect_results` 中 `self._variables[name] = value`

`ScriptManager` 每次 `__init__` 都新建实例,但 `_collect_results` 仍然把变量存到 `self._variables`。如果同一个 ScriptManager 跑多个脚本,变量会累积——但项目里 [interface_executor.py:260](/Users/fanyuxuan/cyq_code/case_auto_hub/croe/interface/executor/interface_executor.py) 每次都 `ScriptManager()` 新建,所以**当前不会泄漏**。但语义不明,后来人加缓存或复用就立刻踩坑。

### BUG-V4 [中] `hub_api_request` 是同步 HTTP,在 async 上下文里阻塞事件循环
**位置**:
- [script_manager.py:218-220](/Users/fanyuxuan/cyq_code/case_auto_hub/croe/a_manager/script_manager.py) `with httpx.Client(timeout=10) as client: response = client.request(...)`

`exec` 同步执行 Python 脚本,内部 `httpx.Client().request()` 是同步阻塞,**阻塞整个 asyncio 事件循环 10 秒**。

**修复建议**:改用 `asyncio.run_coroutine_threadsafe` 桥接到异步;或者用 `httpx.AsyncClient` + `asyncio.get_event_loop().run_until_complete`(复杂但可解);最简单——**禁止 hub_request**,改成纯函数式的变量计算。

### BUG-V5 [中] `MAX_LENGTH = 5` 阈值写死
**位置**:
- [variableTrans.py:21](/Users/fanyuxuan/cyq_code/case_auto_hub/utils/variableTrans.py) `MAX_LENGTH = 5`

>5 个元素时切换为 `asyncio.gather` 并行,≤5 时串行。这个阈值是经验值,但在 CPU 密集 + 大量 IO 的混合场景下,5 不一定是最优点。建议做成可配置(`Config` 里读)。

### BUG-V6 [低] `_resolve_vars` 找不到变量时返回 `f"{var_name}"`(字符串)
**位置**:
- [variableTrans.py:110-114](/Users/fanyuxuan/cyq_code/case_auto_hub/utils/variableTrans.py) `return self._vars.get(var_name, f"{var_name}")`

当变量未定义时,会把变量名作为字面值返回(不抛错)。**断言时 `{{token}}` 找不到就会拿到字符串 `"token"`,断言通过(因为 key/value 都是 `"token"`)**——典型"静默错误"。

---

## 六、安全 BUG

### BUG-S1 [严重] `ScriptManager` 沙箱可绕过:`getattr` 没拦截
**位置**:
- [script_manager.py:55-73](/Users/fanyuxuan/cyq_code/case_auto_hub/croe/a_manager/script_manager.py) `SAFE_BUILTINS` 集合不含 `getattr`
- [script_manager.py:111-115](/Users/fanyuxuan/cyq_code/case_auto_hub/croe/a_manager/script_manager.py) `if isinstance(child, ast.Call): if isinstance(child.func, ast.Name): if child.func.id in DISALLOWED_ATTRS: raise ...`

`ast.Call` 的检查只对 `ast.Name` 形式(即 `eval(x)` 这种直接调函数名)生效;`getattr(obj, '__class__')` 走的是 `ast.Attribute`(`getattr.attr` = `'__class__'`)?**不,`getattr` 的函数名是 `getattr`(`ast.Name` 中),**`child.func.id == 'getattr'`,而 `'getattr'` 不在 `DISALLOWED_ATTRS` 里**——**放行**。

绕过的 payload:
```python
cls = getattr("".__class__.__mro__[1], "__subclasses__")()
# 等价于
getattr("".__class__.__mro__[1], '__subclasses__')()
```

**修复建议**:`SAFE_BUILTINS` 中**只放白名单**(当前其实已经是这样,但 `getattr` 应该显式不放,且 `ast.Call` 检查要扩展到 `ast.Attribute` 形式)。

### BUG-S2 [严重] `ALLOWED_NODE_TYPES` 包含 `Import`/`ImportFrom`,可引入任意 Python 模块
**位置**:
- [script_manager.py:42-43](/Users/fanyuxuan/cyq_code/case_auto_hub/croe/a_manager/script_manager.py) `ast.Import, ast.ImportFrom, ast.alias`

`import os; os.system("rm -rf /")` 通过 AST 检查(`Import` 是允许的),但 `os` 不在 `SAFE_BUILTINS` 里所以 `exec` 找不到 `os`?**会报错**,但用户仍可写:
```python
import builtins
getattr(builtins, '__import__')('os').system('rm -rf /')
```

**修复建议**:删除 `ast.Import` / `ast.ImportFrom`;只允许 `ast.Call` 调 `SAFE_BUILTINS` 中的键。

### BUG-S3 [严重] `SCRIPT_TIMEOUT` 定义了但**从未生效**
**位置**:
- [script_manager.py:26](/Users/fanyuxuan/cyq_code/case_auto_hub/croe/a_manager/script_manager.py) `SCRIPT_TIMEOUT = 5  # 脚本执行超时时间(秒)`

整个文件里 grep `SCRIPT_TIMEOUT` 只在这一行出现。`exec(...)` 是同步执行,**没有任何超时控制**。一个死循环脚本(比如 `while True: pass`)会永久阻塞 worker。

**修复建议**:
- 用 `multiprocessing.Process` + `Process.terminate`;或
- 用 `signal.alarm` 在子线程里执行;或
- 把脚本 AST 静态分析(`_validate_ast` 已经做了一半)——但要更严。

### BUG-S4 [中高] `hub_api_request` SSRF 风险
**位置**:
- [script_manager.py:215-225](/Users/fanyuxuan/cyq_code/case_auto_hub/croe/a_manager/script_manager.py) `with httpx.Client(timeout=10) as client: response = client.request(method=method, url=url, **kwargs)`

用户脚本可以传 `url='http://10.0.0.1/admin' / 'http://169.254.169.254/'` 做内网探测/云元数据获取。**没有 host 白名单、没有内网 IP 拦截**。

**修复建议**:`url` 必须配置在可信域白名单内,或者根本不允许 `hub_request`(推荐后者)。

### BUG-S5 [中高] `_filter_request_body` 处理 Raw 类型不变量替换
**位置**:
- [request_builder.py:200-254](/Users/fanyuxuan/cyq_code/case_auto_hub/croe/interface/builder/request_builder.py) `_process_request_body` → `_filter_request_body` → `_prepare_raw_body`

`interface.interface_body` 是 dict/list 形式,**没有经过变量替换**;变量替换只在 `_transform_request_data(request_data)` 统一做。但如果 `body_type == Raw` 且 raw_type 是 `text`,`{KEY_CONTENT: json.dumps(interface.interface_body)}`——dict 转 json 字符串后再做变量替换,**这意味着 dict 里的 `{{var}}` 会被转义成 `"{{var}}"` 的字面值,而 json.dumps 后再做变量替换,有可能产生错误的 escape**。

### BUG-S6 [中] `SCRIPT_TIMEOUT`/`MAX_SCRIPT_LENGTH` 写到代码里不可配置
`MAX_SCRIPT_LENGTH = 10000`、`SCRIPT_TIMEOUT = 5` 应当走 `Config` 读取,而不是写死。

### BUG-S7 [低] `safe_headers` 列表只信任 `g_headers`,但下游 `interface_headers` 也会被信任合并
**位置**:
- [request_builder.py:106-129](/Users/fanyuxuan/cyq_code/case_auto_hub/croe/interface/builder/request_builder.py) `_prepare_headers`

普通用户可以配 `Host: malicious` 之类的 header,后端直接转发。建议禁止覆盖敏感 header(`Host` / `Content-Length` / `Authorization` 部分场景)。

---

## 七、冗余代码(超出第一版)

### RED-D1 [中] `InterfaceContentStepResultMapper._do_update` 重复 get+refresh
见 BUG-D3。

### RED-D2 [中] `BaseModel.to_dict` 与 `BaseModel.map` 几乎相同,语义不清
**位置**:
- [basic.py:38-65](/Users/fanyuxuan/cyq_code/case_auto_hub/app/model/basic.py) `to_dict(exclude=None)` 和 `map` 区别仅在 exclude 参数

两个方法名都叫 "to dict" 系列,实现差异在 `to_dict` 多了 `exclude`,但 `map` 用了 datetime 格式化、`to_dict` 也用了。两个方法一个 `def` 一个 `@property` 一个 `def`,调用方很容易混。

### RED-D3 [中] `InterfaceCaseContentResult` 写了一半的 `to_dict` 没遵循统一结构
每个子类都重写 `to_dict`,模式高度重复:`super().to_dict() + 加几个字段`。可以抽 `to_dict_template` 装饰器,或者用 SQLAlchemy `__dict__` 直接产出。

### RED-D4 [中] `Mapper.RESULT_TYPE_MAP` / `Mapper.CONTENT_TYPE_MAP` 同一个映射写两份
**位置**:
- [interfaceResultMapper.py:143-152](/Users/fanyuxuan/cyq_code/case_auto_hub/app/mapper/interfaceApi/interfaceResultMapper.py)
- [interfaceCaseContentMapper.py:44-53](/Users/fanyuxuan/cyq_code/case_auto_hub/app/mapper/interfaceApi/interfaceCaseContentMapper.py)

两个 mapper 各维护一份 `CaseStepContentType → Model` 映射。**任何一边漏改,bug**。

### RED-D5 [中] `ResultWriter._progress_update_cache` 是个死字段
[result_writer.py:56](/Users/fanyuxuan/cyq_code/case_auto_hub/croe/interface/writer/result_writer.py)

### RED-D6 [低] `InterfaceGroupMapper.association_interface` 内部对 group 的 `+1` 是两步式更新
`group.interface_group_api_num += 1` 修改 ORM 对象然后等 flush——和别处用 `update(InterfaceCase).values(case_api_num=InterfaceCase.case_api_num + 1)` 的 SQL 增量更新风格不统一,容易出 race condition。

### RED-D7 [低] `runner.py:225` 的 `case_result.interfaceLog = "".join(self.starter.logs)` 是死代码
同 BUG-F1。直接删。

### RED-D8 [低] `InterfaceExecutor` 内部 `ExecutionContext` 与外层 `CaseStepContext`/`ExecutionContext` 同名不同义
[interface_executor.py:35](/Users/fanyuxuan/cyq_code/case_auto_hub/croe/interface/executor/interface_executor.py) 和 [context.py:27](/Users/fanyuxuan/cyq_code/case_auto_hub/croe/interface/executor/context.py) 都叫 `ExecutionContext`,但前者存接口/响应/变量等,后者存 case/env/case_result/task_result。跨模块读起来很混乱。

---

## 八、过度设计(超出第一版)

### OVER-D1 [中高] `__slots__` 与动态加字段的 conflict
[runner.py:35](/Users/fanyuxuan/cyq_code/case_auto_hub/croe/interface/runner.py) `__slots__ = ("starter", "variable_manager", "interface_executor", "global_headers")` —— 但 `global_headers` 已经不更新(见 BUG-F3),可移除 slots 或移除 global_headers 字段。

### OVER-D2 [中] 策略 + 工厂 + 执行器 + 子策略 + 组装服务,5 层包装
见第一版 OVER-1;此版补充:`InterfaceCaseContentResult` 8 个子类 × `step_content` 8 个策略 × `InterfaceCaseContents` 8 个子类——24 个文件,9 个工厂映射表,任意加一种 step type 要改 6 个地方(model 子类 + content 子类 + result 子类 + 策略类 + 策略工厂 + writer 的 RESULT_TYPE_MAP)。耦合度极高,违反"OCP 开闭原则"。

### OVER-D3 [中] `InterfaceResult.to_dict` (如果有) 走 `interface_result` relationship 时会再次 SELECT
基类 `InterfaceCaseContentResult` 有 `relationship(InterfaceResult, ...)`,每个 `to_dict` 都触发 lazy load。`APIStepContentResult.to_dict` 改成 `lazy="selectin"`,但 `GroupStepContentResult.interface_results` 也是 `viewonly`——这两个关系对组步骤有 N+1。

### OVER-D4 [中] `APIStepContentResult.interface_result` 是 `selectin` + `Lazy` 双策略
**位置**:
- [interfaceResultModel.py:280-284](/Users/fanyuxuan/cyq_code/case_auto_hub/app/model/interfaceAPIModel/interfaceResultModel.py)

`lazy="selectin"` 在 with_polymorphic='*' 下行为是"额外一条 IN 查询把所有子类的 interface_result 拉出来"——对只查 API 步骤的场景浪费 8 倍查询。

### OVER-D5 [中] `InterfaceCase` 字段 `case_api_num` 维护成本 > 价值
每次关联/删除步骤都要更新这个字段,而且更新逻辑分散在 mapper 多个方法里——见 BUG-M8。

### OVER-D6 [低] 大量 `@property` 在 model 中做计算
`interface.desc`、`InterfaceLoop.key/value/operate`、`InterfaceCaseContents.resolved_content_name` 等用 `@property` 包装,但实际**都是数据库字段**或简单取值,改成静态方法或裸属性更明确。

---

## 九、性能问题

### PERF-1 [中高] `with_polymorphic='*'` 触发笛卡尔积
见 BUG-M6。

### PERF-2 [中高] `add_flush_expunge` 内部 `refresh` 触发 N+1
[mapper/__init__.py:440-447](/Users/fanyuxuan/cyq_code/case_auto_hub/app/mapper/__init__.py) `flush_expunge` 默认 `refresh=True`,意味着每次插入都再 SELECT 一遍(拿到 server_default 的值)。对于批量插入非常浪费。

### PERF-3 [中高] `bulk_insert_results` 在 `case_result.cache` 写满时,每次 `_flush_cache` 都开新事务
**位置**:
- [result_writer.py:310-339](/Users/fanyuxuan/cyq_code/case_auto_hub/croe/interface/writer/result_writer.py) `_flush_cache` 里 `if self.api_result_cache: try: await self._bulk_insert_api_results()`

每次 _flush 都新建事务;且 cache 写满阈值 `MAX_CACHE_SIZE = 1000` 太大,case 大时早就溢出了。建议:
- 调小到 50;
- 复用 `InterfaceRunner` 实例的事务。

### PERF-4 [中] `result_writer.finalize_case_result` 内部重新计算 `use_time`
**位置**:
- [result_writer.py:291-293](/Users/fanyuxuan/cyq_code/case_auto_hub/croe/interface/writer/result_writer.py) `case_result.use_time = GenerateTools.calculate_time_difference(case_result.map['start_time'])`

`case_result.map['start_time']` 是格式化后的字符串,`calculate_time_difference` 又要 parse 一次。

### PERF-5 [中] `RequestBuilder._transform_request_data` 对所有字段做变量替换
**位置**:
- [request_builder.py:391-413](/Users/fanyuxuan/cyq_code/case_auto_hub/croe/interface/builder/request_builder.py)

连 `read`/`connect`/`follow_redirects` 这种非字符串字段也做 `trans`,会走进 `trans.register(dict)` 路径(对非 dict 直接返回 target),实际无害但浪费 await。

### PERF-6 [低] `set_process` / `update_task_progress` 在循环里多次写库
[task.py:265](/Users/fanyuxuan/cyq_code/case_auto_hub/croe/interface/task.py) `await self.set_process(task_result)` 每个 case 跑完调一次,无节流。N 个 case 触发 N 次 DB update。

---

## 十、可观测性问题

### OBS-1 [严重] 失败链路 trace 不可达
异常分支(except)只 `log.exception`,**不写 step_result、不通知用户**。`InterfaceExecutor.execute` 的 `except Exception as e: ctx.error = str(e)` 把错误吞了,上游只看到 `success=False`,但**没有 step 失败信息写到任何表里**(除非 step_content_xxx 自己处理)。最坏情况:整个 case 100% 失败但 step 表里全是 PENDING,前端无据可查。

### OBS-2 [严重] 缺 correlation id
`interface_case_id` / `case_result_id` / `task_result_id` 在多 case 并发时,光看日志无法拼出"这条日志是哪条 case 跑的"。**应当用 `contextvars` 注入 `trace_id`**,跨日志/DB/WS 一致。

### OBS-3 [中] `log.debug` 散落业务关键点
- [interface_executor.py:168, 178](/Users/fanyuxuan/cyq_code/case_auto_hub/croe/interface/executor/interface_executor.py) `log.info(f"origin_url = {origin_url}")` `log.info(f"resolved_url = {ctx.resolved_url}")`
- [interface_executor.py:210, 230](/Users/fanyuxuan/cyq_code/case_auto_hub/croe/interface/executor/interface_executor.py) `log.info(f"execute_before_handlers variables = {variables}")`

URL/变量属于敏感数据,**直接打到 log 里**(可能包含 token、密钥)。

### OBS-4 [中] `starter.send` 的 emoji 协议
第一版 OVER-5 已提。前端需要正则解析 `🫳🫳` / `✍️✍️` / `⏭️⏭️` 这些 emoji 来区分步骤类型——一旦换前缀或加新类型,前端要同步改。

### OBS-5 [中] `set_result_field` 等只有 setter 没 getter
- [interfaceResultMapper.py:65-71](/Users/fanyuxuan/cyq_code/case_auto_hub/app/mapper/interfaceApi/interfaceResultMapper.py) `InterfaceCaseResultMapper.set_result_field` 只 add_flush_expunge,**不返回任何状态或成功标识**,调用方无法判断是否成功(只能靠 raise)。

### OBS-6 [低] 日志里无 `case_result_id`,只有 `interface_case_id`
- [runner.py:128](/Users/fanyuxuan/cyq_code/case_auto_hub/croe/interface/runner.py) `log.info(f"查询到业务流用例  {interface_case}")` 拿到的是 case 对象,但不打印 `case_result_id`。

---

## 十一、可测试性问题

### TEST-1 [严重] 无单测
整个 `croe/interface/` 目录 0 个 `test_*.py`。整个 `app/mapper/` 也没有测试。意味着所有上面的 BUG 都无法在 CI 拦截。

### TEST-2 [中] 关键类构造时直接做 DB 查询/IO
- `HttpxClient.client` 是懒初始化属性——测试时第一次访问触发 IO。
- `InterfaceRunner.__init__` 同步,不依赖 DB;但 `run_interface_case` 第一个动作 `InterfaceCaseMapper.get_by_id` 立刻 IO。

无法做纯单元测试,只能集成测试,且集成测试要起数据库/Redis/WS——成本高。

### TEST-3 [中] `InterfaceCaseContentResult.to_dict` 行为依赖 `self.__class__`
JTI 多态 `to_dict` 在子类和基类上行为不一致,测试用例必须分两层,代码覆盖成本高。

### TEST-4 [中] `__allow_unmapped__ = True` 含义不明,行为不可预测
一旦 SQLAlchemy 版本升级,可能立刻失效。

### TEST-5 [低] 私有方法难以 mock
- `InterfaceRunner._get_running_env` / `_execute_before_handlers` 等是私有,但业务流程中关键。

---

## 十二、命名 / 一致性问题

| 位置 | 模型字段 | runner 写入字段 | 实际生效 |
| --- | --- | --- | --- |
| [interfaceResultModel.py:102](/Users/fanyuxuan/cyq_code/case_auto_hub/app/model/interfaceAPIModel/interfaceResultModel.py) | `interface_log` (snake) | `case_result.interfaceLog` (camel) | ✗ 失效 |
| [interfaceResultModel.py:95](/Users/fanyuxuan/cyq_code/case_auto_hub/app/model/interfaceAPIModel/interfaceResultModel.py) | `interface_case_name` (snake, 20) | `case_result.interface_case_name = interface_case.case_title` (snake, 40) | ⚠ 长度截断 |

其他:
- `result_writer.py:132` log 标签写 `task_result` 但变量是 `case_result` —— BUG-F7。
- `interface_result.creator` / `creatorName` 等基础字段被频繁重写,容易和 `starter_name` 混淆(谁创建 vs 谁执行)。
- `Result.status` 是 `String(20)` (PENDING/RUNNING/OVER),而 `InterfaceTaskResult.status` 是 `String(10)`(默认 RUNNING)——长度不统一。
- `InterfaceCase.case_status` 是 `String(10)`(没默认值),新插入时如果业务没设,会变 NULL,但下游查询 `case_status = 'WAIT'` 等可能因 NULL 不命中。

---

## 十三、优先级总结

| 等级 | 项 | 简述 |
| --- | --- | --- |
| **P0 立即修** | BUG-F1 | `interfaceLog` 字段名错位,日志从未落库 |
| **P0 立即修** | BUG-F2 | 早返 None 与 Tuple 签名不一致,触发 unpack 崩溃 |
| **P0 立即修** | BUG-M1 | `target_id` 是 ClassVar,to_dict 永远为 None |
| **P0 立即修** | BUG-M2 | `case_title` 40 vs `interface_case_name` 20,长标题截断 |
| **P0 立即修** | BUG-M3 | `BaseModel.map/to_dict` 不识别 JTI 子类字段 |
| **P0 立即修** | BUG-D1 | `result_writer` 单例 + 共享缓存,会污染并发 |
| **P0 立即修** | BUG-E1 | `HttpxClient` 资源泄漏 + timeout 状态被覆盖 |
| **P0 立即修** | BUG-S1 | ScriptManager `getattr` 沙箱可逃逸 |
| **P0 立即修** | BUG-S2 | ScriptManager 允许 `import` |
| **P0 立即修** | BUG-S3 | `SCRIPT_TIMEOUT` 定义了但从未生效 |
| **P0 立即修** | BUG-V1 | `VariableTrans.__find_g_vars` name mangling |
| **P1 近期修** | BUG-F3 | `init_global_headers` 静默错位,header 不生效 |
| **P1 近期修** | BUG-F4 | `init_interface_case_vars` 静默吞错 |
| **P1 近期修** | BUG-F5 | `error_stop` 状态机不统一 |
| **P1 近期修** | BUG-M4 | `InterfaceCaseContentResult.to_dict` mapper 遍历逻辑不清 |
| **P1 近期修** | BUG-M5 | `polymorphic_on` 用 enum 整数值,重排枚举炸库 |
| **P1 近期修** | BUG-M6 | `with_polymorphic='*'` 笛卡尔积 |
| **P1 近期修** | BUG-M7 | `result` 字段塞 enum 但列是 Boolean |
| **P1 近期修** | BUG-M8 | `case_api_num` 与实际步骤数不一致 |
| **P1 近期修** | BUG-D2 | `bulk_insert_results` 静默跳过未知 content_type |
| **P1 近期修** | BUG-D3 | `_do_update` 重复 get+refresh |
| **P1 近期修** | BUG-D4 | `bulk_insert_models` 隐式 commit 不安全 |
| **P1 近期修** | BUG-D5 | `query_steps` 多 joinedload 笛卡尔积 |
| **P1 近期修** | BUG-D6 | `InterfaceResult.content_result_id` 与多态子类 FK 双向冗余 |
| **P1 近期修** | BUG-E3 | `RequestBuilder` 用 Python 3.11+ `TaskGroup` |
| **P1 近期修** | BUG-E4 | `UrlBuilder` 与 `_parse_url` 逻辑不统一 |
| **P1 近期修** | BUG-E8 | `case_result.total_num` 从不更新 |
| **P1 近期修** | BUG-E9 | group / api 步骤的 `total_num` 行为不对称 |
| **P1 近期修** | BUG-E12 | `extract_manager` 失败时 `None` 进变量表 |
| **P1 近期修** | BUG-V2 | `add_vars(list)` 重复 key 静默覆盖 |
| **P1 近期修** | BUG-V4 | `hub_api_request` 同步阻塞事件循环 |
| **P1 近期修** | BUG-V6 | 变量未定义返回变量名字符串,断言静默成功 |
| **P1 近期修** | BUG-S4 | `hub_api_request` SSRF 风险 |
| **P1 近期修** | OBS-1 | 失败链路 trace 不可达 |
| **P1 近期修** | OBS-2 | 缺 correlation id |
| **P1 近期修** | OBS-3 | URL/变量写进 log,泄漏敏感数据 |
| **P1 近期修** | PERF-1 | `with_polymorphic='*'` 笛卡尔积 |
| **P1 近期修** | PERF-2 | `add_flush_expunge` 内部 refresh 触发 N+1 |
| **P1 近期修** | TEST-1 | 全模块 0 个单测 |
| **P2 持续优化** | BUG-F6 | `progress` int 截断 vs 强制 100 语义不一致 |
| **P2 持续优化** | BUG-F7 | `init_case_result` log 错误且冗余 |
| **P2 持续优化** | BUG-M9 | `case_status` 字符串无枚举约束 |
| **P2 持续优化** | BUG-M10 | `__allow_unmapped__ = True` 含义不明 |
| **P2 持续优化** | BUG-M11 | `interface_uid` 长度 20 可能截断 |
| **P2 持续优化** | BUG-D7 | `copy_interface` 死代码 |
| **P2 持续优化** | BUG-D8 | `copy_content` 注释错误 |
| **P2 持续优化** | BUG-D9 | 大量 `pass` 占位方法 |
| **P2 持续优化** | BUG-D10 | `dynamic` 时机不对 |
| **P2 持续优化** | BUG-D11 | `InterfaceGroupAPIAssociation` 缺 cascade |
| **P2 持续优化** | BUG-E2 | `HttpxClient` user-agent 写死 |
| **P2 持续优化** | BUG-E5 | `.strip()` 在 ORM 字段上调用 |
| **P2 持续优化** | BUG-E6 | `success` 字段类型混乱 |
| **P2 持续优化** | BUG-E7 | `asserts/extracts` 默认值混乱 |
| **P2 持续优化** | BUG-E10 | db/script 步骤异常处理 |
| **P2 持续优化** | BUG-E11 | `condition_manager` `assert_data` 写库路径待确认 |
| **P2 持续优化** | BUG-V3 | `ScriptManager._variables` 跨脚本累积 |
| **P2 持续优化** | BUG-V5 | `MAX_LENGTH = 5` 阈值写死 |
| **P2 持续优化** | BUG-S5 | Raw body 变量替换时序问题 |
| **P2 持续优化** | BUG-S6 | `SCRIPT_TIMEOUT`/`MAX_SCRIPT_LENGTH` 写死 |
| **P2 持续优化** | BUG-S7 | 敏感 header 未拦截 |
| **P2 持续优化** | RED-D1 ~ RED-D8 | 冗余代码 |
| **P2 持续优化** | OVER-D1 ~ OVER-D6 | 过度设计 |
| **P2 持续优化** | PERF-3 ~ PERF-6 | 性能调优 |
| **P2 持续优化** | OBS-4 ~ OBS-6 | 可观测性细节 |
| **P2 持续优化** | TEST-2 ~ TEST-5 | 可测试性 |

---

## 十四、修复建议路径(由近及远)

### 第一周(P0 必修)
1. `InterfaceCaseContents` 删除 `ClassVar target_id` → 用 `declared_attr` 或子类自管。
2. `runner.py:225` 改为 `case_result.interface_log = "".join(...)`,并清理 `__init__.py` 早期 return 形态。
3. `result_writer` 改为 `InterfaceRunner` 持有的实例,删除模块单例。
4. `HttpxClient` 加 `aclose`,请求时 timeout 走参数,不在 client 上修改。
5. `ScriptManager`:
   - 删 `ast.Import` / `ast.ImportFrom` 节点
   - `SAFE_BUILTINS` 显式不放 `getattr`/`setattr`/`__import__`
   - `ast.Call` 检查扩展到 `ast.Attribute` 形式(`getattr.__call__`)
   - 真正实施 `SCRIPT_TIMEOUT`(用 `multiprocessing` 跑 + `terminate` 兜底)
6. `BaseModel.map` / `to_dict` 改用 `inspect(self).mapper.columns` 包含 JTI 子类。
7. `InterfaceCase.interface_case_name` 长度调到 64(和 `case_title` 对齐),或反过来。
8. `VariableTrans.__find_g_vars` 改单下划线。

### 第一个月(P1 集中修)
- JTI 多态的 `with_polymorphic` 改成按需 `with_polymorphic=[]`。
- `polymorphic_on` 改用字符串。
- `InterfaceResult.content_result_id` 单向化,删除多态子类的反向 FK。
- `ScriptManager.hub_request` 改为异步或删除。
- 关键模型加 `Enum` 约束(`status`、`case_status`)。
- 添加 trace_id 机制。
- 抽出 `BaseModel.to_dict` 模板,删除 8 个子类的重复 `to_dict`。
- 写第一波单测:Runner 主流程、ScriptManager 安全规则、VariableTrans 转义。

### 第二个月(P2 持续优化)
- 全面梳理 `__allow_unmapped__` 含义,确认无用后删除。
- 整合 `Mapper.RESULT_TYPE_MAP` / `CONTENT_TYPE_MAP` 为单一来源。
- 添加 property 装饰器统一模型层。
- 完整覆盖 80% 行覆盖率的单测 + 集成测试。

---

## 十五、与第一版报告的关系

本报告是 V1([run_interface_case_review.md](/Users/fanyuxuan/cyq_code/case_auto_hub/docs/review/run_interface_case_review.md))的超集:
- 第一版所有 BUG/RED/OVER 仍成立,本报告未删除,只是编号加了前缀(分别加 `BUG-1 → BUG-F1`、`RED-1 → RED-D1`、`OVER-1 → OVER-D1`)。
- 新增:模型层、Mapper 层、执行器、变量系统、安全、性能、可观测性、可测试性、命名一致性。
- 第一版 P0 仍是 P0;第一版 P1 仍是 P1,本报告新增了更多 P0/P1。
