# Splash Reference Route Extraction Audit — 2026-08-26

## Scope

The approved pivot reference image is the **only source of truth** for the next Splash routing layer. All previously generated Splash/reference-mimic routing files were deleted before this extraction phase began.

This phase is extraction only. It does **not** reconstruct `splash.html` and does **not** permit procedural route generation.

## Locked reference geometry

- Reference canvas: `1672 x 941`
- Reference core bounds: `x=608..1041`, `y=224..632`
- Required trace families: cyan, teal, lime, amber, violet
- Required topology capture: origins, every visible segment, junctions/branches, terminals, and routes that reach modules

## Extraction implementation

`scripts/extract_splash_reference_routes.py` performs:

1. HSV color segmentation of the five neon route families.
2. Removal of known UI interiors so text/icons/card artwork cannot be mistaken for PCB routing.
3. Selection of routing connected to the visible Core perimeter.
4. Pixel skeletonization.
5. Graph node detection (`origin`, `junction`, `terminal`).
6. Edge tracing between graph nodes.
7. RDP vector simplification while retaining the pixel-derived topology.
8. Generation of an audit overlay.

## First audit pass — results

A stricter color-separated graph audit was also run locally against the approved 1672x941 image. It found:

- 140 core-connected color-separated components
- 141 detected origin clusters at/near the Core perimeter
- 295 vector graph edges
- 175 terminal clusters
- 145 junction clusters

These figures are **diagnostic, not canonical route counts**. One physical reference route can contain multiple graph edges after a branch/junction; conversely, raster glow can still cause nearby structures to merge.

## Visual audit result

**Status: AUDIT_REQUIRED — NOT CANONICAL**

The current extraction demonstrates that the true reference network can be recovered directly from the pixels, but the first overlay still shows two classes of work that must be completed before promotion:

1. Dim/low-intensity continuations and some peripheral endings must be reconciled so no valid reference trace is omitted.
2. Any residual non-route bright geometry must be rejected so card art, decorative nodes, telemetry marks, or glow do not become routing data.

For that reason no route manifest has been promoted as canonical and no new Splash page has been created.

## Promotion gate

The route manifest may be marked `CANONICAL` only after a tile-by-tile visual overlay audit verifies all of the following:

- Every visible Core tooth/pin is accounted for.
- Every route leaving the Core is present from its exact origin to its exact last visible point.
- Every branch point is represented.
- Every visible dead-end / terminal is represented.
- Every route that reaches a side module is represented.
- No invented path exists.
- No UI/card/text/chart geometry exists in the routing manifest.
- The reference overlay and extracted overlay agree across the entire routing field, not merely near the Core.

Until this gate passes, `splash_reference_extraction_contract_a3.json` keeps `splash_reconstruction_allowed=false`.
