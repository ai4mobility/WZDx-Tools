# Writing work-zone tools for AI agents: a guide for transportation engineers

This guide is for you if you know transportation engineering but have not built anything for AI. By the end you
will be able to take something you know about work zones, streets, lanes or traffic, and turn it into a tool that
an AI model can call and use correctly. The worked example is `contrib/_template/`, read alongside this guide.

## 1. Why the AI needs you

A model that answers a work-zone question never sees the feed, the map or your code. It sees two pieces of text:
the tool's **description**, which tells it what the tool does, and the tool's **result**, the text your function
sends back. Everything it knows about the work zones comes through those two texts.

A feed's documentation can tell a model which field holds what. It cannot tell it what the fields mean on the
street. On FDOT's feed of Nov 5 2026 (`snapshots/2026-11-05/`):

| What a transportation engineer knows | What happens when a tool leaves it out |
|---|---|
| 'Unknown' is not 'open' | 96% of the work zones say `vehicle_impact: unknown`; a model reads silence as open lanes |
| WZDx counts lanes from the left and lists shoulders as lanes | The Busch Blvd record in FDOT's feed has lane 4 of 5 closed; it is the right travel lane of 3 |
| People write street names many ways | A text search for 'Busch Blvd' finds only the record whose name field says 'E Busch Blvd', with no lane data; it misses the record with the closed lane, which says 'East Busch Boulevard' |
| One work is reported as several records | 30th St near USF has 4 records and 2 works |
| A name is not a place | The feed has an East 109th Avenue in Tampa and a Southwest 109th Avenue 200 mi away |
| A permit is not a crew on site | The dates are the window a permit allows, not the hours anyone works |

If you can explain a work zone to a new engineer on your team, you can write a tool.

## 2. How a model uses a tool

1. The model gets a **menu**: for each tool, a name, a description and its inputs (a JSON schema).
2. It reads the menu and the question, and writes a request as text, for example
   `{"name": "work_zones_on_street", "arguments": {"feed": "FL", "street": "Busch Blvd", ...}}`. Writing it runs
   nothing.
3. A program called the **harness** finds the request, checks it, and asks the **MCP server** to run it.
4. Your function runs and returns a short text.
5. The text goes back to the model, which decides what to do next: call another tool, or answer.

`contrib/agent_loop.py` shows each of these steps for a real model on your own computer: the prompt it reads, its
reasoning, the call it writes, the MCP messages, and the result. Run it once on the template before you write
anything (step 7 of `contrib/README.md`).

## 3. Read the data before you design

```
python -c "import os; os.environ['WZDX_SNAPSHOT']='snapshots/2026-11-05'; import wzdx_tools as T; print(T.feed_quality('FL'))"
```

Then open a few raw records. Which fields are filled in, and how often? What does a record from a city permit look
like next to one from an FDOT project? A tool can only be as good as the fields it reads, so design around what is
there, and say plainly what is not. `T._load('FL')['wz']` is the list of work-zone records (GeoJSON features).

## 4. From knowledge to a rule, to code, to a test

Every rule in your knowledge card takes the same four steps. The template's first rule:

| Step | The template's rule 1 |
|---|---|
| What you know | Street suffixes and directions are written several ways |
| The source | USPS Publication 28, Appendix C1; the FDOT feed itself |
| The code | `SUFFIX`, `DIRECTION`, `_street_parts`, `_matches` |
| The test | `test_suffix_and_direction_forms`: 'Busch Blvd' finds 'East Busch Boulevard'; '50th St' does not find 'Northeast 150th Street' |

A rule that is only in the description is a hope. Put it in the code, so the result is right whatever the model
does, and test it on a real record.

Sources you can cite: the WZDx specification; the MUTCD (Part 6 covers temporary traffic control); the HCM (work-zone
capacity); FDOT's Standard Plans (Index 102-600 series, temporary traffic control) and its lane closure practice; USPS
Publication 28 for addresses; a paper; the data itself (say which snapshot and which records); and field practice
you can describe. Cite the section, not just the title.

## 5. Writing the description

The description is the docstring of your function. Answer these questions in it, in plain words:

1. What does it return, and in what units (mph, miles, local time)?
2. When is the answer partial or unknown (lane impact not reported, no road name, position not verified)?
3. Which definition does it use (a work or a record; active by the feed's status or by the dates)?
4. Does it only read? Say "Read-only." Every WZDx tool here only reads.
5. What will it refuse, and what should the model do instead (a route number: use get_work_zones)?
6. How much evidence is behind it (reported, not verified; the feed's update time)?
7. Who must confirm before the result is used (a closure shown to the public needs the agency's confirmation)?

Name the inputs the way people talk ('Busch Blvd', a point and a radius in miles), not the way the feed stores them.

## 6. Writing the result

- A few labelled numbers with units, not raw JSON. The model reads every word of every result at every step.
- Say the verdict either way: "0 active works on the street" is an answer; an empty string is not.
- Say what the tool could not see ("5 active records within 5 mi have no street name").
- Errors are results too: say what went wrong and what to send instead.

## 7. The plain version, and why it is required

Write `<tool>_plain` first: the same question answered the way you would without your knowledge, usually a direct
reading of the fields. It is not served to the model. `test_plain_vs_<tool>` runs both on the same real case and
shows the difference. A result without a baseline is not a result: the plain version is how a reader of your pull
request sees what your knowledge is worth.

## 8. Serve it over MCP

`server.py` puts the toolkit's tools and yours on one MCP server. MCP (Model Context Protocol) is the standard way
a client such as Claude Desktop, Claude Code or `agent_loop.py` finds tools and calls them: `tools/list` returns the
menu, `tools/call` runs one. Mark read-only tools read-only, and write the server's instructions: the client gives
them to the model before the first question, so say what your tools add and when to use them.

## 9. Watch a model use your tool, and fix what you see

| What you see in the transcript | Where to fix it |
|---|---|
| The model never calls your tool | The description: what the tool is for and when to use it; the server's instructions |
| It calls with the wrong inputs (an id, the wrong units, a missing point) | The input names and descriptions; an error that says what to send |
| It goes around in circles in its reasoning | The description or an error: give it what it is missing, or a way to get it |
| It concludes something the result does not support | The result: the verdict either way, and what the data cannot tell |
| It reads 'unknown' as 'open' | The result text, and the server's instructions |

Fix the tool first: a better tool helps every model and every client.

## 10. Ideas

The transportation knowledge is the hard part of each of these. The Python is the easy part.

- **Peak-period conflicts.** Which reported lane closures are active during the AM or PM peak, in local time, on
  arterials versus local streets? Say where the peak periods come from.
- **What a closure does to capacity.** From the lanes closed and the facility type, an estimate of the capacity
  left, with the method and its limits (the HCM has a work-zone capacity method for freeways).
- **Ahead of me, on my side.** For a dashcam or ADAS agent: given a position, a heading and a speed, which reported
  work zones lie ahead in the direction of travel, how far, and in how many seconds.
- **Sidewalk closures and pedestrians.** Which closures take a sidewalk near a school, a transit stop or campus, and
  whether the record says anything about an alternate route (MUTCD Part 6).
- **How much to trust a record.** Who reported it (FDOT project, county, city permit, contractor), whether its dates
  and position were verified, how long since the feed was updated: a confidence label with reasons.
- **Arizona versus Florida.** The same question on both feeds, with what each one fills in and leaves out.
- **Detours.** Florida links detours to their work zones (`get_detours`): which work zones have one, and how much
  longer it is (the geometry is in the raw snapshot; the toolkit drops it to save memory).

## 11. Measure what your work is worth: the ablation

A tool is a claim that the agent does the task better with it. Writing your knowledge into the description and the
result is a second claim: that the words the model reads matter, not only the code. `contrib/ablation.py` tests each
claim with one comparison, on your own three questions:

- **With and without your tools** (A vs. C): the toolkit alone, then your tools as written.
- **With and without the knowledge in what the model reads** (B vs. C): your tools find the same data both times,
  but in B the description is plain (`PLAIN_DESCRIPTIONS`), the result is raw (`RAW_RESULTS`), and your server
  instructions are left out.

In the worked example (`examples/ablation/`), the 1.7B model answered 1 of 3 questions right with the
toolkit alone and 2 of 3 with the new tools (the third partly right). With the plain descriptions it got none right,
because it never called the new tools: the words, not the code, decided whether the tool was used at all.

Write the questions and their right answers before you look at any run, and check each right answer against the
data. When a result goes against you, it is still a result: read the answers to find out why.

Questions and ideas are welcome as issues on this repository.
