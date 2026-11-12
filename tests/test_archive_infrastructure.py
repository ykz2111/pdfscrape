"""Check Phase 4 wiring without Docker, network access, or provider credentials."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]


def load_workflow():
    # BaseLoader preserves YAML's `on` key rather than interpreting it as a boolean.
    path = ROOT / ".github/workflows/archive-pages.yml"
    return yaml.load(path.read_text(encoding="utf-8"), Loader=yaml.BaseLoader)


def test_container_setup():
    folder = ROOT / ".devcontainer"
    config = json.loads((folder / "devcontainer.json").read_text(encoding="utf-8"))
    assert (folder / config["build"]["dockerfile"]).is_file()
    assert config["remoteUser"] == "vscode"
    venv = "/home/vscode/.venvs/pdfscrape"
    assert f"{venv}/bin/python -m pip install -e '.[dev]'" in config["postCreateCommand"]
    assert config["remoteEnv"]["PATH"].startswith(f"{venv}/bin:")
    assert config["forwardPorts"] == [8000]
    assert config["features"]["ghcr.io/devcontainers/features/node:1"]["version"] == "24"
    assert "mounts" not in config
    dockerfile = (folder / "Dockerfile").read_text(encoding="utf-8")
    for package in ("poppler-utils", "tesseract-ocr-eng", "tesseract-ocr-ron"):
        assert package in dockerfile
    assert dockerfile.rstrip().endswith("USER vscode")


def test_pages_triggers_and_permissions():
    workflow = load_workflow()
    assert set(workflow["on"]) == {"schedule", "workflow_dispatch"}
    assert workflow["on"]["schedule"][0]["cron"] == "23 4 * * 1"
    assert workflow["permissions"] == {"contents": "read"}
    assert workflow["concurrency"]["cancel-in-progress"] == "false"
    build = workflow["jobs"]["build"]
    assert "github.event.repository.default_branch" in build["if"]
    assert "permissions" not in build
    deploy = workflow["jobs"]["deploy"]
    assert deploy["needs"] == "build"
    assert deploy["permissions"] == {"pages": "write", "id-token": "write"}
    assert deploy["environment"]["name"] == "github-pages"


def test_pipeline_validates_before_upload():
    workflow = load_workflow()
    steps = workflow["jobs"]["build"]["steps"]
    commands = [step["run"] for step in steps if "run" in step]
    expected = [
        "pdfscrape archive harvest --output build/catalog.jsonl",
        "pdfscrape archive validate --input build/catalog.jsonl",
        "pdfscrape archive build-site --input build/catalog.jsonl --output dist/archive",
        "pdfscrape archive validate --input dist/archive/catalog.json",
    ]
    positions = [commands.index(command) for command in expected]
    assert positions == sorted(positions)
    assert "missing archive CLI" in commands[1]
    assert "not isinstance(catalog, list) or not catalog" in commands[-1]
    assert steps[-1]["uses"] == "actions/upload-pages-artifact@v3"
    assert steps[-1]["with"]["path"] == "dist/archive"
    assert all("continue-on-error" not in step and "if" not in step for step in steps)
    assert "secrets." not in json.dumps(workflow)


def test_preflight_fails_when_archive_cli_is_missing(tmp_path):
    binary = tmp_path / "pdfscrape"
    binary.write_text("#!/bin/sh\nexit 2\n", encoding="utf-8")
    binary.chmod(0o755)
    steps = load_workflow()["jobs"]["build"]["steps"]
    script = next(
        step["run"] for step in steps if step.get("name") == "Require archive implementation"
    )
    result = subprocess.run(
        ["/bin/bash", "-c", script], cwd=tmp_path, capture_output=True, text=True,
        env={**os.environ, "PATH": str(tmp_path) + os.pathsep + os.environ["PATH"]},
    )
    assert result.returncode != 0
    assert "::error::" in result.stdout
    assert "missing archive CLI" in result.stdout


@pytest.mark.parametrize(
    "catalog,success",
    [("[]", False), ("{}", False), ("bad", False), ('[{"id": "example"}]', True)],
)
def test_artifact_gate(tmp_path, catalog, success):
    output = tmp_path / "dist/archive"
    output.mkdir(parents=True)
    (output / "index.html").write_text("<!doctype html>", encoding="utf-8")
    (output / "catalog.json").write_text(catalog, encoding="utf-8")
    steps = load_workflow()["jobs"]["build"]["steps"]
    script = next(
        step["run"] for step in steps if step.get("name") == "Require publishable artifacts"
    )
    result = subprocess.run(
        ["/bin/bash", "-c", script], cwd=tmp_path, capture_output=True, text=True,
        env={**os.environ, "PATH": str(Path(sys.executable).parent) + os.pathsep +
             os.environ["PATH"]},
    )
    assert (result.returncode == 0) is success
