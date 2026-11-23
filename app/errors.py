"""业务异常。

约定：ServiceError 的消息会直接展示给用户，必须是中文、可读、可操作。
"""

from __future__ import annotations


class ServiceError(Exception):
    """业务异常：消息会原样返回给前端展示。"""


class ValidationError(ServiceError):
    """参数校验失败。"""


class NotFoundError(ServiceError):
    """资源不存在。"""


class ConflictError(ServiceError):
    """资源冲突，例如重复上传同一角度。"""
