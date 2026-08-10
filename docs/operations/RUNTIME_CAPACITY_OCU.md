# Runtime Capacity and Maestro Operational Statistical Units

## Purpose

Runtime capacity protects Maestro from excessive simultaneous work. It is an
operational safety control and is intentionally independent of commercial plan
quota, subscription balance, top-ups, and billing usage.

## Units

- **OCU (Operational Capacity Unit)** is instantaneous admitted operational load.
- **1 Maestro operational statistical unit = 1 OCU-second (OCU·s).**
- An admitted operation with weight `W` held for `T` seconds records `W * T`
  operational statistical units.

Examples:

- 1 OCU held for 1 second = 1 operational statistical unit.
- 4 OCU held for 250 ms = 1 operational statistical unit.
- 3 OCU held for 2 seconds = 6 operational statistical units.

Queue/wait time before admission does not consume OCU·s. Rejected requests do
not consume OCU·s. If explicit release fails, accounting charges the accepted
reservation through its lease TTL because capacity remains reserved until that
boundary.

## Default admission policy

The current conservative defaults are:

- Global limit: 40 OCU.
- Per-actor aggregate limit: 12 OCU.
- Lease TTL: 120 seconds.
- Bounded wait before rejection: 250 ms.
- Retry interval while waiting: 25 ms.

The actor limit aggregates simultaneous work for the same hashed customer or API
key identity. Purchasing or activating additional commercial plans does not
multiply this operational safety limit.

## Default request weights

- GET, HEAD, OPTIONS: 1 OCU.
- Standard writes: 2 OCU.
- `/workflows` POST: 2 OCU, or 3 OCU for payloads at least 20 KB.
- `/cgt/govern*`: 3 OCU.
- `/cgt/govern/batch`: 4 OCU.

Exact-path overrides can be supplied through `CAPACITY_ROUTE_WEIGHTS_JSON` after
benchmark evidence justifies a different weight.

## Prometheus metrics

The runtime emits bounded-cardinality operational metrics:

- `maestro_capacity_active_ocu`: process-local OCU currently held by admitted work.
- `maestro_capacity_operational_statistical_units_total`: cumulative OCU·s.
- `maestro_capacity_admissions_total{outcome,reason}`: admitted/rejected decisions.
- `maestro_capacity_backpressure_total{reason}`: requests that encountered a full limit.
- `maestro_capacity_lease_expirations_total`: accounting completed at a lease boundary.

Successful HTTP responses also expose `X-Maestro-Capacity-OCU` and
`X-Maestro-Capacity-OCU-Seconds`. These are operational diagnostics, not billable
usage statements.

## Lease boundary

The current reservation has a finite TTL for crash recovery. OCU·s accounting is
capped at that lease boundary. A workload expected to legitimately exceed the
configured lease duration requires lease renewal/heartbeat support before it can
be considered fully protected by the concurrent-capacity governor. Until that
hardening is added, `CAPACITY_LEASE_SECONDS` must exceed the maximum intended
request execution duration with suitable margin.

## Capacity calibration

Do not interpret an OCU as a fixed number of requests or commercial usage units.
Route weights are relative operational costs. Recalibrate them using sustained
load tests and production telemetry, then set the admission ceiling below the
measured saturation knee so the platform retains headroom for system, health,
authentication, and administrative work.
