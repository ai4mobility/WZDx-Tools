# An example run of contrib/agent_loop.py

`example_busch.md` is one question run through the whole loop with the template's server
(`contrib/_template/server.py`) on the Nov 5 2026 snapshot:

    WZDX_SNAPSHOT=snapshots/2026-11-05 WZDX_NOW=1793888460 \
    python contrib/agent_loop.py contrib/_template/server.py \
      "Is any work reported on Busch Blvd near USF (28.0587, -82.4139) right now, and which lanes are closed?" \
      --name example_busch

Qwen3-1.7B, thinking on, seed 1, on a 2-core cloud CPU with no GPU: two model turns, one tool call, 5.1 minutes
in all. `example_busch.json` holds the same run in full.

Read it in order: the MCP handshake and `tools/list`; the tool list as the model receives it; the whole prompt of
step 1; the model's reasoning and its `<tool_call>`; the harness's check and the `tools/call` request and response;
then step 2, where the model reads its own reasoning, its call and the `<tool_response>`, and answers.

Grade the answer yourself before you read on. It gets the closure right (eastbound, the right lane of 3, until
4 pm) but calls the work "1 record" where the tool said 1 work from 2 records, and it puts "lane impact not reported"
and "right lane of 3 closed" on one line, as if they were the same record. Partly correct: and the result text is
where a fix would start.
