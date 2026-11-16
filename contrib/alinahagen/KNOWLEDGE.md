# Domain Knowledge
This card covers the tools work_zones_during_hours and lane_closure_traffic_impact.

## Rules

| Rule | Source | Test |
|------|--------|------|
| General travel lane closures are different from non-travel lanes. WZDx uses a LaneType field to distinguish travel lanes (general) from non-travel lanes (shoulder, parking, median, sidewalk, bike-lane). Closing a non-travel lane does not reduce vehicle throughput. Tools must check LaneType before assigning impact severity. | WZDx spec, spec-content/enumerated-types/LaneType.md | test_general_vs_nontravellane_types |
| WZDx records are independent and simultaneous closures should be noted. This tool groups records by proximity and time window and flags when more than one closure is active in the same area. Tools must count how many distinct work identifiers are present in the corridor and flag when that count exceeds one. | FDOT snapshot Nov 5 2026 — 7 simultaneous active work zone records within 0.5 mi of Kennedy Blvd between Armenia Ave and Howard Ave, Tampa | test_multiple_closures_flagged |
| Lane counts are the only severity proxy as WZDx does not have annual traffic data or historic traffic use for corridors. Tools must count closed lanes by type (using LaneType), report how many general travel lanes remain open, and state that severity is estimated from lane configuration alone. Do not infer traffic volume from road name or time of day. | WZDx spec, spec-content/enumerated-types/LaneStatus.md and spec-content/enumerated-types/LaneType.md | test_lane_count_reported_by_type |
| EventStatus limits which records are relevant. A record being present in the feed does not mean work is actively disrupting traffic. Tools must report EventStatus explicitly rather than treating all records as active closures, filtering for active and pending records only. Note: deprecated as of WZDx v4.1. | WZDx spec, spec-content/enumerated-types/EventStatus.md | test_event_status_filtering |

## Plain vs. yours
The plan descriptions are incredibly short, and don't really do much to explain what each task does. The longer descriptions outlines use case, input types, limitations, all of it. the plain descriptions are barely a sentence and only really outline the bare function of the tool, not even what it could be used to do. 


## What the data cannot tell
Very strictly, the data can't answer any temporal questions. It can't comment on how traffic flow will be impacted, or anything that would need historic traffic data. Any hint of this is not supported by the data this agent can access. 

## AI use

1. I choose Track W - I originally wanted to use SUMO, and considered asking Claude to help me with setting it up, as I originally wanted to do something with a simulation. However, I will be honest, I misread the due date for this assignment, and had less time then I had hoped to complete this assignment. So, I choose to do Track W as that seemed more manageable and I would need less AI assistance in understanding it. My original idea was to try and simulate what traffic impacts would happen if you shut down certain corridors for "pedestrian hours" (the idea of walkable cities). I couldn't do that with Track W, so I tried to do something similar with trying to estimate how bad it would be to close down roads based on what's already closed around it. (I specifically wanted to test closing things around meal times, like Lunch and Dinner)

2. I did use Claude to help me find where WZDx kept some of its data dictionaries. Once I found the enumerated-types tab on the Github, that got a lot easier. Claude made suggestion for my tools based on a slight misunderstanding I had -- I originally wanted to have the tool take into account what time the permit requester was setting for the permit, and determine if that was a high volume traffic time. This is not possible with the data WZDx has, and that was one misunderstanding I had.

3. I did use Claude to help with suggestions for some wording for some of the rules or tasks, but only after I had fully drafted the rules and knew what I wanted them to say. I will also fully admit I think I may have misread the AI allowance chart on where we could use it. I thought the chart said using AI to help with some rewording was okay, but I realize now after the case as I am writing this that I'm not sure it was. I just want to be upfront that I did use to to help with some of the wording my rules (this document), the docustring descriptions in tool.py, and in figuring out what some of the inputs for each tool needed to be.

5. All git commands and coding adjustments were done with Claude. One issue i ran into was having to set up a virtual environment on my machine, as for some reason my Mac, despite having Python 3.13, did not want to run this assignment as was. The virtual environment worked great though, but it did take some set up.

6. Other than the reported uses, Design.md and Ablation.md are my own work
