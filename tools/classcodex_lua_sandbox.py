"""Hardened embedded-Lua execution for third-party ClassCodex data files.

Ported from the abandoned Scraper repo (github.com/ElaNte75/Scraper), whose
lua_bridge.py/builder_runtime.py already went through a security review that
found two real sandbox escapes with lupa's defaults:

1. lupa injects a `python` global exposing `python.eval(...)` unless the
   runtime is constructed with register_eval=False/register_builtins=False.
2. Lua can read attributes on any live Python object it holds (e.g. a
   callable's own __globals__), reaching __builtins__/__import__ regardless
   of which globals have been nilled out.

Both are closed by constructing the LuaRuntime with an attribute_filter that
denies everything, plus the two register_* flags -- at construction time, not
after the fact. None of the data files this module loads need Python
attribute access or eval; they only ever assign nested Lua tables (plain
globals) or, for addon Shared/*.lua modules, populate a namespace table
passed in as the addon's `...` varargs.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import lupa

DANGEROUS_GLOBALS = ("os", "io", "require", "dofile", "loadfile", "loadstring", "package", "python")


def _deny_python_attribute_access(obj: Any, attr_name: str, is_setting: bool) -> None:
    raise AttributeError("attribute access to Python objects is disabled in this runtime")


def to_python(value: Any) -> Any:
    """Recursively convert a lupa table into plain dict/list/scalar values."""
    if hasattr(value, "keys") and hasattr(value, "values"):
        keys = list(value.keys())
        if keys and all(isinstance(k, int) for k in keys) and sorted(keys) == list(range(1, len(keys) + 1)):
            return [to_python(value[i]) for i in range(1, len(keys) + 1)]
        return {k: to_python(v) for k, v in zip(value.keys(), value.values())}
    return value


def new_sandboxed_runtime() -> "lupa.LuaRuntime":
    """A fresh runtime with no filesystem/process/module-loading access and
    no path back into the Python side. `load` itself is intentionally left
    in place -- callers need it to compile the fetched source text -- but
    every other dangerous global is removed immediately after construction."""
    runtime = lupa.LuaRuntime(
        unpack_returned_tuples=True,
        register_eval=False,
        register_builtins=False,
        attribute_filter=_deny_python_attribute_access,
    )
    g = runtime.globals()
    for name in DANGEROUS_GLOBALS:
        g[name] = None
    return runtime


class LuaSourceError(RuntimeError):
    pass


def _compile(runtime: "lupa.LuaRuntime", source: str, chunk_name: str):
    load = runtime.globals()["load"]
    loaded = load(source, chunk_name)
    chunk, error = loaded if isinstance(loaded, tuple) else (loaded, None)
    if chunk is None:
        raise LuaSourceError(f"{chunk_name} failed to load: {error}")
    return chunk


def run_plain_global(source: str, chunk_name: str, global_name: str) -> Any:
    """For files that assign directly to a global, e.g.
    `ClassCodexSource = ClassCodexSource or {}; ClassCodexSource[...] = {...}`.
    Each call gets its own fresh runtime -- the whole point of running
    untrusted third-party text is that one file's execution must not be able
    to see or taint another's."""
    runtime = new_sandboxed_runtime()
    chunk = _compile(runtime, source, chunk_name)
    chunk()
    return to_python(runtime.globals()[global_name])


def run_addon_namespace(source: str, chunk_name: str, addon_name: str = "ClassCodex") -> Any:
    """For addon Shared/*.lua modules using the `local _, ns = ...` pattern:
    WoW's addon loader calls each file with (addonName, addonTable) as
    varargs. Returns the populated namespace table."""
    runtime = new_sandboxed_runtime()
    chunk = _compile(runtime, source, chunk_name)
    ns = runtime.table()
    chunk(addon_name, ns)
    return to_python(ns)
