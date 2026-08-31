"""API route handlers — all HTTP endpoints organized by domain."""

from processual_api.auth import evaluation_access_extension as _evaluation_access_extension  # noqa: F401,E402

# Register route extensions on settings_router.
# Importing for side effects is intentional: main.py already includes settings_router.
from . import cgt_governor_external_guard as _cgt_governor_external_guard  # noqa: F401,E402
from . import client_api_keys_18 as _client_api_keys_18  # noqa: F401,E402
from . import client_provider_alias_18 as _client_provider_alias_18  # noqa: F401,E402
from . import evaluation_runtime as _evaluation_runtime  # noqa: F401,E402
from . import institution_cases_18 as _institution_cases_18  # noqa: F401,E402
from . import settings_admin_api_key_provisioning as _settings_admin_api_key_provisioning  # noqa: F401,E402
from . import settings_admin_evaluation_grants as _settings_admin_evaluation_grants  # noqa: F401,E402
from . import (  # noqa: F401,E402
    settings_enterprise_endpoint_bindings_runtime as _settings_enterprise_endpoint_bindings_runtime,
)
from . import (  # noqa: F401,E402
    settings_enterprise_endpoint_failure_review_runtime as _settings_enterprise_endpoint_failure_review_runtime,
)
from . import (  # noqa: F401,E402
    settings_enterprise_integration_runtime as _settings_enterprise_integration_runtime,
)
from . import (  # noqa: F401,E402
    settings_enterprise_sandbox_operational_runtime as _settings_enterprise_sandbox_operational_runtime,
)
from . import settings_external_evaluation_access as _settings_external_evaluation_access  # noqa: F401,E402
from . import (  # noqa: F401,E402
    settings_external_evaluation_route_cleanup as _settings_external_evaluation_route_cleanup,
)
from . import settings_provider_test_runtime as _settings_provider_test_runtime  # noqa: F401,E402
from . import settings_subscription_runtime as _settings_subscription_runtime  # noqa: F401,E402
from .applications import router as applications_router
from .cgt import router as cgt_router
from .cgt_governor import router as cgt_governor_router
from .discord import router as discord_router
from .execution_observability import router as execution_observability_router
from .governance import router as governance_router
from .health import router as health_router
from .reports import router as reports_router
from .settings import router as settings_router
from .telemetry import router as telemetry_router
from .workflows import router as workflows_router

__all__ = [
    "health_router",
    "cgt_router",
    "workflows_router",
    "governance_router",
    "telemetry_router",
    "reports_router",
    "discord_router",
    "cgt_governor_router",
    "execution_observability_router",
    "settings_router",
    "applications_router",
]
