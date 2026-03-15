"""
Tool discovery — used by ``ninetrix build`` to extract @Tool definitions
from user-provided Python files.

Two strategies:
  1. ``discover_tools_in_file``  — imports the file in-process and reads the
     registry. Fast. Used when the CLI environment has the same deps as the
     tool file.
  2. ``discover_tools_in_file_subprocess`` — runs a child Python process to
     import the file. Isolated. Used when tool deps may differ from the CLI.

Both return a list of ``ToolManifest`` dicts that are JSON-serialisable and
can be embedded into the Docker build context (written to ``tools.json``).
"""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import textwrap
from pathlib import Path
from typing import Any

import ninetrix.registry as _reg_module
from ninetrix.registry import ToolDef, ToolRegistry, _registry


# ── Public types ──────────────────────────────────────────────────────────────

# What ninetrix build serialises into the Docker image's tools.json
ToolManifest = dict[str, Any]
# Shape: {name, description, parameters, source_file, source_module}


# ── In-process discovery ──────────────────────────────────────────────────────

def discover_tools_in_file(file_path: str | Path) -> list[ToolManifest]:
    """
    Import *file_path* and return all @Tool-decorated functions as manifests.

    Uses a temporary fresh ToolRegistry so discovery is fully isolated —
    it does not contaminate the global registry and is safe to call
    multiple times for the same file (e.g. in tests).

    Raises:
        FileNotFoundError: if the file does not exist.
        ImportError: if the file cannot be imported.
    """
    path = Path(file_path).resolve()
    if not path.exists():
        raise FileNotFoundError(f"Tool file not found: {path}")

    fresh = ToolRegistry()
    original = _reg_module._registry
    _reg_module._registry = fresh

    # Force a fresh import even if the module was imported previously.
    module_name = f"_ninetrix_tool_{path.stem}_{id(fresh)}"

    try:
        _import_file(path, module_name=module_name)
        return [
            _tool_def_to_manifest(td, source_file=str(path))
            for td in fresh.all()
        ]
    finally:
        _reg_module._registry = original
        sys.modules.pop(module_name, None)


def discover_tools_in_files(
    file_paths: list[str | Path],
) -> list[ToolManifest]:
    """
    Discover @Tool functions across multiple files.
    Returns a flat, deduplicated list (first registration wins on name collision).
    """
    seen: set[str] = set()
    manifests: list[ToolManifest] = []

    for path in file_paths:
        for m in discover_tools_in_file(path):
            if m["name"] not in seen:
                seen.add(m["name"])
                manifests.append(m)

    return manifests


# ── Subprocess discovery (isolated) ──────────────────────────────────────────

_DISCOVERY_SCRIPT = textwrap.dedent("""
import sys, json
sys.path.insert(0, sys.argv[1])          # add SDK src/ to path
sys.path.insert(0, sys.argv[2])          # add file's directory to path
from ninetrix.registry import _registry
import importlib.util, pathlib

file_path = sys.argv[3]
path = pathlib.Path(file_path).resolve()
spec = importlib.util.spec_from_file_location("_ninetrix_discover", path)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

results = []
for td in _registry.all():
    results.append({
        "name": td.name,
        "description": td.description,
        "parameters": td.parameters,
        "source_file": str(path),
        "source_module": path.stem,
    })

print(json.dumps(results))
""")


def discover_tools_subprocess(file_path: str | Path) -> list[ToolManifest]:
    """
    Discover @Tool functions by running a child Python process.

    Safer than in-process discovery when tool files import heavy or
    conflicting dependencies. Falls back to in-process on failure.
    """
    path = Path(file_path).resolve()
    sdk_src = str(Path(__file__).parent.parent)  # .../sdk/src

    result = subprocess.run(
        [
            sys.executable,
            "-c",
            _DISCOVERY_SCRIPT,
            sdk_src,
            str(path.parent),
            str(path),
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )

    if result.returncode != 0:
        raise RuntimeError(
            f"Tool discovery failed for {path}:\n{result.stderr.strip()}"
        )

    return json.loads(result.stdout)  # type: ignore[no-any-return]


# ── Manifest helpers ──────────────────────────────────────────────────────────

def _tool_def_to_manifest(td: ToolDef, source_file: str = "") -> ToolManifest:
    return {
        "name": td.name,
        "description": td.description,
        "parameters": td.parameters,
        "source_file": source_file or td.source_file,
        "source_module": Path(source_file or td.source_file).stem if source_file else "",
    }


def write_tools_manifest(
    manifests: list[ToolManifest],
    output_path: str | Path,
) -> None:
    """
    Write tool manifests to *output_path* as JSON.
    Called by ``ninetrix build`` to produce ``tools.json`` in the build context.
    """
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifests, indent=2))


def read_tools_manifest(path: str | Path) -> list[ToolManifest]:
    """
    Read tool manifests from *path*.
    Called at container startup to register local tools.
    """
    return json.loads(Path(path).read_text())  # type: ignore[no-any-return]


# ── Runtime loader (used inside generated entrypoint.py) ─────────────────────

def load_local_tools(tool_files: list[str]) -> None:
    """
    Import a list of Python tool files and populate the global registry.

    Called at container startup by the generated entrypoint. Each file is
    imported once; subsequent calls with the same path are no-ops.
    """
    imported: set[str] = set()
    for file_path in tool_files:
        path = Path(file_path).resolve()
        if str(path) in imported:
            continue
        try:
            _import_file(path, module_name=None)
            imported.add(str(path))
        except Exception as exc:
            raise RuntimeError(
                f"Failed to load tool file '{path}': {exc}"
            ) from exc


def _import_file(path: Path, module_name: str | None = None) -> None:
    """Import a Python file by absolute path, adding its dir to sys.path."""
    parent = str(path.parent)
    if parent not in sys.path:
        sys.path.insert(0, parent)

    name = module_name or f"_ninetrix_tool_{path.stem}"
    if name in sys.modules:
        return  # already imported

    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load spec for '{path}'")

    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)  # type: ignore[union-attr]
