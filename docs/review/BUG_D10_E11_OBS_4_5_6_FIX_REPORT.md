# BUG-D10 + E11 + OBS-4 + OBS-5 + OBS-6 Fix Report: 5 个 easy wins 一锅端

**触发版本**: master
**Commit**: (本 fix)
**测试**: `tests/croe/interface/test_bug_d10_e11_obs_4_5_6.py` (12 个)

---

## 现象 (5 个 BUG)

### D10 [中] dynamicMapper append_dynamic 时机不对
- 位置: `interfaceCaseMapper.py:73-95` / `interfaceMapper.py:69-95` `update_interface_case` / `update_interface`
- `update_by_id` 内部走 `update_cls` 默认 `expunge=True`, 然后返的 `new_case` 已 detached
- 调用方紧跟着 `new.to_dict()` 拿快照: 当前 to_dict 只读列字段没事, **但任何 lazy='selectin' 关系访问会静默拿到 stale data 或 detached instance 报错**
- 后果: latent bug, 当前不爆但加 relationship 访问就炸

### E11 [低] condition_step 写库漏 assert_data
- 位置: `step_content_condition.py:64-77` 写库时只把 `assert_data` 拆成 `condition_key/value/operator` 4 个列, 漏了原始 `assert_data` 字典
- 模型里有 `assert_data` JSON 列, 写库逻辑没用上
- 后果: 排查时拿不到完整 condition 上下文 (key/value/operator/condition_result 整体丢了)

### OBS-4 [中] starter.send emoji 协议无类型安全
- 位置: 全项目, `starter.send(f"🫳🫳  ...")`, `starter.send(f"✍️✍️  ...")`, `starter.send(f"⏭️⏭️  ...")` 等
- 前端靠 emoji 区分步骤类型, 拼错 / 加新类型都得同步改前端
- 修: 加 `STARTER_MSG_TYPE` 常量 + `send_typed(type, msg)` 结构化路径, 旧 emoji 协议 DEPRECATED 但兼容

### OBS-5 [中] set_result_field 只有 setter 没返值
- 位置: `interfaceResultMapper.py:65-71` `set_result_field` 只 `add_flush_expunge`, **不返任何状态**, 调用方只能靠 raise
- 后果: 调用方写 `await mapper.set_result_field(cr)` 后 `if not result: ...` 永远 False (因 result 是 None), 业务上无法表达"成功 vs 失败"

### OBS-6 [低] log 里无 case_result_id
- 位置: `runner.py:180` `log.debug(f"self.result_writer.init_case_result ={case_result}")` 拿到 case_result 对象但不打 case_result_id
- 后果: 排查单 case 时无法 grep `case_result_id=42` 直接定位, 要靠 trace_id 间接关联
- 修: 显式 log `case_id=X case_result_id=Y task_result_id=Z`, 加 trace_id 后也能关联但显式更直接

---

## 修复 (5 处改动, 跨 6 个文件)

### D10: post_update_hook callback (1 个新参数 + 2 个 call site 改动)
```python
# app/mapper/__init__.py
async def update_by_id(
    cls,
    session: AsyncSession = None,
    update_user: User = None,
    post_update_hook: Optional[callable] = None,  # 新
    **kwargs,
) -> M:
    ...
    async with cls.transaction(session) as session:
        target = await cls.get_by_id(ident, session)
        await cls.update_cls(target, session, **kwargs)  # 此时还 attached
        if post_update_hook is not None:
            result = post_update_hook(target)  # 拿快照, target 还 attached!
            if hasattr(result, '__await__'):
                result = await result
            return result
        return target
```

```python
# interfaceCaseMapper.py update_interface_case
old_case_map = old_case.to_dict()
new_case_map_holder = {}
new_case = await cls.update_by_id(
    session=session,
    update_user=user,
    post_update_hook=lambda t: new_case_map_holder.__setitem__('m', t.to_dict()) or t,
    **kwargs
)
new_case_map = new_case_map_holder['m']  # 在 attached 时拿的, 安全
```

### E11: 1 行
```python
# step_content_condition.py write_step_result
condition_result=condition_passed,
condition_key=content_condition.get("key"),
condition_value=content_condition.get("value"),
condition_operator=content_condition.get("operator"),
assert_data=content_condition,  # BUG-E11: 原始 dict 一并存
```

### OBS-4: STARTER_MSG_TYPE + send_typed (新文件 100% 重写)
```python
# croe/interface/starter.py
class STARTER_MSG_TYPE:
    EXECUTE = "✍️✍️"  # DEPRECATED
    EXTRACT = "🫳🫳"  # DEPRECATED
    SKIP = "⏭️⏭️"    # DEPRECATED
    TYPE_EXECUTE = "[TYPE_EXECUTE]"
    TYPE_EXTRACT = "[TYPE_EXTRACT]"
    TYPE_SKIP = "[TYPE_SKIP]"
    TYPE_FINISH = "[TYPE_FINISH]"
    TYPE_ERROR = "[TYPE_ERROR]"
    TYPE_INFO = "[TYPE_INFO]"

class APIStarter(SocketSender):
    async def send(self, msg):  # 旧, 兼容
        ...
    async def send_typed(self, msg_type, msg):  # 新, 推荐
        await self.send(f"{msg_type} {msg}")
```

### OBS-5: 返 bool
```python
@classmethod
async def set_result_field(cls, caseResult: InterfaceCaseResult) -> bool:  # 改返 bool
    try:
        async with cls.transaction() as session:
            await cls.add_flush_expunge(session, caseResult)
        return True  # 成功
    except Exception as e:
        log.error(f"set_result_field case_result 失败: {e}")
        raise
```

### OBS-6: 显式 log
```python
# runner.py:174-181
case_result = await self.result_writer.init_case_result(...)
# BUG-OBS-6 修复: 显式 log case_result_id, 不靠 trace_id 间接关联
log.debug(
    f"[BUG-OBS-6] case_result 初始化完成: "
    f"case_id={interface_case_id} "
    f"case_result_id={getattr(case_result, 'id', None)} "
    f"task_result_id={getattr(task_result, 'id', None) if task_result else None}"
)
```

---

## 关键设计取舍

1. **D10 callback 而非参数 `expunge=False`**: callback 显式表达"我想在 expunge 前做 X", 比 plumb expunge 到底层更安全 (防止调用方忘了手动 expunge)
2. **D10 callback 返值透传**: hook 返什么 update_by_id 就返什么, 给 hook 完整控制 (可以返 None / dict / model)
3. **D10 callback 可 async**: 用 `hasattr(result, '__await__')` 自动 await, 兼容 sync/async hook
4. **E11 存原始 dict + 拆列并存**: 拆列存利于 query / index, 存原始 dict 利于排查 (前端展示完整上下文), 两路都有价值
5. **OBS-4 保留旧 emoji 协议**: 完整切走风险大 (前端要同步改), DEPRECATED 但兼容, 给前端过渡期
6. **OBS-4 走 `send_typed`**: 5 个类型常量, 前端解析 `[TYPE_xxx]` 比解析 emoji 容易 (正则 `\bTYPE_EXECUTE\b` vs Unicode emoji 字符)
7. **OBS-5 返 bool 而非 enum**: 跟 Python 习惯对齐, True=成功, 失败抛异常, 调用方 `if not await mapper.set_result_field(cr): ...` 直接可读
8. **OBS-6 显式 ID 跟 trace_id 并存**: trace_id 是跨多 case 时的 correlation, 显式 ID 是排查单 case 的快速通道, 两者不互斥

---

## 修复前后对照

| 场景 | 修复前 | 修复后 |
|---|---|---|
| update 完访问 lazy 关系 | `lazy='selectin'` 关系在 expunged model 上不命中, stale data | post_update_hook 在 attached 时拿快照, 关系访问安全 ✓ |
| update_interface_case 改 1 字段 | 字段改了但 `old/new_map` 不一致 (新 map 漏关系字段) | `old/new_map` 完整一致 ✓ |
| condition step 排查 | 看 DB 只看到 key/value/operator 4 列, 不知完整 dict | 还能看 `assert_data` JSON 列拿完整 dict ✓ |
| 前端解析 step 类型 | 正则匹配 emoji, 拼错就 broken | 解析 `[TYPE_xxx]` 结构化前缀, type-safe ✓ |
| starter 新加类型 | 找一处 emoji 用, 散落 | `STARTER_MSG_TYPE.TYPE_INFO = "[TYPE_INFO]"` 加常量即可 ✓ |
| 调 `set_result_field` 后判断成功 | 永远 None, `if not result` 永远 False | True/异常, 业务逻辑可表达成功失败 ✓ |
| 单 case 排查 | `grep "case_id=42"` 多 case 共用 ID 易混 | `grep "case_result_id=123"` 唯一 ID 直接定位 ✓ |
| 加 relationship 字段到 to_dict | 静默 stale / 偶尔 detached instance 报错 | callback 在 attached 时拿, 安全 ✓ |

---

## 回归测试 (12 个, mock 不接 DB)

`tests/croe/interface/test_bug_d10_e11_obs_4_5_6.py`:

**D10 (5)**:
1. `test_bug_d10_update_by_id_accepts_post_update_hook` — 签名含 post_update_hook
2. `test_bug_d10_update_cls_keeps_target_attached_for_hook` — hook 必须在 update_cls 之后调 (target 还 attached)
3. `test_bug_d10_post_update_hook_receives_target_before_expunge` — 端到端 mock, hook 拿 attached target
4. `test_bug_d10_no_hook_returns_target_as_before` — 不传 hook 向后兼容, 仍返 target
5. `test_bug_d10_update_interface_case_uses_post_update_hook` — 2 个 call site 都用 hook
6. `test_bug_d10_update_interface_uses_post_update_hook` — 同上

**E11 (1)**:
7. `test_bug_e11_condition_step_writes_assert_data` — 源码含 `assert_data=content_condition`

**OBS-4 (3)**:
8. `test_bug_obs_4_starter_msg_type_constant_exists` — 5 个 TYPE_* 常量
9. `test_bug_obs_4_starter_has_send_typed_method` — `send_typed(type, msg)` 方法
10. `test_bug_obs_4_send_typed_prepends_type_marker` — 端到端 mock, 抓到的消息含 `[TYPE_xxx]`

**OBS-5 (1)**:
11. `test_bug_obs_5_set_result_field_returns_bool` — 源码含 `-> bool` + `return True`

**OBS-6 (1)**:
12. `test_bug_obs_6_runner_logs_case_result_id` — 源码含 `case_result_id=` 显式 log

**全量回归**: 255 unit passed (243 老 + 12 新), 1 skipped (DB 端到端 placeholder), 0 fail.

---

## 教训

- **callback 比参数透传更显式**: D10 用 post_update_hook callback 比 `expunge=False` plumb 到底层更安全, 调用方意图清晰
- **latent bug 也值得修**: D10 当前不爆但埋雷, 加 relationship 访问就坏。**早修低成本, 晚修高风险**
- **emoji 协议不是好协议**: OBS-4 揭示 Unicode emoji 当协议是反模式 (拼写错 / 加新类型都易碎), 结构化 `[TYPE_xxx]` 更稳
- **存原始 + 拆列并存**: E11 模式 (存 dict + 拆列 query-friendly) 在排查/性能间平衡, 比"只存拆列"或"只存 dict"都好
- **setter 返 bool 是 Python 习惯**: OBS-5 改返 bool, 调用方 `if not await ...: ...` 直接可读, 跟 raise 配合表达"成功 vs 失败"
- **显式 ID 跟 trace_id 互补**: trace_id 跨多 case 关联, 显式 ID 单 case 排查。**两者并存, 不互斥**
- **callback 兼容 sync/async**: D10 用 `hasattr(result, '__await__')` 自动 await, 给 hook 实现最大灵活性
