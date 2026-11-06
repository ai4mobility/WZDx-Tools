# Contributing

This repository is a place for work-zone tools that AI agents can trust. Students in AI for Mobility and anyone
else are welcome to add tools, better descriptions, feeds and snapshots.

## The one rule

**Every claim a tool description makes comes with a test.** A description is a promise to the model, and the model
cannot check it. If a sentence in a docstring is not tested, it is a guess.

## Adding your tools

Each contribution is one folder, `contrib/<your-github-username>/`, sent as one pull request. Read
[`WRITING_TOOLS.md`](WRITING_TOOLS.md), then follow [`contrib/README.md`](contrib/README.md). Before you open the
pull request, run

    python contrib/check.py contrib/<your-github-username>

The workflow runs it again on the pull request.

## Changing the toolkit

Fixes to `wzdx_tools.py`, `wzdx_mcp_server.py` or `test_wzdx.py` are welcome as their own pull request, separate from
a contribution folder. Run `python test_wzdx.py mcp` first. Say what transportation knowledge the change adds and
which check shows it.

## Data

Add a snapshot as a new folder in `snapshots/`, with a note in `DATA_LICENSE.md` saying where it came from and when.
Do not commit data you do not have the right to share, personal information, or a feed's API key.
