# Processual Maestro — Startup Tunisia Evidence Index

## Purpose

This index tells the application team exactly what evidence may be shown to Startup Tunisia reviewers and what must remain private. It is not a substitute for the official legal documents, Pitch Deck or founder video.

## A. Public-facing technical evidence

### 1. Public repository

Repository: `don-zak/processual-maestro-kernel`

Use as optional technical evidence after the product story is clear. The public repository is the sanitized review/evaluation surface; do not provide the private repository by default.

### 2. Product/runtime proof

Recommended evidence:

- public README and runtime instructions;
- public/private repository scope documentation;
- controlled client/demo guide;
- OpenAPI/Swagger in a demo environment;
- health/readiness evidence;
- representative CGT governance output;
- entitlement/quota/audit evidence.

### 3. R5 exact-head qualification

SHA: `7082565508537e0c54312c09620cc06ed3e56edb`

Use this as the clean unified Tunisia top-up E2E qualification head.

Recorded successful gates:

- CI (Public) — SUCCESS.
- Security Hardening — SUCCESS.
- M1 Runtime Authority Qualification — SUCCESS.
- Orchestration Soak — SUCCESS.
- Topology Benchmark — SUCCESS including staging canary.

The E2E demonstrates:

```text
order
 -> FX snapshot
 -> payment verification/evidence
 -> atomic quota grant
 -> identical replay
 -> reversal
 -> identical reversal replay
```

### 4. R6 PostgreSQL operational evidence

SHA: `cd93a0ce97b6db886c000a747d3981ecb80241c8`

Workflow: **Pre-launch Operational Evidence**  
Run: `33166590476`  
Result: **SUCCESS**

Proof produced:

- PostgreSQL 17 full Alembic chain to `20260828_0047r`;
- PostgreSQL 17 `pg_dump`;
- isolated database restore;
- restored migration authority check;
- upgrade-to-head idempotence;
- production environment release-contract regression (`3 passed`);
- uploaded evidence artifact.

Artifact:

- ID: `9683836066`
- Name: `prelaunch-postgres-backup-restore-evidence`
- Dump SHA-256: `dfbf4c3ac2f52aadbebddf3d04b75a33db3c768baa29445e7e982e8a16b5784b`
- ZIP digest: `sha256:bdbf4bab39c92736a5da45bfdcd26deb6d77e432a84582be543bcefbbd8dcd69`

The rehearsal also discovered and closed a real PostgreSQL JSON migration defect in migration `20260807_0039`, providing stronger evidence than a fake/synthetic readiness claim.

### 5. Release status wording

Use these three labels consistently:

- **Demo Ready** — safe to show now.
- **Qualified but Fail-Closed** — technically qualified but intentionally disabled for real-money/production use pending operational authority.
- **Production Live** — only after target-environment evidence and explicit GO.

Do not describe Tunisia local top-up as Production Live.

## B. Recommended visual evidence for the Pitch/Demo

Prepare screenshots or short recordings of:

1. governed user/organization entry;
2. plan/entitlement/quota state;
3. AI-agent task submission;
4. CGT allow/block/repair decision;
5. audit/evidence output;
6. quota consumption before/after;
7. admin/supervisor visibility;
8. Tunisia payment destination and `Activate payment route` flow;
9. optional architecture diagram showing Processual Maestro between organizations and agent/model providers.

Use synthetic identifiers and masked payment fields.

## C. Business evidence to add from real records

- `[TO COMPLETE]` target segment and buyer persona;
- `[TO COMPLETE]` problem interviews / pilot evidence;
- `[TO COMPLETE]` LOIs or customer references, if real;
- `[TO COMPLETE]` pricing/business model;
- `[TO COMPLETE]` market sizing with citations;
- `[TO COMPLETE]` competitor/alternative matrix;
- `[TO COMPLETE]` traction/revenue only if documented;
- `[TO COMPLETE]` 12–18 month milestones.

## D. Team evidence to add

- `[TO COMPLETE]` founder/co-founder names;
- `[TO COMPLETE]` roles;
- `[TO COMPLETE]` relevant professional/technical experience;
- `[TO COMPLETE]` team size and responsibilities;
- `[TO COMPLETE]` hiring/partner needs if relevant.

## E. Legal evidence

For an incorporated Label application, prepare the current official documents listed in `STARTUP_TUNISIA_PORTAL_CHECKLIST_20260828.md`.

If applying for Pre-Label, follow the active portal's required legal/identity fields for that session; do not assume the incorporated-company list applies unchanged.

## F. Evidence that must remain private unless specifically redacted and approved

- private GitHub repository;
- proprietary/private CGT modules;
- real API/provider keys;
- JWT or database credentials;
- `.env` files;
- real customer/runtime data;
- raw unredacted bank identifiers;
- secret-manager screens;
- internal handoff/debug reports;
- security-sensitive logs that reveal infrastructure details.

## G. Final technical PDF outline

When producing `PROCESSUAL_MAESTRO_TECHNICAL_POC_EVIDENCE_2026.pdf`, keep it concise:

1. Product/POC statement — 1 page.
2. Architecture and public/private boundary — 1 page.
3. Governed execution flow — 1 page.
4. Innovation/CGT evidence — 1–2 pages.
5. Scalability/operational architecture — 1 page.
6. Exact-SHA CI/security/topology evidence — 1 page.
7. PostgreSQL migration + backup/restore rehearsal — 1 page.
8. Demo-ready vs fail-closed vs production-live table — 1 page.
9. Public technical links — 1 page.

Avoid turning the technical evidence pack into a development history report.