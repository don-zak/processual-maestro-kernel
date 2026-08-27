# Pre-Launch Readiness Evidence Pack — 2026-08-27

## Decision scope

This pack records evidence for **readiness immediately before launch**. It does not start production services, enable commercial feature flags, provision real secrets, or authorize production launch.

## Pinned public evidence

- Repository: `don-zak/processual-maestro-kernel`
- Public `main`: `d2a0baa912efc384c57d086a4d67a8ac29d20987`
- Qualification head proven before readiness-document commits: `21f5db6217418df77165dd83faf2217cff58d9af`
- Program Release Qualification #748: **SUCCESS**
- Launch Closeout Gate #715: **SUCCESS**

### Program Release Qualification #748 proved

- registration and plan qualification;
- subscription entitlement and quota qualification;
- supervisor workspace qualification;
- public UI, browser security and legacy quarantine qualification;
- compatibility retirement qualification;
- production environment and Infisical contract qualification;
- static quality gate;
- secret scan;
- dependency audit.

### Launch Closeout Gate #715 proved

- PostgreSQL service initialization;
- upgrade to the guarded legacy-retirement predecessor;
- guarded legacy quota retirement on real PostgreSQL;
- consolidated PostgreSQL and Redis authority gate;
- container cleanup after qualification.

## Splash archive/quarantine closeout

- Preserved source SHA: `3775d5e4d8ab114f5503de57bab53ecc26e1b32e`
- Archive branch: `archive/maestro-splash-development-2026-08-27`
- Cleanup commit: `4ccbab7ca416eba898e1a0b15904422d6ccf1089`
- Repository archive: `docs/archives/maestro-splash/maestro-splash-development-archive-2026-08-27.zip`
- ZIP SHA256: `ee1d6ce945cfe7c13f7b0893df390ef85dc255d66c51d4717525321bd45a8c16`

Splash-specific development assets were archived and quarantined while the operational entrypoint remained protected. The final bilingual public qualification contract was corrected at `21f5db6217418df77165dd83faf2217cff58d9af` and passed Program Release Qualification #748.

## Private repository evidence

- Repository: `don-zak/processual-maestro-kernel-private`
- Private `main`: `84e3354cd43802176ee93ed94f72144341c0068b`
- Security-readiness branch: `agent/prelaunch-security-readiness-20260827`
- Patch head: `a80923fa482f4412c4ce3980f1d262a35bdb42ec`
- Draft PR: #55

### Supply-chain finding

The scheduled private Security Scan on 2026-08-24 passed Bandit but failed dependency auditing because the CI constraint pinned `pip==26.1.2`, affected by `PYSEC-2026-3721`. The published fixed version was `26.2`.

PR #55 changes only the constraint to `pip==26.2`.

### CI infrastructure limitation

The private PR triggered multiple workflows. The private monorepo CI job was attempted twice. Both attempts ended before a runner was allocated, with:

- `runner_id=0`;
- empty runner name;
- `steps=[]`;
- no executable job log.

This is classified as **CI runner-provisioning failure**. It is not evidence of a code/test failure, and it is also not evidence of a successful security patch. PR #55 must remain unmerged until executable CI proof is available.

## Production configuration gate

The public production template and settings logic enforce a fail-closed production posture for core secrets and runtime configuration. Production deployment must use real, non-placeholder values stored outside source control.

At minimum, verify the final deployment values for:

- `JWT_SECRET`;
- `API_KEYS`;
- `PROCESSUAL_CRYPTO_KEY_B64`;
- `DATABASE_URL` / `POSTGRES_PASSWORD`;
- `REDIS_URL` / `REDIS_PASSWORD`;
- `MAESTRO_ADMIN_EMAIL` / `MAESTRO_ADMIN_PASSWORD`;
- `GRAFANA_ADMIN_PASSWORD`;
- authentication peppers/key rings;
- MFA key ring;
- Admin Marketplace payment-destination key ring;
- billing/provider secrets for only the integrations actually enabled.

No real secret should be committed to either repository.

## Backup / restore evidence gate

Before a production-launch decision, create and retain two real environment-specific identifiers:

- `MIGRATION_BACKUP_REFERENCE`
- `MIGRATION_RESTORE_REHEARSAL_REFERENCE`

These must refer to an actual backup and an actual restore rehearsal. CI placeholders or invented evidence are not acceptable.

Required rehearsal outcome:

1. create a backup from the intended pre-launch database state;
2. restore into an isolated target;
3. run schema/migration verification;
4. verify critical registration/subscription/quota/admin reads after restore;
5. record artifact identifiers, timestamps and integrity hashes where available;
6. keep production untouched during the rehearsal unless a controlled deployment procedure explicitly requires otherwise.

## Commercial feature gates

The following must remain fail-closed until their dedicated evidence is complete:

- Tunisia-local top-up runtime;
- Tunisia-local top-up admin enablement;
- any billing/provider integration lacking real webhook/signature and rollback/replay evidence;
- any migration or destructive maintenance operation lacking backup/restore evidence.

## Public/private compatibility

See `docs/qualification/public_private_compatibility_manifest_20260827.md`.

The public repository currently owns the qualified application/commercial runtime; the private repository owns proprietary CGT/private-engine material. Equal package version labels do not imply configuration parity. A launch release must pin a tested public-runtime ↔ private-engine compatibility pair.

## Final pre-launch checklist

| Gate | Current status | Launch requirement |
|---|---|---|
| Public Program Release Qualification | GREEN on `21f5db...` | Keep green on final release candidate |
| Real PostgreSQL/Redis authority gate | GREEN on `21f5db...` | Keep green on final release candidate |
| Public static quality / secret / dependency audit | GREEN on `21f5db...` | Keep green |
| Splash quarantine/archive | GREEN | Preserve archive and invariants |
| Private pip vulnerability patch | PATCHED ON BRANCH | Executable private CI must pass before merge/use |
| Private CI | INFRASTRUCTURE BLOCKED | Obtain real runner execution |
| Public/private compatibility manifest | CREATED | Pin release compatibility tuple |
| Production secrets | NOT PROVISIONED BY THIS PACK | Validate in intended secret manager |
| Backup reference | PENDING REAL EVIDENCE | Required |
| Restore rehearsal reference | PENDING REAL EVIDENCE | Required |
| Environment-specific deployment smoke | PENDING | Required before launch |
| Tunisia local top-up | FAIL-CLOSED | Enable only after dedicated Package B proof |
| Startup Tunisia technical POC pack | CREATED | Add founder business/legal evidence |

## Decision

### Technical pre-launch readiness

**CONDITIONAL GO FOR FINAL PRE-LAUNCH PREPARATION.**

The public runtime has strong current CI evidence. Production launch remains blocked by environment-specific evidence and the unresolved private CI runner-provisioning condition.

### Production launch

**NO-GO until all required real-environment and private-executable evidence is present.**

This is intentional and preserves the fail-closed launch policy.
