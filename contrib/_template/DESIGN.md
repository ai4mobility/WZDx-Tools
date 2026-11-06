# Design: work_zones_on_street

*This describes the template's example tool. Write your own in your own words: this file is where your
transportation knowledge and your thinking show, and it is not written with AI (see the assignment page). The
checker reads the four section titles, so keep them.*

## 1. The task

<!-- What task are you asking the agent to do? Who asks, in what words, what decision depends on the answer, how
often, and how is it done today without AI? Give two or three questions exactly as that person would ask them. -->

The person is a traffic operations analyst at the City of Tampa, or a dispatcher, who hears about a street and has
to decide whether to send a crew, warn a bus route or tell a caller what to expect. They ask by street name, several
times a day, and they need the answer in under a minute. Today they open FL511's map, zoom to the street, and click
each icon. Questions in their words:

- "Is anything going on along Busch Blvd near USF right now? Which lanes?"
- "Is 30th St blocked anywhere between Fletcher and Fowler today?"
- "Is the work on Bearss Ave still going, and until when?"

The answer they need is a list of works on that street, with direction, lanes and end time, and an honest
"the feed does not say" where it does not.

## 2. The tools

<!-- Which tools did you design for that task, and why these? For each tool: the question it answers, what it
returns, and why it is useful to the person in section 1: what transportation knowledge it carries that the raw
data or the toolkit lacks (point to your rules in KNOWLEDGE.md by number). Why did you split the work this way, and
what did you leave out? -->

One tool, `work_zones_on_street`, answers "what work is on this street near this place?" It returns each active
work on the street, with its records' directions, lane impact, closed lanes, end time and reporter.

The toolkit already has `get_work_zones(road=...)`, but it matches names as plain text. For "Busch Blvd" it finds
only the record whose name field happens to say "E Busch Blvd". It misses the record that says "East Busch
Boulevard", which is the one with the only lane closure near campus. The
new tool carries what a person who works with addresses and permits knows. Street names come in several spellings
(rule 1). One field can hold two streets and a city (rule 2). The same name exists in other cities (rule 3). One
permit appears as several records, one per segment and direction (rule 4). "Unknown" is not "open" (rule 5). And
records with no street name cannot be found by name at all (rule 6).

I asked for a point and a radius instead of a city name because WZDx has no city field and the city appears in only
some road names, while every record has coordinates. I left route numbers out: `get_work_zones` already handles "I-275" and "SR 580"
well, so the tool sends the model there instead of duplicating it.

## 3. The descriptions

<!-- How does each description help the model pick the right tool and fill in its inputs? Quote the sentences that
do the work and explain each one: the words a person would use, when to use it instead of a toolkit tool, input
names and units, what it refuses and where to go instead. Use your transcripts: which sentence did the model's
reasoning pick up, and what did you change? -->

The description of `work_zones_on_street` starts with the job, "Active work on one street near a place, counted as works rather than
records", so a model that reads "street" in a question sees a match before it reads the details.

"a street name as people say it ('Busch Blvd', 'N 30th St', 'Fowler Avenue')" gives examples in the person's
spelling, so the model passes the street as the person said it instead of guessing FDOT's spelling.

"because street names repeat across a state" explains why the point is required. A model that knows the reason
supplies the coordinates instead of leaving them out.

"'Lane impact not reported' means the feed does not say; it does not mean the lanes are open" is aimed at the most
likely misreading. It is in the description because the model reads it before it sees any result.

"For route numbers (I-75, SR 580, US 41) use get_work_zones" draws the line between this tool and the toolkit's, so
the model does not call the wrong one for an interstate.

In `examples/agent_loop/example_busch.md` the model's reasoning says this tool "is designed for this exact
purpose". The question never names a feed, so the model took "FL" from the description's own list ("feed: 'FL',
'AZ' or a name from list_feeds"). All five inputs were right on the first try.

## 4. The results

<!-- How is each result written so the model reads it correctly? Quote a real result and explain each part: units,
the verdict stated either way, definitions (a work vs. a record), unknowns said as unknown, warnings. Use your
transcripts: where did the model read it right, where did it read it wrong, and what would you change? -->

The first line of a `work_zones_on_street` result states the scope and the verdict together: "Busch Blvd within 5 mi of (28.0587, -82.4139), fldot
feed updated Thu Nov 5 09:21 EST". The model can repeat the place, the radius and the feed's time, so the person
knows how fresh the answer is. The count follows either way, even when it is zero.

Each record is one line: "eastbound: some lanes closed, right lane of 3 closed · until Thu Nov 5 16:00 EST". The
lane is in a driver's words, not WZDx's lane order, and the time is local, not UTC.

A record with nothing reported says so in the same place: "direction not reported: lane impact not reported". The
model sees the gap instead of a missing field it could fill.

The last line names what the search cannot see and how to see it: "To see them, call get_work_zones with near_lat,
near_lon and radius_mi."

The example run shows two misreadings. The model called the work "1 record", although the result says "1 active
work(s) on the street, from 2 record(s)". The "(s)" makes "work" and "record" look alike. It also merged the two
records into one line. Next I would write "1 work, reported as 2 records" and label each record line "record 1 of
2".
