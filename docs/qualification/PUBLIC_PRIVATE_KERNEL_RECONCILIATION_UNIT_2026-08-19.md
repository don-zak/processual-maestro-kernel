# Public / Private Kernel Reconciliation Unit — 2026-08-19

**Public main:** `a63b4a7d40643a685caeaafc8cbfd11f59e9d544`  
**Private main:** `84e3354cd43802176ee93ed94f72144341c0068b`  
**Status:** **SEMANTIC CLASSIFICATION COMPLETE FOR INSPECTED KERNEL DRIFT — PORT NOT YET APPLIED**

## Result

The inspected `processual_kernel` drift is overwhelmingly shared-core modernization, not private-product customization.

A large majority of top-level kernel files are byte-identical across public and private. The divergent files inspected in detail preserve the same classes, values, fields and runtime behavior while the public repository modernizes string enums from the legacy pattern:

```python
from enum import Enum
class X(str, Enum): ...
```

to Python's native:

```python
from enum import StrEnum
class X(StrEnum): ...
```

## Confirmed COPY-CANDIDATE files

Detailed public/private semantic inspection confirms the following as shared-core COPY-CANDIDATE paths:

- `processual_kernel/audit.py`
- `processual_kernel/types.py`
- `processual_kernel/adaptive_types.py`
- `processual_kernel/notifications/types.py`
- `processual_kernel/security/envelopes.py`
- `processual_kernel/security/crypto.py`
- `processual_kernel/security/keyring.py`

For these files, no private-only behavior was identified in the reviewed content. The divergence is enum modernization while preserving the same public contract values and surrounding logic.

## Identical kernel surfaces already verified

Examples include:

- `processual_kernel/__init__.py`
- `adaptive_toolkit.py`
- `cgt_bridge.py`
- `continuity.py`
- `governor.py`
- `kernel.py`
- `processual_kernel/observability/`
- most of `processual_kernel/notifications/`
- `processual_kernel/security/__init__.py`
- `processual_kernel/security/exceptions.py`
- `processual_kernel/security/hashes.py`

## Remaining kernel subtree review

Before applying the complete kernel port, inspect the remaining differing subtree paths:

- `processual_kernel/adaptive/efficiency.py` and any later divergent adaptive entries;
- `processual_kernel/security/policies.py`;
- any remaining security/adaptive file whose blob differs but was not yet semantically compared.

Expected hypothesis: these are likely part of the same `StrEnum` modernization wave, but this must be verified rather than assumed.

## Port rule

If the remaining divergent kernel files confirm the same shared-core-only pattern, the whole reviewed kernel drift can be ported from public to a dedicated private reconciliation branch as one focused unit.

Required validation after that port:

1. private focused kernel tests;
2. private full regression;
3. public-exclusion/private-integration tests;
4. no private-only import introduced into shared kernel modules;
5. no public behavior regression;
6. private build still composes private-only integrations successfully.

## Current authority

No cross-repository write has been applied by this record. Private `main` remains unchanged. No merge, staging or production authority is implied.