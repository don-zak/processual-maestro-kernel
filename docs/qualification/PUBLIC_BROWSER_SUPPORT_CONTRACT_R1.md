# Public Browser Support Contract — R1

**Status:** QUALIFICATION CONTRACT — NON-PRODUCTION  
**Date:** 2026-08-19

## Purpose

Define what browser and viewport readiness is actually claimed today, and prevent responsive/mobile readiness from being inferred from a viewport meta tag or static CSS alone.

## Current supported qualification surfaces

### Public acquisition and identity pages

The following public surfaces are intended to remain usable across standard desktop/laptop widths and narrow/mobile widths where their existing responsive CSS supports it:

- splash;
- plans;
- offer;
- registration;
- email verification;
- login;
- pricing.

Current automated qualification proves rendered HTTP availability, browser security headers, registration accessibility baseline, and critical commercial-link invariants. It does **not** yet prove pixel-perfect rendering or automated accessibility conformance at every viewport.

### Maestro operator console

The current console is treated as a **desktop/laptop operator cockpit**, not as a qualified mobile interface.

Reasons visible in current source include:

- fixed-width sidebar architecture;
- multiple four/three/two-column information grids;
- dense metric, chart, gateway, simulation, governance, and settings surfaces;
- no complete source-level responsive/media-query strategy established by current qualification review.

No mobile-production claim is authorized for the operator console until browser evidence proves one.

## Qualification viewport matrix

A future rendered-browser gate should cover at minimum:

- 1440x900 desktop;
- 1280x800 desktop/laptop;
- 1024x768 compact laptop/tablet landscape for explicitly supported surfaces;
- 390x844 mobile for public acquisition/identity pages;
- 360x800 narrow mobile for public acquisition/identity pages.

For the operator console, viewports below the approved desktop/laptop floor must either:

1. render a deliberately supported responsive cockpit proven by browser tests, or
2. present a clear supported-device/viewport message rather than a silently broken layout.

## Browser matrix

Before Real Staging browser closure, prove at minimum:

- current stable Chromium;
- current stable Firefox if officially supported;
- keyboard-only navigation on public identity/acquisition paths;
- focus visibility;
- form labels/status announcements;
- slow/error network behavior;
- 401/403/429/503 user states where relevant;
- quota exhausted, grace, suspended, and session-expired states where relevant;
- screenshot or equivalent visual-regression evidence for release-critical pages.

## Accessibility gate

Static markup assertions are only a baseline. Release closure requires a rendered accessibility scan plus manual keyboard review for critical journeys. At minimum verify:

- document landmarks and heading order;
- form labels/instructions/errors;
- focus order and visible focus;
- status/error announcements;
- contrast for critical text/status states;
- no keyboard traps;
- meaningful controls/names;
- zoom/reflow behavior on public pages.

## Current authority

This contract does not claim full browser qualification. It narrows the current support statement to what has been evidenced and keeps full browser/viewport/accessibility proof open before Real Staging/production closure.

`RealStagingQualified=false` and `ProductionAuthorityGranted=false` remain unchanged.
