"""Serve the Arizona 511 tools over MCP, so Claude Desktop or Claude Code can call them.

    pip install "mcp>=2"            # or mcp 1.x: the import below falls back to FastMCP

Claude Code:     claude mcp add az511 -e AZ511_KEY=<your key> -- python /full/path/to/az511_mcp_server.py
Claude Desktop:  add to claude_desktop_config.json (Settings > Developer > Edit Config):
    {"mcpServers": {"az511": {"command": "python", "args": ["/full/path/to/az511_mcp_server.py"],
                              "env": {"AZ511_KEY": "<your key>"}}}}

The key goes to the server process, not to the model: the tools add it to each request and never print it.
All ten tools only read, and are marked read-only, so a client can let them run without asking.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import az511_tools as T

try:
    from mcp.server.mcpserver import MCPServer as Server, Image      # mcp 2.x
except ImportError:
    from mcp.server.fastmcp import FastMCP as Server, Image          # mcp 1.x
from mcp.types import ToolAnnotations

server = Server('az511', instructions=(
    'Live Arizona highway conditions from AZ511, run by ADOT: road events, statewide alerts, message signs, '
    'road weather stations, rest areas with truck parking, cameras and their live pictures, work zones (WZDx), a '
    'briefing for a trip along one highway, and the cameras around a reported event. Times are Arizona '
    'time (MST, no daylight saving). Everything is reported by ADOT and can lag the road by minutes; say '
    '"reported", and say "unknown" when a field is not reported.'))

def look_at_camera(view_id: int):
    """Over MCP the picture itself goes back with the text, so a model that can see images can look at it."""
    text = T.look_at_camera(view_id)
    if text.startswith('Error'):
        return text
    try:
        data, _ = T._camera_image(view_id)          # cached: the same picture the text describes
    except Exception as e:
        return f'{text}\nError: the picture could not be read: {e}'
    return [text, Image(data=data, format='jpeg')]


for fn in T.TOOLS:
    run = look_at_camera if fn is T.look_at_camera else fn
    kw = dict(name=fn.__name__, description=fn.__doc__,
              annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, openWorldHint=True))
    try:
        server.add_tool(run, structured_output=False, **kw)
    except TypeError:                                # older mcp 1.x: no structured_output
        server.add_tool(run, **kw)

if __name__ == '__main__':
    server.run()
