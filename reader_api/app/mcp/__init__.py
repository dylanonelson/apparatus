# Re-export everything from submodules
# External code should import from app.mcp, not from submodules directly

from app.mcp.wrapper import (
    MCPPromptName,
    MCPResourceURI,
    MCPToolName,
    call_mcp_server_with_api_auth,
    call_mcp_tool,
)
from app.mcp.mcp_server import create_mcp_server

__all__ = [
    "MCPPromptName",
    "MCPResourceURI",
    "MCPToolName",
    "call_mcp_server_with_api_auth",
    "call_mcp_tool",
    "create_mcp_server",
]
