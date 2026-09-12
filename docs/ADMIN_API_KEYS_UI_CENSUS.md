# Admin API Keys / External Evaluation UI Census

## Purpose

This census prevents unsafe cleanup based only on filenames or direct `<script>` tags. A file may be loaded directly, injected by middleware, or loaded dynamically only after Platform Administrator authority is verified.

No file in the protected External Evaluation load graph should be deleted unless its load path, DOM contract, routes, and tests have first been removed or replaced in the same reviewed change.

## Active load graph

### Directly loaded by `admin.html`

| File | Role | Disposition |
| --- | --- | --- |
| `processual_api/static/js/admin_api_keys.js` | Standard API-key lifecycle, supervisor session key UI, integration bridge context | **KEEP — active** |
| `processual_api/static/js/admin_api_key_summary.js` | Safe API-key summary surface | **KEEP — active** |
| `processual_api/static/js/admin_session.js` | Identity/Platform-Admin verification and protected Evaluation asset loader | **KEEP — authority-critical** |

### Middleware-injected bootstrap

| File | Role | Disposition |
| --- | --- | --- |
| `processual_api/static/js/admin_external_evaluation_dom_contract.js` | Adds External Evaluation category/host, hides standard key generation in Evaluation mode, starts verified admin flow | **KEEP — bootstrap contract** |

`SecurityHeadersMiddleware` injects this DOM-contract script into `/admin`; therefore absence from static `admin.html` is not evidence that it is unused.

### Dynamically loaded only after verified Platform Administrator authority

`admin_session.js` loads the following assets from `loadProtectedEvaluationControls()` only after `/settings/admin/evaluation-grants/authority` confirms active PostgreSQL-backed Platform Administrator authority:

| File | Role | Disposition |
| --- | --- | --- |
| `admin_evaluation_grants.js` | Grant creation, binding/task selection, one-time key issue and safe customer handoff | **KEEP — active protected surface** |
| `admin_evaluation_owned_preset.js` | Project-owned sandbox preset workflow | **KEEP — active protected surface** |
| `admin_api_key_provisioning_workspace.js` | Backend-derived operational profiles/endpoints and Evaluation provisioning mode | **KEEP — active protected surface** |
| `admin_api_key_evaluation_lifecycle.js` | Evaluation lifecycle UI, delivery/receipt/revoke controls, lifecycle embedding | **KEEP — active protected surface** |

The dynamic load is intentionally fail-closed. A browser role label is not sufficient authority.

## Regression evidence

Existing tests explicitly cover the dynamic load graph and therefore also prove these files are not obsolete:

- `tests/test_admin_api_key_provisioning_workspace.py`
- `tests/test_admin_api_key_evaluation_lifecycle.py`
- `tests/test_admin_external_evaluation_category_flow.py`
- `tests/test_admin_external_evaluation_self_healing.py`
- `tests/test_admin_evaluation_grants_ui.py`

The provisioning/lifecycle tests verify that the protected scripts load only after Platform Administrator authority is verified, and that External Evaluation cannot fall through to standard API-key generation.

## Legacy compatibility marker debt

`admin.html` currently contains a comment labelled `15A legacy static compatibility markers` with historical `admin_api_keys.js` cache-version strings. It is not runtime behavior. At least one older regression test still searches for an old cache marker, so deleting only the comment would create test churn without reducing runtime code.

Safe cleanup sequence for this marker:

1. update the remaining old regression assertion to pin the real current script reference rather than a historical comment marker;
2. confirm no other test/source depends on the historical versions;
3. remove the compatibility comment from `admin.html` in the same commit;
4. run the Admin/API-key regression suite.

Until those four steps are performed together, keep the marker and classify it as **legacy test debt**, not executable legacy code.

## Current cleanup decision

No protected Evaluation JavaScript file is approved for deletion from this census.

The current evidence supports consolidation/refactoring only after behavior-preserving tests are in place. File count alone is not a sufficient reason to merge or remove these modules because each presently owns a distinct layer:

`DOM bootstrap → verified admin session → provisioning workspace → grant authority → Evaluation key lifecycle`.

## Next UI/UX review

The next Admin UI review should focus on value and operator flow rather than file count:

1. present CRM and Integration presets as clear proof tracks only when their owned sandbox deployments are actually available;
2. keep grant type responsible for fixed Evaluation quota (`crm=100`, `integration=200`);
3. show one recommended next action at each lifecycle stage;
4. keep one-time raw key handling visually separate from safe handoff/audit metadata;
5. keep revoked artifacts visible for audit but visually non-runnable;
6. remove duplicate explanatory text only after verifying it is not carrying a security or authority warning.
