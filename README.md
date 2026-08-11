# Onshape Copilot

An MCP server that gives Claude read-only access to a live Onshape CAD document: mass properties, bill of materials, tab listings, and revision history. Point Claude Desktop or Claude Code at it and ask engineering questions in plain language against a real document instead of a static export.

Built as a portfolio project targeting Forward Deployed Engineer roles — it's a small, honest demonstration of the kind of artifact those roles ship: an MCP server wrapping a real external API, with guardrails appropriate to a live production document.

## Why read-only

Every tool here queries Onshape; none of them create, edit, or delete anything. That's deliberate, not a missing feature — an agent with write access to a shared engineering document under active use is a materially different (and much higher-risk) project than one that answers questions about it. If you want a write-capable version, that's a natural v2, not something to bolt on quietly here.

## Tools exposed

| Tool | What it does |
|---|---|
| `get_document_info` | Name, owner, default workspace ID for a document |
| `list_document_elements` | List the tabs (Part Studios, Assemblies, Drawings) in a document |
| `get_part_studio_mass_properties` | Combined mass properties for every part in a Part Studio tab |
| `get_part_mass_properties` | Mass properties for one specific part |
| `get_assembly_bom` | Bill of materials for an Assembly tab |
| `list_document_versions` | Revision history — every saved version, with IDs |

Every tool that takes a `workspace_id` also accepts a `version_id` instead, which queries the document as it stood at that saved version — e.g. "what was this assembly's mass before the last design change?" via `list_document_versions` → pick a version → re-run `get_part_studio_mass_properties` with `version_id` set.

## Setup

1. **Get Onshape API credentials.** Go to [cad.onshape.com/appstore/dev-portal](https://cad.onshape.com/appstore/dev-portal) → API Keys → Create new API key. Copy the access key and secret immediately — the secret is shown only once.
2. **Install:**
   ```bash
   python -m venv .venv
   .venv/Scripts/activate   # or `source .venv/bin/activate` on macOS/Linux
   pip install -e ".[dev]"
   ```
3. **Configure credentials:**
   ```bash
   cp .env.example .env
   # fill in ONSHAPE_ACCESS_KEY and ONSHAPE_SECRET_KEY
   ```
4. **Run the tests** (no Onshape account needed — the Onshape API is mocked with `respx`):
   ```bash
   pytest
   ```

## Using it with Claude Desktop or Claude Code

Add it as an MCP server in your client's config (Claude Desktop: `claude_desktop_config.json`; Claude Code: `.mcp.json` or `claude mcp add`). Exact config file location and key names vary by client version — check your client's current MCP setup docs — but the shape is:

```json
{
  "mcpServers": {
    "onshape-copilot": {
      "command": "C:/path/to/Onshape Copilot/.venv/Scripts/python.exe",
      "args": ["-m", "onshape_copilot.server"],
      "env": {
        "ONSHAPE_ACCESS_KEY": "...",
        "ONSHAPE_SECRET_KEY": "..."
      }
    }
  }
}
```

Then ask things like: *"List the tabs in document `<id>`, then get the mass properties of the main Part Studio."* You'll need a document ID — the 24-character segment in an Onshape document's URL (`cad.onshape.com/documents/<document_id>/...`).

## Architecture

- `src/onshape_copilot/client.py` — a thin async `httpx`-based wrapper around the handful of Onshape REST endpoints this project uses (HTTP Basic auth with the API key pair). No write endpoints implemented, on purpose.
- `src/onshape_copilot/server.py` — the MCP server (official `mcp` Python SDK, `MCPServer`, stdio transport). Each tool has a description written for the model, not just a human — Claude relies on these to decide when and how to call each tool.
- `tests/` — `client.py` tested against a mocked Onshape API (`respx`); `server.py`'s workspace/version-resolution logic tested directly, without depending on the MCP decorator internals.

## What's not here (yet)

- No write operations (see "Why read-only" above).
- No caching — every tool call is a live Onshape API request. Fine for interactive use; would need a cache layer for high-frequency polling.
- No auth beyond a single static API key pair — fine for a personal/portfolio project, not something to run multi-tenant as-is.
