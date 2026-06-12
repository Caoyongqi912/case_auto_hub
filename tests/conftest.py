"""pytest 公共 fixture / 配置"""
import sys
import pathlib

# 让 pytest 能 import app/ utils/
ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
