# A3 Unified Baseline Summary

## Registration references
processual_api/adapters/kernel_adapter.py:11:        self._registrations: dict[str, str] = {}
processual_api/adapters/kernel_adapter.py:17:        self._registrations[agent_id] = role
processual_api/auth/account_recovery_runtime.py:161:        minimum_response_seconds = config.auth_registration_min_response_ms / 1000
processual_api/auth/recovery_email_runtime.py:155:            config.auth_registration_min_response_ms
processual_api/auth/registration_contracts.py:1:"""Runtime-neutral identity and registration contracts.
processual_api/auth/registration_contracts.py:93:    registration_modes: tuple[RegistrationMode, ...] = PUBLIC_SELF_SERVICE_MODES
processual_api/auth/registration_contracts.py:118:    contract_id: str = "identity_registration_r1"
processual_api/auth/registration_contracts.py:138:    platform_admin_public_registration: bool = False
processual_api/auth/registration_contracts.py:182:            "platform_admin_public_registration": (self.platform_admin_public_registration),
processual_api/auth/registration_contracts.py:208:def get_identity_registration_security_contract() -> IdentityRegistrationSecurityContract:
processual_api/auth/registration_contracts.py:231:    "get_identity_registration_security_contract",
processual_api/auth/registration_repository.py:22:    """A uniqueness race prevented the registration transaction."""
processual_api/auth/registration_repository.py:133:    def add_registration(
processual_api/auth/registration_repository.py:179:                raise ValueError("Organization registration requires slug and name.")
processual_api/auth/registration_repository.py:214:            raise ValueError("Delivery outbox requires pending registration principals.")
processual_api/auth/registration_router.py:23:from processual_api.auth.registration_contracts import (
processual_api/auth/registration_router.py:34:from processual_api.auth.registration_runtime import (
processual_api/auth/registration_router.py:37:    build_registration_runtime,
processual_api/auth/registration_router.py:39:from processual_api.auth.registration_service import RegistrationCommand
processual_api/auth/registration_router.py:43:GENERIC_INVALID = "Invalid registration request."
processual_api/auth/registration_router.py:63:    tags=["identity-registration"],
processual_api/auth/registration_router.py:68:async def get_registration_runtime() -> RegistrationRuntime:
processual_api/auth/registration_router.py:70:        return await build_registration_runtime()
processual_api/auth/registration_router.py:90:        "identity_registration",
processual_api/auth/registration_router.py:93:            "registration_mode": mode.value,
processual_api/auth/registration_router.py:94:            "registration_result": result,
processual_api/auth/registration_router.py:196:            "identity_registration_authority_failed",
processual_api/auth/registration_router.py:199:                "registration_mode": mode.value,
processual_api/auth/registration_router.py:211:    "/registration/config",
processual_api/auth/registration_router.py:214:async def registration_config() -> RegistrationConfigResponseContract:
processual_api/auth/registration_router.py:219:    "/register",
processual_api/auth/registration_router.py:226:    runtime: RegistrationRuntime = Depends(get_registration_runtime),
processual_api/auth/registration_router.py:238:    "/register/organization",
processual_api/auth/registration_router.py:245:    runtime: RegistrationRuntime = Depends(get_registration_runtime),
processual_api/auth/registration_router.py:263:    runtime: RegistrationRuntime = Depends(get_registration_runtime),
processual_api/auth/registration_router.py:310:    runtime: RegistrationRuntime = Depends(get_registration_runtime),
processual_api/auth/registration_router.py:368:__all__ = ["get_registration_runtime", "router"]
processual_api/auth/registration_runtime.py:12:from processual_api.auth.registration_repository import SqlAlchemyRegistrationUnitOfWork
processual_api/auth/registration_runtime.py:13:from processual_api.auth.registration_service import RegistrationService
processual_api/auth/registration_runtime.py:21:    """A required registration authority is missing or invalid."""
processual_api/auth/registration_runtime.py:71:async def build_registration_runtime(config: APISettings = settings) -> RegistrationRuntime:
processual_api/auth/registration_runtime.py:86:        minimum_response_seconds = config.auth_registration_min_response_ms / 1000
processual_api/auth/registration_runtime.py:118:    "build_registration_runtime",
processual_api/auth/registration_service.py:17:from processual_api.auth.registration_contracts import RegistrationMode
processual_api/auth/registration_service.py:18:from processual_api.auth.registration_repository import RegistrationConflictError
processual_api/auth/registration_service.py:29:    def add_registration(self, **values) -> None: ...
processual_api/auth/registration_service.py:96:                raise ValueError("Organization registration requires a name.")
processual_api/auth/registration_service.py:104:            raise ValueError("Individual registration cannot create an organization.")
processual_api/auth/registration_service.py:128:                unit_of_work.repository.add_registration(
processual_api/billing/offer_fulfillment_policy.py:15:    "registration_required": True,
processual_api/billing/offer_fulfillment_policy.py:50:    "registration_required": True,
processual_api/billing/offer_fulfillment_policy.py:67:    "registration_required": True,
processual_api/billing/offer_pricebook.py:52:            "Paid trial for evaluating Starter access after registration and payment. "
processual_api/billing/public_plan_journey.py:91:                "registration_available": not requires_assessment,
processual_api/billing/public_plan_journey.py:92:                "action": ("start_registration" if not requires_assessment else "request_assessment"),
processual_api/billing/public_plan_journey.py:97:        "version": "2026-08-plan-led-registration-v1",
processual_api/billing/router.py:362:    """Return the public plan-led registration journey catalog."""
processual_api/integrations/operator_sandbox_intake.py:544:            "endpoint_registration_disabled",
processual_api/integrations/operator_sandbox_intake.py:546:            "secret_reference_registration_disabled",
processual_api/integrations/secret_manager_contracts.py:887:            "reference_registration_pending",
processual_api/integrations/secret_provider_binding_readiness.py:621:            "secret_reference_registration_disabled",
processual_api/integrations/transport_contracts.py:1015:        "transport_registration_pending",
processual_api/main.py:84:from .auth.registration_router import router as registration_router
processual_api/main.py:145:app.include_router(registration_router)
processual_api/main.py:213:@app.get("/register", response_class=HTMLResponse, include_in_schema=False)
processual_api/main.py:214:async def registration_page() -> HTMLResponse:
processual_api/middleware/rate_limit.py:13:    "/auth/register",
processual_api/middleware/rate_limit.py:14:    "/auth/register/organization",
processual_api/middleware/subscription.py:33:    "/auth/registration/config",
processual_api/middleware/subscription.py:34:    "/auth/register",
processual_api/middleware/subscription.py:35:    "/auth/register/organization",
processual_api/routers/workflows.py:58:        # registration errors visible as 400 responses.
processual_api/settings.py:71:    # --- Identity registration authority (fail-closed when incomplete) ---
processual_api/settings.py:88:    auth_registration_min_response_ms: int = field(
processual_api/static/js/pages/offer.js:50:    action.href = `/register?plan=${encodeURIComponent(
processual_api/static/js/pages/offer.js:61:    action.textContent = "Start registration";
processual_api/static/js/pages/offer.js:62:    action.href = `/register?plan=${encodeURIComponent(plan.plan_id)}`;
processual_api/static/js/pages/register.js:3:(function registrationController() {
processual_api/static/js/pages/register.js:4:  const form = document.getElementById("registration-form");
processual_api/static/js/pages/register.js:5:  const status = document.getElementById("registration-status");
processual_api/static/js/pages/register.js:6:  const submit = document.getElementById("registration-submit");
processual_api/static/js/pages/register.js:7:  const modeFieldset = document.getElementById("registration-mode-fieldset");
processual_api/static/js/pages/register.js:9:  const organizationInput = document.getElementById("registration-organization-name");
processual_api/static/js/pages/register.js:10:  const passwordInput = document.getElementById("registration-password");
processual_api/static/js/pages/register.js:18:    const selected = form.querySelector('input[name="registration_mode"]:checked');
processual_api/static/js/pages/register.js:39:      const response = await fetch("/auth/registration/config", {
processual_api/static/js/pages/register.js:51:      const allowedModes = Array.isArray(config.registration_modes)
processual_api/static/js/pages/register.js:52:        ? config.registration_modes
processual_api/static/js/pages/register.js:60:        .querySelectorAll('input[name="registration_mode"]')
processual_api/static/js/pages/register.js:98:      setStatus("Review the highlighted registration fields.", "error");
processual_api/static/js/pages/register.js:105:        ? "/auth/register/organization"
processual_api/static/js/pages/register.js:106:        : "/auth/register";
processual_api/static/js/pages/register.js:109:    setStatus("Submitting your registration request...", "loading");
processual_api/static/js/pages/register.js:124:          "Too many registration attempts. Please try again later.",
processual_api/static/js/pages/register.js:139:        setStatus("Invalid registration request.", "error");
processual_api/static/login.html:185:    id="login-offers-registration-button"
processual_api/static/login.html:186:    aria-label="View subscription options and registration"
processual_api/static/offer.html:13:    content="Review a Maestro plan offer before registration."
processual_api/static/offer.html:40:          <a id="offer-action" class="primary-action" href="/register">
processual_api/static/plans.html:13:    content="Choose a Maestro plan to review its offer and begin registration."
processual_api/static/pricing.html:669:    return "Self-service after registration and payment";
processual_api/static/register.html:146:    <form id="registration-form" novalidate>
processual_api/static/register.html:147:      <fieldset id="registration-mode-fieldset">
processual_api/static/register.html:151:            <input type="radio" name="registration_mode" value="individual" checked>
processual_api/static/register.html:155:            <input type="radio" name="registration_mode" value="organization">
processual_api/static/register.html:162:        <label for="registration-full-name">Full name</label>
processual_api/static/register.html:164:          id="registration-full-name"
processual_api/static/register.html:175:        <label for="registration-organization-name">Organization name</label>
processual_api/static/register.html:177:          id="registration-organization-name"
processual_api/static/register.html:187:        <label for="registration-email">Email address</label>
processual_api/static/register.html:189:          id="registration-email"
processual_api/static/register.html:200:        <label for="registration-password">Password</label>
processual_api/static/register.html:202:          id="registration-password"
processual_api/static/register.html:218:          id="registration-terms"
processual_api/static/register.html:233:      <button id="registration-submit" type="submit">
processual_api/static/register.html:234:        Submit registration
processual_api/static/register.html:239:      id="registration-status"
processual_api/static/register.html:259:  <script src="/console/js/pages/register.js"></script>
tests/integration/test_auth_email_verification_r6a_integration.py:17:import processual_api.auth.registration_runtime as runtime_module
tests/integration/test_auth_email_verification_r6a_integration.py:23:from processual_api.auth.registration_router import get_registration_runtime, router
tests/integration/test_auth_email_verification_r6a_integration.py:24:from processual_api.auth.registration_runtime import build_registration_runtime
tests/integration/test_auth_email_verification_r6a_integration.py:67:        auth_registration_min_response_ms=0,
tests/integration/test_auth_email_verification_r6a_integration.py:75:    runtime = await build_registration_runtime(config)
tests/integration/test_auth_email_verification_r6a_integration.py:83:    app.dependency_overrides[get_registration_runtime] = lambda: runtime
tests/integration/test_auth_email_verification_r6a_integration.py:88:            registration = await client.post(
tests/integration/test_auth_email_verification_r6a_integration.py:89:                "/auth/register",
tests/integration/test_auth_email_verification_r6a_integration.py:97:            assert registration.status_code == 202
tests/integration/test_auth_registration_http_r5b_r1_integration.py:16:import processual_api.auth.registration_runtime as runtime_module
tests/integration/test_auth_registration_http_r5b_r1_integration.py:29:from processual_api.auth.registration_router import get_registration_runtime, router
tests/integration/test_auth_registration_http_r5b_r1_integration.py:30:from processual_api.auth.registration_runtime import build_registration_runtime
tests/integration/test_auth_registration_http_r5b_r1_integration.py:47:async def test_registration_http_uses_real_postgresql_and_redis(monkeypatch):
tests/integration/test_auth_registration_http_r5b_r1_integration.py:65:        auth_registration_min_response_ms=0,
tests/integration/test_auth_registration_http_r5b_r1_integration.py:73:    runtime = await build_registration_runtime(config)
tests/integration/test_auth_registration_http_r5b_r1_integration.py:94:    app.dependency_overrides[get_registration_runtime] = lambda: runtime
tests/integration/test_auth_registration_http_r5b_r1_integration.py:100:                "/auth/register",
tests/integration/test_auth_registration_http_r5b_r1_integration.py:148:                "/auth/register/organization",
tests/test_auth_account_recovery_runtime_r9a.py:34:        "auth_registration_min_response_ms": 350,
tests/test_auth_account_recovery_runtime_r9a.py:83:        {"auth_registration_min_response_ms": 6000},
tests/test_auth_rate_limit_r5a.py:113:def test_security_policy_defaults_cover_registration_resend_and_verification() -> None:
tests/test_auth_recovery_email_runtime_r8d.py:34:        auth_registration_min_response_ms=0,
tests/test_auth_registration_http_r5b_r1.py:14:from processual_api.auth.registration_router import (
tests/test_auth_registration_http_r5b_r1.py:15:    get_registration_runtime,
tests/test_auth_registration_http_r5b_r1.py:18:from processual_api.auth.registration_runtime import RegistrationRuntime
tests/test_auth_registration_http_r5b_r1.py:73:    app.dependency_overrides[get_registration_runtime] = lambda: runtime
tests/test_auth_registration_http_r5b_r1.py:98:def test_individual_registration_uses_ip_then_normalized_email_and_returns_202():
tests/test_auth_registration_http_r5b_r1.py:104:        "/auth/register",
tests/test_auth_registration_http_r5b_r1.py:106:        headers={"X-Request-ID": "registration-test-1"},
tests/test_auth_registration_http_r5b_r1.py:111:    assert response.headers["X-Request-ID"] == "registration-test-1"
tests/test_auth_registration_http_r5b_r1.py:117:def test_email_limit_is_generic_202_and_does_not_call_registration_service():
tests/test_auth_registration_http_r5b_r1.py:126:        "/auth/register",
tests/test_auth_registration_http_r5b_r1.py:140:        "/auth/register",
tests/test_auth_registration_http_r5b_r1.py:152:        "/auth/register",
tests/test_auth_registration_http_r5b_r1.py:156:        "/auth/register",
tests/test_auth_registration_http_r5b_r1.py:172:        "/auth/register",
tests/test_auth_registration_http_r5b_r1.py:177:    assert response.json() == {"detail": "Invalid registration request."}
tests/test_auth_registration_http_r5b_r1.py:187:        "/auth/register/organization",
tests/test_auth_registration_http_r5b_r1.py:197:    response = _client(_runtime()).get("/auth/registration/config")
tests/test_auth_registration_http_r5b_r1.py:201:        "registration_modes": ["individual", "organization"],
tests/test_auth_registration_http_r5b_r1.py:225:    accepted_response = accepted_client.post("/auth/register", json=_individual_payload())
tests/test_auth_registration_http_r5b_r1.py:228:    limited_response = limited_client.post("/auth/register", json=_individual_payload())
tests/test_auth_registration_http_r5b_r1.py:300:    assert response.json() == {"detail": "Invalid registration request."}
tests/test_auth_registration_repository_r4.py:18:from processual_api.auth.registration_repository import (
tests/test_auth_registration_repository_r4.py:30:    repository.add_registration(
tests/test_auth_registration_repository_r4.py:68:    repository.add_registration(
tests/test_auth_registration_runtime_r5b_r1.py:9:import processual_api.auth.registration_runtime as runtime_module
tests/test_auth_registration_runtime_r5b_r1.py:10:from processual_api.auth.registration_runtime import (
tests/test_auth_registration_runtime_r5b_r1.py:12:    build_registration_runtime,
tests/test_auth_registration_runtime_r5b_r1.py:29:        "auth_registration_min_response_ms": 350,
tests/test_auth_registration_runtime_r5b_r1.py:43:    runtime = await build_registration_runtime(_config())
tests/test_auth_registration_runtime_r5b_r1.py:61:        {"auth_registration_min_response_ms": 6000},
tests/test_auth_registration_runtime_r5b_r1.py:72:        await build_registration_runtime(_config(**updates))
tests/test_auth_registration_runtime_r5b_r1.py:83:        await build_registration_runtime(_config())
tests/test_auth_registration_service_r4.py:12:from processual_api.auth.registration_contracts import RegistrationMode
tests/test_auth_registration_service_r4.py:13:from processual_api.auth.registration_repository import RegistrationConflictError
tests/test_auth_registration_service_r4.py:14:from processual_api.auth.registration_service import (
tests/test_auth_registration_service_r4.py:43:    def add_registration(self, **values) -> None:
tests/test_auth_registration_service_r4.py:88:async def test_individual_registration_is_atomic_and_hash_only() -> None:
tests/test_connector_secret_manager_contracts_16e_r2.py:458:        "reference_registration_pending",
tests/test_connector_transport_contracts_16e_r3.py:492:        "transport_registration_pending",
tests/test_identity_auth_models_r2.py:17:from processual_api.auth.registration_contracts import (
tests/test_identity_auth_models_r2.py:19:    get_identity_registration_security_contract,
tests/test_identity_auth_models_r2.py:100:    contract = get_identity_registration_security_contract()
tests/test_identity_registration_contracts_r1.py:9:from processual_api.auth.registration_contracts import (
tests/test_identity_registration_contracts_r1.py:19:    get_identity_registration_security_contract,
tests/test_identity_registration_contracts_r1.py:25:def test_registration_modes_are_hybrid_and_platform_admin_is_not_public() -> None:
tests/test_identity_registration_contracts_r1.py:26:    contract = get_identity_registration_security_contract()
tests/test_identity_registration_contracts_r1.py:39:    assert contract.platform_admin_public_registration is False
tests/test_identity_registration_contracts_r1.py:42:def test_registration_and_login_requests_forbid_authority_fields() -> None:
tests/test_identity_registration_contracts_r1.py:70:def test_registration_safe_response_does_not_expose_identity_or_tokens() -> None:
tests/test_identity_registration_contracts_r1.py:87:    contract = get_identity_registration_security_contract()
tests/test_identity_registration_contracts_r1.py:104:    contract = get_identity_registration_security_contract()
tests/test_identity_registration_contracts_r1.py:125:        ("platform_admin_public_registration", True),
tests/test_identity_registration_contracts_r1.py:144:    contract = get_identity_registration_security_contract()
tests/test_identity_registration_contracts_r1.py:183:        / "identity-registration-session.adr.md"
tests/test_identity_registration_contracts_r1.py:217:        "POST /auth/register",
tests/test_identity_registration_contracts_r1.py:226:def test_registration_contract_module_is_runtime_neutral() -> None:
tests/test_identity_registration_contracts_r1.py:231:        / "registration_contracts.py"
tests/test_login_gateway_actions_ui.py:14:    assert 'id="login-offers-registration-button"' in text
tests/test_middleware_regression.py:81:def test_registration_routes_bypass_legacy_rate_limit_middleware(monkeypatch):
tests/test_middleware_regression.py:84:            raise AssertionError("legacy limiter must not inspect registration")
tests/test_middleware_regression.py:92:        "/auth/register",
tests/test_middleware_regression.py:93:        "/auth/register/organization",
tests/test_pricing_offers_surface_ui.py:73:    assert "Self-service after registration and payment" in source
tests/test_pricing_subscriptions_surface_ui.py:63:    assert 'id="login-offers-registration-button"' in text
tests/test_pricing_subscriptions_surface_ui.py:65:    assert 'aria-label="View subscription options and registration"' in text
tests/test_public_plan_journey_a3.py:39:        assert by_id[plan_id]["registration_available"] is True
tests/test_public_plan_journey_a3.py:40:        assert by_id[plan_id]["action"] == "start_registration"
tests/test_public_plan_journey_a3.py:55:        assert by_id[plan_id]["registration_available"] is False
tests/test_public_plan_journey_route_a3.py:13:    assert payload["version"] == "2026-08-plan-led-registration-v1"
tests/test_public_plan_journey_route_a3.py:48:        assert by_id[plan_id]["registration_available"] is False
tests/test_registration_page_ui_a3.py:11:def test_registration_page_is_available() -> None:
tests/test_registration_page_ui_a3.py:14:    response = client.get("/register")
tests/test_registration_page_ui_a3.py:20:def test_registration_page_contains_accessible_form_contract() -> None:
tests/test_registration_page_ui_a3.py:23:    assert 'id="registration-form"' in html
tests/test_registration_page_ui_a3.py:33:def test_registration_page_loads_controller() -> None:
tests/test_registration_page_ui_a3.py:36:    assert "/console/js/pages/register.js" in html
tests/test_registration_page_ui_a3.py:39:def test_registration_controller_uses_server_config_and_safe_response() -> None:
tests/test_registration_page_ui_a3.py:42:    assert "registration/config" in javascript
tests/test_registration_page_ui_a3.py:43:    assert "registration" in javascript

## Verification references
processual_api/admin_marketplace/audit_contracts.py:24:    PAYMENT_VERIFICATION_DECIDED = "payment_verification_decided"
processual_api/admin_marketplace/audit_contracts.py:32:    PAYMENT_VERIFICATION = "payment_verification"
processual_api/admin_marketplace/contracts.py:121:    AWAITING_PAYMENT_VERIFICATION = "awaiting_payment_verification"
processual_api/admin_marketplace/contracts.py:283:    verification_id: str
processual_api/admin_marketplace/contracts.py:289:        object.__setattr__(self, "verification_id", _required_code(self.verification_id, field_name="verification_id"))
processual_api/admin_marketplace/models.py:332:                'awaiting_payment_verification',
processual_api/admin_marketplace/models.py:383:    __tablename__ = "admin_market_payment_verifications"
processual_api/admin_marketplace/models.py:397:            "verification_ref",
processual_api/admin_marketplace/models.py:398:            name=("uq_admin_market_payment_verifications_verification_ref"),
processual_api/admin_marketplace/models.py:401:            "ix_admin_market_payment_verifications_order_status",
processual_api/admin_marketplace/models.py:408:    verification_ref: Mapped[str] = mapped_column(
processual_api/admin_marketplace/models.py:416:            name="fk_admin_market_payment_verification_order",
processual_api/admin_marketplace/models.py:736:                'payment_verification_decided',
processual_api/admin_marketplace/models.py:748:                'payment_verification',
processual_api/admin_marketplace/persistence/protocols.py:100:        verification_id: uuid.UUID,
processual_api/admin_marketplace/persistence/protocols.py:107:        verification: AdminMarketPaymentVerification,
processual_api/admin_marketplace/persistence/protocols.py:211:    payment_verifications: PaymentVerificationRepository
processual_api/admin_marketplace/persistence/repositories.py:160:    """Persistence operations for payment-verification decisions."""
processual_api/admin_marketplace/persistence/repositories.py:167:        verification_id: uuid.UUID,
processual_api/admin_marketplace/persistence/repositories.py:172:            AdminMarketPaymentVerification.id == verification_id,
processual_api/admin_marketplace/persistence/repositories.py:182:        verification: AdminMarketPaymentVerification,
processual_api/admin_marketplace/persistence/repositories.py:184:        self._session.add(verification)
processual_api/admin_marketplace/persistence/unit_of_work.py:44:        self.payment_verifications: SqlAlchemyPaymentVerificationRepository
processual_api/admin_marketplace/persistence/unit_of_work.py:67:        self.payment_verifications = SqlAlchemyPaymentVerificationRepository(session)
processual_api/auth/account_recovery_contracts.py:3:AUTH-R9A deliberately separates recovery-email verification from account
processual_api/auth/account_recovery_repository.py:12:    AuthActionToken,
processual_api/auth/account_recovery_repository.py:109:        verification_token_hash: str,
processual_api/auth/account_recovery_repository.py:131:            verification_token_hash=(verification_token_hash),
processual_api/auth/account_recovery_repository.py:147:            event_type="account_recovery_verification",
processual_api/auth/account_recovery_repository.py:222:            update(AuthActionToken)
processual_api/auth/account_recovery_repository.py:224:                AuthActionToken.user_id == user_id,
processual_api/auth/account_recovery_repository.py:225:                AuthActionToken.consumed_at.is_(None),
processual_api/auth/account_recovery_repository.py:226:                AuthActionToken.invalidated_at.is_(None),
processual_api/auth/account_recovery_router.py:46:GENERIC_DENIED = "Account recovery verification is unavailable."
processual_api/auth/account_recovery_service.py:23:ACCOUNT_RECOVERY_VERIFICATION_TOKEN_PURPOSE = "account_recovery_verification"
processual_api/auth/account_recovery_service.py:165:        verification_ttl: timedelta = (ACCOUNT_RECOVERY_VERIFICATION_TTL),
processual_api/auth/account_recovery_service.py:169:        if verification_ttl <= timedelta(0):
processual_api/auth/account_recovery_service.py:170:            raise ValueError("Account recovery verification TTL must be positive.")
processual_api/auth/account_recovery_service.py:184:        self._verification_ttl = verification_ttl
processual_api/auth/account_recovery_service.py:267:            verification_expires_at = now + self._verification_ttl
processual_api/auth/account_recovery_service.py:269:            verification = self._token_digester.generate_token(purpose=(ACCOUNT_RECOVERY_VERIFICATION_TOKEN_PURPOSE))
processual_api/auth/account_recovery_service.py:277:                verification.raw,
processual_api/auth/account_recovery_service.py:291:                verification_token_hash=verification.digest,
processual_api/auth/account_recovery_service.py:294:                expires_at=verification_expires_at,
processual_api/auth/account_recovery_service.py:323:            raise AccountRecoveryDeniedError("Account recovery verification is unavailable.") from exc
processual_api/auth/account_recovery_service.py:329:                raise AccountRecoveryDeniedError("Account recovery verification is unavailable.")
processual_api/auth/account_recovery_service.py:338:                raise AccountRecoveryDeniedError("Account recovery verification is unavailable.")
processual_api/auth/account_recovery_service.py:346:                raise AccountRecoveryDeniedError("Account recovery verification is unavailable.")
processual_api/auth/account_recovery_service.py:349:                request.verification_token_hash,
processual_api/auth/account_recovery_service.py:363:                raise AccountRecoveryDeniedError("Account recovery verification is unavailable.")
processual_api/auth/admin_recovery_email_service.py:145:                    "Pending recovery email verification is unavailable."
processual_api/auth/delivery_dispatcher.py:32:    verification_path: str
processual_api/auth/delivery_dispatcher.py:37:    "verify_email": DeliveryEventProfile(
processual_api/auth/delivery_dispatcher.py:38:        purpose="verify_email",
processual_api/auth/delivery_dispatcher.py:39:        template="verify_email",
processual_api/auth/delivery_dispatcher.py:40:        verification_path="/verify-email",
processual_api/auth/delivery_dispatcher.py:41:        eligible_user_statuses=frozenset({"pending_verification"}),
processual_api/auth/delivery_dispatcher.py:46:        verification_path="/auth/recovery-email/verify",
processual_api/auth/delivery_dispatcher.py:49:    "account_recovery_verification": DeliveryEventProfile(
processual_api/auth/delivery_dispatcher.py:50:        purpose="account_recovery_verification",
processual_api/auth/delivery_dispatcher.py:51:        template="account_recovery_verification",
processual_api/auth/delivery_dispatcher.py:52:        verification_path="/auth/account-recovery/verify",
processual_api/auth/delivery_dispatcher.py:177:    def _verification_url(
processual_api/auth/delivery_dispatcher.py:191:        return f"{self._config.public_base_url}{profile.verification_path}?{query}"
processual_api/auth/delivery_dispatcher.py:329:                    await self._provider.send_verification_email(
processual_api/auth/delivery_dispatcher.py:332:                        verification_url=(
processual_api/auth/delivery_dispatcher.py:333:                            self._verification_url(
processual_api/auth/delivery_provider.py:10:        "verify_email",
processual_api/auth/delivery_provider.py:12:        "account_recovery_verification",
processual_api/auth/delivery_provider.py:30:    async def send_verification_email(
processual_api/auth/delivery_provider.py:35:        verification_url: str,
processual_api/auth/delivery_provider.py:83:    async def send_verification_email(
processual_api/auth/delivery_provider.py:88:        verification_url: str,
processual_api/auth/delivery_provider.py:92:            raise ValueError("Delivery verification template is invalid.")
processual_api/auth/delivery_provider.py:108:                        "verification_url": verification_url,
processual_api/auth/delivery_repository.py:18:    AuthActionToken,
processual_api/auth/delivery_repository.py:50:                        AuthActionToken,
processual_api/auth/delivery_repository.py:60:                        AuthActionToken,
processual_api/auth/delivery_repository.py:61:                        AuthActionToken.id == AuthDeliveryOutbox.action_token_id,
processual_api/auth/delivery_repository.py:123:                    if outbox.event_type == "verify_email":
processual_api/auth/delivery_repository.py:127:                    elif outbox.event_type == "account_recovery_verification" and verified_recovery_address is not None:
processual_api/auth/email_verification_service.py:14:    from processual_api.auth.models import AuthActionToken, IdentityUser
processual_api/auth/email_verification_service.py:21:    async def verification_principals_for_update(
processual_api/auth/email_verification_service.py:24:    ) -> tuple[AuthActionToken, IdentityUser] | None: ...
processual_api/auth/email_verification_service.py:28:    async def latest_active_verification_token(
processual_api/auth/email_verification_service.py:31:    ) -> AuthActionToken | None: ...
processual_api/auth/email_verification_service.py:33:    async def invalidate_active_verification_tokens(
processual_api/auth/email_verification_service.py:40:    def add_verification_delivery(self, **values) -> None: ...
processual_api/auth/email_verification_service.py:80:            raise ValueError("Email verification clock must be timezone-aware.")
processual_api/auth/email_verification_service.py:84:        token_hash = self._token_digester.digest(raw_token, purpose="verify_email")
processual_api/auth/email_verification_service.py:87:            principals = await unit_of_work.repository.verification_principals_for_update(
processual_api/auth/email_verification_service.py:97:                or user.status not in {"pending_verification", "active"}
processual_api/auth/email_verification_service.py:101:            if user.status == "pending_verification":
processual_api/auth/email_verification_service.py:110:        verification = self._token_digester.generate_token(purpose="verify_email")
processual_api/auth/email_verification_service.py:118:            latest = await unit_of_work.repository.latest_active_verification_token(user.id)
processual_api/auth/email_verification_service.py:122:                verification.raw,
processual_api/auth/email_verification_service.py:126:                purpose="verify_email",
processual_api/auth/email_verification_service.py:128:            await unit_of_work.repository.invalidate_active_verification_tokens(
processual_api/auth/email_verification_service.py:132:            unit_of_work.repository.add_verification_delivery(
processual_api/auth/email_verification_service.py:135:                action_token_hash=verification.digest,
processual_api/auth/mfa_router.py:97:async def _limit_verification(
processual_api/auth/mfa_router.py:174:    await _limit_verification(request, runtime, user_id=user_id)
processual_api/auth/mfa_router.py:202:    await _limit_verification(request, runtime, user_id=user_id)
processual_api/auth/mfa_router.py:234:        raise HTTPException(status_code=403, detail="Recent MFA verification required.") from exc
processual_api/auth/mfa_router.py:254:        raise HTTPException(status_code=403, detail="Recent MFA verification required.") from exc
processual_api/auth/mfa_service.py:163:            raise MfaStepUpRequiredError("Recent MFA verification is required.")
processual_api/auth/models.py:45:            "status IN ('pending_verification', 'active', 'locked', 'disabled', 'deleted')",
processual_api/auth/models.py:54:    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending_verification")
processual_api/auth/models.py:360:class AuthActionToken(Base):
processual_api/auth/models.py:365:            "'verify_email', "
processual_api/auth/models.py:445:    verification_token_hash: Mapped[str] = mapped_column(
processual_api/auth/models.py:488:            "event_type IN ('verify_email', 'verify_recovery_email', 'account_recovery_verification')",
processual_api/auth/models.py:545:    action_token: Mapped[AuthActionToken | None] = relationship()
processual_api/auth/models.py:626:    AuthActionToken,
processual_api/auth/recovery_email_router.py:35:from processual_api.auth.recovery_email_verification_service import (
processual_api/auth/recovery_email_router.py:164:    "/verification",
processual_api/auth/recovery_email_router.py:167:async def issue_recovery_email_verification(
processual_api/auth/recovery_email_router.py:240:async def resend_recovery_email_verification(
processual_api/auth/recovery_email_router.py:249:    return await issue_recovery_email_verification(
processual_api/auth/recovery_email_runtime.py:15:from processual_api.auth.recovery_email_verification_repository import (
processual_api/auth/recovery_email_runtime.py:18:from processual_api.auth.recovery_email_verification_service import (
processual_api/auth/recovery_email_verification_repository.py:11:    AuthActionToken,
processual_api/auth/recovery_email_verification_repository.py:61:    async def verification_principals_for_update(
processual_api/auth/recovery_email_verification_repository.py:66:        AuthActionToken,
processual_api/auth/recovery_email_verification_repository.py:71:                AuthActionToken,
processual_api/auth/recovery_email_verification_repository.py:77:                == AuthActionToken.user_id,
processual_api/auth/recovery_email_verification_repository.py:80:                AuthActionToken.token_hash == token_hash,
processual_api/auth/recovery_email_verification_repository.py:81:                AuthActionToken.purpose
processual_api/auth/recovery_email_verification_repository.py:98:                    select(AuthActionToken)
processual_api/auth/recovery_email_verification_repository.py:100:                        AuthActionToken.user_id == user_id,
processual_api/auth/recovery_email_verification_repository.py:101:                        AuthActionToken.purpose
processual_api/auth/recovery_email_verification_repository.py:103:                        AuthActionToken.consumed_at.is_(None),
processual_api/auth/recovery_email_verification_repository.py:115:    def add_verification(
processual_api/auth/recovery_email_verification_repository.py:126:    ) -> tuple[AuthActionToken, AuthDeliveryOutbox]:
processual_api/auth/recovery_email_verification_repository.py:127:        token = AuthActionToken(
processual_api/auth/recovery_email_verification_repository.py:193:                "Recovery-email verification unit of work "
processual_api/auth/recovery_email_verification_service.py:34:    async def verification_principals_for_update(
processual_api/auth/recovery_email_verification_service.py:47:    def add_verification(
processual_api/auth/recovery_email_verification_service.py:101:                "Recovery-email verification TTL must be positive."
processual_api/auth/recovery_email_verification_service.py:115:                "Recovery-email verification clock "
processual_api/auth/recovery_email_verification_service.py:137:        verification = self._token_digester.generate_token(
processual_api/auth/recovery_email_verification_service.py:173:                verification.raw,
processual_api/auth/recovery_email_verification_service.py:180:            repository.add_verification(
processual_api/auth/recovery_email_verification_service.py:184:                token_hash=verification.digest,
processual_api/auth/recovery_email_verification_service.py:215:                "Recovery-email verification is unavailable."
processual_api/auth/recovery_email_verification_service.py:221:                .verification_principals_for_update(
processual_api/auth/recovery_email_verification_service.py:228:                    "Recovery-email verification is unavailable."
processual_api/auth/recovery_email_verification_service.py:240:                    "Recovery-email verification is unavailable."
processual_api/auth/registration_contracts.py:25:    PENDING_VERIFICATION = "pending_verification"
processual_api/auth/registration_contracts.py:42:    VERIFY_EMAIL = "verify_email"
processual_api/auth/registration_contracts.py:96:    email_verification_required: bool = True
processual_api/auth/registration_contracts.py:128:    email_verification_required: bool = True
processual_api/auth/registration_contracts.py:166:            "email_verification_required": self.email_verification_required,
processual_api/auth/registration_repository.py:12:    AuthActionToken,
processual_api/auth/registration_repository.py:29:        self._pending_action_tokens: dict[uuid.UUID, AuthActionToken] = {}
processual_api/auth/registration_repository.py:35:    async def verification_principals_for_update(
processual_api/auth/registration_repository.py:38:    ) -> tuple[AuthActionToken, IdentityUser] | None:
processual_api/auth/registration_repository.py:40:            select(AuthActionToken, IdentityUser)
processual_api/auth/registration_repository.py:41:            .join(IdentityUser, IdentityUser.id == AuthActionToken.user_id)
processual_api/auth/registration_repository.py:43:                AuthActionToken.token_hash == token_hash,
processual_api/auth/registration_repository.py:44:                AuthActionToken.purpose == "verify_email",
processual_api/auth/registration_repository.py:56:                IdentityUser.status == "pending_verification",
processual_api/auth/registration_repository.py:62:    async def latest_active_verification_token(
processual_api/auth/registration_repository.py:65:    ) -> AuthActionToken | None:
processual_api/auth/registration_repository.py:67:            select(AuthActionToken)
processual_api/auth/registration_repository.py:69:                AuthActionToken.user_id == user_id,
processual_api/auth/registration_repository.py:70:                AuthActionToken.purpose == "verify_email",
processual_api/auth/registration_repository.py:71:                AuthActionToken.consumed_at.is_(None),
processual_api/auth/registration_repository.py:72:                AuthActionToken.invalidated_at.is_(None),
processual_api/auth/registration_repository.py:74:            .order_by(AuthActionToken.created_at.desc())
processual_api/auth/registration_repository.py:79:    async def invalidate_active_verification_tokens(
processual_api/auth/registration_repository.py:86:            update(AuthActionToken)
processual_api/auth/registration_repository.py:88:                AuthActionToken.user_id == user_id,
processual_api/auth/registration_repository.py:89:                AuthActionToken.purpose == "verify_email",
processual_api/auth/registration_repository.py:90:                AuthActionToken.consumed_at.is_(None),
processual_api/auth/registration_repository.py:91:                AuthActionToken.invalidated_at.is_(None),
processual_api/auth/registration_repository.py:97:    def add_verification_delivery(
processual_api/auth/registration_repository.py:109:        action_token = AuthActionToken(
processual_api/auth/registration_repository.py:112:            purpose="verify_email",
processual_api/auth/registration_repository.py:123:                event_type="verify_email",
processual_api/auth/registration_repository.py:154:            status="pending_verification",
processual_api/auth/registration_repository.py:167:        action_token = AuthActionToken(
processual_api/auth/registration_repository.py:170:            purpose="verify_email",
processual_api/auth/registration_router.py:99:def _verification_audit(request: Request, *, action: str, result: str) -> None:
processual_api/auth/registration_router.py:101:        "identity_email_verification",
processual_api/auth/registration_router.py:104:            "verification_action": action,
processual_api/auth/registration_router.py:105:            "verification_result": result,
processual_api/auth/registration_router.py:257:    "/verify-email",
processual_api/auth/registration_router.py:260:async def verify_email(
processual_api/auth/registration_router.py:269:            action="verify_email",
processual_api/auth/registration_router.py:274:        _verification_audit(request, action="verify", result="authority_unavailable")
processual_api/auth/registration_router.py:278:        _verification_audit(request, action="verify", result="limited")
processual_api/auth/registration_router.py:284:    verification_service = runtime.email_verification_service
processual_api/auth/registration_router.py:285:    if verification_service is None:
processual_api/auth/registration_router.py:286:        _verification_audit(request, action="verify", result="authority_unavailable")
processual_api/auth/registration_router.py:289:        await verification_service.verify(payload.token)
processual_api/auth/registration_router.py:292:            "identity_email_verification_authority_failed",
processual_api/auth/registration_router.py:295:        _verification_audit(request, action="verify", result="authority_unavailable")
processual_api/auth/registration_router.py:298:    _verification_audit(request, action="verify", result="processed")
processual_api/auth/registration_router.py:303:    "/verification/resend",
processual_api/auth/registration_router.py:307:async def resend_email_verification(
processual_api/auth/registration_router.py:317:            action="resend_email_verification",
processual_api/auth/registration_router.py:322:        _verification_audit(request, action="resend", result="authority_unavailable")
processual_api/auth/registration_router.py:326:        _verification_audit(request, action="resend", result="ip_limited")
processual_api/auth/registration_router.py:335:            action="resend_email_verification",
processual_api/auth/registration_router.py:341:        _verification_audit(request, action="resend", result="accepted")
processual_api/auth/registration_router.py:344:        _verification_audit(request, action="resend", result="authority_unavailable")
processual_api/auth/registration_router.py:348:        _verification_audit(request, action="resend", result="accepted")
processual_api/auth/registration_router.py:350:    verification_service = runtime.email_verification_service
processual_api/auth/registration_router.py:351:    if verification_service is None:
processual_api/auth/registration_router.py:352:        _verification_audit(request, action="resend", result="authority_unavailable")
processual_api/auth/registration_router.py:355:        await verification_service.resend(normalized_email)
processual_api/auth/registration_router.py:358:            "identity_email_verification_resend_authority_failed",
processual_api/auth/registration_router.py:361:        _verification_audit(request, action="resend", result="authority_unavailable")
processual_api/auth/registration_router.py:364:    _verification_audit(request, action="resend", result="accepted")
processual_api/auth/registration_runtime.py:9:from processual_api.auth.email_verification_service import EmailVerificationService
processual_api/auth/registration_runtime.py:30:    email_verification_service: EmailVerificationService | None = None
processual_api/auth/registration_runtime.py:104:        email_verification_service=EmailVerificationService(
processual_api/auth/registration_service.py:107:        verification = self._token_digester.generate_token(purpose="verify_email")
processual_api/auth/registration_service.py:117:            verification.raw,
processual_api/auth/registration_service.py:121:            purpose="verify_email",
processual_api/auth/registration_service.py:136:                    action_token_hash=verification.digest,
processual_api/auth/registration_service.py:146:                    event_type="verify_email",
processual_api/auth/security.py:525:                detail="Recent MFA verification required.",
processual_api/auth/security.py:616:                detail="Recent MFA verification required.",
processual_api/auth/session_service.py:117:            verification = self._password_service.verify_password(user.password_hash, password)
processual_api/auth/session_service.py:120:            if not verification.valid or not eligible:
processual_api/auth/session_service.py:121:                if not verification.valid and not locked:
processual_api/auth/session_service.py:128:            if verification.needs_rehash:
processual_api/billing/commercial_settings_top_up_checkout_contracts.py:52:    VERIFICATION_PENDING = "verification_pending"
processual_api/billing/commercial_top_up_application_service.py:77:    payment_verification_enabled: bool = PAYMENT_VERIFICATION_ENABLED
processual_api/billing/commercial_top_up_application_service.py:332:            self._policy.payment_verification_enabled,
processual_api/billing/commercial_top_up_application_service.py:333:            "top-up payment verification is disabled",
processual_api/billing/commercial_top_up_application_service.py:580:        "payment_verification_enabled": (policy.payment_verification_enabled),
processual_api/billing/commercial_top_up_order_grant_contracts.py:1:"""Order, payment verification, and idempotent unit-grant contracts.
processual_api/billing/commercial_top_up_order_grant_contracts.py:123:            raise ValueError("units cannot be granted before payment verification")
processual_api/billing/commercial_top_up_order_grant_contracts.py:299:        "payment_verification_enabled": PAYMENT_VERIFICATION_ENABLED,
processual_api/billing/maestro_calibration_contracts.py:29:    VERIFICATION_REVIEW = "verification_review"
processual_api/billing/maestro_calibration_contracts.py:71:    verification_items: Decimal = ZERO
processual_api/billing/maestro_group1_pricing_review.py:54:    "verification_items": Decimal("0.04"),
processual_api/billing/maestro_reference_workloads.py:23:        "verification_items": "0",
processual_api/billing/maestro_reference_workloads.py:72:        _q(base_executions="1", integration_actions="4", verification_items="25"),
processual_api/billing/maestro_reference_workloads.py:83:            verification_items="75",
processual_api/billing/maestro_reference_workloads.py:247:        "Ten verification items",
processual_api/billing/maestro_reference_workloads.py:249:        _q(verification_items="10"),
processual_api/billing/maestro_reference_workloads.py:255:        "Twenty-five verification items",
processual_api/billing/maestro_reference_workloads.py:257:        _q(verification_items="25"),
processual_api/billing/maestro_reference_workloads.py:263:        "Two hundred fifty verification items",
processual_api/billing/maestro_reference_workloads.py:265:        _q(verification_items="250"),
processual_api/billing/maestro_reference_workloads.py:271:        "Execution with fifty verifications",
processual_api/billing/maestro_reference_workloads.py:273:        _q(base_executions="1", verification_items="50"),
processual_api/billing/maestro_reference_workloads.py:327:            verification_items="50",
processual_api/billing/maestro_reference_workloads.py:341:            verification_items="50",
processual_api/cgt_governor/types.py:85:        "description": "Fails to carry the required meaning. Regenerate or use a verification tool.",
processual_api/main.py:182:_verify_email_page_path = _static_dir / "verify-email.html"
processual_api/main.py:223:@app.get("/verify-email", response_class=HTMLResponse, include_in_schema=False)
processual_api/main.py:224:async def email_verification_page() -> HTMLResponse:
processual_api/main.py:225:    if not _verify_email_page_path.exists():
processual_api/main.py:227:            "<h1>Email verification page unavailable</h1>",
processual_api/main.py:230:    return HTMLResponse(_verify_email_page_path.read_text("utf-8"))
processual_api/middleware/rate_limit.py:15:    "/auth/verify-email",
processual_api/middleware/rate_limit.py:16:    "/auth/verification/resend",
processual_api/middleware/subscription.py:36:    "/auth/verify-email",
processual_api/middleware/subscription.py:37:    "/auth/verification/resend",
processual_api/services/operator_pilot_handoff.py:138:            "document_verification",
processual_api/static/js/admin_operator_pilot_handoff.js:61:          "Document verification",
processual_api/static/js/pages/register.js:156:          window.location.assign(`/verify-email?email=${email}`);
processual_api/static/js/pages/verify-email.js:3:(function verificationController() {
processual_api/static/js/pages/verify-email.js:4:  const status = document.getElementById("verification-status");
processual_api/static/js/pages/verify-email.js:5:  const resendForm = document.getElementById("verification-resend-form");
processual_api/static/js/pages/verify-email.js:6:  const resendButton = document.getElementById("verification-resend-button");
processual_api/static/js/pages/verify-email.js:7:  const emailInput = document.getElementById("verification-email");
processual_api/static/js/pages/verify-email.js:16:      .querySelectorAll("[data-verification-state]")
processual_api/static/js/pages/verify-email.js:19:          section.dataset.verificationState === name ? "true" : "false";
processual_api/static/js/pages/verify-email.js:27:    showState("processing", "Processing the verification request...");
processual_api/static/js/pages/verify-email.js:30:      const response = await fetch("/auth/verify-email", {
processual_api/static/js/pages/verify-email.js:57:        showState("invalid", "The verification request could not be processed.");
processual_api/static/js/pages/verify-email.js:92:    status.textContent = "Requesting another verification email...";
processual_api/static/js/pages/verify-email.js:95:      const response = await fetch("/auth/verification/resend", {
processual_api/static/js/pages/verify-email.js:110:          "Please wait before requesting another verification email.",
processual_api/static/js/pages/verify-email.js:130:        "Request accepted. Check your email for the verification link.",
processual_api/static/js/pages/verify-email.js:156:      "Waiting for a verification link. You may request another email below.",
processual_api/static/js/tour/tour-steps.js:72:      title: 'Report Detail', content: 'Detailed view of the selected report including evidence pack with integrity verification and SHA3 checksum.', position: 'top' },
processual_api/static/verify-email.html:105:    <h1>Email verification</h1>
processual_api/static/verify-email.html:109:      data-verification-state="pending"
processual_api/static/verify-email.html:113:      <p>Open the verification link sent to your address.</p>
processual_api/static/verify-email.html:118:      data-verification-state="processing"
processual_api/static/verify-email.html:122:      <p>Your verification request is being processed.</p>
processual_api/static/verify-email.html:127:      data-verification-state="verified"
processual_api/static/verify-email.html:136:      data-verification-state="invalid"
processual_api/static/verify-email.html:139:      <h2>Invalid verification request</h2>
processual_api/static/verify-email.html:140:      <p>The verification link could not be used.</p>
processual_api/static/verify-email.html:145:      data-verification-state="expired"
processual_api/static/verify-email.html:149:      <p>Request another verification email below.</p>
processual_api/static/verify-email.html:154:      data-verification-state="already-used"
processual_api/static/verify-email.html:163:      data-verification-state="rate-limited"
processual_api/static/verify-email.html:167:      <p>Too many verification attempts were received.</p>
processual_api/static/verify-email.html:172:      data-verification-state="unavailable"
processual_api/static/verify-email.html:176:      <p>Email verification is temporarily unavailable.</p>
processual_api/static/verify-email.html:179:    <form id="verification-resend-form" novalidate>
processual_api/static/verify-email.html:180:      <label for="verification-email">Email address</label>
processual_api/static/verify-email.html:182:        id="verification-email"
processual_api/static/verify-email.html:190:      <button id="verification-resend-button" type="submit">
processual_api/static/verify-email.html:191:        Resend verification email
processual_api/static/verify-email.html:196:      id="verification-status"
processual_api/static/verify-email.html:201:      Waiting for a verification link.
processual_api/static/verify-email.html:210:  <script src="/console/js/pages/verify-email.js"></script>
tests/integration/test_auth_delivery_dispatcher_r6b_integration.py:18:from processual_api.auth.models import AuthActionToken, AuthDeliveryOutbox, IdentityUser
tests/integration/test_auth_delivery_dispatcher_r6b_integration.py:32:    async def send_verification_email(self, **values: str) -> None:
tests/integration/test_auth_delivery_dispatcher_r6b_integration.py:49:        "integration-verification-token",
tests/integration/test_auth_delivery_dispatcher_r6b_integration.py:53:        purpose="verify_email",
tests/integration/test_auth_delivery_dispatcher_r6b_integration.py:71:            status="pending_verification",
tests/integration/test_auth_delivery_dispatcher_r6b_integration.py:73:        action_token = AuthActionToken(
tests/integration/test_auth_delivery_dispatcher_r6b_integration.py:76:            purpose="verify_email",
tests/integration/test_auth_delivery_dispatcher_r6b_integration.py:89:                    event_type="verify_email",
tests/integration/test_auth_delivery_multi_worker_concurrency_r9d_integration.py:25:    AuthActionToken,
tests/integration/test_auth_delivery_multi_worker_concurrency_r9d_integration.py:53:    async def send_verification_email(
tests/integration/test_auth_delivery_multi_worker_concurrency_r9d_integration.py:128:        status="pending_verification",
tests/integration/test_auth_delivery_multi_worker_concurrency_r9d_integration.py:144:            purpose="verify_email",
tests/integration/test_auth_delivery_multi_worker_concurrency_r9d_integration.py:147:        action_token = AuthActionToken(
tests/integration/test_auth_delivery_multi_worker_concurrency_r9d_integration.py:150:            purpose="verify_email",
tests/integration/test_auth_delivery_multi_worker_concurrency_r9d_integration.py:162:            event_type="verify_email",
tests/integration/test_auth_email_verification_r6a_integration.py:22:from processual_api.auth.models import AuthActionToken, AuthDeliveryOutbox, IdentityUser
tests/integration/test_auth_email_verification_r6a_integration.py:45:        purpose="verify_email",
tests/integration/test_auth_email_verification_r6a_integration.py:104:                    select(AuthActionToken).where(AuthActionToken.user_id == user.id)
tests/integration/test_auth_email_verification_r6a_integration.py:116:                "/auth/verification/resend",
tests/integration/test_auth_email_verification_r6a_integration.py:126:                            select(AuthActionToken)
tests/integration/test_auth_email_verification_r6a_integration.py:127:                            .where(AuthActionToken.user_id == user.id)
tests/integration/test_auth_email_verification_r6a_integration.py:128:                            .order_by(AuthActionToken.created_at)
tests/integration/test_auth_email_verification_r6a_integration.py:143:                "/auth/verify-email",
tests/integration/test_auth_email_verification_r6a_integration.py:147:                "/auth/verify-email",
tests/integration/test_auth_email_verification_r6a_integration.py:151:                "/auth/verify-email",
tests/integration/test_auth_email_verification_r6a_integration.py:159:                replacement = await session.get(AuthActionToken, tokens[1].id)
tests/integration/test_auth_recovery_email_delivery_r8d_integration.py:26:    AuthActionToken,
tests/integration/test_auth_recovery_email_delivery_r8d_integration.py:50:    async def send_verification_email(
tests/integration/test_auth_recovery_email_delivery_r8d_integration.py:116:        action_token = AuthActionToken(
tests/integration/test_auth_recovery_email_delivery_r8d_integration.py:179:            "verification_url"
tests/integration/test_auth_recovery_email_e2e_r8d_integration.py:28:    AuthActionToken,
tests/integration/test_auth_recovery_email_e2e_r8d_integration.py:46:from processual_api.auth.recovery_email_verification_repository import (
tests/integration/test_auth_recovery_email_e2e_r8d_integration.py:49:from processual_api.auth.recovery_email_verification_service import (
tests/integration/test_auth_recovery_email_e2e_r8d_integration.py:95:    async def send_verification_email(
tests/integration/test_auth_recovery_email_e2e_r8d_integration.py:266:                "/auth/recovery-email/verification"
tests/integration/test_auth_recovery_email_e2e_r8d_integration.py:281:                    select(AuthActionToken)
tests/integration/test_auth_recovery_email_e2e_r8d_integration.py:283:                        AuthActionToken.user_id
tests/integration/test_auth_recovery_email_e2e_r8d_integration.py:285:                        AuthActionToken.purpose
tests/integration/test_auth_recovery_email_e2e_r8d_integration.py:343:                            select(AuthActionToken)
tests/integration/test_auth_recovery_email_e2e_r8d_integration.py:345:                                AuthActionToken.user_id
tests/integration/test_auth_recovery_email_e2e_r8d_integration.py:347:                                AuthActionToken.purpose
tests/integration/test_auth_recovery_email_e2e_r8d_integration.py:450:                "verification_url"
tests/integration/test_auth_recovery_email_e2e_r8d_integration.py:457:                    "verification_url"
tests/integration/test_auth_recovery_email_e2e_r8d_integration.py:462:                    "verification_url"
tests/integration/test_auth_recovery_email_e2e_r8d_integration.py:574:                        AuthActionToken,
tests/integration/test_auth_registration_http_r5b_r1_integration.py:22:    AuthActionToken,
tests/integration/test_auth_registration_http_r5b_r1_integration.py:116:                    select(IdentityUser, AuthActionToken, AuthDeliveryOutbox)
tests/integration/test_auth_registration_http_r5b_r1_integration.py:117:                    .join(AuthActionToken, AuthActionToken.user_id == IdentityUser.id)
tests/integration/test_auth_registration_http_r5b_r1_integration.py:135:                purpose="verify_email",
tests/integration/test_auth_registration_http_r5b_r1_integration.py:140:                purpose="verify_email",
tests/test_admin_marketplace_integrity_translation_r3.py:96:        ("uq_admin_market_payment_verifications_verification_ref"),
tests/test_admin_marketplace_migration_r2.py:20:    "admin_market_payment_verifications",
tests/test_admin_marketplace_migration_r2.py:105:        "awaiting_payment_verification",
tests/test_admin_marketplace_migration_r2.py:127:        "ix_admin_market_payment_verifications_order_status",
tests/test_admin_marketplace_models_r2.py:31:    "admin_market_payment_verifications",
tests/test_admin_marketplace_models_r2.py:95:        "awaiting_payment_verification" in expression and "fulfilled" in expression for expression in order_checks
tests/test_admin_marketplace_models_r2.py:114:def test_payment_verification_has_no_raw_evidence() -> None:
tests/test_admin_marketplace_payment_repositories_r3.py:59:        "admin_market_payment_verifications",
tests/test_admin_marketplace_unit_of_work_r3.py:87:            unit_of_work.payment_verifications,
tests/test_admin_marketplace_unit_of_work_r3.py:130:            unit_of_work.payment_verifications,
tests/test_auth_account_recovery_delivery_crypto_r9a.py:22:        "purpose": "account_recovery_verification",
tests/test_auth_account_recovery_delivery_crypto_r9a.py:48:        purpose="account_recovery_verification",
tests/test_auth_account_recovery_delivery_crypto_r9a.py:60:            purpose="account_recovery_verification",
tests/test_auth_account_recovery_delivery_crypto_r9a.py:88:            purpose="verify_email",
tests/test_auth_account_recovery_delivery_crypto_r9a.py:100:        "purpose": "verify_email",
tests/test_auth_account_recovery_delivery_migration_r9a.py:21:    assert "account_recovery_verification" in source
tests/test_auth_account_recovery_delivery_migration_r9a.py:33:        "account_recovery_verification"
tests/test_auth_account_recovery_delivery_models_r9a.py:20:    assert "account_recovery_verification" in combined
tests/test_auth_account_recovery_http_r9a.py:83:            raise AccountRecoveryDeniedError("private verification detail")
tests/test_auth_account_recovery_http_r9a.py:289:            "token": "raw-verification-token",
tests/test_auth_account_recovery_http_r9a.py:310:            "raw_token": "raw-verification-token",
tests/test_auth_account_recovery_http_r9a.py:330:    assert response.json() == {"detail": "Account recovery verification is unavailable."}
tests/test_auth_account_recovery_migration_r9a.py:53:    assert "verification_token_hash" in sql
tests/test_auth_account_recovery_migration_r9a.py:64:        "\n\tverification_token ",
tests/test_auth_account_recovery_models_r9a.py:42:        "verification_token_hash",
tests/test_auth_account_recovery_models_r9a.py:53:    assert columns["verification_token_hash"].nullable is False
tests/test_auth_account_recovery_models_r9a.py:64:        "verification_token",
tests/test_auth_account_recovery_models_r9a.py:78:    assert "verification_token_hash" in column_names
tests/test_auth_account_recovery_models_r9a.py:103:    assert ("verification_token_hash",) in unique_columns
tests/test_auth_account_recovery_models_r9a.py:168:        verification_token_hash="a" * 64,
tests/test_auth_account_recovery_models_r9a.py:174:    assert request.verification_token_hash == "a" * 64
tests/test_auth_account_recovery_repository_r9a.py:52:        verification_token_hash="digest-only",
tests/test_auth_account_recovery_repository_r9a.py:68:    assert request.verification_token_hash == ("digest-only")
tests/test_auth_account_recovery_repository_r9a.py:72:    assert outbox.event_type == ("account_recovery_verification")
tests/test_auth_account_recovery_service_r9a.py:120:            verification_token_hash=(values["verification_token_hash"]),
tests/test_auth_account_recovery_service_r9a.py:136:            event_type=("account_recovery_verification"),
tests/test_auth_account_recovery_service_r9a.py:298:        verification_token_hash=(token_hash or (ACCOUNT_RECOVERY_VERIFICATION_TOKEN_PURPOSE + "-digest-1")),
tests/test_auth_account_recovery_service_r9a.py:475:    assert request.verification_token_hash == (ACCOUNT_RECOVERY_VERIFICATION_TOKEN_PURPOSE + "-digest-1")
tests/test_auth_account_recovery_service_r9a.py:476:    assert "verification-token" not in repr(request)
tests/test_auth_account_recovery_service_r9a.py:481:    assert outbox.event_type == ("account_recovery_verification")
tests/test_auth_account_recovery_service_r9a.py:483:    assert b"verification-token" not in (outbox.payload_ciphertext)
tests/test_auth_account_recovery_service_r9a.py:651:            verification_ttl=timedelta(0),
tests/test_auth_account_recovery_service_r9a.py:707:    verification_fields = {field.name for field in fields(AccountRecoveryVerificationReceipt)}
tests/test_auth_account_recovery_service_r9a.py:713:    assert "session" not in verification_fields
tests/test_auth_account_recovery_service_r9a.py:714:    assert "access_token" not in verification_fields
tests/test_auth_account_recovery_service_r9a.py:715:    assert "refresh_token" not in verification_fields
tests/test_auth_account_recovery_service_r9a.py:716:    assert "completion_token" in verification_fields
tests/test_auth_delivery_crypto_r5b.py:14:    "purpose": "verify_email",
tests/test_auth_delivery_crypto_r5b.py:24:    first = cipher.encrypt("opaque-verification-token", **AUTHORITY)
tests/test_auth_delivery_crypto_r5b.py:25:    second = cipher.encrypt("opaque-verification-token", **AUTHORITY)
tests/test_auth_delivery_crypto_r5b.py:29:    assert b"opaque-verification-token" not in first.ciphertext
tests/test_auth_delivery_crypto_r5b.py:30:    assert cipher.decrypt(first, **AUTHORITY) == "opaque-verification-token"
tests/test_auth_delivery_crypto_r5b.py:47:    encrypted = cipher.encrypt("opaque-verification-token", **AUTHORITY)
tests/test_auth_delivery_dispatcher_migration_r6b.py:4:def test_dispatcher_migration_extends_email_verification_head():
tests/test_auth_delivery_dispatcher_r6b.py:53:    async def send_verification_email(self, **values):
tests/test_auth_delivery_dispatcher_r6b.py:67:    async def send_verification_email(self, **values):
tests/test_auth_delivery_dispatcher_r6b.py:85:def _claim(*, now, attempt_count=1, user_status="pending_verification", consumed=None, invalidated=None):
tests/test_auth_delivery_dispatcher_r6b.py:91:        "raw-verification-token",
tests/test_auth_delivery_dispatcher_r6b.py:95:        purpose="verify_email",
tests/test_auth_delivery_dispatcher_r6b.py:104:        event_type="verify_email",
tests/test_auth_delivery_dispatcher_r6b.py:133:        purpose="account_recovery_verification",
tests/test_auth_delivery_dispatcher_r6b.py:143:        event_type="account_recovery_verification",
tests/test_auth_delivery_dispatcher_r6b.py:185:    assert provider.calls[0]["verification_url"].startswith("https://accounts.example.test/verify-email?token=")
tests/test_auth_delivery_dispatcher_r6b.py:211:    assert call["template"] == ("account_recovery_verification")
tests/test_auth_delivery_dispatcher_r6b.py:213:    assert call["verification_url"].startswith("https://accounts.example.test/auth/account-recovery/verify?token=")
tests/test_auth_delivery_dispatcher_r6b.py:214:    assert "raw-account-recovery-token" in (call["verification_url"])
tests/test_auth_delivery_dispatcher_r6b.py:332:    assert "raw-verification-token" not in repr(result)
tests/test_auth_delivery_dispatcher_r6b.py:351:        "raw-verification-token "
tests/test_auth_delivery_dispatcher_r6b.py:410:    assert "raw-verification-token" not in log_text
tests/test_auth_delivery_outbox_migration_r5b.py:63:def test_email_verification_revision_extends_delivery_outbox_head() -> None:
tests/test_auth_delivery_outbox_migration_r5b.py:64:    source = Path("alembic/versions/20260722_0004_auth_email_verification_lifecycle.py").read_text(encoding="utf-8")
tests/test_auth_delivery_provider_r9b.py:77:    return provider.send_verification_email(
tests/test_auth_delivery_provider_r9b.py:78:        template="account_recovery_verification",
tests/test_auth_delivery_provider_r9b.py:80:        verification_url=(
tests/test_auth_delivery_provider_r9b.py:126:        "template": "account_recovery_verification",
tests/test_auth_delivery_provider_r9b.py:128:        "verification_url": (
tests/test_auth_delivery_provider_r9b.py:252:            provider.send_verification_email(
tests/test_auth_delivery_provider_r9b.py:255:                verification_url=(
tests/test_auth_delivery_repository_account_recovery_r9a.py:85:        event_type="account_recovery_verification",
tests/test_auth_delivery_repository_account_recovery_r9a.py:141:    assert claim.event_type == ("account_recovery_verification")
tests/test_auth_delivery_repository_account_recovery_r9a.py:169:        event_type="verify_email",
tests/test_auth_delivery_repository_account_recovery_r9a.py:182:        status="pending_verification",
tests/test_auth_email_verification_migration_r6a.py:4:def test_email_verification_migration_extends_delivery_outbox_head():
tests/test_auth_email_verification_migration_r6a.py:6:        "alembic/versions/20260722_0004_auth_email_verification_lifecycle.py"
tests/test_auth_email_verification_r6a.py:8:from processual_api.auth.email_verification_service import (
tests/test_auth_email_verification_r6a.py:23:    async def verification_principals_for_update(self, token_hash):
tests/test_auth_email_verification_r6a.py:31:    async def latest_active_verification_token(self, user_id):
tests/test_auth_email_verification_r6a.py:34:    async def invalidate_active_verification_tokens(self, user_id, *, invalidated_at):
tests/test_auth_email_verification_r6a.py:37:    def add_verification_delivery(self, **values):
tests/test_auth_email_verification_r6a.py:68:def test_valid_verification_consumes_once_and_activates_pending_user():
tests/test_auth_email_verification_r6a.py:71:    material = digester.generate_token(purpose="verify_email")
tests/test_auth_email_verification_r6a.py:72:    user = SimpleNamespace(status="pending_verification", email_verified_at=None)
tests/test_auth_email_verification_r6a.py:94:def test_expired_or_invalidated_verification_is_generic_and_has_no_write():
tests/test_auth_email_verification_r6a.py:97:    material = digester.generate_token(purpose="verify_email")
tests/test_auth_email_verification_r6a.py:98:    user = SimpleNamespace(status="pending_verification", email_verified_at=None)
tests/test_auth_email_verification_r6a.py:114:    assert user.status == "pending_verification"
tests/test_auth_platform_admin_step_up_r8d.py:194:    assert raised.value.detail == "Recent MFA verification required."
tests/test_auth_platform_admin_step_up_r8d.py:238:    assert raised.value.detail == "Recent MFA verification required."
tests/test_auth_platform_admin_step_up_r8d.py:293:    assert raised.value.detail == "Recent MFA verification required."
tests/test_auth_rate_limit_r5a.py:107:            action="verify_email",
tests/test_auth_rate_limit_r5a.py:113:def test_security_policy_defaults_cover_registration_resend_and_verification() -> None:
tests/test_auth_recovery_email_delivery_r8d.py:49:    async def send_verification_email(self, **values):
tests/test_auth_recovery_email_delivery_r8d.py:149:def test_primary_verification_contract_is_preserved():
tests/test_auth_recovery_email_delivery_r8d.py:151:        event_type="verify_email",
tests/test_auth_recovery_email_delivery_r8d.py:152:        purpose="verify_email",
tests/test_auth_recovery_email_delivery_r8d.py:153:        user_status="pending_verification",
tests/test_auth_recovery_email_delivery_r8d.py:168:    assert provider.calls[0]["template"] == "verify_email"
tests/test_auth_recovery_email_delivery_r8d.py:176:        "verification_url"
tests/test_auth_recovery_email_delivery_r8d.py:179:        "verify-email?token="
tests/test_auth_recovery_email_delivery_r8d.py:183:def test_recovery_verification_uses_recovery_contract():
tests/test_auth_recovery_email_delivery_r8d.py:209:        "verification_url"
tests/test_auth_recovery_email_delivery_r8d.py:222:            "pending_verification",
tests/test_auth_recovery_email_delivery_r8d.py:292:        provider.send_verification_email(
tests/test_auth_recovery_email_delivery_r8d.py:295:            verification_url=(
tests/test_auth_recovery_email_delivery_r8d.py:307:        "verification_url": (
tests/test_auth_recovery_email_delivery_r8d.py:323:            provider.send_verification_email(
tests/test_auth_recovery_email_delivery_r8d.py:326:                verification_url=(
tests/test_auth_recovery_email_http_r8d.py:99:        "/auth/recovery-email/verification"
tests/test_auth_recovery_email_http_r8d.py:113:        "/auth/recovery-email/verification"
tests/test_auth_recovery_email_verification_contract_r8d.py:5:    AuthActionToken,
tests/test_auth_recovery_email_verification_contract_r8d.py:10:def test_models_allow_recovery_email_verification_values():
tests/test_auth_recovery_email_verification_contract_r8d.py:13:        for constraint in AuthActionToken.__table__.constraints
tests/test_auth_recovery_email_verification_contract_r8d.py:34:        / "20260723_0008_recovery_email_verification_tokens.py",
tests/test_auth_recovery_email_verification_contract_r8d.py:38:        / "20260723_0008_recovery_email_verification_tokens.py",
tests/test_auth_recovery_email_verification_contract_r8d.py:78:        / "recovery_email_verification_repository.py"
tests/test_auth_recovery_email_verification_contract_r8d.py:85:        / "recovery_email_verification_service.py"
tests/test_auth_recovery_email_verification_contract_r8d.py:88:    assert "token_hash=verification.digest" in service_source
tests/test_auth_recovery_email_verification_service_r8d.py:13:from processual_api.auth.recovery_email_verification_service import (
tests/test_auth_recovery_email_verification_service_r8d.py:54:    async def verification_principals_for_update(
tests/test_auth_recovery_email_verification_service_r8d.py:83:    def add_verification(self, **values):
tests/test_auth_registration_http_r5b_r1.py:55:            raise RuntimeError("verification detail must stay private")
tests/test_auth_registration_http_r5b_r1.py:77:def _runtime(*, limiter=None, service=None, verification_service=None, floor=0.0) -> RegistrationRuntime:
tests/test_auth_registration_http_r5b_r1.py:83:        email_verification_service=verification_service or FakeVerificationService(),
tests/test_auth_registration_http_r5b_r1.py:204:        "email_verification_required": True,
tests/test_auth_registration_http_r5b_r1.py:237:def test_verify_email_is_rate_limited_and_returns_only_generic_processed():
tests/test_auth_registration_http_r5b_r1.py:239:    verification = FakeVerificationService()
tests/test_auth_registration_http_r5b_r1.py:241:        _runtime(limiter=limiter, verification_service=verification)
tests/test_auth_registration_http_r5b_r1.py:242:    ).post("/auth/verify-email", json={"token": "raw-secret-token"})
tests/test_auth_registration_http_r5b_r1.py:246:    assert verification.verified == ["raw-secret-token"]
tests/test_auth_registration_http_r5b_r1.py:250:def test_verify_email_replay_throttling_is_429_without_service_call():
tests/test_auth_registration_http_r5b_r1.py:252:    verification = FakeVerificationService()
tests/test_auth_registration_http_r5b_r1.py:254:        _runtime(limiter=limiter, verification_service=verification)
tests/test_auth_registration_http_r5b_r1.py:255:    ).post("/auth/verify-email", json={"token": "raw-secret-token"})
tests/test_auth_registration_http_r5b_r1.py:259:    assert verification.verified == []
tests/test_auth_registration_http_r5b_r1.py:265:    verification = FakeVerificationService()
tests/test_auth_registration_http_r5b_r1.py:267:        _runtime(limiter=limiter, verification_service=verification)
tests/test_auth_registration_http_r5b_r1.py:268:    ).post("/auth/verification/resend", json={"email": " Person@Example.COM "})
tests/test_auth_registration_http_r5b_r1.py:272:    assert verification.resent == ["person@example.com"]
tests/test_auth_registration_http_r5b_r1.py:283:    verification = FakeVerificationService()
tests/test_auth_registration_http_r5b_r1.py:285:        _runtime(limiter=limiter, verification_service=verification)
tests/test_auth_registration_http_r5b_r1.py:286:    ).post("/auth/verification/resend", json={"email": "person@example.com"})
tests/test_auth_registration_http_r5b_r1.py:290:    assert verification.resent == []
tests/test_auth_registration_http_r5b_r1.py:293:def test_verification_validation_does_not_reflect_token_or_authority_fields():
tests/test_auth_registration_http_r5b_r1.py:295:        "/auth/verify-email",
tests/test_auth_registration_repository_r4.py:11:    AuthActionToken,
tests/test_auth_registration_repository_r4.py:49:    action_token = next(item for item in added if isinstance(item, AuthActionToken))
tests/test_auth_registration_repository_r4.py:83:        event_type="verify_email",
tests/test_auth_registration_repository_r4.py:109:        status="pending_verification",
tests/test_auth_registration_repository_r4.py:113:    repository.add_verification_delivery(
tests/test_auth_registration_repository_r4.py:125:    action_token = next(item for item in added if isinstance(item, AuthActionToken))
tests/test_auth_registration_runtime_r5b_r1.py:48:    assert runtime.email_verification_service is not None
tests/test_auth_registration_service_r4.py:112:    assert queued["event_type"] == "verify_email"
tests/test_auth_registration_service_r4.py:124:        purpose="verify_email",
tests/test_auth_registration_service_r4.py:129:        purpose="verify_email",
tests/test_auth_session_service_r7.py:181:def test_unknown_login_runs_dummy_password_verification(monkeypatch):
tests/test_commercial_top_up_application_service_group2.py:155:        payment_verification_enabled=True,
tests/test_commercial_top_up_application_service_group2.py:368:        "payment_verification_enabled",
tests/test_identity_registration_contracts_r1.py:112:    assert contract.email_verification_required is True
tests/test_identity_registration_contracts_r1.py:132:        ("email_verification_required", False),
tests/test_integration_readiness_tracking_11n.py:85:def test_readiness_tracking_can_mark_case_sandbox_ready_only_after_verification():
tests/test_maestro_group1_pricing_review.py:54:    assert calculate_maestro_units(CalibrationQuantities(verification_items=Decimal("25"))).raw_units == Decimal(
tests/test_middleware_regression.py:94:        "/auth/verify-email",
tests/test_middleware_regression.py:95:        "/auth/verification/resend",
tests/test_middleware_regression.py:105:def test_email_verification_routes_are_public_subscription_paths():
tests/test_middleware_regression.py:107:        "/auth/verify-email",
tests/test_middleware_regression.py:108:        "/auth/verification/resend",
tests/test_registration_verification_ui_a3.py:11:def test_email_verification_page_is_available() -> None:
tests/test_registration_verification_ui_a3.py:14:    response = client.get("/verify-email")
tests/test_registration_verification_ui_a3.py:20:def test_email_verification_page_declares_distinct_states() -> None:
tests/test_registration_verification_ui_a3.py:21:    html = (STATIC / "verify-email.html").read_text(encoding="utf-8")
tests/test_registration_verification_ui_a3.py:33:        assert f'data-verification-state="{state}"' in html
tests/test_registration_verification_ui_a3.py:40:def test_email_verification_page_loads_controller() -> None:
tests/test_registration_verification_ui_a3.py:41:    html = (STATIC / "verify-email.html").read_text(encoding="utf-8")
tests/test_registration_verification_ui_a3.py:43:    assert "/console/js/pages/verify-email.js" in html
tests/test_registration_verification_ui_a3.py:46:def test_email_verification_controller_does_not_render_server_html() -> None:
tests/test_registration_verification_ui_a3.py:47:    javascript = (STATIC / "js" / "pages" / "verify-email.js").read_text(encoding="utf-8")
tests/test_registration_verification_ui_a3.py:50:    assert "verification" in javascript
tests/test_security_crypto_regression.py:102:def test_envelope_verification_reports_success_and_failure():

## Plan state references
processual_api/admin_marketplace/models.py:123:            "plan_id",
processual_api/admin_marketplace/models.py:133:    plan_id: Mapped[uuid.UUID] = mapped_column(
processual_api/admin_marketplace/models.py:224:    plan_id: Mapped[uuid.UUID] = mapped_column(
processual_api/admin_marketplace/models.py:292:    plan_id: Mapped[uuid.UUID] = mapped_column(
processual_api/admin_marketplace/persistence/protocols.py:27:        plan_id: uuid.UUID,
processual_api/admin_marketplace/persistence/repositories.py:33:        plan_id: uuid.UUID,
processual_api/admin_marketplace/persistence/repositories.py:37:            plan_id,
processual_api/auth/registration_contracts.py:140:    client_selected_plan_allowed: bool = False
processual_api/auth/registration_contracts.py:184:            "client_selected_plan_allowed": (self.client_selected_plan_allowed),
processual_api/auth/security.py:658:                    "plan_id": detail.get("plan_id", current_user.get("plan_id", "")),
processual_api/billing/maestro_group1_pricing_review.py:193:    plan_id: str
processual_api/billing/maestro_group1_pricing_review.py:208:        if not self.plan_id or not self.plan_id.strip():
processual_api/billing/maestro_group1_pricing_review.py:209:            raise PricingReviewValidationError("plan_id must not be blank")
processual_api/billing/maestro_group1_pricing_review.py:398:    plan_id: str,
processual_api/billing/maestro_group1_pricing_review.py:433:        plan_id=plan_id,
processual_api/billing/maestro_group1_pricing_review.py:449:        for plan_id, config in PLAN_REVIEW_CONFIG.items():
processual_api/billing/maestro_group1_pricing_review.py:453:                    plan_id,
processual_api/billing/maestro_group1_selected_pricing.py:78:    plan_id: str
processual_api/billing/maestro_group1_selected_pricing.py:94:        if not self.plan_id:
processual_api/billing/maestro_group1_selected_pricing.py:95:            raise PricingReviewValidationError("plan_id must not be blank")
processual_api/billing/maestro_group1_selected_pricing.py:134:def calculate_selected_plan_proposal(plan_id: str) -> SelectedPlanProposal:
processual_api/billing/maestro_group1_selected_pricing.py:135:    if plan_id not in PLAN_REVIEW_CONFIG:
processual_api/billing/maestro_group1_selected_pricing.py:136:        raise PricingReviewValidationError(f"unknown selected proposal plan: {plan_id}")
processual_api/billing/maestro_group1_selected_pricing.py:137:    if plan_id not in SELECTED_MONTHLY_PRICES:
processual_api/billing/maestro_group1_selected_pricing.py:138:        raise PricingReviewValidationError(f"selected monthly price missing for plan: {plan_id}")
processual_api/billing/maestro_group1_selected_pricing.py:139:    if plan_id not in SELECTED_OVERAGE_PRICES_PER_1000_UNITS:
processual_api/billing/maestro_group1_selected_pricing.py:140:        raise PricingReviewValidationError(f"selected overage price missing for plan: {plan_id}")
processual_api/billing/maestro_group1_selected_pricing.py:142:    allowance, value_band = PLAN_REVIEW_CONFIG[plan_id]
processual_api/billing/maestro_group1_selected_pricing.py:144:        plan_id,
processual_api/billing/maestro_group1_selected_pricing.py:150:    selected_monthly_price = SELECTED_MONTHLY_PRICES[plan_id]
processual_api/billing/maestro_group1_selected_pricing.py:156:        plan_id=plan_id,
processual_api/billing/maestro_group1_selected_pricing.py:162:        enterprise_volume_adjustment_percent=(ENTERPRISE_VOLUME_ADJUSTMENTS_PERCENT.get(plan_id, ZERO)),
processual_api/billing/maestro_group1_selected_pricing.py:165:        selected_overage_price_per_1000_units=(SELECTED_OVERAGE_PRICES_PER_1000_UNITS[plan_id]),
processual_api/billing/maestro_group1_selected_pricing.py:170:    proposals = [calculate_selected_plan_proposal(plan_id).to_dict() for plan_id in SELECTED_MONTHLY_PRICES]
processual_api/billing/offer_fulfillment_policy.py:97:    plan_id = str(offer.get("plan_id") or "").strip()
processual_api/billing/offer_fulfillment_policy.py:102:    if offer_id in ENTERPRISE_OFFER_IDS or plan_id in ENTERPRISE_PLAN_IDS:
processual_api/billing/offer_pricebook.py:45:        "plan_id": "starter",
processual_api/billing/offer_pricebook.py:58:        "plan_id": "starter",
processual_api/billing/offer_pricebook.py:68:        "plan_id": "starter",
processual_api/billing/offer_pricebook.py:78:        "plan_id": "business",
processual_api/billing/offer_pricebook.py:88:        "plan_id": "business",
processual_api/billing/offer_pricebook.py:98:        "plan_id": "enterprise_integration_starter",
processual_api/billing/offer_pricebook.py:111:        "plan_id": "enterprise_integration_starter",
processual_api/billing/offer_pricebook.py:121:        "plan_id": "enterprise_integration_starter",
processual_api/billing/offer_pricebook.py:131:        "plan_id": "enterprise",
processual_api/billing/offer_pricebook.py:153:    plan_id = str(offer_definition["plan_id"])
processual_api/billing/offer_pricebook.py:154:    plan = get_subscription_plan(plan_id)
processual_api/billing/offer_pricebook.py:155:    allowance = monthly_unit_allowance(plan_id)
processual_api/billing/offer_pricebook.py:158:        raise ValueError(f"Unknown subscription plan for offer: {plan_id}")
processual_api/billing/offer_pricebook.py:161:        raise ValueError(f"Unknown monthly unit allowance for offer plan: {plan_id}")
processual_api/billing/offer_pricebook.py:165:        "plan_id": plan_id,
processual_api/billing/public_plan_journey.py:63:def _public_price(plan_id: str) -> Decimal | None:
processual_api/billing/public_plan_journey.py:64:    plan_index = PUBLIC_PLAN_ORDER.index(plan_id)
processual_api/billing/public_plan_journey.py:70:    return SELECTED_MONTHLY_PRICES[plan_id]
processual_api/billing/public_plan_journey.py:73:def public_plan_journey_catalog() -> dict[str, Any]:
processual_api/billing/public_plan_journey.py:78:    for position, plan_id in enumerate(PUBLIC_PLAN_ORDER, start=1):
processual_api/billing/public_plan_journey.py:79:        monthly_price = _public_price(plan_id)
processual_api/billing/public_plan_journey.py:84:                "plan_id": plan_id,
processual_api/billing/public_plan_journey.py:85:                "display_name": PUBLIC_PLAN_NAMES[plan_id],
processual_api/billing/public_plan_journey.py:86:                "description": PUBLIC_PLAN_DESCRIPTIONS[plan_id],
processual_api/billing/public_plan_journey.py:110:    "public_plan_journey_catalog",
processual_api/billing/router.py:16:from processual_api.billing.public_plan_journey import public_plan_journey_catalog
processual_api/billing/router.py:361:async def get_public_plan_journey() -> dict[str, object]:
processual_api/billing/router.py:363:    return public_plan_journey_catalog()
processual_api/billing/subscription_catalog.py:30:        "plan_id": "developer",
processual_api/billing/subscription_catalog.py:42:        "plan_id": "internal",
processual_api/billing/subscription_catalog.py:54:        "plan_id": "pilot_starter",
processual_api/billing/subscription_catalog.py:66:        "plan_id": "starter",
processual_api/billing/subscription_catalog.py:78:        "plan_id": "business",
processual_api/billing/subscription_catalog.py:90:        "plan_id": "enterprise_integration_starter",
processual_api/billing/subscription_catalog.py:102:        "plan_id": "enterprise",
processual_api/billing/subscription_catalog.py:114:        "plan_id": "enterprise_integration",
processual_api/billing/subscription_catalog.py:129:    plan_id = str(plan_definition["plan_id"])
processual_api/billing/subscription_catalog.py:130:    allowance = monthly_unit_allowance(plan_id)
processual_api/billing/subscription_catalog.py:133:        raise ValueError(f"Unknown monthly unit allowance for subscription plan: {plan_id}")
processual_api/billing/subscription_catalog.py:136:        "plan_id": plan_id,
processual_api/billing/subscription_catalog.py:165:def get_subscription_plan(plan_id: str) -> dict[str, Any] | None:
processual_api/billing/subscription_catalog.py:168:    normalized_plan_id = str(plan_id or "").strip()
processual_api/billing/subscription_catalog.py:170:        if plan["plan_id"] == normalized_plan_id:
processual_api/billing/usage_pricing.py:81:def normalize_plan_id(plan_id: str | None) -> str:
processual_api/billing/usage_pricing.py:82:    return str(plan_id or "").strip().lower().replace(" ", "_")
processual_api/billing/usage_pricing.py:85:def monthly_unit_allowance(plan_id: str | None) -> int:
processual_api/billing/usage_pricing.py:86:    return PLAN_MONTHLY_UNIT_ALLOWANCES.get(normalize_plan_id(plan_id), 0)
processual_api/billing/usage_pricing.py:89:def allows_enterprise_integration(plan_id: str | None) -> bool:
processual_api/billing/usage_pricing.py:90:    return normalize_plan_id(plan_id) in ENTERPRISE_INTEGRATION_PLANS
processual_api/integrations/fake_sandbox_transport.py:262:    plan_id: str
processual_api/integrations/fake_sandbox_transport.py:302:            "plan_id",
processual_api/integrations/fake_sandbox_transport.py:569:    plan_id: str
processual_api/integrations/fake_sandbox_transport.py:602:            "plan_id",
processual_api/integrations/fake_sandbox_transport.py:874:            contract.plan_id
processual_api/integrations/fake_sandbox_transport.py:964:        if pilot.selected_plan_id != contract.plan_id:
processual_api/integrations/fake_sandbox_transport.py:1013:        if base_transport.plan_id != contract.plan_id:
processual_api/integrations/fake_sandbox_transport.py:1080:        plan_id=_SELECTED_PLAN_ID,
processual_api/integrations/fake_sandbox_transport.py:1181:            contract.plan_id
processual_api/integrations/fake_sandbox_transport.py:1329:        "plan_id",
processual_api/integrations/fake_sandbox_transport.py:1368:        plan_id=(
processual_api/integrations/fake_sandbox_transport.py:1371:            .plan_id
processual_api/integrations/fake_sandbox_transport.py:1473:        request_plan_id = (
processual_api/integrations/fake_sandbox_transport.py:1476:            .plan_id
processual_api/integrations/fake_sandbox_transport.py:1479:        if request_plan_id != contract.plan_id:
processual_api/integrations/mock_dispatcher.py:105:    plan_id: str
processual_api/integrations/mock_dispatcher.py:137:    plan_id: str
processual_api/integrations/mock_dispatcher.py:174:            "plan_id",
processual_api/integrations/mock_dispatcher.py:234:        "plan_id",
processual_api/integrations/mock_dispatcher.py:262:        plan_id=request.plan_id or "missing_plan_id",
processual_api/integrations/mock_dispatcher.py:300:        plan = CONNECTOR_OPERATION_PLANS.get(request.plan_id)
processual_api/integrations/mock_dispatcher.py:314:        if plan.plan_id != request.plan_id:
processual_api/integrations/operation_plans.py:53:    "plan_id",
processual_api/integrations/operation_plans.py:133:    plan_id: str
processual_api/integrations/operation_plans.py:149:        _validate_identifier(self.plan_id, "plan_id")
processual_api/integrations/operation_plans.py:180:    plan_id: str
processual_api/integrations/operation_plans.py:190:        _validate_identifier(self.plan_id, "plan_id")
processual_api/integrations/operation_plans.py:206:    plan_id: str
processual_api/integrations/operation_plans.py:231:        _validate_identifier(self.plan_id, "plan_id")
processual_api/integrations/operation_plans.py:311:def _plan_identifier(connector_id: str, environment: str, capability_id: str) -> str:
processual_api/integrations/operation_plans.py:316:def _build_steps(plan_id: str) -> tuple[ConnectorOperationStep, ...]:
processual_api/integrations/operation_plans.py:319:            step_id=f"{plan_id}_{order}_{step_kind}",
processual_api/integrations/operation_plans.py:343:            _plan_id = _plan_identifier(
processual_api/integrations/operation_plans.py:349:            _approval_id = f"{_plan_id}_approval_requirement"
processual_api/integrations/operation_plans.py:350:            _audit_id = f"{_plan_id}_audit_projection"
processual_api/integrations/operation_plans.py:355:                plan_id=_plan_id,
processual_api/integrations/operation_plans.py:364:                plan_id=_plan_id,
processual_api/integrations/operation_plans.py:365:                event_name=f"{_plan_id}_audit_event",
processual_api/integrations/operation_plans.py:368:            _OPERATION_PLANS[_plan_id] = ConnectorOperationPlan(
processual_api/integrations/operation_plans.py:369:                plan_id=_plan_id,
processual_api/integrations/operation_plans.py:378:                steps=_build_steps(_plan_id),
processual_api/integrations/operation_plans.py:412:def get_connector_operation_plan(plan_id: str) -> ConnectorOperationPlan:
processual_api/integrations/operation_plans.py:413:    normalized_id = _normalize_identifier(plan_id)
processual_api/integrations/operation_plans.py:417:        raise KeyError(f"Unsupported connector operation plan '{plan_id}'.") from exc
processual_api/integrations/operation_plans.py:451:    plan_ids = tuple(plan.plan_id for plan in plans)
processual_api/integrations/operation_plans.py:457:    if len(set(plan_ids)) != len(plan_ids):
processual_api/integrations/operation_plans.py:503:                f"Plan '{plan.plan_id}' references an unknown approval requirement."
processual_api/integrations/operation_plans.py:505:        elif approval.plan_id != plan.plan_id:
processual_api/integrations/operation_plans.py:507:                f"Plan '{plan.plan_id}' approval requirement links another plan."
processual_api/integrations/operation_plans.py:513:                f"Plan '{plan.plan_id}' references an unknown audit projection."
processual_api/integrations/operation_plans.py:515:        elif audit.plan_id != plan.plan_id:
processual_api/integrations/operation_plans.py:517:                f"Plan '{plan.plan_id}' audit projection links another plan."
processual_api/integrations/operation_plans.py:521:            issues.append(f"Plan '{plan.plan_id}' contains an executable step.")
processual_api/integrations/operation_plans.py:523:            issues.append(f"Plan '{plan.plan_id}' contains an HTTP-enabled step.")
processual_api/integrations/sandbox_evidence.py:323:    plan_id_reference: str
processual_api/integrations/sandbox_evidence.py:363:            "plan_id_reference",
processual_api/integrations/sandbox_evidence.py:906:        plan_id_reference = _safe_reference(
processual_api/integrations/sandbox_evidence.py:907:            "plan_id",
processual_api/integrations/sandbox_evidence.py:908:            result.plan_id,
processual_api/integrations/sandbox_evidence.py:940:        plan_id_reference = "plan_not_projected_reference"
processual_api/integrations/sandbox_evidence.py:1001:        plan_id_reference=plan_id_reference,
processual_api/integrations/sandbox_pilot.py:185:    candidate_plan_ids: tuple[str, ...]
processual_api/integrations/sandbox_pilot.py:186:    selected_plan_id: str
processual_api/integrations/sandbox_pilot.py:215:            "selected_plan_id",
processual_api/integrations/sandbox_pilot.py:225:            "candidate_plan_ids",
processual_api/integrations/sandbox_pilot.py:264:        if self.selected_plan_id not in self.candidate_plan_ids:
processual_api/integrations/sandbox_pilot.py:266:                "Selected plan must exist in candidate_plan_ids."
processual_api/integrations/sandbox_pilot.py:553:    selected_plan = CONNECTOR_OPERATION_PLANS.get(
processual_api/integrations/sandbox_pilot.py:554:        contract.selected_plan_id
processual_api/integrations/sandbox_pilot.py:634:    if selected_plan is None:
processual_api/integrations/sandbox_pilot.py:636:            f"{contract.pilot_id}:selected_plan_not_found"
processual_api/integrations/sandbox_pilot.py:639:        selected_plan,
processual_api/integrations/sandbox_pilot.py:644:            f"{contract.pilot_id}:selected_plan_not_safe"
processual_api/integrations/sandbox_pilot.py:647:    for candidate_plan_id in contract.candidate_plan_ids:
processual_api/integrations/sandbox_pilot.py:649:            candidate_plan_id
processual_api/integrations/sandbox_pilot.py:655:                f"{candidate_plan_id}"
processual_api/integrations/sandbox_pilot.py:666:                f"{candidate_plan_id}"
processual_api/integrations/sandbox_pilot.py:740:        candidate_plan_ids=_TICKETING_READ_CANDIDATE_PLAN_IDS,
processual_api/integrations/sandbox_pilot.py:741:        selected_plan_id=_SELECTED_OPERATION_PLAN_ID,
processual_api/integrations/sandbox_read_faults.py:836:    if dispatch_request.plan_id != workflow.plan_id:
processual_api/integrations/sandbox_read_workflow.py:235:    plan_id: str
processual_api/integrations/sandbox_read_workflow.py:277:            "plan_id",
processual_api/integrations/sandbox_read_workflow.py:448:    plan_id: str
processual_api/integrations/sandbox_read_workflow.py:482:            "plan_id",
processual_api/integrations/sandbox_read_workflow.py:726:        plan = get_connector_operation_plan(contract.plan_id)
processual_api/integrations/sandbox_read_workflow.py:745:            pilot.selected_plan_id == contract.plan_id
processual_api/integrations/sandbox_read_workflow.py:783:            and base.plan_id == contract.plan_id
processual_api/integrations/sandbox_read_workflow.py:811:            and fake.plan_id == contract.plan_id
processual_api/integrations/sandbox_read_workflow.py:860:    plan_id=_PLAN_ID,
processual_api/integrations/sandbox_read_workflow.py:999:    if dispatch_request.plan_id != contract.plan_id:
processual_api/integrations/sandbox_read_workflow.py:1100:        plan_id=(
processual_api/integrations/sandbox_read_workflow.py:1104:            .plan_id
processual_api/integrations/transport_contracts.py:210:    plan_id: str
processual_api/integrations/transport_contracts.py:245:            "plan_id",
processual_api/integrations/transport_contracts.py:491:    plan_id: str
processual_api/integrations/transport_contracts.py:515:            "plan_id",
processual_api/integrations/transport_contracts.py:717:            contract.plan_id
processual_api/integrations/transport_contracts.py:761:        if plan.plan_id != contract.plan_id:
processual_api/integrations/transport_contracts.py:763:                f"{contract.transport_id}:plan_id_mismatch"
processual_api/integrations/transport_contracts.py:792:        if pilot.selected_plan_id != contract.plan_id:
processual_api/integrations/transport_contracts.py:872:        plan_id=_SELECTED_PLAN_ID,
processual_api/integrations/transport_contracts.py:963:            contract.plan_id
processual_api/integrations/transport_contracts.py:1075:        "plan_id",
processual_api/integrations/transport_contracts.py:1111:        plan_id=request.dispatch_request.plan_id,
processual_api/integrations/transport_contracts.py:1180:        if request.dispatch_request.plan_id != (
processual_api/integrations/transport_contracts.py:1181:            contract.plan_id
processual_api/main.py:198:    "/offer/{plan_id}",
processual_api/main.py:202:async def offer_page(plan_id: str) -> HTMLResponse:
processual_api/main.py:203:    del plan_id
processual_api/middleware/usage_log.py:50:        "plan_id": quota.get("plan_id") or current_user.get("plan_id", ""),
processual_api/routers/client_api_keys_18.py:48:    plan_id = settings_module._resolve_client_api_key_integration_plan_id(
processual_api/routers/client_api_keys_18.py:53:    if not settings_module._allows_client_api_key_integration(plan_id):
processual_api/routers/client_api_keys_18.py:60:    return plan_id
processual_api/routers/client_api_keys_18.py:135:    plan_id: str,
processual_api/routers/client_api_keys_18.py:168:        "plan_id": plan_id,
processual_api/routers/client_api_keys_18.py:170:        "quota_limit": settings_module.quota_limit_for_plan(plan_id, "evaluation"),
processual_api/routers/client_api_keys_18.py:194:    plan_id = _eligible_plan(user_id, client_id, raw, current_user)
processual_api/routers/client_api_keys_18.py:198:        "plan_id": plan_id,
processual_api/routers/client_api_keys_18.py:216:    plan_id = _eligible_plan(user_id, client_id, raw, current_user)
processual_api/routers/client_api_keys_18.py:222:        plan_id=plan_id,
processual_api/routers/client_api_keys_18.py:247:    plan_id = _eligible_plan(user_id, client_id, raw, current_user)
processual_api/routers/client_api_keys_18.py:258:        plan_id=plan_id,
processual_api/routers/settings.py:31:    normalize_plan_id,
processual_api/routers/settings.py:50:from ..services.plan_store import PLAN_POLICIES, get_plan_policy, quota_limit_for_plan, resolve_plan_id
processual_api/routers/settings.py:207:    plan_id: str
processual_api/routers/settings.py:217:    plan_id: str | None = Field(default=None, min_length=1)
processual_api/routers/settings.py:1293:    for key in ("plan_id", "plan", "approved_plan"):
processual_api/routers/settings.py:1354:    plan_id, allowance = _supported_admin_direct_plan(requested_plan)
processual_api/routers/settings.py:1355:    if not plan_id or allowance <= 0:
processual_api/routers/settings.py:1373:        str(raw.get("approved_plan") or "").strip() == plan_id
processual_api/routers/settings.py:1376:        and str(existing_subscription.get("plan_id") or existing_subscription.get("plan") or "").strip()
processual_api/routers/settings.py:1377:        == plan_id
processual_api/routers/settings.py:1389:        subscription["plan_id"] = plan_id
processual_api/routers/settings.py:1390:        subscription["plan"] = plan_id
processual_api/routers/settings.py:1394:        raw["approved_plan"] = plan_id
processual_api/routers/settings.py:1405:                "plan_id": plan_id,
processual_api/routers/settings.py:1426:            "plan_id": plan_id,
processual_api/routers/settings.py:1437:            "plan_id": plan_id,
processual_api/routers/settings.py:1442:            "approved_plan": plan_id,
processual_api/routers/settings.py:1564:                    "plan_id": plan.get("plan_id"),
processual_api/routers/settings.py:2374:        "plan_id": key.get("plan_id"),
processual_api/routers/settings.py:2396:def _allows_client_api_key_integration(plan_id: str | None) -> bool:
processual_api/routers/settings.py:2397:    normalized = normalize_plan_id(plan_id)
processual_api/routers/settings.py:2424:def _resolve_client_api_key_integration_plan_id(
processual_api/routers/settings.py:2430:        current_user.get("plan_id"),
processual_api/routers/settings.py:2439:            latest.get("plan_id"),
processual_api/routers/settings.py:2446:            subscription.get("plan_id"),
processual_api/routers/settings.py:2451:        normalized = normalize_plan_id(str(candidate) if candidate is not None else None)
processual_api/routers/settings.py:2507:            "plan_id": key.get("plan_id"),
processual_api/routers/settings.py:2529:    plan_id = _resolve_client_api_key_integration_plan_id(
processual_api/routers/settings.py:2535:    enabled = _allows_client_api_key_integration(plan_id)
processual_api/routers/settings.py:2541:            "plan_id": plan_id,
processual_api/routers/settings.py:2556:        "plan_id": plan_id,
processual_api/routers/settings.py:2565:    return [get_plan_policy(plan_id) for plan_id in PLAN_POLICIES.keys()]
processual_api/routers/settings.py:2606:            "plan_id": key.get("plan_id"),
processual_api/routers/settings.py:2619:def _resolve_current_plan_id(user_id: str, raw: dict) -> str:
processual_api/routers/settings.py:2624:        return resolve_plan_id(latest.get("plan_id") or latest.get("plan"))
processual_api/routers/settings.py:2627:    return resolve_plan_id(subscription.get("plan_id") or subscription.get("plan", "Starter"))
processual_api/routers/settings.py:2663:    requested_plan_id = body.plan_id if body and body.plan_id else None
processual_api/routers/settings.py:2664:    plan_id = resolve_plan_id(requested_plan_id) if requested_plan_id else _resolve_current_plan_id(owner_user_id, raw)
processual_api/routers/settings.py:2667:        quota_policy = get_plan_policy(plan_id)
processual_api/routers/settings.py:2668:        quota_limit = quota_limit_for_plan(plan_id, "evaluation")
processual_api/routers/settings.py:2696:        "plan_id": plan_id,
processual_api/routers/settings.py:2718:        "plan_id": plan_id,
processual_api/routers/settings.py:2757:    plan_id = resolve_plan_id(body.plan_id)
processual_api/routers/settings.py:2759:    quota_policy = get_plan_policy(plan_id)
processual_api/routers/settings.py:2760:    quota_limit = quota_limit_for_plan(plan_id, quota_scope)
processual_api/routers/settings.py:2762:    key["plan_id"] = plan_id
processual_api/routers/settings.py:2790:    plan_id = resolve_plan_id(
processual_api/routers/settings.py:2791:        key.get("plan_id")
processual_api/routers/settings.py:2793:        or raw.get("subscription", {}).get("plan_id")
processual_api/routers/settings.py:2799:        quota_policy = get_plan_policy(plan_id)
processual_api/routers/settings.py:2800:        quota_limit = quota_limit_for_plan(plan_id, quota_scope)
processual_api/routers/settings.py:2803:        key["plan_id"] = plan_id
processual_api/routers/settings.py:2812:        key["plan_id"] = plan_id
processual_api/services/admin_subscription_analytics.py:9:from processual_api.billing.usage_pricing import monthly_unit_allowance, normalize_plan_id
processual_api/services/admin_subscription_analytics.py:107:        normalized = normalize_plan_id(raw)
processual_api/services/admin_subscription_analytics.py:113:def _plan_allowance(plan_id: str) -> int:
processual_api/services/admin_subscription_analytics.py:114:    if not plan_id or plan_id == "unknown":
processual_api/services/admin_subscription_analytics.py:117:        return _safe_int(monthly_unit_allowance(plan_id))
processual_api/services/admin_subscription_analytics.py:133:def _client_status(value: Any, plan_id: str) -> str:
processual_api/services/admin_subscription_analytics.py:135:    if "pilot" in str(plan_id or "").lower():
processual_api/services/admin_subscription_analytics.py:193:def _record_plan_id(record: dict) -> str:
processual_api/services/admin_subscription_analytics.py:195:        _first_text(record, "plan_id", "plan", "tier")
processual_api/services/admin_subscription_analytics.py:196:        or _nested_text(record, "plan", "plan_id", "id")
processual_api/services/admin_subscription_analytics.py:197:        or _nested_text(record, "subscription", "plan_id", "plan")
processual_api/services/admin_subscription_analytics.py:283:    direct_plan = _normalize_plan(_record_plan_id(record))
processual_api/services/admin_subscription_analytics.py:298:                    "plan_id",
processual_api/services/admin_subscription_analytics.py:315:    plan_id: str,
processual_api/services/admin_subscription_analytics.py:325:        "plan_id": plan_id,
processual_api/services/admin_subscription_analytics.py:391:        plan_id, plan_source = _resolve_plan_from_settings(raw)
processual_api/services/admin_subscription_analytics.py:396:            plan_id,
processual_api/services/admin_subscription_analytics.py:400:        client_plans.setdefault(client_id, plan_id)
processual_api/services/admin_subscription_analytics.py:417:        plan_id = _normalize_plan(_record_plan_id(subscription))
processual_api/services/admin_subscription_analytics.py:430:            client_plans.setdefault(client_id, plan_id)
processual_api/services/admin_subscription_analytics.py:431:            client_statuses[client_id] = _client_status(status, plan_id)
processual_api/services/admin_subscription_analytics.py:439:                plan_id=plan_id,
processual_api/services/admin_subscription_analytics.py:448:                plan_id=plan_id,
processual_api/services/admin_subscription_analytics.py:458:                plan_id=plan_id,
processual_api/services/admin_subscription_analytics.py:472:        plan_id = _normalize_plan(_record_plan_id(record))
processual_api/services/admin_subscription_analytics.py:484:        if plan_id != "unknown":
processual_api/services/admin_subscription_analytics.py:485:            client_plans.setdefault(client_id, plan_id)
processual_api/services/admin_subscription_analytics.py:490:        plan_id = client_plans.get(client_id, "unknown")
processual_api/services/admin_subscription_analytics.py:495:        summary["plans"][plan_id if plan_id in PLAN_BUCKETS else "unknown"] += 1
processual_api/services/admin_subscription_analytics.py:498:        limit = client_limits.get(client_id) or _plan_allowance(plan_id)
processual_api/services/admin_subscription_analytics.py:510:                plan_id=plan_id,
processual_api/services/admin_subscription_analytics.py:516:        if plan_id == "unknown":
processual_api/services/admin_subscription_analytics.py:522:                plan_id=plan_id,
processual_api/services/admin_subscription_analytics.py:535:                plan_id=plan_id,
processual_api/services/admin_subscription_analytics.py:548:                plan_id=plan_id,
processual_api/services/admin_subscription_analytics.py:560:                plan_id=plan_id,
processual_api/services/client_plan_source.py:5:from processual_api.billing.usage_pricing import monthly_unit_allowance, normalize_plan_id
processual_api/services/client_plan_source.py:23:    plan_id = normalize_plan_id(_text(plan_value))
processual_api/services/client_plan_source.py:24:    allowance = monthly_unit_allowance(plan_id)
processual_api/services/client_plan_source.py:25:    if not plan_id or allowance <= 0:
processual_api/services/client_plan_source.py:27:    return plan_id, allowance
processual_api/services/client_plan_source.py:31:    for key in ('approved_plan', 'requested_plan', 'plan_id', 'plan'):
processual_api/services/client_plan_source.py:41:    plan_id: str,
processual_api/services/client_plan_source.py:53:        'plan_id': plan_id,
processual_api/services/client_plan_source.py:80:    plan_id, allowance = supported_verified_plan(request_plan_candidate(entry))
processual_api/services/client_plan_source.py:81:    if not plan_id or allowance <= 0:
processual_api/services/client_plan_source.py:90:        and normalize_plan_id(entry.get('approved_plan')) == plan_id
processual_api/services/client_plan_source.py:95:        entry['approved_plan'] = plan_id
processual_api/services/client_plan_source.py:103:            plan_id=plan_id,
processual_api/services/client_plan_source.py:113:            'plan_id': plan_id,
processual_api/services/client_usage_summary.py:10:    normalize_plan_id,
processual_api/services/client_usage_summary.py:29:        "plan_id",
processual_api/services/client_usage_summary.py:43:    normalized = normalize_plan_id(value)
processual_api/services/client_usage_summary.py:60:        plan_id = _known_plan(_candidate_plan(record))
processual_api/services/client_usage_summary.py:61:        if plan_id:
processual_api/services/client_usage_summary.py:62:            return plan_id, "settings"
processual_api/services/client_usage_summary.py:68:        plan_id = _known_plan(_candidate_plan(entry))
processual_api/services/client_usage_summary.py:69:        if plan_id:
processual_api/services/client_usage_summary.py:70:            return plan_id, "client_requests"
processual_api/services/client_usage_summary.py:155:    plan_id, plan_source = resolve_client_plan(raw)
processual_api/services/client_usage_summary.py:157:        monthly_unit_allowance(plan_id)
processual_api/services/client_usage_summary.py:158:        if plan_id != "unknown" and plan_source != "missing"
processual_api/services/client_usage_summary.py:186:            "plan_id": plan_id,
processual_api/services/enterprise_r10_controlled_sandbox_18.py:314:        plan_id=_PLAN_ID,
processual_api/services/enterprise_r10_controlled_sandbox_18.py:480:        "plan_id": _PLAN_ID,
processual_api/services/plan_store.py:84:def resolve_plan_id(value: Any) -> str:
processual_api/services/plan_store.py:96:def get_plan_policy(plan_id: Any) -> dict[str, Any]:
processual_api/services/plan_store.py:97:    resolved = resolve_plan_id(plan_id)
processual_api/services/plan_store.py:102:    plan_id: Any,
processual_api/services/plan_store.py:106:    policy = get_plan_policy(plan_id)
processual_api/services/quota_store.py:17:from .plan_store import get_plan_policy, quota_limit_for_plan, resolve_plan_id
processual_api/services/quota_store.py:126:            plan_id = resolve_plan_id(
processual_api/services/quota_store.py:127:                key.get("plan_id")
processual_api/services/quota_store.py:129:                or subscription.get("plan_id")
processual_api/services/quota_store.py:149:                    plan_id,
processual_api/services/quota_store.py:153:                key["plan_id"] = plan_id
processual_api/services/quota_store.py:154:                key["quota_policy"] = get_plan_policy(plan_id)
processual_api/services/quota_store.py:173:                        "plan_id": plan_id,
processual_api/services/quota_store.py:192:                "plan_id": key.get("plan_id"),
processual_api/services/usage_log_store.py:96:        "plan_id": record.get("plan_id", ""),
processual_api/services/usage_log_store.py:202:    latest_plan_id = ""
processual_api/services/usage_log_store.py:241:        plan_id = str(record.get("plan_id", "") or "")
processual_api/services/usage_log_store.py:242:        if plan_id:
processual_api/services/usage_log_store.py:243:            latest_plan_id = plan_id
processual_api/services/usage_log_store.py:254:    monthly_included_units = monthly_unit_allowance(latest_plan_id)
processual_api/services/usage_log_store.py:282:        "plan_id": latest_plan_id,
processual_api/static/js/admin_api_keys.js:185:    'plan_id',
processual_api/static/js/admin_api_keys.js:316:      plan_id: optionalValue('admin-api-key-plan-id'),
processual_api/static/js/admin_api_keys.js:810:        client_id, user_id, plan_id, quota_limit, quota_used, status, usage_count,
processual_api/static/js/admin_client_requests.js:816:      const data = await postJson(directClientPlanPath(clientId), { plan_id: planId });
processual_api/static/js/admin_client_requests.js:822:          '; plan_id=' +
processual_api/static/js/admin_client_requests.js:823:          text(data?.plan?.plan_id || planId) +
processual_api/static/js/admin_runtime_fixups.js:302:        plan_id: profile.plan,
processual_api/static/js/admin_subscription_analytics.js:138:        const planId = statusText(item.plan_id);
processual_api/static/js/pages/institution_workspace_18.js:215:    const plan = String(state.subscription?.plan || state.subscription?.plan_id || 'starter');
processual_api/static/js/pages/offer.js:51:      plan.plan_id,
processual_api/static/js/pages/offer.js:62:    action.href = `/register?plan=${encodeURIComponent(plan.plan_id)}`;
processual_api/static/js/pages/offer.js:91:    const plan = payload.plans.find((item) => item.plan_id === planId);
processual_api/static/js/pages/plans.js:12:  link.href = `/offer/${encodeURIComponent(plan.plan_id)}`;
processual_api/static/js/pages/plans.js:13:  link.dataset.planId = plan.plan_id;
processual_api/static/js/pages/settings.js:84:    return sub.plan_id || sub.plan || "";
processual_api/static/js/pages/settings.js:132:      planId: plan.plan_id || summary.plan_id || summary.plan || 'unknown',
processual_api/static/js/pages/settings.js:332:    setText('set-api-key-integration-plan', info.plan_id || '-');
processual_api/static/js/pages/settings.js:363:      "plan=" + (info.plan_id || "-"),
processual_api/static/js/pages/settings.js:887:      ? ((readinessState.subscription.plan || readinessState.subscription.plan_id || "-") + " / " + (readinessState.subscription.status || "-"))
processual_api/static/js/pages/settings.js:1147:        ? ((readinessState.subscription.plan || readinessState.subscription.plan_id || '-') + ' / ' + (readinessState.subscription.status || '-'))
processual_api/static/js/settings_operations_18.js:101:          <div class="sops-status"><strong>${integrationEnabled ? 'Self-service available' : 'Locked by current plan'}</strong><span>${integrationEnabled ? `${keyCount} / ${esc(state.sandboxKeys?.max_active_keys || 3)} active keys` : esc(state.integration?.plan_id || 'Enterprise Integration required')}</span></div>
processual_api/static/pricing.html:634:      <article class="plan-card" data-plan-id="${text(plan.plan_id, "unknown")}">
processual_api/static/pricing.html:683:            <span class="meta-value">${text(offer.plan_display_name, offer.plan_id)}</span>
tests/test_admin_api_key_lifecycle_regression.py:54:        "plan_id",
tests/test_admin_api_key_lifecycle_regression.py:127:        "plan_id",
tests/test_admin_api_key_profile_payload_regression.py:63:        plan_id="Starter",
tests/test_admin_api_key_profiles_regression.py:180:        "`plan_id`",
tests/test_admin_api_keys_populated_cards_13e_h4.py:95:        "plan_id",
tests/test_admin_client_request_apply_plan_regression.py:135:    assert result["plan"]["plan_id"] == "enterprise"
tests/test_admin_client_request_apply_plan_regression.py:149:    assert saved_request["status_history"][-1]["plan_id"] == "enterprise"
tests/test_admin_direct_client_plan_setting.py:66:            {"plan_id": "enterprise"},
tests/test_admin_direct_client_plan_setting.py:73:    assert result["plan"]["plan_id"] == "enterprise"
tests/test_admin_direct_client_plan_setting.py:83:    assert raw["subscription"]["plan_id"] == "enterprise"
tests/test_admin_direct_client_plan_setting.py:129:                {"plan_id": "unsupported-direct-plan"},
tests/test_admin_direct_client_plan_setting.py:148:                {"plan_id": "enterprise"},
tests/test_admin_direct_client_plan_setting.py:179:    assert summary["plan"]["plan_id"] == "enterprise"
tests/test_admin_direct_client_plan_setting.py:194:            {"plan_id": "enterprise"},
tests/test_admin_direct_client_plan_setting.py:215:            {"plan_id": "enterprise"},
tests/test_admin_direct_client_plan_ui.py:38:        "postJson(directClientPlanPath(clientId), { plan_id: planId })",
tests/test_admin_marketplace_models_r2.py:63:        "plan_id",
tests/test_admin_marketplace_models_r2.py:177:            "plan_id",
tests/test_admin_marketplace_models_r2.py:191:            "plan_id",
tests/test_admin_marketplace_repositories_r3.py:84:    plan_id = uuid.uuid4()
tests/test_admin_marketplace_repositories_r3.py:89:    result = await repository.get_by_id(plan_id)
tests/test_admin_marketplace_repositories_r3.py:92:    assert session.get_calls == [(AdminMarketPlan, plan_id)]
tests/test_admin_runtime_fixups_regression.py:35:        "plan_id",
tests/test_admin_subscription_analytics_regression.py:45:            "plan_id": "starter",
tests/test_admin_subscription_analytics_regression.py:66:            "plan_id": "enterprise",
tests/test_admin_subscription_analytics_regression.py:83:                    "plan_id": "starter",
tests/test_admin_subscription_analytics_regression.py:88:                    "plan_id": "enterprise",
tests/test_admin_subscription_analytics_regression.py:99:            "plan_id": "starter",
tests/test_admin_subscription_analytics_regression.py:109:            "plan_id": "enterprise",
tests/test_admin_subscription_analytics_risk_indicators.py:28:            "plan_id": "mystery-plan",
tests/test_admin_subscription_analytics_risk_indicators.py:45:                    "plan_id": "mystery-plan",
tests/test_admin_subscription_analytics_risk_indicators.py:56:            "plan_id": "mystery-plan",
tests/test_admin_subscription_analytics_risk_indicators.py:80:            "plan_id": "unknown",
tests/test_admin_subscription_analytics_risk_indicators.py:96:            "plan_id": "unknown",
tests/test_admin_subscription_analytics_risk_indicators.py:114:            "plan_id": "unknown",
tests/test_api_key_quota_plan_regression.py:12:        "plan_id": "starter",
tests/test_api_key_quota_plan_regression.py:54:    def fake_resolve_plan_id(value):
tests/test_api_key_quota_plan_regression.py:57:    def fake_get_plan_policy(plan_id):
tests/test_api_key_quota_plan_regression.py:58:        limit = plan_limits[plan_id]
tests/test_api_key_quota_plan_regression.py:60:            "id": plan_id,
tests/test_api_key_quota_plan_regression.py:61:            "name": plan_id.title(),
tests/test_api_key_quota_plan_regression.py:66:    def fake_quota_limit_for_plan(plan_id, quota_scope):
tests/test_api_key_quota_plan_regression.py:68:        return plan_limits[plan_id]
tests/test_api_key_quota_plan_regression.py:70:    monkeypatch.setattr(settings_router, "resolve_plan_id", fake_resolve_plan_id)
tests/test_api_key_quota_plan_regression.py:93:            settings_router.ApiKeyPlanUpdate(plan_id="pro"),
tests/test_api_key_quota_plan_regression.py:104:    assert response["plan_id"] == "pro"
tests/test_api_key_quota_plan_regression.py:113:    assert stored["plan_id"] == "pro"
tests/test_api_key_quota_plan_regression.py:125:            "subscription": {"plan_id": "starter"},
tests/test_api_key_quota_plan_regression.py:160:            "subscription": {"plan_id": "pro"},
tests/test_api_key_quota_plan_regression.py:163:                    plan_id="pro",
tests/test_api_key_quota_plan_regression.py:189:    assert response["plan_id"] == "pro"
tests/test_api_key_quota_plan_regression.py:196:    assert stored["plan_id"] == "pro"
tests/test_api_key_settings_routes.py:46:    monkeypatch.setattr(settings_router, "_resolve_current_plan_id", lambda user_id, raw: "starter")
tests/test_api_key_settings_routes.py:47:    monkeypatch.setattr(settings_router, "resolve_plan_id", lambda value: "starter")
tests/test_api_key_settings_routes.py:51:        lambda plan_id: {"id": plan_id, "name": "Starter", "quotas": {"evaluation": 100}},
tests/test_api_key_settings_routes.py:53:    monkeypatch.setattr(settings_router, "quota_limit_for_plan", lambda plan_id, scope: 100)
tests/test_auth_registration_http_r5b_r1.py:173:        json=_individual_payload(password=secret, role="platform_admin", plan_id="enterprise"),
tests/test_client_api_key_integration_endpoint_regression.py:27:                "plan_id": "starter",
tests/test_client_api_key_integration_endpoint_regression.py:44:    assert result["plan_id"] == "starter"
tests/test_client_api_key_integration_endpoint_regression.py:58:                "plan_id": "enterprise_integration",
tests/test_client_api_key_integration_endpoint_regression.py:96:    assert result["plan_id"] == "enterprise_integration"
tests/test_client_api_key_integration_endpoint_regression.py:119:                "plan_id": "enterprise_private",
tests/test_client_api_key_integration_endpoint_regression.py:135:    assert result["plan_id"] == "enterprise_private"
tests/test_client_plan_source_service.py:59:            'plan_id': 'business',
tests/test_client_plan_source_service.py:71:    assert entry['status_history'][-1]['plan_id'] == 'business'
tests/test_client_plan_source_service.py:89:    assert result['plan']['plan_id'] == 'starter'
tests/test_client_sandbox_api_keys_18.py:29:        "_resolve_client_api_key_integration_plan_id",
tests/test_client_sandbox_api_keys_18.py:112:        "_resolve_client_api_key_integration_plan_id",
tests/test_client_usage_summary_route_regression.py:31:                "subscription": {"plan_id": "enterprise"},
tests/test_client_usage_summary_route_regression.py:89:    assert result["plan"]["plan_id"] == "enterprise"
tests/test_client_usage_summary_security_regression.py:40:                "subscription": {"plan_id": "enterprise"},
tests/test_client_usage_summary_security_regression.py:89:    assert result["plan"]["plan_id"] == "unknown"
tests/test_client_usage_summary_service_regression.py:65:                "plan_id": "business",
tests/test_client_usage_summary_service_regression.py:83:                "plan_id": "business",
tests/test_client_usage_summary_service_regression.py:96:                "plan_id": "starter",
tests/test_client_usage_summary_service_regression.py:113:    assert summary["plan_id"] == "business"
tests/test_client_usage_summary_service_regression.py:150:            "plan_id": "business",
tests/test_commercial_catalog_contracts_group2.py:18:def test_catalog_contracts_cover_all_selected_plans() -> None:
tests/test_connector_fake_sandbox_transport_16e_r4.py:133:    plan_id: str = PLAN_ID,
tests/test_connector_fake_sandbox_transport_16e_r4.py:137:        plan_id=plan_id,
tests/test_connector_fake_sandbox_transport_16e_r4.py:153:    plan_id: str = PLAN_ID,
tests/test_connector_fake_sandbox_transport_16e_r4.py:159:            plan_id=plan_id,
tests/test_connector_fake_sandbox_transport_16e_r4.py:168:    plan_id: str = PLAN_ID,
tests/test_connector_fake_sandbox_transport_16e_r4.py:175:            plan_id=plan_id,
tests/test_connector_fake_sandbox_transport_16e_r4.py:184:    plan_id: str = PLAN_ID,
tests/test_connector_fake_sandbox_transport_16e_r4.py:192:                plan_id=plan_id,
tests/test_connector_fake_sandbox_transport_16e_r4.py:307:    assert contract.plan_id == PLAN_ID
tests/test_connector_fake_sandbox_transport_16e_r4.py:458:    assert pilot.selected_plan_id == PLAN_ID
tests/test_connector_fake_sandbox_transport_16e_r4.py:520:    assert contract.plan_id == PLAN_ID
tests/test_connector_fake_sandbox_transport_16e_r4.py:703:        plan_id=HELPDESK_PLAN_ID
tests/test_connector_mock_dispatcher_16d.py:55:        "plan_id": plan.plan_id,
tests/test_connector_mock_dispatcher_16d.py:107:        request.plan_id = "changed"
tests/test_connector_mock_dispatcher_16d.py:121:        "plan_id",
tests/test_connector_mock_dispatcher_16d.py:250:        plan_id="unknown_operation_plan_16d",
tests/test_connector_mock_dispatcher_16d.py:349:        plan_id="plan_16d",
tests/test_connector_mock_dispatcher_16d.py:366:        plan_id="plan_16d",
tests/test_connector_operation_plans_16c.py:185:        assert approval.plan_id == plan.plan_id
tests/test_connector_operation_plans_16c.py:205:        assert audit.plan_id == plan.plan_id
tests/test_connector_operation_plans_16c.py:226:    assert get_connector_operation_plan(plan.plan_id.upper()) is plan
tests/test_connector_operation_plans_16c.py:253:            plan_id=f"{plan.plan_id}_production_probe",
tests/test_connector_sandbox_evidence_16e_r7.py:213:        plan_id=PLAN_ID,
tests/test_connector_sandbox_evidence_16e_r7.py:509:    assert first.plan_id_reference == PLAN_ID
tests/test_connector_sandbox_pilot_16e_r1.py:168:    assert contract.selected_plan_id == SELECTED_PLAN_ID
tests/test_connector_sandbox_pilot_16e_r1.py:169:    assert contract.candidate_plan_ids == CANDIDATE_PLAN_IDS
tests/test_connector_sandbox_pilot_16e_r1.py:170:    assert len(contract.candidate_plan_ids) == 2
tests/test_connector_sandbox_pilot_16e_r1.py:260:    for plan_id in contract.candidate_plan_ids:
tests/test_connector_sandbox_pilot_16e_r1.py:261:        plan = CONNECTOR_OPERATION_PLANS[plan_id]
tests/test_connector_sandbox_pilot_16e_r1.py:287:def test_selected_plan_uses_ticket_read_scope() -> None:
tests/test_connector_sandbox_pilot_16e_r1.py:463:def test_contract_rejects_selected_plan_outside_candidates() -> None:
tests/test_connector_sandbox_pilot_16e_r1.py:467:            selected_plan_id="unlisted_plan",
tests/test_connector_sandbox_read_faults_16e_r6.py:156:    plan_id: str = PLAN_ID,
tests/test_connector_sandbox_read_faults_16e_r6.py:161:        plan_id=plan_id,
tests/test_connector_sandbox_read_faults_16e_r6.py:179:    plan_id: str = PLAN_ID,
tests/test_connector_sandbox_read_faults_16e_r6.py:186:            plan_id=plan_id,
tests/test_connector_sandbox_read_faults_16e_r6.py:210:    plan_id: str = PLAN_ID,
tests/test_connector_sandbox_read_faults_16e_r6.py:220:            plan_id=plan_id,
tests/test_connector_sandbox_read_faults_16e_r6.py:561:            "plan_id",
tests/test_connector_sandbox_read_workflow_16e_r5.py:136:    plan_id: str = PLAN_ID,
tests/test_connector_sandbox_read_workflow_16e_r5.py:140:        plan_id=plan_id,
tests/test_connector_sandbox_read_workflow_16e_r5.py:156:    plan_id: str = PLAN_ID,
tests/test_connector_sandbox_read_workflow_16e_r5.py:162:            plan_id=plan_id,
tests/test_connector_sandbox_read_workflow_16e_r5.py:171:    plan_id: str = PLAN_ID,
tests/test_connector_sandbox_read_workflow_16e_r5.py:178:            plan_id=plan_id,
tests/test_connector_sandbox_read_workflow_16e_r5.py:188:    plan_id: str = PLAN_ID,
tests/test_connector_sandbox_read_workflow_16e_r5.py:196:            plan_id=plan_id,
tests/test_connector_sandbox_read_workflow_16e_r5.py:206:    plan_id: str = PLAN_ID,
tests/test_connector_sandbox_read_workflow_16e_r5.py:213:            plan_id=plan_id,
tests/test_connector_sandbox_read_workflow_16e_r5.py:335:    assert contract.plan_id == PLAN_ID
tests/test_connector_sandbox_read_workflow_16e_r5.py:447:        .plan_id
tests/test_connector_sandbox_read_workflow_16e_r5.py:568:            "plan_id",
tests/test_connector_transport_contracts_16e_r3.py:113:    plan_id: str = PLAN_ID,
tests/test_connector_transport_contracts_16e_r3.py:118:        plan_id=plan_id,
tests/test_connector_transport_contracts_16e_r3.py:134:    plan_id: str = PLAN_ID,
tests/test_connector_transport_contracts_16e_r3.py:140:            plan_id=plan_id,
tests/test_connector_transport_contracts_16e_r3.py:254:    assert contract.plan_id == PLAN_ID
tests/test_connector_transport_contracts_16e_r3.py:409:    assert pilot.selected_plan_id == PLAN_ID
tests/test_connector_transport_contracts_16e_r3.py:570:            plan_id=HELPDESK_PLAN_ID,
tests/test_fastapi_integration_smoke.py:240:                "subscription": {"plan_id": "starter"},
tests/test_fastapi_integration_smoke.py:250:                        "plan_id": "starter",
tests/test_identity_auth_models_r2.py:52:    assert "plan_id" not in _column_names(IdentityUser)
tests/test_identity_registration_contracts_r1.py:59:            plan_id="enterprise",
tests/test_identity_registration_contracts_r1.py:92:    assert contract.client_selected_plan_allowed is False
tests/test_identity_registration_contracts_r1.py:127:        ("client_selected_plan_allowed", True),
tests/test_maestro_group1_pricing_review.py:128:    assert {item["plan_id"] for item in payload["plans"]} == set(PLAN_REVIEW_CONFIG)
tests/test_maestro_group1_selected_pricing.py:13:    calculate_selected_plan_proposal,
tests/test_maestro_group1_selected_pricing.py:41:    for plan_id in SELECTED_MONTHLY_PRICES:
tests/test_maestro_group1_selected_pricing.py:42:        proposal = calculate_selected_plan_proposal(plan_id)
tests/test_maestro_group1_selected_pricing.py:54:    for plan_id in enterprise_ids:
tests/test_maestro_group1_selected_pricing.py:55:        proposal = calculate_selected_plan_proposal(plan_id)
tests/test_maestro_group1_selected_pricing.py:80:        calculate_selected_plan_proposal("unknown")
tests/test_offer_fulfillment_policy.py:8:    offer = {"offer_id": "starter_monthly", "plan_id": "starter"}
tests/test_offer_fulfillment_policy.py:19:    offer = {"offer_id": "business_monthly", "plan_id": "business"}
tests/test_offer_fulfillment_policy.py:29:    offer = {"offer_id": "enterprise_contact", "plan_id": "enterprise"}
tests/test_offer_fulfillment_policy.py:41:    offer = {"offer_id": "starter_monthly", "plan_id": "starter"}
tests/test_offer_fulfillment_policy.py:51:    offer = {"offer_id": "starter_trial", "plan_id": "starter"}
tests/test_offer_fulfillment_policy.py:67:        "plan_id": "enterprise_integration_starter",
tests/test_offer_pricebook.py:78:        plan = get_subscription_plan(offer["plan_id"])
tests/test_offer_pricebook.py:82:        assert offer["monthly_unit_allowance"] == monthly_unit_allowance(offer["plan_id"])
tests/test_plan_led_registration_pages_a3.py:39:def test_offer_page_loads_selected_plan_from_server_catalog() -> None:
tests/test_pricing_plan_allowance_catalog_regression.py:23:    for plan_id, allowance in expected.items():
tests/test_pricing_plan_allowance_catalog_regression.py:24:        assert monthly_unit_allowance(plan_id) == allowance
tests/test_pricing_quota_usage_log_metadata_regression.py:44:            "plan_id": "enterprise_integration",
tests/test_pricing_quota_usage_log_metadata_regression.py:73:    assert record["plan_id"] == "enterprise_integration"
tests/test_pricing_quota_usage_log_metadata_regression.py:103:        "plan_id": "enterprise_integration",
tests/test_pricing_quota_usage_log_metadata_regression.py:127:    assert record["plan_id"] == "enterprise_integration"
tests/test_pricing_rejection_usage_log_metadata_regression.py:64:                "plan_id": "business",
tests/test_pricing_rejection_usage_log_metadata_regression.py:87:        "plan_id": "business",
tests/test_pricing_rejection_usage_log_metadata_regression.py:106:            "plan_id": "business",
tests/test_pricing_rejection_usage_log_metadata_regression.py:131:    assert record["plan_id"] == "business"
tests/test_pricing_rejection_usage_log_metadata_regression.py:171:        "plan_id": "business",
tests/test_pricing_rejection_usage_log_metadata_regression.py:185:    assert record["plan_id"] == "business"
tests/test_pricing_usage_ledger_schema_docs.py:41:        "plan_id",
tests/test_productization_pricing_surface_regression.py:16:            "subscription": {"plan_id": "enterprise", "plan": "enterprise"},
tests/test_productization_pricing_surface_regression.py:22:    assert summary["plan"]["plan_id"] == "enterprise"
tests/test_public_plan_journey_a3.py:1:from processual_api.billing.public_plan_journey import (
tests/test_public_plan_journey_a3.py:3:    public_plan_journey_catalog,
tests/test_public_plan_journey_a3.py:7:def test_public_plan_journey_has_expected_order() -> None:
tests/test_public_plan_journey_a3.py:8:    payload = public_plan_journey_catalog()
tests/test_public_plan_journey_a3.py:10:    assert [plan["plan_id"] for plan in payload["plans"]] == list(PUBLIC_PLAN_ORDER)
tests/test_public_plan_journey_a3.py:14:    payload = public_plan_journey_catalog()
tests/test_public_plan_journey_a3.py:15:    plan_ids = {plan["plan_id"] for plan in payload["plans"]}
tests/test_public_plan_journey_a3.py:17:    assert "developer" not in plan_ids
tests/test_public_plan_journey_a3.py:18:    assert "internal" not in plan_ids
tests/test_public_plan_journey_a3.py:19:    assert "pilot_starter" not in plan_ids
tests/test_public_plan_journey_a3.py:20:    assert "enterprise_integration" not in plan_ids
tests/test_public_plan_journey_a3.py:24:    payload = public_plan_journey_catalog()
tests/test_public_plan_journey_a3.py:25:    by_id = {plan["plan_id"]: plan for plan in payload["plans"]}
tests/test_public_plan_journey_a3.py:35:    for plan_id, expected_price in expected_prices.items():
tests/test_public_plan_journey_a3.py:36:        assert by_id[plan_id]["monthly_price_usd"] == expected_price
tests/test_public_plan_journey_a3.py:37:        assert by_id[plan_id]["price_visibility"] == "public"
tests/test_public_plan_journey_a3.py:38:        assert by_id[plan_id]["requires_assessment"] is False
tests/test_public_plan_journey_a3.py:39:        assert by_id[plan_id]["registration_available"] is True
tests/test_public_plan_journey_a3.py:40:        assert by_id[plan_id]["action"] == "start_registration"
tests/test_public_plan_journey_a3.py:44:    payload = public_plan_journey_catalog()
tests/test_public_plan_journey_a3.py:45:    by_id = {plan["plan_id"]: plan for plan in payload["plans"]}
tests/test_public_plan_journey_a3.py:47:    for plan_id in (
tests/test_public_plan_journey_a3.py:52:        assert by_id[plan_id]["monthly_price_usd"] is None
tests/test_public_plan_journey_a3.py:53:        assert by_id[plan_id]["price_visibility"] == "assessment"
tests/test_public_plan_journey_a3.py:54:        assert by_id[plan_id]["requires_assessment"] is True
tests/test_public_plan_journey_a3.py:55:        assert by_id[plan_id]["registration_available"] is False
tests/test_public_plan_journey_a3.py:56:        assert by_id[plan_id]["action"] == "request_assessment"
tests/test_public_plan_journey_a3.py:60:    payload = public_plan_journey_catalog()
tests/test_public_plan_journey_a3.py:67:def test_public_plan_journey_contains_eight_plans() -> None:
tests/test_public_plan_journey_a3.py:68:    payload = public_plan_journey_catalog()
tests/test_public_plan_journey_route_a3.py:6:def test_public_plan_journey_route_returns_catalog() -> None:
tests/test_public_plan_journey_route_a3.py:22:def test_public_plan_journey_route_exposes_expected_prices() -> None:
tests/test_public_plan_journey_route_a3.py:26:    by_id = {plan["plan_id"]: plan for plan in payload["plans"]}
tests/test_public_plan_journey_route_a3.py:35:def test_public_plan_journey_route_hides_post_pilot_prices() -> None:
tests/test_public_plan_journey_route_a3.py:39:    by_id = {plan["plan_id"]: plan for plan in payload["plans"]}
tests/test_public_plan_journey_route_a3.py:41:    for plan_id in (
tests/test_public_plan_journey_route_a3.py:46:        assert by_id[plan_id]["monthly_price_usd"] is None
tests/test_public_plan_journey_route_a3.py:47:        assert by_id[plan_id]["requires_assessment"] is True
tests/test_public_plan_journey_route_a3.py:48:        assert by_id[plan_id]["registration_available"] is False
tests/test_public_plan_journey_route_a3.py:49:        assert by_id[plan_id]["action"] == "request_assessment"
tests/test_quota_store.py:16:        "plan_id": "starter",
tests/test_quota_store.py:53:        "subscription": subscription or {"plan_id": "starter"},
tests/test_quota_store.py:118:        "plan_id": "starter",
tests/test_quota_store.py:289:        "resolve_plan_id",
tests/test_quota_store.py:295:        lambda _plan_id, _scope, _default=50: 7,
tests/test_quota_store.py:300:        lambda plan_id: {
tests/test_quota_store.py:301:            "id": plan_id,
tests/test_quota_store.py:310:            plan_id="pro",
tests/test_quota_store.py:325:    assert stored_key["plan_id"] == "resolved-pro"
tests/test_subscription_pricing_catalog.py:42:    assert {plan["plan_id"] for plan in commercial_plans} == {
tests/test_subscription_pricing_catalog.py:51:        assert plan["monthly_unit_allowance"] == monthly_unit_allowance(plan["plan_id"])
tests/test_subscription_pricing_catalog.py:70:    assert starter["plan_id"] == "starter"
