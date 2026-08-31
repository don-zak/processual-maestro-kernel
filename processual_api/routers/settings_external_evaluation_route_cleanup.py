"""Remove duplicate registrations created while replacing legacy evaluation routes."""

from __future__ import annotations

from typing import Any

from fastapi.routing import APIRoute

from . import settings as settings_module

_TARGETS = {
    ("/settings/admin/evaluation-grants/authority", "GET"),
    ("/settings/admin/evaluation-grants/access-catalog", "GET"),
}


def _key(route: Any) -> tuple[str, str] | None:
    if not isinstance(route, APIRoute):
        return None
    for method in route.methods or set():
        candidate = (route.path, method)
        if candidate in _TARGETS:
            return candidate
    return None


last_index: dict[tuple[str, str], int] = {}
for index, route in enumerate(settings_module.router.routes):
    key = _key(route)
    if key is not None:
        last_index[key] = index

settings_module.router.routes[:] = [
    route
    for index, route in enumerate(settings_module.router.routes)
    if (key := _key(route)) is None or last_index.get(key) == index
]

__all__ = ["_TARGETS"]
