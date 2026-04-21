# Code Review Report: redis_worker_pool.py

## Report Metadata
- **File**: `/Users/cyq/work/code/case_auto_hub/common/redis_worker_pool.py`
- **Review Date**: 2026-04-21
- **Reviewer**: AI Code Reviewer
- **Target Audience**: AI Systems (for automated code modification)

---

## Issue Summary

| Priority | Issue ID | Issue Title | Status |
|----------|----------|-------------|--------|
| CRITICAL | ISS-001 | `_raw_redis` 连接泄漏 | ✅ Fixed |
| CRITICAL | ISS-002 | processing_key 任务无超时机制导致任务永久丢失 | ✅ Fixed |
| HIGH | ISS-003 | processing_key 缺少 TTL 导致 Worker 崩溃后任务卡死 | ✅ Fixed |
| MEDIUM | ISS-004 | `get_stats` 中冗余的条件判断 | ✅ Fixed |
| MEDIUM | ISS-005 | 多进程环境下任务被重复领取的风险 | Pending (Optional) |
| LOW | ISS-006 | 代码注释遗留（调试日志） | ✅ Fixed |

---

## Issue Detail & Solution

---

### ISS-001: `_raw_redis` 连接泄漏

**Priority**: CRITICAL

**Location**:
- File: `redis_worker_pool.py`
- Line: 301-305

**Problem Description**:
`disconnect_redis()` 方法没有关闭 `_raw_redis` 连接，导致连接泄漏。长期运行可能导致 Redis 连接池耗尽。

**Current Code**:
```python
async def disconnect_redis(self):
    """断开Redis连接"""
    self._redis_connected = False
    self.redis_client = None
    log.info("RedisWorkerPool 连接已关闭")
```

**Optimal Solution**:
```python
async def disconnect_redis(self):
    """断开Redis连接"""
    self._redis_connected = False
    if self._raw_redis:
        await self._raw_redis.aclose()
        self._raw_redis = None
    self.redis_client = None
    log.info("RedisWorkerPool 连接已关闭")
```

**Modification Type**: Fix Bug

---

### ISS-002: processing_key 任务无超时机制

**Priority**: CRITICAL

**Location**:
- File: `redis_worker_pool.py`
- Line: 491-493

**Problem Description**:
任务被 Worker 领取后存储在 `processing_key` 中，但如果 Worker 进程崩溃或卡住，任务会永久卡在 "处理中" 状态。没有任何超时机制来释放这些任务。

**Current Code**:
```python
await self._raw_redis.hset(processing_key, job_id, serialized_job)
return job_id, serialized_job
```

**Optimal Solution**:
```python
await self._raw_redis.hset(processing_key, job_id, serialized_job)
await self._raw_redis.expire(processing_key, 300)  # 5分钟超时，防止任务永久卡住
return job_id, serialized_job
```

**Note**: 需要确保 `processing_key` 格式正确，包含 worker 标识以支持多 Worker 并发。

**Modification Type**: Feature Improvement

---

### ISS-003: processing_key 缺少 TTL 导致 Worker 崩溃后任务卡死

**Priority**: HIGH

**Location**:
- File: `redis_worker_pool.py`
- Line: 491-493
- Also affects: `_get_job_atomic` fallback path (line 481-492)

**Problem Description**:
当 Lua 脚本执行失败回退到 `bzpopmin` 方案时，同样没有为 processing_key 设置 TTL。如果 Worker 在任务执行过程中崩溃，任务将永久丢失。

**Current Code (fallback path)**:
```python
except (UnicodeDecodeError, Exception) as e:
    log.warning(f"Lua script error, falling back: {e}")
    result = await self._raw_redis.bzpopmin(self.queue_key, timeout=0.5)
    if not result:
        return None

    _key, job_id, _score = result
    job_id = job_id.decode('utf-8') if isinstance(job_id, bytes) else job_id

    serialized_job = await self._raw_redis.hget(self.job_data_key, job_id)
    if not serialized_job:
        return None

    await self._raw_redis.hset(processing_key, job_id, serialized_job)
    return job_id, serialized_job
```

**Optimal Solution**:
```python
except (UnicodeDecodeError, Exception) as e:
    log.warning(f"Lua script error, falling back: {e}")
    result = await self._raw_redis.bzpopmin(self.queue_key, timeout=0.5)
    if not result:
        return None

    _key, job_id, _score = result
    job_id = job_id.decode('utf-8') if isinstance(job_id, bytes) else job_id

    serialized_job = await self._raw_redis.hget(self.job_data_key, job_id)
    if not serialized_job:
        return None

    await self._raw_redis.hset(processing_key, job_id, serialized_job)
    await self._raw_redis.expire(processing_key, 300)  # 5分钟超时
    return job_id, serialized_job
```

**Modification Type**: Fix Bug

---

### ISS-004: `get_stats` 中冗余的条件判断

**Priority**: MEDIUM

**Location**:
- File: `redis_worker_pool.py`
- Line: 576-583

**Problem Description**:
代码中存在冗余的条件判断，`if len(parts) >= 3` 判断了两次且结果相同时执行相同逻辑。

**Current Code**:
```python
for key in processing_keys:
    parts = key.decode('utf-8').split(':') if isinstance(key, bytes) else key.split(':')
    if len(parts) >= 3:
        server_worker = parts[2]
        if len(parts) >= 3:  # ← 冗余判断
            server_id = '_'.join(server_worker.split('_')[:-2])
        else:
            server_id = '_'.join(server_worker.split('_')[:-2])  # ← 完全相同的代码
    servers.add(server_id)
```

**Optimal Solution**:
```python
for key in processing_keys:
    parts = key.decode('utf-8').split(':') if isinstance(key, bytes) else key.split(':')
    if len(parts) >= 3:
        server_worker = parts[2]
        server_id = '_'.join(server_worker.split('_')[:-2])
        servers.add(server_id)
```

**Modification Type**: Code Cleanup

---

### ISS-005: 多进程环境下任务被重复领取的风险

**Priority**: MEDIUM

**Location**:
- File: `redis_worker_pool.py`
- Line: 481
- Also affects: `_get_job_atomic` fallback path

**Problem Description**:
当 Lua 脚本执行失败回退到 `bzpopmin` 方案时，`bzpopmin` 操作不是原子的。多个 Worker 可能同时从队列取出同一个任务，导致任务被重复执行。

**Current Code**:
```python
except (UnicodeDecodeError, Exception) as e:
    log.warning(f"Lua script error, falling back: {e}")
    result = await self._raw_redis.bzpopmin(self.queue_key, timeout=0.5)  # 非原子操作
```

**Optimal Solution**:
```python
except (UnicodeDecodeError, Exception) as e:
    log.warning(f"Lua script error, falling back: {e}")
    # 使用悲观锁确保同一任务不被多个 Worker 领取
    lock_key = f"job_lock:{self.queue_name}"
    async with self._raw_redis.lock(lock_key, timeout=5):
        result = await self._raw_redis.bzpopmin(self.queue_key, timeout=0.5)
        if not result:
            return None

        _key, job_id, _score = result
        job_id = job_id.decode('utf-8') if isinstance(job_id, bytes) else job_id

        # 检查任务是否已被其他 Worker 领取
        already_processing = False
        for worker_id in range(self.worker_count):
            check_key = f"{self.processing_key}:{self.server_id}_worker_{worker_id}"
            if await self._raw_redis.hexists(check_key, job_id):
                already_processing = True
                break

        if already_processing:
            # 将任务放回队列
            await self._raw_redis.zadd(self.queue_key, {job_id: _score})
            return None

        serialized_job = await self._raw_redis.hget(self.job_data_key, job_id)
        if not serialized_job:
            return None

        await self._raw_redis.hset(processing_key, job_id, serialized_job)
        await self._raw_redis.expire(processing_key, 300)
        return job_id, serialized_job
```

**Note**: 此修复较为复杂，如果 Lua 脚本工作正常（ISS-001 修复后），此 fallback 分支不会被执行。建议优先确保 Lua 脚本正常工作。

**Modification Type**: Robustness Improvement

---

### ISS-006: 代码注释遗留（调试日志）

**Priority**: LOW

**Location**:
- File: `redis_worker_pool.py`
- Line: 819-826

**Problem Description**:
调试用的临时日志注释遗留在线上代码中。

**Current Code**:
```python
@r_pool.register_function
async def register_interface_task_RoBot(**kwargs):
    log.info("=== register_interface_task_RoBot 开始 ===")  # 添加
    try:
        runner = TaskRunner(APIStarter(StarterEnum.RoBot))
        log.info(f"=== runner created: {runner} ===")  # 添加
        await runner.execute_task(params=TaskParams(**kwargs))
        log.info("=== register_interface_task_RoBot 结束 ===")  # 添加
    except Exception as e:
        log.error(f"=== register_interface_task_RoBot 异常: {e} ===")  # 添加
```

**Optimal Solution**:
```python
@r_pool.register_function
async def register_interface_task_RoBot(**kwargs):
    """
    接口任务注册执行
    定时执行
    """
    try:
        runner = TaskRunner(APIStarter(StarterEnum.RoBot))
        await runner.execute_task(params=TaskParams(**kwargs))
    except Exception as e:
        log.error(f"register_interface_task_RoBot 执行失败: {e}")
```

**Modification Type**: Code Cleanup

---

## Implementation Order

AI 系统应按以下顺序应用修复：

1. **ISS-001** - `_raw_redis` 连接泄漏 (CRITICAL)
2. **ISS-002** - processing_key 添加 TTL (CRITICAL)
3. **ISS-003** - fallback 路径添加 TTL (HIGH)
4. **ISS-004** - 移除冗余条件判断 (MEDIUM)
5. **ISS-006** - 清理调试日志 (LOW)
6. **ISS-005** - 多进程安全优化 (MEDIUM, 可选如果 Lua 脚本正常)

---

## Verification Checklist

After applying all fixes, verify:

- [ ] `disconnect_redis()` 正确关闭 `_raw_redis` 连接
- [ ] `processing_key` 拥有 300 秒 TTL
- [ ] `get_stats()` 中无冗余条件判断
- [ ] 调试日志已清理
- [ ] 多 Worker 环境下任务不会丢失或重复执行
- [ ] 应用重启后 Worker Pool 正常启动
- [ ] 任务提交和执行流程正常

---

## End of Report
