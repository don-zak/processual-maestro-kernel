# External Evaluation — CRM Scenario Expansion

**State:** staged, not live-qualified  
**Qualified foundation baseline:** `6f7dd018737151cd1906be068f2478d02d19392b`

This workstream expands the existing CRM External Evaluation proof breadth without changing the qualified grant/key/quota/idempotency/evidence semantics.

## Staged scenarios

### CRM-SUMMARY-01 — CRM Customer State Summary

- canonical task: `crm.customer_state_summary`
- operation class: `read`
- sandbox binding: `evaluation.crm.customer_state_summary.owned`
- sandbox method/path: `GET /users/1`
- required scope: `crm:read`
- required canonical inputs: `customer_id`, `account_status`
- production execution: disabled

### CRM-DRAFT-01 — Draft Customer Update

- canonical task: `crm.customer_update_draft`
- operation class: `draft`
- sandbox binding: `evaluation.crm.customer_update_draft.owned`
- sandbox method/path: `POST /users/1/update-draft`
- required scopes: `crm:read`, `customer:update`
- required canonical inputs: `customer_id`, `proposed_changes`
- request body is built from the canonical task contract through a prepared request mapping
- result is a draft artifact only
- `applied=false`
- `review_required=true`
- `production_mutation_performed=false`
- production execution: disabled

The draft endpoint is intentionally not a CRM mutation endpoint. It does not alter the project-owned synthetic customer fixture and does not grant production-write authority.

## Source-level safety

The project-owned Worker contract now stages:

- synthetic customer `account_status` and `segment` fields required by the Summary proof;
- exactly one POST route, `/users/1/update-draft`, for deterministic draft generation;
- every other non-GET/HEAD request remains rejected as `read_only_sandbox`;
- draft responses declare `draft_only=true`, `applied=false`, `review_required=true`, and `production_allowed=false`.

The Maestro preset routes remain Platform-Admin gated, reuse prepared PostgreSQL Evaluation authority, require live sandbox operational proof, and fail closed unless the resulting binding is `sandbox_ready` and selectable.

## Guided scenario contract repair

The customer-safe scenario samples were aligned with the canonical task catalog:

- Summary now includes both required inputs: `customer_id` and `account_status`.
- Draft uses canonical `proposed_changes` rather than the non-contract `requested_change` field.
- Draft includes an optional synthetic `reason` for evaluator readability.

This correction does not widen authority. The scenario still becomes runnable only when its task, matching prepared binding, and `/evaluation/runtime/task-execute` endpoint are sealed into the Evaluation Grant.

## Current activation boundary

The Cloudflare Worker source is updated in the repository, but this repository currently has no GitHub Actions workflow that performs `wrangler deploy`, and the current ChatGPT tool connection has no Cloudflare deployment connector.

Therefore:

1. do **not** describe CRM-SUMMARY-01 or CRM-DRAFT-01 as live-qualified yet;
2. do **not** expose the new Admin proof buttons as ready until the owned Worker v2 contract is deployed;
3. after deployment, prove `/users/1` contains the Summary fields and `/users/1/update-draft` returns a non-mutating draft;
4. then run each Platform-Admin preset once and require `sandbox_ready · selectable`;
5. create a fresh CRM Evaluation Grant containing only the intended new task/binding(s);
6. issue a fresh one-time Evaluation API key;
7. verify customer Workspace readiness and perform bounded Q4/Q5/Q6-style execution/replay/conflict checks for the newly affected scenario semantics only;
8. revoke the qualification key/grant and retain safe evidence for audit.

Do not reuse the revoked Q1–Q10 qualification grant/key from the foundation closeout.

## Tests added

`tests/test_external_evaluation_owned_crm_scenarios.py` verifies:

- Summary binding matches the canonical read contract;
- Draft binding is sandbox-only and uses the complete required POST request mapping;
- guided samples satisfy every canonical required input;
- the project-owned Worker source preserves a non-mutating draft contract;
- preset responses cannot claim a production mutation;
- content and secret references remain synthetic/project-owned and secret-value-free.

## Merge / qualification policy

These scenario changes affect prepared binding and sandbox-provider semantics. They must not inherit the `6f7dd018...` Q1–Q10 label automatically. Keep PR #210 Draft/Open until the current CI/security gates are green, the owned Worker is deployed and live-proven, and the newly affected CRM scenario qualification is complete.
