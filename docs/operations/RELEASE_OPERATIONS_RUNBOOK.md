# Processual Maestro — Release Operations Runbook

**Scope:** pre-release, Real Staging and controlled-production operational procedure  
**Authority:** documentation only; does not authorize staging or production actions  
**Default posture:** fail closed, preserve data, preserve evidence, stop before destructive recovery

## 1. Purpose

Provide one maintained operational procedure for:

- pre-deployment backup evidence;
- restore rehearsal;
- application rollback;
- migration rollback decision-making;
- service health verification;
- incident response and containment;
- evidence retention for readiness review.

This runbook must be exercised in Real Staging before it can support a production-readiness claim.

## 2. Current container/runtime contract

The repository Compose topology defines:

- API service: `api` / container `processual-maestro-api`;
- authentication delivery worker: `auth-delivery-worker` / `processual-auth-delivery-worker`;
- PostgreSQL: `db` / `processual-db`, PostgreSQL 16, persistent volume `pgdata`;
- Redis: `redis` / `processual-redis`;
- Prometheus: `prometheus` / `processual-prometheus`;
- Grafana: `grafana` / `processual-grafana`;
- API liveness endpoint: `http://localhost:8000/health/live` inside the API container;
- an internal Docker network;
- production-mode secrets supplied by environment/secret authority rather than committed values.

Never paste real credentials into this runbook, shell history, tickets or evidence artifacts.

## 3. Mandatory preconditions

Before any staging restore/rollback rehearsal or production recovery action, record:

1. environment identity;
2. exact repository SHA;
3. immutable image digest;
4. expected Alembic head;
5. current Alembic head;
6. database identity;
7. backup reference and digest;
8. operator name/role;
9. change or incident reference;
10. rollback decision owner;
11. start time in UTC.

For Real Staging and production, raw secret values must be supplied through the approved secret authority only.

## 4. Prohibited shortcuts

Do **not** use destructive volume deletion as a recovery mechanism.

Examples that are prohibited unless a separately authorized destructive-data procedure explicitly requires them:

```text
docker compose down -v
docker volume rm ...
DROP DATABASE ...
TRUNCATE ...
```

Do not delete the current database/volume before the backup has been independently verified and the restore target is identified.

Do not downgrade schema blindly merely because an application image is rolled back. Application rollback and schema rollback are separate decisions.

## 5. Pre-deployment database backup

### 5.1 Read-only checks

Confirm service state first:

```bash
docker compose ps
```

Confirm PostgreSQL is reachable through the Compose service:

```bash
docker compose exec -T db sh -lc 'pg_isready -U "${POSTGRES_USER:-processual}" -d "${POSTGRES_DB:-processual_db}"'
```

Record the current migration head from the application environment:

```bash
docker compose exec -T api python -m alembic current
```

### 5.2 Create logical backup

Create the evidence directory outside tracked source and with restrictive filesystem permissions appropriate to the deployment platform.

Example operator command:

```bash
mkdir -p release-evidence/runtime-backups
chmod 700 release-evidence/runtime-backups
```

Create a PostgreSQL custom-format logical backup without exposing the database password in the command line:

```bash
docker compose exec -T db sh -lc \
  'pg_dump -U "${POSTGRES_USER:-processual}" -d "${POSTGRES_DB:-processual_db}" -Fc' \
  > release-evidence/runtime-backups/pre-deploy.dump
```

Generate and retain a digest:

```bash
sha256sum release-evidence/runtime-backups/pre-deploy.dump \
  > release-evidence/runtime-backups/pre-deploy.dump.sha256
```

The backup itself is sensitive operational material and must not be committed to the public repository.

### 5.3 Backup acceptance

A backup is not accepted merely because `pg_dump` exited successfully.

Record:

- file is non-empty;
- SHA-256 exists;
- backup timestamp;
- source database/environment;
- exact source SHA/image digest;
- current migration head;
- encrypted storage/reference destination;
- retention/expiry policy.

## 6. Restore rehearsal

A restore rehearsal must use an **isolated target database/environment**. It must not overwrite the currently running database.

### 6.1 Minimum proof

The rehearsal must prove:

1. the retained backup can be read;
2. schema and data restore successfully into the isolated target;
3. migration state can be inspected;
4. application startup against the restored target succeeds;
5. health/readiness checks pass;
6. representative auth/commercial/read-only flows pass;
7. restored data integrity checks pass;
8. no production authority is inferred from a staging rehearsal.

### 6.2 Restore mechanics

The exact creation of the isolated restore database is deployment-platform specific and must be approved for the target environment.

Once an approved empty target database exists, restore the custom-format backup using `pg_restore` with the approved target connection parameters.

Do not embed target passwords in the command or evidence. Use the environment secret authority.

### 6.3 Evidence

Retain:

- source backup digest;
- isolated target identifier;
- restore start/end UTC;
- restore exit status;
- migration head after restore;
- application health result;
- selected smoke-test results;
- reviewer/approver;
- cleanup confirmation for the isolated target.

Real Staging readiness requires this proof against the actual staging secret/database authority, not only local Compose.

## 7. Application rollback

### 7.1 Trigger conditions

Rollback should be considered when the newly deployed candidate shows a material regression such as:

- startup/readiness failure;
- authentication authority regression;
- persistent migration/runtime incompatibility;
- elevated error rate;
- corrupt or inconsistent commercial/subscription behavior;
- secret/credential handling defect;
- security boundary regression;
- unrecoverable connector behavior;
- operator-approved SLO/rollback threshold breach.

### 7.2 Safe sequence

1. engage applicable kill switches / disable external execution paths;
2. stop traffic expansion;
3. capture current logs/metrics/correlation references without secrets;
4. identify last known-good image digest and source SHA;
5. determine whether the database schema is backward-compatible with that image;
6. if schema rollback is **not** required, roll back application image only;
7. if schema rollback **is** required, stop and enter the separately reviewed migration rollback procedure;
8. verify API/worker health;
9. verify authentication and critical read paths;
10. continue heightened monitoring;
11. record the final disposition.

Never infer that `alembic downgrade` is safe solely because a downgrade function exists.

## 8. Migration rollback decision

Migration rollback is a high-risk operation and requires an explicit compatibility decision.

Before any downgrade:

- identify exact current and target revisions;
- inspect the downgrade implementation for every intervening migration;
- identify irreversible or data-loss operations;
- confirm a verified pre-change backup exists;
- stop writes if required;
- obtain the designated release/database approval;
- rehearse the exact downgrade in Real Staging first where feasible.

If any migration is not safely reversible, prefer application forward-fix or restore-from-backup according to the approved incident decision rather than improvising a downgrade.

## 9. Service recovery checks

After deploy/rollback/recovery, verify at minimum:

```bash
docker compose ps
```

API liveness from inside the container:

```bash
docker compose exec -T api curl -fsS http://localhost:8000/health/live
```

Database health:

```bash
docker compose exec -T db sh -lc 'pg_isready -U "${POSTGRES_USER:-processual}" -d "${POSTGRES_DB:-processual_db}"'
```

Inspect migration state:

```bash
docker compose exec -T api python -m alembic current
```

Do not mark recovery complete until the expected migration head, API health, worker behavior, logs and monitoring agree.

## 10. Incident response

### 10.1 Severity and ownership

Every incident must have:

- named incident owner;
- severity;
- environment;
- start/detection time in UTC;
- affected surface;
- known authority/data exposure;
- containment status;
- rollback/forward-fix decision owner.

### 10.2 Immediate containment priorities

If a secret or authority boundary may be compromised:

1. stop expansion of affected traffic;
2. disable affected connector/provider execution if possible;
3. revoke/rotate exposed credentials through the secret/provider authority;
4. preserve audit/log evidence without copying raw secrets;
5. invalidate affected sessions/tokens/keys according to the relevant subsystem contract;
6. block compromised endpoint/configuration references;
7. escalate to security/privacy owners where required.

If database integrity is at risk:

1. stop unsafe writes if authorized and operationally possible;
2. preserve current database and logs;
3. take an incident snapshot/backup if safe;
4. do not destroy the primary volume;
5. choose forward repair, image rollback, schema rollback, or isolated restore based on evidence.

### 10.3 Evidence sanitation

Incident evidence may contain:

- source/image/revision identifiers;
- timestamps;
- sanitized error classes;
- request/correlation IDs approved for retention;
- service state;
- metrics;
- hashes/digests;
- decision/approval references.

Do not retain broad logs containing:

- client secrets;
- OAuth/access tokens;
- passwords;
- MFA secrets/recovery codes;
- raw sensitive request/response bodies;
- private keys;
- customer identifiers beyond the minimum privacy-approved need.

## 11. Post-incident exit gate

An incident is not operationally closed until:

- containment is verified;
- service health is stable;
- credential/key revocation or rotation is complete where applicable;
- data-integrity status is known;
- rollback/forward-fix outcome is recorded;
- monitoring confirms recovery;
- evidence is sanitized and retained;
- follow-up defects/actions have owners;
- a recurrence-prevention decision is recorded.

## 12. Real Staging qualification requirement

Before `RealStagingQualified=true`, execute and retain evidence for:

- backup creation;
- restore into an isolated staging target;
- application health against restored data;
- migration rehearsal;
- rollback/kill-switch drill;
- monitoring/alert observation;
- incident-response tabletop or controlled drill;
- named human approval.

Local Compose or CI rehearsal is useful preflight evidence only.

## 13. Authority boundary

This runbook does not change:

```text
RepositoryReconciliationComplete=false
GeneralPackagingComplete=false
RealStagingQualified=false
ProductionAuthorityGranted=false
```

No command in this document is authorization to execute against staging or production. Environment access and destructive actions require their separate operational approval.