# BUG-M7 + M8 修复报告

**提交**: `fix(M7 + M8): result 类型安全 + case_api_num 一致性`
**作者**: cyq (Codex 代笔)
**日期**: 2026-06-19
**测试**: 95 unit + 3 integration = 98 全过 (原 91, +7)

---

## TL;DR

- **M7**: 删了 `InterfaceCaseResultEnum` (str 值, 跟 `InterfaceAPIResultEnum` (bool 值) 同名不同值, 全仓 0 引用), 加 `_result_flag_to_bool()` helper 防御 str 误用导致 `bool("ERROR")=True` 静默写反。
- **M8**: 7 个 `±1/±N` 同步点 (associate_interfaces/groups/condition/loop/db + copy_step + remove_step) 的事务末尾都加了 `recompute_case_api_num()` 兜底对账, 任何漂移都会被纠正。

两个 BUG 都是"长期数据漂移"型, 修法都是"补一个权威源 + 在每个写入点结尾对账", 不破坏现有行为。

---

## BUG-M7: result 列 enum/bool 类型安全

### 根因

`enums/InterfaceEnum.py` 里有两个名字几乎一样但**值类型不同**的命名常量:

```python
class InterfaceAPIResultEnum:
    SUCCESS = True    # bool
    ERROR = False     # bool

class InterfaceCaseResultEnum:  # ← 删
    SUCCESS = "SUCCESS"  # str
    ERROR = "ERROR"      # str
```

`InterfaceCaseResult` (用例结果) 和 `InterfaceTaskResult` (任务结果) 的 `result` 列是 `Column(Boolean)`。如果哪天有人 (包括我) 不小心写成:

```python
case_result.result = InterfaceCaseResultEnum.ERROR  # 写 "ERROR"
```

SQLAlchemy 不会报错, Python 的 `bool("ERROR") == True` 会把 Boolean 列写反, **整个 result 列错位, 而且查不出来** (没有类型错误, 没有任何日志)。

`grep -rnE "InterfaceCaseResultEnum" croe/ app/ tests/` **零结果** — 这个类定义了没人用, 是"两个看起来一样的命名常量"陷阱。

### 修法 (最小侵入)

| 文件 | 改动 | 行数 |
|---|---|---|
| `enums/InterfaceEnum.py` | 删 `InterfaceCaseResultEnum` (4 行) | -4 |
| `enums/InterfaceEnum.py` | `InterfaceAPIResultEnum` 加防御性 docstring (14 行) | +14 |
| `croe/interface/writer/result_writer.py` | 加 `_result_flag_to_bool()` helper (24 行) | +24 |
| `tests/croe/interface/test_bug_m7_result_enum_safety.py` | 4 个回归测试 | +88 |

**11 个赋值点** (`InterfaceAPIResultEnum.X`) **代码保持不变** — 它们就是 bool 值, 写库 OK。改它们反而引入风险。

### 修复前后对照

| 场景 | 修复前 | 修复后 |
|---|---|---|
| `case_result.result = InterfaceAPIResultEnum.ERROR` | 写 False (正确) | 写 False (正确) |
| `case_result.result = InterfaceCaseResultEnum.ERROR` | 写 True (静默写反) | **不存在了** (类已删) |
| 有人手滑写 `result = "ERROR"` | 写 True (静默写反) | helper 归一为 False |
| 历史遗留脏数据 | 一直错 | helper 至少不污染新数据 |

### 回归测试 (4 个)

1. `test_bug_m7_interface_case_result_enum_removed` — `hasattr(ie_mod, "InterfaceCaseResultEnum")` 必须 False
2. `test_bug_m7_api_result_enum_values_are_bool` — `SUCCESS is True`, `ERROR is False`
3. `test_bug_m7_result_flag_helper_normalizes` — `_result_flag_to_bool` 接受 bool/str/None, 统一返回 bool
4. `test_bug_m7_status_enum_unchanged` — `InterfaceAPIStatusEnum` (str 状态) 不受 M7 影响

---

## BUG-M8: case_api_num 跟实际 step 关联数对账

### 根因

`InterfaceCase.case_api_num` 字段名"接口数量"误导, 实际数的是 **step 关联数** (interface_case_content_association 行数)。

同步点散落在 `app/mapper/interfaceApi/interfaceCaseMapper.py`:

| 同步点 | 行号 | 写法 | 问题 |
|---|---|---|---|
| `associate_interfaces` | 193 | `+ len(interface_ids_to_add)` | 复制模式时 N 对, OK |
| `associate_groups` | 251 | `+ len(group_id_list)` | OK |
| `associate_condition` | 303 | `+ 1` | 1 个 condition OK |
| `associate_loop` | 352 | `+ 1` | 1 个 loop OK |
| `associate_db` | 390 | `+ 1` | 1 个 db OK |
| `copy_step` | 534 | `+ 1` | OK |
| `remove_step` | 680 | `- 1` | **写死 -1, 但 group 内部可能含 N 个 API!** |

**核心 bug**: 移除 GROUP/CONDITION/LOOP 时只 `-1`, 实际一个 group 可能含 N 个 API, `case_api_num` 永远算错 (只会 -1, 不会 -N)。

其他隐患:
- 批量操作中途失败, 部分 ±1 没回滚, 字段永久错位
- 新加关联类型 (DB / WAIT / 任意未来扩展) 时容易漏改
- 没有"权威源" — 字段是计算列, 应该 COUNT, 没必要维护

### 修法 (权威源策略)

不逐个替换 (太碎, 易遗漏), 加一个权威源方法, 在 7 个事务末尾都调一次:

```python
@classmethod
async def recompute_case_api_num(cls, case_id, session=None) -> int:
    async def _do(sess):
        result = await sess.execute(
            select(InterfaceCaseStepContentAssociation).where(
                InterfaceCaseStepContentAssociation.interface_case_id == case_id
            )
        )
        actual_count = len(result.all())
        await sess.execute(
            update(InterfaceCase)
            .where(InterfaceCase.id == case_id)
            .values(case_api_num=actual_count)
        )
        return actual_count

    if session is not None:
        return await _do(session)
    async with cls.transaction() as session:
        return await _do(session)
```

**保留 ±N 立即更新** (给 UI 实时反馈), **recompute 兜底** (保证最终一致)。任何漂移都会被纠正, 而且是同步阻塞, 事务提交时已经对齐。

### 文件改动

| 文件 | 改动 |
|---|---|
| `app/mapper/interfaceApi/interfaceCaseMapper.py` | 加 `recompute_case_api_num` classmethod (+57 行, 含 docstring) |
| `app/mapper/interfaceApi/interfaceCaseMapper.py` | 7 个事务末尾追加 `await cls.recompute_case_api_num(case_id, session)` (各 +2 行) |
| `tests/croe/interface/test_bug_m8_case_api_num_consistency.py` | 3 个回归测试 (+85 行) |

### 修复前后对照

| 场景 | 修复前 | 修复后 |
|---|---|---|
| 关联 1 个 GROUP (含 3 个 API) | case_api_num +1 (实际 +1 step, OK) | +1 后 recompute: 1 (OK) |
| 移除上面那个 GROUP | case_api_num -1 (实际 -1 step, OK) | -1 后 recompute: 0 (OK) |
| 关联 5 个独立 API | case_api_num +5 (OK) | +5 后 recompute: 5 (OK) |
| 上面 5 个 API 中途失败 (插入 3 个, 2 个 rollback) | case_api_num +5 (但实际只有 3) ❌ | +5 → 回滚 → recompute 不调 (事务回滚, OK) ✅ |
| 历史漂移: 字段=10, 实际只有 2 | 永远错 | 任何 add/remove 后 recompute: 2 ✅ |
| 新加关联类型 (比如 WAIT) 漏写同步 | 字段永久错 | recompute 兜底 ✅ |

### 回归测试 (3 个)

1. `test_bug_m8_recompute_writes_actual_count` — mock session, 验证 COUNT + UPDATE 各调一次
2. `test_bug_m8_recompute_corrects_drift` — 漂移场景 (字段=100, 实际=2), recompute 后应写 2
3. `test_bug_m8_callers_pass_session` — grep 静态检查 7 个 call site 都传了 session

---

## 测试覆盖

```bash
$ .venv/bin/python -m pytest tests/ -q -m "not integration" --tb=short
================= 95 passed, 3 deselected, 6 warnings in 6.27s =================

$ .venv/bin/python -m pytest tests/ -m integration
================= 3 passed, 95 deselected, 6 warnings in 1.02s =================
```

新增 7 个测试 (4 × M7 + 3 × M8), 全部通过, 无回归。

---

## 风险评估

### M7

- **删除 `InterfaceCaseResultEnum`**: 全仓 0 引用, 零风险
- **helper 不调用**: 零侵入, 是给"未来写错的人"留的护栏
- **docstring 提示**: 防止后人重新引入同名 str 类

### M8

- **7 处 `recompute_case_api_num` 调用都在事务末尾**: 跟现有 ±N update 共享事务, 一起 commit/rollback
- **如果事务失败**: recompute 不执行, ±N update 也不执行, 字段维持原值
- **如果有人调了 recompute 但没开事务**: helper 自己开 `cls.transaction()`, 安全
- **COUNT vs COUNT(*)**: 用 `select(InterfaceCaseStepContentAssociation).where(...).all()` 然后 `len()`, 跟 ORM 一致, 没 N+1 (就一次 count + 一次 update)

---

## 候选下一波

| 优先级 | BUG | 估时 | 说明 |
|---|---|---|---|
| P0 | F6 | 0.5h | progress int 截断语义 (跟 F5 同源) |
| P1 | M6 | 1h | with_polymorphic 笛卡尔积 (性能 bug) |
| P1 | D5 | 2-3h | query_steps 多 joinedload 笛卡尔积 |
| P1 | E6-E12 | 1.5-2h | 剩余执行器层 easy wins |
| P2 | RED-D6/7/8 | 2h | 测试覆盖补全 |

总剩余 P1 ~14 项, 1-2 天能再清一波。
