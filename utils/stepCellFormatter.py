"""
子步骤 cell 序列化: 把步骤列表拼到 Excel 单 cell 多步文本.

格式约定与 utils/aioFileReader 的上传解析保持对称:
  - 0 步: 整 cell 为空
  - 1 步: 整 cell = 单条文本
  - N 步: "xxx\nyyy\nzzz" (按行拼, 不加 "【x】" 前缀, DB 存什么就写什么)

重构: 导出去掉 "【x】" 前缀. 原因是入库侧已统一用 _parse_steps 系列的
_clean_line 剥离前缀 (DB 存的是清洗后的纯文本), 导出再补前缀会形成
"【1】【1】xxx" 双重前缀. 现在 "步骤是什么就导出什么", 入库 -> 导出链路零中间态.

导入方向的 parse_steps_cell 见 _parse_steps (testcaseMapper 内的 M1 实现 +
m2ImportService 内的 M2 实现), 暂不抽到本文件 (M1 0 步骤返回 [{}] vs
M2 0 步骤返回 [] 的行为差异保留在调用方).
"""

from typing import Dict, List


def format_steps_cell(steps: List[Dict], field: str) -> str:
    """
    把步骤列表中指定字段拼到 Excel 单 cell.

    PR-3: 步骤是啥就导出啥, 不加 "【x】" 前缀. 0 步 -> "", 1 步 -> 单条文本,
    N 步 -> "\n" 拼接. 跟入库侧 _clean_line 清洗对称, 避免双重前缀.

    :param steps: 步骤字典列表 (按 order 升序), 每项至少含 {order, field}
    :param field:  要拼的字段名, "action" 或 "expected_result"
    :return: cell 文本; 0 步返回 ""
    """
    if not steps:
        return ""

    return "\n".join(
        (step.get(field) or "").strip()
        for step in steps
    )
