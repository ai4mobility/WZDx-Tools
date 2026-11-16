"""Serve the toolkit's five tools and yours over MCP, from one server, so Claude Desktop or Claude Code can call them.

    pip install "mcp>=2"
    python contrib/<you>/server.py           # starts and waits: a client (Claude) talks to it over stdin/stdout

Claude Code (in a terminal):
    claude mcp add wzdx-<you> -- python /full/path/to/WZDx-Tools/contrib/<you>/server.py
Claude Desktop: Settings > Developer > Edit Config, then add to claude_desktop_config.json
    {"mcpServers": {"wzdx-<you>": {"command": "python",
                                   "args": ["/full/path/to/WZDx-Tools/contrib/<you>/server.py"]}}}
To use the saved snapshot instead of the live feeds, add to that entry
    "env": {"WZDX_SNAPSHOT": "/full/path/to/WZDx-Tools/snapshots/2026-11-05", "WZDX_NOW": "1793888460"}

What you decide here, for your own tools (contrib/check.py checks the first one and the ABLATION switch):
  1. annotations: read-only or not, and whether the tool reaches outside (openWorldHint: these read public feeds)
  2. INSTRUCTIONS: what the model must know before it calls any tool. The client gives it to the model once, at
     the start. Say what your tools add and when to use them instead of the toolkit's.
Nothing may print to stdout: over stdio, stdout carries the protocol. Use print(..., file=sys.stderr) to debug.
"""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(HERE, '..', '..'))
import wzdx_tools as T          # the toolkit
import tools as mine            # your tools.py

try:
    from mcp.server.mcpserver import MCPServer as Server      # mcp 2.x
except ImportError:
    from mcp.server.fastmcp import FastMCP as Server          # mcp 1.x
from mcp.types import ToolAnnotations

# The ablation (contrib/ablation.py) sets ABLATION for each run; keep this switch working:
#   full     your tools, your descriptions and your instructions (the default, and what Claude sees)
#   plain    your tools, but what the model reads has no transportation knowledge: mine.PLAIN_DESCRIPTIONS for the
#            descriptions, mine.RAW_RESULTS for the results, and none of your instructions
#   without  the toolkit only
ABLATION = os.environ.get('ABLATION', 'full')

TOOLKIT_INSTRUCTIONS = (
    'Work zones from public WZDx feeds (USDOT format): Florida (FL, FDOT via One.network), Arizona (AZ) and others '
    'from list_feeds. Times are local. Most work zones do not report lane impact and none has a verified position: '
    'say "unknown" and "reported", never "open" or "confirmed". No reported work zone does not mean none exists.')
MY_INSTRUCTIONS = (
    "If the user gives a work zone ID and asks about walking directions, call get_pedestrian_detour_info first. "
    "Pass the ID exactly as written, including any -R suffix. This lookup only needs the feed and ID. "
    "Use find_sidewalk_closures to discover an ID when the user supplies a street and coordinates. Never guess coordinates. "
    "Distinguish an estimated project end from a confirmed reopening. Mention gaps in the report. "
    "These tools cannot calculate a walking time or establish that an alternate path is safe.")
INSTRUCTIONS = TOOLKIT_INSTRUCTIONS + (' ' + MY_INSTRUCTIONS if ABLATION == 'full' else '')

server = Server('wzdx-' + os.path.basename(HERE), instructions=INSTRUCTIONS)

# structured_output=False: the result goes back as text only (otherwise the SDK sends the same text twice)
for fn in T.TOOLS:                                             # the toolkit's tools, unchanged
    server.add_tool(fn, name=fn.__name__, description=fn.__doc__, structured_output=False,
                    annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, openWorldHint=True))

if ABLATION != 'without':
    for fn in mine.TOOLS:                                      # yours
        desc = mine.PLAIN_DESCRIPTIONS[fn.__name__] if ABLATION == 'plain' else ' '.join(fn.__doc__.split())
        run = mine.RAW_RESULTS[fn.__name__] if ABLATION == 'plain' else fn
        server.add_tool(run, name=fn.__name__, description=desc, structured_output=False,
                        annotations=ToolAnnotations(readOnlyHint=fn.__name__ in mine.READ_ONLY,
                                                    destructiveHint=False, openWorldHint=True))

if __name__ == '__main__':
    server.run()
