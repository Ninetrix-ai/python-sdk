"""
Ninetrix SDK — Python primitives for building AI agent tools.

Phase 1: @Tool decorator
    Define Python functions as agent-callable tools. They are auto-discovered
    by ``ninetrix build``, bundled into the Docker image, and dispatched at
    runtime alongside MCP tools.

Phase 2 (upcoming): Agent + Workflow
    Define full agents and complex workflows in Python.

Quick start::

    from ninetrix import Tool

    @Tool
    def query_customers(sql: str, limit: int = 100) -> list[dict]:
        \"\"\"Run a read-only SQL query against the customer database.

        Args:
            sql: A valid SELECT statement.
            limit: Maximum rows to return.
        \"\"\"
        return db.execute(sql, limit=limit)

Reference the tool in ``agentfile.yaml``::

    tools:
      - name: query_customers
        source: ./tools/db_tools.py

Then build and run as usual::

    ninetrix build
    ninetrix run
"""

from ninetrix.tool import Tool
from ninetrix.registry import ToolDef, ToolRegistry, _registry
from ninetrix.discover import (
    discover_tools_in_file,
    discover_tools_in_files,
    load_local_tools,
)

__version__ = "0.1.0"
__all__ = [
    # Primary public API
    "Tool",
    # Registry types (useful for type hints and testing)
    "ToolDef",
    "ToolRegistry",
    # Build-time discovery
    "discover_tools_in_file",
    "discover_tools_in_files",
    # Runtime loader (called by generated entrypoint)
    "load_local_tools",
    # Internal registry (advanced / testing)
    "_registry",
]
