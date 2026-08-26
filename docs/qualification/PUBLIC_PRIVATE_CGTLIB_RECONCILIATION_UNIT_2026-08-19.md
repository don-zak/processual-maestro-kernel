# Public / Private cgtlib Reconciliation Unit — 2026-08-19

**Public main:** `a63b4a7d40643a685caeaafc8cbfd11f59e9d544`  
**Private main:** `84e3354cd43802176ee93ed94f72144341c0068b`  
**Status:** **CLASSIFIED — PORT MANIFEST READY, PRIVATE MAIN UNCHANGED**

## Result

The cgtlib surface contains both shared formal-core code and a genuine private engine boundary. Reconciliation must update the shared formal-core contract without overwriting or publishing `cgtlib/private/`.

## Shared-core paths that should converge from public

### `cgtlib/api.py`

Private currently embeds the full `CGTLIB_STABLE_API` tuple directly in `api.py`. Public has moved that dependency-light contract to `cgtlib/_stable_api.py`, imports it into `api.py`, and exports `ReferenceScenarioRecord` alongside the existing public surface.

Disposition: **COPY-CANDIDATE as part of a coordinated API/fallback port**.

### `cgtlib/_stable_api.py`

Public contains the dependency-light stable API declaration. Private main does not contain this file.

Disposition: **ADD TO PRIVATE** during the cgtlib port.

### `cgtlib/_fallback.py`

Public fallback imports `CGTLIB_STABLE_API` from `._stable_api`. Private fallback still imports it from `.api`, creating unnecessary import coupling.

Disposition: **COPY-CANDIDATE together with `_stable_api.py` and `api.py`**.

### `cgtlib/__init__.py`

Public and private share the same overall formal-core/fallback architecture, including the `_MISSING_PRIVATE_MSG`, formal-core imports and fallback behavior. Public has newer shared public API/reference-data wiring.

Disposition: **MERGE/COPY REVIEW**, preserving the private engine detection/composition behavior while converging the shared public exports.

## Genuine PRIVATE-PRESERVE boundary

The private repository contains:

`cgtlib/private/`

with private engine modules such as:

- `calibration.py`
- `compute.py`
- `constants.py`
- `equations.py`
- `thresholds.py`
- `version.py`

This subtree is genuinely private and must:

1. remain in the private repository;
2. remain absent from the public repository/build;
3. never become a dependency required for importing the public formal-core package;
4. continue to compose correctly from the private build after shared-core reconciliation.

## Correction: `cgtlib/data/` is not private-only

Earlier top-level inventory suggested `cgtlib/data/` might be private-only because it existed in private and was absent from public main. Deeper semantic inspection disproved that classification.

Both repositories contain identical `cgtlib/reference_data.py`, which explicitly loads:

- package: `cgtlib.data`
- resource: `reference_scenarios.json`

Private contains the required package/resource; public main did not.

The retained JSON contains only three canonical formal-core datasets:

- `balanced_transition_band`
- `stress_recovery_band`
- `boundary_lock_band`

No secret, customer, provider or operational data is present.

Therefore `cgtlib/data/` is a **shared canonical package resource** and its absence from public main is a public packaging defect, not evidence of private ownership.

## Public qualification-branch repair

The public qualification branch now restores the shared resource package with:

- `cgtlib/data/__init__.py`
- `cgtlib/data/reference_scenarios.json`
- `tests/test_cgtlib_reference_data_packaging.py`

The regression coverage verifies:

- the exact canonical dataset IDs;
- successful loading through `importlib.resources`;
- non-empty transition data;
- stable canonical scenario identity.

This repair is not yet considered CI-qualified on the newest HEAD because no workflow run was associated with the exact latest commit at the last check.

## Safe cgtlib private-port manifest

When a controlled private reconciliation branch can be published, apply this unit atomically:

1. add public `_stable_api.py` to private;
2. converge private `api.py` to the public stable-API/reference-data contract;
3. converge private `_fallback.py` to import from `_stable_api.py`;
4. reconcile `__init__.py` shared exports while preserving private engine detection/composition;
5. retain `cgtlib/private/` unchanged unless a separate private-only review requires a change;
6. retain/verify `cgtlib/data/` as shared canonical package data;
7. run public-surface tests both with and without private engine availability;
8. run private CGT integration tests;
9. verify the public package/build contains no `cgtlib/private` material.

## Current authority

- public qualification branch contains the package-data repair and regression test;
- private `main` remains unchanged;
- no private engine code was copied to public;
- no cross-repository merge/port was performed;
- no staging or production authority is implied.