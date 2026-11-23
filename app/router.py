"""极简路由器：支持 /api/garments/{id} 形式的路径参数。

不依赖任何 Web 框架，只做正则匹配与参数提取。
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Callable

from .errors import ValidationError


@dataclass
class Request:
    """一次接口请求。"""

    method: str
    path: str
    query: dict[str, str]
    headers: dict[str, str]
    body: bytes
    params: dict[str, str] = field(default_factory=dict)

    def json(self) -> dict:
        """把请求体解析成 JSON 对象。"""
        if not self.body:
            return {}
        try:
            data = json.loads(self.body.decode("utf-8"))
        except (UnicodeDecodeError, ValueError) as exc:
            raise ValidationError("请求内容格式不正确") from exc
        if not isinstance(data, dict):
            raise ValidationError("请求内容必须是 JSON 对象")
        return data


Handler = Callable[[Request], tuple[int, dict]]


def _compile(pattern: str) -> re.Pattern[str]:
    """把 /api/x/{id} 编译成带命名组的正则。"""
    pieces: list[str] = []
    for part in re.split(r"(\{\w+\})", pattern):
        matched = re.fullmatch(r"\{(\w+)\}", part)
        if matched:
            pieces.append(f"(?P<{matched.group(1)}>[^/]+)")
        else:
            pieces.append(re.escape(part))
    return re.compile("^" + "".join(pieces) + "$")


class Router:
    """按 (方法, 路径) 匹配处理函数。"""

    def __init__(self) -> None:
        self._routes: list[tuple[str, re.Pattern[str], Handler]] = []

    def get(self, pattern: str):
        return self._register("GET", pattern)

    def post(self, pattern: str):
        return self._register("POST", pattern)

    def put(self, pattern: str):
        return self._register("PUT", pattern)

    def delete(self, pattern: str):
        return self._register("DELETE", pattern)

    def _register(self, method: str, pattern: str):
        regex = _compile(pattern)

        def decorator(handler: Handler) -> Handler:
            self._routes.append((method, regex, handler))
            return handler

        return decorator

    def match(self, method: str, path: str) -> tuple[Handler | None, dict[str, str]]:
        """返回 (处理函数, 路径参数)，未匹配时处理函数为 None。"""
        for route_method, regex, handler in self._routes:
            if route_method != method:
                continue
            matched = regex.match(path)
            if matched:
                return handler, matched.groupdict()
        return None, {}
