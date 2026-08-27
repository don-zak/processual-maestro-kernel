# MAESTRO Splash Archive & Quarantine Closeout — 2026-08-27

## Scope

This record documents the preservation and quarantine of the MAESTRO Splash development work without modifying `main` and without merging historical PR #165.

## Preserved source

- Repository: `don-zak/processual-maestro-kernel`
- Preserved source SHA: `3775d5e4d8ab114f5503de57bab53ecc26e1b32e`
- Archive branch: `archive/maestro-splash-development-2026-08-27`
- Cleanup commit: `4ccbab7ca416eba898e1a0b15904422d6ccf1089`
- Archive directory: `docs/archives/maestro-splash/`
- Archive ZIP: `maestro-splash-development-archive-2026-08-27.zip`
- ZIP SHA-256: `ee1d6ce945cfe7c13f7b0893df390ef85dc255d66c51d4717525321bd45a8c16`

## Inventory gate

The archive gate classified exactly 60 Splash-related tracked files from the preserved source state:

- 58 `ARCHIVE_DELETE`
- 1 `ARCHIVE_RESTORE_MAIN`: `processual_api/static/splash.html`
- 1 `HOLD`: `docs/reports/SPLASH_REFERENCE_ROUTE_EXTRACTION_AUDIT_20260826.md`

The ZIP was rebuilt from the preserved source SHA, validated with its internal SHA-256 manifest, checked with `unzip -t`, and force-tracked in the repository because ZIP files are otherwise ignored.

## Safety invariants

- `main` remains untouched by this cleanup.
- `processual_api/main.py` has the same Git blob before and after quarantine: `2c00dc29d2d5e69cbdfcd9d23f17ec3488991fea`.
- `processual_api/static/splash.html` is restored to the current `main` version.
- Splash-only scripts, tests, fixtures, SVG routing assets, and `.github/workflows/splash-visual-contract.yml` are removed from the active working branch.
- The HOLD audit report remains present and unchanged by quarantine.
- Historical PR #165 is not a cleanup/merge mechanism and must remain unmerged.

## Release gate

This closeout document intentionally lives under `docs/qualification/` so the repository's existing `Program Release Qualification` workflow validates the final branch state after archive persistence. Closeout is complete only when the resulting workflow run is observed and its result recorded.