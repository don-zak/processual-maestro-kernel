# Psi v2 shadow qualification

`PsiV2Engine` is an experimental, read-only continuity evaluator. It is intentionally
separate from the production `ContinuityEngine` and does not participate in routing,
lifecycle decisions, CGT transition evaluation, archival, quarantine, or reroute logic.

## Equations

Instantaneous vitality drive:

    G = ((T * N) - C) * exp(-M)

Bounded shadow state:

    dPsi = (G - lambda * Psi) * dt
    Psi_next = Psi + dPsi

The decay term prevents indefinite linear accumulation under constant positive drive.
The public shadow API also exposes `drive` separately from `dpsi`: a negative `dpsi`
can reflect relaxation from a high accumulated state even while current drive remains
positive.

## Safety boundary

- Legacy `ContinuityEngine` remains unchanged.
- Legacy `snapshot()` and `maestro_snapshot()` schemas remain unchanged.
- Shadow failures are caught and reported through `psi_v2_shadow_snapshot()`.
- Shadow state never changes a governance decision.
- `decay_lambda` is frozen at `0.05` during qualification and is not adaptive.

## Public observability

Use `psi_v2_shadow_snapshot()` to inspect qualification telemetry for agents. On
`ProcessualMaestroKernel` it also reports handoff and workflow shadow states.

This is a qualification surface, not a production replacement for Psi.
