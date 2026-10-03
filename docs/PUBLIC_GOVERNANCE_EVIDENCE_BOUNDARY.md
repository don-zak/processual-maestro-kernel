# Public governance evidence admission boundary (draft)

The public repository contains only the **fail-closed integration protocol**,
NOT original evidence, secret attestations, proprietary CGT equations,
operational Fate Vector details or calibration thresholds.

- `processual_kernel.admission_port` checks the SAFE result of a trusted
  SERVER-SIDE private evidence verifier. A client-provided receipt has no
  authorization value.
- `processual_kernel.governed_execution` calls a server-provided private
  evaluation handler **only after** the trusted backend has admitted the
  source-bound evidence and, for operational fate, the calibration.
- `ProcessualMaestroKernel` blocks legacy direct raw-data governance
  observations, task execution, workflow execution, routing and intervention
  when strict evidence mode is enabled. `ENVIRONMENT=production` **always**
  activates strict mode and overrides any attempt to disable it.
- Non-production legacy methods remain for compatibility/tests only.
  They are NOT certified governance entrypoints. Deployment MUST wire the
  trusted private verifier and private qualified evaluator first, or
  production will deliberately refuse these legacy paths.

Public CI tests the fail-closed boundary and that public code contains no
private signer, original source logs, sensitive telemetry or CGT weight
material. No new public deployment or Workspace API contract is approved.
