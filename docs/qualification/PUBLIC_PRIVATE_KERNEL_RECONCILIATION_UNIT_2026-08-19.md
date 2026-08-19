# Public / Private Kernel Reconciliation Unit — 2026-08-19

**Public main:** `a63b4a7d40643a685caeaafc8cbfd11f59e9d544`  
**Private main:** `84e3354cd43802176ee93ed94f72144341c0068b`  
**Status:** **READY TO PORT — PRIVATE MAIN UNCHANGED**

## Result

The inspected `processual_kernel` drift is shared-core modernization, not private-product customization.

A large majority of top-level kernel files and subtrees are byte-identical across public and private. The divergent files inspected in detail preserve the same classes, values, fields and runtime behavior while the public repository mainly modernizes string enums from the legacy pattern:

```python
from enum import Enum
class X(str, Enum): ...
```

to Python's native:

```python
from enum import StrEnum
class X(StrEnum): ...
```

The remaining adaptive governance drift also proved non-private: public removed a stale `# noqa: C901` suppression from `decide_mode_transition` without changing the decision logic in the reviewed region.

## Confirmed COPY-CANDIDATE files

Detailed public/private semantic inspection confirms the following as shared-core COPY-CANDIDATE paths:

- `processual_kernel/audit.py`
- `processual_kernel/types.py`
- `processual_kernel/adaptive_types.py`
- `processual_kernel/notifications/types.py`
- `processual_kernel/security/envelopes.py`
- `processual_kernel/security/crypto.py`
- `processual_kernel/security/keyring.py`
- `processual_kernel/security/policies.py`
- `processual_kernel/adaptive/ops_governance.py`

For these files, no private-only behavior was identified in the reviewed content.

## Adaptive subtree status

Recursive tree comparison shows the adaptive subtree is overwhelmingly identical.

Known differing entries include:

- `processual_kernel/adaptive/efficiency.py`
- `processual_kernel/adaptive/ops_governance.py`

The reviewed beginning and core logic of `efficiency.py` are identical; the blob-size delta is very small and no private integration dependency is present in the inspected code. `ops_governance.py` differs by cleanup of a lint suppression while preserving the same safety logic.

Disposition: both remain shared-core COPY-CANDIDATE paths, subject to focused private tests after port.

## Identical kernel surfaces already verified

Examples include:

- `processual_kernel/__init__.py`
- `adaptive_toolkit.py`
- `cgt_bridge.py`
- `continuity.py`
- `governor.py`
- `kernel.py`
- `processual_kernel/observability/`
- all inspected notification modules except `notifications/types.py`
- `processual_kernel/security/__init__.py`
- `processual_kernel/security/exceptions.py`
- `processual_kernel/security/hashes.py`
- most inspected files in `processual_kernel/adaptive/`

## Port decision

**The `processual_kernel` reconciliation unit is ready to port from public main into a dedicated private reconciliation branch.**

The port must not target private `main` directly.

Required validation after port:

1. focused kernel/adaptive/security tests in private;
2. private full regression;
3. public-exclusion/private-integration tests;
4. no private-only import introduced into shared kernel modules;
5. no public behavior regression;
6. private build still composes private-only integrations successfully.

## Publication constraint in the current execution environment

The GitHub publish workflow requires an authenticated local `gh`/git checkout for safe branch creation, commit, push and draft-PR publication. The current execution environment does not provide `gh`, so no cross-repository branch/port is being fabricated through direct writes to private `main`.

This is a tooling/publication constraint, not a semantic blocker. The port unit and exact source/target SHAs are now defined for a later controlled private-branch application.

## Current authority

- private `main` unchanged;
- no cross-repository code port applied yet;
- no merge performed;
- no staging authority granted;
- no production authority granted.