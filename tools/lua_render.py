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


_LUA_KEYWORDS = frozenset(
    "and break do else elseif end false for function goto if in local nil not or repeat return then true until while".split()
)


def _is_lua_name(key: str) -> bool:
    return (
        bool(key)
        and (key[0].isalpha() or key[0] == "_")
        and all(ch.isalnum() or ch == "_" for ch in key)
        and key.isascii()
        and key not in _LUA_KEYWORDS
    )


def to_lua_compact(value: Any) -> str:
    """Same data as to_lua, without indentation or newlines and with bare
    identifier keys where Lua allows them. The game loads the generated files
    at login and they are size-limited, so whitespace is not worth its bytes."""
    if value is None:
        return "nil"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, list):
        return "{" + ",".join(to_lua_compact(item) for item in value) + "}"
    if isinstance(value, dict):
        parts = []
        for key in sorted(value, key=str):
            name = str(key)
            lua_key = name if _is_lua_name(name) else f"[{json.dumps(name, ensure_ascii=False)}]"
            parts.append(f"{lua_key}={to_lua_compact(value[key])}")
        return "{" + ",".join(parts) + "}"
    raise TypeError(f"Unsupported type: {type(value)}")
