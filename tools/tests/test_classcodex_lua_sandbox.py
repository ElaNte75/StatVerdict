from __future__ import annotations

import unittest

from tools.classcodex_lua_sandbox import LuaSourceError, new_sandboxed_runtime, run_addon_namespace, run_plain_global


class ClassCodexLuaSandboxTests(unittest.TestCase):
    def test_run_plain_global_reads_nested_tables(self) -> None:
        source = 'ClassCodexSource = ClassCodexSource or {}\nClassCodexSource["ugg"] = {data={DEATHKNIGHT={frost={x=1}}}}'
        result = run_plain_global(source, "fixture.lua", "ClassCodexSource")
        self.assertEqual(1, result["ugg"]["data"]["DEATHKNIGHT"]["frost"]["x"])

    def test_run_plain_global_converts_array_style_tables_to_lists(self) -> None:
        source = 'ClassCodexSource = {list = {"a", "b", "c"}}'
        result = run_plain_global(source, "fixture.lua", "ClassCodexSource")
        self.assertEqual(["a", "b", "c"], result["list"])

    def test_run_addon_namespace_matches_wow_addon_loader_varargs(self) -> None:
        source = "local addonName, ns = ...\nns.Value = addonName"
        result = run_addon_namespace(source, "fixture.lua", addon_name="ClassCodex")
        self.assertEqual("ClassCodex", result["Value"])

    def test_invalid_syntax_raises_lua_source_error_not_a_crash(self) -> None:
        with self.assertRaises(LuaSourceError):
            run_plain_global("this is not valid lua {{{", "fixture.lua", "Anything")

    def test_os_and_io_are_unavailable_to_fetched_code(self) -> None:
        # A real fetched file only ever assigns tables; this proves a
        # malicious one could not shell out or touch the filesystem even if
        # it tried, without needing to trust that it won't try.
        source = "ClassCodexSource = {ranOs = (os == nil), ranIo = (io == nil)}"
        result = run_plain_global(source, "fixture.lua", "ClassCodexSource")
        self.assertTrue(result["ranOs"])
        self.assertTrue(result["ranIo"])

    def test_python_eval_escape_is_closed(self) -> None:
        # lupa injects a `python` global with register_eval/register_builtins
        # left at their defaults; this is the escape a real code review found
        # in the abandoned Scraper repo. Proves it stays closed here too.
        source = "ClassCodexSource = {hasPython = (python ~= nil)}"
        result = run_plain_global(source, "fixture.lua", "ClassCodexSource")
        self.assertFalse(result["hasPython"])

    def test_python_attribute_access_on_a_live_python_object_is_denied(self) -> None:
        # The real escape a code review found: with lupa's defaults, Lua can
        # read attributes on any Python object it holds (e.g. a callable's
        # own __globals__), reaching __builtins__/__import__ regardless of
        # which globals were nilled. Exercised here by handing Lua an actual
        # Python function, exactly like builder_runtime.py's `date` shim did.
        runtime = new_sandboxed_runtime()
        runtime.globals()["python_fn"] = lambda: None
        load = runtime.globals()["load"]
        loaded = load("local ok, err = pcall(function() return python_fn.__globals__ end); return ok", "fixture.lua")
        chunk, error = loaded if isinstance(loaded, tuple) else (loaded, None)
        self.assertIsNone(error)
        ok = chunk()
        self.assertFalse(ok)


if __name__ == "__main__":
    unittest.main()
