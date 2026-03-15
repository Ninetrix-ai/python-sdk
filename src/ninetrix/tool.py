"""
@Tool decorator — the primary public API of the Ninetrix SDK.

Usage (bare decorator)::

    from ninetrix import Tool

    @Tool
    def search_web(query: str, max_results: int = 5) -> str:
        \"\"\"Search the web and return a summary of results.

        Args:
            query: The search query string.
            max_results: Maximum number of results to return.
        \"\"\"
        ...

Usage (decorator factory with overrides)::

    @Tool(name="web_search", description="Search the web for any topic.")
    def search_web(query: str) -> str:
        ...

The original function is returned **unchanged** — it remains a normal callable.
The decorator only registers metadata in the module-level ToolRegistry.
"""

from __future__ import annotations

import functools
from typing import Any, Callable, TypeVar, overload

import ninetrix.registry as _reg_module
from ninetrix.registry import ToolDef
from ninetrix.schema import build_parameters_schema, parse_docstring

F = TypeVar("F", bound=Callable[..., Any])


# ── Core registration logic ───────────────────────────────────────────────────

def _register_tool(
    fn: Callable[..., Any],
    *,
    name: str | None = None,
    description: str | None = None,
) -> None:
    """Extract metadata from *fn* and register a ToolDef in the global registry."""
    tool_name = name or fn.__name__
    docstring = fn.__doc__ or ""
    summary, param_docs = parse_docstring(docstring)
    tool_description = description or summary or f"Tool: {tool_name}"
    parameters = build_parameters_schema(fn, param_docs)

    tool_def = ToolDef(
        name=tool_name,
        description=tool_description,
        parameters=parameters,
        fn=fn,
    )
    # Late-bind to _reg_module._registry so discover.py can swap it temporarily.
    _reg_module._registry.register(tool_def)


# ── Public decorator ──────────────────────────────────────────────────────────

@overload
def Tool(fn: F) -> F: ...


@overload
def Tool(
    fn: None = None,
    *,
    name: str | None = None,
    description: str | None = None,
) -> Callable[[F], F]: ...


def Tool(  # type: ignore[misc]
    fn: F | None = None,
    *,
    name: str | None = None,
    description: str | None = None,
) -> F | Callable[[F], F]:
    """
    Mark a Python function as a Ninetrix tool.

    The function is registered in the module-level ToolRegistry and returned
    **unchanged** — it can still be called normally in tests or other code.

    Parameters
    ----------
    fn:
        The function to decorate. Provided automatically when used as
        ``@Tool`` (without parentheses).
    name:
        Override the tool name. Defaults to the function's ``__name__``.
    description:
        Override the tool description. Defaults to the function's docstring
        summary (first paragraph).

    Examples
    --------
    Bare decorator::

        @Tool
        def fetch_user(user_id: str) -> dict:
            \"\"\"Fetch a user record by ID.\"\"\"
            ...

    Decorator factory::

        @Tool(name="fetch_user_record")
        def fetch_user(user_id: str) -> dict:
            ...
    """

    def decorator(f: F) -> F:
        _register_tool(f, name=name, description=description)

        # Preserve function metadata (name, docstring, signature)
        @functools.wraps(f)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            return f(*args, **kwargs)

        # Attach a marker so introspection tools can detect ninetrix tools
        wrapper.__ninetrix_tool__ = True  # type: ignore[attr-defined]
        wrapper.__ninetrix_tool_name__ = name or f.__name__  # type: ignore[attr-defined]

        return wrapper  # type: ignore[return-value]

    if fn is not None:
        # Used as @Tool — fn is the decorated function
        return decorator(fn)

    # Used as @Tool(...) — return the decorator
    return decorator
