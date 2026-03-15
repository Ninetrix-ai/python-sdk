"""
ToolRegistry — module-level singleton that collects @Tool-decorated functions.

Design:
  - One global registry per Python process (can be reset in tests).
  - Thread-safe reads; registrations happen at import time (single-threaded).
  - The registry is the bridge between user code (which registers tools via
    @Tool) and the build step / runtime dispatcher (which reads them).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass(frozen=True)
class ToolDef:
    """
    Immutable description of a single @Tool-decorated function.

    Attributes:
        name:        Tool name exposed to the LLM (default: function name).
        description: Natural-language description (from docstring).
        parameters:  JSON Schema ``object`` describing the inputs.
        fn:          The original callable (unchanged by the decorator).
        source_file: Absolute path to the .py file that defines this tool.
                     Set by the discover step; empty when used in-process.
    """

    name: str
    description: str
    parameters: dict[str, Any]
    fn: Callable[..., Any]
    source_file: str = ""

    # ── Schema helpers ─────────────────────────────────────────────────────

    def to_anthropic_schema(self) -> dict[str, Any]:
        """Return schema in Anthropic tool_use format."""
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.parameters,
        }

    def to_openai_schema(self) -> dict[str, Any]:
        """Return schema in OpenAI function-calling format."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }

    def call(self, **kwargs: Any) -> Any:
        """Invoke the underlying function with validated keyword arguments."""
        return self.fn(**kwargs)


class ToolRegistry:
    """
    Collects ToolDef instances registered via @Tool.

    Usage::

        registry = ToolRegistry()

        @Tool
        def my_tool(x: str) -> str:
            \"\"\"Does something.\"\"\"
            ...

        registry.all()          # [ToolDef(name="my_tool", ...)]
        registry.get("my_tool") # ToolDef(...)
    """

    def __init__(self) -> None:
        self._tools: dict[str, ToolDef] = {}

    # ── Registration ───────────────────────────────────────────────────────

    def register(self, tool_def: ToolDef) -> None:
        """Add a ToolDef. Raises ValueError if name already registered."""
        if tool_def.name in self._tools:
            existing = self._tools[tool_def.name]
            if existing.fn is not tool_def.fn:
                raise ValueError(
                    f"Tool '{tool_def.name}' is already registered "
                    f"(from {existing.source_file or 'unknown'}). "
                    "Use a unique function name or set name= explicitly."
                )
        self._tools[tool_def.name] = tool_def

    # ── Lookup ─────────────────────────────────────────────────────────────

    def get(self, name: str) -> ToolDef | None:
        """Return the ToolDef for *name*, or None if not found."""
        return self._tools.get(name)

    def all(self) -> list[ToolDef]:
        """Return all registered ToolDefs in registration order."""
        return list(self._tools.values())

    def names(self) -> list[str]:
        """Return all registered tool names."""
        return list(self._tools.keys())

    def __len__(self) -> int:
        return len(self._tools)

    def __contains__(self, name: object) -> bool:
        return name in self._tools

    # ── Testing helpers ────────────────────────────────────────────────────

    def clear(self) -> None:
        """Remove all registrations. Intended for use in tests only."""
        self._tools.clear()

    def snapshot(self) -> dict[str, ToolDef]:
        """Return a shallow copy of the current registry state."""
        return dict(self._tools)


# Module-level singleton — used by @Tool and the runtime dispatcher.
_registry = ToolRegistry()
