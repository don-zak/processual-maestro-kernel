# CAMARA QoD Sandbox Transition Addendum — Telefonica Missing-Session Divergence

Date: 2026-08-19

This addendum updates the comprehensive transition report after the negative-path and isolated missing-session probes were executed against Telefonica Open Gateway QoD v0.10 sandbox/mock.

## Confirmed observation

A bounded negative-path probe authenticated through CIBA and produced:

```text
POST /bc-authorize                                  -> 200
POST /token                                         -> 200
POST /qod/v0/sessions with duration=0               -> 400
GET  /qod/v0/sessions/{syntheticMissingSessionId}   -> 200
GET  same missing session without Authorization     -> 401
POST /qod/v0/sessions with documented conflict UE   -> 409
```

The missing-session test was then isolated with a newly generated random UUID that:

- was generated locally for that single run;
- was never supplied to `createSession`;
- was not retained in public evidence.

The isolated probe again observed:

```text
GET /qod/v0/sessions/{freshSyntheticSessionId} -> 200
```

Telefonica's QoD v0.10 API reference documents `404` for a missing session. Therefore the sandbox/mock behavior is retained as a reproducible provider mock/documentation divergence.

## Qualification interpretation

The observation does **not** revoke the positive-path evidence already proven for:

- `createSession`;
- `getSession` for a session returned by create;
- `deleteSession`;
- `extendQosSessionDuration`.

It does mean that negative-path conformance is incomplete and that `getSession` missing-resource semantics are not conformant to the documented expectation in the exercised mock environment.

Current state is therefore:

```text
authenticated_sandbox_reachability_proven=true
external_mock_sandbox_proven=true
external_mock_extend_proven=true
negative_path_conformance_complete=false
missing_session_documented_expectation_met=false
mock_documentation_divergence_observed=true
operator_network_qos_proven=false
governed_camara_v1_1_provider_sandbox_proven=false
provider_sandbox_proven=false
runtime_connector_approved=false
staging_allowed=false
production_allowed=false
```

## Retained evidence

Primary positive-path evidence:

`docs/qualification/evidence/TELEFONICA_QOD_CIBA_SESSION_LIFECYCLE_2026-08-19.json`

Missing-session divergence evidence:

`docs/qualification/evidence/TELEFONICA_QOD_MISSING_SESSION_DIVERGENCE_2026-08-19.json`

Probe tools:

- `tools/telefonica_qod_ciba_negative_probe.ps1`
- `tools/telefonica_qod_missing_session_probe.ps1`

No client secret, access token, auth request ID, raw response body, or session identifier is retained in public evidence.

## New blocker codes

The sandbox qualification package must now carry:

```text
telefonica_missing_session_returns_200_instead_of_documented_404
telefonica_negative_path_conformance_incomplete
telefonica_api_version_differs_from_governed_camara_v1_1
retrieve_sessions_by_device_unproven
operator_network_qos_unproven
runtime_connector_unapproved
```

## S1 closure impact

S1 remains partially complete. The negative-path package is now materially stronger because it includes reproducible positive and negative observations, but exact provider conformance cannot close while the missing-session behavior diverges and `retrieveSessionsByDevice` remains unproven.

Required next decisions:

1. Determine whether the `200` missing-session behavior is specific to the mock implementation or also present in any operator-backed/test provider environment.
2. Raise the divergence as an explicit provider compatibility issue; do not normalize `200` to `404` silently in governance evidence.
3. Determine whether a current Telefonica/provider surface exposes `retrieveSessionsByDevice` or an approved equivalent.
4. If the provider surface intentionally differs, require an explicit provider-adapter compatibility decision before any runtime connector approval.

All higher authority gates remain fail-closed.
