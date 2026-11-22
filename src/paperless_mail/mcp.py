"""Mail API resources published through MCP, with their supported actions."""

MAIL_TOOLS = {
    "mail_accounts": ("list", "create", "update", "destroy"),
    "mail_rules": ("list", "create", "update", "destroy"),
    "processed_mail": ("list",),
}
