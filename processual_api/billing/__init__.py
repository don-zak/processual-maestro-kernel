"""Billing & subscription management — Lemon Squeezy integration.

Keep the package attribute ``router`` available as the *submodule* so imports like
``import processual_api.billing.router as br`` resolve to the module, not the
APIRouter instance.  The APIRouter is exposed as ``billing_router``.
"""

from importlib import import_module

router = import_module(__name__ + ".router")
billing_router = router.router

__all__ = ["billing_router"]
