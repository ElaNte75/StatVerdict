from __future__ import annotations

import hashlib
import json
import unittest
from unittest.mock import patch

from tools.classcodex_fetch import FetchFailure, fetch_all

CONFIG = {
    "buildId": "build-1",
    "publishedAt": "2026-09-28T00:00:00.000Z",
    "manifestUrl": "https://wow-class-codex.s3.us-east-1.amazonaws.com/builds/retail/build-1/manifest.json",
}


def _manifest_with(files: dict[str, bytes]) -> dict:
    return {
        "files": [
            {"path": path, "sha256": hashlib.sha256(content).hexdigest()} for path, content in files.items()
        ]
    }


ALL_PATHS = (
    "ClassCodex/Data/db_ugg.lua",
    "ClassCodex/Data/db_icyveins.lua",
    "ClassCodex/Data/db_gamedata.lua",
    "ClassCodex/Shared/StatDR.lua",
)


class ClassCodexFetchTests(unittest.TestCase):
    def _fake_get_sequence(self, files: dict[str, bytes]):
        """Builds the ordered list of byte responses: config.json, manifest.json,
        then each of ALL_PATHS in NEEDED_FILES order."""
        manifest = _manifest_with(files)
        responses = [json.dumps(CONFIG).encode(), json.dumps(manifest).encode()]
        responses.extend(files[path] for path in ALL_PATHS)
        return responses

    def test_fetch_all_succeeds_when_every_file_matches_its_checksum(self) -> None:
        files = {path: f"-- {path}".encode() for path in ALL_PATHS}
        responses = self._fake_get_sequence(files)
        with patch("tools.classcodex_fetch._get", side_effect=responses):
            result = fetch_all()
        self.assertEqual("build-1", result.build_id)
        self.assertEqual(4, len(result.sources))

    def test_checksum_mismatch_fails_closed(self) -> None:
        files = {path: f"-- {path}".encode() for path in ALL_PATHS}
        manifest = _manifest_with(files)
        # Corrupt the actually-downloaded bytes for one file so it no longer
        # matches the manifest's recorded sha256 -- simulates a truncated or
        # tampered transfer.
        responses = [
            json.dumps(CONFIG).encode(),
            json.dumps(manifest).encode(),
            b"tampered bytes",
            files["ClassCodex/Data/db_icyveins.lua"],
            files["ClassCodex/Data/db_gamedata.lua"],
            files["ClassCodex/Shared/StatDR.lua"],
        ]
        with patch("tools.classcodex_fetch._get", side_effect=responses):
            with self.assertRaises(FetchFailure):
                fetch_all()

    def test_manifest_missing_a_needed_file_fails_closed(self) -> None:
        present_paths = [path for path in ALL_PATHS if path != "ClassCodex/Shared/StatDR.lua"]
        files = {path: f"-- {path}".encode() for path in present_paths}
        manifest = _manifest_with(files)
        responses = [json.dumps(CONFIG).encode(), json.dumps(manifest).encode()]
        responses.extend(files[path] for path in present_paths)  # the 3 files found before the missing one
        with patch("tools.classcodex_fetch._get", side_effect=responses):
            with self.assertRaises(FetchFailure):
                fetch_all()

    def test_non_json_config_fails_closed(self) -> None:
        with patch("tools.classcodex_fetch._get", side_effect=[b"not json"]):
            with self.assertRaises(FetchFailure):
                fetch_all()

    def test_config_missing_required_key_fails_closed(self) -> None:
        broken_config = {"buildId": "build-1"}  # missing manifestUrl/publishedAt
        with patch("tools.classcodex_fetch._get", side_effect=[json.dumps(broken_config).encode()]):
            with self.assertRaises(FetchFailure):
                fetch_all()


if __name__ == "__main__":
    unittest.main()
