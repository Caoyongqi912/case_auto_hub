"""
2026-06-22 Round 2 - 修复

触发: 端点 GET /interfaceResult/queryStepResult?case_result_id=68
 跨机房 DB 场景 (10.1.5.49) 响应 4s 慢

回归: tests/croe/interface/test_bug_result_step_cache.py
"""
import inspect
import re

import pytest

from tests.croe.interface._bug_ids import BUG_RESULT_STEP_CACHE


def _controller_src() -> str:
    from app.controller.interface import interfaceResultController
    return inspect.getsource(interfaceResultController)


def _writer_src() -> str:
    from croe.interface.writer import result_writer
    return inspect.getsource(result_writer)


def _extract_func(src: str, name: str, indent: str = "") -> str:
        """从源码里抽函数/方法体, 按缩进找边界。"""
    start = src.find(f"{indent}async def {name}")
    if start < 0:
        start = src.find(f"{indent}def {name}")
    assert start >= 0, f"{name} not found"
    end = len(src)
 # 找下一个同层级的 def/class/decorator
    boundary_re = re.compile(rf"\n({indent}async def |{indent}def |class |@)")
    for m in boundary_re.finditer(src[start+1:]):
        end = start + 1 + m.start()
        break
    return src[start:end]

def _mysql_reachable() -> bool:
        """本地 MySQL 可达 = True. 用 2s 超时, 跑默认单测不卡."""
    try:
        import pymysql
        from config import LocalConfig
        conn = pymysql.connect(
            host=LocalConfig.MYSQL_SERVER,
            port=LocalConfig.MYSQL_PORT,
            user="root",
            password=LocalConfig.MYSQL_PASSWORD,
            database=LocalConfig.MYSQL_DATABASE,
            connect_timeout=2,
        )
        conn.close()
        return True
    except Exception:
        return False



# ============================================================
# controller 缓存配置
# ============================================================
class TestBugResultStepCacheController:
    """controller 必须有 STEP_RESULT_CACHE_PREFIX/TTL 常量 + cache 读写逻辑"""

    def test_controller_has_cache_prefix(self):
        """controller 必须有 STEP_RESULT_CACHE_PREFIX"""
        src = _controller_src()
        assert "STEP_RESULT_CACHE_PREFIX" in src
        m = re.search(r'STEP_RESULT_CACHE_PREFIX\s*=\s*["\']([^"\']+)["\']', src)
        assert m
        assert m.group(1).startswith("result:"), (
            f"[{BUG_RESULT_STEP_CACHE}] 缓存 key prefix 建议 'result:steps:', 实际: {m.group(1)}"
        )

    def test_controller_has_cache_ttl(self):
        """controller 必须有 STEP_RESULT_CACHE_TTL=1-30"""
        src = _controller_src()
        assert "STEP_RESULT_CACHE_TTL" in src
        m = re.search(r"STEP_RESULT_CACHE_TTL\s*=\s*(\d+)", src)
        assert m
        ttl = int(m.group(1))
        assert 1 <= ttl <= 30, f"[{BUG_RESULT_STEP_CACHE}] TTL 建议 1-30s, 实际: {ttl}"

    def test_controller_uses_redis_client(self):
        """controller 必须 import Redis client (rc)"""
        src = _controller_src()
        assert "from common import rc" in src

    def test_controller_query_step_results_has_cache_read(self):
        """query_step_results 必须有 cache 读取逻辑, 且在 mapper 之前"""
        src = _controller_src()
        body = _extract_func(src, "query_step_results")
        cache_read_pos = body.find("rc.r.get")
        mapper_pos = body.find("InterfaceContentStepResultMapper.query_steps_result")
        assert cache_read_pos > 0, f"[{BUG_RESULT_STEP_CACHE}] 缺 rc.r.get 读 cache"
        assert mapper_pos > 0, "缺 mapper 调用"
        assert cache_read_pos < mapper_pos, (
            f"[{BUG_RESULT_STEP_CACHE}] cache 读必须在 mapper 调之前"
        )

    def test_controller_query_step_results_has_cache_write(self):
        """query_step_results 必须在 mapper 之后写 cache"""
        src = _controller_src()
        body = _extract_func(src, "query_step_results")
        mapper_pos = body.find("InterfaceContentStepResultMapper.query_steps_result")
        cache_write_pos = body.find("rc.r.set")
        assert cache_write_pos > 0, f"[{BUG_RESULT_STEP_CACHE}] 缺 rc.r.set 写 cache"
        assert cache_write_pos > mapper_pos, (
            f"[{BUG_RESULT_STEP_CACHE}] cache 写必须在 mapper 调之后, 否则写空数据"
        )

    def test_controller_cache_uses_ex_ttl(self):
        """cache 写必须用 ex=TTL (Redis TTL 语法)"""
        src = _controller_src()
 # set 调用可能跨行, 用 [\s\S] (DOTALL) 不用 [^)]
 # 找 "rc.r.set" 出现的位置, 后面 200 字符内必须有 ex=
        m = re.search(r"rc\.r\.set", src)
        assert m, f"[{BUG_RESULT_STEP_CACHE}] controller 缺 rc.r.set 调用"
        snippet = src[m.start():m.start()+300]
        assert re.search(r"ex\s*=", snippet), (
            f"[{BUG_RESULT_STEP_CACHE}] rc.r.set 必须带 ex= 参数 (Redis TTL 语法)"
        )

    def test_controller_invalidate_helper(self):
        """必须有 _invalidate_step_result_cache async helper"""
        from app.controller.interface.interfaceResultController import _invalidate_step_result_cache
        assert callable(_invalidate_step_result_cache)
        import asyncio
        assert asyncio.iscoroutinefunction(_invalidate_step_result_cache)


# ============================================================
# writer 写时 invalidation
# ============================================================
class TestBugResultStepCacheWriter:
    """write_step_result 必须在写库前 DEL cache"""

    def test_writer_imports_rc(self):
        """result_writer 必须 import rc"""
        src = _writer_src()
        assert "from common import rc" in src

    def test_writer_write_step_result_invalidates_cache(self):
        """write_step_result 必须在 insert 之前 rc.r.delete"""
        src = _writer_src()
        body = _extract_func(src, "write_step_result", indent="    ")
        assert "rc.r.delete" in body, (
            f"[{BUG_RESULT_STEP_CACHE}] write_step_result 缺 rc.r.delete (写时清缓存)"
        )
        delete_pos = body.find("rc.r.delete")
        insert_pos = body.find("InterfaceContentStepResultMapper.insert_result")
        assert delete_pos < insert_pos, (
            f"[{BUG_RESULT_STEP_CACHE}] rc.r.delete 必须在 insert_result 之前, "
            f"否则 cache 清的是旧值, 新值又写回 cache"
        )

    def test_writer_uses_same_prefix_as_controller(self):
        """writer 和 controller 用同一 cache prefix"""
        assert "result:steps:" in _writer_src(), (
            f"[{BUG_RESULT_STEP_CACHE}] writer 必须用 'result:steps:' 前缀"
        )


# ============================================================
# DB 索引 (集成层, 需要真 DB)
# ============================================================
@pytest.mark.integration
class TestBugResultStepCacheIndex:
    """DB 必须加 (case_result_id, content_step) 联合索引

 注: 集成测试, 需要真实 MySQL. CI 跑时 pytest -m integration 才执行.
 单元测试 (默认) 跳过, 由人工 / 部署脚本验证.
 """

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_db_has_composite_index(self):
        """interface_case_content_result 必须有 (case_result_id, content_step) 联合索引"""
        if not _mysql_reachable():
            pytest.skip("本地 MySQL 不可达, 跳过集成测试")
        from sqlalchemy import text
        from app.model import async_session
        async with async_session() as s:
 result = await s.execute(text("""
 SHOW INDEX FROM interface_case_content_result
 WHERE Column_name = 'content_step'
 """))
            rows = result.fetchall()
            found = False
            for r in rows:
                key_name = (r[2] or "").lower()
                if "case_result" in key_name and "content_step" in key_name:
                    found = True
                    break
        assert found, (
            f"[{BUG_RESULT_STEP_CACHE}] 缺 (case_result_id, content_step) 联合索引"
        )

    @pytest.mark.integration
    def test_explain_no_filesort(self):
        """queryStepResult 路径的 SQL 不能有 Using filesort

 改用 sync pymysql, 避开 pytest-asyncio 多 loop 切换时
 async_session scoped session 拿旧 loop 连接的 RuntimeError.
 集成测试, 默认 run 跳过 (没 MySQL 时), 用 -m integration 才会跑.
 """
        if not _mysql_reachable():
            pytest.skip("本地 MySQL 不可达, 跳过集成测试")
        import pymysql
        from config import LocalConfig
        conn = pymysql.connect(
            host=LocalConfig.MYSQL_SERVER,
            port=LocalConfig.MYSQL_PORT,
            user="root",
            password=LocalConfig.MYSQL_PASSWORD,
            database=LocalConfig.MYSQL_DATABASE,
            connect_timeout=2,
        )
        try:
            with conn.cursor() as cur:
 cur.execute("""
 EXPLAIN SELECT * FROM interface_case_content_result
 WHERE case_result_id = 68 ORDER BY content_step
 """)
                row = cur.fetchone()
        finally:
            conn.close()
        assert row is not None
        row_str = " ".join(str(c) for c in row)
        assert "filesort" not in row_str.lower(), (
            f"[{BUG_RESULT_STEP_CACHE}] queryStepResult 路径仍有 Using filesort: {row_str}"
        )
