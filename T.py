import asyncio
from typing import List, Callable, Any
from collections import deque


class DynamicTaskScheduler:
    """动态任务调度器"""

    def __init__(self, max_concurrent: int = 5):
        self.max_concurrent = max_concurrent
        self.active_tasks = set()
        self.pending_queue = deque()
        self.completed_results = []
        self.task_id_counter = 0

    async def job1(self, job_id: int):
        """你的job1函数"""
        try:
            print(f"[Job-{job_id}] Job start")
            for i in range(10):
                await asyncio.sleep(0.5)  # 改成0.5秒方便演示
                print(f"[Job-{job_id}] Progress {i + 1}/10")
            print(f"[Job-{job_id}] Job completed")
            return f"Job-{job_id}-result"
        except Exception as e:
            print(f"[Job-{job_id}] Error: {e}")
            raise

    async def _task_wrapper(self, task_id: int, func: Callable, *args, **kwargs):
        """任务包装器，处理完成后的清理工作"""
        try:
            result = await func(*args, **kwargs)
            self.completed_results.append((task_id, result))
            return result
        finally:
            self.active_tasks.discard(task_id)
            # 检查是否有等待的任务可以开始
            await self._schedule_next()

    async def _schedule_next(self):
        """调度下一个等待的任务"""
        while len(self.active_tasks) < self.max_concurrent and self.pending_queue:
            task_id, func, args, kwargs = self.pending_queue.popleft()
            print(f"[Scheduler] Starting pending task {task_id} "
                  f"({len(self.pending_queue)} still waiting)")

            task = asyncio.create_task(
                self._task_wrapper(task_id, func, *args, **kwargs)
            )
            self.active_tasks.add(task_id)

    async def submit(self, func: Callable, *args, **kwargs) -> int:
        """提交任务"""
        self.task_id_counter += 1
        task_id = self.task_id_counter

        if len(self.active_tasks) < self.max_concurrent:
            # 有空位，立即开始
            print(f"[Scheduler] Task {task_id} starts immediately")
            task = asyncio.create_task(
                self._task_wrapper(task_id, func, *args, **kwargs)
            )
            self.active_tasks.add(task_id)
        else:
            # 没有空位，加入等待队列
            print(f"[Scheduler] Task {task_id} added to queue "
                  f"({len(self.pending_queue) + 1} in queue)")
            self.pending_queue.append((task_id, func, args, kwargs))

        return task_id

    async def wait_all(self):
        """等待所有任务完成"""
        while self.active_tasks or self.pending_queue:
            await asyncio.sleep(0.1)

    def get_status(self):
        """获取当前状态"""
        return {
            'max_concurrent': self.max_concurrent,
            'active': len(self.active_tasks),
            'waiting': len(self.pending_queue),
            'completed': len(self.completed_results)
        }


async def task():
    """主任务 - 演示动态调度"""
    print("=" * 50)
    print("动态任务调度器演示")
    print("=" * 50)

    scheduler = DynamicTaskScheduler(max_concurrent=5)

    # 提交初始5个任务
    print("\n[阶段1] 提交5个任务（全部立即开始）")
    for i in range(1, 6):
        await scheduler.submit(scheduler.job1, i)
        await asyncio.sleep(0.1)

    print(f"\n状态: {scheduler.get_status()}")

    # 等待1秒后提交第6个任务
    await asyncio.sleep(1)
    print("\n[阶段2] 提交第6个任务（进入等待队列）")
    task6_id = await scheduler.submit(scheduler.job1, 6)
    print(f"状态: {scheduler.get_status()}")

    # 提交更多任务
    await asyncio.sleep(0.5)
    print("\n[阶段3] 提交更多任务（7-12）")
    for i in range(7, 13):
        await scheduler.submit(scheduler.job1, i)
        await asyncio.sleep(0.2)

    # 监控状态
    print("\n[阶段4] 监控执行过程...")
    for _ in range(10):
        status = scheduler.get_status()
        print(f"状态: 运行中 {status['active']}, 等待中 {status['waiting']}, "
              f"已完成 {status['completed']}")
        await asyncio.sleep(1)

    # 等待所有任务完成
    print("\n[阶段5] 等待所有任务完成...")
    await scheduler.wait_all()

    print("\n" + "=" * 50)
    print("所有任务完成!")
    final_status = scheduler.get_status()
    print(f"总任务数: {final_status['completed']}")
    print("=" * 50)


if __name__ == '__main__':
    asyncio.run(task())