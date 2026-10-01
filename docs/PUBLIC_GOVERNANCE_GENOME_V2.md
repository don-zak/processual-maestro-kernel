# Public Governance Genome v2 Candidate

This document describes the public-safe governance layer used by Maestro. It is an engineering runtime contract, not a claim that a universal cognitive genome has been scientifically established.

## Decision precedence

The public gateway applies governance in this order:

1. constitutive constraints
2. authorization boundary
3. required evidence
4. dynamic qualification
5. Fate/rank optimization
6. lifecycle recommendation

Hard gates are fail-closed and cannot be overridden by reward, rank, or Fate Vector scores.

## Evidence ceiling

The runtime claim ceiling is currently E4 (cross-fit qualified). E5 and higher are defined in the evidence ladder but are not claimed by this public configuration until the corresponding external qualification is complete.

## Public operation policies

The server owns the minimum requirements for registered operations. Caller-provided governance context may only make those requirements stricter.

Execution-sensitive operations require an explicit runtime execution attestation. Readiness, eligibility, or a good Fate score alone is not sufficient proof that an operation executed.

## Public/private boundary

The public repository contains only generic governance contracts:

- governance configuration and precedence
- operation policies
- factual/execution/task-sufficiency evidence types
- trusted-evidence binding
- runtime execution attestation
- dynamic qualification
- gateway policy enforcement and audit provenance

Private integration artifacts, private CGT packages, private qualification datasets, and private execution adapters are not included.

## Runtime observability

GET /cgt/govern/status exposes the public governance genome version, fail-closed mode, current evidence ceiling, precedence, and registered operation IDs.

Gateway evaluation responses expose the authoritative gateway action separately from runtime telemetry. Runtime policy telemetry reflects the Gateway decision and does not re-decide it from rank/reward.

## Qualification

The branch is qualified by:

- .github/workflows/public-governance-genome.yml
- the existing public CI/security/integrity workflows
- scripts/qualify-public-governance-genome.ps1 as a local fallback

The candidate remains fail-closed until those checks pass.
