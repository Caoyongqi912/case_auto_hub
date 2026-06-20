#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Time : 2025/5/25
# @Author : cyq
# @File : uploadCacheService
# @Software: PyCharm
# @Desc: 上传文件缓存服务

import json
from typing import Dict, Any, List, Literal, Optional
from dataclasses import asdict

from common import RedisClient
from utils import log

UPLOAD_CACHE_PREFIX = "upload:case:"
UPLOAD_CACHE_EXPIRES = 1800

# PR-3: 模板类型. 缓存里跟响应保持一致, M2 commit 阶段做防御性校验.
TemplateTypeLiteral = Literal["M1", "M2"]


class UploadCacheService:
    def __init__(self, redis_client: RedisClient):
        self.redis = redis_client
        self.prefix = UPLOAD_CACHE_PREFIX
        self.expires = UPLOAD_CACHE_EXPIRES

    def _get_key(self, file_md5: str, user_id: int) -> str:
        return f"{self.prefix}{user_id}:{file_md5}"

    async def save_preview(
            self,
            file_md5: str,
            user_id: int,
            valid_cases: List[Dict[str, Any]],
            errors: List[Dict[str, Any]],
            total_count: int,
            *,
            # 导回 (PR-2+) 用的额外字段, 老调用方不传, 新调用方走 valid_rows / meta / scope_check
            valid_rows: Optional[List[Dict[str, Any]]] = None,
            meta: Optional[Dict[str, str]] = None,
            scope_check: Optional[Dict[str, Any]] = None,
            warnings: Optional[List[Dict[str, Any]]] = None,
            # PR-3 新增: 模板类型. 走 /upload 时 controller 显式传 M1/M2, 老调用方
            # (如 /upload 老版本) 不传, 缓存里缺省 None, M2 commit 阶段会拒绝.
            template_type: Optional[TemplateTypeLiteral] = None,
    ) -> bool:
        key = self._get_key(file_md5, user_id)
        cache_data = {
            "file_md5": file_md5,
            "user_id": user_id,
            "valid_cases": valid_cases,
            "errors": errors,
            "total_count": total_count,
            "valid_rows": valid_rows or [],
            "meta": meta or {},
            "scope_check": scope_check or {},
            "warnings": warnings or [],
            # PR-3: 缓存层存 template_type, M2 commit 阶段靠它做防御性校验
            # (防止 M1 缓存误走 /import/commit 端点).
            "template_type": template_type,
        }
        try:
            await self.redis.r.set(key, json.dumps(cache_data), ex=self.expires)
            log.info(
                f"保存预览缓存成功: {key}, 有效用例: {len(valid_cases)}, "
                f"valid_rows: {len(valid_rows or [])}, 错误: {len(errors)}"
            )
            return True
        except Exception as e:
            log.exception(f"保存预览缓存失败: {key}, error: {e}")
            return False

    async def get_preview(self, file_md5: str, user_id: int) -> Optional[Dict[str, Any]]:
        key = self._get_key(file_md5, user_id)
        try:
            data = await self.redis.r.get(key)
            if data:
                return json.loads(data)
            return None
        except Exception as e:
            log.exception(f"获取预览缓存失败: {key}, error: {e}")
            return None

    async def exists(self, file_md5: str, user_id: int) -> bool:
        key = self._get_key(file_md5, user_id)
        return await self.redis.r.exists(key) > 0

    async def delete(self, file_md5: str, user_id: int) -> bool:
        key = self._get_key(file_md5, user_id)
        try:
            await self.redis.r.delete(key)
            log.info(f"删除预览缓存: {key}")
            return True
        except Exception as e:
            log.exception(f"删除预览缓存失败: {key}, error: {e}")
            return False

    async def mark_committed(self, file_md5: str, user_id: int) -> bool:
        key = self._get_key(file_md5, user_id)
        try:
            data = await self.get_preview(file_md5, user_id)
            if data:
                data["committed"] = True
                await self.redis.r.set(key, json.dumps(data), ex=self.expires)
                return True
            return False
        except Exception as e:
            log.exception(f"标记已提交失败: {key}, error: {e}")
            return False

    async def is_committed(self, file_md5: str, user_id: int) -> bool:
        data = await self.get_preview(file_md5, user_id)
        if data:
            return data.get("committed", False)
        return False