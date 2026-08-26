# VQ-1 Execution Preparation — 2026-08-19

**Status:** PREPARATION — VISUAL REVIEW NOT YET EXECUTED  
**Gate:** `VISUAL_QUALIFICATION_GATE_V1.md`  
**Sequence:** release-truth reconciliation -> VQ-1 execution -> Real Staging qualification  
**Authority:** qualification evidence only; no staging or production authority

## Near-term presentation milestone

The next user-visible qualification milestone is **VQ-1 Comprehensive Visual Review**. It is intentionally scheduled immediately after this execution-preparation wave reaches an exact-head green state and before any Real Staging qualification.

At that milestone the program is to be run as a complete controlled qualification UI and presented page-by-page and section-by-section for comprehensive visual review. VQ-1 is not permitted to collapse into a sampled smoke review.

## Entry conditions for the visual presentation

Before the visual presentation begins:

1. the preparation head must pass Packaging Qualification, Program Release Qualification, CAMARA Public Source Contracts, Public Docker Build, and Sandbox Integration Qualification;
2. release-truth documents must remain neutralized and non-authoritative;
3. the delivered UI must continue to exclude quarantined legacy CGT/Governor browser surfaces;
4. a frozen exact source SHA must be selected and recorded for the visual run;
5. the browser capture tool and browser binary versions must be recorded;
6. route and section discovery must be completed before the evidence matrix is declared closed.

## Browser-capture approach

The preferred capture harness is Python Playwright because the repository qualification stack is Python/pytest and Playwright supports deterministic browser automation and full-page screenshots.

The harness is not added as an unpinned runtime dependency in this preparation change. The execution wave must pin the qualification-only Playwright package and the browser engine used for capture, install the matching browser binary, and record both versions in the execution record.

Minimum browser target for VQ-1 execution: Chromium. Additional Firefox/WebKit runs may be added later but are not required to begin VQ-1 unless a product support contract requires them.

## Viewport contract

Minimum evidence viewports:

- `desktop-wide`: 1440 x 900 — public acquisition, identity, commercial, and general application pages;
- `desktop-cockpit`: 1366 x 768 — Console and Admin dense operational surfaces;
- `narrow`: 390 x 844 — acquisition, identity, commercial, settings, and explicit Console/Admin narrow observation.

The execution record may add viewports but may not silently remove one of these minimum classes after a defect is observed.

## Route discovery

The current minimum route seed is:

- `/`;
- `/login`;
- `/plans`;
- `/offer/starter` plus every active offer variant discovered at the frozen SHA;
- `/register`;
- `/verify-email`;
- `/pricing`;
- `/console/`;
- `/admin`.

This seed is not the final inventory. Before screenshots are captured, runtime/router and delivered-navigation inspection must discover every user-visible HTML route present at the frozen SHA. Any newly discovered route receives an evidence row before VQ-1 can pass.

## Console section discovery

Minimum Console seed:

- Overview;
- Workflows;
- Governance;
- Telemetry;
- Reports;
- Gateway;
- Simulation;
- Settings.

The browser run must enumerate the delivered active navigation and add any additional active section. Legacy CGT Evaluator and Governor sections are not valid active targets; their absence/inaccessibility is evidence that must be recorded.

## Admin section discovery

The `/admin` page is not a single evidence row. The execution harness must enumerate every active Admin navigation destination and nested section from the delivered DOM before capture.

Where present, the inventory must include dashboard/home, subscription/commercial controls, API-key/credential summaries, provider/integration controls, supervisor/audit/readiness surfaces, client requests, operator/pilot controls, and any other discovered active target.

## Evidence matrix schema

The execution artifact must use one row per route/section/state/viewport/locale combination and include at least:

`source_sha`, `browser_engine`, `browser_version`, `capture_tool_version`, `route`, `section`, `state`, `viewport`, `viewport_width`, `viewport_height`, `locale`, `evidence_id`, `screenshot_path`, `result`, `defect_id`, `notes`.

`result` is one of `PASS`, `FAIL`, or `NOT_APPLICABLE`. `NOT_APPLICABLE` requires a reason in `notes`.

Stable evidence ID format:

`VQ1-<route-or-surface>-<section>-<state>-<viewport>-<locale>-NNN`

Screenshot filenames must begin with the same evidence ID.

## Required state families

For each applicable surface:

- default/loaded;
- loading;
- empty/no-data;
- success/confirmation;
- form validation error;
- permission denied/insufficient scope;
- unavailable/fail-closed;
- subscription/billing restriction, grace, suspended, or terminated state where applicable;
- long-content/overflow;
- focus/keyboard-visible;
- localization/RTL wherever exposed.

## Presentation order

The visual review is executed in this order:

1. entry/acquisition: splash, plans, pricing, offers;
2. identity: login, registration, verification;
3. application Console: every active section;
4. Settings and provider-related user-visible flows;
5. Admin: every active navigation destination and nested section;
6. negative/fail-closed states and subscription restrictions;
7. narrow/RTL and long-content observations;
8. final sweep proving quarantined CGT/Governor UI remains absent.

This order is for review usability only; all discovered surfaces remain mandatory regardless of order.

## Defect handling

Every failed evidence row creates or references a defect classified as `VQ-BLOCKER`, `VQ-HIGH`, `VQ-MEDIUM`, or `VQ-LOW` according to the gate contract.

No VQ-BLOCKER or VQ-HIGH may remain open when VQ-1 is closed. Fixes require recapture against the same frozen SHA if no source change occurred, or a new frozen SHA plus requalification if source changed.

## Exit from preparation into VQ-1

Preparation is complete only when:

- this document and its regression guard are exact-head green;
- the PR records the exact-head CI evidence;
- the qualification-only browser harness/version pin is ready to be introduced;
- the source SHA to be visually reviewed can be frozen without unrelated cleanup work.

At that point the program should be **presented for the comprehensive visual review** rather than continuing broad cleanup. Visual defects discovered by VQ-1 become the prioritized source-change backlog.

## Authority boundaries

This preparation does not grant browser-review completion, Real Staging, provider/operator proof, or production authority.

The following remain false:

- `RepositoryReconciliationComplete=false`;
- `GeneralPackagingComplete=false`;
- `PrivateRuntimeAuthorityGranted=false`;
- `runtime_connector_approved=false`;
- `provider_sandbox_proven=false`;
- `operator_network_qos_proven=false`;
- `RealStagingQualified=false`;
- `ProductionAuthorityGranted=false`.
