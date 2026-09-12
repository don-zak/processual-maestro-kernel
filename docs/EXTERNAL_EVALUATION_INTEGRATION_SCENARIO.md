# External Evaluation — Integration Billing Scenario

## Status

`INT-BILLING-01` is implemented and staged on the working branch. It is **not live-qualified** until the updated project-owned Cloudflare Worker is deployed and a fresh Integration Evaluation Grant/key pair is used for qualification.

The previously revoked CRM qualification Grant/key must not be reused.

## Scenario

- Scenario: `INT-BILLING-01`
- Title: Integration Billing Account Context
- Canonical task: `billing.account_context`
- Operation class: `read`
- Adapter contract: `billing`
- Required scope: `billing:read`
- Owned binding: `evaluation.integration.billing_account_context.owned`
- Owned sandbox path: `GET /billing/accounts/1`
- Evaluation type: `integration`
- Recommended admitted-execution quota: `200`
- Subscription required: `false`
- Production allowed: `false`

## Synthetic sandbox contract

The project-owned Worker source exposes a deterministic synthetic billing account with:

- `account_id`
- `balance`
- `currency`
- `invoice_status`
- `payment_status`
- `synthetic=true`
- `production_allowed=false`

No billing write route is introduced for this scenario. Non-CRM/non-draft mutation attempts remain rejected by the Worker read-only boundary.

## Authority and readiness

The scenario is visible only when `billing.account_context` is inside the sealed Evaluation Grant.

It becomes runnable only when all of the following are true:

1. the Grant contains `billing.account_context`;
2. the Grant contains `evaluation.integration.billing_account_context.owned`;
3. authoritative prepared-binding storage maps that binding to the same canonical task;
4. the Grant contains `POST /evaluation/runtime/task-execute`;
5. the binding has reached sandbox-ready selectable state.

Client-side scenario metadata cannot add any task, binding, endpoint, scope, quota, or production authority.

## Qualification proof required

After the Worker source is actually deployed:

1. provision the owned billing binding through the Platform Admin preset;
2. require the operational proof to verify network request, peer address, response mapping, and readiness;
3. issue a new Integration Evaluation Grant with only the required task/binding/runtime endpoints and quota `200`;
4. issue a fresh one-time Evaluation API key;
5. verify status read consumes `+0`;
6. execute `INT-BILLING-01` and verify a fresh admitted execution consumes exactly `+1`;
7. verify durable replay consumes `+0`;
8. verify conflicting idempotency request consumes `+0`;
9. verify safe evidence is persisted without raw key, raw task input, or provider secret material;
10. revoke the key/Grant and verify authority ends immediately while historical evidence remains reviewable.

## Guarded deployment path

The repository now contains a manual-only workflow:

`.github/workflows/evaluation-owned-sandbox-cloudflare.yml`

The workflow is intentionally fail-closed:

- it runs only through `workflow_dispatch`;
- the operator must supply the exact commit SHA expected to be deployed;
- checkout is verified against that exact SHA before tests or deployment;
- owned CRM, Integration, and sandbox contract tests execute before deployment;
- deployment requires the `external-evaluation-sandbox` GitHub Environment;
- Cloudflare authority is read only from repository/environment secrets named `CLOUDFLARE_API_TOKEN` and `CLOUDFLARE_ACCOUNT_ID`;
- the workflow contains no secret values;
- Wrangler is pinned explicitly (`4.131.1`) instead of relying on a mutable global install or a nonexistent package lock;
- no push or pull-request event can deploy the Worker automatically.

## Remaining deployment blocker

The guarded workflow has **not been executed**. GitHub Actions is currently failing to allocate new jobs for the latest public branch heads, and the presence/authorization of the required Cloudflare secrets/environment has not been proven in an executable run.

Therefore Worker source presence and workflow presence must not be treated as live sandbox deployment. The updated Worker is considered deployed only after an executable runner completes the exact-ref verification, contract tests, Cloudflare deployment, and a subsequent live endpoint proof.
