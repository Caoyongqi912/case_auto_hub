"""
全局 pytest fixtures。

约定:
- unit 测试不需要 DB,完全 mock
- integration 测试需要真实的 MySQL + Redis
"""
import os
import sys
from pathlib import Path

# 把项目根加入 sys.path,确保 `import croe` 等能找到
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


# 默认环境:单元测试不连真实 DB
os.environ.setdefault("CONFIG", "test")


import pytest
from unittest.mock import AsyncMock, MagicMock


@pytest.fixture
def mock_session():
    """返回一个 AsyncMock 的 SQLAlchemy AsyncSession。"""
    session = AsyncMock()
    session.__aenter__ = AsyncMock(return_value=session)
    session.__aexit__ = AsyncMock(return_value=None)
    return session


@pytest.fixture
def mock_starter():
    """Mock APIStarter,send/over 都是 AsyncMock。"""
    starter = MagicMock()
    starter.send = AsyncMock()
    starter.over = AsyncMock()
    starter.logs = []
    starter.userId = 1
    starter.username = "tester"
    starter.uid = "test-uid"
    starter.startBy = 1
    return starter
