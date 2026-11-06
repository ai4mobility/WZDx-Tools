# WZDx-Tools: work zones as tools for AI agents

Tools an AI agent can call to read public work-zone feeds in WZDx (Work Zone Data Exchange, the USDOT format),
written the way a transportation engineer would write them, with tests for every claim their descriptions make, and
an MCP server that serves them to Claude Desktop, Claude Code or any MCP client. Built for **AI for Mobility**
(CGN 6933, University of South Florida), and open to anyone.

Florida is the main case: FDOT's statewide feed, hosted by One.network, which crews, cities, counties and
contractors update. Arizona's AZ511 feed is the second.

**Want to write your own tool?** Read [`WRITING_TOOLS.md`](WRITING_TOOLS.md), then
[`contrib/README.md`](contrib/README.md): each contribution is one folder, `contrib/<your-github-username>/`, sent as
a pull request. Students in AI for Mobility: this is Assignment 6.

## Quick start

```
pip install -r requirements.txt
python test_wzdx.py                                    # the toolkit's checks, offline
python test_wzdx.py mcp                                # also starts the MCP server and calls it as a client would
python contrib/_template/test_tools.py                 # the template contribution's tests
WZDX_SNAPSHOT=snapshots/2026-11-05 python wzdx_tools.py demo FL
```

The tools use only the Python standard library; `mcp` is needed for the server, and `torch` and `transformers` only
for `contrib/agent_loop.py`.

| File | What it is |
|---|---|
| `wzdx_tools.py` | the five toolkit tools; each docstring is what the model reads |
| `wzdx_mcp_server.py` | serves them over MCP (`pip install "mcp>=2"`; falls back to mcp 1.x) |
| `test_wzdx.py` | offline checks on `fixtures/` |
| `fixtures/` | a Tampa-area slice of FDOT's feed (work zones within 8 mi of USF, one Miami work zone and its detours), 400 Arizona work zones, USDOT's feed registry with URL query strings removed |
| `snapshots/2026-11-05/` | both feeds in full as read on Nov 5 2026 (Florida 09:21 EST, Arizona 06:53 MST), and the registry: the data every contribution is tested on |
| `contrib/` | contributions, the template, `check.py` (what a pull request must pass) and `agent_loop.py` (watch a model use your tools) |

## The tools

| Tool | Question it answers |
|---|---|
| `list_feeds(state)` | Which public work-zone feeds exist, and which are open? (USDOT registry) |
| `get_work_zones(feed, road, near_lat, near_lon, radius_mi, status)` | What work is on this road or near this point? |
| `check_location(feed, lat, lon, radius_mi=0.5)` | Is the vehicle in or near a reported work zone? (dashcam, ADAS) |
| `get_detours(feed, work_zone_id)` | Which detour routes are posted for this work zone? (Florida) |
| `feed_quality(feed)` | How complete is this feed right now? |

`feed` is `FL`, `AZ`, or a name from `list_feeds`. No feed address or key is written in the code: addresses come
from the registry at run time, and feeds the registry marks as needing a key are refused. To read the saved
snapshot instead of the live feeds, set `WZDX_SNAPSHOT=snapshots/2026-11-05` and `WZDX_NOW=1793888460` (the time
the Florida feed was read).

## Use it from Claude

```
claude mcp add wzdx -- python /full/path/to/wzdx_mcp_server.py                      # Claude Code
```
Claude Desktop: Settings > Developer > Edit Config, then add
`{"mcpServers": {"wzdx": {"command": "python", "args": ["/full/path/to/wzdx_mcp_server.py"]}}}`

Florida's feed is 1.7 MB as sent (gzip) and 106 MB unpacked; 94% of it is detour route geometry. The server parses
it in about 2 s with about 1.1 GB peak memory, keeps the work zones, drops the detour geometry, and caches for 5
minutes.

## What Florida's feed said on Nov 5 2026, 09:21 EST (`feed_quality('FL')`)

- 28,429 features: 3,109 work zones and 25,320 detour routes (each detour linked to one work zone)
- work zones by status: active 1,334, completed 1,056, pending 719 (WZDx 4.2 `event_status`)
- lane impact unknown for 2,994 (96%); start position verified for 0; start date verified for 595 (19%)
- no road name for 688 (22%); FDOT construction projects name the road only in the description
- lane-by-lane detail 31, workers reported 48, reduced speed limit 16
- reported by: Plant City 1,712, Florida DOT 547, ELGIN 325, City of Tampa 195, Hillsborough County 46, contractors
- 37 active work zones within 5 mi of USF, most of them City of Tampa permits (sidewalk closures, sewer work);
  one lane closure on East Busch Boulevard (the right travel lane of 3)

Arizona (az511, WZDx 4.1, 06:53 MST): 3,443 work zones, lane impact unknown for 2,351 (68%), lane detail for 1,094,
reduced speed for 332, no detours.

## Design decisions (and the test that holds each)

- Roads: 'I 75' = 'I-75' but not I-275; 'FL 434' = 'SR 434'. Street names match as plain text, so 'Busch Blvd'
  finds only a record whose name field happens to say 'E Busch Blvd', and misses the one that says 'East Busch
  Boulevard' (the record with the lane closure): the template contribution shows how to do better.
- Lanes: WZDx numbers lanes from the left (order 1 = left-most) and lists shoulders as lanes, so the Busch Boulevard
  record's 'lane 4 of 5 closed' is written 'right lane of 3 closed'.
- Speed: WZDx stores km/h; the tools give mph (72.42 km/h -> 45 mph).
- Time: Florida is Eastern except the panhandle west of the Apalachicola River (Central), approximated by
  longitude < -85.0 (Gulf County is split; not handled). Arizona is MST all year. Dates in another year show the year.
- Status: WZDx 4.2 `event_status` when present (Florida lists completed work zones), otherwise the dates.
- Honesty: 'lane impact unknown (not reported)', 'position not verified'; no reported work zone is "not proof there
  is none: trust the camera".

## Licenses

Code: MIT ([`LICENSE`](LICENSE)). Data: see [`DATA_LICENSE.md`](DATA_LICENSE.md). The structure of the course's
agents unit follows CMU 11-768 AI Agents (Fried and Neubig, Fall 2026); no CMU material is copied.
