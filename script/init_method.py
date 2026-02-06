#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Time : 2025/7/21
# @Author : cyq
# @File : init_method
# @Software: PyCharm
# @Desc:


locator_list = [
    {
        "getter_name": "get_by_alt_text",
        "getter_desc": "通过 alt 文本定位元素（通常用于图片)",
        "getter_demo": ' <img alt="User Avatar">',

    }, {
        "getter_name": "get_by_label",
        "getter_desc": "通过关联的 label 文本定位表单元素",
        "getter_demo": """
        <label for="username">Username:</label>
        <input id="username">
       """,

    }, {
        "getter_name": "get_by_placeholder",
        "getter_desc": "通过 placeholder 属性定位输入框",
        "getter_demo": """<input placeholder="Enter your name">""",
    }, {
        "getter_name": "get_by_test_id",
        "getter_desc": "通过 data-testid 获取元素",
        "getter_demo": """
        <button data-testid="submit-button">Submit</button>
       """,
    }, {
        "getter_name": "get_by_text",
        "getter_desc": "通过文本内容定位元素",
        "getter_demo": """
        <button>Click me</button>
        <span>Welcome</span>
       """,
    }, {
        "getter_name": "get_by_title",
        "getter_desc": "通过 title 获取元素",
        "getter_demo": """
        <button title="Save changes">Save</button>
       """,

    },
]

methods_list = [  # ========== 页面操作方法 ==========
    {
        'label': "跳转页面",
        'value': "goto",
        'description': "跳转到指定URL",
        'need_locator': False,
        'need_value': True,
        'need_key': False
    },
    {
        'label': "刷新页面",
        'value': "reload",
        'description': "刷新当前页面",
        'need_locator': False,
        'need_value': False,
        'need_key': False
    },
    {
        'label': "返回上一页",
        'value': "back",
        'description': "浏览器返回上一页",
        'need_locator': False,
        'need_value': False,
        'need_key': False
    },
    {
        'label': "前进下一页",
        'value': "forward",
        'description': "浏览器前进下一页",
        'need_locator': False,
        'need_value': False,
        'need_key': False
    },
    {
        'label': "等待",
        'value': "wait",
        'description': "等待指定时间(毫秒)",
        'need_locator': False,
        'need_value': True,
        'need_key': False
    },

    # ========== 元素交互方法 ==========
    {
        'label': "点击",
        'value': "click",
        'description': "点击某个元素",
        'need_locator': True,
        'need_value': False,
        'need_key': False
    },
    {
        'label': "双击",
        'value': "dblclick",
        'description': "双击某个元素",
        'need_locator': True,
        'need_value': False,
        'need_key': False
    },
    {
        'label': "勾选",
        'value': "check",
        'description': "勾选复选框",
        'need_locator': True,
        'need_value': False,
        'need_key': False
    },
    {
        'label': "取消勾选",
        'value': "uncheck",
        'description': "取消勾选复选框",
        'need_locator': True,
        'need_value': False,
        'need_key': False
    },
    {
        'label': "清空",
        'value': "clear",
        'description': "清空输入框内容",
        'need_locator': True,
        'need_value': False,
        'need_key': False
    },
    {
        'label': "填充",
        'value': "fill",
        'description': "清空后填充输入框",
        'need_locator': True,
        'need_value': True,
        'need_key': False
    },
    {
        'label': "输入",
        'value': "type",
        'description': "追加输入文本(不清空)",
        'need_locator': True,
        'need_value': True,
        'need_key': False
    },
    {
        'label': "聚焦",
        'value': "focus",
        'description': "聚焦到某个元素",
        'need_locator': True,
        'need_value': False,
        'need_key': False
    },
    {
        'label': "失焦",
        'value': "blur",
        'description': "元素失去焦点",
        'need_locator': True,
        'need_value': False,
        'need_key': False
    },
    {
        'label': "悬停",
        'value': "hover",
        'description': "鼠标悬停在元素上",
        'need_locator': True,
        'need_value': False,
        'need_key': False
    },
    {
        'label': "按键",
        'value': "press",
        'description': "按下键盘按键",
        'need_locator': True,
        'need_value': True,
        'need_key': False
    },
    {
        'label': "选择选项(标签)",
        'value': "select_option_label",
        'description': "通过标签文本选择下拉选项",
        'need_locator': True,
        'need_value': True,
        'need_key': False
    },
    {
        'label': "选择选项(值)",
        'value': "select_option_value",
        'description': "通过value值选择下拉选项",
        'need_locator': True,
        'need_value': True,
        'need_key': False
    },
    {
        'label': "选择多个选项",
        'value': "select_option_values",
        'description': "选择多个下拉选项(逗号分隔)",
        'need_locator': True,
        'need_value': True,
        'need_key': False
    },
    {
        'label': "设置勾选",
        'value': "set_checked",
        'description': "设置为勾选状态",
        'need_locator': True,
        'need_value': False,
        'need_key': False
    },
    {
        'label': "设置未勾选",
        'value': "set_unchecked",
        'description': "设置为未勾选状态",
        'need_locator': True,
        'need_value': False,
        'need_key': False
    },
    {
        'label': "上传文件",
        'value': "upload",
        'description': "上传文件(xlsx/png)",
        'need_locator': True,
        'need_value': True,
        'need_key': False
    },

    # ========== 数据提取方法 ==========
    {
        'label': "获取数量",
        'value': "count",
        'description': "获取元素数量并存储到变量",
        'need_locator': True,
        'need_value': False,
        'need_key': True
    },
    {
        'label': "获取属性",
        'value': "get_attribute",
        'description': "获取元素属性值",
        'need_locator': True,
        'need_value': True,
        'need_key': True
    },
    {
        'label': "获取内部文本",
        'value': "get_inner_text",
        'description': "获取元素innerText",
        'need_locator': True,
        'need_value': False,
        'need_key': True
    },
    {
        'label': "获取输入值",
        'value': "get_input_value",
        'description': "获取输入框的值",
        'need_locator': True,
        'need_value': True,
        'need_key': False
    },
    {
        'label': "获取文本内容",
        'value': "get_text_content",
        'description': "获取元素textContent",
        'need_locator': True,
        'need_value': False,
        'need_key': True
    },
    {
        'label': "执行脚本",
        'value': "evaluate",
        'description': "执行JavaScript表达式",
        'need_locator': True,
        'need_value': True,
        'need_key': False
    },

    # ========== 断言方法 ==========
    {
        'label': "断言已勾选",
        'value': "expect.to_be_checked",
        'description': "断言元素处于勾选状态",
        'need_locator': True,
        'need_value': False,
        'need_key': False
    },
    {
        'label': "断言已禁用",
        'value': "expect.to_be_disabled",
        'description': "断言元素处于禁用状态",
        'need_locator': True,
        'need_value': False,
        'need_key': False
    },
    {
        'label': "断言可编辑",
        'value': "expect.to_be_editable",
        'description': "断言元素可编辑",
        'need_locator': True,
        'need_value': False,
        'need_key': False
    },
    {
        'label': "断言为空",
        'value': "expect.to_be_empty",
        'description': "断言元素内容为空",
        'need_locator': True,
        'need_value': False,
        'need_key': False
    },
    {
        'label': "断言已启用",
        'value': "expect.to_be_enabled",
        'description': "断言元素处于启用状态",
        'need_locator': True,
        'need_value': False,
        'need_key': False
    },
    {
        'label': "断言已聚焦",
        'value': "expect.to_be_focused",
        'description': "断言元素处于聚焦状态",
        'need_locator': True,
        'need_value': False,
        'need_key': False
    },
    {
        'label': "断言已隐藏",
        'value': "expect.to_be_hidden",
        'description': "断言元素处于隐藏状态",
        'need_locator': True,
        'need_value': False,
        'need_key': False
    },
    {
        'label': "断言页面标题",
        'value': "expect.url_title",
        'description': "断言页面标题等于期望值",
        'need_locator': False,
        'need_value': True,
        'need_key': False
    },
]


async def init_play_method():
    """
    初始化UI 方法API入库
    """
    from app.mapper.play.playConfigMapper import PlayMethodMapper
    from utils import log
    if await PlayMethodMapper.query_all():
        return
    await PlayMethodMapper.init_play_methods(methods_list)
    log.info("init play methods success")



async def init_play_locator():
    """
    初始化UI 方法API入库
    """
    from app.mapper.play.playConfigMapper import PlayLocatorMapper
    from utils import log
    if await PlayLocatorMapper.query_all():
        return
    await PlayLocatorMapper.init_play_locators(locator_list)
    log.info("init play locators success")

