# AUTH-R10 Production Runtime Readiness

**Final status:** PASSED  
**Date:** 2026-07-27  
**Target branch:** `main`  
**Closure branch:** `docs/auth-r10-production-runtime-readiness`

---

## 1. Executive Decision

AUTH-R10 production runtime readiness is accepted.

The authentication runtime has completed the required delivery lifecycle, protected operations, concurrency, graceful shutdown, reconciliation, and crash-recovery verification work.

Final decision:

```text
AUTH-R10 production runtime readiness: PASSED
```

No additional AUTH-R10 crash-recovery candidate is required.

---

## 2. Accepted Scope

The accepted AUTH-R10 scope includes:

- governed authentication delivery lifecycle;
- protected delivery operations;
- multi-worker delivery concurrency;
- graceful worker process shutdown;
- reconciliation after interrupted delivery processing;
- Docker container restart recovery;
- idempotent duplicate delivery handling;
- deterministic MFA ciphertext tamper testing;
- full public test-suite qualification;
- successful public CI qualification.

---

## 3. Completed Authentication Milestones

### R8D — Platform administration authority

Platform-level authentication authority and governed session claims were established and verified.

### R9A — Account recovery

Secure account recovery flows and delivery integration were completed.

### R9B — Delivery lifecycle

The authentication delivery lifecycle was hardened with explicit claim, retry, delivery, stale-finalization, and dead-letter behavior.

### R9C — Protected delivery operations

Protected operational controls for delivery inspection and management were completed.

Relevant merged components include:

```text
processual_api/auth/delivery_operations_http_contracts.py
processual_api/auth/delivery_operations_router.py
processual_api/auth/delivery_operations_runtime.py
processual_api/auth/delivery_operations_service.py
```

Relevant verification includes:

```text
tests/test_auth_delivery_operations_http_r9c.py
tests/test_auth_delivery_operations_repository_r9c.py
tests/test_auth_delivery_operations_service_r9c.py
```

### R9D — Multi-worker concurrency

Multi-worker delivery concurrency was verified through integration testing.

Evidence test:

```text
tests/integration/test_auth_delivery_multi_worker_concurrency_r9d_integration.py
```

### R10B — Graceful worker process shutdown

The real worker process was verified to:

- receive `SIGTERM`;
- finish its active batch;
- avoid starting a second batch;
- close database resources;
- return the expected aggregate result;
- exit successfully.

Evidence test:

```text
tests/integration/test_auth_delivery_worker_process_r10b_integration.py
```

The test environment was corrected to provide strong explicit settings to the spawned child process so that security warnings did not incorrectly fail the empty-`stderr` assertion.

### R10C — Crash recovery

AUTH-R10C crash recovery was verified through reconciliation and Docker restart scenarios.

---

## 4. C6-H Reconciliation

C6-H established successful reconciliation behavior after interrupted or stale delivery processing.

Accepted behavior included:

- recovery from stale claim state;
- valid final delivery state;
- absence of an active claim after reconciliation;
- no incorrect dead-letter outcome;
- preserved idempotency behavior.

C6-H is accepted as complete.

---

## 5. C6-I Docker Container Restart Recovery

### Final accepted candidate

```text
Candidate:       05
Outbox ID:       eec494e5-9fbf-4b8a-86d3-1520fd6ac51d
User ID:         1842c926-45c1-5b2d-84d0-d251041f7e29
Action token ID: c15fac2a-a907-5c27-97c6-66b16b1028a7
Recipient:       auth-r10c-c6i-container-restart-05@example.test
Idempotency key: pmk-auth-delivery-v1:eec494e5-9fbf-4b8a-86d3-1520fd6ac51d
```

### Initial pristine state

```text
CandidatePending: True
CandidateAttemptCount: 0
CandidateClaimId:
CandidateDeliveredAt:
CandidateDeadLetteredAt:
CandidateLastErrorCode:
```

Initial database baseline:

```text
Total:          37
Pending:         1
Delivered:      31
Dead-lettered:   5
```

### Runtime configuration

```text
Lease:                  30 seconds
Provider timeout:       60 seconds
Provider URL:           https://host.docker.internal:65534/auth-r10c-provider
Health endpoint:        https://127.0.0.1:65534/health
Worker container:       processual-auth-delivery-worker
Database container:     pmk-auth-r10c-runtime-r1-db-1
```

### Accepted sequence

1. The candidate was confirmed pristine and pending.
2. The controlled HTTPS provider was configured for Candidate 05.
3. The worker claimed the candidate.
4. The provider received and held the first request.
5. The worker container was restarted immediately.
6. The restarted worker returned with a changed execution identity.
7. The expired lease was reclaimed after approximately one lease interval.
8. A second request was issued with the same idempotency key.
9. The provider classified the second request as a duplicate.
10. The outbox row reached delivered state.
11. The row was not dead-lettered.
12. The worker was stopped after evidence collection.

### Final corrected proof

```text
RecoveredPassed: True

AllCandidateEventCount: 6
ActualRequestRecordCount: 2
LifecycleEventCount: 4

AcceptedRequestCount: 2
DuplicateRequestCount: 1

RequestRecipientConsistent: True
RequestKeyConsistent: True
RequestTokenValid: True

RestartSucceeded: True
ContainerIdentityChanged: True
LeaseReclaimTimingValid: True

SecondsFirstHoldToSecondCall: 29.6860125

FinalDelivered: True
FinalWorkerStopped: True
FinalAttemptCount: 2
FinalDeliveredAt: 2026-07-27T08:44:50.489239+00:00
FinalDeadLetteredAt:
FinalLastErrorCode:
```

### Authoritative evidence

```text
candidate-05-posthoc-proof-20260727-094811.json
```

SHA-256:

```text
DCA82F42A84537F0241E379E667683DA543817BF228D06B952290732AF2E472F
```

### Original-manifest classification

The original C6-I run manifest reported a false negative because lifecycle events were evaluated as if they were HTTP request records.

Correct classification:

```text
2 actual request records
4 provider lifecycle events
```

Recipient consistency, token validity, and idempotency-key consistency passed for the actual requests.

C6-I is therefore accepted as passed.

---

## 6. Deterministic MFA Tamper Verification

The prior MFA tamper test changed the ciphertext suffix using:

```python
encrypted.ciphertext[:-1] + b"x"
```

That operation did not guarantee a changed ciphertext when the final byte was already `b"x"`.

The test was corrected to flip one bit deterministically:

```python
tampered_ciphertext = bytearray(encrypted.ciphertext)
tampered_ciphertext[len(tampered_ciphertext) // 2] ^= 0x01
```

Verification results:

```text
Focused pytest runs:          10 passed out of 10
Direct modified-cipher probe: 20 rejected out of 20
Authentication failure type:  ValueError
Authentication message:       MFA ciphertext authentication failed.
```

No production cryptography change was required.

---

## 7. Final Test Qualification

Full local test-suite result:

```text
2908 passed
12 skipped
0 failed
29 warnings
Duration: 89.58 seconds
```

The warnings were non-failing development, deprecation, weak-test-key, and resource warnings. They did not produce qualification failures.

Critical result:

```text
0 failed
```

---

## 8. CI Qualification

### Pull Request 26

Title:

```text
docs(auth): record successful C6-I container restart recovery
```

Status:

```text
MERGED
```

Merge commit:

```text
05267ba927f3072ecf9e568d573d652f2459767b
```

Public CI:

```text
CI (Public) / lint-and-test (3.14): PASSED
```

PR #26 included:

- C6-I verification documentation;
- graceful worker process shutdown integration coverage;
- strong child-process test settings correction.

### Pull Request 27

Title:

```text
test(auth): make MFA tamper assertion deterministic
```

Status:

```text
MERGED
```

Merge commit:

```text
9b1b0a7ffe9ff1126219a9ec2de3d4adb38c2bee
```

Public CI:

```text
CI (Public) / lint-and-test (3.14): PASSED
```

PR #27 removed the probabilistic MFA test behavior without changing production encryption logic.

---

## 9. Repository State at Closure

The primary worktree was updated to:

```text
main
origin/main
```

Final verified state:

```text
Your branch is up to date with 'origin/main'.
nothing to commit, working tree clean
```

Main included both accepted merge commits:

```text
05267ba927f3072ecf9e568d573d652f2459767b
9b1b0a7ffe9ff1126219a9ec2de3d4adb38c2bee
```

---

## 10. Tooling Defects Identified During Qualification

The AUTH-R10 qualification work identified the following orchestration and test-harness defects:

1. invalid outbox schema assumptions;
2. PowerShell 5.1 empty-array binding failures;
3. PowerShell 5.1 empty-string evidence binding failures;
4. multiline `python -c` probe corruption;
5. provider timeout values outside the supported `1..60` range;
6. false-negative worker-running detection;
7. missing automatic worker shutdown after controller failure;
8. stale provider recipient and idempotency contracts;
9. long-lived child-process waiting through `Start-Process -Wait`;
10. optional PID files treated as authoritative;
11. provider request records conflated with lifecycle records;
12. seed result artifacts missing despite successful database mutation;
13. child-process security warnings incorrectly treated as process failure;
14. nondeterministic ciphertext tamper construction in an MFA test.

These defects were either corrected or documented sufficiently to prevent them from invalidating the final readiness decision.

---

## 11. Residual Non-Blocking Work

The following work may continue independently after AUTH-R10 closure:

- consolidate the C6 harness into reusable maintained tooling;
- add automatic `finally` cleanup for all worker-starting test controllers;
- replace PID checks with health and socket readiness checks everywhere;
- separate provider lifecycle and request schemas explicitly;
- improve seed-result artifact reliability;
- reduce expected development warnings in the full test suite;
- review deprecated Starlette status constants;
- review test-only JWT key lengths;
- review resource warnings from SQLite-backed tests;
- archive or securely remove temporary runtime evidence after retention needs are satisfied;
- prune obsolete local feature worktrees and branches.

These items do not block the AUTH-R10 readiness decision.

---

## 12. Final Acceptance

AUTH-R10 has demonstrated:

- secure authentication delivery lifecycle behavior;
- protected operational controls;
- safe concurrent worker behavior;
- graceful process shutdown;
- stale-claim reconciliation;
- Docker restart recovery;
- idempotent duplicate handling;
- successful final delivery after restart;
- deterministic cryptographic tamper verification;
- full local suite success;
- successful public CI.

Final decision:

```text
AUTH-R10 production runtime readiness: PASSED
```

AUTH-R10 is closed and ready for the next planned authentication roadmap stage.
