"""Document API resources published through MCP, with their supported actions."""

DOCUMENT_TOOLS = {
    "correspondents": ("list", "create", "update", "destroy"),
    "tags": ("list", "create", "update", "destroy"),
    "documents": ("list", "update", "destroy"),
    "document_types": ("list", "create", "update", "destroy"),
    "storage_paths": ("list", "create", "update", "destroy"),
    "saved_views": ("list", "create", "update", "destroy"),
    "share_links": ("list", "create", "destroy"),
    "workflow_triggers": ("list", "create", "update", "destroy"),
    "workflow_actions": ("list", "create", "update", "destroy"),
    "workflows": ("list", "create", "update", "destroy"),
    "custom_fields": ("list", "create", "update", "destroy"),
    "tasks": ("list",),
}
