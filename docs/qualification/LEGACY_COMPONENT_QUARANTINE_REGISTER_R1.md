# Legacy Component Quarantine Register — R1

**Status:** ACTIVE QUALIFICATION CONTROL — NO DELETION AUTHORITY  
**Date:** 2026-08-19

## Purpose

Keep superseded, compatibility-only, replaced, or legacy components physically and operationally controlled until deletion is proven safe. The goal is to reduce runtime and maintenance weight without destroying evidence, breaking compatibility, or accidentally reconnecting unsafe surfaces.

## Classification

- `ACTIVE`: current production-path candidate; normal maintenance applies.
- `COMPATIBILITY_ONLY`: retained only to preserve an established import/API contract while callers migrate. New production dependencies are forbidden.
- `QUARANTINED_SOURCE`: source retained for review/history, but runtime delivery/import/registration is blocked.
- `ACTIVE_LEGACY_DEBT`: still reachable or required by current behavior; must not be mislabeled as dead code. Migration is required before quarantine/deletion.
- `DELETE_CANDIDATE`: no known production-path dependency remains and removal may enter a dedicated deletion review. External/API/test/history obligations still have to be explicitly checked before deletion.

Deletion is never inferred from age, naming, or apparent duplication alone.

## Current register

| Component | Classification | Active replacement / authority | Runtime control | Deletion gate |
|---|---|---|---|---|
| `processual_api/static/js/adapters/governor.js` | `QUARANTINED_SOURCE` | Future ref-oriented private evaluation client using `/cgt/govern/evaluate` after real opaque-reference issuance exists | Removed from delivered console HTML; direct HTTP request returns `410 Gone`; explicitly removed from the public Docker runtime image | Real opaque-reference issuer/resolver exists; legacy console migration complete; no source/test/document references require retention |
| `processual_api/static/js/adapters/cgt.js` | `QUARANTINED_SOURCE` | Same sanitized private-evaluation boundary | Removed from delivered console HTML; direct HTTP request returns `410 Gone`; explicitly removed from the public Docker runtime image | Same as above |
| `processual_api/static/js/pages/governor.js` | `QUARANTINED_SOURCE` | Future sanitized governed-decision UI | Removed from delivered console HTML; Governor navigation/page hidden; direct HTTP request returns `410 Gone`; explicitly removed from the public Docker runtime image | Sanitized replacement UI proven and legacy references removed |
| `processual_api/static/js/pages/cgt.js` | `QUARANTINED_SOURCE` | Future sanitized evaluation UI | Removed from delivered console HTML; CGT navigation/page hidden; direct HTTP request returns `410 Gone`; explicitly removed from the public Docker runtime image | Sanitized replacement UI proven and legacy references removed |
| `processual_api/billing/subscription_catalog.py` | `COMPATIBILITY_ONLY` | `processual_api.billing.pricing_catalog` and canonical commercial contracts | Compatibility facade only; new production imports are rejected by CI | External compatibility review confirms no import contract remains; compatibility tests converted to retirement assertions |
| `processual_api/routers/client_provider_alias_18.py` | `COMPATIBILITY_ONLY` | `/settings/provider-connection` | Deprecated API alias remains reachable only for external compatibility; response carries deprecation/link headers; current Settings UI uses the canonical route; new internal dependencies rejected by CI | External clients confirmed migrated; compatibility tests converted to retirement assertions; route registration removed in a dedicated change |
| `POST /settings/llm-provider/test` in `settings_provider_test_runtime.py` | `COMPATIBILITY_ONLY` | `POST /settings/provider-connection/test` | Deprecated route remains only for external compatibility; response carries deprecation/link successor metadata; no internal production/UI reference is allowed by CI | External clients confirmed migrated; compatibility test converted to retirement assertion; legacy route removed from route installer in a dedicated change |
| `processual_api/billing/maestro_units.py::credits_from_maestro_units` | `DELETE_CANDIDATE` | Canonical Maestro Units metric; no production caller found for this conversion helper | Function remains source-present while deletion review checks external import/API compatibility. The separate `credits` metric read/migration alias remains active and is not a deletion candidate | Confirm no external/public import promise; remove helper and its dedicated compatibility test in one isolated change; keep legacy metric normalization until its own migration gate closes |
| `processual_api/routers/cgt_governor.py` | `ACTIVE_LEGACY_DEBT` | Canonical sanitized private evaluation boundary, after real opaque-reference topology implementation | Not quarantined: still contains active historical routes/contracts and therefore must not be deleted or partially amputated | Opaque-reference topology approved and implemented; browser/router/report migration complete; route consumers and persistence contracts reconciled |
| legacy raw-score/vector report surfaces coupled to `cgt_governor` | `ACTIVE_LEGACY_DEBT` | Sanitized six-field result contract | Remain under architectural quarantine policy; no new public raw-score/vector consumers permitted | Full migration plus evidence that raw mathematical surfaces no longer cross the public/private boundary |

## Runtime quarantine rules

1. A `QUARANTINED_SOURCE` browser asset must not appear in delivered HTML.
2. A direct request for a quarantined browser asset must return `410 Gone`, not the source file.
3. Quarantined browser sources must not be present in the public Docker runtime image unless a later reviewed decision explicitly reverses that exclusion.
4. Navigation/page shells linked exclusively to quarantined behavior must not be user-visible.
5. Quarantine must be enforced in tests against rendered application responses and image/build contracts, not only source inspection.
6. Quarantine does not authorize deletion; Git remains the review/evidence location until the deletion gate passes.

## Compatibility-only rules

1. New production code must import or call the canonical replacement directly.
2. Compatibility facades/routes may be exercised only by explicit compatibility tests or known external-contract preservation.
3. Deprecated HTTP compatibility routes must advertise a canonical successor where one exists; no fabricated sunset date is allowed without an approved retirement schedule.
4. Compatibility surfaces must not regain commercial/runtime authority or become dependencies of new UI/application code.
5. Once all callers are migrated, the component advances to `DELETE_CANDIDATE` for a separate deletion review.

## Delete-candidate rules

1. `DELETE_CANDIDATE` means source removal is eligible for review, not pre-authorized.
2. Production-path absence must be proven independently from external/public API compatibility.
3. Related compatibility behavior must be split: an unused helper may be deleted while a still-consumed migration alias remains active.
4. Deletion should occur in a small isolated change so rollback and evidence are unambiguous.

## Deletion review checklist

A component may be deleted only when all of the following are demonstrated:

- no active imports, router registrations, static HTML references, dynamic loader references, templates, migrations, configuration hooks, or operator scripts;
- no public/external compatibility obligation requires the old path;
- no test depends on the old component except a deletion/migration assertion;
- no documentation or release evidence requires the source to remain in-tree rather than Git history;
- replacement behavior is independently qualified;
- rollback does not rely on reconnecting the obsolete component;
- removal reduces maintenance/runtime/package surface without removing required audit evidence.

## Current safety decision

The four legacy browser CGT/Governor JavaScript files are source-retained in Git, runtime-disconnected, and absent from the public Docker runtime image. `subscription_catalog.py`, `client_provider_alias_18.py`, and `POST /settings/llm-provider/test` remain compatibility-only. `credits_from_maestro_units()` is a deletion candidate only; the legacy `credits` metric read/migration alias remains active. `cgt_governor.py` remains active legacy debt and is explicitly **not** a deletion candidate.

No private-runtime authority, Real Staging authority, or Production authority is granted by this register.
