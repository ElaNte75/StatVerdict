from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from tools.addon_benchmarks import build_addon_data, render_lua
from tools.tests.addon_fixtures import make_profile, make_raw_database

try:
    from lupa import LuaRuntime
except ImportError:  # optional dev dependency: pip install lupa
    LuaRuntime = None

ROOT = Path(__file__).resolve().parents[2]
ADDON = ROOT / "StatVerdict"


def toc_lua_files() -> list[Path]:
    files = []
    for line in (ADDON / "StatVerdict.toc").read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if line and not line.startswith("##"):
            files.append(ADDON / line.replace("\\", "/"))
    return files


def new_runtime():
    lua = LuaRuntime(unpack_returned_tuples=True)
    lua.execute("time = os.time")  # WoW provides time()
    return lua


def load_addon_file(lua, ns, relative_path: str) -> None:
    loader = lua.eval("function(path) local f, err = loadfile(path) if not f then error(err) end return f end")
    loader(str(ADDON / relative_path))("StatVerdict", ns)


def write_data_file(path: Path, generated_at: str, profiles: dict | None = None) -> None:
    data = build_addon_data([make_raw_database(generated_at, profiles)])
    path.write_text(render_lua(data), encoding="utf-8")


def now_stamp(days_ago: int = 0) -> str:
    return (datetime.now(timezone.utc) - timedelta(days=days_ago)).strftime("%Y-%m-%dT%H:%M:%SZ")


@unittest.skipIf(LuaRuntime is None, "lupa not installed")
class AddonLuaSyntaxTests(unittest.TestCase):
    def test_every_toc_file_compiles(self) -> None:
        lua = new_runtime()
        check = lua.eval("function(src, name) local f, err = load(src, name) if not f then return err end return nil end")
        for path in toc_lua_files():
            self.assertTrue(path.exists(), f"{path} is listed in the .toc but missing")
            error = check(path.read_text(encoding="utf-8-sig"), "@" + path.name)
            self.assertIsNone(error, f"{path.name}: {error}")


if __name__ == "__main__":
    unittest.main()
