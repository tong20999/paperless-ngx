"""Expose Paperless REST actions to authenticated Streamable HTTP MCP clients."""

import json
from io import BytesIO
from urllib.parse import urlencode

from asgiref.sync import sync_to_async
from django.core.handlers.wsgi import WSGIRequest
from django.urls import get_script_prefix
from django.urls import resolve
from django.urls import reverse
from mcp_server import mcp_server
from mcp_server.djangomcp import django_request_ctx

from documents.mcp import DOCUMENT_TOOLS
from paperless_mail.mcp import MAIL_TOOLS

API_TOOLS = {
    **DOCUMENT_TOOLS,
    **MAIL_TOOLS,
    "users": ("list", "create", "update", "destroy"),
    "groups": ("list", "create", "update", "destroy"),
    "config": ("list", "update"),
}


@sync_to_async
def _call_api(route, method="GET", *, pk=None, params=None, body=None):
    """Dispatch the same router callback as the API with the caller's credentials."""
    outer = django_request_ctx.get()
    path = reverse(route, kwargs={"pk": pk} if pk is not None else None)
    path_info = "/" + path.removeprefix(get_script_prefix())
    match = resolve(path_info)
    payload = b"" if body is None else json.dumps(body).encode()
    request = WSGIRequest(
        {
            **outer.META,
            "REQUEST_METHOD": method,
            "PATH_INFO": path_info,
            "QUERY_STRING": urlencode(params or {}, doseq=True),
            "CONTENT_TYPE": "application/json",
            "CONTENT_LENGTH": str(len(payload)),
            "HTTP_ACCEPT": "application/json",
            "wsgi.input": BytesIO(payload),
            "wsgi.url_scheme": outer.scheme,
        },
    )
    request.user = outer.user
    request.session = outer.session
    request.resolver_match = match
    response = match.func(request, **match.kwargs)
    if response.status_code >= 400:
        detail = getattr(response, "data", None) or response.reason_phrase
        raise ValueError(f"Paperless API returned {response.status_code}: {detail}")
    return response.data


def _register_viewset(viewset, basename, resource, actions):
    async def list_records(page: int = 1, page_size: int = 25):
        return await _call_api(
            f"{basename}-list",
            params={"page": page, "page_size": page_size},
        )

    async def create_record(body: dict):
        return await _call_api(f"{basename}-list", "POST", body=body)

    async def update_record(id: int, body: dict):
        return await _call_api(f"{basename}-detail", "PUT", pk=id, body=body)

    async def delete_record(id: int):
        return await _call_api(f"{basename}-detail", "DELETE", pk=id)

    tools = {
        "list": ("List", list_records),
        "create": ("Create", create_record),
        "update": ("Update", update_record),
        "destroy": ("Delete", delete_record),
    }
    for action in actions:
        label, handler = tools[action]
        mcp_server.add_tool(
            handler,
            name=f"{viewset.__name__}_{label}Tool",
            description=f"{label} {resource.replace('_', ' ')} using the Paperless API.",
        )


def register_api_tools(router):
    collections = {}
    for resource, viewset, basename in router.registry:
        if resource in API_TOOLS:
            _register_viewset(viewset, basename, resource, API_TOOLS[resource])
            collections[resource] = f"{basename}-list"

    async def query_data_collections(
        collection: str,
        filters: dict[str, str | int | list[str]] | None = None,
    ):
        if collection == "note":
            document_id = (filters or {}).get("document")
            if not isinstance(document_id, int):
                raise ValueError(
                    "For notes, supply the integer document ID in filters.document.",
                )
            return await _call_api("document-notes", pk=document_id)
        if collection not in collections:
            raise ValueError(f"Available collections: {', '.join(collections)}, note")
        return await _call_api(collections[collection], params=filters)

    async def search_documents(
        query: str | None = None,
        more_like_id: int | None = None,
        fields: list[str] | None = None,
        page: int = 1,
        page_size: int = 25,
        *,
        full_perms: bool | None = None,
    ):
        if bool(query) == (more_like_id is not None):
            raise ValueError("Supply exactly one of query and more_like_id.")
        params = {"page": page, "page_size": page_size}
        if query:
            params["query"] = query
        else:
            params["more_like_id"] = more_like_id
        if fields:
            params["fields"] = ",".join(fields)
        if full_perms is not None:
            params["full_perms"] = str(full_perms).lower()
        return await _call_api(collections["documents"], params=params)

    mcp_server.add_tool(
        query_data_collections,
        description=(
            "Query a collection with Paperless REST API filters, ordering and pagination. "
            f"Collections: {', '.join(collections)}, note. For note, supply filters.document."
        ),
    )
    mcp_server.add_tool(
        search_documents,
        description="Search the full-text document index with a query or a similar document ID.",
    )
