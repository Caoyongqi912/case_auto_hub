"""
子步骤 cell 序列化: 把步骤列表拼到 Excel 单 cell 多步文本.

格式约定与 utils/aioFileReader 的上传解析保持对称:
  - 0 步: 整 cell 为空
  - 1 步: 整 cell = 单条文本, 不加 "【1】" 前缀
  - N 步: "【1】xxx\n【2】yyy\n【3】zzz"

导入方向的 parse_steps_cell 见 PR-2 import 链路, 暂不在本文件.
"""

from typing import Dict, List


def format_steps_cell(steps: List[Dict], field: str) -> str:
    """
    把步骤列表中指定字段拼到 Excel 单 cell.

    :param steps: 步骤字典列表 (按 order 升序), 每项至少含 {order, field}
    :param field:  要拼的字段名, "action" 或 "expected_result"
    :return: cell 文本; 0 步返回 ""
    """
    if not steps:
        return ""

    if len(steps) == 1:
        return (steps[0].get(field) or "").strip()

    return "\n".join(
        f"【{step.get('order', idx + 1)}】{(step.get(field) or '').strip()}"
        for idx, step in enumerate(steps)
    )
