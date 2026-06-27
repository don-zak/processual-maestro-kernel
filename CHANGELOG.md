# Changelog

## [2.0.0] — 2026-05-19

### Added
- CGT Governor module with adapter comparison, auto-repair, gateway management, and simulation engine
- LLM-powered narrative report generation (OpenAI, Anthropic, Gemini, DeepSeek)
- Rate limiting middleware with Redis backend
- Comprehensive test coverage at 99%
- Security audit: sanitised error messages, removed exception type disclosure

### Changed
- Migrated from raw CGT equations to adapter-based architecture
- Production readiness improvements across all modules
- Code organisation cleanup (package exports, docstrings)

### Fixed
- Info leakage via endpoint error messages and exception traces
- Missing middleware exports in package API

## [1.9.0] — 2026-05-13

### Added
- Billing integration with Lemon Squeezy (checkout, portal, webhooks)
- B2B application/approval workflow
- Discord notification service with rate limiting
- Telemetry ingestion endpoint

### Changed
- Upgraded to Python 3.14
- Enhanced security headers middleware

## [1.8.0] — 2026-05-10

### Added
- Encrypted report indexing and HTML review interface
- Arabic UI with RTL support
- Adaptive governance toolkit enhancements

### Fixed
- Concurrent write issues in JSON file storage
- CGT evaluation edge cases
