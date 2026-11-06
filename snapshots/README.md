# Snapshots

Each folder holds the feeds as read at one time, so that tests give the same answer on any computer and on any day.
Point the tools at one with two environment variables:

    WZDX_SNAPSHOT=snapshots/2026-11-05      # read <feed>.json.gz and registry.json from this folder
    WZDX_NOW=1793888460                     # "now" for the tools: Nov 5 2026 14:21 UTC (09:21 EST)

`2026-11-05/`: FDOT 09:21 EST (3,109 work zones, 25,320 detour routes), AZ511 06:53 MST (3,443 work zones), and
USDOT's feed registry. Sources and terms: `../DATA_LICENSE.md`.
