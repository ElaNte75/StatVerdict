"""Renders Python data as a Lua table constructor for the generated addon files."""
from __future__ import annotations

import json
from typing import Any


def to_lua(value: Any, indent: int = 0) -> str:
    pad = "    " * indent
    child = "    " * (indent + 1)
    if value is None:
        return "nil"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, list):
        if not value:
            return "{}"
        return "{\n" + "\n".join(f"{child}{to_lua(item, indent + 1)}," for item in value) + f"\n{pad}}}"
    if isinstance(value, dict):
        if not value:
            return "{}"
        rows = []
        for key in sorted(value, key=str):
            rows.append(f"{child}[{json.dumps(str(key), ensure_ascii=False)}] = {to_lua(value[key], indent + 1)},")
        return "{\n" + "\n".join(rows) + f"\n{pad}}}"
    raise TypeError(f"Unsupported type: {type(value)}")
