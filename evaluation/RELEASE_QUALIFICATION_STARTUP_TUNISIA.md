# Processual Maestro — Startup Tunisia Evaluation Release Qualification

## Qualified head

- Branch: `agent/startup-tunisia-evaluation-edition`
- Head: `ffe91ab528c3dca71f3b8cac2c80c07536a18386`
- Pull request: #191

## CI evidence

- Startup Tunisia Evaluation Edition — run #8: **success**
- Portable Evaluation Bundle — run #15: **success**
- Artifact ID: `9715035222`
- Artifact digest: `sha256:cec740e108469df6a02531d47b6e010c8407a407e59ef56af90e081b8a714346`

## Distribution integrity

The generated outer Actions artifact contains:

- `Processual-Maestro-Portable-Evaluation.zip`
- `Processual-Maestro-Portable-Evaluation.zip.sha256`

Verified inner distribution SHA-256:

`0c710f88aff0bcaa21d049f0a02703c815211fcb04d8e76a8eb1ba01081dbd0e`

The archive checksum matches its companion `.sha256` file.

`SHA256SUMS.txt` inside the distribution was verified successfully for:

- `images/processual-maestro-evaluation-v1.tar`
- `images/postgres-17-alpine.tar`
- `images/redis-7-alpine.tar`
- `RELEASE_MANIFEST.json`

## Reviewer flow

The package includes:

- `START-MAESTRO.ps1`
- `SHOW-EVALUATION-ACCESS.ps1`
- `RUN-GUIDED-DEMO.ps1`
- `EVALUATION_HOME.html`
- `GUIDED-DEMO.md`
- `RECORDED-GOVERNANCE-EVIDENCE.html`
- `CHECK-STATUS.ps1`
- `RESET-DEMO.ps1`
- `STOP-MAESTRO.ps1`
- bundled Docker images for the API, PostgreSQL and Redis

The recommended evaluator story is:

`runtime health -> Console -> authority/entitlement/quota controls -> governance/CGT evidence -> Admin/audit -> technical API evidence`

## Safety boundary

- no Production secrets are shipped;
- local evaluation secrets are generated at first start;
- secrets are hidden by default by the access helper;
- private `cgtlib/private` implementation is excluded from the public image;
- external billing and real Tunisia top-up are disabled;
- external LLM execution is disabled by default;
- the guided scenario uses synthetic information;
- recorded governance evidence is explicitly identified as non-live;
- Mock/Sandbox evidence must not be described as Production evidence.

## Network-independence caveat

The runtime and Docker dependencies are portable and locally bundled. Static inspection of the built image nevertheless found presentation-layer network references in legacy UI surfaces:

- Google Fonts in Console/Login/Splash pages;
- Chart.js loaded from jsDelivr in the Console;
- Swagger UI / ReDoc assets provided by FastAPI from CDN URLs.

These references do **not** change the runtime safety boundary or the recorded evidence replay, but they mean the current package should be described as a **portable evaluation runtime**, not as a fully network-independent UI distribution.

The evaluator home and recorded evidence pages themselves are self-contained and do not load Google Fonts or jsDelivr.

## Publication decision

**Qualified for controlled evaluation / demo use.**

**Not yet qualified for the stronger claim “fully offline UI bundle”.**

Before publishing on `zaxam.net`, either:

1. vendor/remove the remaining UI CDN dependencies; or
2. publish with the precise label `Portable Evaluation Runtime` and state that some optional visual/API-documentation assets may require internet access.

No Production Authority claim is implied by this qualification.
