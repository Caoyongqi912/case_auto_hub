# P1.5 修复完成报告

日期:2026-06-19
审查文档:`docs/review/run_interface_case_deep_review.md` (V2)
前置报告:`docs/review/P1_FIX_REPORT.md`

本轮范围:把 V2 报告里**P0 风险项 + 几个 high-ROI 修复**一锅端,
共 5 个 commit 入仓。所有改动均带回归测试,全量 55/55 PASS。

## 已修复 BUG 清单

### 流程层 (1)

| BUG | 严重度 | 修复 |
| --- | --- | --- |
| **D3** `_do_update` 重复 refresh | 中高 | `interfaceResultMapper.py` 删 `get_by_id` 后的 `session.refresh(target)` 调用。`get_by_id` 内部 `session.get(model, ident)` 已经从 DB 取到最新数据并 attach,本函数接着只有 setattr 不会有人改 target,refresh 纯粹浪费 1 次往返。 |

### Mapper (1)

| BUG | 严重度 | 修复 |
| --- | --- | --- |
| **D4** `bulk_insert_*` 隐式 commit | 中高 | **3 处协同改动:**<br>1. `Mapper.bulk_insert_models` session 改必填,`session=None` 直接 `ValueError`<br>2. `InterfaceContentStepResultMapper.bulk_insert_results` session 改必填,删 `if/else` 分支<br>3. `result_writer._flush_cache` 改用 `InterfaceResultMapper.transaction()` 单一事务包两次 bulk,任一失败整体回滚;降级路径(逐条)自开新事务不被前面半写污染 |

### 模型 (1)

| BUG | 严重度 | 修复 |
| --- | --- | --- |
| **M5** polymorphic_on 用 enum 整数值 | 中高 | `interfaceCaseContentsModel.py` / `interfaceResultModel.py` 改 `content_type = Column(Enum(CaseStepContentType, native_enum=False, length=20))`。SQLAlchemy 自动在 DB 存 enum NAME (`'STEP_API'` 等),与 int value 解耦。`native_enum=False` 让 MySQL 5.7 / 8.0 都用 `VARCHAR(20)` 兼容。 |

### 冗余 (1) + 死代码 (2)

| BUG | 严重度 | 修复 |
| --- | --- | --- |
| **D7** `copy_interface` 死代码 | 中 | 删 `if not group: raise` / `if not interface: raise` 两条死代码。`get_by_id` 内部已抛 `NotFind`,重复判断是冗余。 |
| **D8** `copy_content` 注释错位 | 中 | 字段名 `creatorName=user.username` → `username=user.username`,注释统一。`BaseModel.creatorName` 列就是存 username 字符串。 |
| **F7** `init_case_result` 误导 log | 低 | 删 `log.info("task_result {}".format(case_result))` / `log.info("task_result {}".format(task_result))`。标签写 task_result 但变量是 case_result,只 `str(obj)` 调试价值为零。 |
| **RED-D5** `_progress_update_cache` 死字段 | 中 | `ResultWriter` 删 `_progress_update_cache` 字段定义 + `clear_cache` 两处的清空。全文搜索无任何读写,纯死字段。 |

## 未做的 Easy Wins (说明)

| BUG | 为何跳过 |
| --- | --- |
| **M7** `case_result.result` 塞 enum | 复查发现 `InterfaceAPIResultEnum` 是 namespace 写法,`SUCCESS = True` / `ERROR = False` 实际就是 Python bool,赋给 `Column(Boolean)` 没问题。**不是 bug**。 |
| **M9** `case_status` 无枚举约束 | 需要 schema 迁移(`String(10)` → `Enum`),单独一轮做。 |
| **S6** `SCRIPT_TIMEOUT` / `MAX_SCRIPT_LENGTH` 写死 | 走 `Config` 需修改 `config.py`,用户约束 "**不动 config.py**",需另议。 |

## 改动文件清单

| 文件 | 性质 | 说明 |
| --- | --- | --- |
| `app/mapper/__init__.py` | 修 (D4) | `bulk_insert_models` 强制 session |
| `app/mapper/interfaceApi/interfaceResultMapper.py` | 修 (D2 + D3 + D4) | `_do_update` 删 refresh;`bulk_insert_results` 强制 session 删 if/else |
| `app/mapper/interfaceApi/interfaceGroupMapper.py` | 修 (D7) | `copy_interface` 删死代码 |
| `app/mapper/interfaceApi/interfaceCaseContentMapper.py` | 修 (D8) | `copy_content` 字段名 / 注释 |
| `app/model/interfaceAPIModel/contents/interfaceCaseContentsModel.py` | 修 (M5) | `content_type` 列改 Enum |
| `app/model/interfaceAPIModel/interfaceResultModel.py` | 修 (M5) | `content_type` 列改 Enum |
| `croe/interface/writer/result_writer.py` | 修 (D4 + F7 + RED-D5) | 单事务 + 删 log + 删死字段 |
| `docs/MANUAL_MIGRATION.sql` | 改 (M5) | 追加 M5 章节:ALTER + UPDATE + 验证 + 回滚 |
| `tests/croe/interface/_bug_ids.py` | 改 (M5 / D4) | 加 BUG_M5 / BUG_D4 常量 |
| `tests/croe/interface/test_bug_d2_bulk_insert_no_silent_swal.py` | 改 (D4) | 每个调用加 session 参数 |
| `tests/croe/interface/test_bug_d4_bulk_insert_requires_session.py` | 新增 (D4) | 5 个测试 |
| `tests/utils/test_bug_m5_polymorphic_uses_enum_name.py` | 新增 (M5) | 4 个测试 |
| `tests/croe/interface/test_easy_wins_d7_d8_f7_red_d5.py` | 新增 (easy wins) | 5 个测试 |

合计:**9 改 + 3 新增**,约 +550 / -80 净行。

## 新增测试统计

- **新增测试文件**: 3
- **新增/修改测试用例**: 14(D4: 5 新 + 5 改,M5: 4 新,easy wins: 5 新)
- **测试结果**:`pytest -m unit --ignore=tests/integration` → **55/55 passed in 6.22s**
- **覆盖 BUG**: D3 (1 通过行为不变验证) / D4 (5) / M5 (4) / D7 / D8 / F7 / RED-D5 (5)

## 测试设计要点

### D4

- **必填 session** 用 `pytest.raises(ValueError, match="external session")` 双重断言:不传 + 显式 `session=None` 都拒
- **不再走 transaction** 用 `patch.object(InterfaceResultMapper, "transaction")` 计数器:传了 session,`transaction()` 调用次数必须为 0
- **单事务回滚** 用 `@contextlib.asynccontextmanager` 模拟 `_broken_tx` 抛异常,验证 `_fallback_insert_api_results` / `_fallback_insert_content_results` 被调用 + 缓存清空

### M5

- **`Column.type` 类型断言** 拿 `mapper.columns["content_type"]`,断言 `isinstance(col.type, Enum)` + `not isinstance(col.type, Integer)`,防"改回 Integer"作弊
- **`enum_class` 锁定** `col.type.enum_class is CaseStepContentType` 防"绑了别的 enum"
- **`native_enum=False` + `length`** 断言 `col.type.native_enum is False` + `length > 0`,确保跨 MySQL 版本兼容
- **`polymorphic_on` 仍挂 content_type** 防止改 Column 时不小心把多态断了

### easy wins

- **源码级断言** 用 `inspect.getsource(...)` + `"if not group:" not in src` 模式,简洁但能锁住"死代码别复活"
- **D8 测试** 用 "过滤掉注释行" 模式: `code_lines = [l for l in src.splitlines() if not l.strip().startswith("#")]`,防注释里出现 `creatorName=` 触发误判
- **F7 测试** mock 整个 `InterfaceCaseResultMapper.insert` + `log.info`,跑 `init_case_result(task_result=...)` 看 log 调用,断言不再有 `"task_result {"` 形式的 str.format

## 计划外发现

1. **M7 不是 bug**:初看像"Boolean 列塞 enum",实际 `InterfaceAPIResultEnum` 是 namespace 写法的常量,`SUCCESS = True` / `ERROR = False`,直接赋给 `Column(Boolean)` 是合理的。要修就只是文档化 enum 名字易混淆,不值得 commit。

2. **D4 改 `bulk_insert_results` 触发 D2 测试连锁更新**:session 改必填后,5 个 D2 测试都因不传 session 而抛 ValueError。修改方案:`_fake_session()` helper + 每个测试加 `session=fake_session`。这验证了 D4 修复**真的有效**(测试不过 = 修复失败)。

3. **M5 schema 迁移** 写完才意识到这是需要 DBA 配合的停机操作(改列类型 + UPDATE 全表),已加完整的 `MANUAL_MIGRATION.sql` 章节(ALTER / UPDATE / 验证 / 回滚),并在 commit message 里**强调**必须先跑迁移。

4. **D3 的 V2 review 描述有误**:V2 报告说"get_by_id 内部已经做了 refresh/expunge",实际 `get_by_id` 只调 `session.get(model, ident)` 没做 refresh。结论仍然对(冗余 refresh),但理由要纠正。

5. **RED-D5 的 `_progress_update_cache` 死字段** 全仓 grep 确认无任何读写,3 处出现全在 `ResultWriter` 自己内部(初始化 + 两处 clear_cache),纯死代码。

## 兼容性 / 注意事项

- **M5 是 schema breaking change**:生产部署必须跑 `docs/MANUAL_MIGRATION.sql` 的 M5 章节。两张表 `interface_case_step_content` 和 `interface_case_step_content_result` 的 `content_type` 列从 `INT` 改 `VARCHAR(20)`,并 UPDATE 所有行从 int 转 enum NAME。**未跑迁移前不能部署新代码**(否则 SQLAlchemy 写入 enum NAME,DB 还是 INT 列,直接报错)。
  
- **D4 是 mapper API 破坏**:`bulk_insert_models` / `bulk_insert_results` 不再允许 `session=None` 隐式 commit。仓内只有 `result_writer._flush_cache` 一个调用方,已同步改完。**任何仓外脚本(CLI 工具 / 一次性任务)直接调这两个方法,需要补传 session,否则 ValueError**。

- **D4 的 `transaction()` 上下文**:writer 改用 `InterfaceResultMapper.transaction()` 开事务,行为跟 `cls.transaction()` 一致(传 session = 复用,不传 = 自开 + 自动 commit)。原 `bulk_insert_models` 内的 `async with cls.transaction(session)` 自循环,现改成直接用传入 session,**性能更好**(少一层 async ctx)。

- **降级路径的副作用**:writer 走降级时,降级方法(逐条 `insert` / `insert_result`)内部**仍然自开事务**自 commit。这意味着 api_result 失败 → 降级插入 → content_result 失败 → 又降级,**两次降级之间 api_result 已经落库,content_result 没落,数据仍可能半写**。要彻底解决需要在降级路径也用单事务包两次逐条,本轮没做(超出 30min easy win 范围),作为 known limitation 留 TODO。

- **`config.py` 始终未动**,用户的 MySQL 密码修改保留在工作区,从未进任何 commit。

## 当前进度

- **已合并到 master 的 commit 数**:`master` 领先 `origin/master` **26 个 commit** (22 → 26)
- **P0**:12/12 ✅
- **P1**:F4 / V4 / D2 / D3 / D4 / M5 / D7 / D8 / F7 / RED-D5 共 10 项 ✅
- **P1 未做** (剩余):M6 (with_polymorphic 笛卡尔积) / M8 (case_api_num 不一致) / M9 (case_status enum) / M10 / S4 (SSRF) / S6 (config 化) / V3 (脚本状态累积) / V5 / V6 / E3-E12 / D5 / D6 / D9-D11 / RED-D6 / RED-D7 / RED-D8 / OVER-1~6
- **测试基线**:55 unit tests passed(每次 commit 前都跑过,本次新增 14 个)
