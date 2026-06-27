# Frontend Documentation

## Maestro Console

The Maestro Console is a single-page application served at `/console` when the static build directory exists.

### Technology Stack

- **Framework**: Vanilla HTML/CSS/JS (no framework dependency)
- **Styling**: Dark theme with CSS custom properties
  - `--void: #080b0f` — primary background
  - `--amber: #f5a623` — accent color
  - `--surface: #0d1117` — card surfaces
- **Typography**:
  - Syne — display headings
  - Space Mono — code/monospace
  - DM Mono — data visualisations
- **RTL Support**: Full Arabic right-to-left layout with language toggle

### Pages

| Route | Description |
|-------|-------------|
| `/console/` | Dashboard — overview, stats, recent evaluations |
| `/console/login` | Authentication (JWT + API key) |
| `/console/metrics` | System metrics and Prometheus dashboard |

### Build

```bash
# Static files live in processual_api/static/
# No build step required — served directly by FastAPI
```
