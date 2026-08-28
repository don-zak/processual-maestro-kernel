# Processual Maestro — Startup Tunisia Demo Script

## Objective

Demonstrate a real POC story that makes **Innovation + Scalability** visible without exposing private implementation, secrets or real-money operations.

Recommended live-demo duration: **4–6 minutes**. This is an internal presentation target, not a claimed Startup Tunisia portal limit.

## Pre-demo safety checklist

- [ ] Use a dedicated demo/evaluation environment.
- [ ] Use synthetic organization/user data only.
- [ ] Use demo API credentials only; never display the raw secret after setup.
- [ ] No `.env` file, real provider key, database password or private repository is visible on screen.
- [ ] Keep Tunisia local top-up fail-closed; do not transfer real money.
- [ ] Preload one normal task, one policy-block example and one repair example.
- [ ] Confirm `/health` and readiness before presentation.
- [ ] Keep a recorded fallback walkthrough/screenshots available if the live environment becomes unavailable.

## Demo story

### Scene 1 — Governed entry (30–40 sec)

Show the user/organization context and explain:

> “The agent is not entered directly. Execution starts inside a governed identity and authority context.”

Show only the minimum evidence of authenticated/governed access.

**Point proven:** this is a control layer, not a public unbounded agent endpoint.

### Scene 2 — Runtime rights (30–40 sec)

Show the active plan/entitlement/quota context.

Explain:

> “Before an agent task can consume resources, Processual Maestro knows what this organization is entitled to execute and what quota remains.”

**Point proven:** commercial rights and runtime authority are connected.

### Scene 3 — Submit an AI-agent task (40–60 sec)

Submit a representative safe task through the public/evaluation surface.

Show:

- task identity/context;
- selected provider/runtime abstraction where appropriate;
- no private provider secret.

Explain that the same governance layer can sit above different runtimes/providers.

**Point proven:** provider/runtime independence and product scalability.

### Scene 4 — CGT governance decision (60–90 sec)

Show the clearest available governance evidence:

```text
observation/context
 -> CGT/policy evaluation
 -> allow / block / repair
 -> evidence
```

Prefer a repair or block example because it makes the value more visible than a successful request alone.

Explain:

> “The platform does not only execute. It can recognize an unacceptable or degraded path, block it or repair it, and retain the reason as evidence.”

**Point proven:** innovation and differentiated control behavior.

### Scene 5 — Audit evidence + quota consumption (40–60 sec)

After execution, show:

- execution/audit evidence;
- relevant decision/outcome;
- quota/usage change.

Explain:

> “The result is coupled to a durable record of what happened and to measurable consumption of the organization’s runtime rights.”

**Point proven:** auditability + measurable commercial governance.

### Scene 6 — Admin/supervisor visibility (40–60 sec)

Switch to the admin/supervisor surface and show the same activity from the operational side.

Focus on:

- visibility into governed operations;
- evidence/state rather than editing internals;
- recovery/administrative authority where relevant.

**Point proven:** operational product, not only an API prototype.

### Scene 7 — Tunisia commercial readiness (30–45 sec)

Show the local payment-destination setup and **Activate payment route** flow.

Explain:

> “For an eligible Tunisia customer, commercial availability is still decided server-side. The administrator configures and activates the payment route; the client does not bypass eligibility rules.”

If useful, show that local top-up is **Qualified but Fail-Closed**, not Production Live.

**Point proven:** the platform can connect governed execution to a real commercial operating model without misrepresenting launch status.

## Close (15–20 sec)

Close with one sentence:

> “Processual Maestro turns heterogeneous AI-agent execution into a governed, auditable and commercially controllable operating layer.”

## Three proof moments reviewers should remember

1. **A task can be allowed, blocked or repaired under governance — not only executed.**
2. **The decision creates audit evidence and consumes controlled runtime rights.**
3. **The same layer is designed to work across providers/runtimes and organizational use cases.**

## Fallback if live demo fails

Use, in this order:

1. a pre-recorded walkthrough of the exact same story;
2. 5–7 annotated screenshots in the Pitch appendix;
3. technical evidence index with exact release SHA and successful workflow evidence.

Never troubleshoot secrets, production databases or private modules live in front of reviewers.

## Do not show

- private repository screens;
- raw source-code tours unless explicitly requested by a technical reviewer;
- API keys, JWTs, passwords, encrypted payloads or secret-manager contents;
- real customer data;
- real bank identifiers beyond intentionally masked demo fields;
- production flags being enabled;
- long CI logs in the main demo.

If a technical reviewer asks for deeper proof, use the public repository and the technical evidence pack after the product story is complete.