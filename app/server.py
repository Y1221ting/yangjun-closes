"""本地 HTTP 服务。

职责：
1. 提供 web/ 下的前端静态文件
2. 提供 data/ 下的图片等资源
3. 提供 /api/* 的 JSON 接口（路由见 app/router.py）

只监听 127.0.0.1，端口由系统随机分配，避免与其他程序冲突。
所有接口统一返回 {"ok": true, "data": ...} 或 {"ok": false, "error": "中文提示"}。
"""

from __future__ import annotations

import json
import mimetypes
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

from .api import build_router
from .config import DATA_DIR, HOST, MAX_UPLOAD_BYTES, WEB_DIR
from .errors import ServiceError
from .router import Request
from .utils import logger

# 补充 Windows 上可能缺失的 MIME 类型
mimetypes.add_type("image/webp", ".webp")
mimetypes.add_type("font/ttf", ".ttf")
mimetypes.add_type("application/javascript", ".js")

_TEXT_TYPES = {"application/javascript", "application/json"}
ROUTER = build_router()


class WardrobeHandler(BaseHTTPRequestHandler):
    """处理全部 HTTP 请求。"""

    server_version = "Wardrobe/0.1"
    protocol_version = "HTTP/1.1"

    # ---------------------------------------------------------------- 方法

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = unquote(parsed.path)
        if path.startswith("/api/"):
            self._dispatch("GET", path, parsed.query, b"")
            return
        self._serve_static(path)

    def do_POST(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = unquote(parsed.path)
        body = self._read_body()
        if body is None:
            return
        self._dispatch("POST", path, parsed.query, body)

    def do_PUT(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = unquote(parsed.path)
        body = self._read_body()
        if body is None:
            return
        self._dispatch("PUT", path, parsed.query, body)

    def do_DELETE(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = unquote(parsed.path)
        self._dispatch("DELETE", path, parsed.query, b"")

    # ---------------------------------------------------------------- 接口

    def _dispatch(self, method: str, path: str, query_string: str, body: bytes) -> None:
        query = {key: values[0] for key, values in parse_qs(query_string).items()}
        handler, params = ROUTER.match(method, path)
        if handler is None:
            self._send_json({"ok": False, "error": "接口不存在"}, status=404)
            return

        request = Request(
            method=method,
            path=path,
            query=query,
            headers=dict(self.headers),
            body=body,
            params=params,
        )
        try:
            status, payload = handler(request)
        except ServiceError as exc:
            logger.info("%s %s 业务错误：%s", method, path, exc)
            self._send_json({"ok": False, "error": str(exc)}, status=400)
        except Exception:  # noqa: BLE001 - 兜底，避免连接被直接断开
            logger.exception("接口异常 %s %s", method, path)
            self._send_json({"ok": False, "error": "服务器内部错误，请查看日志"}, status=500)
        else:
            self._send_json(payload, status=status)

    # ---------------------------------------------------------------- 静态文件

    def _serve_static(self, path: str) -> None:
        if path == "/":
            self._send_file(WEB_DIR / "index.html")
            return
        if path.startswith("/data/"):
            self._send_from(DATA_DIR, path[len("/data/"):])
            return
        self._send_from(WEB_DIR, path.lstrip("/"))

    def _send_from(self, root: Path, relative: str) -> None:
        target = self._safe_path(root, relative)
        if target is None:
            self._send_json({"ok": False, "error": "禁止访问"}, status=403)
            return
        self._send_file(target)

    def _send_file(self, target: Path) -> None:
        if not target.is_file():
            self._send_json({"ok": False, "error": "文件不存在"}, status=404)
            return
        try:
            data = target.read_bytes()
        except OSError:
            logger.exception("读取文件失败: %s", target)
            self._send_json({"ok": False, "error": "读取文件失败"}, status=500)
            return

        content_type = mimetypes.guess_type(str(target))[0] or "application/octet-stream"
        if content_type.startswith("text/") or content_type in _TEXT_TYPES:
            content_type += "; charset=utf-8"

        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(data)

    # ---------------------------------------------------------------- 工具

    def _send_json(self, payload: dict, status: int = 200) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _read_body(self) -> bytes | None:
        """读取请求体；超过上限时返回 None 并已发送错误响应。"""
        raw_length = self.headers.get("Content-Length")
        try:
            length = int(raw_length) if raw_length else 0
        except ValueError:
            length = 0

        if length > MAX_UPLOAD_BYTES:
            self.close_connection = True
            self._send_json(
                {"ok": False, "error": "文件太大，单张图片不能超过 20MB"}, status=413
            )
            return None
        if length <= 0:
            return b""
        return self.rfile.read(length)

    @staticmethod
    def _safe_path(root: Path, relative: str) -> Path | None:
        """拼接路径并防止目录穿越（../）。"""
        try:
            target = (root / relative).resolve()
            target.relative_to(root.resolve())
        except (ValueError, OSError):
            return None
        return target

    def log_message(self, fmt: str, *args) -> None:
        logger.debug("%s - %s", self.address_string(), fmt % args)


class WardrobeServer(ThreadingHTTPServer):
    """带 daemon 线程的 HTTP 服务，便于随窗口退出。"""

    daemon_threads = True
    allow_reuse_address = True


def start_server() -> tuple[WardrobeServer, int]:
    """在后台线程启动服务，返回 (服务实例, 端口号)。"""
    httpd = WardrobeServer((HOST, 0), WardrobeHandler)
    port = httpd.server_address[1]
    thread = threading.Thread(target=httpd.serve_forever, name="http-server", daemon=True)
    thread.start()
    logger.info("本地服务已启动 http://%s:%s", HOST, port)
    return httpd, port
