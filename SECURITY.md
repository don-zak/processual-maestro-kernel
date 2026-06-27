# Security Policy

## Reporting a Vulnerability

If you discover a security vulnerability, please do **not** open a public issue.

Instead, send a detailed report to the project maintainers. Please include:

- A description of the vulnerability
- Steps to reproduce
- Potential impact
- Suggested fix (if known)

## What to Expect

- Acknowledgement within 48 hours
- A fix will be prioritised based on severity
- You will be credited for the discovery (unless you request otherwise)

## Security Measures

This project implements the following security measures:

- **Authentication**: JWT (HS256) + API keys (bcrypt-hashed)
- **Encryption**: AES-256-GCM for sensitive stored data
- **Rate Limiting**: Per-client throttling via Redis
- **Input Validation**: Pydantic schemas on all endpoints
- **Error Handling**: Sanitised error messages (no stack traces, no exception types)
- **Headers**: Security headers via `SecurityHeadersMiddleware`
- **Audit**: Request logging via `AuditMiddleware`

See [docs/security/](docs/security/) for full documentation.
