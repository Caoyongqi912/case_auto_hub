# P1 修复完成报告

日期:2026-06-19
审查文档:`docs/review/run_interface_case_deep_review.md` (V2)
前置报告:`docs/review/P0_FIX_REPORT.md` (P0 已完成 12/12)

本轮范围:在 P0 基础上,把"V2 审查里 ROI 最高的一批 P1"做掉,
包含 **V4 / D2** 两个 BUG 修复(用户后续追加了 **F4**,与 P1 一并入仓)。

## 已修复 BUG 清单

### 流程层 (1) — F4 由 P0 计划追加

| BUG | 严重度 | 修复 |
| --- | --- | --- |
| **F4** init_interface_case_vars 静默吞错 | 中高 | `runner.py` `init_interface_case_vars` mapper 抛错时 `log.error → log.exception`(留 traceback)+ 调 `self.starter.send` 把错误推给用户;**仍不抛**——后续步骤继续跑,只是用户能看到。 |

### 变量 / 执行器 (1)

| BUG | 严重度 | 修复 |
| --- | --- | --- |
| **V4** _hub_api_request 同步阻塞 | 中 | `script_manager.py` 把 `httpx.Client(timeout=10)` 换成 `httpx.AsyncClient(timeout=10)` + `asyncio.run(_do_request())`。函数对外仍是同步签名(子进程入口 `_exec_in_subprocess` 里 `exec()` 调用,无现成 loop,`asyncio.run` 干净);`log.error → log.exception` 跟 F4 一致。 |

### Mapper (1)

| BUG | 严重度 | 修复 |
| --- | --- | --- |
| **D2** bulk_insert_results 静默吞数据 | 严重 | `interfaceResultMapper.py` `bulk_insert_results` 三大改动:<br>1. 缺 `content_type` → 直接 `ValueError`(编程错误,跟 `insert_result` 策略对齐)<br>2. 未知 `content_type` → 走 `skipped_items` 列表,末尾 WARNING 输出 `content_name / content_id / content_type`<br>3. 返回值 `int → Tuple[int, int] = (inserted, skipped)`,调用方 `result_writer._bulk_insert_content_results` 同步改成解构元组,skipped 时 WARN、正常时 INFO;DB 异常透传前先把已知 skip 数落盘 |

## 改动文件清单

| 文件 | 性质 | 行数变化 |
| --- | --- | --- |
| `croe/interface/runner.py` | 修 (F4) | 既有 |
| `croe/a_manager/script_manager.py` | 修 (V4) | +20 / -7 |
| `app/mapper/interfaceApi/interfaceResultMapper.py` | 修 (D2) | +65 / -10 |
| `croe/interface/writer/result_writer.py` | 修 (D2 调用方) | +10 / -4 |
| `tests/croe/interface/_bug_ids.py` | 加常量 (V4 / D2) | +4 / 0 |
| `tests/croe/a_manager/test_bug_v4_hub_request_async.py` | 新增 (V4) | +75 / 0 |
| `tests/croe/interface/test_bug_d2_bulk_insert_no_silent_swal.py` | 新增 (D2) | +145 / 0 |

合计:**6 改 + 2 新增**,约 +320 / -21 净行。

## 新增测试统计

- **新增测试文件**: 2(`test_bug_v4_hub_request_async.py`、`test_bug_d2_bulk_insert_no_silent_swal.py`)
- **新增测试用例**: 9(V4: 4,D2: 5)
- **测试结果**:`pytest -m unit --ignore=tests/integration` → **41/41 passed in 6.19s**
- **覆盖 BUG**: V4 (async 路径 / JSON / text / 失败 None) + D2 (空 / 缺 type 抛错 / 未知 type 计入 skip / 合法+未知混用 / 全合法无警告)

## 测试设计要点

### V4

- 用 `inspect.getsource(ScriptManager._hub_api_request)` 抓源码,断言**不再含 `httpx.Client`、必须含 `httpx.AsyncClient`** —— 防止有人"为了通过测试"把代码改回同步
- `patch("httpx.AsyncClient.request", new=fake_request)` 注入 `async def fake_request(self, method, url, **kwargs)`,验证异步路径
- 三种响应(JSON / 纯文本 / 抛错)各一个测试

### D2

- `_patch_transaction(fake_session)` helper:用 `contextlib.asynccontextmanager` 把 `cls.transaction()` 替换成 yield fake_session 的 async ctx,绕过真 DB
- 五个测试覆盖:**空 / 缺 type 抛错 / 未知 type 计入 skip+WARNING / 合法+未知混用不被污染 / 全合法无 WARNING**
- "未知 type 计入 skip" 这条**精确断言 `add_all` 收到的是合法 items,被跳过的不会被错加**(D2 bug 的核心)
- WARNING 捕获用 `patch("utils.log.warning")` 而不是 `caplog` —— 项目用 loguru,`caplog` 不接 (与 F4 测试同款)

## 计划外发现

1. **D2 实际位置在 `interfaceResultMapper.py`,不是 `result_writer.py`** — V2 报告定位准确,handoff 摘要里写错文件路径,排查时已纠正。

2. **D2 返回值签名变更(`int → Tuple[int, int]`)** 是**有意的 API 破坏**,但 blast radius 极小:全仓只有 `result_writer._bulk_insert_content_results` 一个调用点,同步改完。

3. **V4 的 `asyncio.run` 在主进程 async 上下文里会爆**(`asyncio.run() cannot be called from a running event loop`),但当前调用路径是 `execute()` → `multiprocessing.spawn` 子进程 → `_exec_in_subprocess()` 顶层 `exec()`,子进程无现成 loop,所以安全。**已加 docstring 警告**:未来若有人在 async 上下文直接调,需要再换成 `await self._do_request()`。

4. **`_bug_ids.py` 之前漏了 `BUG_V4` / `BUG_D2` 常量** — handoff 摘要说"已加",实际是 V4 缺的;本轮顺手补上(挂在文件末尾 `# V4 审查 + D2 追加` 段)。

## 兼容性 / 注意事项

- **D2 是 API 破坏**:任何外部脚本直接调 `bulk_insert_results` 并把结果当 `int` 用的,会收到 tuple 后解包失败。本次只发现仓内一个调用点(`result_writer`),已同步修复。**如果未来有其它脚本直接调,需要适配**。

- **V4 在 async 上下文**:`asyncio.run()` 在已有 event loop 里运行会抛 `RuntimeError`。本轮 `_hub_api_request` 文档已写明该限制;若以后真在 async 路径里调,需要把 `asyncio.run(_do_request())` 改成"如果已有 loop,直接 `await _do_request()`,否则 `asyncio.run`"。

- **`asyncio.run` 每次新建 event loop**:对子进程里偶尔一次的调用 OK(子进程本来也只跑一次 `exec()`),对热路径不友好。当前不是热路径,无需优化。

- **D2 WARNING 的样本数**:跳过的 item 多于 5 条时,日志里只展示前 5 条 + `(还有 N 条)` 提示,避免大失败时 WARNING 把日志刷爆。完整数据通过 `(inserted, skipped)` 元组返回,需要全量时可以拉监控。

- **`config.py` 始终未动**,用户的 MySQL 密码修改保留在工作区,从未进任何 commit。

## 当前进度

- **已合并到 master 的 commit 数**:`master` 领先 `origin/master` 21 个 commit
- **P0**:12/12 ✅
- **P1 (本轮)**:V4 ✅、D2 ✅、F4 ✅
- **未做项**:见 `docs/review/run_interface_case_deep_review.md` 剩余章节(D3 / D4 / D5 / M4 / M5 / M6 / M7 / M8 / S4 / V3 / V5 / V6 / RED-* / OVER-*)
- **测试基线**:41 unit tests passed(每次提交前都跑过,本次新增 9 个)
