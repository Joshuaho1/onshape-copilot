"""MCP server exposing read-only Onshape CAD queries as tools for Claude.

Run directly (stdio transport, for Claude Desktop / Claude Code):

    python -m onshape_copilot.server

Every tool here is read-only by design — there is no tool that creates,
edits, or deletes anything in a live CAD document. That's a deliberate
guardrail, not a missing feature: an agent with write access to a shared
engineering document is a very different (and much higher-risk) project
than one that answers questions about it.
"""

from __future__ import annotations

import os

from dotenv import load_dotenv
from mcp.server import MCPServer

from onshape_copilot.client import OnshapeClient, OnshapeError, DEFAULT_BASE_URL

load_dotenv()

mcp = MCPServer("Onshape Copilot")

_client: OnshapeClient | None = None


def _get_client() -> OnshapeClient:
    global _client
    if _client is None:
        access_key = os.environ.get("ONSHAPE_ACCESS_KEY")
        secret_key = os.environ.get("ONSHAPE_SECRET_KEY")
        if not access_key or not secret_key:
            raise RuntimeError(
                "ONSHAPE_ACCESS_KEY and ONSHAPE_SECRET_KEY must be set "
                "(see .env.example) — create a key pair at "
                "https://cad.onshape.com/appstore/dev-portal"
            )
        _client = OnshapeClient(
            access_key=access_key,
            secret_key=secret_key,
            base_url=os.environ.get("ONSHAPE_BASE_URL", DEFAULT_BASE_URL),
        )
    return _client


async def _resolve_wvm(
    document_id: str, workspace_id: str | None, version_id: str | None
) -> tuple[str, str]:
    """Resolve which document state to query: an explicit version (for
    historical/point-in-time queries), an explicit workspace, or — if
    neither is given — the document's current default workspace."""
    if version_id:
        return "v", version_id
    if workspace_id:
        return "w", workspace_id
    return "w", await _get_client().get_default_workspace_id(document_id)


@mcp.tool()
async def get_document_info(document_id: str) -> dict:
    """Get metadata for an Onshape document: name, owner, and its default
    workspace ID. Call this first when you only have a document ID/URL, since
    most other tools need a workspace ID (or a version ID, for read-only
    historical queries)."""
    try:
        return await _get_client().get_document(document_id)
    except OnshapeError as exc:
        return {"error": str(exc)}


@mcp.tool()
async def list_document_elements(
    document_id: str,
    workspace_id: str | None = None,
    version_id: str | None = None,
) -> list[dict]:
    """List the tabs (Part Studios, Assemblies, Drawings, etc.) in an Onshape
    document. Each entry has an elementId you'll need for mass-properties or
    BOM lookups, and an elementType telling you whether it's a Part Studio or
    an Assembly. Omit both workspace_id and version_id to use the document's
    current default workspace; pass version_id to see the tabs as they stood
    at a specific saved version instead."""
    wvm, wvmid = await _resolve_wvm(document_id, workspace_id, version_id)
    try:
        return await _get_client().list_elements(document_id, wvmid, wvm=wvm)
    except OnshapeError as exc:
        return [{"error": str(exc)}]


@mcp.tool()
async def get_part_studio_mass_properties(
    document_id: str,
    element_id: str,
    workspace_id: str | None = None,
    version_id: str | None = None,
) -> dict:
    """Get combined mass properties (mass, volume, center of mass, inertia
    tensor) for every part in a Part Studio tab. Use list_document_elements
    first to find a Part Studio's element_id. For a single part's properties
    within a multi-part studio, use get_part_mass_properties instead. Pass
    version_id instead of workspace_id to get mass properties as they stood
    at a specific saved version — e.g. to compare "current" vs. "as released"."""
    wvm, wvmid = await _resolve_wvm(document_id, workspace_id, version_id)
    try:
        return await _get_client().get_part_studio_mass_properties(
            document_id, element_id, wvmid, wvm=wvm
        )
    except OnshapeError as exc:
        return {"error": str(exc)}


@mcp.tool()
async def get_part_mass_properties(
    document_id: str,
    element_id: str,
    part_id: str,
    workspace_id: str | None = None,
    version_id: str | None = None,
) -> dict:
    """Get mass properties (mass, volume, center of mass, inertia tensor) for
    one specific part, identified by its partId within a Part Studio tab.
    Part IDs are visible in Onshape's UI or in the output of
    get_part_studio_mass_properties. Pass version_id instead of workspace_id
    to query as of a specific saved version."""
    wvm, wvmid = await _resolve_wvm(document_id, workspace_id, version_id)
    try:
        return await _get_client().get_part_mass_properties(
            document_id, element_id, part_id, wvmid, wvm=wvm
        )
    except OnshapeError as exc:
        return {"error": str(exc)}


@mcp.tool()
async def get_assembly_bom(
    document_id: str,
    element_id: str,
    workspace_id: str | None = None,
    version_id: str | None = None,
) -> dict:
    """Get the bill of materials for an Assembly tab: every part/sub-assembly
    instance, quantity, and configured properties (name, material, etc).
    Use list_document_elements first to find an Assembly's element_id. Pass
    version_id instead of workspace_id to get the BOM as of a specific saved
    version, e.g. to diff the BOM between two releases."""
    wvm, wvmid = await _resolve_wvm(document_id, workspace_id, version_id)
    try:
        return await _get_client().get_assembly_bom(
            document_id, element_id, wvmid, wvm=wvm
        )
    except OnshapeError as exc:
        return {"error": str(exc)}


@mcp.tool()
async def list_document_versions(document_id: str) -> list[dict]:
    """List every saved version of an Onshape document, oldest first, with
    each version's ID, name, and creation date. Use this to answer questions
    about a document's revision history, or to get a version ID to pass as
    version_id to the other tools for point-in-time queries (e.g. "what was
    the mass before the last design change?")."""
    try:
        return await _get_client().list_versions(document_id)
    except OnshapeError as exc:
        return [{"error": str(exc)}]


def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
