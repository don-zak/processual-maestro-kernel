# Private repository guarded synchronization from Windows PowerShell

## Purpose

This runbook describes a local, fail-closed way to prepare a private-repository synchronization from the exact qualified public External Evaluation baseline.

It does **not** authorize a merge, force-push, direct `main` write, or synchronization of post-qualification public work.

## Fixed synchronization target

The only qualified public target for private PR #56 is:

`6f7dd018737151cd1906be068f2478d02d19392b`

Do not substitute the current public feature-branch head. Workspace, ZAXAM hosting, CRM Summary/Draft, Integration Billing, Admin UX, and later deployment-workflow commits are post-baseline work and are not part of this private synchronization step.

## Preconditions

- Git for Windows is installed and available as `git` in PowerShell.
- The public and private repositories are cloned into separate local directories.
- The private checkout is on the PR #56 branch, not `main`.
- The private working tree is clean.
- The exact previous synchronized public baseline is known before replacing shared files.
- No secret values are stored in the public checkout or copied from private-only surfaces.

## Protected private surfaces

At minimum, the following paths must never be overwritten by the public sync:

- `cgtlib/private/**`
- `processual_api/private_integrations/**`
- `processual_api/integrations/cgt_adapter.py`
- `processual_api/routers/cgt.py`
- `tests/test_cgt_private_bridge_security.py`
- `tests/private_cgt17a/**`
- private deployment/security/ops assets

## PowerShell safety setup

```powershell
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$PublicRepo  = 'C:\path\to\processual-maestro-kernel'
$PrivateRepo = 'C:\path\to\processual-maestro-kernel-private'
$QualifiedPublicSha = '6f7dd018737151cd1906be068f2478d02d19392b'

# Must be filled with the exact public baseline that the current private
# shared layer was synchronized from. Do not guess this value.
$PreviousPublicBaselineSha = '<REQUIRED-EXACT-PREVIOUS-PUBLIC-BASELINE>'
```

Abort if `$PreviousPublicBaselineSha` is still the placeholder.

## Verify repository state

```powershell
if ($PreviousPublicBaselineSha -like '<*') {
    throw 'PreviousPublicBaselineSha must be resolved before synchronization.'
}

Push-Location $PublicRepo
try {
    git fetch origin --prune
    git cat-file -e "$QualifiedPublicSha^{commit}"
    git cat-file -e "$PreviousPublicBaselineSha^{commit}"
} finally {
    Pop-Location
}

Push-Location $PrivateRepo
try {
    if ((git status --porcelain).Length -ne 0) {
        throw 'Private working tree is not clean.'
    }

    $branch = (git branch --show-current).Trim()
    if ($branch -eq 'main') {
        throw 'Refusing to synchronize directly on private main.'
    }
} finally {
    Pop-Location
}
```

## Use an explicit allowlist

Create a local text file containing only shared paths approved for synchronization, one path per line. Do not derive the allowlist from `git diff` automatically.

Example location:

```powershell
$Allowlist = Join-Path $env:TEMP 'maestro-qualified-sync-allowlist.txt'
```

Before using it, reject protected paths:

```powershell
$ProtectedPatterns = @(
    '^cgtlib/private/',
    '^processual_api/private_integrations/',
    '^processual_api/integrations/cgt_adapter\.py$',
    '^processual_api/routers/cgt\.py$',
    '^tests/test_cgt_private_bridge_security\.py$',
    '^tests/private_cgt17a/',
    '^ops/',
    '^deployment/private',
    '^docs/private'
)

$Paths = Get-Content $Allowlist | ForEach-Object { $_.Trim() } | Where-Object { $_ }
foreach ($Path in $Paths) {
    foreach ($Pattern in $ProtectedPatterns) {
        if ($Path -match $Pattern) {
            throw "Protected private path entered allowlist: $Path"
        }
    }
}
```

## Conflict check before replacement

For every allowlisted path that existed in the previous public baseline, compare the current private copy against that previous public baseline. If they differ, stop; that path has private-side divergence and must be reviewed manually.

A path introduced after the previous baseline must also fail closed if the private branch already contains a different file at that path.

Do not copy any file until all allowlisted paths pass this conflict check.

## Stage, do not push

After the conflict check passes, copy only the allowlisted files from `$QualifiedPublicSha` into the private working tree. Then verify:

```powershell
Push-Location $PrivateRepo
try {
    git diff --check
    git status --short

    # Review protected surfaces explicitly; expected output is empty.
    git diff --name-only -- `
      cgtlib/private `
      processual_api/private_integrations `
      processual_api/integrations/cgt_adapter.py `
      processual_api/routers/cgt.py `
      tests/test_cgt_private_bridge_security.py `
      tests/private_cgt17a `
      ops
} finally {
    Pop-Location
}
```

Any output from the protected-surface diff is a hard stop.

Also compare the complete changed-file list with the explicit allowlist. Any unexpected changed path is a hard stop.

## Commit only after review

Only after the staged tree is reviewed:

```powershell
Push-Location $PrivateRepo
try {
    git add -A
    git diff --cached --check
    git diff --cached --name-only
    git commit -m 'sync(public): align shared layer to qualified 6f7dd018'
} finally {
    Pop-Location
}
```

Do not push automatically from a synchronization script. Inspect the exact commit SHA first.

## Qualification after push

The synchronization is not complete merely because the commit exists.

Before advancing private PR #56, the exact private staging SHA must receive executable private CI/security/qualification proof, including private-module presence, shared/private lint and typing checks, tests/coverage, security/dependency audit, package build, protected-private zero-diff review, and final changed-file review.

If GitHub Actions still produces jobs with `steps=null`, treat runner allocation as unresolved and keep PR #56 Draft/Open/Unmerged.

## What this runbook deliberately excludes

- current post-baseline public Workspace/CRM/Integration/Admin commits;
- direct synchronization to private `main`;
- force-push;
- copying private-only paths from public;
- automatic commit or push before manual review;
- treating Render deployment as private qualification;
- reuse of the revoked qualification Grant/key.
