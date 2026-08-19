# Visual Qualification Gate V1

**Status:** REQUIRED PRE-REAL-STAGING QUALIFICATION GATE  
**Authority:** qualification evidence only; no staging or production authority  
**Sequence:** release-truth reconciliation -> VQ-1 -> Real Staging qualification

## Purpose

VQ-1 is the first comprehensive browser-visible review of the complete user-facing program. It converts the current rendered HTTP/DOM qualification into a systematic visual inspection of every active page, section, supported viewport, and material UI state.

VQ-1 must be executed against one frozen exact source SHA. The evidence matrix, defect register, screenshots, and closure decision must all name that SHA. A passing VQ-1 does not set `RealStagingQualified=true` and does not grant production authority.

## Entry gate

VQ-1 may start only after:

1. the current public head is green on Packaging Qualification, Program Release Qualification, CAMARA Public Source Contracts, Public Docker Build, and Sandbox Integration Qualification;
2. release-truth reconciliation has neutralized stale or contradictory readiness/release claims that would confuse the visual review;
3. quarantined legacy CGT/Governor browser assets remain absent from delivered UI and runtime image;
4. the build under review can be run locally or in a non-real qualification environment without private proprietary source exposure.

## Page inventory

The execution record must contain every user-visible route present at the frozen SHA. At minimum the current public inventory includes:

- `/` — splash/entry;
- `/login` — identity entry;
- `/plans` — plan selection;
- `/offer/starter` — representative offer flow, plus every additional active offer variant discovered in the route inventory;
- `/register` — registration;
- `/verify-email` — email verification;
- `/pricing` — pricing/commercial surface;
- `/console/` — application console;
- `/admin` — administrative surface.

The route inventory is not closed by this list. VQ-1 fails incomplete if runtime/router inspection discovers another user-visible HTML route that has no evidence row.

## Console section inventory

The active Console sections to be visually reviewed include:

- Overview;
- Workflows;
- Governance;
- Telemetry;
- Reports;
- Gateway;
- Simulation;
- Settings.

Legacy CGT Evaluator and Governor sections are not active visual targets. VQ-1 must instead prove that their navigation/page surfaces remain absent or inaccessible according to the quarantine contract.

If the frozen SHA exposes additional active Console sections, they must be added to the evidence matrix before VQ-1 can pass.

## Admin section inventory

Every active Admin navigation destination and nested administrative section present at the frozen SHA must be enumerated from the delivered DOM/navigation contract before screenshots are captured. No Admin subsection may be sampled or omitted merely because `/admin` itself renders successfully.

The Admin review must include, where present, dashboard/home, subscription/commercial controls, API-key/credential summaries, integration/provider controls, supervisor/audit/readiness summaries, client requests, operator/pilot controls, and any other active navigation target discovered at execution time.

## Viewport matrix

VQ-1 uses two minimum viewport classes:

- acquisition/identity/commercial pages: desktop and narrow viewport;
- dense Console/Admin cockpit pages: supported desktop/laptop viewport, plus an explicit narrow-viewport observation that records whether the page is supported, degraded-by-contract, or defective.

Exact viewport dimensions must be written into the execution evidence. A viewport may not be silently excluded after defects are observed.

## Required visual states

For each applicable page or section, review and record:

- default/loaded;
- loading;
- empty/no-data;
- success/confirmation;
- form validation error;
- permission denied/insufficient scope;
- unavailable/fail-closed;
- subscription/billing restriction or grace/suspended state where applicable;
- long-content/overflow state for tables, labels, identifiers, and translated text;
- focus/keyboard-visible state for interactive controls;
- localization/RTL state wherever the product exposes it.

A state may be marked not-applicable only with a reason in the evidence matrix.

## Visual inspection checklist

Each evidence row must assess:

- navigation continuity and correct active state;
- hierarchy, typography, spacing, alignment, density, and whitespace;
- clipping, overflow, wrapping, scrolling, and sticky/fixed elements;
- forms, labels, placeholders, validation placement, disabled controls, and button hierarchy;
- tables, cards, charts, legends, empty states, dialogs, banners, notifications, and error surfaces;
- focus visibility and obvious keyboard traps;
- contrast and readability observations;
- English/Arabic or LTR/RTL behavior where exposed;
- absence of ungranted production/readiness wording;
- absence of quarantined legacy CGT/Governor UI;
- no raw private mathematical values, vectors, scores, thresholds, equations, calibration values, or private implementation names exposed in the browser.

## Evidence matrix

The VQ-1 execution artifact must contain one row per page/section/state/viewport combination with at least:

`source_sha`, `route`, `section`, `state`, `viewport`, `locale`, `evidence_id`, `result`, `defect_id`, `notes`.

Screenshots or browser captures must use stable evidence IDs that map back to the matrix. The matrix must report zero unreviewed active routes and zero unreviewed active navigation sections.

## Defect severity

- `VQ-BLOCKER`: security/trust-boundary leak, unusable critical flow, missing critical page, authority misrepresentation, or visual failure that prevents review/use.
- `VQ-HIGH`: major navigation, layout, state, accessibility, localization, or commercial-flow defect with no acceptable qualification workaround.
- `VQ-MEDIUM`: material visual/usability inconsistency that does not block the principal flow.
- `VQ-LOW`: cosmetic/polish issue with no material flow impact.

VQ-1 cannot pass with open `VQ-BLOCKER` or `VQ-HIGH` defects. Medium/low defects may remain only if explicitly recorded for later closure and they do not invalidate a required evidence row.

## Exit criteria

VQ-1 passes only when all of the following are true:

1. exact source SHA is frozen and recorded;
2. route inventory has zero unreviewed user-visible pages;
3. Console inventory has zero unreviewed active sections;
4. Admin inventory has zero unreviewed active sections;
5. required viewport/state/locale combinations are either reviewed or explicitly justified as not applicable;
6. every evidence row has a result and evidence ID;
7. no open blocker/high visual defects remain;
8. quarantined legacy UI remains absent;
9. no private mathematical implementation detail is exposed;
10. no UI text implies Real Staging or production authority that has not been independently granted;
11. the final VQ-1 decision is committed as qualification evidence and linked from the program qualification continuation record.

## Authority boundaries

VQ-1 is intentionally before Real Staging. It validates visual completeness and user-facing behavior in a controlled qualification environment. It does not prove cloud infrastructure, real provider/operator behavior, production secrets, backup/restore, load, rollback, or production readiness.

The following remain false unless independently proven by their own gates:

- `GeneralPackagingComplete=false`;
- `PrivateRuntimeAuthorityGranted=false`;
- `runtime_connector_approved=false`;
- `provider_sandbox_proven=false`;
- `operator_network_qos_proven=false`;
- `RealStagingQualified=false`;
- `ProductionAuthorityGranted=false`.
