# AUTH-R10C-C6-I — Docker Container Restart Crash-Recovery Report

**Status:** PASSED  
**Final accepted candidate:** Candidate 05  
**Test date:** 2026-07-27  
**Scope:** Authentication delivery worker recovery after an immediate Docker container restart during an in-flight provider request.

---

## 1. Executive Summary

The AUTH-R10C-C6-I crash-recovery scenario has been completed successfully.

The test demonstrated that:

- the delivery worker claimed a pending authentication-delivery outbox row;
- the controlled HTTPS provider received and held the first request;
- the worker container was restarted immediately with zero shutdown timeout;
- the worker returned in a new container execution;
- the expired claim was reclaimed after approximately one lease interval;
- a second request was sent with the same idempotency key;
- the provider detected the request as a duplicate;
- the outbox row was ultimately delivered;
- the row was not dead-lettered;
- the worker was stopped after final evidence collection.

The original run manifest reported `Passed: False` because its recipient-consistency assertion incorrectly treated provider lifecycle records as HTTP request records. A read-only post-hoc verifier separated actual request records from lifecycle events and produced the authoritative result:

```text
RecoveredPassed: True
```

No additional candidate or rerun is required for C6-I.

---

## 2. Environment

### Repository

```text
C:\Users\zaksam\AppData\Local\Temp\pmk_auth_r10_production_runtime_r1
```

### Runtime

```text
C:\Users\zaksam\AppData\Local\Temp\pmk_auth_r10c_runtime_r1
```

### C6-I runtime directory

```text
C:\Users\zaksam\AppData\Local\Temp\pmk_auth_r10c_runtime_r1\
crash-recovery-c6\c6i-docker-container-restart
```

### Python interpreter

```text
C:\Users\zaksam\Desktop\.venvs\pmk314\Scripts\python.exe
```

### Containers

```text
Worker:   processual-auth-delivery-worker
Database: pmk-auth-r10c-runtime-r1-db-1
```

### Database

```text
User:     processual_r10c
Database: processual_auth_r10c
```

### Final worker configuration

```text
AUTH_DELIVERY_LEASE_SECONDS=30
AUTH_DELIVERY_REQUEST_TIMEOUT_SECONDS=60
AUTH_PUBLIC_BASE_URL=https://auth-r10c-c6i.example.test
AUTH_DELIVERY_PROVIDER_URL=https://host.docker.internal:65534/auth-r10c-provider
SSL_CERT_FILE=/run/c6i/host-docker-internal-cert.pem
```

The initially proposed request timeout of `120` seconds was rejected by the runtime provider constructor. Inspection of `HttpEmailDeliveryProvider` established the valid range:

```text
1 <= timeout_seconds <= 60
```

The final timeout was therefore set to `60` seconds, with a lease of `30` seconds.

---

## 3. Controlled Provider

### Provider implementation

```text
controlled_http_provider_c6i.py
```

### Provider environment

```text
controlled-http-provider-c6i.env
```

### HTTPS endpoint

```text
https://host.docker.internal:65534/auth-r10c-provider
```

### Health endpoint

```text
https://127.0.0.1:65534/health
```

### TLS certificate

```text
host-docker-internal-cert.pem
```

The worker image successfully validated the controlled provider over HTTPS using:

```text
SSL_CERT_FILE=/run/c6i/host-docker-internal-cert.pem
```

The provider verifies:

- bearer token;
- expected recipient;
- expected idempotency key;
- duplicate use of an accepted idempotency key.

The provider also writes request and lifecycle evidence to:

```text
controlled-http-provider-c6i-calls.jsonl
controlled-http-provider-c6i-hold.json
controlled-http-provider-c6i-release.flag
controlled-http-provider-c6i-ready.json
```

---

## 4. Candidate History

### Candidate 01

```text
Outbox ID:
86f87087-f8d9-4dd7-8b92-6696f7bd42f7
```

Candidate 01 was invalidated and ultimately dead-lettered. It was not accepted as C6-I evidence.

### Candidate 02

```text
Outbox ID:
be24c8ef-114d-44f0-9359-9077f2d3296c

Email:
auth-r10c-c6i-container-restart-02@example.test
```

Candidate 02 was not seeded correctly because its generated seed still contained deterministic Candidate 01 identities and an outdated baseline.

No valid Candidate 02 test execution occurred.

### Candidate 03

```text
Outbox ID:
83c3eb72-ed2e-499d-9ec4-c882bf7c8e86

User ID:
24df7545-1c3f-523c-99d3-fb59e59e0b02

Action token ID:
f6cc853f-7ed8-59aa-9f68-93548fd34a68

Email:
auth-r10c-c6i-container-restart-03@example.test

Idempotency key:
pmk-auth-delivery-v1:83c3eb72-ed2e-499d-9ec4-c882bf7c8e86
```

Candidate 03 was seeded successfully and initially recovered as pristine pending.

During execution, multiple tool defects caused the worker to continue after an orchestration script had aborted:

- an invalid `updated_at` column was queried;
- an empty string was rejected by a PowerShell parameter;
- worker-running detection produced a false negative;
- a request timeout of `120` seconds caused a restart loop;
- the worker continued processing after the test controller stopped.

Candidate 03 accumulated retries and provider timeouts, then became dead-lettered:

```text
Final attempt count: 3
Final provider event count: 9
Final error: provider_timeout
Crash-restart proof valid: False
```

Candidate 03 is retained only as failed-run evidence.

### Candidate 04

```text
Outbox ID:
4d44c1d7-707e-4dd0-8407-6c1df4aa48e7

Email:
auth-r10c-c6i-container-restart-04@example.test

Idempotency key:
pmk-auth-delivery-v1:4d44c1d7-707e-4dd0-8407-6c1df4aa48e7
```

Candidate 04 was seeded as pristine pending.

The controlled provider, however, was still configured with Candidate 03's recipient and idempotency key. It rejected Candidate 04 before creating a hold:

```text
token_valid: True
recipient_valid: False
idempotency_key_valid: False
accepted: False
```

The worker classified the response as:

```text
provider_4xx
```

Candidate 04 became dead-lettered after one attempt and was not valid evidence.

### Candidate 05 — Accepted

```text
Outbox ID:
eec494e5-9fbf-4b8a-86d3-1520fd6ac51d

User ID:
1842c926-45c1-5b2d-84d0-d251041f7e29

Action token ID:
c15fac2a-a907-5c27-97c6-66b16b1028a7

Email:
auth-r10c-c6i-container-restart-05@example.test

Idempotency key:
pmk-auth-delivery-v1:eec494e5-9fbf-4b8a-86d3-1520fd6ac51d
```

Before execution, Candidate 05 was independently verified as pristine:

```text
RecoveredProofPassed: True
CandidatePending: True
CandidateAttemptCount: 0
CandidateClaimId:
CandidateDeliveredAt:
CandidateDeadLetteredAt:
CandidateLastErrorCode:
```

The database baseline was:

```text
Total:         37
Pending:        1
Delivered:     31
Dead-lettered:  5
```

The controlled provider was updated to expect Candidate 05 before the test was run.

---

## 5. Final Test Sequence

The accepted C6-I run used Candidate 05.

### Run directory

```text
C:\Users\zaksam\AppData\Local\Temp\pmk_auth_r10c_runtime_r1\
crash-recovery-c6\c6i-docker-container-restart\
candidate-05-run-20260727-094411
```

### Sequence

1. Confirmed repository cleanliness.
2. Confirmed Candidate 05 was pristine pending.
3. Confirmed no prior Candidate 05 provider calls.
4. Confirmed hold and release controls were absent.
5. Confirmed the provider health endpoint was available.
6. Started the delivery worker with the final Compose configuration.
7. Waited until the provider received and held the first request.
8. Restarted the worker container using:

   ```text
   docker restart --timeout 0 processual-auth-delivery-worker
   ```

9. Confirmed the worker returned with a changed container start identity.
10. Waited for the lease to expire and the outbox claim to be reclaimed.
11. Observed a second provider request using the same idempotency key.
12. Created the release control.
13. Waited for final outbox delivery.
14. Captured worker logs, provider records, container states and database state.
15. Stopped the worker.

---

## 6. Final Results

### Original run output

```text
InitialPending: True
FirstHoldReached: True
FirstCallCount: 2
RestartExitCode: 0
WorkerRestarted: True
RestartCountIncreased: True
DuplicateReached: True
FinalCallCount: 6
ProviderKeyConsistent: True
ProviderRecipientConsistent: False
FinalDelivered: True
FinalWorkerRunning: False
FinalAttemptCount: 2
FinalDeliveredAt: 2026-07-27T08:44:50.489239+00:00
FinalDeadLetteredAt:
FinalLastErrorCode:
SecondsFirstHoldToSecondCall: 29.6860125
```

The aggregate `FirstCallCount` and `FinalCallCount` included provider lifecycle records in addition to actual request records.

### Corrected post-hoc classification

```text
OriginalManifestPassed: False
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

---

## 7. Authoritative Evidence

### Post-hoc proof

```text
C:\Users\zaksam\AppData\Local\Temp\pmk_auth_r10c_runtime_r1\
crash-recovery-c6\c6i-docker-container-restart\
candidate-05-run-20260727-094411\
candidate-05-posthoc-proof-20260727-094811.json
```

### SHA-256

```text
DCA82F42A84537F0241E379E667683DA543817BF228D06B952290732AF2E472F
```

### Original run manifest

```text
C:\Users\zaksam\AppData\Local\Temp\pmk_auth_r10c_runtime_r1\
crash-recovery-c6\c6i-docker-container-restart\
candidate-05-run-20260727-094411\
auth-r10c-c6i-candidate-05-container-restart-run.json
```

### Original run manifest SHA-256

```text
FC69521330D8DAE0872F22463C28D7DDEA20C6E2271D2289F30E8D6BBC9BAA33
```

The original manifest must be retained as raw evidence, but its overall failure classification is superseded by the post-hoc verifier.

### Classification of original failure

```text
False negative in test tooling.
```

Reason:

The original verifier required every provider record containing the idempotency key to also contain a recipient. Four of the six matching records were provider lifecycle events, not HTTP request records, and were not required to carry the request recipient.

---

## 8. Acceptance Decision

### Final status

```text
AUTH-R10C-C6-I: PASSED
```

### Acceptance basis

C6-I is accepted because:

- an in-flight request was observed before the crash;
- an immediate worker container restart was executed successfully;
- worker execution identity changed;
- the lease was reclaimed after approximately 30 seconds;
- two actual requests used the same idempotency key;
- the second accepted request was identified as a duplicate;
- request recipient, token and idempotency key were valid;
- the outbox row was delivered after two attempts;
- the row was not dead-lettered;
- no final error remained;
- the worker was stopped after evidence collection.

No Candidate 06 and no C6-I rerun are required.

---

## 9. Tooling Defects Discovered

The following defects were found in the orchestration and evidence tooling:

1. **Invalid schema assumption**

   The first run queried a nonexistent `updated_at` column in `auth_delivery_outbox`.

2. **PowerShell empty-array binding**

   PowerShell 5.1 rejected an empty array passed to an obligatory `ExtraArguments` parameter.

3. **PowerShell empty-string binding**

   An evidence writer rejected an empty string when creating an initially empty provider-call snapshot.

4. **Multiline `python -c` corruption**

   A container health probe passed multiline code via `python -c`, resulting in a syntax error at `import`.

5. **Provider timeout contract mismatch**

   The orchestration expected `120` seconds, while `HttpEmailDeliveryProvider` accepts at most `60`.

6. **Worker-state false negative**

   The initial container-state probe reported that the worker did not become running even though it continued processing.

7. **Unsafe abort behavior**

   Some failed controller runs did not stop the worker, allowing candidates to continue retrying.

8. **Stale provider identity contract**

   Candidate 04 was tested while the controlled provider still expected Candidate 03.

9. **Long-lived provider launcher wait**

   `Start-Process -Wait` blocked because it waited on a launcher associated with a long-running child process.

10. **PID-file dependency**

    Several scripts treated an optional/stale PID file as authoritative instead of checking the health endpoint directly.

11. **Request/lifecycle record conflation**

    The original final verifier counted provider lifecycle events as request records, causing a false-negative recipient assertion.

---

## 10. Required Permanent Fixes

Before reusing this harness for another scenario:

- query actual database columns only;
- make optional PowerShell arrays and empty evidence strings explicitly valid;
- use mounted probe files instead of multiline `python -c`;
- enforce the provider timeout range `1..60`;
- detect worker state through full `docker inspect`;
- stop the worker automatically on every post-start controller failure;
- update the provider identity contract before seeding each candidate;
- verify provider readiness by direct HTTPS health check;
- do not depend on PID files as the source of truth;
- classify provider request records separately from lifecycle records;
- count only actual HTTP request records for recipient/token/request assertions;
- archive control files and evidence before candidate transitions;
- make seed proof generation reliable, or explicitly support read-only proof recovery.

---

## 11. Repository and Runtime Policy

The test did not require source changes to the production repository.

The repository should remain clean unless the test-harness corrections are intentionally committed as a separate maintenance change.

Runtime artifacts under the temporary C6-I directory contain operational evidence and should not be committed wholesale because they may contain:

- absolute workstation paths;
- runtime configuration;
- tokens or secrets;
- generated certificates or private keys;
- database-derived identifiers;
- large logs.

Only this sanitized report and explicitly reviewed non-secret evidence should be added to Git.

Do **not** commit:

```text
controlled-http-provider-c6i.env
host-docker-internal-key.pem
runtime .env files
raw secret-bearing manifests
database credentials
provider bearer tokens
```

---

## 12. Recommended Repository Location

Recommended path:

```text
docs/verification/AUTH-R10C-C6-I-docker-container-restart.md
```

Suggested commit message:

```text
docs(auth): record successful C6-I container restart recovery
```

---

## 13. Next Work

C6-I is closed.

The next workflow should:

1. store this sanitized report in the repository;
2. optionally store reviewed, non-secret proof JSON under a verification evidence directory;
3. update the parent AUTH-R10C/C6 transition or verification index;
4. fix the discovered harness defects separately;
5. continue with the next planned AUTH-R10C crash-recovery or production-readiness gate.

Do not create another C6-I candidate unless the acceptance decision is intentionally revoked.
