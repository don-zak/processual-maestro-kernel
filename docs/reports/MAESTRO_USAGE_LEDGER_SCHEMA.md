# Maestro Usage Ledger Schema

## Phase

PRICING-LEDGER-01 — document full usage ledger schema.

This document defines the audit and support meaning of records written to `processual_api/data/usage_logs.jsonl`.

The usage ledger connects:

1. BYOK policy.
2. Maestro usage-unit pricing.
3. Unit-based quota enforcement.
4. Quota metadata.
5. Quota rejection audit metadata.

The ledger is not a provider-token bill. It is a Maestro usage ledger.

---

## 1. Core Principle

Processual Maestro tracks and bills Maestro usage units.

It does not include external LLM/provider token costs.

The customer brings their own provider account, provider API key, and provider billing relationship.

This is the BYOK policy.

---

## 2. Record Format

Each usage ledger entry is one JSON object on one line.

The file format is JSONL.

One line equals one API-key usage event.

Example fields may include:

- created_at
- request_id
- client_id
- endpoint
- status_code
- units_charged
- quota_before
- quota_after
- quota_rejected
- plan_id

---

## 3. Identity Fields

| Field | Meaning |
| --- | --- |
| `created_at` | UTC timestamp for the ledger event |
| `request_id` | Request correlation identifier |
| `client_id` | Customer or client identity |
| `user_id` | User or service owner |
| `api_key_id` | Internal API key record id |
| `api_key_prefix` | Safe public prefix, never the raw key |
| `auth_method` | Expected value for API-key usage is `api_key` |
| `session_type` | API key session type |
| `role` | Role associated with the API key |

Supervisor note:

Never ask the customer to send a full raw API key. The ledger stores safe identity references only.

---

## 4. Request Fields

| Field | Meaning |
| --- | --- |
| `method` | HTTP method |
| `endpoint` | Sanitized endpoint path |
| `status_code` | HTTP status code |
| `latency_ms` | Request latency in milliseconds |

Raw `pmk_...` API keys must never appear in stored ledger endpoint paths.

---

## 5. Pricing Fields

| Field | Meaning |
| --- | --- |
| `pricing_version` | Pricing catalog version |
| `billing_policy` | Expected value: `byok` |
| `billing_scope` | Expected value: `maestro_usage_units` |
| `provider_cost_included` | Expected value: `false` |
| `endpoint_class` | Commercial class of endpoint |
| `units_charged` | Maestro usage units charged or requested |

Current expected values:

| Field | Expected value |
| --- | --- |
| `pricing_version` | `2026-07-byok-v1` |
| `billing_policy` | `byok` |
| `billing_scope` | `maestro_usage_units` |
| `provider_cost_included` | `false` |

Customer answer:

Maestro tracks Maestro usage only. Provider token billing belongs to the customer provider account because Maestro uses BYOK.

---

## 6. Endpoint Classes

| Endpoint class | Meaning |
| --- | --- |
| `free_operational_check` | Health, readiness, status, and subscription checks |
| `analysis_evaluation` | Analysis endpoints |
| `governance_evaluation` | Governance decision endpoints |
| `batch_governance_evaluation` | Batch governance operations |
| `report_generation` | Report endpoints |
| `metered_api_request` | Default metered request |

---

## 7. Unit Cost Examples

| Operation | Endpoint | Units |
| --- | --- | ---: |
| Health live | `/health/live` | 0 |
| Adapter status | `/adapters/status` | 0 |
| Analyze | `/cgt/analyze` | 1 |
| Govern | `/cgt/govern` | 1 |
| Govern batch | `/cgt/govern/batch` | item_count × 1 |
| Compare | `/cgt/govern/compare` | 2 |
| Fate report | `/reports/fate` | 2 |
| Governance report | `/cgt/govern/report` | 3 |
| Generate LLM report | `/reports/generate-llm` | 5 |
| Auto repair | `/cgt/govern/auto-repair` | 5 |

---

## 8. Quota Fields

| Field | Meaning |
| --- | --- |
| `quota_scope` | Quota category, usually `evaluation` |
| `quota_limit` | Maximum allowed Maestro units |
| `quota_used` | Used units after success, or used units at rejection |
| `quota_requested` | Units requested by the current operation |
| `quota_remaining` | Remaining units after success or at rejection time |
| `quota_before` | Used units before the request |
| `quota_after` | Used units after success, or unchanged used units at rejection |
| `plan_id` | Plan used for quota context |
| `quota_rejected` | Whether this event represents quota rejection |

For a successful request:

`quota_before + quota_requested = quota_after`

For a rejected request:

`status_code = 429` and `quota_rejected = true`.

The rejected request is logged for audit and support.

---

## 9. Successful Request Meaning

A successful auto-repair request with 5 units means:

- the request succeeded;
- 5 Maestro units were consumed;
- quota moved from before to after;
- the remaining quota was updated;
- `quota_rejected` is false.

Supervisor explanation:

The customer had enough units. Maestro executed the operation and consumed the required units.

---

## 10. Rejected Request Meaning

A rejected auto-repair request with 5 requested units and only 2 remaining units means:

- the request needed 5 Maestro units;
- the customer had only 2 remaining;
- Maestro returned 429;
- the attempt was logged;
- `quota_rejected` is true;
- successful usage was not advanced as if the operation completed.

Supervisor explanation:

The request was blocked because it required more units than the remaining quota.

---

## 11. Customer Answers

### Why was my request rejected?

The request required more Maestro units than the remaining quota. The ledger shows `quota_requested`, `quota_remaining`, and `quota_rejected=true`.

### Did you charge me for a rejected request?

The rejected attempt is logged for audit and support. It is marked with `quota_rejected=true`.

### Why did auto-repair consume more than govern?

Different endpoints have different Maestro usage-unit costs. Auto-repair is heavier and currently costs 5 Maestro units.

### Does this include LLM provider cost?

No. `provider_cost_included=false` confirms that external provider token costs are not included. Maestro uses BYOK.

---

## 12. Supervisor Checklist

When reviewing a customer issue, check:

1. `client_id`
2. `api_key_id`
3. `endpoint`
4. `status_code`
5. `units_charged`
6. `quota_limit`
7. `quota_before`
8. `quota_requested`
9. `quota_after`
10. `quota_remaining`
11. `quota_rejected`
12. `plan_id`

If `quota_rejected=true`, explain the rejection using `quota_requested` and `quota_remaining`.

If `provider_cost_included=false`, remind the customer that provider tokens are BYOK and external to Maestro billing.

---

## 13. Minimal Required Ledger Fields

A commercially useful ledger record should include:

- created_at
- request_id
- client_id
- api_key_id
- method
- endpoint
- status_code
- pricing_version
- billing_policy
- billing_scope
- provider_cost_included
- endpoint_class
- units_charged
- quota_scope
- quota_limit
- quota_before
- quota_requested
- quota_after
- quota_remaining
- quota_rejected
- plan_id

These fields are enough for a supervisor to explain what happened, why it happened, and whether the customer needs more quota, an overage block, or a plan upgrade.
