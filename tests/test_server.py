"""Tests for the workspace/version resolution logic that every tool relies on.

Deliberately does not invoke the @mcp.tool()-decorated functions directly —
that would couple the test suite to FastMCP's decorator internals. Testing
_resolve_wvm (the plain function every tool calls first) covers the actual
branching logic without that dependency.
"""

import pytest

from onshape_copilot import server


class _FakeClient:
    async def get_default_workspace_id(self, document_id: str) -> str:
        return "default-ws"


@pytest.fixture(autouse=True)
def fake_client(monkeypatch):
    monkeypatch.setattr(server, "_get_client", lambda: _FakeClient())


async def test_explicit_version_id_wins():
    wvm, wvmid = await server._resolve_wvm("doc1", workspace_id=None, version_id="ver1")
    assert (wvm, wvmid) == ("v", "ver1")


async def test_explicit_workspace_id_used_when_no_version():
    wvm, wvmid = await server._resolve_wvm("doc1", workspace_id="ws1", version_id=None)
    assert (wvm, wvmid) == ("w", "ws1")


async def test_falls_back_to_default_workspace():
    wvm, wvmid = await server._resolve_wvm("doc1", workspace_id=None, version_id=None)
    assert (wvm, wvmid) == ("w", "default-ws")


async def test_version_id_takes_priority_over_workspace_id():
    wvm, wvmid = await server._resolve_wvm(
        "doc1", workspace_id="ws1", version_id="ver1"
    )
    assert (wvm, wvmid) == ("v", "ver1")
