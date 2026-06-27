# ADR-001: JSON File Storage for MVP

**Date**: 2026-05-13

**Status**: Accepted

## Context
The project needs persistent storage for settings, applications, and subscription data. A traditional relational database (PostgreSQL) is scaffolded in docker-compose and session management, but no ORM models exist yet.

## Decision
Use JSON file storage (`processual_api/data/*.json`) for MVP phase. This includes:
- User settings and LLM provider config (encrypted API keys via AES-256-GCM)
- B2B applications and approvals
- Subscription state

## Rationale
- No database migrations to manage during rapid iteration
- Easy to inspect, backup, and debug (plain JSON)
- Sufficient for single-server deployments with low request volume
- PostgreSQL + Alembic migrations will be introduced when multi-tenant user/org system is needed

## Consequences
- Not suitable for high-write concurrency (file locking)
- No built-in querying or indexing
- Migration to DB will require a script to convert existing JSON data

## Migration Trigger
Transition to PostgreSQL when any of:
1. More than 10 concurrent users
2. Need for relational queries (e.g., multi-tenant orgs)
3. Deployment to multi-replica setup
