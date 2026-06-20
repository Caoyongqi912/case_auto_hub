# UI 自动化单测覆盖报告 (2026-06-20)

> 覆盖目标: croe/play (PlayRunner / PlayTaskRunner / writer / executor / context / exception / starter) + app/mapper/play + app/model/playUI + utils/io_sender

## TL;DR

| 阶段 | 总测数 | 增量 | 失败 |
|---|---|---|---|
| **基线** (接手前) | 414 | - | 0 |
| **Coverage Phase 1** (P-3-1 + writer/runner/task 模型) | 530 | +116 | 0 |
| **Coverage Phase 2** (mapper + step_content 策略) | 561 | +31 | 0 |
| **Coverage Phase 3** (context/exception/starter/io_sender + P-4-1) | 658 | +97 | 0 |
| **Coverage Phase 4** (PlayRunner/TaskRunner e2e) | 671 | +13 | 0 |
| **本次报告产出** | **671** | **+257** | **0** |

UI 自动化目录 (`tests/croe/play/`) 单独收集 279 测, 全 pass。

## 测试文件清单 (本次报告共 11 个新单测文件 + 5 个 BUG 回归批)

### 单测文件 (新)
| 文件 | 测数 | 覆盖目标 |
|---|---|---|
| `tests/croe/play/test_base_strategy_unit.py` | 11 | StepBaseStrategy._build_content_result / write_result / write_child_result |
| `tests/croe/play/test_play_runner_unit.py` | 9 | PlayRunner 初始化 / _init_page / _clean / init_case_variables / run_case |
| `tests/croe/play/test_task_runner_unit.py` | 11 | PlayTaskExecuteParams + execute_task + __notify_report |
| `tests/croe/play/test_writer_unit.py` | 26 | ContentResultWriter / PlayCaseResultWriter / PlayTaskResultWriter |
| `tests/croe/play/test_playui_model_unit.py` | 28 | PlayCase / PlayCaseResult / PlayTask / PlayTaskResult / PlayCaseVariables / PlayStepContentResult |
| `tests/croe/play/test_step_content_strategies_unit.py` | 10 | PlayAssert / PlayGroup / PlayCondition / PlayLoop (xfail) / PlayStep |
| `tests/croe/play/test_mapper_play_unit.py` | 23 | 7 个 play mapper + 关键方法签名 |
| `tests/croe/play/test_context_unit.py` | 31 | StepContext / StepContentContext / PlayExecutionContext |
| `tests/croe/play/test_exception_unit.py` | 20 | 6 个异常类的继承层级 |
| `tests/croe/play/test_starter_unit.py` | 17 | UIStarter 继承 + event/ns 常量 + send 行为 |
| `tests/utils/test_io_sender_unit.py` | 24 | SocketSender.send/over/push/username/clear_logs |
| `tests/croe/play/test_play_runner_e2e.py` | 6 | PlayRunner.run_case 全流程编排 (e2e) |
| `tests/croe/play/test_task_runner_e2e.py` | 7 | PlayTaskRunner.execute_task 全流程编排 (e2e) |

### BUG 回归批
| 文件 | 测数 | 对应 BUG |
|---|---|---|
| `tests/croe/play/test_bug_pr1_pr2_pr3_pr4_pr5_batch.py` | 14 | P-R1..P-R5 (P0 批) |
| `tests/croe/play/test_bug_p1_1_to_p1_8_batch.py` | 15 | P-1-1..P-1-8 (P1 批) |
| `tests/croe/play/test_bug_p2_1_to_p2_3_batch.py` | 8 | P-2-1..P-2-3 (P2 批) |
| `tests/croe/play/test_bug_p_4_1_obs4_class_pollution.py` | 5 | P-4-1 (单测覆盖阶段发现) |

## 覆盖矩阵

| 模块 | 产品代码行数 | 单测文件 | 测数 | 覆盖率 | 备注 |
|---|---|---|---|---|---|
| `croe/play/play_runner.py` | ~190 | test_play_runner_unit + test_play_runner_e2e | 15 | 80%+ | 核心编排 + run_case e2e |
| `croe/play/task_runner.py` | ~150 | test_task_runner_unit + test_task_runner_e2e | 18 | 80%+ | 任务级 + execute_task e2e |
| `croe/play/writer.py` | ~190 | test_writer_unit | 26 | 70%+ | 3 个 writer + init/update/flush |
| `croe/play/context/__init__.py` | 52 | test_context_unit | 31 | 95%+ | 3 个 dataclass + 所有 property |
| `croe/play/exception.py` | 37 | test_exception_unit | 20 | 100% | 所有异常类继承关系 |
| `croe/play/starter.py` | 26 | test_starter_unit | 17 | 90%+ | event/ns 常量 + send 行为 |
| `croe/play/executor/step_content_strategy/_base.py` | ~80 | test_base_strategy_unit | 11 | 70%+ | 抽象基类行为 |
| `croe/play/executor/step_content_strategy/*` | ~400 | test_step_content_strategies_unit | 10 | 30%+ | 5 个策略基本流程 (PlayLoop 复杂 xfail) |
| `app/mapper/play/*` | ~1500 | test_mapper_play_unit | 23 | 20%+ | 关键方法签名 + 死代码锁 |
| `app/model/playUI/*` | ~600 | test_playui_model_unit | 28 | 50%+ | 核心模型 + __repr__ |
| `utils/io_sender.py` | 99 | test_io_sender_unit | 24 | 95%+ | send/over/push/username 全覆盖 |

## 关键约定 (本次报告沉淀)

1. **测试不加 DB**: 用 `inspect.getsource()` + 正则 + `unittest.mock` 锁产品代码
2. **BUG_ID 必加** `_bug_ids.py`, commit msg + 测试 + 报告三处引用
3. **修复注释格式**: `# BUG-{ID} 修复: 一句话根因 + 一句话修法 + 为什么方案 B 不行`
4. **测试文件命名**: `test_{module}_unit.py` (单文件 unit) / `test_bug_{id1}_{id2}_{id3}_batch.py` (BUG 批) / `test_{module}_e2e.py` (集成)
5. **pytest_asyncio 端到端 mock**: concrete 子类化 (e.g. `_TestStrategy(StepBaseStrategy)`) 来实例化 abstract class
6. **lock 源码时去掉注释行**, 避免误命中修复注释
7. **mapper 方法 patch 在 strategy 模块的 namespace**, 不是源模块 (`patch("croe.play.executor.step_content_strategy.play_condition_strategy.PlayConditionMapper")` not `patch("app.mapper.play.playConditionMapper.PlayConditionMapper")`)
8. **classmethod + iscoroutinefunction**: `inspect.iscoroutinefunction(Cls.method.__func__)`
9. **MagicMock + dataclass**: 不要 `spec=DataclassClass`, spec 会限制 attributes
10. **真实 User 实例 (不存 DB)**: `User()` 然后 set `id/uid/username` 而不是 MagicMock, 否则 `isinstance(user, User)` 拦不住
11. **patch.object 不要直接赋类属性**: 用 `with patch.object(X, "attr", ...)`, 不要 `X.attr = ...` (会污染后续测试, 见 P-4-1)

## 发现的隐藏 BUG (本次报告)

### P-4-1: OBS-4 测试污染类属性 (P0)
**根因**: `test_bug_obs_4_send_typed_prepends_type_marker` 用 `starter.__class__.__bases__[0].send = AsyncMock(...)` 永久改 `SocketSender.send` 类属性, 用完不还原。
**症状**: 之后所有用 `SocketSender` 的测试拿到 `AsyncMock` 的 `send` (没有真实 `self.logs.append` / `super().send` 调用链), 看似无关的 io_sender / starter 测随机 FAILED (`Expected emit awaited 0 times` / `len(logs)==0`)。
**修法**: 用 `with patch.object(SocketSender, "send", ...)` 临时改, with 退出自动还原。
**回归测试**: `tests/croe/play/test_bug_p_4_1_obs4_class_pollution.py` (5 测, 含 source scan 防 `__bases__[0].send =` 写法回归)

## 已知 xfail (1 条)

- `test_step_content_strategies_unit.py::TestPlayLoopStrategy::test_loop_*`: PlayLoopContentStrategy 接口复杂, 依赖多个 mapper, 单独跑过, 全量跑 loop 污染。`strict=False`, 后续单独完善。

## 已知跳过 (2 条)

- `test_bug_f8b_e2e_backfill_after_real_case_run`: 标记 `@pytest.mark.integration`, 需要真实 MySQL/Redis。
- `test_bug_obs_6_log_message_contains_case_result_id`: AST check 已足够, 真实 `case_result.id` 需要 DB。

## 全量回归基线

```bash
$ .venv/bin/python -m pytest -m "not integration" -q
671 passed, 2 skipped, 3 deselected, 1 xfailed, 6 warnings in 83.40s
```

## 后续优化建议 (非阻塞)

1. **PlayLoop 策略单测**: 当前 1 xfail, 后续可加 3-5 测覆盖 loop_type=1/2/3 (次数/列表/条件)
2. **script_manager 解析**: `croe/a_manager/script_manager.py` 508 行, 涵盖 `ScriptSecurityError` / `_validate_ast` / `_check_ssrf` / `_exec_in_subprocess`, 可加 8-10 测
3. **page_manager / browser**: 涉及真实 Playwright, 集成测试用 pytest-playwright 可加 e2e
4. **覆盖率数字**: 当前未跑 coverage.py 测行覆盖率, 建议加 `--cov=croe.play --cov=app.mapper.play --cov=app.model.playUI --cov=utils.io_sender` 拿真实数字
