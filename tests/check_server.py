"""阶段 0 自检：不打开窗口，只验证 HTTP 服务与静态文件。

用法：.venv/Scripts/python.exe tests/check_server.py
"""

from __future__ import annotations

import sys
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.server import start_server  # noqa: E402
from app.utils import ensure_dirs, setup_logging  # noqa: E402

PATHS = [
    ("/api/health", 200),
    ("/", 200),
    ("/css/variables.css", 200),
    ("/css/base.css", 200),
    ("/js/boot.js", 200),
    ("/api/not-found", 404),
    ("/../main.py", 403),
]


def main() -> int:
    setup_logging()
    ensure_dirs()
    httpd, port = start_server()
    base = f"http://127.0.0.1:{port}"
    failures = 0

    try:
        for path, expected in PATHS:
            url = base + path
            try:
                with urllib.request.urlopen(url, timeout=5) as resp:
                    status = resp.status
                    size = len(resp.read())
            except urllib.error.HTTPError as exc:
                status = exc.code
                size = 0
            ok = status == expected
            failures += 0 if ok else 1
            mark = "PASS" if ok else "FAIL"
            print(f"[{mark}] {status} (期望 {expected}) {path}  {size} bytes")
    finally:
        httpd.shutdown()
        httpd.server_close()

    print(f"\n结果：{'全部通过' if failures == 0 else f'{failures} 项失败'}")
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
