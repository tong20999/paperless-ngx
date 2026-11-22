import asyncio
import json
from http import HTTPStatus

import httpx
import pytest
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client
from rest_framework.authtoken.models import Token

from documents.models import Tag
from documents.search import get_backend
from paperless_mail.models import MailAccount
from paperless_testing.factories import DocumentFactory
from paperless_testing.factories import UserFactory
from paperless_testing.permissions import grant_global


def rpc(client, method, params):
    return client.post(
        "/mcp/",
        {"jsonrpc": "2.0", "id": 1, "method": method, "params": params},
        format="json",
        HTTP_ACCEPT="application/json, text/event-stream",
    )


@pytest.fixture
def mcp_client(rest_api_client, regular_user):
    token = Token.objects.create(user=regular_user)
    rest_api_client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")
    return rest_api_client


def call_tool(client, name, **arguments):
    response = rpc(client, "tools/call", {"name": name, "arguments": arguments})
    assert response.status_code == HTTPStatus.OK
    return response.json()["result"]


def test_authentication_and_discovery(rest_api_client, mcp_client):
    params = {
        "protocolVersion": "2025-03-26",
        "capabilities": {},
        "clientInfo": {"name": "test", "version": "1"},
    }
    assert (
        rpc(mcp_client, "initialize", params).json()["result"]["serverInfo"]["name"]
        == "paperless-ngx"
    )
    tools = rpc(mcp_client, "tools/list", {}).json()["result"]["tools"]
    assert {"search_documents", "query_data_collections", "TagViewSet_CreateTool"} <= {
        tool["name"] for tool in tools
    }
    rest_api_client.credentials()
    assert rpc(rest_api_client, "tools/list", {}).status_code == HTTPStatus.UNAUTHORIZED


def test_document_visibility(mcp_client, regular_user, paperless_dirs):
    grant_global(regular_user, "view_document")
    visible = DocumentFactory(owner=regular_user, title="receipt")
    private = DocumentFactory(owner=UserFactory(), title="receipt")
    backend = get_backend()
    for document in (visible, private):
        backend.add_or_update(document)

    for name, arguments in (
        ("search_documents", {"query": "receipt"}),
        ("query_data_collections", {"collection": "documents"}),
        ("UnifiedSearchViewSet_ListTool", {}),
    ):
        result = call_tool(mcp_client, name, **arguments)
        assert not result["isError"], result
        page = json.loads(result["content"][0]["text"])
        assert [item["id"] for item in page["results"]] == [visible.pk]
    assert mcp_client.get("/api/documents/").json()["count"] == 1


def test_write_uses_api_permissions_and_serializer(mcp_client, regular_user):
    name = "TagViewSet_CreateTool"
    result = call_tool(mcp_client, name, body={"name": "Invoices"})
    assert result["isError"]
    assert not Tag.objects.filter(name="Invoices").exists()
    grant_global(regular_user, "add_tag")
    result = call_tool(mcp_client, name, body={"name": "Invoices"})
    assert not result["isError"], result
    tag = Tag.objects.get(name="Invoices", owner=regular_user)
    grant_global(regular_user, "view_tag", "change_tag", "delete_tag")
    result = call_tool(
        mcp_client,
        "TagViewSet_UpdateTool",
        id=tag.pk,
        body={"name": "Paid invoices"},
    )
    assert not result["isError"], result
    tag.refresh_from_db()
    assert tag.name == "Paid invoices"
    result = call_tool(mcp_client, "TagViewSet_DeleteTool", id=tag.pk)
    assert not result["isError"], result
    assert not Tag.objects.filter(pk=tag.pk).exists()


def test_mail_query_uses_api_representation(mcp_client, regular_user):
    grant_global(regular_user, "view_mailaccount")
    MailAccount.objects.create(
        name="Inbox",
        owner=regular_user,
        password="example-mail-password",
        refresh_token="example-refresh-token",
    )
    result = call_tool(mcp_client, "query_data_collections", collection="mail_accounts")
    assert not result["isError"], result
    page = json.loads(result["content"][0]["text"])
    assert page == mcp_client.get("/api/mail_accounts/").json()
    assert page["results"][0]["password"] != "example-mail-password"
    assert "refresh_token" not in page["results"][0]


def test_streamable_http_client(live_server, regular_user):
    grant_global(regular_user, "view_tag")
    token = Token.objects.create(user=regular_user)
    Tag.objects.create(name="Bills", owner=regular_user)

    async def query_tags():
        url = f"{live_server.url}/mcp/"
        async with (
            httpx.AsyncClient(headers={"Authorization": f"Token {token.key}"}) as http,
            streamable_http_client(url, http_client=http) as streams,
            ClientSession(streams[0], streams[1]) as session,
        ):
            await session.initialize()
            result = await session.call_tool("TagViewSet_ListTool", {})
            assert not result.isError, result
            assert json.loads(result.content[0].text)["results"][0]["name"] == "Bills"

    asyncio.run(query_tags())
