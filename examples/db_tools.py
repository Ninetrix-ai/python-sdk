"""
Example: custom database + API tools for a Ninetrix agent.

Reference in agentfile.yaml:
    tools:
      - name: db_tools
        source: ./examples/db_tools.py

Then ninetrix build bundles this file and registers all @Tool functions.
"""

from __future__ import annotations

from typing import Literal

from ninetrix import Tool


@Tool
def query_customers(sql: str, limit: int = 100) -> list[dict]:
    """Execute a read-only SQL query against the customer database.

    Args:
        sql: A valid SELECT statement. UPDATE/DELETE/INSERT are not allowed.
        limit: Maximum number of rows to return. Hard-capped at 1000.
    """
    # Replace with real DB call
    raise NotImplementedError("Connect to your database here")


@Tool
def get_customer(customer_id: str) -> dict:
    """Fetch a single customer record by ID.

    Args:
        customer_id: The unique customer identifier (UUID or integer string).
    """
    raise NotImplementedError


@Tool
def search_products(
    query: str,
    category: str | None = None,
    sort: Literal["price_asc", "price_desc", "relevance"] = "relevance",
    limit: int = 20,
) -> list[dict]:
    """Search the product catalog.

    Args:
        query: Full-text search query.
        category: Optional category filter (e.g. "electronics", "apparel").
        sort: Sort order for results.
        limit: Maximum products to return.
    """
    raise NotImplementedError


@Tool(name="send_internal_notification")
def notify(channel: str, message: str, priority: Literal["low", "high"] = "low") -> bool:
    """Send a notification to an internal Slack channel or PagerDuty.

    Args:
        channel: Destination channel name (e.g. "#ops-alerts").
        message: Notification body. Keep it under 500 characters.
        priority: "high" pages on-call, "low" posts silently.
    """
    raise NotImplementedError
