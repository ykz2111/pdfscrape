"""Tests for the macOS .app bundle builder."""

import plistlib
from pathlib import Path

from pdfscrape.macos import APP_NAME, build_app


def test_build_app_creates_the_bundle(tmp_path: Path):
    app = build_app(tmp_path / f"{APP_NAME}.app")

    assert app.is_dir()
    assert (app / "Contents" / "Info.plist").is_file()
    assert (app / "Contents" / "MacOS" / APP_NAME).is_file()
    assert (app / "Contents" / "Resources" / "AppIcon.icns").is_file()


def test_launcher_is_executable(tmp_path: Path):
    app = build_app(tmp_path / f"{APP_NAME}.app")
    launcher = app / "Contents" / "MacOS" / APP_NAME
    assert launcher.stat().st_mode & 0o111, "launcher must be executable"


def test_launcher_points_at_the_repo(tmp_path: Path):
    from pdfscrape.macos import repo_root

    app = build_app(tmp_path / f"{APP_NAME}.app")
    launcher = (app / "Contents" / "MacOS" / APP_NAME).read_text()

    assert str(repo_root()) in launcher
    assert "__REPO__" not in launcher, "the repo placeholder must be replaced"


def test_info_plist_is_valid(tmp_path: Path):
    app = build_app(tmp_path / f"{APP_NAME}.app")
    with open(app / "Contents" / "Info.plist", "rb") as fh:
        plist = plistlib.load(fh)

    assert plist["CFBundleExecutable"] == APP_NAME
    assert plist["CFBundlePackageType"] == "APPL"
    assert plist["CFBundleIdentifier"]


def test_rebuild_replaces_the_existing_bundle(tmp_path: Path):
    target = tmp_path / f"{APP_NAME}.app"
    build_app(target)
    stale = target / "Contents" / "stale.txt"
    stale.write_text("old")

    build_app(target)
    assert not stale.exists(), "a rebuild must start from a clean bundle"
