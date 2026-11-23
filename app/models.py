"""数据库行与接口字典之间的转换。"""

from __future__ import annotations

import json
import sqlite3
from typing import Any

JSON_FIELDS = {"seasons", "occasions", "scenes"}


def row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    """把一行数据转成字典，并解析 JSON 字段。"""
    data = dict(row)
    for field in JSON_FIELDS & data.keys():
        raw = data[field]
        try:
            data[field] = json.loads(raw) if raw else []
        except (TypeError, ValueError):
            data[field] = []
    return data


def rows_to_dicts(rows: list[sqlite3.Row]) -> list[dict[str, Any]]:
    """批量转换。"""
    return [row_to_dict(row) for row in rows]


def dump_list(values: list[str] | None) -> str:
    """列表转 JSON 字符串，统一用中文不转义。"""
    return json.dumps(values or [], ensure_ascii=False)
