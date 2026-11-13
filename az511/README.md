# az511: Arizona 511 as tools for AI agents

Ten read-only tools over ADOT's Arizona 511 developer API, and an MCP server that serves them to Claude Desktop,
Claude Code or any MCP client. Seven read one feed each; `get_trip_briefing` combines six of them for one trip;
`get_event_cameras` and `look_at_camera` let a model that can see images check a reported event on ADOT's cameras.

**Not part of Assignment 5.1.** The assignment's toolkit is `wzdx_tools.py` in the folder above, and nothing here
changes it. This folder shows what a larger set of tools can do with traffic engineering knowledge built in: which
camera is upstream of a crash, which signs face the driver, which rest area is on the driver's side. It needs a free
AZ511 developer key for live data; the tests run without one.

| File | What it is |
|---|---|
| `az511_tools.py` | the ten tools (plain Python, standard library only); each docstring is what the model reads |
| `az511_mcp_server.py` | serves them over MCP (`pip install "mcp>=2"`; falls back to mcp 1.x) |
| `test_az511.py` | 67 offline checks; `mcp` starts the server and calls it as a client would (72) |
| `fixtures/` | the sample responses printed in ADOT's API documentation, and the first 400 work zones of the Nov 5 2026 WZDx snapshot |
| `fixtures_trip/` | SYNTHETIC data for the trip and camera tests: a made-up I-17 trip, and three made-up crashes with cameras around them (real places, road names and milepost directions; invented events and picture) |

## The tools

| Tool | Question it answers |
|---|---|
| `get_road_events` | What incidents, closures and roadwork are on this road or near this point? |
| `get_alerts` | Which traveler alerts are active now (major closures, weather, special events)? |
| `get_message_signs` | What do the message signs on this road say now? |
| `get_road_weather` | What do road-weather stations near this point report (air and pavement temperature, wind, grip)? |
| `get_rest_areas` | Which rest areas are open, and how many truck spaces are free? |
| `get_cameras` | Which cameras are on this road or near this point? |
| `get_work_zones` | What work zones does ADOT's WZDx feed list here? (no key needed) |
| `get_trip_briefing` | I'm driving this road from A to B: what will I meet, in order? |
| `get_event_cameras` | Which cameras are upstream of, at, and downstream of this event? |
| `look_at_camera` | What does this camera show right now? (the picture itself, over MCP) |

## Get a key (free)

Sign in at az511.com, open Developers (https://az511.com/developers/doc) and request a key. Put it in the
environment variable `AZ511_KEY`, or in a one-line file `.secrets/az511_key.txt` at the top of this repository
(git ignores `.secrets/`). Never put a key in a notebook, a commit or a pull request. The work-zone feed and the
camera pictures need no key. AZ511 allows 10 calls per 60 s; the tools cache each endpoint for 60 s.

## Run it

```
python az511/test_az511.py mcp                     # offline checks, then the MCP server as a client would call it
python az511/az511_tools.py demo                   # a short tour (live: needs the key)
python az511/az511_tools.py trip                   # the trip briefing: I-17 north, Phoenix to Flagstaff (live)
claude mcp add az511 -e AZ511_KEY=<your key> -- python /full/path/to/az511/az511_mcp_server.py      # Claude Code
```
Claude Desktop: Settings > Developer > Edit Config, then add
`{"mcpServers": {"az511": {"command": "python", "args": ["/full/path/to/az511/az511_mcp_server.py"], "env": {"AZ511_KEY": "<your key>"}}}}`

## The trip briefing (`get_trip_briefing`)

"I'm driving I-17 from Phoenix to Flagstaff: what's on the way?" The tool takes a road and the trip's start and
end points, and lists, in the order the driver meets them: events in the driver's direction or both, message signs
facing the driver, road weather within 5 mi of the road, and rest areas on the driver's side. Full closures and
freezing pavement come first, in a "Most important" line. Left out and counted: the other direction, events past
their planned end, events not started yet, and the other side's rest areas. Signs that show only travel times are
summed up in one line.

What the live feed showed (Nov 12 2026, 2,911 events):
- The direction is in AZ511's direction field for only 17% of events; another 10% give it only in the road name
  ("I-17 Northbound") or the description; 73% do not say. The tool reads all three places and lists the rest
  apart, as "direction not reported", because they may be on the driver's side.
- Blank message signs report the text "NO_MESSAGE"; most lit signs on I-17 show only travel times.
- A rest area's side of the road is in its name: "McGuireville Rest Area (SB)", "Sunset Point Rest Area (SB/NB)".
- 18% of events are roadwork past its planned end, some by years, still "updated minutes ago".

## Cameras around an event (`get_event_cameras`, `look_at_camera`)

"Is the crash on I-10 at 24th St real, and is traffic backing up?" `get_event_cameras(event_id)` lists the cameras
on the event's road, split into upstream (where the traffic comes from), at the event, and downstream, with each
view's id, ADOT label and link; cameras on other roads nearby come last. `look_at_camera(view_id)` sends the
picture itself over MCP, with its label and the time it was fetched, so the model can look at it. The pictures
(`https://az511.com/map/Cctv/<view_id>`, 1920 x 1080 JPEG) need no key.

What live data showed (Nov 12 2026):
- Upstream follows the mileposts, and the tool works out which way they increase from the cameras' own positions:
  usually north and east, but on Loop 202's Santan Freeway they increase westward. The tool names that way on a
  16-point compass, because roads bend away from their signed direction: I-10 through Tucson is signed eastbound
  but runs south-southeast.
- Phoenix's loops are state routes: events say "202-LOOP", cameras say "SR-202". The tools treat both as `L-202`.
- Events give whole-number mileposts ("MP 144"), so the cross street they are reported "near" places them better:
  the "@5th Ave" camera sits at milepost 144.8 for a crash "Near 5th Ave HOV (MP 144)".
- A view's label (NB/SB/EB/WB/NA) may name the side of the road, not the view: a camera labelled EB showed
  westbound traffic, judging by the exit signs facing it. Check the picture.
- Time stamps on pictures differ: one I-10 camera's stamp read an hour behind Arizona time.
- One picture cannot confirm a crash, or that it has cleared. A queue upstream with traffic moving downstream
  points to a bottleneck between the two cameras.

## Design decisions (and the test that holds each)

- Arizona time is MST all year (`America/Phoenix`); the Navajo Nation's daylight saving time is not handled.
- A date shows its year when it is not this year, and a planned end in the past is marked "(already passed)".
- Direction of travel follows U.S. route numbering: odd routes are signed north-south, even routes east-west;
  loops take the trip's heading.
- "NO_MESSAGE" on a sign is a blank sign; "No Data" truck spaces are "availability not reported".
- WZDx lanes are counted from the left with shoulders included; the tools say "right 2 lanes of 3 closed".
- The WZDx feed sends no status, so a work zone past its planned end is counted and left out, not called
  finished; its direction "undefined" is written "direction not reported".
- "No Data", null directions and unknown impacts are written as "not reported" or "unknown", never guessed.
- Limits carry the documented units (ft, tons, mph); wind speed gets none, because AZ511 states none.
- Each endpoint is cached 60 s; a call that would pass 9 calls in 60 s returns an error text instead.
- Errors never include the request address, because it carries the key (checked with a fake key).
- All ten tools are marked read-only (MCP `readOnlyHint`). The trip briefing makes 6 calls, within the limit.
