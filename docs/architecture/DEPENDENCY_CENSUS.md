# Dependency Census and Boundary Lock

This document establishes the first non-invasive architecture baseline for the Maestro public repository.

## Safety rule

Wave 1 does not move, rename, split, or delete runtime source files. It only measures the current dependency graph and locks two already-intended inward boundaries:

- `processual_kernel` must not import `processual_api`.
- `cgtlib` must not import `processual_api`.

Broader dependency rules must not be added until the census demonstrates that they match the repository's actual structure and tests confirm they are safe.

## Census tool

Run from the repository root:

```bash
python tools/dependency_census.py --format json --output dependency-census.json
python tools/dependency_census.py --format markdown --output dependency-census.md
```

The tool is stdlib-only and read-only. It parses Python source with `ast` and records:

- Python file count and byte size per current package root;
- total Python source bytes for the scanned package roots;
- top-level import roots used by the source;
- cross-package internal dependency edges;
- per-file imports and internal edges.

The current scanned package roots are:

- `processual_kernel`
- `cgtlib`
- `processual_api`

The generated output is intentionally deterministic so later architecture waves can compare snapshots rather than relying on manual estimates.

## Boundary tests

`tests/test_architecture_boundaries.py` parses source without importing it and fails CI if either `processual_kernel` or `cgtlib` starts depending on `processual_api`.

These are initial guardrails, not the final architecture. Future rules should be introduced one at a time only after the dependency census, regression tests, and runtime readiness gates support them.

## Next gate

Before any source relocation or package split:

1. run the census and inspect all internal edges;
2. classify files into contracts, core, governance, runtime, and outward adapters;
3. identify cycles and reverse dependencies;
4. add only evidence-backed architecture tests;
5. keep Public CI, Security Scan, Security Hardening, and branch-protection checks green.

Only after those gates are satisfied should a later wave consider compatibility shims or physical file movement.
