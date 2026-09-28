"""Fetches the live ClassCodex data files straight from the public build
host the official Icy Veins / U.GG desktop app itself updates from --
verified 2026-09-28 by reading that app's own network log on this machine.

No login, no browser, no app required: plain HTTPS GETs against a public
S3-backed build manifest system.

    channels/<gameVersionId>/<channel>/config.json  -- current build pointer
    builds/<gameVersionId>/<buildId>/manifest.json  -- exact file list + sha256
    builds/<gameVersionId>/<buildId>/<file path>     -- the file itself

This replaces the abandoned Scraper repo, which fetched from a third-party
GitHub mirror (Tharavol/ClassCodexContinued) that the mirror's own README
now says is frozen and stale -- confirmed live: it was missing Critical
Strike from Frost Death Knight's stat priority entirely, while this source
and the real installed addon both have it correctly.
"""
from __future__ import annotations

import hashlib
import json
import urllib.error
import urllib.request
from dataclasses import dataclass, field

BASE_URL = "https://wow-class-codex.s3.us-east-1.amazonaws.com"
GAME_VERSION_ID = "retail"
CHANNEL = "production"

# The four files this pipeline actually needs. Everything else in a build
# (UI code, locales, media) is the addon's own presentation layer.
NEEDED_FILES: dict[str, str] = {
    "db_ugg": "ClassCodex/Data/db_ugg.lua",
    "db_icyveins": "ClassCodex/Data/db_icyveins.lua",
    "db_gamedata": "ClassCodex/Data/db_gamedata.lua",
    "stat_dr": "ClassCodex/Shared/StatDR.lua",
}

FETCH_ERRORS = (urllib.error.URLError, OSError)


class FetchFailure(RuntimeError):
    """Raised when the current build pointer, its manifest, or a needed file
    cannot be fetched or fails its checksum -- fail closed, never guess."""


@dataclass
class FetchResult:
    build_id: str
    published_at: str
    sources: dict[str, str] = field(default_factory=dict)  # key -> raw Lua text


def _get(url: str, timeout: float = 30.0) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": "StatVerdict-ClassCodexFetch/1.0"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.read()
    except FETCH_ERRORS as exc:
        raise FetchFailure(f"GET {url} failed: {exc}") from exc


def get_current_build() -> dict:
    url = f"{BASE_URL}/channels/{GAME_VERSION_ID}/{CHANNEL}/config.json"
    try:
        config = json.loads(_get(url))
    except json.JSONDecodeError as exc:
        raise FetchFailure(f"config.json at {url} was not valid JSON: {exc}") from exc
    for key in ("buildId", "manifestUrl", "publishedAt"):
        if key not in config:
            raise FetchFailure(f"config.json at {url} is missing '{key}'")
    return config


def get_manifest(manifest_url: str) -> dict:
    try:
        manifest = json.loads(_get(manifest_url))
    except json.JSONDecodeError as exc:
        raise FetchFailure(f"manifest at {manifest_url} was not valid JSON: {exc}") from exc
    if not isinstance(manifest.get("files"), list):
        raise FetchFailure(f"manifest at {manifest_url} has no 'files' list")
    return manifest


def fetch_all() -> FetchResult:
    config = get_current_build()
    manifest = get_manifest(config["manifestUrl"])
    files_by_path = {entry["path"]: entry for entry in manifest["files"]}

    sources: dict[str, str] = {}
    for key, path in NEEDED_FILES.items():
        entry = files_by_path.get(path)
        if entry is None:
            raise FetchFailure(f"build {config['buildId']} manifest does not list '{path}' (upstream layout changed)")
        file_url = f"{BASE_URL}/builds/{GAME_VERSION_ID}/{config['buildId']}/{path}"
        raw = _get(file_url)
        actual_sha256 = hashlib.sha256(raw).hexdigest()
        expected_sha256 = entry.get("sha256")
        if expected_sha256 and actual_sha256 != expected_sha256:
            raise FetchFailure(
                f"'{path}' checksum mismatch: manifest says {expected_sha256}, downloaded file hashes to {actual_sha256}"
            )
        try:
            sources[key] = raw.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise FetchFailure(f"'{path}' is not valid UTF-8 text: {exc}") from exc

    return FetchResult(build_id=config["buildId"], published_at=config["publishedAt"], sources=sources)
