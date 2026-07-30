# Group 2 Auth and Subscription UI Alignment Readiness

Generated at: 2026-07-30T18:05:56Z

## Compatibility outcome

- Legacy `/billing/pricing-catalog` API contract is preserved.
- Group 2 catalog is exposed at
  `/billing/commercial-pricing-catalog`.
- Subscription options request the Group 2 catalog first.
- The legacy pricing catalog remains a real fallback for compatibility.
- Academic plan appears first when the Group 2 catalog is available.
- Login UTF-8 baseline and multilingual markers are preserved.
- Password visibility and registration assets use cache version 2.
- Full Python suite passed.
- Alembic head remains `20260730_0016`.

## Fail-closed boundaries

- Group 2 pricing status: `draft_review`.
- Legacy catalog status: `draft`.
- Checkout runtime: disabled.
- Provider runtime: disabled.
- Automatic activation: disabled.
- Purchase and publication: disabled.
- Quota enforcement and settlement: disabled.