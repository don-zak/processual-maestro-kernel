"""Billing package.

Import concrete routers from their modules explicitly. Package initialization is
kept side-effect free so domain helpers can be imported without constructing the
entire HTTP application graph.
"""

__all__: list[str] = []
