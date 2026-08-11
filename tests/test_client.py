import httpx
import pytest
import respx

from onshape_copilot.client import OnshapeClient, OnshapeError

BASE_URL = "https://cad.onshape.com/api"


@pytest.fixture
async def client():
    async with OnshapeClient("test-access", "test-secret", base_url=BASE_URL) as c:
        yield c


@respx.mock
async def test_get_document_sends_basic_auth(client):
    route = respx.get(f"{BASE_URL}/documents/d/doc1").mock(
        return_value=httpx.Response(200, json={"id": "doc1", "name": "Bracket"})
    )

    result = await client.get_document("doc1")

    assert result == {"id": "doc1", "name": "Bracket"}
    sent_request = route.calls.last.request
    assert sent_request.headers["Authorization"].startswith("Basic ")


@respx.mock
async def test_get_default_workspace_id(client):
    respx.get(f"{BASE_URL}/documents/d/doc1").mock(
        return_value=httpx.Response(
            200, json={"id": "doc1", "defaultWorkspace": {"id": "ws1"}}
        )
    )

    workspace_id = await client.get_default_workspace_id("doc1")

    assert workspace_id == "ws1"


@respx.mock
async def test_list_elements_uses_workspace_path(client):
    respx.get(f"{BASE_URL}/documents/d/doc1/w/ws1/elements").mock(
        return_value=httpx.Response(
            200, json=[{"id": "el1", "name": "Part Studio 1", "elementType": "PARTSTUDIO"}]
        )
    )

    elements = await client.list_elements("doc1", "ws1")

    assert elements[0]["elementType"] == "PARTSTUDIO"


@respx.mock
async def test_list_elements_uses_version_path_when_wvm_v(client):
    route = respx.get(f"{BASE_URL}/documents/d/doc1/v/ver1/elements").mock(
        return_value=httpx.Response(200, json=[])
    )

    await client.list_elements("doc1", "ver1", wvm="v")

    assert route.called


@respx.mock
async def test_get_part_studio_mass_properties(client):
    respx.get(
        f"{BASE_URL}/partstudios/d/doc1/w/ws1/e/el1/massproperties"
    ).mock(return_value=httpx.Response(200, json={"bodies": {}}))

    result = await client.get_part_studio_mass_properties("doc1", "el1", "ws1")

    assert result == {"bodies": {}}


@respx.mock
async def test_get_assembly_bom_passes_indented_param(client):
    route = respx.get(f"{BASE_URL}/assemblies/d/doc1/w/ws1/e/el1/bom").mock(
        return_value=httpx.Response(200, json={"rows": []})
    )

    await client.get_assembly_bom("doc1", "el1", "ws1", indented=False)

    assert route.calls.last.request.url.params["indented"] == "false"


@respx.mock
async def test_list_versions(client):
    respx.get(f"{BASE_URL}/documents/d/doc1/versions").mock(
        return_value=httpx.Response(200, json=[{"id": "v1", "name": "Release 1"}])
    )

    versions = await client.list_versions("doc1")

    assert versions[0]["name"] == "Release 1"


@respx.mock
async def test_non_2xx_response_raises_onshape_error(client):
    respx.get(f"{BASE_URL}/documents/d/missing").mock(
        return_value=httpx.Response(404, text="Document not found")
    )

    with pytest.raises(OnshapeError) as exc_info:
        await client.get_document("missing")

    assert exc_info.value.status_code == 404
