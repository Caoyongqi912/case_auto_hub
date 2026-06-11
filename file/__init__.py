import os.path

current_dir = os.path.dirname(__file__)

# 用例导入的空模板, downloadCaseDemo 接口直接 FileResponse 返回
TestCaseDemoFile = os.path.join(current_dir, "用例模版.xlsx")
