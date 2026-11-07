# External Evaluation full-readiness gate before commercial presentations

Commercial presentations must not describe new External Evaluation scenarios as live until every applicable gate below is complete.

## Gate A — Public External Evaluation authority and Workspace

Required state:
- Render External Evaluation Authority is live on the intended public feature-branch head.
- `/console/evaluation.html` is reachable through the dedicated Evaluation origin.
- ZAXAM embeds only that dedicated origin with the scoped `frame-ancestors https://zaxam.net` contract.
- production execution remains disabled.

Current disposition: operationally live; latest-head GitHub Actions qualification remains a separate CI blocker.

## Gate B — Updated project-owned Cloudflare Worker

Required source:
- CRM customer fixture exposes `account_status` and `segment`.
- `POST /users/1/update-draft` returns a review-only draft with `draft_only=true`, `applied=false`, `review_required=true`, `production_allowed=false`.
- `GET /billing/accounts/1` returns only synthetic/non-production billing data.

Preferred guarded local deployment from Windows PowerShell:

```powershell
$env:CLOUDFLARE_API_TOKEN = '<set-in-process-only>'
$env:CLOUDFLARE_ACCOUNT_ID = '<set-in-process-only>'
$sha = (git rev-parse HEAD).Trim()
.\deployment\evaluation-owned-sandbox\cloudflare\deploy-and-verify.ps1 -ExpectedGitSha $sha
```

PASS requires the script to finish with its explicit `PASS:` line. A source commit, Render deploy, or Admin button is not Cloudflare deployment evidence.

## Gate C — Persist and live-prove every required binding

Using verified Platform Admin authority, run the owned scenario preparation controls. Each control must return backend proof with:
- `binding_selectable=true`
- `operational_proof=true`
- `peer_address_verified=true`
- `network_request_executed=true`
- `mapping_valid=true`
- `ready_for_task_consumption=true`
- `production_allowed=false`

Required bindings:

### CRM grant family
- `evaluation.crm.customer_context.owned`
- `evaluation.crm.customer_state_summary.owned`
- `evaluation.crm.customer_update_draft.owned`

### Integration grant family
- `evaluation.integration.billing_account_context.owned`

CRM Draft additionally requires:
- `draft_contract.operation_class=draft`
- `draft_contract.review_required=true`
- `draft_contract.applied=false`
- `draft_contract.production_mutation_performed=false`
- `draft_contract.production_allowed=false`

Any failed proof keeps that scenario blocked and must prevent it from entering a customer grant.

## Gate D — Fresh Evaluation Grants and one-time API keys

Never reuse the revoked qualification grant/key.

### CRM Evaluation grant
Recommended envelope:
- `evaluation_type=crm`
- tasks:
  - `crm.customer_context`
  - `crm.customer_state_summary`
  - `crm.customer_update_draft`
- bindings: the three matching CRM owned bindings
- endpoint: `POST /evaluation/runtime/task-execute`
- quota: `100` admitted executions
- subscription required: `false`
- production allowed: `false`

Issue a new one-time Evaluation key only after all three CRM bindings are selectable.

### Integration Evaluation grant
Recommended envelope:
- `evaluation_type=integration`
- task: `billing.account_context`
- binding: `evaluation.integration.billing_account_context.owned`
- endpoint: `POST /evaluation/runtime/task-execute`
- quota: `200` admitted executions
- subscription required: `false`
- production allowed: `false`

Issue a separate fresh one-time Evaluation key after the Integration binding is selectable.

Do not combine CRM and Integration into one grant merely for convenience; the grant type, quota policy, task scope and customer evaluation narrative must remain explicit.

## Gate E — Workspace qualification with fresh keys

For each fresh key:
1. Connect in External Evaluation Workspace.
2. Confirm credential active and expected Evaluation type.
3. Confirm only sealed tasks/bindings are shown.
4. Confirm all intended scenarios render `Runnable`, not `Locked`.
5. Execute each scenario once with a fresh idempotency key.
6. Confirm each fresh admitted execution consumes exactly `+1` quota.
7. Replay one identical operation and confirm `+0` quota.
8. Submit one idempotency conflict and confirm rejection with `+0` quota.
9. Confirm safe evidence exists and excludes raw key/raw task input/provider secret.
10. Confirm CRM Draft remains review-only and non-applying.
11. Confirm Billing remains synthetic/non-production.
12. Revoke the qualification key/grant after evidence capture and confirm authority ends while evidence remains reviewable.

Only after these checks may the new scenarios be described as live-qualified.

## Gate F — Private repository synchronization remains independent

Private synchronization does not block the public External Evaluation runtime, but it must be prepared safely before final repository convergence.

Only approved public synchronization target for private PR #56:

`6f7dd018737151cd1906be068f2478d02d19392b`

Use `docs/PRIVATE_REPO_POWERSHELL_SYNC_RUNBOOK.md` locally. Required disposition:
- private working tree clean
- never synchronize on private `main`
- protected private-only surfaces preserved
- local tests pass
- push only to staging/PR branch
- PR #56 remains Draft
- no private merge until GitHub Actions runner allocation returns and private CI/qualification executes successfully

## Commercial-deck release condition

Digital & Beyond / e& decks may be prepared only when:
- Gate A = PASS
- Gate B = PASS
- Gate C = PASS for every scenario intended to be demonstrated
- Gate D = fresh keys issued
- Gate E = fresh live qualification PASS
- Gate F = locally prepared or explicitly tracked as independent private convergence work, with PR #56 still Draft until CI returns

If any scenario has not passed Gates B–E, it must be labeled `planned`, `staged`, or `next evaluation scenario`, never `live` or `qualified`.
