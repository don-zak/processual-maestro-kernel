from __future__ import annotations

import subprocess
import sys


def _import_in_fresh_interpreter(statement: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-c", statement],
        text=True,
        capture_output=True,
        check=False,
    )


def test_billing_domain_helper_import_does_not_construct_router_graph() -> None:
    completed = _import_in_fresh_interpreter(
        "import sys; "
        "from processual_api.billing.public_plan_journey import public_plan_journey_catalog; "
        "assert callable(public_plan_journey_catalog); "
        "assert 'processual_api.billing.router' not in sys.modules; "
        "assert 'processual_api.admin_marketplace.lemon_squeezy_secure_webhook_router' not in sys.modules"
    )
    assert completed.returncode == 0, completed.stderr


def test_registration_runtime_import_is_free_of_billing_admin_cycle() -> None:
    completed = _import_in_fresh_interpreter(
        "import processual_api.auth.registration_runtime; print('ok')"
    )
    assert completed.returncode == 0, completed.stderr
    assert completed.stdout.strip().endswith("ok")


def test_billing_and_admin_packages_can_be_imported_in_either_order() -> None:
    statements = (
        "import processual_api.billing; import processual_api.admin_marketplace",
        "import processual_api.admin_marketplace; import processual_api.billing",
    )
    for statement in statements:
        completed = _import_in_fresh_interpreter(statement)
        assert completed.returncode == 0, completed.stderr
