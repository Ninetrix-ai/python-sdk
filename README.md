# ninetrix-sdk

Python SDK for [Ninetrix](https://ninetrix.io) — define AI agent tools in code.

## Phase 1: `@Tool` decorator

Connect any Python function to a Ninetrix agent. The function is auto-discovered by `ninetrix build`, bundled into the Docker image, and dispatched at runtime alongside MCP tools.

```bash
pip install ninetrix-sdk
```

---

## Quick start

**1. Define your tools**

```python
# tools/db_tools.py
from ninetrix import Tool

@Tool
def query_customers(sql: str, limit: int = 100) -> list[dict]:
    """Execute a read-only SQL query against the customer database.

    Args:
        sql: A valid SELECT statement.
        limit: Maximum rows to return.
    """
    return db.execute(sql, limit=limit)


@Tool
def send_notification(channel: str, message: str) -> bool:
    """Send a message to an internal Slack channel.

    Args:
        channel: Destination channel (e.g. "#ops").
        message: Notification text.
    """
    return slack.post(channel, message)
```

**2. Reference in `agentfile.yaml`**

```yaml
agents:
  my-agent:
    metadata:
      role: Operations assistant
      goal: Answer questions and send alerts using internal tools

    runtime:
      provider: anthropic
      model: claude-sonnet-4-6

    tools:
      - name: web_search
        source: mcp://brave-search        # MCP tool — unchanged

      - name: db_tools
        source: ./tools/db_tools.py       # Python tool file — NEW
```

**3. Build and run**

```bash
ninetrix build    # discovers @Tool functions, bundles them into the image
ninetrix run      # agent can now call query_customers and send_notification
```

---

## How it works

| Step | What happens |
|------|-------------|
| `ninetrix build` | Scans `source: ./...py` entries, imports the file, extracts `@Tool` schemas |
| Dockerfile | Copies the `.py` files into the image, installs `ninetrix-sdk` |
| Container start | Imports the tool files, registers functions in the local registry |
| LLM call | Agent receives local tool schemas alongside MCP tool schemas |
| Tool dispatch | When the LLM calls a local tool, the Python function is invoked directly |

---

## `@Tool` API

### Bare decorator

```python
@Tool
def my_function(param: str, count: int = 5) -> str:
    """One-line description used as the tool description.

    Args:
        param: Injected into the tool's parameter schema.
        count: Optional param — not required, default shown to LLM.
    """
    ...
```

### Decorator factory (with overrides)

```python
@Tool(name="custom_name", description="Override the docstring description.")
def my_function(param: str) -> str:
    ...
```

### Supported parameter types

| Python type | JSON Schema |
|------------|------------|
| `str` | `{"type": "string"}` |
| `int` | `{"type": "integer"}` |
| `float` | `{"type": "number"}` |
| `bool` | `{"type": "boolean"}` |
| `list[str]` | `{"type": "array", "items": {"type": "string"}}` |
| `dict` | `{"type": "object"}` |
| `Optional[str]` | `{"type": "string"}` (not required) |
| `Literal["a","b"]` | `{"type": "string", "enum": ["a","b"]}` |

Parameters without defaults → `required`. Parameters with defaults → optional (default shown in schema).

---

## Multiple tool files

```yaml
tools:
  - name: db_tools
    source: ./tools/db_tools.py

  - name: api_tools
    source: ./tools/api_tools.py

  - name: web_search
    source: mcp://brave-search
```

---

## Testing your tools

Tools are plain Python functions — test them directly:

```python
# tests/test_db_tools.py
from tools.db_tools import query_customers

def test_query_customers():
    result = query_customers("SELECT id FROM customers LIMIT 1")
    assert isinstance(result, list)
```

To inspect the generated schema:

```python
from ninetrix import _registry
from tools import db_tools  # triggers @Tool registrations

td = _registry.get("query_customers")
print(td.to_anthropic_schema())
```

---

## Roadmap

- **Phase 1** ✅ — `@Tool` decorator, build discovery, runtime dispatch
- **Phase 2** — `Agent(...)` class + `@Workflow` decorator for Python-first agent definition
- **Phase 3** — Durable execution: checkpoint every workflow step, resume on crash

---

## License

Apache 2.0
