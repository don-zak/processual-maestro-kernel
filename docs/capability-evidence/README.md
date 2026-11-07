# Maestro Capability & Governance Evidence (v1)

This dossier is an **auditable internal experiment**, not a sales claim or a substitute
for real External Evaluation Workspace qualification. It deliberately calls the
**real public CGT Evaluation governance policy** and the **real Maestro kernel's
hash-only synthetic task-consumption pathway** without contacting any external
sandbox, issuing keys, admitting Neon quota or modifying production.

## Reproduce the entire dossier

From the reviewed repository revision, with development dependencies installed:

```bash
PYTHONPATH=. python -m pytest -q tests/test_capability_dossier.py
PYTHONPATH=. python -m ops.evaluation.export_capability_dossier --output capability-evidence-output
```

The GitHub Actions `Maestro Capability Evidence` workflow reruns the same
tests and exports a downloadable `maestro-capability-evidence-<SHA>` artifact
containing `index.html`, `results.json` and `manifest.json`.
Open `index.html` locally; no network connection or API key is required.
The manifest binds exact public source SHA and SHA-256 of both the report and viewer.

## Exactly what the sixteen experiments measure

Ten synthetic task scenarios use registered canonical task contracts: CRM read,
summary and review-only draft; billing read; university student request, course
and admission draft; government case, citizen request and response draft.
Six controlled negative variants request production execution, auto-execution,
non-sandbox execution or an unsupported operation class.

Every case includes the unabridged **synthetic** input, requested operation,
exact required scopes, modified constraints, expected and actual decision,
the CGT reason codes and policy version, all seven original fate-vector values,
the fixed numeric policy profile passed to `compute_fate_vector`, an independent
recalculation and its consistency test. Permitted scenarios additionally run
`ProcessualMaestroKernel` over synthetic hash-only task outcomes and expose
its original safe receipt. Denied scenarios verify that no kernel consumption
was invoked. The viewer shows any FAIL instead of filtering it away.

**Important:** the External Evaluation `fate_vector_basis` is
`external-evaluation-policy-signal-profile-v1`. The numeric profile depends on
policy rank and operation type, rather than independently measuring the domain
task's quality or predicting its real-world outcome. Independent recomputation
can verify arithmetic and drift, but is **not** proof of empirical predictive
validity or evidence that governance is correct for every possible input.

## Workspace evidence and independent review

`workspace_evidence=NOT_IMPORTED` is intentional in v1. The fixture-based
CGT experiments do not contact a live Worker or Maestro API. The actual
Workspace operational evidence must be separately collected via its existing
status/receipt APIs with approved key-scoped access. In particular, **never**
use a synthetic execution SHA as an external network proof, and never copy
sensitive raw keys or customer data into investor-facing HTML. Before linking
a real receipt to a dossier case, verify exact public and private deployment
provenance, task ID, binding ID, governance trace, synthetic-vs-live provenance,
real execution status, Maestro consumption receipt, quota delta and hash bindings.

## UI/UX

`index.html` is a self-contained bilingual Arabic/English interactive report:
sector and decision filtering, explicit PASS/FAIL, readable original case content,
numeric fate-vector bars, the frozen policy inputs, independently recomputed
values, governance reasons, safe hash-only kernel receipt and all per-case checks.
It has no third-party scripts or fonts, is responsive and includes print styling.
The source template is `docs/capability-evidence/template.html`.

PR qualification remains Draft/fail-closed until existing checks pass. This
dossier does not merge PR221 or authorize any production deployment.
