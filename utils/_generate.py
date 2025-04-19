#!/usr/bin/env python# -*- coding:utf-8 -*-# @Time : 2024/6/6# @Author : cyq# @File : _generate# @Software: PyCharm# @Desc:from typing import List, Any, Dictfrom uuid import uuid4from datetime import datetime, timedeltaimport timeclass KVItem:    KEY = "key"    VALUE = "value"class GenerateTools:    @classmethod    def uid(cls) -> str:        """        生成uuid        :return: uuid4        """        return str(uuid4())[:8]    @staticmethod    def list2dict(items: List[dict[str, Any]] | None = None) -> Dict[str, Any]:        return {item[KVItem.KEY]: item.get(KVItem.VALUE) for item in items if                item.get(KVItem.KEY) and item.get(KVItem.VALUE)}    @staticmethod    def getTime(detail: int):        """       获取当前时间       :param detail:            1:%Y-%m-%d %H:%M:%S            2:%Y-%m-%d            3:timeStamp            4:%H:%M:%S            5:%Y-%m-%d            6:%Y%m%d_%H%M%S       :return:time       """        if detail == 3:            return int(time.time()) * 1000        opt = {1: "%Y-%m-%d %H:%M:%S",               2: '%Y-%m-%d',               5: "%Y-%m-%d",               4: "%H:%M:%S",               6: "%Y%m%d%H%M%S",               }        return datetime.now().strftime(opt[detail])    @staticmethod    def timeDiff(sTime: datetime, eTime: datetime):        """        计算时间差        :param sTime:        :param eTime:        :return:        """        time_diff = eTime - sTime        hours, remainder = divmod(time_diff.seconds, 3600)        minutes, seconds = divmod(remainder, 60)        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"    @staticmethod    def getYesterday(day=7):        """        获取过去{day}天        :return:        """        today = datetime.today()        yesterday = today - timedelta(days=day)        yesterday_str = yesterday.strftime("%Y-%m-%d")        return yesterday_str    @staticmethod    def start_of_week():        """        """        today = datetime.today()  # 获取今天的日期和时间        start_of_week = today - timedelta(days=today.weekday())  # 计算本周的开始日期（周一）        start_of_week_date = start_of_week.date()  # 获取日期部分        return start_of_week_date    @staticmethod    def getMonthFirst() -> str:        """        获取当月1号        :return:        """        current_date = datetime.now()        # 构造当月1号日期        first_day_of_month = current_date.replace(day=1)        return first_day_of_month.strftime("%Y-%m-%d")    @staticmethod    def getYear():        return datetime.now().year    @staticmethod    def get_date_days_ago(days=7):        today = datetime.today()        seven_days_ago = today - timedelta(days=days)        return seven_days_ago.strftime('%Y-%m-%d')if __name__ == '__main__':    print(GenerateTools.get_date_days_ago(0))