"""Serve the work-zone tools over MCP, so Claude Desktop or Claude Code can call them.

    pip install "mcp>=2"            # or mcp 1.x: the import below falls back to FastMCP

Claude Code:     claude mcp add wzdx -- python /full/path/to/wzdx_mcp_server.py
Claude Desktop:  add to claude_desktop_config.json (Settings > Developer > Edit Config):
    {"mcpServers": {"wzdx": {"command": "python", "args": ["/full/path/to/wzdx_mcp_server.py"]}}}

No key is needed: the server reads only feeds that USDOT's registry lists as open. Loading Florida's feed takes a
few seconds and about 1 GB of memory once every 5 minutes (it is 106 MB unpacked; detour geometry is dropped).
All five tools only read, and are marked read-only.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import wzdx_tools as T

try:
    from mcp.server.mcpserver import MCPServer as Server      # mcp 2.x
except ImportError:
    from mcp.server.fastmcp import FastMCP as Server          # mcp 1.x
from mcp.types import ToolAnnotations

server = Server('wzdx', instructions=(
    'Work zones from public WZDx feeds (USDOT format): Florida (FL, FDOT via One.network), Arizona (AZ) and others '
    'from list_feeds. Times are local. Most work zones do not report lane impact and none has a verified position: '
    'say "unknown" and "reported", never "open" or "confirmed". No reported work zone does not mean none exists.'))

for fn in T.TOOLS:
    server.add_tool(fn, name=fn.__name__, description=fn.__doc__,
                    annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, openWorldHint=True))

if __name__ == '__main__':
    server.run()
