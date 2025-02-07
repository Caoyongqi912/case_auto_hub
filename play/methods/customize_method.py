import inspect
from playwright.async_api import Page

from app.model.ui import UICaseStepsModel
from play.extract import ExtractManager
from play.methods.page_methods import PageMethods

from play.upload_files import png, xlsx
from utils.io_sender import SocketSender
from utils import MyLoguru

log = MyLoguru().get_logger()


class CustomizeMethod:
    """
    Page Method
    """

    @staticmethod
    async def invoke(page: Page, step: UICaseStepsModel, io: SocketSender, em: ExtractManager):
        """
        执行方法
        :param page:
        :param step:
        :param io:SocketSender
        :param em:ExtractManager
        :return:
        """
        try:
            await getattr(CustomizeMethod, step.method)(page, step, io, em)

        except Exception as e:
            raise e

    @staticmethod
    async def wait(page: Page, step: UICaseStepsModel, io: SocketSender, em: ExtractManager):
        """
        执行方法
        :param page:
        :param step:
        :param io:SocketSender
        :param em:ExtractManager
        :return:
        """
        try:
            await io.send(f"wait {step.value} ...")
            await page.wait_for_timeout(float(step.value))
        except Exception as e:
            raise e

    @staticmethod
    async def get_attr(page: Page, step: UICaseStepsModel, io: SocketSender, em: ExtractManager):
        """
        获取locator上的属性
        :param page:
        :param step:
        :param io: SocketSender
        :param em:ExtractManager
        :return:
        """
        try:
            try:
                name, value = step.value.split(";")
            except Exception:
                await io.send(f"提取变量失败 ⚠️ :{step.value}")
                raise Exception(f"提取变量失败 ⚠️ :{step.value}")
            locator = await PageMethods.get_locator(page, step)
            attr = await locator.get_attribute(name)
            if attr:
                tempVariable = {
                    value.strip(): attr.strip()
                }
                await io.send(f"提取变量 ✅ {tempVariable}")
                await em.add_var(key=step.value.strip(), value=attr.strip())

        except Exception as e:
            raise e

    @staticmethod
    async def get_text(page: Page, step: UICaseStepsModel, io: SocketSender, em: ExtractManager):
        """
        获取locator上的文案
        :param page:
        :param step:
        :param io:SocketSender
        :param em:ExtractManager
        :return:
        """
        try:
            if step.value:
                locator = await PageMethods.get_locator(page, step)
                text = await locator.text_content()
                tempVariable = {
                    step.value.strip(): text.strip()
                }
                await io.send(f"提取变量 ✅ {tempVariable}")
                await em.add_var(key=step.value.strip(), value=text.strip())
            else:
                pass
        except Exception as e:
            raise e

    @staticmethod
    async def upload_file(page: Page, step: UICaseStepsModel, io: SocketSender, **kwargs):
        """
        上传文件
        :param page:
        :param step:
        :param io:SocketSender
        :return:
        """
        try:
            locator = await PageMethods.get_locator(page, step)
            if step.value == "xlsx":
                await locator.set_input_files(xlsx)
            else:
                await locator.set_input_files(png)
            await io.send("上传附件 ✅")
        except Exception as e:
            raise e

    @staticmethod
    async def to_reload(page: Page, **kwargs):
        """
        页面刷新
        :param page:
        :return:
        """
        await page.reload()

    @staticmethod
    async def to_fill(page: Page, step: UICaseStepsModel,
                      io: SocketSender, em: ExtractManager):
        """
        输入方法特殊处理
        fill 前 先清空
        查询变量提取。进行替换
        :param page:Page
        :param step:UICaseStepsModel
        :param io:SocketSender
        :param em:ExtractManager
        :return:
        """
        try:
            locator = await PageMethods.get_locator(page, step)
            # 找到元素方法
            fill_value = await em.transform_target(step.value)
            await io.send(f"输入 >> {fill_value}")
            await locator.fill(str(fill_value))
        except Exception as e:
            raise e

    @staticmethod
    async def to_evaluate(page: Page, step: UICaseStepsModel,
                          io: SocketSender, **kwargs):
        """
        执行js
        :param page:
        :param io:SocketSender
        :param step: UICaseStepsModel
        :return:
        """
        try:

            result = await page.evaluate(step.value)
            await io.send(f">> evaluate:  '{step.value}' result: {result}")
        except Exception as e:
            raise e

    @staticmethod
    async def to_wait(page: Page, step: UICaseStepsModel,
                      io: SocketSender, **kwargs):
        """
        等一会
        :param page:
        :param step:
        :param io
        :return:
        """
        try:
            await page.wait_for_timeout(float(step.value))
            await io.send(f"wait_for_timeout  {step.value} done")
        except Exception as e:
            raise e

    @staticmethod
    async def to_goto(page: Page, step: UICaseStepsModel | str,
                      io: SocketSender,
                      em: ExtractManager):
        """

        :param page:Page
        :param step: 跳转
        :param io: SocketSender
        :param em:ExtractManager
        :return:

        """
        if isinstance(step, str):
            url = await em.transform_target(step)
        else:
            url = await em.transform_target(step.value)
        await io.send(f"执行 >> 打开地址:'{url}'")
        try:
            await page.goto(url, wait_until="load")
            await page.wait_for_load_state()
        except Exception as e:
            log.error(f"An error occurred: {e}")
            raise e


CustomizeMethods = [name for name, member in inspect.getmembers(CustomizeMethod, predicate=inspect.isfunction)]
