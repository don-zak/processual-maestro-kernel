# Startup Tunisia Portal Checklist — 2026-08-28

This checklist separates the **official portal/legal submission** from optional technical evidence. Re-check the live Startup Tunisia portal immediately before filing because session fields and accepted formats can change.

## 1. Choose the correct route

### A. Company already incorporated under Tunisian law — Startup Label

Use the Startup Label route and verify all five label criteria:

1. Age: company less than 8 years old.
2. Size: fewer than 100 employees and total balance sheet or annual turnover below 15 million TND.
3. Capital independence: more than 2/3 of capital held by individuals, regulated investment organizations and/or foreign startups as defined by the framework.
4. Innovation: differentiated/interesting solution and innovative business model.
5. Scalability: large/homogeneous target market, solution-market fit and a team capable of execution.

### B. Company not incorporated yet — Pre-Label

A natural person may apply when the project satisfies **Innovation + Scalability**. The Pre-Label is valid for six months; the company must then be incorporated and satisfy age, size and independence before the period expires to obtain the Label.

**Route decision to complete before filing:**

- [ ] Incorporated company → Label.
- [ ] Not incorporated → Pre-Label.
- [ ] Verify the active portal exposes the expected route for the current session.

## 2. Official documents currently published for a submitted Label application

Prepare the following as current, readable files:

1. [ ] Trade register extract, not older than 3 months.
2. [ ] Financial statements for the last 3 fiscal years, where applicable to the company's age/status.
3. [ ] CNSS declaration.
4. [ ] Company statutes.
5. [ ] Shareholder register.
6. [ ] Pitch Deck.
7. [ ] Video in which founders/co-founders present the project, maximum 3 minutes.

Do not fabricate unavailable historical financial statements. If the company is younger than the requested period or a document is not applicable, follow the portal's current handling/instructions rather than inventing a substitute.

## 3. Recommended dossier filenames

These names are an internal organization convention; portal filenames/formats must follow the active portal constraints.

```text
01_trade_register_YYYYMMDD.pdf
02_financial_statements_<years>.pdf
03_cnss_declaration.pdf
04_company_statutes.pdf
05_shareholder_register.pdf
06_processual_maestro_pitch_deck.pdf
07_processual_maestro_founder_video.mp4
```

Optional supporting material, only if the portal provides an appropriate field or the committee requests it:

```text
08_processual_maestro_demo_link_or_walkthrough.pdf
09_processual_maestro_technical_poc_evidence.pdf
10_processual_maestro_architecture.pdf
```

## 4. Official evaluation points to address directly

The application materials must make it easy to evaluate:

- [ ] Concept.
- [ ] Business model.
- [ ] Pitch.
- [ ] Product demo / POC.
- [ ] Innovation.
- [ ] Scalability.

The POC must be visible and understandable without asking reviewers to inspect source code.

## 5. Processual Maestro evidence mapping

### Innovation

Show:

- runtime-independent AI-agent governance;
- CGT adaptive governance/evaluation;
- allow/block/repair decisions with evidence;
- auditability;
- commercial rights connected to runtime entitlements/quotas;
- provider failure containment and resumable/idempotent flows.

### Scalability

Show:

- multi-provider/multi-runtime control plane;
- PostgreSQL + Redis distributed architecture;
- multi-worker topology evidence;
- subscription/entitlement/quota model;
- public evaluation + protected private engine;
- container/cloud deployment path.

### POC

Use one flow:

```text
User/organization
 -> governed access
 -> entitlement/quota
 -> AI-agent task
 -> CGT decision
 -> audit evidence
 -> quota consumption
 -> admin/supervisor visibility
```

Do not use real payment processing as a POC requirement. Tunisia payment-destination readiness may be shown as commercial evidence without transferring real funds.

## 6. Founder/business facts that must be supplied from real evidence

Complete before final Pitch Deck/video submission:

- [ ] Legal company name / route (Label or Pre-Label).
- [ ] Founder/co-founder names and roles.
- [ ] Relevant founder/team experience.
- [ ] Team size.
- [ ] Target customer segment.
- [ ] Customer/problem discovery evidence.
- [ ] Pilots, LOIs, users, revenue or traction — only if real and documentable.
- [ ] Pricing/business model.
- [ ] Market sizing with cited sources.
- [ ] Competitor/alternative comparison.
- [ ] 12–18 month milestones.
- [ ] Funding/resource plan if relevant.

## 7. Final portal preflight

Immediately before submission:

- [ ] Open the official Startup Tunisia portal from the official site.
- [ ] Confirm current application session is open.
- [ ] Confirm Label vs Pre-Label route.
- [ ] Confirm current fee, if any.
- [ ] Confirm allowed file formats and size limits.
- [ ] Confirm whether Pitch Deck/video fields are mandatory in this exact session.
- [ ] Confirm video maximum duration.
- [ ] Confirm any language constraints displayed by the active form.
- [ ] Confirm all legal documents are current and legible.
- [ ] Open every uploaded PDF/video after upload to verify it is the intended file.
- [ ] Keep a local immutable copy of the submitted dossier and submission receipt/reference.

## 8. What not to submit by default

- private GitHub repository;
- real API keys or secrets;
- `.env` files;
- internal/private CGT implementation;
- raw customer/runtime data;
- internal handoff reports;
- unredacted security logs;
- claims of Production Live that are not backed by target-environment evidence.

The public GitHub repository may be provided as **optional technical evidence**, not as a substitute for the Pitch, Demo and business application.