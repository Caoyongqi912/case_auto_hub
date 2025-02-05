#!/usr/bin/env python# -*- coding:utf-8 -*-# @Time : 2024/7/5# @Author : cyq# @File : extract# @Software: PyCharm# @Desc:import asynciofrom typing import Any, Dict, Listimport refrom app.model.ui import UIVariablesModelfrom play.execFunc import ExecFuncManagerfrom utils import logclass ExtractManager:    def __init__(self):        self.variables = {}    async def clear(self):        self.variables = {}    async def add_vars(self, varDict: Dict[str, Any]):        self.variables.update(**varDict)    async def add_var(self, key: str, value: Any):        self.variables[key] = value    async def initBeforeVars(self, variables: List[UIVariablesModel]):        """        提取前置变量        """        var_map = {}        for var in variables:            if var.value.startswith("${"):                await self._transformFuncStr(var)            else:                var_map[var.key] = var.value        self.variables.update(var_map)    async def _transformFuncStr(self, var: "UIVariablesModel"):        """        方法处理        :param var:        :return:        """        funcStr = re.findall(r"\$\{(.*?)\}", var.value)        if funcStr:            funcStr = funcStr[0]        try:            from play.execFunc import ExecFuncManager            ex = ExecFuncManager(funcStr, var.key)            obj = ex.execFunc()            self.variables.update(obj)        except Exception as e:            log.error(e)    async def transform_target(self, target: Any):        """        参数转换        数据转换        """        # 如果单纯字符串        if isinstance(target, str):            return await self._transformStr(target)        # 如果是字典        if isinstance(target, dict):            return await self._transFormObj(target)        # 如果是列表        if isinstance(target, list):            return await self._transFormList(target)    async def _transformStr(self, target: str) -> str:        """        字符串替换        """        if target.startswith("{{") and target.endswith("}}"):            extractKey = target[2:-2]            if extractKey in self.variables:                newValue = self.variables[extractKey]                return newValue            else:                return target        elif target.startswith("${"):            funcStr = re.findall(r"\$\{(.*?)\}", target)            if funcStr:                funcStr = funcStr[0]            ex = ExecFuncManager(funcStr, "KEY")            obj = ex.execFunc()            return obj.get("KEY")        else:            pattern = r"{{(.*?)}}"            newValue = re.sub(pattern, lambda match: str(self.variables.get(match.group(1), "")), target)            return newValue    async def _transFormObj(self, target: Dict[str, Any]) -> Dict[str, Any]:        """        字典替换        :param target        """        transformed_target = {}        for key, value in target.items():            # 如果value是字符串            if isinstance(value, str):                newValue = await self._transformStr(value)                transformed_target[key] = newValue            # 如果还是字典            elif isinstance(value, dict):                newObj = await self._transFormObj(value)                transformed_target[key] = newObj            # 如果是列表            elif isinstance(value, list):                newList = await self._transFormList(value)                transformed_target[key] = newList            else:                transformed_target[key] = value        return transformed_target    async def _transFormList(self, target: List[Any]) -> List[Any]:        """        列表替换        """        transformed_list = []        for i in target:            if isinstance(i, str):                newValue = await self._transformStr(i)                transformed_list.append(newValue)            elif isinstance(i, dict):                transformed_list.append(await self._transFormObj(i))            elif isinstance(i, list):                transformed_list.append(await self._transFormList(i))            else:                transformed_list.append(i)        return transformed_listasync def test():    extractManager = ExtractManager(1)    await extractManager.add_var("a", "1")    await extractManager.add_var("b", "${{{a}} +1}")    data = await extractManager.transform_target("${a + 1}")    print(data)if __name__ == '__main__':    asyncio.run(test())