"""Tests for discover.py — file-based tool discovery."""

from __future__ import annotations

import json
import textwrap
from pathlib import Path

import pytest

from ninetrix import _registry
from ninetrix.discover import (
    discover_tools_in_file,
    discover_tools_in_files,
    read_tools_manifest,
    write_tools_manifest,
)


@pytest.fixture(autouse=True)
def clear_registry():
    _registry.clear()
    yield
    _registry.clear()


@pytest.fixture
def tool_file(tmp_path: Path) -> Path:
    """Create a temp .py file with two @Tool-decorated functions."""
    code = textwrap.dedent("""\
        from ninetrix import Tool

        @Tool
        def search(query: str, limit: int = 5) -> str:
            \"\"\"Search the web.

            Args:
                query: The search query.
                limit: Max results.
            \"\"\"
            return ""

        @Tool(name="fetch_user")
        def get_user(user_id: str) -> dict:
            \"\"\"Fetch a user by ID.\"\"\"
            return {}
    """)
    f = tmp_path / "my_tools.py"
    f.write_text(code)
    return f


class TestDiscoverToolsInFile:
    def test_discovers_all_tools(self, tool_file: Path):
        manifests = discover_tools_in_file(tool_file)
        names = {m["name"] for m in manifests}
        assert names == {"search", "fetch_user"}

    def test_manifest_has_required_keys(self, tool_file: Path):
        manifests = discover_tools_in_file(tool_file)
        for m in manifests:
            assert "name" in m
            assert "description" in m
            assert "parameters" in m
            assert "source_file" in m

    def test_description_from_docstring(self, tool_file: Path):
        manifests = discover_tools_in_file(tool_file)
        search = next(m for m in manifests if m["name"] == "search")
        assert "Search the web" in search["description"]

    def test_param_schema_present(self, tool_file: Path):
        manifests = discover_tools_in_file(tool_file)
        search = next(m for m in manifests if m["name"] == "search")
        props = search["parameters"]["properties"]
        assert "query" in props
        assert "limit" in props

    def test_source_file_set(self, tool_file: Path):
        manifests = discover_tools_in_file(tool_file)
        for m in manifests:
            assert str(tool_file) in m["source_file"]

    def test_file_not_found_raises(self):
        with pytest.raises(FileNotFoundError):
            discover_tools_in_file("/nonexistent/path/tools.py")

    def test_no_tools_returns_empty_list(self, tmp_path: Path):
        f = tmp_path / "empty.py"
        f.write_text("x = 1\n")
        assert discover_tools_in_file(f) == []


class TestDiscoverToolsInFiles:
    def test_multiple_files_merged(self, tmp_path: Path):
        f1 = tmp_path / "a.py"
        f1.write_text(textwrap.dedent("""\
            from ninetrix import Tool
            @Tool
            def tool_a(x: str) -> str:
                \"\"\"Tool A.\"\"\"
                return x
        """))
        f2 = tmp_path / "b.py"
        f2.write_text(textwrap.dedent("""\
            from ninetrix import Tool
            @Tool
            def tool_b(x: str) -> str:
                \"\"\"Tool B.\"\"\"
                return x
        """))
        manifests = discover_tools_in_files([f1, f2])
        names = {m["name"] for m in manifests}
        assert names == {"tool_a", "tool_b"}

    def test_duplicate_names_first_wins(self, tmp_path: Path):
        f1 = tmp_path / "first.py"
        f1.write_text(textwrap.dedent("""\
            from ninetrix import Tool
            @Tool(name="dupe")
            def fn1(x: str) -> str:
                \"\"\"First version.\"\"\"
                return x
        """))
        f2 = tmp_path / "second.py"
        f2.write_text(textwrap.dedent("""\
            from ninetrix import Tool
            @Tool(name="dupe")
            def fn2(x: str) -> str:
                \"\"\"Second version.\"\"\"
                return x
        """))
        manifests = discover_tools_in_files([f1, f2])
        dupes = [m for m in manifests if m["name"] == "dupe"]
        assert len(dupes) == 1
        assert "First version" in dupes[0]["description"]


class TestManifestIO:
    def test_write_and_read_roundtrip(self, tmp_path: Path, tool_file: Path):
        manifests = discover_tools_in_file(tool_file)
        out = tmp_path / "tools.json"
        write_tools_manifest(manifests, out)

        loaded = read_tools_manifest(out)
        assert loaded == manifests

    def test_write_creates_parent_dirs(self, tmp_path: Path, tool_file: Path):
        manifests = discover_tools_in_file(tool_file)
        out = tmp_path / "nested" / "dir" / "tools.json"
        write_tools_manifest(manifests, out)
        assert out.exists()

    def test_manifest_is_valid_json(self, tmp_path: Path, tool_file: Path):
        manifests = discover_tools_in_file(tool_file)
        out = tmp_path / "tools.json"
        write_tools_manifest(manifests, out)
        data = json.loads(out.read_text())
        assert isinstance(data, list)
