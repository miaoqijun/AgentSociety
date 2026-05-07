# Stage: compare_angles

Multi-angle handling for the framing producer.

## Mechanism

The producer may emit a `candidate_angles` array in its storyline_map.
When this happens:

1. The producer recommends one angle as `current_angle`.
2. Rejected angles and their kill-criteria reasoning fall into
   `storyline_map.rejected_angles[]`.

## Orchestrator Behavior

- Always accept the producer's `current_angle` as the working angle.
- Dispatch angle-critic on the full `candidate_angles` list if present.
- The critic may rank or re-order angles; if the critic recommends a
  rejected angle over the current one, route to revision-router.
- Rejected angles are preserved for future pivot decisions — do not
  discard them.

## Single-Angle Case

When `candidate_angles` is absent or has length 1, this stage is a
no-op. Proceed directly to angle-critic on the single angle.
