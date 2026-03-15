"""Tests for the @Tool decorator."""

from __future__ import annotations

from typing import Optional

import pytest

from ninetrix import Tool, _registry
from ninetrix.registry import ToolDef


@pytest.fixture(autouse=True)
def clear_registry():
    """Reset the global registry before each test."""
    _registry.clear()
    yield
    _registry.clear()


# ── Basic decoration ──────────────────────────────────────────────────────────

class TestToolDecorator:
    def test_bare_decorator_registers_tool(self):
        @Tool
        def my_func(query: str) -> str:
            """Search the web."""
            return "result"

        assert "my_func" in _registry
        td = _registry.get("my_func")
        assert td is not None
        assert td.name == "my_func"
        assert td.description == "Search the web."

    def test_function_still_callable(self):
        @Tool
        def add(a: int, b: int) -> int:
            """Add two numbers."""
            return a + b

        assert add(2, 3) == 5

    def test_factory_with_name_override(self):
        @Tool(name="web_search")
        def search(query: str) -> str:
            """Search."""
            ...

        assert "web_search" in _registry
        assert "search" not in _registry

    def test_factory_with_description_override(self):
        @Tool(description="Custom description override.")
        def my_tool(x: str) -> str:
            """Original docstring."""
            ...

        td = _registry.get("my_tool")
        assert td is not None
        assert td.description == "Custom description override."

    def test_no_docstring_falls_back_to_name(self):
        @Tool
        def undocumented(x: str) -> str:
            return x

        td = _registry.get("undocumented")
        assert td is not None
        assert "undocumented" in td.description

    def test_marker_attributes_set(self):
        @Tool
        def marked(x: str) -> str:
            """Marked."""
            ...

        assert getattr(marked, "__ninetrix_tool__", False) is True
        assert marked.__ninetrix_tool_name__ == "marked"

    def test_duplicate_registration_same_fn_is_idempotent(self):
        """Re-decorating the same function should not raise."""
        def fn(x: str) -> str:
            """A tool."""
            ...

        Tool(fn)
        Tool(fn)  # same function — no error

    def test_duplicate_registration_different_fn_raises(self):
        @Tool(name="collision")
        def fn1(x: str) -> str:
            """First."""
            ...

        with pytest.raises(ValueError, match="collision"):
            @Tool(name="collision")
            def fn2(x: str) -> str:
                """Second."""
                ...


# ── Schema generation ─────────────────────────────────────────────────────────

class TestToolSchema:
    def test_parameters_schema_built(self):
        @Tool
        def fetch(user_id: str, active: bool = True) -> dict:
            """Fetch a user."""
            ...

        td = _registry.get("fetch")
        assert td is not None
        props = td.parameters["properties"]
        assert props["user_id"]["type"] == "string"
        assert props["active"]["type"] == "boolean"
        assert props["active"]["default"] is True

    def test_required_fields(self):
        @Tool
        def create(name: str, email: str, role: str = "viewer") -> dict:
            """Create a user."""
            ...

        td = _registry.get("create")
        assert td is not None
        assert set(td.parameters["required"]) == {"name", "email"}

    def test_anthropic_schema_format(self):
        @Tool
        def search(query: str) -> str:
            """Search the web."""
            ...

        td = _registry.get("search")
        assert td is not None
        schema = td.to_anthropic_schema()
        assert schema["name"] == "search"
        assert schema["description"] == "Search the web."
        assert "input_schema" in schema

    def test_openai_schema_format(self):
        @Tool
        def search(query: str) -> str:
            """Search."""
            ...

        td = _registry.get("search")
        assert td is not None
        schema = td.to_openai_schema()
        assert schema["type"] == "function"
        assert schema["function"]["name"] == "search"
        assert "parameters" in schema["function"]

    def test_param_docs_from_docstring(self):
        @Tool
        def query(sql: str, limit: int = 100) -> list:
            """Run a SQL query.

            Args:
                sql: A valid SELECT statement.
                limit: Maximum rows to return.
            """
            ...

        td = _registry.get("query")
        assert td is not None
        props = td.parameters["properties"]
        assert props["sql"]["description"] == "A valid SELECT statement."
        assert props["limit"]["description"] == "Maximum rows to return."

    def test_optional_param_not_required(self):
        @Tool
        def fn(required: str, optional: Optional[str] = None) -> str:
            """A function."""
            ...

        td = _registry.get("fn")
        assert td is not None
        assert "required" in td.parameters["required"]
        assert "optional" not in td.parameters.get("required", [])

    def test_tool_call(self):
        @Tool
        def multiply(a: int, b: int) -> int:
            """Multiply two numbers."""
            return a * b

        td = _registry.get("multiply")
        assert td is not None
        assert td.call(a=4, b=5) == 20
