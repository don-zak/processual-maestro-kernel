# Maestro Startup Tunisia Static Showcase

This folder contains the presentation-oriented Maestro showcase used for video capture and guided review.

## Purpose

The showcase is intentionally separated from the technical Portable Evaluation Runtime.

It is designed to open instantly and deterministically without:

- Docker
- PostgreSQL or Redis
- localhost services
- generated secrets
- passwords or API keys
- external LLM providers
- billing connections
- network calls

## Run on Windows

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\START-SHOWCASE.ps1
```

Or open `MAESTRO_SHOWCASE.html` directly in a browser.

## Evidence boundary

The UI states in the showcase are synthetic/mock demonstration states unless explicitly marked as recorded evidence.

The recorded CGT/Gateway values are replayed from previously verified evidence and are not live provider execution.

The separate Portable Evaluation Runtime remains the technical qualification artifact. It has its own Docker-based runtime and qualification evidence.

Do not describe this static showcase as Production execution, a customer deployment, a live CGT run, or a fully operational backend.

## Recommended video path

1. Product Overview
2. Operations Console
3. Governance / CGT
4. Admin Workspace
5. Qualification Evidence

This order matches the Startup Tunisia demo narrative while avoiding authentication and runtime setup during recording.
