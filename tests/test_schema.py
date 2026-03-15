"""Tests for schema.py — type annotation → JSON Schema conversion."""

from __future__ import annotations

from typing import Literal, Optional

import pytest

from ninetrix.schema import (
    build_parameters_schema,
    parse_docstring,
    type_to_json_schema,
)


# ── type_to_json_schema ───────────────────────────────────────────────────────

class TestTypeToJsonSchema:
    def test_str(self):
        assert type_to_json_schema(str) == {"type": "string"}

    def test_int(self):
        assert type_to_json_schema(int) == {"type": "integer"}

    def test_float(self):
        assert type_to_json_schema(float) == {"type": "number"}

    def test_bool(self):
        assert type_to_json_schema(bool) == {"type": "boolean"}

    def test_list_untyped(self):
        assert type_to_json_schema(list) == {"type": "array"}

    def test_list_typed(self):
        assert type_to_json_schema(list[str]) == {
            "type": "array",
            "items": {"type": "string"},
        }

    def test_list_nested(self):
        assert type_to_json_schema(list[list[int]]) == {
            "type": "array",
            "items": {"type": "array", "items": {"type": "integer"}},
        }

    def test_dict(self):
        assert type_to_json_schema(dict) == {"type": "object"}

    def test_optional_str(self):
        assert type_to_json_schema(Optional[str]) == {"type": "string"}

    def test_optional_int(self):
        assert type_to_json_schema(Optional[int]) == {"type": "integer"}

    def test_literal(self):
        result = type_to_json_schema(Literal["asc", "desc"])
        assert result == {"type": "string", "enum": ["asc", "desc"]}

    def test_unknown_falls_back_to_string(self):
        class Custom:
            pass
        assert type_to_json_schema(Custom) == {"type": "string"}


# ── parse_docstring ───────────────────────────────────────────────────────────

class TestParseDocstring:
    def test_empty(self):
        summary, params = parse_docstring("")
        assert summary == ""
        assert params == {}

    def test_summary_only(self):
        doc = "Search the web for information."
        summary, params = parse_docstring(doc)
        assert summary == "Search the web for information."
        assert params == {}

    def test_google_style_args(self):
        doc = """
        Search the web.

        Args:
            query: The search query.
            max_results: Maximum results to return.
        """
        summary, params = parse_docstring(doc)
        assert "Search the web" in summary
        assert params["query"] == "The search query."
        assert params["max_results"] == "Maximum results to return."

    def test_args_and_returns(self):
        doc = """
        Fetch a user record.

        Args:
            user_id: The user identifier.

        Returns:
            A dict with user data.
        """
        _, params = parse_docstring(doc)
        assert "user_id" in params
        assert "A dict" not in params  # Returns section not in params


# ── build_parameters_schema ───────────────────────────────────────────────────

class TestBuildParametersSchema:
    def test_all_required(self):
        def fn(query: str, limit: int) -> str:
            """Search."""
            ...

        schema = build_parameters_schema(fn, {})
        assert schema["required"] == ["query", "limit"]
        assert schema["properties"]["query"] == {"type": "string"}
        assert schema["properties"]["limit"] == {"type": "integer"}

    def test_optional_params_not_required(self):
        def fn(query: str, limit: int = 10) -> str:
            """Search."""
            ...

        schema = build_parameters_schema(fn, {})
        assert "query" in schema["required"]
        assert "limit" not in schema["required"]
        assert schema["properties"]["limit"]["default"] == 10

    def test_param_descriptions_injected(self):
        def fn(query: str) -> str:
            """Search."""
            ...

        schema = build_parameters_schema(fn, {"query": "The search query string."})
        assert schema["properties"]["query"]["description"] == "The search query string."

    def test_skips_self(self):
        class MyClass:
            def method(self, x: str) -> str:
                """Method."""
                ...

        schema = build_parameters_schema(MyClass.method, {})
        assert "self" not in schema["properties"]

    def test_no_params(self):
        def fn() -> str:
            """No params."""
            ...

        schema = build_parameters_schema(fn, {})
        assert schema["properties"] == {}
        assert "required" not in schema
