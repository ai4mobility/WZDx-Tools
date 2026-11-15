# Knowledge card: work-zone checks for crash diversions

The tests use the FDOT export in
`snapshots/2026-11-05/fldot.json.gz`, captured at 09:21 EST. Feature IDs refer to that snapshot.

## Rules

| # | Rule and effect on the result | Source | Where in tools.py | Test |
|---|---|---|---|---|
| 1 | A lane restriction applies to its reported direction of travel. For a directional query, return matching records and separately list records requiring direction verification. Exclude known opposite directions from the matches. Use the direction field even when the event name suggests a different direction. | [WZDx WorkZoneRoadEvent, `vehicle_impact`](https://github.com/usdot-jpo-ode/wzdx/blob/main/spec-content/objects/WorkZoneRoadEvent.md) and [RoadEventCoreDetails, `direction`](https://github.com/usdot-jpo-ode/wzdx/blob/main/spec-content/objects/RoadEventCoreDetails.md). FDOT features `4577091647`, `4577091647/292055206`, and `4571671574/291384760-R`. | Direction selection in both tools. | `test_crash_screen_partitions_reported_directions`: the eastbound Busch segment is a match and its unknown-direction record is listed separately. `test_detour_uses_direction_field`: the Miami Gardens reverse feature reports southbound and stays out of the northbound matches despite its name. |
| 2 | WZDx lane order starts at the left in the direction of travel and can include shoulders. Use the lane types to count general travel lanes separately and report their closed position among those lanes. Report shoulder closures separately. If the inventory is missing or incomplete, report a lane count or precise position only when supported. | [WZDx Lane, `order`, `type`, `status`](https://github.com/usdot-jpo-ode/wzdx/blob/main/spec-content/objects/Lane.md). FDOT feature `4577091647/292055206`, `lanes`. | Lane summary in `crash_area_work_zone_constraints`. | `test_crash_screen_counts_travel_lanes_without_shoulders`: the closed entry at order 4 is the rightmost of three general travel lanes, with shoulders at orders 1 and 5. |
| 3 | A work-zone record can report an unknown traffic impact even when its dates overlap the incident. Return “lane impact not reported” for that record. Keep it separate from any record with an explicit closure and preserve records that need a field check. | [WZDx VehicleImpact, `unknown`](https://github.com/usdot-jpo-ode/wzdx/blob/main/spec-content/enumerated-types/VehicleImpact.md). FDOT feature `4577091647`, `vehicle_impact` and absence of `lanes`. | Impact summary in `crash_area_work_zone_constraints`. | `test_crash_screen_surfaces_unreported_lane_impact`: the unknown-direction Busch record has an explicit unknown impact and no asserted lane count. |
| 4 | A posted work-zone detour belongs to the work zone identified by the feed relationship. Use the exact feature ID and require an explicit link. A similar name or proximity does not establish that link. Return “no linked detour for this work-zone ID and direction” if the feed supplies none. | [WZDx RoadEventCoreDetails, `related_road_events`](https://github.com/usdot-jpo-ode/wzdx/blob/main/spec-content/objects/RoadEventCoreDetails.md). FDOT feature `4571671574` lists two `related-detour` IDs, and both linked detour features list `4571671574` as their `related-work-zone`. | Link lookup in `linked_work_zone_detours_for_direction`. | `test_detour_requires_exact_work_zone_relationship`: the northbound child `4571671574/291384760` is returned for parent `4571671574` and is never attached to the Busch feature. |
| 5 | An estimated end date is a planning window. Label the reported time as unverified when the feed does not confirm the end. Keep that status visible even after the reported end passes, so the operator knows to verify reopening instead of treating the clock as evidence of clearance. | [WZDx WorkZoneRoadEvent, `end_date` and `is_end_date_verified`](https://github.com/usdot-jpo-ode/wzdx/blob/main/spec-content/objects/WorkZoneRoadEvent.md) and [DetourRoadEvent, time and verification fields](https://github.com/usdot-jpo-ode/wzdx/blob/main/spec-content/objects/DetourRoadEvent.md). FDOT features `4571671574` and `4571671574/291384760` report `is_end_date_verified=false` and estimated end dates. | Date summary in both tools. | `test_reported_detour_end_does_not_confirm_reopening`: the northbound Miami Gardens detour's Nov. 30 end is labeled unverified even when a test clock is later than the reported time. |

## Plain vs. yours

The baseline displays the feed's direction, lane entries, linked IDs, and dates as returned.
The tools separate direction matches from records needing verification, turn lane orders into
travel-lane positions when possible, and label unverified end times. Both versions read the same
snapshot records. The tests compare the two versions on the Busch Boulevard and Miami Gardens cases.

## What the data cannot tell

- **Crash status and actual clearance.** These WZDx records describe work zones and their detours.
  The tools label their findings as work-zone reports. Crash location, direction, blocked lanes, and
  clearance come from the dispatch incident record, field responders, or a live camera.
- **Whether an unreported or nearby restriction affects the candidate route.** The radius screen can
  flag work on a nearby road or miss a restriction elsewhere along the bypass. It returns the search
  scope and the feed timestamp. When impact or direction is missing, it identifies the missing field.
  Check the route alignment against a road network map and verify the actual lane setup with a camera
  or field crew. A work permit can explain the planned setup.
- **Whether the bypass can carry diverted traffic.** A linked detour gives a published work-zone
  relationship and a reported date window. The tool reports that relationship and window. Current
  queues and travel times require detector, probe, or camera data. Approval for the crash diversion
  comes from the TMC's incident response plan and the operator's operational check.

## AI use

The student provided the design ideas and interpretation of the rerun. Codex assisted with tool
implementation, testing, running the experiments, and drafting the transcript analysis, grades,
and ablation comparisons.
