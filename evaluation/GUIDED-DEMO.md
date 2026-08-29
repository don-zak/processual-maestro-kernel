# Processual Maestro — Startup Tunisia Guided Demo

## Purpose

This scenario is designed for a short evaluator walkthrough. It demonstrates the difference between merely calling an AI model and governing an operational AI workflow.

## Recommended scenario: Enterprise Incident / Ticket Governance

Use synthetic data only.

Example incident:

> A business customer reports repeated service interruptions during the last two hours. The SLA is at risk. Analyze the incident, identify the likely operational priority, recommend the next action and explain what should require human validation.

## Narrative

1. **Input** — a user or application submits a controlled operational task.
2. **Identity / Authority** — Maestro identifies the actor and checks whether the requested operation is within the allowed authority.
3. **Entitlement / Quota** — the runtime verifies that the capability is included and that sufficient usage capacity remains.
4. **Runtime capacity** — the system verifies that operational capacity is available.
5. **Governed processing** — the task is handled through the public evaluation path. External LLM execution remains disabled by default in the portable bundle.
6. **CGT / Governance evidence** — show the evaluation or governance signals exposed by the public runtime without exposing private CGT implementation details.
7. **Decision** — explain how governance can support continue, control, repair, clarification or stop behavior according to policy.
8. **Human validation** — keep sensitive operational actions recommendation-only in the first POC.
9. **Audit / Evidence** — show that the important decision path is traceable and reviewable.

## What the evaluator should understand

- Maestro is not only an agent builder or chat interface.
- Authorization is separated from execution.
- Commercial rights, quotas and runtime capacity influence execution.
- Governance participates in the execution lifecycle rather than only observing the final output.
- The same control plane is designed to sit above multiple providers and integrations.
- Important decisions are auditable.

## Five-minute product demo structure

- **0:00–0:30** — Evaluation Home + purpose of the POC.
- **0:30–1:15** — Console / Front Office: submit or inspect the incident workflow.
- **1:15–2:15** — Show identity, authority, entitlement, quota and runtime constraints.
- **2:15–3:20** — Show CGT/governance-facing evaluation and explain continue/control/repair/stop semantics.
- **3:20–4:20** — Admin / audit / evidence surfaces.
- **4:20–5:00** — Scalability: same core, adapters/providers, read-only first POC, then controlled expansion.

## Evidence discipline

Do not describe Mock/Sandbox evidence as Production. Do not expose production credentials, private CGT formulas or private repositories. Use only synthetic information in this evaluation edition.
