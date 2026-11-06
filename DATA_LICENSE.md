# Data

The files in `snapshots/` and `fixtures/` are copies of public work-zone feeds, kept so that every test, and every
contribution, gives the same answer on any computer. They belong to their publishers.

- `snapshots/2026-11-05/fldot.json.gz`: the Florida Department of Transportation's statewide WZDx feed (WZDx 4.2,
  hosted by One.network), read on Nov 5 2026 at 09:21 EST from the address listed in USDOT's public WZDx feed
  registry, saved as served.
- `snapshots/2026-11-05/az511.json.gz`: the Arizona Department of Transportation's AZ511 WZDx feed (WZDx 4.1),
  read on Nov 5 2026 at 06:53 MST from az511.com/api/wzdx (documented at az511.com/developers/doc).
- `snapshots/2026-11-05/registry.json` and `fixtures/registry.json`: USDOT's WZDx feed registry
  (datahub.transportation.gov, dataset 69qe-yiui), with every URL query string removed.
- `fixtures/fldot.json.gz` and `fixtures/az511.json`: slices of the two feeds above (see `test_wzdx.py`).

They are here for teaching and testing. Before you reuse them anywhere else, check each publisher's terms of use.
Do not add other data to this repository unless you have the right to share it.
