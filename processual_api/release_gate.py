from __future__ import annotations

import os
import sys
from collections.abc import Mapping
from dataclasses import dataclass
from urllib.parse import urlparse

EXPECTED_ALEMBIC_HEAD = "20260805_0029"
ALLOWED_RELEASE_ENVIRONMENTS = {"staging", "production"}
_PLACEHOLDER_MARKERS = (
    "replace_with",
    "change_me",
    "changeme",
    "example.com",
    "your-frontend",
    "yourdomain",
)
