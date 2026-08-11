"""Thin async client for the read-only slice of the Onshape REST API this project uses.

Auth: HTTP Basic with an API key pair (access key as username, secret key as
password), created at https://cad.onshape.com/appstore/dev-portal.

Endpoint paths follow Onshape's {wvm}/{wvmid} convention, where wvm is one of
"w" (workspace), "v" (version), or "m" (microversion). This client only ever
uses "w" (current workspace state) or "v" (a pinned version/revision) — never
issues a write request.
"""

from __future__ import annotations

import httpx

DEFAULT_BASE_URL = "https://cad.onshape.com/api"


class OnshapeError(RuntimeError):
    """Raised when the Onshape API returns a non-2xx response."""

    def __init__(self, status_code: int, message: str):
        self.status_code = status_code
        super().__init__(f"Onshape API error {status_code}: {message}")


class OnshapeClient:
    """Read-only wrapper around the Onshape REST API.

    Deliberately exposes no write/mutation endpoints (no element creation,
    no updates, no deletes) — this client backs an MCP server whose tools
    must never modify a live CAD document.
    """

    def __init__(
        self,
        access_key: str,
        secret_key: str,
        base_url: str = DEFAULT_BASE_URL,
        timeout: float = 30.0,
    ):
        self._client = httpx.AsyncClient(
            base_url=base_url,
            auth=httpx.BasicAuth(access_key, secret_key),
            headers={"Accept": "application/json"},
            timeout=timeout,
        )

    async def aclose(self) -> None:
        await self._client.aclose()

    async def __aenter__(self) -> "OnshapeClient":
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        await self.aclose()

    async def _get(self, path: str, params: dict | None = None) -> dict:
        response = await self._client.get(path, params=params)
        if response.is_error:
            raise OnshapeError(response.status_code, response.text)
        return response.json()

    # -- Document metadata ------------------------------------------------

    async def get_document(self, document_id: str) -> dict:
        """GET /documents/d/{did} — name, owner, default workspace, etc."""
        return await self._get(f"/documents/d/{document_id}")

    async def get_default_workspace_id(self, document_id: str) -> str:
        doc = await self.get_document(document_id)
        return doc["defaultWorkspace"]["id"]

    async def list_elements(
        self, document_id: str, workspace_id: str, wvm: str = "w"
    ) -> list[dict]:
        """GET /documents/d/{did}/{wvm}/{wvmid}/elements — the document's tabs."""
        return await self._get(
            f"/documents/d/{document_id}/{wvm}/{workspace_id}/elements"
        )

    # -- Mass properties ----------------------------------------------------

    async def get_part_studio_mass_properties(
        self, document_id: str, element_id: str, workspace_id: str, wvm: str = "w"
    ) -> dict:
        """GET .../partstudios/.../massproperties — mass properties for every
        part in a Part Studio tab, combined."""
        return await self._get(
            f"/partstudios/d/{document_id}/{wvm}/{workspace_id}"
            f"/e/{element_id}/massproperties"
        )

    async def get_part_mass_properties(
        self,
        document_id: str,
        element_id: str,
        part_id: str,
        workspace_id: str,
        wvm: str = "w",
    ) -> dict:
        """GET .../parts/.../partid/{partid}/massproperties — a single part."""
        return await self._get(
            f"/parts/d/{document_id}/{wvm}/{workspace_id}"
            f"/e/{element_id}/partid/{part_id}/massproperties"
        )

    # -- Bill of materials ----------------------------------------------------

    async def get_assembly_bom(
        self,
        document_id: str,
        element_id: str,
        workspace_id: str,
        wvm: str = "w",
        indented: bool = True,
    ) -> dict:
        """GET .../assemblies/.../bom — flat or indented BOM for an assembly tab."""
        return await self._get(
            f"/assemblies/d/{document_id}/{wvm}/{workspace_id}/e/{element_id}/bom",
            params={"indented": str(indented).lower()},
        )

    # -- Revision / version history ------------------------------------------

    async def list_versions(self, document_id: str) -> list[dict]:
        """GET /documents/d/{did}/versions — every saved version, newest last."""
        return await self._get(f"/documents/d/{document_id}/versions")
