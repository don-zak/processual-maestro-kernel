# Group 2 Ã¢â‚¬â€ Commercial and UI/UX Foundation Inventory

## Purpose

This inventory establishes the exact implementation surface before connecting
the selected Maestro pricing proposal to catalog, entitlements, subscriptions,
checkout, local Tunisia payment choice, and Admin Marketplace.

## Binding UI/UX acceptance gate

- Reuse the current program design system, tokens, layouts, components, and interaction patterns.
- Do not introduce a temporary, prototype, or visually disconnected interface.
- Provide explicit loading, empty, error, success, disabled, and permission-denied states.
- Preserve responsive behavior and accessibility.
- Prevent confusion between public subscription flow and super-admin commercial controls.
- Keep delegated supervisors denied from Admin Marketplace.
- Keep Tunisia local checkout optional and visible only to eligible Tunisian addresses at the start of the payment journey.
- Keep Lemon Squeezy available as the general route.
- Keep pricing, checkout, invoicing, settlement, and quota enforcement disabled until explicit approval.

## Repository state

Branch: feat/group2-commercial-ui-foundation
Base: origin/main
Generated: 2026-07-29T12:31:02+01:00
## Frontend framework markers

```text
(none found)
```

## Design-system and UI candidate files

```text
processual_api\static\css\admin_integration_center_18.css
processual_api\static\css\admin_operator_pilot_handoff.css
processual_api\static\css\admin_operator_pilot_handoff_17c.css
processual_api\static\css\admin_ui_hardening_13c.css
processual_api\static\css\console.css
processual_api\static\css\institution_workspace_18.css
processual_api\static\css\settings_layout_18.css
processual_api\static\css\settings_operations_18.css
processual_api\static\css\tour.css
processual_api\static\js\adapters\adapters.js
processual_api\static\js\adapters\cgt.js
processual_api\static\js\adapters\gateway.js
processual_api\static\js\adapters\governance.js
processual_api\static\js\adapters\governor.js
processual_api\static\js\adapters\health.js
processual_api\static\js\adapters\reports.js
processual_api\static\js\adapters\simulation.js
processual_api\static\js\adapters\telemetry.js
processual_api\static\js\adapters\workflows.js
processual_api\static\js\admin_actions.js
processual_api\static\js\admin_adapters.js
processual_api\static\js\admin_api_key_summary.js
processual_api\static\js\admin_api_keys.js
processual_api\static\js\admin_auth_bridge.js
processual_api\static\js\admin_client_requests.js
processual_api\static\js\admin_dashboard.js
processual_api\static\js\admin_home_layout.js
processual_api\static\js\admin_integration_center_18.js
processual_api\static\js\admin_integration_pilot_controls_13b.js
processual_api\static\js\admin_integration_readiness.js
processual_api\static\js\admin_layout_cleanup.js
processual_api\static\js\admin_nav.js
processual_api\static\js\admin_operator_pilot_handoff.js
processual_api\static\js\admin_operator_pilot_handoff_17c.js
processual_api\static\js\admin_runtime.js
processual_api\static\js\admin_runtime_fixups.js
processual_api\static\js\admin_session.js
processual_api\static\js\admin_subscription_analytics.js
processual_api\static\js\admin_supervisor_audit_summary.js
processual_api\static\js\admin_supervisor_readiness_summary.js
processual_api\static\js\admin_supervisor_stats.js
processual_api\static\js\admin_ui_hardening_13c.js
processual_api\static\js\app.js
processual_api\static\js\auth.js
processual_api\static\js\charts.js
processual_api\static\js\client.js
processual_api\static\js\i18n.js
processual_api\static\js\login_token_capture.js
processual_api\static\js\pages\adapters.js
processual_api\static\js\pages\cgt.js
processual_api\static\js\pages\gateway.js
processual_api\static\js\pages\governance.js
processual_api\static\js\pages\governor.js
processual_api\static\js\pages\institution_workspace_18.js
processual_api\static\js\pages\overview.js
processual_api\static\js\pages\reports.js
processual_api\static\js\pages\settings.js
processual_api\static\js\pages\simulation.js
processual_api\static\js\pages\telemetry.js
processual_api\static\js\pages\workflows.js
processual_api\static\js\settings_layout_18.js
processual_api\static\js\settings_operations_18.js
processual_api\static\js\tour\tour-engine.js
processual_api\static\js\tour\tour-steps.js
```

## Root files

```text
.dockerignore
.env.example
.env.production.example
.flake8
.git
.gitattributes
.gitignore
.pre-commit-config.yaml
alembic.ini
CHANGELOG.md
cloudbuild.yaml
CONTRIBUTING.md
DEPLOYMENT_EXTERNAL.md
docker-compose.yml
Dockerfile
EXTERNAL_READINESS_REPORT.md
FINAL_READINESS_REPORT.md
fix_ascii_labels.py
fix_gateway_policies_ascii.py
fix_policy_engine_ascii.py
MAESTRO_GATEWAY_MULTI_AGENT_PROOF.md
patch_repair_loop_accept_exit.py
patch_repair_loop_client_query.py
pyproject.toml
readiness_report.html
README.md
RELEASE_NOTES.md
repair_loop_writer.py
run_ollama_maestro_repair_loop.py
run_ollama_to_maestro.py
SECURITY.md
```

## Root directories

```text
.github
alembic
cgtlib
docs
examples
ops
processual_api
processual_kernel
scripts
tests
tools
```

## Commercial files

```text
alembic\versions\20260727_0011_admin_marketplace_persistence.py
cgtlib\catalogs.py
docs\ADMIN_MARKETPLACE_HANDOFF.md
docs\pricing\calibration\MAESTRO_AGENT_IDENTITY_BRIDGE_M1_R4.md
docs\pricing\calibration\MAESTRO_AGENT_IDENTITY_CARRIER_M1_R3.md
docs\pricing\calibration\MAESTRO_CALIBRATION_METHOD_R1.md
docs\pricing\calibration\MAESTRO_COMMERCIAL_EXECUTION_IDENTITY_M1_R2.md
docs\pricing\calibration\MAESTRO_EXECUTION_AUTHORITY_GAP_R2B.md
docs\pricing\calibration\MAESTRO_EXECUTION_AUTHORITY_READINESS_R2C.md
docs\pricing\calibration\MAESTRO_EXECUTION_FAMILY_EVIDENCE_M1.md
docs\pricing\calibration\MAESTRO_REFERENCE_WORKLOADS_R1.md
docs\pricing\calibration\MAESTRO_SHADOW_MEASUREMENT_R2.md
docs\pricing\CHECKOUT_DISABLED_CONTRACT_09D.md
docs\pricing\COMMERCIAL_TERMS_REVIEW_09C.md
docs\pricing\MAESTRO_ENTERPRISE_USAGE_REFERENCE.md
docs\pricing\MAESTRO_GROUP1_PRICING_REVIEW.md
docs\pricing\MAESTRO_GROUP1_SELECTED_PRICING_PROPOSAL.md
docs\pricing\PRICING_REVIEW_09A_DRAFT.md
docs\reports\API_KEYS_QUOTA_STORE_AUDIT_AR.md
docs\reports\MAESTRO_PRICING_MARKET_POSITIONING.md
docs\reports\UI_00A_SUBSCRIPTIONS_PAGE_CONTENT_PLAN_AR.md
processual_api\admin_marketplace\__init__.py
processual_api\admin_marketplace\audit_contracts.py
processual_api\admin_marketplace\authority.py
processual_api\admin_marketplace\contracts.py
processual_api\admin_marketplace\errors.py
processual_api\admin_marketplace\models.py
processual_api\admin_marketplace\persistence\__init__.py
processual_api\admin_marketplace\persistence\errors.py
processual_api\admin_marketplace\persistence\integrity.py
processual_api\admin_marketplace\persistence\protocols.py
processual_api\admin_marketplace\persistence\repositories.py
processual_api\admin_marketplace\persistence\unit_of_work.py
processual_api\billing\__init__.py
processual_api\billing\maestro_agent_identity_bridge.py
processual_api\billing\maestro_agent_identity_carrier.py
processual_api\billing\maestro_calibration_contracts.py
processual_api\billing\maestro_commercial_execution_identity.py
processual_api\billing\maestro_execution_authority.py
processual_api\billing\maestro_execution_authority_readiness.py
processual_api\billing\maestro_execution_family_evidence.py
processual_api\billing\maestro_group1_pricing_review.py
processual_api\billing\maestro_group1_selected_pricing.py
processual_api\billing\maestro_reference_workloads.py
processual_api\billing\maestro_shadow_measurements.py
processual_api\billing\maestro_shadow_store.py
processual_api\billing\offer_fulfillment_policy.py
processual_api\billing\offer_pricebook.py
processual_api\billing\router.py
processual_api\billing\subscription_catalog.py
processual_api\billing\unit_cost_assumptions.py
processual_api\billing\usage_pricing.py
processual_api\integrations\scope_catalog.py
processual_api\middleware\subscription.py
processual_api\services\admin_subscription_analytics.py
processual_api\services\quota_store.py
processual_api\static\js\admin_subscription_analytics.js
processual_api\static\pricing.html
tests\test_admin_marketplace_audit_contracts_r1.py
tests\test_admin_marketplace_authority_r1.py
tests\test_admin_marketplace_channel_policy_r1.py
tests\test_admin_marketplace_commercial_policy_repositories_r3.py
tests\test_admin_marketplace_contracts_r1.py
tests\test_admin_marketplace_exports_r1.py
tests\test_admin_marketplace_integrity_translation_r3.py
tests\test_admin_marketplace_migration_r2.py
tests\test_admin_marketplace_models_r2.py
tests\test_admin_marketplace_payment_repositories_r3.py
tests\test_admin_marketplace_repositories_r3.py
tests\test_admin_marketplace_repository_contracts_r3.py
tests\test_admin_marketplace_transactional_repositories_r3.py
tests\test_admin_marketplace_unit_of_work_r3.py
tests\test_admin_subscription_analytics_plan_sources.py
tests\test_admin_subscription_analytics_regression.py
tests\test_admin_subscription_analytics_risk_indicators.py
tests\test_admin_subscription_analytics_ui.py
tests\test_api_key_quota_plan_regression.py
tests\test_billing_pricing_catalog_route.py
tests\test_billing_subscription_regression.py
tests\test_byok_usage_logging_pricing_regression.py
tests\test_byok_usage_pricing.py
tests\test_checkout_disabled_contract_09d_document.py
tests\test_client_requests_billing_endpoint_regression.py
tests\test_client_requests_billing_ui_regression.py
tests\test_integration_scope_catalog.py
tests\test_maestro_group1_pricing_review.py
tests\test_maestro_group1_pricing_review_boundaries.py
tests\test_maestro_group1_selected_pricing.py
tests\test_maestro_group1_selected_pricing_boundaries.py
tests\test_offer_fulfillment_policy.py
tests\test_offer_pricebook.py
tests\test_offer_pricebook_route.py
tests\test_pricing_commercial_supervisor_lesson_docs.py
tests\test_pricing_factors_surface_ui.py
tests\test_pricing_market_positioning_docs.py
tests\test_pricing_offers_surface_ui.py
tests\test_pricing_page_route_regression.py
tests\test_pricing_plan_allowance_catalog_regression.py
tests\test_pricing_quota_usage_log_metadata_regression.py
tests\test_pricing_rejection_usage_log_metadata_regression.py
tests\test_pricing_review_09a_document.py
tests\test_pricing_subscriptions_surface_ui.py
tests\test_pricing_unit_quota_enforcement_regression.py
tests\test_pricing_usage_ledger_schema_docs.py
tests\test_productization_pricing_surface_regression.py
tests\test_quota_store.py
tests\test_subscription_pricing_catalog.py
```

## Route and page candidates

```text
.\alembic\env.py
.\alembic\versions\20260727_0011_admin_marketplace_persistence.py
.\fix_ascii_labels.py
.\processual_api\admin_marketplace\__init__.py
.\processual_api\admin_marketplace\audit_contracts.py
.\processual_api\admin_marketplace\authority.py
.\processual_api\admin_marketplace\contracts.py
.\processual_api\admin_marketplace\errors.py
.\processual_api\admin_marketplace\models.py
.\processual_api\admin_marketplace\persistence\__init__.py
.\processual_api\admin_marketplace\persistence\errors.py
.\processual_api\admin_marketplace\persistence\integrity.py
.\processual_api\admin_marketplace\persistence\protocols.py
.\processual_api\admin_marketplace\persistence\repositories.py
.\processual_api\admin_marketplace\persistence\unit_of_work.py
.\processual_api\auth\__init__.py
.\processual_api\auth\account_recovery_router.py
.\processual_api\auth\account_recovery_runtime.py
.\processual_api\auth\delivery_dispatcher.py
.\processual_api\auth\delivery_operations_router.py
.\processual_api\auth\mfa_router.py
.\processual_api\auth\recovery_email_router.py
.\processual_api\auth\registration_contracts.py
.\processual_api\auth\registration_router.py
.\processual_api\auth\router.py
.\processual_api\auth\security.py
.\processual_api\auth\session_router.py
.\processual_api\billing\__init__.py
.\processual_api\billing\maestro_agent_identity_bridge.py
.\processual_api\billing\maestro_agent_identity_carrier.py
.\processual_api\billing\maestro_calibration_contracts.py
.\processual_api\billing\maestro_commercial_execution_identity.py
.\processual_api\billing\maestro_execution_authority.py
.\processual_api\billing\maestro_execution_family_evidence.py
.\processual_api\billing\maestro_group1_pricing_review.py
.\processual_api\billing\maestro_group1_selected_pricing.py
.\processual_api\billing\maestro_shadow_measurements.py
.\processual_api\billing\offer_fulfillment_policy.py
.\processual_api\billing\offer_pricebook.py
.\processual_api\billing\router.py
.\processual_api\billing\subscription_catalog.py
.\processual_api\billing\unit_cost_assumptions.py
.\processual_api\billing\usage_pricing.py
.\processual_api\cache\redis.py
.\processual_api\cgt_governor\adapters\__init__.py
.\processual_api\cgt_governor\adapters\openrouter_adapter.py
.\processual_api\cgt_governor\adapters\provider_metadata.py
.\processual_api\cgt_governor\adapters\registry.py
.\processual_api\cgt_governor\data\storage.py
.\processual_api\cgt_governor\gateway\storage.py
.\processual_api\cgt_governor\policy\engine.py
.\processual_api\cgt_governor\simulation\engine.py
.\processual_api\cgt_governor\simulation\scenarios.py
.\processual_api\integrations\adapter_contracts.py
.\processual_api\integrations\connector_registry.py
.\processual_api\integrations\credential_profiles.py
.\processual_api\integrations\external_connectivity_cases.py
.\processual_api\integrations\operator_sandbox_intake.py
.\processual_api\integrations\outbound_allowlist_tls_readiness.py
.\processual_api\integrations\sandbox_evidence.py
.\processual_api\integrations\sandbox_read_faults.py
.\processual_api\integrations\sandbox_read_workflow.py
.\processual_api\integrations\secret_provider_binding_readiness.py
.\processual_api\integrations\sector_profiles.py
.\processual_api\integrations\training_connection_request.py
.\processual_api\integrations\training_outbound_tls_approval.py
.\processual_api\integrations\training_secret_provider_binding.py
.\processual_api\main.py
.\processual_api\middleware\__init__.py
.\processual_api\middleware\subscription.py
.\processual_api\middleware\usage_log.py
.\processual_api\routers\__init__.py
.\processual_api\routers\applications.py
.\processual_api\routers\cgt.py
.\processual_api\routers\cgt_governor.py
.\processual_api\routers\client_api_keys_18.py
.\processual_api\routers\client_provider_alias_18.py
.\processual_api\routers\discord.py
.\processual_api\routers\governance.py
.\processual_api\routers\health.py
.\processual_api\routers\institution_cases_18.py
.\processual_api\routers\institution_qualification_18.py
.\processual_api\routers\reports.py
.\processual_api\routers\settings.py
.\processual_api\routers\telemetry.py
.\processual_api\routers\workflows.py
.\processual_api\schemas\settings.py
.\processual_api\services\admin_subscription_analytics.py
.\processual_api\services\api_key_store.py
.\processual_api\services\client_plan_source.py
.\processual_api\services\client_usage_summary.py
.\processual_api\services\discord_service.py
.\processual_api\services\enterprise_r10_binding_creation_18.py
.\processual_api\services\enterprise_r10_controlled_sandbox_18.py
.\processual_api\services\enterprise_r10_lifecycle_sync_18.py
.\processual_api\services\integration_readiness_tracking_store.py
.\processual_api\services\plan_store.py
.\processual_api\services\quota_store.py
.\processual_api\services\usage_log_store.py
.\processual_api\static\js\admin_actions.js
.\processual_api\static\js\admin_api_keys.js
.\processual_api\static\js\admin_client_requests.js
.\processual_api\static\js\admin_dashboard.js
.\processual_api\static\js\admin_integration_center_18.js
.\processual_api\static\js\admin_nav.js
.\processual_api\static\js\admin_operator_pilot_handoff_17c.js
.\processual_api\static\js\admin_runtime.js
.\processual_api\static\js\admin_subscription_analytics.js
.\processual_api\static\js\app.js
.\processual_api\static\js\pages\gateway.js
.\processual_api\static\js\pages\institution_workspace_18.js
.\processual_api\static\js\pages\settings.js
.\processual_api\static\js\settings_layout_18.js
.\processual_api\static\js\tour\tour-steps.js
.\processual_kernel\adaptive\checkpoints.py
.\processual_kernel\adaptive\contracts.py
.\processual_kernel\adaptive\efficiency.py
.\processual_kernel\adaptive\history.py
.\processual_kernel\adaptive\metrics.py
.\processual_kernel\adaptive\ops_governance.py
.\processual_kernel\adaptive\policy_critic.py
.\processual_kernel\adaptive\quality_gates.py
.\processual_kernel\adaptive\replay_lab.py
.\processual_kernel\adaptive\runtime_adapter.py
.\processual_kernel\adaptive\safety.py
.\processual_kernel\adaptive_toolkit.py
.\processual_kernel\adaptive_types.py
.\processual_kernel\governor.py
.\processual_kernel\kernel.py
.\processual_kernel\types.py
.\scripts\provider_experiments\run_real_multi_task_governance.py
.\tests\integration\test_auth_email_verification_r6a_integration.py
.\tests\integration\test_auth_login_sessions_r7_integration.py
.\tests\integration\test_auth_recovery_email_e2e_r8d_integration.py
.\tests\integration\test_auth_registration_http_r5b_r1_integration.py
.\tests\test_adapter_configure_status_routes.py
.\tests\test_adapter_readiness_endpoint.py
.\tests\test_adapter_registry.py
.\tests\test_adapter_test_readiness_behavior.py
.\tests\test_admin_api_key_external_usage_logging_regression.py
.\tests\test_admin_api_key_external_usage_regression.py
.\tests\test_admin_api_key_lifecycle_summary_ui.py
.\tests\test_admin_api_key_profile_payload_regression.py
.\tests\test_admin_api_key_profiles_regression.py
.\tests\test_admin_api_key_valid_runtime_acceptance_regression.py
.\tests\test_admin_area_shell_regression.py
.\tests\test_admin_audit_log.py
.\tests\test_admin_backend_dashboard_regression.py
.\tests\test_admin_backend_readiness_audit.py
.\tests\test_admin_client_request_apply_plan_regression.py
.\tests\test_admin_client_request_detail_regression.py
.\tests\test_admin_client_request_response_draft_regression.py
.\tests\test_admin_client_request_status_actions_regression.py
.\tests\test_admin_client_request_supervisor_response_lifecycle_regression.py
.\tests\test_admin_client_request_supervisor_response_regression.py
.\tests\test_admin_client_requests_inbox_regression.py
.\tests\test_admin_direct_client_plan_setting.py
.\tests\test_admin_direct_client_plan_ui.py
.\tests\test_admin_endpoint_registry_regression.py
.\tests\test_admin_integration_readiness_case_management_12a.py
.\tests\test_admin_integration_readiness_route_11k.py
.\tests\test_admin_integration_readiness_supervisor_scope_audit_12b.py
.\tests\test_admin_integration_readiness_tracking_route_11p.py
.\tests\test_admin_integration_readiness_tracking_summary_11o.py
.\tests\test_admin_marketplace_audit_contracts_r1.py
.\tests\test_admin_marketplace_authority_r1.py
.\tests\test_admin_marketplace_channel_policy_r1.py
.\tests\test_admin_marketplace_commercial_policy_repositories_r3.py
.\tests\test_admin_marketplace_contracts_r1.py
.\tests\test_admin_marketplace_exports_r1.py
.\tests\test_admin_marketplace_integrity_translation_r3.py
.\tests\test_admin_marketplace_migration_r2.py
.\tests\test_admin_marketplace_models_r2.py
.\tests\test_admin_marketplace_payment_repositories_r3.py
.\tests\test_admin_marketplace_repositories_r3.py
.\tests\test_admin_marketplace_repository_contracts_r3.py
.\tests\test_admin_marketplace_transactional_repositories_r3.py
.\tests\test_admin_marketplace_unit_of_work_r3.py
.\tests\test_admin_runtime_cards_regression.py
.\tests\test_admin_subscription_analytics_plan_sources.py
.\tests\test_admin_subscription_analytics_regression.py
.\tests\test_admin_subscription_analytics_risk_indicators.py
.\tests\test_admin_subscription_analytics_ui.py
.\tests\test_admin_supervisor_audit_summary_ui.py
.\tests\test_admin_supervisor_session_enforcement.py
.\tests\test_admin_supervisor_session_header.py
.\tests\test_admin_supervisor_session_key_routes.py
.\tests\test_admin_supervisor_session_route_storage_overrides_16g_r6.py
.\tests\test_api_key_quota_plan_regression.py
.\tests\test_api_key_settings_routes.py
.\tests\test_api_key_store.py
.\tests\test_applications_onboarding_regression.py
.\tests\test_auth_account_recovery_external_revocation_r9a.py
.\tests\test_auth_account_recovery_http_r9a.py
.\tests\test_auth_admin_credentials_production_hardening.py
.\tests\test_auth_delivery_operations_http_r9c.py
.\tests\test_auth_jwt_claims_regression.py
.\tests\test_auth_mfa_http_r8.py
.\tests\test_auth_recovery_email_http_r8d.py
.\tests\test_auth_registration_http_r5b_r1.py
.\tests\test_auth_scopes_regression.py
.\tests\test_auth_session_http_r7.py
.\tests\test_billing_pricing_catalog_route.py
.\tests\test_billing_subscription_regression.py
.\tests\test_byok_usage_logging_pricing_regression.py
.\tests\test_byok_usage_pricing.py
.\tests\test_cgt_governor_behavior.py
.\tests\test_cgt_governor_route_boundaries.py
.\tests\test_checkout_disabled_contract_09d_document.py
.\tests\test_client_api_key_integration_endpoint_regression.py
.\tests\test_client_api_key_operational_profile_request_11j.py
.\tests\test_client_api_key_operational_profiles_route_11h.py
.\tests\test_client_integration_guide_ui_regression.py
.\tests\test_client_plan_enterprise_eligibility_ui_regression.py
.\tests\test_client_plan_source_service.py
.\tests\test_client_provider_connection_endpoint_regression.py
.\tests\test_client_provider_secret_setup_ui_regression.py
.\tests\test_client_readiness_ui_regression.py
.\tests\test_client_requests_billing_endpoint_regression.py
.\tests\test_client_requests_billing_ui_regression.py
.\tests\test_client_sandbox_api_keys_18.py
.\tests\test_client_settings_collapsible_ui_regression.py
.\tests\test_client_settings_ui_regression.py
.\tests\test_client_supervisor_messages_ui_regression.py
.\tests\test_client_support_ui_regression.py
.\tests\test_client_usage_summary_endpoint_regression.py
.\tests\test_client_usage_summary_route_regression.py
.\tests\test_client_usage_summary_security_regression.py
.\tests\test_commercial_terms_review_09c_document.py
.\tests\test_connector_fake_sandbox_transport_16e_r4.py
.\tests\test_connector_mock_dispatcher_16d.py
.\tests\test_connector_sandbox_evidence_16e_r7.py
.\tests\test_connector_sandbox_pilot_16e_r1.py
.\tests\test_connector_sandbox_read_faults_16e_r6.py
.\tests\test_connector_sandbox_read_workflow_16e_r5.py
.\tests\test_connector_secret_manager_contracts_16e_r2.py
.\tests\test_connector_transport_contracts_16e_r3.py
.\tests\test_deployment_docs_alignment.py
.\tests\test_enterprise_qualification_decisions_18.py
.\tests\test_enterprise_r10_binding_creation_18.py
.\tests\test_enterprise_r10_binding_rebinding_18.py
.\tests\test_enterprise_r10_binding_store_18.py
.\tests\test_enterprise_r10_controlled_sandbox_18.py
.\tests\test_enterprise_r10_lifecycle_sync_18.py
.\tests\test_evaluation_store_regression.py
.\tests\test_external_connectivity_intake_service_r9.py
.\tests\test_external_connectivity_key_lifecycle_r10.py
.\tests\test_external_connectivity_key_routes_r10.py
.\tests\test_external_connectivity_r10_document_and_exports.py
.\tests\test_external_connectivity_r8_document.py
.\tests\test_external_connectivity_r9_document_and_exports.py
.\tests\test_external_connectivity_routes_r9.py
.\tests\test_fastapi_integration_smoke.py
.\tests\test_governance_gateway_behavior_regression.py
.\tests\test_governor_reports_regression.py
.\tests\test_identity_registration_contracts_r1.py
.\tests\test_institution_cases_18.py
.\tests\test_institution_qualification_activation_routes_18.py
.\tests\test_institution_qualification_read_routes_18.py
.\tests\test_institution_qualification_real_supervisor_session_18.py
.\tests\test_institution_qualification_write_routes_18.py
.\tests\test_integration_audit_11a_r1_document.py
.\tests\test_integration_claim_keys_13a.py
.\tests\test_integration_pilot_controls_13b.py
.\tests\test_integration_pilot_controls_validated_write_guard_15b_r4.py
.\tests\test_integration_sector_profiles.py
.\tests\test_integration_task_request_body_contract_16g_r7.py
.\tests\test_jwt_backend_dependency_regression.py
.\tests\test_login_gateway_actions_ui.py
.\tests\test_maestro_agent_identity_bridge_boundaries_m1_r4.py
.\tests\test_maestro_agent_identity_bridge_m1_r4.py
.\tests\test_maestro_agent_identity_carrier_boundaries_m1_r3.py
.\tests\test_maestro_agent_identity_carrier_m1_r3.py
.\tests\test_maestro_calibration_contracts_r1.py
.\tests\test_maestro_commercial_execution_identity_boundaries_m1_r2.py
.\tests\test_maestro_commercial_execution_identity_m1_r2.py
.\tests\test_maestro_execution_authority_boundaries_r2b.py
.\tests\test_maestro_execution_authority_r2b.py
.\tests\test_maestro_execution_authority_readiness_boundaries_r2c.py
.\tests\test_maestro_execution_family_evidence_boundaries_m1.py
.\tests\test_maestro_group1_pricing_review.py
.\tests\test_maestro_group1_pricing_review_boundaries.py
.\tests\test_maestro_group1_selected_pricing.py
.\tests\test_maestro_group1_selected_pricing_boundaries.py
.\tests\test_maestro_shadow_measurements_r2.py
.\tests\test_middleware_regression.py
.\tests\test_offer_fulfillment_policy.py
.\tests\test_offer_pricebook.py
.\tests\test_offer_pricebook_route.py
.\tests\test_operator_pilot_handoff_actions_14d.py
.\tests\test_operator_pilot_handoff_dashboard_ui_17c_r1.py
.\tests\test_operator_pilot_handoff_intake_preview_http_17c_r1.py
.\tests\test_operator_pilot_handoff_intake_preview_route_17c_r1.py
.\tests\test_operator_pilot_handoff_progress_routes_14e.py
.\tests\test_operator_pilot_handoff_routes_14b.py
.\tests\test_operator_readiness_package_12c.py
.\tests\test_operator_sandbox_intake_16f_r1.py
.\tests\test_outbound_allowlist_tls_readiness_16f_r3a.py
.\tests\test_pricing_commercial_supervisor_lesson_docs.py
.\tests\test_pricing_factors_surface_ui.py
.\tests\test_pricing_market_positioning_docs.py
.\tests\test_pricing_offers_surface_ui.py
.\tests\test_pricing_page_route_regression.py
.\tests\test_pricing_plan_allowance_catalog_regression.py
.\tests\test_pricing_quota_usage_log_metadata_regression.py
.\tests\test_pricing_rejection_usage_log_metadata_regression.py
.\tests\test_pricing_review_09a_document.py
.\tests\test_pricing_subscriptions_surface_ui.py
.\tests\test_pricing_unit_quota_enforcement_regression.py
.\tests\test_pricing_usage_ledger_schema_docs.py
.\tests\test_production_env_template_regression.py
.\tests\test_productization_pricing_surface_regression.py
.\tests\test_project_release_regression.py
.\tests\test_provider_metadata.py
.\tests\test_public_ci_workflow_boundary.py
.\tests\test_quota_store.py
.\tests\test_secret_encryption_readiness_regression.py
.\tests\test_secret_provider_binding_readiness_16f_r2a.py
.\tests\test_settings_persistence_safety.py
.\tests\test_stage18_integration_center_ui_r1.py
.\tests\test_static_console_smoke.py
.\tests\test_static_favicon_fallback.py
.\tests\test_subscription_pricing_catalog.py
.\tests\test_supervisor_session_write_guard_15b.py
.\tests\test_training_activation_lifecycle_16g_r3.py
.\tests\test_training_connection_request_16g_r1.py
.\tests\test_training_outbound_tls_approval_16g_r5.py
.\tests\test_training_secret_provider_binding_16g_r4.py
.\tests\test_unit_cost_assumptions.py
.\tests\test_unit_cost_assumptions_route.py
.\tests\test_workflow_kernel_regression.py
```

## Existing loading, state, accessibility, and permission patterns

```text
.\scripts\run_multi_agent_governance.py:193:                role=mode["role"],
.\scripts\run_multi_agent_governance.py:211:                role=mode["role"],
.\scripts\run_multi_agent_governance.py:246:    print(f"  Successful:   {len(valid)}")
.\scripts\run_external_pilot.py:347:                        role=mode["role"],
.\scripts\run_external_pilot.py:366:                        role=mode["role"],
.\scripts\release_check.py:202:        _ok("Docker public target builds successfully")
.\examples\demo_full_flow.py:53:            agent_id=agent_id, status="success",
.\examples\demo_full_flow.py:98:            success_rate=0.95, cooperation_success=0.90, useful_handoff_rate=0.80,
.\examples\demo_full_flow.py:102:            success_rate=0.55, cooperation_success=0.50, useful_handoff_rate=0.40,
.\examples\demo_full_flow.py:107:            success_rate=0.30, cooperation_success=0.25, useful_handoff_rate=0.15,
.\examples\basic_usage.py:32:        success_rate=0.95, cooperation_success=0.90, useful_handoff_rate=0.8,
.\examples\basic_usage.py:36:        success_rate=0.25, cooperation_success=0.20, useful_handoff_rate=0.1,
.\examples\basic_usage.py:41:        success_rate=0.55, cooperation_success=0.50, useful_handoff_rate=0.4,
.\processual_kernel\types.py:79:    success_rate: float = 1.0
.\processual_kernel\types.py:80:    cooperation_success: float = 0.5
.\scripts\provider_experiments\run_real_multi_task_governance.py:188:    lines.append(f"- Successful governance runs: `{ok_count}/{total_count}`.")
.\alembic\versions\20260721_0001_identity_auth_foundation.py:56:            "status IN ('pending_verification', 'active', 'locked', 'disabled', 'deleted')",
.\alembic\versions\20260721_0001_identity_auth_foundation.py:241:        sa.Column("disabled_at", sa.DateTime(timezone=True), nullable=True),
.\alembic\versions\20260721_0001_identity_auth_foundation.py:246:            "status IN ('pending', 'active', 'disabled')",
.\processual_kernel\continuity.py:24:        synergy = clamp(0.45 * m.cooperation_success + 0.35 * m.useful_handoff_rate + 0.20 * m.success_rate)
.\tests\test_adapter_test_readiness_behavior.py:78:def test_adapter_test_returns_metadata_on_success(monkeypatch):
.\processual_kernel\adaptive_types.py:150:    success_probability_delta: float = 0.0
.\processual_kernel\adaptive_types.py:244:    success_probability_delta: float = 0.0
.\processual_kernel\adaptive_types.py:251:    workflow_success_rate: float
.\processual_kernel\adaptive_types.py:254:    cost_per_successful_workflow: float
.\processual_kernel\adaptive_types.py:261:    policy_patch_success_rate: float
.\processual_kernel\adaptive_toolkit.py:145:        self._successful_patch_versions: set[str] = set()
.\processual_kernel\adaptive_toolkit.py:599:        self._successful_patch_versions.add(patch.policy_version_to)
.\processual_kernel\adaptive_toolkit.py:621:        self._successful_patch_versions.discard(patch.policy_version_to)
.\processual_kernel\adaptive_toolkit.py:1032:        success_probability_delta: float | None = None,
.\processual_kernel\adaptive_toolkit.py:1079:                    inferred_result = "success"
.\processual_kernel\adaptive_toolkit.py:1092:                else (0.10 if inferred_result == "success" else (-0.08 if inferred_result == "failed" else 0.0))
.\processual_kernel\adaptive_toolkit.py:1097:                success_probability_delta
.\processual_kernel\adaptive_toolkit.py:1098:                if success_probability_delta is not None
.\processual_kernel\adaptive_toolkit.py:1099:                else (0.10 * progress if inferred_result in {"success", "observed", "partial"} else -0.10)
.\processual_kernel\adaptive_toolkit.py:1109:                success_probability_delta=sp_delta,
.\processual_kernel\adaptive_toolkit.py:1313:            mediator_agent_role="Synthesizer" if suggestion.recommend_mediator else None,
.\processual_kernel\adaptive_toolkit.py:1555:            successful_patch_versions=self._successful_patch_versions,
.\processual_kernel\notifications\templates.py:45:        "color": 5814783 if status == "success" else 15158332,
.\processual_kernel\notifications\discord.py:32:            return {"sent": False, "reason": "notifier disabled or no webhook URL"}
.\processual_kernel\kernel.py:123:            success_rate=1.0 if result.ok else 0.0,
.\processual_kernel\kernel.py:124:            cooperation_success=0.6,
.\processual_kernel\kernel.py:351:                success_rate=1.0 if result.ok else 0.0,
.\processual_kernel\kernel.py:352:                cooperation_success=0.65 if result.ok else 0.25,
.\tests\integration\test_auth_delivery_multi_worker_concurrency_r9d_integration.py:586:        successful = [
.\tests\integration\test_auth_delivery_multi_worker_concurrency_r9d_integration.py:592:        assert len(successful) == 1
.\tests\integration\test_auth_delivery_multi_worker_concurrency_r9d_integration.py:594:        winner = successful[0]
.\tests\test_admin_audit_log.py:9:def test_admin_audit_event_store_writes_safe_success_event(tmp_path):
.\tests\test_admin_audit_log.py:27:        result="success",
.\tests\test_admin_audit_log.py:42:    assert event["result"] == "success"
.\tests\test_admin_audit_log.py:90:        result="success",
.\tests\test_admin_audit_log.py:218:def test_admin_request_status_route_records_success_and_denied_audit(
.\tests\test_admin_audit_log.py:258:    success = events[0]
.\tests\test_admin_audit_log.py:259:    assert success["actor"] == "reviewer@example.test"
.\tests\test_admin_audit_log.py:260:    assert success["actor_level"] == "review_supervisor"
.\tests\test_admin_audit_log.py:261:    assert success["session_key_id"] == "supsk_review_audit"
.\tests\test_admin_audit_log.py:262:    assert success["target_type"] == "client_request"
.\tests\test_admin_audit_log.py:263:    assert success["target_id"] == "creq_audit_route"
.\tests\test_admin_audit_log.py:264:    assert success["client_id"] == "client-audit"
.\tests\test_admin_audit_log.py:265:    assert success["source"] == "admin_clients_panel"
.\tests\test_admin_audit_log.py:266:    assert success["result"] == "success"
.\tests\test_admin_audit_log.py:267:    assert success["safe_note"] == "Client request status updated to reviewed."
.\tests\test_admin_audit_log.py:268:    assert success["request_path"].endswith("/status")
.\tests\test_admin_audit_log.py:318:    assert events[0]["result"] == "success"
.\tests\test_admin_audit_log.py:381:    assert events[0]["result"] == "success"
.\tests\test_admin_client_request_supervisor_response_lifecycle_regression.py:18:    assert "disable" in admin_js.lower() or ".disabled" in admin_js
.\tests\test_admin_api_key_valid_runtime_acceptance_regression.py:55:        role="client",
.\tests\test_admin_api_key_profile_payload_regression.py:61:        role="partner",
.\tests\test_admin_api_key_profile_payload_regression.py:119:        role="service",
.\tests\test_admin_api_key_lifecycle_summary_ui.py:58:    assert "Loading API key lifecycle summary" in source
.\tests\test_admin_api_key_profiles_regression.py:146:        "LEMONSQUEEZY_SUCCESS_URL",
.\tests\test_admin_api_key_external_usage_regression.py:40:        role="client",
.\tests\test_admin_api_key_external_usage_logging_regression.py:66:        role="client",
.\processual_kernel\adaptive\runtime_adapter.py:88:                reason="blocked because command is not authorized",
.\processual_kernel\adaptive\quality_gates.py:16:        min_patch_success_rate: float = 0.80,
.\processual_kernel\adaptive\quality_gates.py:24:        self.min_patch_success_rate = min_patch_success_rate
.\processual_kernel\adaptive\quality_gates.py:51:        if metrics.policy_patch_success_rate < self.min_patch_success_rate:
.\processual_kernel\adaptive\quality_gates.py:53:                f"policy patch success rate {metrics.policy_patch_success_rate:.2f} "
.\processual_kernel\adaptive\quality_gates.py:54:                f"below {self.min_patch_success_rate:.2f}"
.\processual_kernel\adaptive\outcome_evaluator.py:26:        success_probability_delta: float = 0.0,
.\processual_kernel\adaptive\outcome_evaluator.py:35:            success_probability_delta,
.\processual_kernel\adaptive\outcome_evaluator.py:47:            success_probability_delta=success_probability_delta,
.\processual_kernel\adaptive\outcome_evaluator.py:61:        success_probability_delta: float,
.\processual_kernel\adaptive\outcome_evaluator.py:64:        success_bias = 0.20 if actual_result.lower() in {"success", "improved", "recovered"} else -0.15
.\processual_kernel\adaptive\outcome_evaluator.py:65:        # Positive quality/success deltas help. Negative cost/latency/recovery deltas help.
.\processual_kernel\adaptive\outcome_evaluator.py:67:        raw += success_bias
.\processual_kernel\adaptive\outcome_evaluator.py:69:        raw += 0.20 * success_probability_delta
.\tests\test_admin_rbac_ui_reflection.py:52:        "data-disabled-reason",
.\processual_kernel\adaptive\ops_governance.py:92:        if metrics.policy_patch_success_rate < 0.5 and requested_mode == RuntimeMode.CONTROLLED_ADAPTIVE:
.\processual_kernel\adaptive\ops_governance.py:93:            violations.append("policy patch success rate is too low for controlled adaptation")
.\processual_kernel\adaptive\ops_governance.py:146:            if not regressions and metrics.policy_patch_success_rate >= 0.80:
.\processual_kernel\adaptive\metrics.py:11:    """Aggregates the success metrics named by the technical paper.
.\processual_kernel\adaptive\metrics.py:24:        successful_patch_versions: Iterable[str] = (),
.\processual_kernel\adaptive\metrics.py:32:        successful_versions = set(successful_patch_versions)
.\processual_kernel\adaptive\metrics.py:35:        workflow_success_rate = completed / len(workflows) if workflows else 0.0
.\processual_kernel\adaptive\metrics.py:40:        successful_workflows = max(1, completed)
.\processual_kernel\adaptive\metrics.py:42:        cost_per_successful_workflow = cost_pressure_sum / successful_workflows if workflows else 0.0
.\processual_kernel\adaptive\metrics.py:76:            successful = sum(1 for p in patch_list if p.policy_version_to in successful_versions or p.reason)
.\processual_kernel\adaptive\metrics.py:77:            policy_patch_success_rate = successful / len(patch_list)
.\processual_kernel\adaptive\metrics.py:79:            policy_patch_success_rate = 1.0
.\processual_kernel\adaptive\metrics.py:84:            workflow_success_rate=round(workflow_success_rate, 4),
.\processual_kernel\adaptive\metrics.py:87:            cost_per_successful_workflow=round(cost_per_successful_workflow, 4),
.\processual_kernel\adaptive\metrics.py:94:            policy_patch_success_rate=round(policy_patch_success_rate, 4),
.\tests\test_admin_supervisor_session_browser_proof_regression.py:71:    assert "data-disabled-reason" in source
.\processual_kernel\adaptive\history.py:105:                success_probability_delta=outcome.success_probability_delta,
.\tests\test_admin_supervisor_session_key_routes.py:104:    assert events[0]["result"] == "success"
.\processual_kernel\adaptive\efficiency.py:84:                reason="checkpoint coalescing disabled or not applicable",
.\processual_kernel\adaptive\efficiency.py:389:                reasons.append(f"command {index} allowed because throttling is disabled")
.\processual_kernel\adaptive\efficiency.py:707:            reason = "adaptive workload budget disabled this optional operation"
.\tests\test_admin_supervisor_session_route_storage_overrides_16g_r6.py:180:    assert events[0]["result"] == "success"
.\tests\test_admin_supervisor_stats_ui.py:59:    assert "Loading supervisor overview" in source
.\processual_kernel\adaptive\contracts.py:91:            warnings.append("audit is disabled for this contract; adaptive evidence will be weaker")
.\processual_api\static\js\admin_client_requests.js:270:        button.dataset.supervisorDisabledReason ||
.\processual_api\static\js\admin_client_requests.js:271:        button.getAttribute('data-disabled-reason') ||
.\processual_api\static\js\admin_client_requests.js:316:      button.dataset.supervisorDisabledReason = reason;
.\processual_api\static\js\admin_client_requests.js:322:      button.removeAttribute('data-disabled-reason');
.\processual_api\static\js\admin_client_requests.js:323:      if (button.dataset.rbacDisabled === 'true') {
.\processual_api\static\js\admin_client_requests.js:324:        button.disabled = false;
.\processual_api\static\js\admin_client_requests.js:325:        delete button.dataset.rbacDisabled;
.\processual_api\static\js\admin_client_requests.js:333:    const disabledReason =
.\processual_api\static\js\admin_client_requests.js:335:    button.disabled = true;
.\processual_api\static\js\admin_client_requests.js:336:    button.dataset.rbacDisabled = 'true';
.\processual_api\static\js\admin_client_requests.js:337:    button.setAttribute('data-disabled-reason', disabledReason);
.\processual_api\static\js\admin_client_requests.js:338:    button.title = disabledReason;
.\processual_api\static\js\admin_client_requests.js:453:  function renderAdminClientApiKeysQuickBridge(parent) {   if (!parent || document.getElementById('admin-client-api-keys-quick-bridge')) return;   const panel = document.createElement('section');   panel.id = 'admin-client-api-keys-quick-bridge';   panel.className = 'admin-client-request-panel';   panel.setAttribute('aria-label', 'Admin API Keys quick bridge');   const title = document.createElement('h3');   title.textContent = 'Integration API Keys';   panel.appendChild(title);   const note = document.createElement('p');   note.className = 'text-muted';   note.textContent = 'Open the Admin API Keys panel from the Clients area. Select a client request first to pre-fill client-specific metadata.';   panel.appendChild(note);   const actions = document.createElement('div');   actions.className = 'admin-client-request-actions';   const button = document.createElement('button');   button.id = 'admin-client-open-api-keys-panel';   button.className = 'btn sm';   button.type = 'button';   button.textContent = 'Open Integration API Keys';   button.addEventListener('click', () => {     const payload = {       source: 'admin_clients_quick_bridge',       key_profile: 'service_integration',       category: 'service_integration',       production_connector_approved: false,       raw_secret_visible: false,     };     try {       sessionStorage.setItem(ADMIN_INTEGRATION_KEY_BRIDGE_STORAGE, JSON.stringify(payload));     } catch {}     window.dispatchEvent(new CustomEvent('pmk-admin-integration-key-bridge', { detail: payload }));     const target = document.getElementById('admin-api-key-client-id') || document.getElementById('admin-api-key-create-result') || document.getElementById('admin-api-key-table');     if (target && target.scrollIntoView) {       target.scrollIntoView({ behavior: 'smooth', block: 'center' });     }   });   actions.appendChild(button);   const status = document.createElement('div');   status.id = 'admin-client-api-keys-quick-bridge-status';   status.className = 'admin-status';   status.textContent = 'Visible admin shortcut only. No raw secret is shown and no production connector is approved.';   actions.appendChild(status);   panel.appendChild(actions);   parent.appendChild(panel); } function renderCounts(counts) {
.\processual_api\static\js\admin_client_requests.js:663:      button.dataset.supervisorDisabledReason =
.\processual_api\static\js\admin_client_requests.js:763:    select.setAttribute('aria-label', 'Direct client plan');
.\processual_api\static\js\admin_client_requests.js:781:    button.dataset.supervisorDisabledReason =
.\processual_api\static\js\admin_client_requests.js:1045:    send.disabled = isLatestDraftSent;
.\processual_api\static\js\admin_client_requests.js:1359:    panel.setAttribute('aria-label', 'Admin integration key bridge');
.\processual_api\static\js\admin_client_requests.js:1461:        'Loading detail for request ' + text(requestId) + ' ...';
.\processual_api\static\js\admin_client_requests.js:1533:        'Loading admin client requests from ' + ENDPOINT + ' ...';
.\processual_api\static\js\admin_client_requests.js:1674:  if (document.readyState === 'loading') {
.\processual_api\static\js\admin_client_requests.js:1708:    card.setAttribute("aria-label", "Admin integration readiness");
.\processual_api\static\js\admin_client_requests.js:1719:      "<pre id=\"admin-integration-readiness-body\" class=\"mono-block\">Loading integration readiness...</pre>",
.\processual_api\static\js\admin_client_requests.js:1782:  if (document.readyState === "loading") {
.\processual_api\static\js\admin_client_requests.js:1853:    card.setAttribute("aria-label", "Supervisor integration readiness workflow");
.\processual_api\static\js\admin_client_requests.js:1873:      <dl class="settings-summary-grid" aria-label="Supervisor readiness summary">
.\processual_api\static\js\admin_client_requests.js:1926:        aria-label="Safe supervisor response draft"
.\processual_api\static\js\admin_client_requests.js:2112:  if (document.readyState === "loading") {
.\processual_api\static\js\admin_client_requests.js:2170:    card.setAttribute("aria-label", "Admin integration readiness tracking summary");
.\processual_api\static\js\admin_client_requests.js:2189:      <dl class="settings-summary-grid" aria-label="Integration readiness tracking counters">
.\processual_api\static\js\admin_client_requests.js:2219:        aria-label="Integration readiness tracking cases"
.\processual_api\static\js\admin_client_requests.js:2244:        Empty state is intentional: current readiness checks are declarative.
.\processual_api\static\js\admin_client_requests.js:2390:  if (document.readyState === "loading") {
.\processual_api\static\js\admin_client_requests.js:2430:    host.setAttribute("aria-label", "Integration readiness case management");
.\processual_api\static\js\admin_client_requests.js:2435:      "<div data-admin-integration-readiness-case-table data-admincase12a=\"case-table\">Loading integration readiness casesÃ”Ã‡Âª</div>",
.\processual_api\static\js\admin_client_requests.js:2470:      "<button type=\"button\" disabled data-admin-integration-readiness-item-action-provided>Mark Provided</button>",
.\processual_api\static\js\admin_client_requests.js:2471:      "<button type=\"button\" disabled data-admin-integration-readiness-item-action-verified>Verify</button>",
.\processual_api\static\js\admin_client_requests.js:2472:      "<button type=\"button\" disabled data-admin-integration-readiness-item-action-rejected>Reject</button>",
.\processual_api\static\js\admin_client_requests.js:2613:    button.disabled = true;
.\processual_api\static\js\admin_client_requests.js:2632:      button.disabled = false;
.\processual_api\static\js\admin_client_requests.js:2667:    if (providedButton && !providedButton.disabled) {
.\processual_api\static\js\admin_client_requests.js:2674:    if (verifiedButton && !verifiedButton.disabled) {
.\processual_api\static\js\admin_client_requests.js:2681:    if (rejectedButton && !rejectedButton.disabled) {
.\processual_api\static\js\admin_client_requests.js:2692:  if (document.readyState === "loading") {
.\processual_api\static\js\admin_client_requests.js:2845:  if (document.readyState === "loading") {
.\processual_api\static\js\admin_client_requests.js:2961:      host.setAttribute("aria-label", "Integration claim keys");
.\processual_api\static\js\admin_client_requests.js:3086:                              ${claim.revoked ? "disabled" : ""}
.\processual_api\static\js\admin_client_requests.js:3138:  if (document.readyState === "loading") {
.\processual_api\admin_audit_log.py:14:_ALLOWED_RESULTS = frozenset({"success", "denied", "already_sent", "failure"})
.\processual_api\static\js\admin_api_key_summary.js:139:      <div class="mono-block" style="font-size:11px;white-space:pre-wrap">Loading API key lifecycle summary...</div>
.\processual_api\static\js\admin_api_keys.js:500:          <span class="admin-api-key-metadata-card-toggle" aria-hidden="true">
.\processual_api\static\js\admin_api_keys.js:554:    target.innerHTML = '<div class="admin-note">Loading supervisor session key metadata ...</div>';
.\processual_api\static\js\admin_api_keys.js:685:    target.innerHTML = '<div class="admin-note">Loading API key metadata from /settings/api-keys ...</div>';
.\processual_api\static\js\admin_api_keys.js:845:  if (document.readyState === 'loading') {
.\processual_api\static\js\admin_api_keys.js:924:  if (document.readyState === 'loading') {
.\processual_api\billing\maestro_group1_pricing_review.py:235:            raise PricingReviewValidationError("checkout must remain disabled during pricing review")
.\processual_api\static\js\admin_adapters.js:20:    btn.disabled = busy;
.\processual_api\static\js\admin_actions.js:72:  if (document.readyState === 'loading') {
.\processual_api\billing\router.py:41:def _get_success_url() -> str:
.\processual_api\billing\router.py:42:    return os.environ.get("LEMONSQUEEZY_CHECKOUT_SUCCESS_URL", "https://yourdomain.com/console")
.\processual_api\billing\router.py:129:                        "success_url": _get_success_url(),
.\processual_api\services\usage_log_store.py:195:    successful_units = 0
.\processual_api\services\usage_log_store.py:198:    successful_requests = 0
.\processual_api\services\usage_log_store.py:210:        is_success = 200 <= status_code < 400 and not quota_rejected
.\processual_api\services\usage_log_store.py:212:        if is_success:
.\processual_api\services\usage_log_store.py:213:            successful_requests += 1
.\processual_api\services\usage_log_store.py:214:            successful_units += units
.\processual_api\services\usage_log_store.py:274:        "successful_requests": successful_requests,
.\processual_api\services\usage_log_store.py:277:        "successful_units": successful_units,
.\processual_api\billing\offer_fulfillment_policy.py:17:    "activation_policy": "automatic_after_successful_payment",
.\processual_api\billing\offer_fulfillment_policy.py:26:    "success_criteria": [
.\processual_api\billing\offer_fulfillment_policy.py:52:    "activation_policy": "automatic_after_successful_payment",
.\processual_api\billing\maestro_reference_workloads.py:62:        "Simple successful automation",
.\processual_api\billing\maestro_reference_workloads.py:111:        "Single successful integration action",
.\processual_api\billing\maestro_reference_workloads.py:119:        "Four successful integration actions",
.\processual_api\billing\maestro_reference_workloads.py:127:        "Twenty successful integration actions",
.\processual_api\billing\maestro_reference_workloads.py:141:        notes="Only successful actions are represented.",
.\processual_api\billing\maestro_group1_selected_pricing.py:11:- checkout, invoicing, settlement, and quota enforcement disabled.
.\processual_api\services\operator_readiness_package.py:99:            "step_key": "pilot_success_criteria",
.\processual_api\services\operator_readiness_package.py:100:            "label": "Pilot success criteria",
.\processual_api\services\operator_readiness_package.py:120:            "label": "Runtime connector approval is disabled",
.\processual_api\static\js\tour\tour-engine.js:236:    showToast(_lang === 'ar' ? 'ÃÂºâ”˜Ã¢ÃÂ¬â”˜Ã â”˜Ã¤ÃÂ¬ ÃÂºâ”˜Ã¤ÃÂ¼â”˜Ãªâ”˜Ã¤ÃÂ®!' : 'Tour completed!', 'success');
.\processual_api\static\js\settings_operations_18.js:6:    loading: false,
.\processual_api\static\js\settings_operations_18.js:36:        return `<option value="${esc(profile.profile_id)}" ${selfService ? '' : 'disabled'}>${esc(profile.display_name)} â”¬Ã€ ${suffix}</option>`;
.\processual_api\static\js\settings_operations_18.js:103:            <select id="sops-profile" class="sops-select" ${integrationEnabled ? '' : 'disabled'}>
.\processual_api\static\js\settings_operations_18.js:107:            <input id="sops-label" class="sops-input" value="Institution sandbox" maxlength="120" placeholder="Key label" ${integrationEnabled ? '' : 'disabled'}>
.\processual_api\static\js\settings_operations_18.js:108:            <select id="sops-expiry" class="sops-select" ${integrationEnabled ? '' : 'disabled'}><option value="30">30 days</option><option value="60">60 days</option><option value="90">90 days</option></select>
.\processual_api\static\js\settings_operations_18.js:110:          <div class="sops-actions"><button class="sops-btn" data-sops-create ${integrationEnabled ? '' : 'disabled'}>Create sandbox key</button><button class="sops-btn ghost" data-sops-refresh>Refresh</button></div>
.\processual_api\static\js\settings_operations_18.js:112:          ${state.message ? `<div class="sops-note sops-success">${esc(state.message)}</div>` : ''}
.\processual_api\static\js\settings_operations_18.js:124:    if (state.loading) return;
.\processual_api\static\js\settings_operations_18.js:125:    state.loading = true;
.\processual_api\static\js\settings_operations_18.js:159:      state.loading = false;
.\processual_api\static\js\settings_operations_18.js:184:      state.message = 'Sandbox key created successfully.';
.\processual_api\static\js\settings_operations_18.js:247:      APP.showToast('API key copied', 'success');
.\processual_api\static\js\settings_operations_18.js:277:  if (document.readyState === 'loading') {
.\processual_api\services\operator_pilot_handoff_actions.py:82:        "action_id": "request_pilot_success_criteria",
.\processual_api\services\operator_pilot_handoff_actions.py:83:        "label": "Request pilot success criteria",
.\processual_api\services\discord_service.py:153:    if "created" in event or "success" in event:
.\processual_api\static\js\settings_layout_18.js:113:      tabs.setAttribute('aria-label', 'Client settings sections');
.\processual_api\static\js\settings_layout_18.js:119:          role="tab"
.\processual_api\static\js\settings_layout_18.js:120:          aria-selected="false"
.\processual_api\static\js\settings_layout_18.js:412:          'aria-selected',
.\processual_api\static\js\settings_layout_18.js:537:  if (document.readyState === 'loading') {
.\processual_api\services\operator_pilot_handoff.py:249:PILOT_SUCCESS_CRITERIA = [
.\processual_api\services\operator_pilot_handoff.py:304:        "pilot_success_criteria": deepcopy(PILOT_SUCCESS_CRITERIA),
.\processual_api\services\operator_pilot_handoff.py:347:    success_criteria = list(package.get("pilot_success_criteria") or [])
.\processual_api\services\operator_pilot_handoff.py:408:    lines.extend(["", "## Pilot success criteria", ""])
.\processual_api\services\operator_pilot_handoff.py:410:    if success_criteria:
.\processual_api\services\operator_pilot_handoff.py:411:        for item in success_criteria:
.\processual_api\services\api_key_store.py:138:            if status in {"revoked", "disabled", "expired"}:
.\processual_api\services\admin_subscription_analytics.py:137:    if status in {"suspended", "disabled", "blocked"}:
.\processual_api\services\admin_subscription_analytics.py:146:    if status in {"revoked", "disabled", "inactive", "expired"}:
.\processual_api\services\admin_subscription_analytics.py:152:    return bool(record.get("revoked_at") or record.get("disabled_at"))
.\processual_api\services\admin_subscription_analytics.py:452:        if raw_subscription_status in {"suspended", "disabled", "blocked"}:
.\processual_api\services\admin_subscription_analytics.py:459:                message="Subscription is suspended or disabled.",
.\processual_api\services\integration_pilot_controls.py:43:DISABLED_STATUSES: set[str] = {
.\processual_api\services\integration_pilot_controls.py:253:        "sandbox_grant_disabled": True,
.\processual_api\services\integration_pilot_controls.py:255:        "runtime_connector_grant_disabled": True,
.\processual_api\services\integration_pilot_controls.py:338:        task["sandbox_grant_disabled"] = True
.\processual_api\services\integration_pilot_controls.py:339:        task["runtime_connector_grant_disabled"] = True
.\processual_api\services\integration_pilot_controls.py:363:        sandbox_grant_disabled=task["sandbox_grant_disabled"],
.\processual_api\services\integration_pilot_controls.py:364:        runtime_connector_grant_disabled=task["runtime_connector_grant_disabled"],
.\processual_api\services\integration_pilot_controls.py:393:    if task.get("status") in DISABLED_STATUSES:
.\processual_api\services\integration_pilot_controls.py:431:    task["sandbox_grant_disabled"] = True
.\processual_api\services\integration_pilot_controls.py:432:    task["runtime_connector_grant_disabled"] = True
.\processual_api\services\integration_pilot_controls.py:448:        sandbox_grant_disabled=True,
.\processual_api\services\integration_pilot_controls.py:449:        runtime_connector_grant_disabled=True,
.\processual_api\services\integration_pilot_controls.py:503:        or task.get("status") in DISABLED_STATUSES
.\processual_api\services\enterprise_r10_controlled_sandbox_18.py:53:    "telecom_ticketing_disabled_no_network_transport"
.\processual_api\schemas\settings.py:53:    success: bool
.\tests\test_auth_account_recovery_repository_r9a.py:161:        disabled_at=NOW,
.\tests\test_auth_delivery_operations_http_r9c.py:208:async def test_redrive_success_returns_generic_acceptance():
.\tests\test_auth_delivery_dispatcher_r6b.py:174:def test_dispatch_success_uses_stable_idempotency_and_marks_claim_delivered():
.\processual_api\static\js\pages\workflows.js:20:        APP.showToast('Workflow ' + id + ' created', 'success');
.\processual_api\static\js\pages\workflows.js:28:  if (document.readyState !== 'loading') init(); else document.addEventListener('DOMContentLoaded', init);
.\processual_api\static\js\pages\telemetry.js:37:        APP.showToast('Ingested ' + metric + ' = ' + value, 'success');
.\processual_api\static\js\pages\telemetry.js:101:  if (document.readyState !== 'loading') init(); else document.addEventListener('DOMContentLoaded', init);
.\processual_api\static\js\pages\simulation.js:30:    APP.showLoading('sim-run-btn', 'Running...');
.\processual_api\static\js\pages\simulation.js:36:      APP.showToast('Simulation complete: ' + res.total_agents + ' agents evaluated', 'success');
.\processual_api\static\js\pages\simulation.js:42:    APP.hideLoading('sim-run-btn');
.\processual_api\static\js\pages\simulation.js:108:      if (sig && sig !== 'Ã”Ã‡Ã¶') { navigator.clipboard.writeText(sig); APP.showToast('Signature copied', 'success'); }
.\processual_api\static\js\pages\simulation.js:118:          APP.showToast('PDF downloaded', 'success');
.\processual_api\static\js\pages\simulation.js:124:  if (document.readyState !== 'loading') init(); else document.addEventListener('DOMContentLoaded', init);
.\tests\test_auth_account_recovery_contracts_r9a.py:75:            role="platform_admin",
.\tests\test_auth_admin_credentials_production_hardening.py:110:                    role="admin",
.\tests\test_auth_account_recovery_service_r9a.py:216:        disabled_at,
.\tests\test_auth_account_recovery_service_r9a.py:410:        ("disabled", "verified", True, False),
.\processual_api\static\js\pages\settings.js:318:  function normalizeIntegrationOperationalProfiles(info) {   const profiles = info && Array.isArray(info.operational_profiles) ? info.operational_profiles : [];   return profiles.filter((profile) => profile && profile.client_visible === true); } function integrationProfileScopes(profile, key) {   const scopes = Array.isArray(profile && profile[key]) ? profile[key] : [];   return scopes.length ? scopes.join(", ") : "-"; } function integrationOperationalProfileLabel(profile) {   return (profile.profile_id || "-") + " / " + (profile.display_name || "Operational profile"); } function selectedIntegrationOperationalProfile(info) {   const profiles = normalizeIntegrationOperationalProfiles(info);   const select = document.getElementById("set-api-key-operational-profile-selector");   const selected = select ? select.value : "";   return profiles.find((profile) => profile.profile_id === selected) || profiles[0] || null; } function renderIntegrationOperationalProfileSelector(info) {   const select = document.getElementById("set-api-key-operational-profile-selector");   if (!select) return;   const profiles = normalizeIntegrationOperationalProfiles(info);   const previous = select.value;   select.innerHTML = "";   const placeholder = document.createElement("option");   placeholder.value = "";   placeholder.textContent = "Choose operational purpose";   select.appendChild(placeholder);   profiles.forEach((profile) => {     const option = document.createElement("option");     option.value = profile.profile_id || "";     option.textContent = integrationOperationalProfileLabel(profile);     select.appendChild(option);   });   const profileIds = profiles.map((profile) => profile.profile_id);   if (profiles.length) {     select.value = profileIds.includes(previous) ? previous : profiles[0].profile_id;   }   select.disabled = profiles.length === 0;   setText("set-api-key-operational-profile-count", formatNumber(info?.operational_profile_count ?? profiles.length));   setText("set-api-key-operational-profile-enabled", String(info?.operational_profiles_enabled === true)); } function renderSelectedIntegrationOperationalProfile(info) {   const profile = selectedIntegrationOperationalProfile(info);   if (!profile) {     setText("set-api-key-operational-profile-summary", "No operational profiles available for this client plan.");     setText("set-api-key-operational-profile-allowed-scopes", "-");     setText("set-api-key-operational-profile-forbidden-scopes", "-");     setText("set-api-key-operational-profile-readiness", "Integration readiness is required before production work.");     setText("set-api-key-operational-profile-safety", "Production connector approval remains separate. Runtime connectors are not approved from this selector. Raw integration secrets are never displayed.");     return;   }   const mode = profile.read_only === true ? "read_only" : "sandbox_write_review";   setText("set-api-key-operational-profile-summary", [     "profile_id=" + (profile.profile_id || "-"),     "display_name=" + (profile.display_name || "-"),     "base_key_profile=" + (profile.base_key_profile || "-"),     "environment=" + (profile.environment || "sandbox"),     "mode=" + mode,     "next_action=" + (profile.next_action || "-"),   ].join("\n"));   setText("set-api-key-operational-profile-allowed-scopes", integrationProfileScopes(profile, "allowed_scopes"));   setText("set-api-key-operational-profile-forbidden-scopes", integrationProfileScopes(profile, "forbidden_scopes"));   setText("set-api-key-operational-profile-readiness", [     "requires_enterprise_plan=" + String(profile.requires_enterprise_plan === true),     "requires_integration_readiness=" + String(profile.requires_integration_readiness === true),     "requires_supervisor_for_write=" + String(profile.requires_supervisor_for_write === true),     "production_allowed=" + String(profile.production_allowed === true),     "runtime_connector_approved=" + String(profile.runtime_connector_approved === true),   ].join("\n"));   setText("set-api-key-operational-profile-safety", "Production connector approval remains separate. Runtime connectors are not approved from this selector. Raw integration secrets are never displayed."); } function initIntegrationOperationalProfileSelector() {   const select = document.getElementById("set-api-key-operational-profile-selector");   if (!select || select.dataset.profileSelectorReady === "true") return;   select.dataset.profileSelectorReady = "true";   select.addEventListener("change", () => {     renderSelectedIntegrationOperationalProfile(readinessState.integration || {});   }); } function applyApiKeyIntegration(info) {
.\processual_api\static\js\pages\settings.js:473:      const message = result.success
.\processual_api\static\js\pages\settings.js:477:      APP.showToast(message, result.success ? 'success' : 'error');
.\processual_api\static\js\pages\settings.js:499:      APP.showToast('Provider connection saved', 'success');
.\processual_api\static\js\pages\settings.js:511:      APP.showToast('Provider connection cleared', 'success');
.\processual_api\static\js\pages\settings.js:760:    if (submitBtn) submitBtn.disabled = true;
.\processual_api\static\js\pages\settings.js:765:      APP.showToast('Client request submitted', 'success');
.\processual_api\static\js\pages\settings.js:770:      if (submitBtn) submitBtn.disabled = false;
.\processual_api\static\js\pages\settings.js:824:    if (sendBtn) sendBtn.disabled = true;
.\processual_api\static\js\pages\settings.js:830:      APP.showToast('Supervisor message sent', 'success');
.\processual_api\static\js\pages\settings.js:835:      if (sendBtn) sendBtn.disabled = false;
.\processual_api\static\js\pages\settings.js:888:      : "loading";
.\processual_api\static\js\pages\settings.js:893:      { ok: usageOk, label: "3. Review usage and quota summary", status: usageOk ? "available" : "loading", action: "usage" },
.\processual_api\static\js\pages\settings.js:930:      setText("set-launch-action-status", "Reloading client settings...");
.\processual_api\static\js\pages\settings.js:1058:    if (!integration) return { ok: false, status: 'loading' };
.\processual_api\static\js\pages\settings.js:1071:    if (!provider) return { ok: false, status: 'loading' };
.\processual_api\static\js\pages\settings.js:1080:    if (!requests) return { ok: false, status: 'loading' };
.\processual_api\static\js\pages\settings.js:1109:        status: accountOk ? 'loaded' : 'loading',
.\processual_api\static\js\pages\settings.js:1114:        status: planOk ? (readinessState.subscription.status || 'loaded') : 'loading',
.\processual_api\static\js\pages\settings.js:1119:        status: usageOk ? 'available' : 'loading',
.\processual_api\static\js\pages\settings.js:1143:    setText('set-readiness-account', accountOk ? 'Ready' : 'Loading');
.\processual_api\static\js\pages\settings.js:1148:        : 'Loading'
.\processual_api\static\js\pages\settings.js:1196:        APP.showToast('Integration guide copied', 'success');
.\processual_api\static\js\pages\settings.js:1252:      toggle.setAttribute('aria-expanded', collapsed ? 'false' : 'true');
.\processual_api\static\js\pages\settings.js:1320:      toggle.setAttribute('aria-expanded', card.dataset.collapsed === 'true' ? 'false' : 'true');
.\processual_api\static\js\pages\settings.js:1405:        APP.showToast('Client preferences saved', 'success');
.\processual_api\static\js\pages\settings.js:1504:      operationalStatus.includes("disabled") ||
.\processual_api\static\js\pages\settings.js:1611:  if (document.readyState === "loading") {
.\processual_api\static\js\pages\settings.js:1665:      host.setAttribute("aria-label", "Integration onboarding claim key");
.\processual_api\static\js\pages\settings.js:1815:  if (document.readyState === "loading") {
.\tests\test_auth_jwt_claims_regression.py:27:        role="admin",
.\tests\test_auth_jwt_claims_regression.py:51:        'role="admin"',
.\tests\test_auth_platform_authority_session_r8d.py:115:        role="client",
.\tests\test_auth_platform_authority_session_r8d.py:133:        role="client",
.\processual_api\auth\mfa_repository.py:70:    async def disable_pending_factors(self, user_id: uuid.UUID, *, disabled_at: datetime) -> None:
.\processual_api\auth\mfa_repository.py:74:            .values(status="disabled", disabled_at=disabled_at)
.\processual_api\static\js\pages\reports.js:142:    APP.showLoading('llm-report-btn', 'Generating...');
.\processual_api\static\js\pages\reports.js:163:      APP.showToast('AI report generated', 'success');
.\processual_api\static\js\pages\reports.js:169:      APP.hideLoading('llm-report-btn');
.\processual_api\static\js\pages\reports.js:184:        APP.showToast('Fate report submitted', 'success');
.\processual_api\static\js\pages\reports.js:196:  if (document.readyState !== 'loading') init(); else document.addEventListener('DOMContentLoaded', init);
.\processual_api\routers\settings.py:1421:        result="success",
.\processual_api\routers\settings.py:1556:                result="success",
.\processual_api\routers\settings.py:1664:                result="success",
.\processual_api\routers\settings.py:1798:                result="success",
.\processual_api\routers\settings.py:1971:                result="success",
.\processual_api\routers\settings.py:2231:                    return TestConnectionResult(success=False, error="GENERIC_OPENAI_API_URL is required")
.\processual_api\routers\settings.py:2240:                return TestConnectionResult(success=True, latency_ms=round(latency, 1))
.\processual_api\routers\settings.py:2243:                    success=False,
.\processual_api\routers\settings.py:2248:        return TestConnectionResult(success=False, error="Connection timed out after 10s")
.\processual_api\routers\settings.py:2250:        return TestConnectionResult(success=False, error=str(e)[:200])
.\processual_api\routers\settings.py:2271:                json={"content": "[OK] Processual Maestro - Notification test successful"},
.\processual_api\routers\settings.py:2475:        if key.get("status") in {"revoked", "disabled", "expired"}:
.\processual_api\routers\settings.py:3076:        result="success",
.\processual_api\routers\settings.py:3130:        result="success",
.\processual_api\static\js\pages\institution_workspace_18.js:30:    loading: true,
.\processual_api\static\js\pages\institution_workspace_18.js:52:    state.loading = true;
.\processual_api\static\js\pages\institution_workspace_18.js:67:    state.loading = false;
.\processual_api\static\js\pages\institution_workspace_18.js:157:          <button class="iw18-button ghost" data-save-task="${esc(key)}" ${busy ? 'disabled' : ''}>${busy ? 'SavingÃ”Ã‡Âª' : 'Save task'}</button>
.\processual_api\static\js\pages\institution_workspace_18.js:170:        <div class="iw18-toolbar"><button class="iw18-button" data-create-track="${track.key}" ${state.busy ? 'disabled' : ''}>Create operational case</button></div>
.\processual_api\static\js\pages\institution_workspace_18.js:182:        <button class="iw18-button" data-validate-case="${esc(item.case_id)}" ${validateBusy ? 'disabled' : ''}>${validateBusy ? 'ValidatingÃ”Ã‡Âª' : 'Run automated validation'}</button>
.\processual_api\static\js\pages\institution_workspace_18.js:211:    if (state.loading) {
.\processual_api\static\js\pages\institution_workspace_18.js:212:      root.innerHTML = '<div class="iw18-empty">Loading enterprise integration workspaceÃ”Ã‡Âª</div>';
.\processual_api\static\js\pages\governor.js:31:      document.getElementById('gov-evaluate-btn').textContent = st.enabled ? 'Evaluate via Governor' : 'Governor Disabled';
.\processual_api\static\js\pages\governor.js:89:    APP.showLoading('gov-evaluate-btn', 'Evaluating...');
.\processual_api\static\js\pages\governor.js:93:      APP.showToast('Evaluation: ' + (res.rank || 'Ã”Ã‡Ã¶') + ' | Reward: ' + (res.reward || 0).toFixed(4), 'success');
.\processual_api\static\js\pages\governor.js:97:    APP.hideLoading('gov-evaluate-btn');
.\processual_api\static\js\pages\governor.js:145:        APP.showToast('Repair prompt copied', 'success');
.\processual_api\static\js\pages\governor.js:178:  if (document.readyState !== 'loading') init(); else document.addEventListener('DOMContentLoaded', init);
.\processual_api\static\js\pages\governance.js:72:  if (document.readyState !== 'loading') init(); else document.addEventListener('DOMContentLoaded', init);
.\processual_api\auth\session_service.py:84:                role="client",
.\processual_api\static\js\pages\gateway.js:146:    APP.showLoading('gw-reg-btn', 'Registering...');
.\processual_api\static\js\pages\gateway.js:151:      APP.showToast('Agent ' + id + ' registered', 'success');
.\processual_api\static\js\pages\gateway.js:157:    APP.hideLoading('gw-reg-btn');
.\processual_api\static\js\pages\gateway.js:168:    APP.showLoading('gw-eval-btn', 'Evaluating...');
.\processual_api\static\js\pages\gateway.js:189:      APP.showToast('Evaluation: ' + action.toUpperCase() + ' Ã”Ã‡Ã¶ ' + agentId, action === 'block' ? 'error' : action === 'repair' ? 'warn' : 'success');
.\processual_api\static\js\pages\gateway.js:194:    APP.hideLoading('gw-eval-btn');
.\processual_api\static\js\pages\gateway.js:238:      APP.showToast('Agent ' + agentId + ' Ã”Ã¥Ã† ' + (res.new_state || action), 'success');
.\processual_api\static\js\pages\gateway.js:255:    APP.showToast('CSV exported', 'success');
.\processual_api\static\js\pages\gateway.js:263:    APP.showToast('JSON exported', 'success');
.\processual_api\static\js\pages\gateway.js:278:        APP.showToast('PDF downloaded', 'success');
.\processual_api\static\js\pages\gateway.js:296:  if (document.readyState !== 'loading') init(); else document.addEventListener('DOMContentLoaded', init);
.\tests\test_auth_mfa_service_r8.py:52:    async def disable_pending_factors(self, user_id, *, disabled_at):
.\tests\test_auth_mfa_service_r8.py:54:            self.factor.status = "disabled"
.\tests\test_auth_mfa_service_r8.py:65:            disabled_at=None,
.\tests\test_auth_mfa_service_r8.py:227:    assert repository.factor.status == "disabled"
.\processual_api\static\js\pages\cgt.js:25:    APP.showLoading('cgt-eval-btn', 'Evaluating...');
.\processual_api\static\js\pages\cgt.js:53:      APP.showToast('CGT Evaluation: ' + rank, 'success');
.\processual_api\static\js\pages\cgt.js:57:    APP.hideLoading('cgt-eval-btn');
.\processual_api\static\js\pages\cgt.js:65:  if (document.readyState !== 'loading') init(); else document.addEventListener('DOMContentLoaded', init);
.\tests\test_auth_mfa_http_r8.py:121:    disabled = client.post("/auth/mfa/disable")
.\tests\test_auth_mfa_http_r8.py:130:    assert disabled.json() == {"status": "processed"}
.\processual_api\static\js\pages\adapters.js:45:    APP.showLoading('adp-configure-btn', 'Configuring...');
.\processual_api\static\js\pages\adapters.js:49:      APP.showToast(provider + ' configured successfully', 'success');
.\processual_api\static\js\pages\adapters.js:54:    APP.hideLoading('adp-configure-btn');
.\processual_api\static\js\pages\adapters.js:62:    APP.showLoading('adp-test-btn', 'Testing...');
.\processual_api\static\js\pages\adapters.js:66:      APP.showToast('Test ' + provider + ': ' + (res.ok ? 'connected' : 'disconnected'), res.ok ? 'success' : 'error');
.\processual_api\static\js\pages\adapters.js:70:    APP.hideLoading('adp-test-btn');
.\processual_api\static\js\pages\adapters.js:79:  if (document.readyState !== 'loading') init(); else document.addEventListener('DOMContentLoaded', init);
.\processual_api\routers\discord.py:19:    success: bool
.\processual_api\routers\discord.py:28:        return DiscordWebhookTestResponse(success=False, message="DISCORD_WEBHOOK_URL not configured")
.\processual_api\routers\discord.py:30:        success=True,
.\processual_api\routers\discord.py:40:        return DiscordWebhookTestResponse(success=False, message="DISCORD_ADMIN_WEBHOOK_URL not configured")
.\processual_api\routers\discord.py:42:        success=True,
.\processual_api\auth\router.py:62:            role="admin",
.\processual_api\auth\router.py:70:            role="client",
.\processual_api\static\js\i18n.js:16:      loading:      'Loading...',
.\processual_api\static\js\i18n.js:18:      success:      'Success',
.\processual_api\static\js\i18n.js:74:      loading:      'ÃÂ¼ÃÂºÃâ–’â”˜Ã¬ ÃÂºâ”˜Ã¤ÃÂ¬ÃÂ¡â”˜Ã â”˜Ã¨â”˜Ã¤...',
.\processual_api\static\js\i18n.js:76:      success:      'â”˜Ã¥ÃÂ¼ÃÂºÃÂ¡',
.\processual_api\routers\client_api_keys_18.py:105:        and key.get("status") not in {"revoked", "disabled", "expired"}
.\processual_api\static\js\charts.js:150:        responsive: true, maintainAspectRatio: false,
.\tests\test_checkout_disabled_contract_09d_document.py:3:CHECKOUT_DISABLED_CONTRACT_DOC = Path(
.\tests\test_checkout_disabled_contract_09d_document.py:4:    "docs/pricing/CHECKOUT_DISABLED_CONTRACT_09D.md"
.\tests\test_checkout_disabled_contract_09d_document.py:10:        CHECKOUT_DISABLED_CONTRACT_DOC.read_text(
.\tests\test_checkout_disabled_contract_09d_document.py:16:def test_checkout_disabled_contract_09d_document_exists():
.\tests\test_checkout_disabled_contract_09d_document.py:17:    assert CHECKOUT_DISABLED_CONTRACT_DOC.exists()
.\tests\test_checkout_disabled_contract_09d_document.py:20:def test_checkout_disabled_contract_09d_guardrails_are_present():
.\tests\test_checkout_disabled_contract_09d_document.py:32:        "checkout remains disabled",
.\tests\test_checkout_disabled_contract_09d_document.py:42:def test_checkout_disabled_contract_09d_forbidden_work_is_explicit():
.\tests\test_checkout_disabled_contract_09d_document.py:61:def test_checkout_disabled_contract_09d_future_inputs_are_required():
.\tests\test_checkout_disabled_contract_09d_document.py:82:def test_checkout_disabled_contract_09d_future_fields_are_neutral():
.\tests\test_checkout_disabled_contract_09d_document.py:107:def test_checkout_disabled_contract_09d_safe_disabled_behavior_is_defined():
.\tests\test_checkout_disabled_contract_09d_document.py:111:        "checkout-disabled behavior expectations",
.\tests\test_checkout_disabled_contract_09d_document.py:119:        "the disabled route should not create payment sessions or activate subscriptions",
.\tests\test_checkout_disabled_contract_09d_document.py:126:def test_checkout_disabled_contract_09d_approval_gate_is_present():
.\tests\test_checkout_disabled_contract_09d_document.py:139:        "without these decisions, checkout must remain disabled",
.\tests\test_checkout_disabled_contract_09d_document.py:146:def test_checkout_disabled_contract_09d_publication_restrictions_are_present():
.\tests\test_checkout_disabled_contract_09d_document.py:168:def test_checkout_disabled_contract_09d_has_no_provider_specific_identifiers():
.\tests\test_checkout_disabled_contract_09d_document.py:169:    raw_text = CHECKOUT_DISABLED_CONTRACT_DOC.read_text(encoding="utf-8").lower()
.\processual_api\static\js\app.js:44:  function showLoading(btnId, text) {
.\processual_api\static\js\app.js:48:    btn.disabled = true;
.\processual_api\static\js\app.js:49:    btn.innerHTML = '<span class="spinner"></span> ' + (text || 'Loading...');
.\processual_api\static\js\app.js:52:  function hideLoading(btnId) {
.\processual_api\static\js\app.js:55:    btn.disabled = false;
.\processual_api\static\js\app.js:206:    showToast, showLoading, hideLoading,
.\processual_api\static\js\app.js:230:    page.innerHTML = '<div id="institution-workspace-root"><div class="iw18-empty">Loading enterprise integration workspaceÃ”Ã‡Âª</div></div>';
.\processual_api\auth\registration_repository.py:192:                    role="organization_owner",
.\processual_api\routers\cgt_governor.py:863:    # Sort by reward descending (successful results first)
.\processual_api\routers\cgt_governor.py:1311:        role=req.role,
.\processual_api\static\js\admin_ui_hardening_13c.js:26:      frame.setAttribute("aria-label", title);
.\processual_api\static\js\admin_ui_hardening_13c.js:69:        node.title = value === "false" ? "Guardrail remains false/disabled" : "Flag is true/enabled";
.\processual_api\static\js\admin_ui_hardening_13c.js:137:          chip.setAttribute("aria-label", `${guardrailLabels[index]}: ${value}`);
.\processual_api\static\js\admin_ui_hardening_13c.js:184:  if (document.readyState === "loading") {
.\processual_api\auth\registration_contracts.py:28:    DISABLED = "disabled"
.\processual_api\auth\registration_contracts.py:195:                raise ValueError(f"{field_name} must remain disabled.")
.\processual_api\static\js\admin_supervisor_stats.js:160:      <div class="mono-block" style="font-size:11px;white-space:pre-wrap">Loading supervisor overview...</div>
.\processual_api\static\js\admin_supervisor_readiness_summary.js:94:        Loading program and supervision readiness...
.\processual_api\auth\account_recovery_service.py:88:        disabled_at: datetime,
.\processual_api\auth\account_recovery_service.py:481:                disabled_at=now,
.\tests\test_billing_pricing_catalog_route.py:43:def test_pricing_catalog_route_keeps_checkout_disabled_for_all_plans() -> None:
.\processual_api\static\js\admin_subscription_analytics.js:156:      <section class="admin-card admin-subscription-analytics-card" aria-live="polite">
.\processual_api\static\js\admin_subscription_analytics.js:182:      <section class="admin-card admin-subscription-analytics-card" aria-live="polite">
.\processual_api\static\js\admin_subscription_analytics.js:272:    host.dataset.adminSubscriptionAnalytics = "loading";
.\processual_api\static\js\admin_subscription_analytics.js:274:      <section class="admin-card admin-subscription-analytics-card" aria-live="polite">
.\processual_api\static\js\admin_subscription_analytics.js:276:        <p class="admin-muted">Loading subscription analytics...</p>
.\processual_api\static\js\admin_subscription_analytics.js:321:  if (document.readyState === "loading") {
.\processual_api\auth\account_recovery_repository.py:238:        disabled_at: datetime,
.\processual_api\auth\account_recovery_repository.py:252:                status="disabled",
.\processual_api\auth\account_recovery_repository.py:253:                disabled_at=disabled_at,
.\processual_api\auth\account_recovery_repository.py:254:                updated_at=disabled_at,
.\processual_api\static\js\admin_runtime_fixups.js:292:    if (button) button.disabled = true;
.\processual_api\static\js\admin_runtime_fixups.js:341:        if (button) button.disabled = false;
.\processual_api\static\js\admin_runtime_fixups.js:389:    if (button) button.disabled = false;
.\processual_api\static\js\admin_runtime_fixups.js:434:  if (document.readyState === 'loading') {
.\tests\test_commercial_terms_review_09c_document.py:29:        "checkout remains disabled",
.\processual_api\auth\account_recovery_external_revocation.py:122:                "disabled",
.\processual_api\static\js\admin_runtime.js:415:      '<div data-admin-runtime-body class="admin-note">Loading...</div>',
.\processual_api\static\js\admin_runtime.js:570:    if (button) button.disabled = true;
.\processual_api\static\js\admin_runtime.js:590:        if (button) button.disabled = false;
.\processual_api\static\js\admin_runtime.js:602:      if (button) button.disabled = false;
.\processual_api\static\js\admin_runtime.js:616:    if (button) button.disabled = false;
.\processual_api\static\js\admin_runtime.js:784:  if (document.readyState === 'loading') {
.\processual_api\auth\account_recovery_contracts.py:155:    """Successful completion never signs the caller in."""
.\processual_api\static\js\admin_operator_pilot_handoff_17c.js:51:    loadState: "loading",
.\processual_api\static\js\admin_operator_pilot_handoff_17c.js:180:    state.loadState = "loading";
.\processual_api\static\js\admin_operator_pilot_handoff_17c.js:217:      <li class="pmk17c-phase ${step[1]}" aria-current="${step[1] === "active" ? "step" : "false"}">
.\processual_api\static\js\admin_operator_pilot_handoff_17c.js:239:      <section class="pmk17c-summary-grid" aria-label="Pilot executive summary">
.\processual_api\static\js\admin_operator_pilot_handoff_17c.js:245:        ${metric("Runtime", "Disabled", "locked", "No connector authority")}
.\processual_api\static\js\admin_operator_pilot_handoff_17c.js:271:      <section class="pmk17c-intake-flow" aria-label="How integration data reaches Maestro">
.\processual_api\static\js\admin_operator_pilot_handoff_17c.js:305:        <div id="pmk17c-intake-result" class="pmk17c-intake-result" data-state="${escapeHtml(state.intakeState)}" aria-live="polite">${renderIntakeResult()}</div>
.\processual_api\static\js\admin_operator_pilot_handoff_17c.js:311:    if (state.intakeState === "loading") return "Validating structure, completeness and safety policyÃ”Ã‡Âª";
.\processual_api\static\js\admin_operator_pilot_handoff_17c.js:349:      ["Runtime connector", "Disabled", "Platform owner", "Yes"],
.\processual_api\static\js\admin_operator_pilot_handoff_17c.js:351:      ["External HTTP", "Disabled", "Network security", "Yes"],
.\processual_api\static\js\admin_operator_pilot_handoff_17c.js:419:      <nav class="pmk17c-tabs" aria-label="Pilot handoff sections">
.\processual_api\static\js\admin_operator_pilot_handoff_17c.js:420:        ${[["overview","Overview"],["intake","Intake & Validation"],["inputs","Required Inputs"],["reviews","Reviews & Controls"],["plan","Pilot Plan"],["evidence","Evidence & Audit"]].map((tab) => `<button type="button" role="tab" aria-selected="${state.activeTab === tab[0]}" class="${state.activeTab === tab[0] ? "active" : ""}" data-pmk17c-tab="${tab[0]}">${tab[1]}</button>`).join("")}
.\processual_api\static\js\admin_operator_pilot_handoff_17c.js:435:    if (state.loadState === "loading") {
.\processual_api\static\js\admin_operator_pilot_handoff_17c.js:436:      host.innerHTML = `<section class="pmk17c-state"><span class="pmk17c-spinner"></span><h2>Loading Pilot Handoff</h2><p>Gathering the package, review actions and progress metadata.</p></section>`;
.\processual_api\static\js\admin_operator_pilot_handoff_17c.js:478:      state.intakeState = "loading";
.\processual_api\static\js\admin_operator_pilot_handoff_17c.js:582:  if (document.readyState === "loading") {
.\processual_api\static\js\admin_operator_pilot_handoff.js:143:    success_criteria: [
.\processual_api\static\js\admin_operator_pilot_handoff.js:289:    lines.push("", "## Pilot Success Criteria", "");
.\processual_api\static\js\admin_operator_pilot_handoff.js:291:    PACKAGE.success_criteria.forEach((item) => {
.\processual_api\static\js\admin_operator_pilot_handoff.js:439:        <div class="operator-pilot-tools" aria-label="Operator handoff tools">
.\processual_api\static\js\admin_operator_pilot_handoff.js:473:          <h3>Pilot success criteria</h3>
.\processual_api\static\js\admin_operator_pilot_handoff.js:474:          <ul>${listItems(PACKAGE.success_criteria, "operator-pilot-criterion")}</ul>
.\processual_api\static\js\admin_operator_pilot_handoff.js:508:    panel.setAttribute("aria-label", "Operator pilot handoff explanation");
.\processual_api\static\js\admin_operator_pilot_handoff.js:557:  if (document.readyState === "loading") {
.\processual_api\static\js\admin_operator_pilot_handoff.js:571:  let actionsLoadState14D = "actions_loading";
.\processual_api\static\js\admin_operator_pilot_handoff.js:757:    panel.setAttribute("aria-label", "Supervisor readiness actions");
.\processual_api\static\js\admin_operator_pilot_handoff.js:849:  if (document.readyState === "loading") {
.\processual_api\static\js\admin_operator_pilot_handoff.js:878:  let progressLoadState14E = "progress_loading";
.\processual_api\static\js\admin_operator_pilot_handoff.js:1061:    progressLoadState14E = "progress_loading";
.\processual_api\static\js\admin_operator_pilot_handoff.js:1177:    const disabled = writeAvailable ? "" : "disabled";
.\processual_api\static\js\admin_operator_pilot_handoff.js:1206:            ${disabled}
.\processual_api\static\js\admin_operator_pilot_handoff.js:1222:            ${disabled}
.\processual_api\static\js\admin_operator_pilot_handoff.js:1233:          data-supervisor-disabled-reason="Supervisor write session required"
.\processual_api\static\js\admin_operator_pilot_handoff.js:1234:          ${disabled}
.\processual_api\static\js\admin_operator_pilot_handoff.js:1298:          button.disabled = true;
.\processual_api\static\js\admin_operator_pilot_handoff.js:1379:              state: "success",
.\processual_api\static\js\admin_operator_pilot_handoff.js:1548:  if (document.readyState === "loading") {
.\tests\test_auth_registration_http_r5b_r1.py:173:        json=_individual_payload(password=secret, role="platform_admin", plan_id="enterprise"),
.\processual_api\static\js\admin_nav.js:283:  if (document.readyState === 'loading') {
.\processual_api\static\js\admin_nav.js:314:      page.innerHTML = '<div id="admin-integration-center-root"><div class="ic18-empty">Loading integration centerÃ”Ã‡Âª</div></div>';
.\processual_api\static\js\admin_nav.js:340:  if (document.readyState === 'loading') {
.\tests\test_client_usage_summary_service_regression.py:28:    assert summary["successful_requests"] == 0
.\tests\test_client_usage_summary_service_regression.py:105:    assert summary["successful_requests"] == 1
.\tests\test_client_usage_summary_service_regression.py:108:    assert summary["successful_units"] == 1
.\processual_api\static\js\admin_layout_cleanup.js:78:  if (document.readyState === 'loading') {
.\processual_api\static\js\admin_integration_readiness.js:28:    card.setAttribute("aria-label", "Admin integration readiness");
.\processual_api\static\js\admin_integration_readiness.js:39:      "<pre id=\"admin-integration-readiness-body\" class=\"mono-block\">Loading integration readiness...</pre>",
.\processual_api\static\js\admin_integration_readiness.js:99:  if (document.readyState === "loading") {
.\processual_api\static\js\admin_integration_pilot_controls_13b.js:304:      .pmk-13b-actions button:disabled {
.\processual_api\static\js\admin_integration_pilot_controls_13b.js:367:      host.setAttribute("aria-label", "Integration Pilot Controls");
.\processual_api\static\js\admin_integration_pilot_controls_13b.js:513:      button.disabled = true;
.\processual_api\static\js\admin_integration_pilot_controls_13b.js:553:        freshButton.disabled = false;
.\processual_api\static\js\admin_integration_pilot_controls_13b.js:579:        create.disabled = true;
.\processual_api\static\js\admin_integration_pilot_controls_13b.js:584:          create.disabled = false;
.\processual_api\static\js\admin_integration_pilot_controls_13b.js:599:        button.disabled = true;
.\processual_api\static\js\admin_integration_pilot_controls_13b.js:603:          button.disabled = false;
.\processual_api\static\js\admin_integration_pilot_controls_13b.js:624:  if (document.readyState === "loading") {
.\processual_api\static\js\admin_integration_center_18.js:26:    loading: true,
.\processual_api\static\js\admin_integration_center_18.js:307:    if (state.loading) {
.\processual_api\static\js\admin_integration_center_18.js:308:      root.innerHTML = '<div class="ic18-empty">Loading integration readiness, cases and pilot evidenceÃ”Ã‡Âª</div>';
.\processual_api\static\js\admin_integration_center_18.js:343:          ${metric("Runtime authority", "Disabled", "Explicit guardrail")}
.\processual_api\static\js\admin_integration_center_18.js:368:    state.loading = true;
.\processual_api\static\js\admin_integration_center_18.js:386:    state.loading = false;
.\processual_api\static\js\admin_integration_center_18.js:392:  if (document.readyState === "loading") {
.\processual_api\auth\models.py:45:            "status IN ('pending_verification', 'active', 'locked', 'disabled', 'deleted')",
.\processual_api\auth\models.py:553:        CheckConstraint("status IN ('pending', 'active', 'disabled')", name="status_allowed"),
.\processual_api\auth\models.py:571:    disabled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
```

## Authority and Admin Marketplace patterns

```text
.\.env.production.example:89:AUTH_MFA_KEY_RING_JSON={"v1":"replace_with_base64_encoded_32_byte_mfa_key"}
.\.env.production.example:90:AUTH_MFA_CURRENT_KEY_VERSION=v1
.\.env.production.example:91:AUTH_MFA_ISSUER=Processual Maestro
.\.env.production.example:92:AUTH_MFA_RECOVERY_CODE_COUNT=10
.\.env.production.example:93:AUTH_MFA_STEP_UP_SECONDS=300
.\alembic\env.py:11:from processual_api.admin_marketplace import models as admin_marketplace_models  # noqa: F401
.\alembic\versions\20260721_0001_identity_auth_foundation.py:140:        sa.Column("mfa_satisfied_at", sa.DateTime(timezone=True), nullable=True),
.\alembic\versions\20260721_0001_identity_auth_foundation.py:231:        "auth_mfa_factors",
.\alembic\versions\20260721_0001_identity_auth_foundation.py:244:        sa.CheckConstraint("factor_type IN ('totp')", name="ck_auth_mfa_factors_factor_type_allowed"),
.\alembic\versions\20260721_0001_identity_auth_foundation.py:247:            name="ck_auth_mfa_factors_status_allowed",
.\alembic\versions\20260721_0001_identity_auth_foundation.py:252:            name="fk_auth_mfa_factors_user_id_identity_users",
.\alembic\versions\20260721_0001_identity_auth_foundation.py:255:        sa.PrimaryKeyConstraint("id", name="pk_auth_mfa_factors"),
.\alembic\versions\20260721_0001_identity_auth_foundation.py:260:            name="uq_auth_mfa_factor_user_type_label",
.\alembic\versions\20260721_0001_identity_auth_foundation.py:264:        "ix_auth_mfa_factors_user_status",
.\alembic\versions\20260721_0001_identity_auth_foundation.py:265:        "auth_mfa_factors",
.\alembic\versions\20260721_0001_identity_auth_foundation.py:271:        "auth_mfa_recovery_codes",
.\alembic\versions\20260721_0001_identity_auth_foundation.py:279:            ["auth_mfa_factors.id"],
.\alembic\versions\20260721_0001_identity_auth_foundation.py:280:            name="fk_auth_mfa_recovery_codes_factor_id_auth_mfa_factors",
.\alembic\versions\20260721_0001_identity_auth_foundation.py:283:        sa.PrimaryKeyConstraint("id", name="pk_auth_mfa_recovery_codes"),
.\alembic\versions\20260721_0001_identity_auth_foundation.py:284:        sa.UniqueConstraint("code_hash", name="uq_auth_mfa_recovery_codes_code_hash"),
.\alembic\versions\20260721_0001_identity_auth_foundation.py:288:        "auth_mfa_challenges",
.\alembic\versions\20260721_0001_identity_auth_foundation.py:299:            name="ck_auth_mfa_challenges_status_allowed",
.\alembic\versions\20260721_0001_identity_auth_foundation.py:304:            name="fk_auth_mfa_challenges_user_id_identity_users",
.\alembic\versions\20260721_0001_identity_auth_foundation.py:307:        sa.PrimaryKeyConstraint("id", name="pk_auth_mfa_challenges"),
.\alembic\versions\20260721_0001_identity_auth_foundation.py:308:        sa.UniqueConstraint("challenge_hash", name="uq_auth_mfa_challenges_challenge_hash"),
.\alembic\versions\20260721_0001_identity_auth_foundation.py:311:        "ix_auth_mfa_challenges_user_expiry",
.\alembic\versions\20260721_0001_identity_auth_foundation.py:312:        "auth_mfa_challenges",
.\alembic\versions\20260721_0001_identity_auth_foundation.py:319:    op.drop_index("ix_auth_mfa_challenges_user_expiry", table_name="auth_mfa_challenges")
.\alembic\versions\20260721_0001_identity_auth_foundation.py:320:    op.drop_table("auth_mfa_challenges")
.\alembic\versions\20260721_0001_identity_auth_foundation.py:321:    op.drop_table("auth_mfa_recovery_codes")
.\alembic\versions\20260721_0001_identity_auth_foundation.py:322:    op.drop_index("ix_auth_mfa_factors_user_status", table_name="auth_mfa_factors")
.\alembic\versions\20260721_0001_identity_auth_foundation.py:323:    op.drop_table("auth_mfa_factors")
.\alembic\versions\20260723_0007_admin_recovery_email_supervisor_authority.py:25:        "authority IN ('platform_admin', 'platform_supervisor')",
.\alembic\versions\20260723_0007_admin_recovery_email_supervisor_authority.py:60:        "authority IN ('platform_admin')",
.\alembic\versions\20260722_0006_platform_authority.py:86:            "authority IN ('platform_admin')",
.\alembic\versions\20260727_0011_admin_marketplace_persistence.py:2:"""Add Admin Marketplace persistence foundation.
.\alembic\versions\20260727_0011_admin_marketplace_persistence.py:925:            "platform_authority = 'platform_admin'",
.\docs\ADMIN_MARKETPLACE_HANDOFF.md:3:## â”œÃ–Ã”Ã‡Âªâ”œÃ¿â”¬â”¤â”œÃ¿â”¬â–’â”œÃ–â•¦Ã¥â”œÃ¿â”¬â•£ Processual Maestro â”œÃ³Ã”Ã©Â¼Ã”Ã‡Ã˜ â”œÃ–Ã”Ã‡Âªâ”œÃ¿â”¬â”‚â”œÃ¿â”¬Âºâ”œÃ¿â”¬â–’ Admin Marketplace
.\docs\ADMIN_MARKETPLACE_HANDOFF.md:11:â”œÃ–â”¼Ã¡â”œÃ–Ã”Ã‡Ã­â”œÃ¿â”¬Â»â”œÃ–â”¬Ã¼ â”œÃ–Ã”Ã‡Ã­â”œÃ¿â”¬â–‘â”œÃ¿â”¬Âº â”œÃ¿â”¬Âºâ”œÃ–Ã”Ã‡Ã—â”œÃ¿â”¬Â¬â”œÃ–Ã”Ã‡Ãœâ”œÃ¿â”¬â–’â”œÃ–â”¼Ã¡â”œÃ¿â”¬â–’ â”œÃ¿â”¬Ã‘â”œÃ–Ã”Ã‡Ã—â”œÃ–Ã”Ã‡â–‘ â”œÃ¿â”¬Â¬â”œÃ–â•¦Ã¥â”œÃ¿â”¬Â½â”œÃ–â”¼Ã¡â”œÃ–Ã”Ã‡Ãœ â”œÃ–Ã£Ã†â”œÃ–Ã”Ã‡Ã— â”œÃ–Ã”Ã‡Âªâ”œÃ¿â”¬Âº â”œÃ¿â”¬Â¬â”œÃ–Ã”Ã‡Âª â”œÃ¿â”¬Ã‘â”œÃ–Ã”Ã‡Ã¡â”œÃ¿â”¬Â¼â”œÃ¿â”¬Âºâ”œÃ¿â”¬â–“â”œÃ–Ã”Ã‡Ã­ â”œÃ–â”¬Ã¼â”œÃ–â”¼Ã¡ â”œÃ–Ã”Ã‡Âªâ”œÃ¿â”¬â”‚â”œÃ¿â”¬Âºâ”œÃ¿â”¬â–’ **Admin Marketplace**â”œÃ¿â”¼Ã† â”œÃ–â•¦Ã¥â”œÃ¿â”¬â”¤â”œÃ¿â”¬â–’â”œÃ¿â”¬Â¡ â”œÃ¿â”¬Âºâ”œÃ–Ã”Ã‡Ã—â”œÃ–â•¦Ã¥â”œÃ¿â”¬Ã‚â”œÃ¿â”¬â•£ â”œÃ¿â”¬Âºâ”œÃ–Ã”Ã‡Ã—â”œÃ¿â”¬Â¡â”œÃ¿â”¬Âºâ”œÃ–Ã”Ã‡Ã—â”œÃ–â”¼Ã¡ â”œÃ–Ã”Ã‡Ã—â”œÃ–Ã”Ã‡Ã—â”œÃ–Ã”Ã‡Âªâ”œÃ¿â”¬â”‚â”œÃ¿â”¬Â¬â”œÃ–â•¦Ã¥â”œÃ¿â”¬Â»â”œÃ¿â”¬â•£ â”œÃ–â•¦Ã¥â”œÃ¿â”¬Âºâ”œÃ–Ã”Ã‡Ã—â”œÃ–â”¬Ã¼â”œÃ¿â”¬â–’â”œÃ–â•¦Ã¥â”œÃ¿â”¬â•£ â”œÃ–â•¦Ã¥â”œÃ¿â”¬â•£â”œÃ–Ã”Ã‡Âªâ”œÃ–Ã”Ã‡Ã—â”œÃ–â”¼Ã¡â”œÃ¿â”¬Âºâ”œÃ¿â”¬Â¬ â”œÃ¿â”¬Âºâ”œÃ–Ã”Ã‡Ã—â”œÃ¿â”¬Â»â”œÃ–Ã”Ã‡Âªâ”œÃ¿â”¬Â¼ â”œÃ–â•¦Ã¥â”œÃ¿â”¬Âºâ”œÃ–Ã”Ã‡Ã—â”œÃ¿â”¬Âºâ”œÃ¿â”¬Â«â”œÃ¿â”¬Â¬â”œÃ¿â”¬Â¿â”œÃ¿â”¬Âºâ”œÃ¿â”¬â–’â”œÃ¿â”¬Âºâ”œÃ¿â”¬Â¬â”œÃ¿â”¼Ã† â”œÃ–â•¦Ã¥â”œÃ¿â”¬Â¬â”œÃ¿â”¬Â¡â”œÃ¿â”¬Â»â”œÃ–â”¼Ã¡â”œÃ¿â”¬Â» â”œÃ–Ã”Ã‡Âªâ”œÃ¿â”¬Âº â”œÃ¿â”¬Â¬â”œÃ¿â”¬Â¿â”œÃ–Ã”Ã‡Ãœâ”œÃ–Ã”Ã‡â–‘ â”œÃ¿â”¬Â¬â”œÃ–Ã”Ã‡Ã¡â”œÃ–â”¬Ã¼â”œÃ–â”¼Ã¡â”œÃ¿â”¬â–‘â”œÃ–Ã”Ã‡Ã­â”œÃ¿â”¼Ã† â”œÃ–Ã”Ã‡Âªâ”œÃ¿â”¬â•£ â”œÃ¿â”¬Â¬â”œÃ–â•¦Ã¥â”œÃ–â”¬Ã¼â”œÃ–â”¼Ã¡â”œÃ¿â”¬â–’ â”œÃ¿â”¬â”‚â”œÃ–â”¼Ã¡â”œÃ¿â”¬Âºâ”œÃ–Ã”Ã‡Ãœ â”œÃ¿â”¬Â¬â”œÃ–Ã”Ã‡Ãœâ”œÃ–Ã”Ã‡Ã¡â”œÃ–â”¼Ã¡ â”œÃ–â•¦Ã¥â”œÃ¿â”¬Â¬â”œÃ¿â”¬â”¤â”œÃ¿â”¬â•‘â”œÃ–â”¼Ã¡â”œÃ–Ã”Ã‡Ã—â”œÃ–â”¼Ã¡ â”œÃ–Ã£Ã†â”œÃ¿â”¬Âºâ”œÃ–â”¬Ã¼â”œÃ–â”¬Ã¬ â”œÃ–Ã”Ã‡Ã—â”œÃ–Ã”Ã‡Âªâ”œÃ–â•¦Ã¥â”œÃ¿â”¬Âºâ”œÃ¿â”¬Ãâ”œÃ–Ã”Ã‡Ã—â”œÃ¿â”¬Â® â”œÃ¿â”¬Âºâ”œÃ–Ã”Ã‡Ã—â”œÃ¿â”¬â•£â”œÃ–Ã”Ã‡Âªâ”œÃ–Ã”Ã‡Ã— â”œÃ–â”¬Ã¼â”œÃ–â”¼Ã¡ â”œÃ–Ã”Ã‡Âªâ”œÃ¿â”¬â”‚â”œÃ¿â”¬Âºâ”œÃ¿â”¬Â¡â”œÃ¿â”¬Â® â”œÃ¿â”¬Â¼â”œÃ¿â”¬Â»â”œÃ–â”¼Ã¡â”œÃ¿â”¬Â»â”œÃ¿â”¬Â® â”œÃ¿â”¬Â»â”œÃ–â•¦Ã¥â”œÃ–Ã”Ã‡Ã¡ â”œÃ¿â”¬Âºâ”œÃ–Ã”Ã‡Ã—â”œÃ¿â”¬Â¡â”œÃ¿â”¬Âºâ”œÃ¿â”¬Â¼â”œÃ¿â”¬Â® â”œÃ¿â”¬Ã‘â”œÃ–Ã”Ã‡Ã—â”œÃ–Ã”Ã‡â–‘ â”œÃ¿â”¬Âºâ”œÃ–Ã”Ã‡Ã—â”œÃ¿â”¬â–’â”œÃ¿â”¬Â¼â”œÃ–â•¦Ã¥â”œÃ¿â”¬â•£ â”œÃ¿â”¬Ã‘â”œÃ–Ã”Ã‡Ã—â”œÃ–Ã”Ã‡â–‘ â”œÃ¿â”¬Âºâ”œÃ–Ã”Ã‡Ã—â”œÃ–Ã”Ã‡Âªâ”œÃ¿â”¬Â¡â”œÃ¿â”¬Âºâ”œÃ¿â”¬Â»â”œÃ¿â”¬Â½â”œÃ¿â”¬Â® â”œÃ¿â”¬Âºâ”œÃ–Ã”Ã‡Ã—â”œÃ¿â”¬â”‚â”œÃ¿â”¬Âºâ”œÃ¿â”¬Â¿â”œÃ–Ã”Ã‡Ãœâ”œÃ¿â”¬Â®.
.\docs\ADMIN_MARKETPLACE_HANDOFF.md:77:# 3. â”œÃ¿â”¬Âºâ”œÃ–Ã”Ã‡Ã—â”œÃ¿â”¬Â¡â”œÃ¿â”¬Âºâ”œÃ–Ã”Ã‡Ã—â”œÃ¿â”¬Â® â”œÃ¿â”¬Âºâ”œÃ–Ã”Ã‡Ã—â”œÃ¿â”¬â•£â”œÃ¿â”¬Âºâ”œÃ–Ã”Ã‡Âªâ”œÃ¿â”¬Â® â”œÃ–Ã”Ã‡Ã—â”œÃ–Ã”Ã‡Âªâ”œÃ¿â”¬â”‚â”œÃ¿â”¬Âºâ”œÃ¿â”¬â–’ Admin Marketplace
.\docs\ADMIN_MARKETPLACE_HANDOFF.md:79:â”œÃ¿â”¬Â¬â”œÃ–Ã”Ã‡Âª â”œÃ¿â”¬Â¬â”œÃ–Ã”Ã‡Ãœâ”œÃ¿â”¬â”‚â”œÃ–â”¼Ã¡â”œÃ–Ã”Ã‡Âª â”œÃ¿â”¬Â¿â”œÃ–Ã”Ã‡Ã¡â”œÃ¿â”¬Âºâ”œÃ¿â”¬Ã­ Admin Marketplace â”œÃ¿â”¬Ã‘â”œÃ–Ã”Ã‡Ã—â”œÃ–Ã”Ã‡â–‘ â”œÃ–Ã”Ã‡Âªâ”œÃ¿â”¬â–’â”œÃ¿â”¬Âºâ”œÃ¿â”¬Â¡â”œÃ–Ã”Ã‡Ã— â”œÃ–Ã”Ã‡Âªâ”œÃ¿â”¬â”‚â”œÃ¿â”¬Â¬â”œÃ–Ã”Ã‡Ãœâ”œÃ–Ã”Ã‡Ã—â”œÃ¿â”¬Â® â”œÃ–â•¦Ã¥â”œÃ–Ã”Ã‡Âªâ”œÃ¿â”¬Ã‚â”œÃ¿â”¬Â¿â”œÃ–â•¦Ã¥â”œÃ¿â”¬Ã€â”œÃ¿â”¬Â® â”œÃ¿â”¬Âºâ”œÃ–Ã”Ã‡Ã—â”œÃ–Ã”Ã‡Ã¡â”œÃ¿â”¬Ã€â”œÃ¿â”¬Âºâ”œÃ–Ã”Ã‡Ãœ:
.\docs\ADMIN_MARKETPLACE_HANDOFF.md:109:â”œÃ¿â”¬Ã‘â”œÃ–Ã”Ã‡Ã¡â”œÃ¿â”¬â”¤â”œÃ¿â”¬Âºâ”œÃ¿â”¬Ã­ â”œÃ¿â”¬Âºâ”œÃ–Ã”Ã‡Ã—â”œÃ¿â”¬Ãºâ”œÃ¿â”¬â”‚â”œÃ¿â”¬Âºâ”œÃ¿â”¬â”‚ â”œÃ¿â”¬Âºâ”œÃ–Ã”Ã‡Ã—â”œÃ¿â”¬Â»â”œÃ–â•¦Ã¥â”œÃ–Ã”Ã‡Âªâ”œÃ–â”¼Ã¡â”œÃ–Ã”Ã‡Ã¡â”œÃ–â”¼Ã¡ â”œÃ–â•¦Ã¥â”œÃ¿â”¬Âºâ”œÃ–Ã”Ã‡Ã—â”œÃ¿â”¬â•£â”œÃ–Ã”Ã‡Ãœâ”œÃ–â•¦Ã¥â”œÃ¿â”¬Â» â”œÃ¿â”¬Âºâ”œÃ–Ã”Ã‡Ã—â”œÃ¿â”¬Ãºâ”œÃ–Ã”Ã‡Âªâ”œÃ–Ã”Ã‡Ã¡â”œÃ–â”¼Ã¡â”œÃ¿â”¬Â® â”œÃ–â•¦Ã¥â”œÃ¿â”¬Âºâ”œÃ–Ã”Ã‡Ã—â”œÃ¿â”¬Â¬â”œÃ¿â”¬Â¼â”œÃ¿â”¬Âºâ”œÃ¿â”¬â–’â”œÃ–â”¼Ã¡â”œÃ¿â”¬Â® â”œÃ–Ã”Ã‡Ã—â”œÃ–Ã”Ã©Â¼Admin Marketplace â”œÃ¿â”¬Â»â”œÃ–â•¦Ã¥â”œÃ–Ã”Ã‡Ã¡ â”œÃ¿â”¬Ãºâ”œÃ–â”¼Ã¡ runtime â”œÃ¿â”¬Ãºâ”œÃ–â•¦Ã¥ persistence â”œÃ¿â”¬Ãºâ”œÃ–â•¦Ã¥ routes â”œÃ¿â”¬Ãºâ”œÃ–â•¦Ã¥ â”œÃ–â•¦Ã¥â”œÃ¿â”¬Âºâ”œÃ¿â”¬Â¼â”œÃ–Ã”Ã‡Ã­â”œÃ¿â”¬Â® â”œÃ–Ã”Ã‡Âªâ”œÃ¿â”¬â”‚â”œÃ¿â”¬Â¬â”œÃ¿â”¬Â«â”œÃ¿â”¬Â»â”œÃ–Ã”Ã‡Âª.
.\docs\ADMIN_MARKETPLACE_HANDOFF.md:131:active platform_admin
.\docs\ADMIN_MARKETPLACE_HANDOFF.md:144:inactive platform_admin
.\docs\ADMIN_MARKETPLACE_HANDOFF.md:149:## MFA â”œÃ–â•¦Ã¥Step-Up
.\docs\ADMIN_MARKETPLACE_HANDOFF.md:154:MFA step-up
.\docs\ADMIN_MARKETPLACE_HANDOFF.md:175:* â”œÃ¿â”¬Âºâ”œÃ–Ã”Ã‡Ã—â”œÃ¿â”¬â•£â”œÃ–Ã”Ã‡Âªâ”œÃ–Ã”Ã‡Ã—â”œÃ–â”¼Ã¡â”œÃ¿â”¬Âºâ”œÃ¿â”¬Â¬ â”œÃ¿â”¬Âºâ”œÃ–Ã”Ã‡Ã—â”œÃ¿â”¬Â¡â”œÃ¿â”¬â”‚â”œÃ¿â”¬Âºâ”œÃ¿â”¬â”‚â”œÃ¿â”¬Â® â”œÃ¿â”¬Â¬â”œÃ¿â”¬Â¬â”œÃ¿â”¬Ã€â”œÃ–Ã”Ã‡Ã—â”œÃ¿â”¬Â¿ MFA step-up.
.\docs\ADMIN_MARKETPLACE_HANDOFF.md:277:alembic/versions/20260727_0011_admin_marketplace_persistence.py
.\docs\ADMIN_MARKETPLACE_HANDOFF.md:278:processual_api/admin_marketplace/__init__.py
.\docs\ADMIN_MARKETPLACE_HANDOFF.md:279:processual_api/admin_marketplace/audit_contracts.py
.\docs\ADMIN_MARKETPLACE_HANDOFF.md:280:processual_api/admin_marketplace/authority.py
.\docs\ADMIN_MARKETPLACE_HANDOFF.md:281:processual_api/admin_marketplace/contracts.py
.\docs\ADMIN_MARKETPLACE_HANDOFF.md:282:processual_api/admin_marketplace/models.py
.\docs\ADMIN_MARKETPLACE_HANDOFF.md:283:tests/test_admin_marketplace_migration_r2.py
.\docs\ADMIN_MARKETPLACE_HANDOFF.md:284:tests/test_admin_marketplace_models_r2.py
.\docs\ADMIN_MARKETPLACE_HANDOFF.md:299:alembic/versions/20260727_0011_admin_marketplace_persistence.py
.\docs\ADMIN_MARKETPLACE_HANDOFF.md:300:processual_api/admin_marketplace/models.py
.\docs\ADMIN_MARKETPLACE_HANDOFF.md:301:tests/test_admin_marketplace_migration_r2.py
.\docs\ADMIN_MARKETPLACE_HANDOFF.md:302:tests/test_admin_marketplace_models_r2.py
.\docs\ADMIN_MARKETPLACE_HANDOFF.md:312:processual_api/admin_marketplace/models.py
.\docs\ADMIN_MARKETPLACE_HANDOFF.md:315:â”œÃ–â•¦Ã¥â”œÃ–Ã”Ã‡Ã­â”œÃ–â•¦Ã¥ â”œÃ–â”¼Ã¡â”œÃ¿â”¬Â¡â”œÃ¿â”¬Â¬â”œÃ–â•¦Ã¥â”œÃ–â”¼Ã¡ â”œÃ¿â”¬â•£â”œÃ–Ã”Ã‡Ã—â”œÃ–Ã”Ã‡â–‘ â”œÃ¿â”¬Âºâ”œÃ¿â”¬Â½â”œÃ–Ã”Ã‡Ã¡â”œÃ–â”¼Ã¡ â”œÃ¿â”¬â•£â”œÃ¿â”¬â”¤â”œÃ¿â”¬â–’ model â”œÃ¿â”¬Â¬â”œÃ–Ã”Ã‡Âªâ”œÃ¿â”¬Â½â”œÃ–Ã”Ã‡Ã— â”œÃ¿â”¬Âºâ”œÃ–Ã”Ã‡Ã—â”œÃ¿â”¬Ãºâ”œÃ¿â”¬â”‚â”œÃ¿â”¬Âºâ”œÃ¿â”¬â”‚ â”œÃ¿â”¬Âºâ”œÃ–Ã”Ã‡Ã—â”œÃ–Ã£Ã†â”œÃ¿â”¬Âºâ”œÃ–Ã”Ã‡Âªâ”œÃ–Ã”Ã‡Ã— â”œÃ–Ã”Ã‡Ã—â”œÃ¿â”¬Â¬â”œÃ¿â”¬Â«â”œÃ¿â”¬â–“â”œÃ–â”¼Ã¡â”œÃ–Ã”Ã‡Ã¡ Admin Marketplace.
.\docs\ADMIN_MARKETPLACE_HANDOFF.md:515:* â”œÃ–Ã”Ã‡Âªâ”œÃ–Ã”Ã‡Ã¡â”œÃ¿â”¬â•£ coupling â”œÃ–Ã”Ã‡Âªâ”œÃ¿â”¬Â¿â”œÃ–Ã£Ã†â”œÃ¿â”¬â–’ â”œÃ¿â”¬Â¿â”œÃ–â”¼Ã¡â”œÃ–Ã”Ã‡Ã¡ Admin Marketplace â”œÃ–â•¦Ã¥â”œÃ¿â”¬Â¿â”œÃ–Ã”Ã‡Ãœâ”œÃ–â”¼Ã¡â”œÃ¿â”¬Â® â”œÃ¿â”¬Âºâ”œÃ–Ã”Ã‡Ã—â”œÃ¿â”¬Ãºâ”œÃ–Ã”Ã‡Ã¡â”œÃ¿â”¬Â©â”œÃ–Ã”Ã‡Âªâ”œÃ¿â”¬Â®.
.\docs\ADMIN_MARKETPLACE_HANDOFF.md:588:alembic/versions/20260727_0011_admin_marketplace_persistence.py
.\docs\ADMIN_MARKETPLACE_HANDOFF.md:645:â”œÃ–Ã”Ã‡Ã—â”œÃ¿â”¬Â¬â”œÃ¿â”¬Â¡â”œÃ–Ã”Ã‡Âªâ”œÃ–â”¼Ã¡â”œÃ–Ã”Ã‡Ã— Admin Marketplace models â”œÃ¿â”¬Ã‚â”œÃ–Ã”Ã‡Âªâ”œÃ–Ã”Ã‡Ã¡ metadata â”œÃ¿â”¬Âºâ”œÃ–Ã”Ã‡Ã—â”œÃ¿â”¬Â«â”œÃ¿â”¬Âºâ”œÃ¿â”¬Ãâ”œÃ¿â”¬Â® â”œÃ¿â”¬Â¿â”œÃ–Ã”Ã©Â¼Alembic:
.\docs\ADMIN_MARKETPLACE_HANDOFF.md:648:from processual_api.admin_marketplace import models as admin_marketplace_models  # noqa: F401
.\docs\ADMIN_MARKETPLACE_HANDOFF.md:666:tests/test_admin_marketplace_models_r2.py
.\docs\ADMIN_MARKETPLACE_HANDOFF.md:689:tests/test_admin_marketplace_migration_r2.py
.\docs\ADMIN_MARKETPLACE_HANDOFF.md:783:* F401 â”œÃ–â”¬Ã¼â”œÃ–â”¼Ã¡ `admin_marketplace/__init__.py`.
.\docs\ADMIN_MARKETPLACE_HANDOFF.md:807:processual_api/admin_marketplace/__init__.py
.\docs\ADMIN_MARKETPLACE_HANDOFF.md:892:## Admin Marketplace R1 + R2
.\docs\ADMIN_MARKETPLACE_HANDOFF.md:899:## Auth platform authority and MFA regression
.\docs\ADMIN_MARKETPLACE_HANDOFF.md:930:tests/test_admin_marketplace_models_r2.py
.\docs\ADMIN_MARKETPLACE_HANDOFF.md:931:tests/test_admin_marketplace_migration_r2.py
.\docs\ADMIN_MARKETPLACE_HANDOFF.md:1081:pmk_auth_r8d_platform_admin_r1
.\docs\ADMIN_MARKETPLACE_HANDOFF.md:1157:Admin Marketplace repositories
.\docs\ADMIN_MARKETPLACE_HANDOFF.md:1176:admin marketplace UI
.\docs\ADMIN_MARKETPLACE_HANDOFF.md:1253:active platform_admin
.\docs\ADMIN_MARKETPLACE_HANDOFF.md:1256:â”œÃ–â•¦Ã¥â”œÃ¿â”¬Âºâ”œÃ–Ã”Ã‡Ã—â”œÃ¿â”¬â•£â”œÃ–Ã”Ã‡Âªâ”œÃ–Ã”Ã‡Ã—â”œÃ–â”¼Ã¡â”œÃ¿â”¬Âºâ”œÃ¿â”¬Â¬ â”œÃ¿â”¬Âºâ”œÃ–Ã”Ã‡Ã—â”œÃ¿â”¬Â¡â”œÃ¿â”¬â”‚â”œÃ¿â”¬Âºâ”œÃ¿â”¬â”‚â”œÃ¿â”¬Â® â”œÃ–â”¼Ã¡â”œÃ¿â”¬Â¼â”œÃ¿â”¬Â¿ â”œÃ¿â”¬Ãºâ”œÃ–Ã”Ã‡Ã¡ â”œÃ¿â”¬Â¬â”œÃ¿â”¬â”‚â”œÃ¿â”¬Â¬â”œÃ–Ã”Ã‡Ãœâ”œÃ¿â”¬Â¿â”œÃ–Ã”Ã‡Ã— â”œÃ¿â”¬Â»â”œÃ–Ã”Ã‡Ã—â”œÃ–â”¼Ã¡â”œÃ–Ã”Ã‡Ã— step-up â”œÃ¿â”¬Ãâ”œÃ¿â”¬Âºâ”œÃ–Ã”Ã‡Ã—â”œÃ¿â”¬Â¡ â”œÃ¿â”¬Ãºâ”œÃ–â•¦Ã¥ context â”œÃ–â”¼Ã¡â”œÃ¿â”¬Â½â”œÃ¿â”¬Â¿â”œÃ¿â”¬Â¬ MFA step-up.
.\docs\ADMIN_MARKETPLACE_HANDOFF.md:1339:step-up requirement
.\docs\ADMIN_MARKETPLACE_HANDOFF.md:1393:platform_admin
.\docs\ADMIN_MARKETPLACE_HANDOFF.md:1396:MFA step-up when action is sensitive
.\docs\ADMIN_MARKETPLACE_HANDOFF.md:1410:expired step-up
.\docs\ADMIN_MARKETPLACE_HANDOFF.md:1411:missing step-up
.\docs\ADMIN_MARKETPLACE_HANDOFF.md:1459:processual_api/admin_marketplace/
.\docs\ADMIN_MARKETPLACE_HANDOFF.md:1474:processual_api/admin_marketplace/persistence/
.\docs\ADMIN_MARKETPLACE_HANDOFF.md:1524:* â”œÃ–â”¬Ã¼â”œÃ¿â”¬â–’â”œÃ¿â”¬Ã‚ platform_admin.
.\docs\ADMIN_MARKETPLACE_HANDOFF.md:1526:* â”œÃ–â”¬Ã¼â”œÃ¿â”¬â–’â”œÃ¿â”¬Ã‚ step-up â”œÃ–Ã”Ã‡Ã—â”œÃ–Ã”Ã‡Ã—â”œÃ¿â”¬â•£â”œÃ–Ã”Ã‡Âªâ”œÃ–Ã”Ã‡Ã—â”œÃ–â”¼Ã¡â”œÃ¿â”¬Âºâ”œÃ¿â”¬Â¬ â”œÃ¿â”¬Âºâ”œÃ–Ã”Ã‡Ã—â”œÃ¿â”¬Â¡â”œÃ¿â”¬â”‚â”œÃ¿â”¬Âºâ”œÃ¿â”¬â”‚â”œÃ¿â”¬Â®.
.\docs\ADMIN_MARKETPLACE_HANDOFF.md:1540:* full Admin Marketplace tests.
.\docs\ADMIN_MARKETPLACE_HANDOFF.md:1609:â”œÃ–â”¼Ã¡â”œÃ–Ã”Ã‡Ã¡â”œÃ¿â”¬Â¿â”œÃ¿â”¬â•‘â”œÃ–â”¼Ã¡ â”œÃ¿â”¬Â¬â”œÃ¿â”¬â”¤â”œÃ¿â”¬â•‘â”œÃ–â”¼Ã¡â”œÃ–Ã”Ã‡Ã— â”œÃ¿â”¬Âºâ”œÃ¿â”¬Â«â”œÃ¿â”¬Â¬â”œÃ¿â”¬Â¿â”œÃ¿â”¬Âºâ”œÃ¿â”¬â–’â”œÃ¿â”¬Âºâ”œÃ¿â”¬Â¬ Admin Marketplace â”œÃ¿â”¬Âºâ”œÃ–Ã”Ã‡Ã—â”œÃ¿â”¬Â¡â”œÃ¿â”¬Âºâ”œÃ–Ã”Ã‡Ã—â”œÃ–â”¼Ã¡â”œÃ¿â”¬Â® â”œÃ–Ã”Ã‡Ãœâ”œÃ¿â”¬Â¿â”œÃ–Ã”Ã‡Ã— â”œÃ¿â”¬Ãºâ”œÃ–â”¼Ã¡ â”œÃ¿â”¬Â¬â”œÃ¿â”¬â•£â”œÃ¿â”¬Â»â”œÃ–â”¼Ã¡â”œÃ–Ã”Ã‡Ã—:
.\docs\ADMIN_MARKETPLACE_HANDOFF.md:1613:  tests/test_admin_marketplace_models_r2.py `
.\docs\ADMIN_MARKETPLACE_HANDOFF.md:1614:  tests/test_admin_marketplace_migration_r2.py `
.\docs\ADMIN_MARKETPLACE_HANDOFF.md:1615:  tests/test_admin_marketplace_contracts_r1.py `
.\docs\ADMIN_MARKETPLACE_HANDOFF.md:1616:  tests/test_admin_marketplace_authority_r1.py `
.\docs\ADMIN_MARKETPLACE_HANDOFF.md:1617:  tests/test_admin_marketplace_channel_policy_r1.py `
.\docs\ADMIN_MARKETPLACE_HANDOFF.md:1618:  tests/test_admin_marketplace_audit_contracts_r1.py `
.\docs\ADMIN_MARKETPLACE_HANDOFF.md:1619:  tests/test_admin_marketplace_exports_r1.py
.\docs\ADMIN_MARKETPLACE_HANDOFF.md:1659:36 Admin Marketplace tests
.\docs\ADMIN_MARKETPLACE_HANDOFF.md:1660:53 platform authority/MFA tests
.\docs\ADMIN_MARKETPLACE_HANDOFF.md:1700:  processual_api/admin_marketplace/<new-files> `
.\docs\ADMIN_MARKETPLACE_HANDOFF.md:1753:* MFA step-up boundaries.
.\docs\ADMIN_MARKETPLACE_HANDOFF.md:1857:Admin Marketplace â”œÃ–Ã”Ã‡Ã—â”œÃ–â”¼Ã¡â”œÃ¿â”¬â”‚ â”œÃ–Ã”Ã‡Âªâ”œÃ¿â”¬Â¼â”œÃ¿â”¬â–’â”œÃ¿â”¬Â» â”œÃ–â•¦Ã¥â”œÃ¿â”¬Âºâ”œÃ¿â”¬Â¼â”œÃ–Ã”Ã‡Ã­â”œÃ¿â”¬Â® â”œÃ¿â”¬Ãºâ”œÃ¿â”¬Â«â”œÃ¿â”¬â–’â”œÃ–Ã”Ã‡â–‘ â”œÃ–Ã”Ã‡Ã—â”œÃ–Ã”Ã©Â¼`processual_api/billing`.
.\docs\ADMIN_MARKETPLACE_HANDOFF.md:1865:â”œÃ¿â”¬Â¬â”œÃ–Ã”Ã‡Âª â”œÃ¿â”¬Ã‘â”œÃ–Ã”Ã‡Ã¡â”œÃ¿â”¬Â¼â”œÃ¿â”¬Âºâ”œÃ¿â”¬â–“ â”œÃ¿â”¬Âºâ”œÃ–Ã”Ã‡Ã—â”œÃ¿â”¬Ãºâ”œÃ¿â”¬â”‚â”œÃ¿â”¬Âºâ”œÃ¿â”¬â”‚ â”œÃ¿â”¬Âºâ”œÃ–Ã”Ã‡Ã—â”œÃ¿â”¬Â»â”œÃ–â•¦Ã¥â”œÃ–Ã”Ã‡Âªâ”œÃ–â”¼Ã¡â”œÃ–Ã”Ã‡Ã¡â”œÃ–â”¼Ã¡ â”œÃ–â•¦Ã¥â”œÃ¿â”¬Âºâ”œÃ–Ã”Ã‡Ã—â”œÃ¿â”¬Ãºâ”œÃ–Ã”Ã‡Âªâ”œÃ–Ã”Ã‡Ã¡â”œÃ–â”¼Ã¡ â”œÃ–â•¦Ã¥â”œÃ¿â”¬Âºâ”œÃ–Ã”Ã‡Ã—â”œÃ¿â”¬Â¬â”œÃ¿â”¬Â«â”œÃ¿â”¬â–“â”œÃ–â”¼Ã¡â”œÃ–Ã”Ã‡Ã¡â”œÃ–â”¼Ã¡ â”œÃ–Ã”Ã‡Ã—â”œÃ–Ã”Ã©Â¼Admin Marketplace â”œÃ¿â”¬Â¿â”œÃ–Ã”Ã‡Ã¡â”œÃ¿â”¬Â¼â”œÃ¿â”¬Âºâ”œÃ¿â”¬Â¡.
.\docs\ADMIN_MARKETPLACE_HANDOFF.md:1873:* MFA step-up.
.\docs\ADMIN_MARKETPLACE_HANDOFF.md:1951:6. â”œÃ¿â”¬Ã‘â”œÃ¿â”¬Ã‚â”œÃ¿â”¬Âºâ”œÃ–â”¬Ã¼â”œÃ¿â”¬Â® authority â”œÃ–â•¦Ã¥step-up enforcement.
.\docs\ADMIN_MARKETPLACE_HANDOFF.md:1999:Admin Marketplace baseline tests:
.\docs\ADMIN_MARKETPLACE_HANDOFF.md:2023:â”œÃ¿â”¬Âºâ”œÃ–Ã”Ã‡Ã—â”œÃ¿â”¬Â¬â”œÃ–Ã”Ã‡Ãœâ”œÃ¿â”¬â”‚â”œÃ–â”¼Ã¡â”œÃ–Ã”Ã‡Âª â”œÃ¿â”¬Âºâ”œÃ–Ã”Ã‡Ã—â”œÃ¿â”¬Â¬â”œÃ¿â”¬Âºâ”œÃ–Ã”Ã‡Ã—â”œÃ–â”¼Ã¡ â”œÃ–Ã”Ã‡Ã­â”œÃ–â•¦Ã¥ â”œÃ¿â”¬Âºâ”œÃ–Ã”Ã‡Ã—â”œÃ¿â”¬Â«â”œÃ¿â”¬Ã€â”œÃ¿â”¬Â® â”œÃ¿â”¬Âºâ”œÃ–Ã”Ã‡Ã—â”œÃ¿â”¬Â¬â”œÃ–Ã”Ã‡Ã¡â”œÃ–â”¬Ã¼â”œÃ–â”¼Ã¡â”œÃ¿â”¬â–‘â”œÃ–â”¼Ã¡â”œÃ¿â”¬Â® â”œÃ¿â”¬Âºâ”œÃ–Ã”Ã‡Ã—â”œÃ–Ã”Ã‡Âªâ”œÃ¿â”¬â•£â”œÃ¿â”¬Â¬â”œÃ–Ã”Ã‡Âªâ”œÃ¿â”¬Â»â”œÃ¿â”¬Â® â”œÃ¿â”¬Âºâ”œÃ–Ã”Ã‡Ã—â”œÃ–Ã”Ã‡Âªâ”œÃ–Ã”Ã‡Ãœâ”œÃ¿â”¬Â¬â”œÃ¿â”¬â–’â”œÃ¿â”¬Â¡â”œÃ¿â”¬Â® â”œÃ–Ã”Ã‡Ã—â”œÃ¿â”¬Âºâ”œÃ¿â”¬â”‚â”œÃ¿â”¬Â¬â”œÃ–Ã£Ã†â”œÃ–Ã”Ã‡Âªâ”œÃ¿â”¬Âºâ”œÃ–Ã”Ã‡Ã— Admin Marketplace â”œÃ¿â”¬Â¿â”œÃ¿â”¬â•£â”œÃ¿â”¬Â» â”œÃ¿â”¬Ã‘â”œÃ¿â”¬â•‘â”œÃ–Ã”Ã‡Ã—â”œÃ¿â”¬Âºâ”œÃ–Ã”Ã‡Ãœ R3. â”œÃ–â”¼Ã¡â”œÃ¿â”¬Â¼â”œÃ¿â”¬Â¿ â”œÃ¿â”¬Â¬â”œÃ–Ã”Ã‡Ã¡â”œÃ–â”¬Ã¼â”œÃ–â”¼Ã¡â”œÃ¿â”¬â–‘ â”œÃ–Ã£Ã†â”œÃ–Ã”Ã‡Ã— â”œÃ¿â”¬Ã‘â”œÃ¿â”¬Ãâ”œÃ¿â”¬Â»â”œÃ¿â”¬Âºâ”œÃ¿â”¬â–’ â”œÃ–â”¬Ã¼â”œÃ–â”¼Ã¡ â”œÃ–â”¬Ã¼â”œÃ¿â”¬â–’â”œÃ¿â”¬â•£ â”œÃ–â•¦Ã¥Pull Request â”œÃ–Ã”Ã‡Âªâ”œÃ¿â”¬â”‚â”œÃ¿â”¬Â¬â”œÃ–Ã”Ã‡Ãœâ”œÃ–Ã”Ã‡Ã—â”œÃ–â”¼Ã¡â”œÃ–Ã”Ã‡Ã¡â”œÃ¿â”¼Ã† â”œÃ–Ã”Ã‡Âªâ”œÃ¿â”¬â•£ â”œÃ–Ã”Ã‡Âªâ”œÃ–Ã”Ã‡Ã¡â”œÃ¿â”¬â•£ â”œÃ¿â”¬Âºâ”œÃ–Ã”Ã‡Ã—â”œÃ¿â”¬Â¬â”œÃ–â•¦Ã¥â”œÃ¿â”¬â”‚â”œÃ¿â”¬â•£ â”œÃ¿â”¬Ã‘â”œÃ–Ã”Ã‡Ã—â”œÃ–Ã”Ã‡â–‘ â”œÃ–Ã”Ã‡Ã¡â”œÃ¿â”¬Ã€â”œÃ¿â”¬Âºâ”œÃ–Ã”Ã‡Ãœ â”œÃ¿â”¬Âºâ”œÃ–Ã”Ã‡Ã—â”œÃ¿â”¬Ã‘â”œÃ¿â”¬Ãâ”œÃ¿â”¬Â»â”œÃ¿â”¬Âºâ”œÃ¿â”¬â–’ â”œÃ¿â”¬Âºâ”œÃ–Ã”Ã‡Ã—â”œÃ–Ã”Ã‡Ã—â”œÃ¿â”¬Âºâ”œÃ¿â”¬Â¡â”œÃ–Ã”Ã‡Ãœ â”œÃ–Ã”Ã‡Ãœâ”œÃ¿â”¬Â¿â”œÃ–Ã”Ã‡Ã— â”œÃ¿â”¬Ã‘â”œÃ¿â”¬â•‘â”œÃ–Ã”Ã‡Ã—â”œÃ¿â”¬Âºâ”œÃ–Ã”Ã‡Ãœ â”œÃ¿â”¬Âºâ”œÃ–Ã”Ã‡Ã—â”œÃ¿â”¬Ã‘â”œÃ¿â”¬Ãâ”œÃ¿â”¬Â»â”œÃ¿â”¬Âºâ”œÃ¿â”¬â–’ â”œÃ¿â”¬Âºâ”œÃ–Ã”Ã‡Ã—â”œÃ¿â”¬Â¡â”œÃ¿â”¬Âºâ”œÃ–Ã”Ã‡Ã—â”œÃ–â”¼Ã¡.
.\docs\ADMIN_MARKETPLACE_HANDOFF.md:2045:authority and MFA step-up enforcement
.\docs\ADMIN_MARKETPLACE_HANDOFF.md:2069:active platform_admin only
.\docs\ADMIN_MARKETPLACE_HANDOFF.md:2070:delegated supervisors denied by default
.\docs\ADMIN_MARKETPLACE_HANDOFF.md:2073:sensitive operations require valid MFA step-up
.\docs\ADMIN_MARKETPLACE_HANDOFF.md:2102:## ADMIN-MARKET-R6 â”œÃ³Ã”Ã©Â¼Ã”Ã‡Ã˜ Private Admin Marketplace UI
.\docs\ADMIN_MARKETPLACE_HANDOFF.md:2110:â”œÃ¿â”¬Ã‘â”œÃ¿â”¬Â«â”œÃ–â”¬Ã¼â”œÃ¿â”¬Âºâ”œÃ¿â”¬Ã­ â”œÃ¿â”¬Âºâ”œÃ–Ã”Ã‡Ã—â”œÃ¿â”¬â–’â”œÃ¿â”¬Âºâ”œÃ¿â”¬Â¿â”œÃ¿â”¬Ã€ â”œÃ–â”¬Ã¼â”œÃ–â”¼Ã¡ â”œÃ¿â”¬Âºâ”œÃ–Ã”Ã‡Ã—â”œÃ–â•¦Ã¥â”œÃ¿â”¬Âºâ”œÃ¿â”¬Â¼â”œÃ–Ã”Ã‡Ã­â”œÃ¿â”¬Â® â”œÃ–Ã”Ã‡Ã—â”œÃ–â”¼Ã¡â”œÃ¿â”¬â”‚ â”œÃ¿â”¬Â¡â”œÃ–Ã”Ã‡Âªâ”œÃ¿â”¬Âºâ”œÃ–â”¼Ã¡â”œÃ¿â”¬Â® â”œÃ–Ã£Ã†â”œÃ¿â”¬Âºâ”œÃ–â”¬Ã¼â”œÃ–â”¼Ã¡â”œÃ¿â”¬Â®. â”œÃ–â”¼Ã¡â”œÃ¿â”¬Â¼â”œÃ¿â”¬Â¿ â”œÃ¿â”¬Ãºâ”œÃ–Ã”Ã‡Ã¡ â”œÃ–â”¼Ã¡â”œÃ¿â”¬Â¿â”œÃ–Ã”Ã‡Ãœâ”œÃ–Ã”Ã‡â–‘ â”œÃ¿â”¬Âºâ”œÃ–Ã”Ã‡Ã—â”œÃ¿â”¬â–’â”œÃ–â”¬Ã¼â”œÃ¿â”¬Ã‚ â”œÃ–Ã”Ã‡Âªâ”œÃ–â”¬Ã¼â”œÃ¿â”¬â–’â”œÃ–â•¦Ã¥â”œÃ¿â”¬Ã‚â”œÃ–Ã”Ã‡â•£â”œÃ¿â”¬Âº â”œÃ–â”¬Ã¼â”œÃ–â”¼Ã¡ backend â”œÃ–â•¦Ã¥application boundariesâ”œÃ¿â”¼Ã† â”œÃ–Ã”Ã‡Âªâ”œÃ¿â”¬â•£ â”œÃ¿â”¬Âºâ”œÃ¿â”¬Â«â”œÃ¿â”¬Â¬â”œÃ¿â”¬Â¿â”œÃ¿â”¬Âºâ”œÃ¿â”¬â–’â”œÃ¿â”¬Âºâ”œÃ¿â”¬Â¬ â”œÃ¿â”¬â–’â”œÃ–â”¬Ã¼â”œÃ¿â”¬Ã‚ â”œÃ¿â”¬Ãâ”œÃ¿â”¬â–’â”œÃ–â”¼Ã¡â”œÃ¿â”¬Â¡â”œÃ¿â”¬Â® â”œÃ–Ã”Ã‡Ã—â”œÃ–Ã”Ã‡Ã—â”œÃ–Ã”Ã©Â¼delegated supervisors.
.\docs\ADMIN_MARKETPLACE_HANDOFF.md:2124:step-up prompts for sensitive operations
.\docs\ADMIN_MARKETPLACE_HANDOFF.md:2215:â”œÃ¿â”¬Ã‘â”œÃ¿â”¬â•‘â”œÃ–Ã”Ã‡Ã—â”œÃ¿â”¬Âºâ”œÃ–Ã”Ã‡Ãœ Admin Marketplace â”œÃ¿â”¬Â¬â”œÃ¿â”¬â”¤â”œÃ¿â”¬â•‘â”œÃ–â”¼Ã¡â”œÃ–Ã”Ã‡Ã—â”œÃ–â”¼Ã¡â”œÃ–Ã”Ã‡â•£â”œÃ¿â”¬Âº â”œÃ–â•¦Ã¥â”œÃ¿â”¬Ãºâ”œÃ–Ã”Ã‡Âªâ”œÃ–Ã”Ã‡Ã¡â”œÃ–â”¼Ã¡â”œÃ–Ã”Ã‡â•£â”œÃ¿â”¬Âº â”œÃ–Ã”Ã‡Ãœâ”œÃ¿â”¬Â¿â”œÃ–Ã”Ã‡Ã— â”œÃ¿â”¬Âºâ”œÃ–Ã”Ã‡Ã—â”œÃ¿â”¬Âºâ”œÃ–Ã”Ã‡Ã¡â”œÃ¿â”¬Â¬â”œÃ–Ã”Ã‡Ãœâ”œÃ¿â”¬Âºâ”œÃ–Ã”Ã‡Ã— â”œÃ¿â”¬Ã‘â”œÃ–Ã”Ã‡Ã—â”œÃ–Ã”Ã‡â–‘ â”œÃ¿â”¬Âºâ”œÃ–Ã”Ã‡Ã—â”œÃ–Ã”Ã‡Âªâ”œÃ¿â”¬â–’â”œÃ¿â”¬Â¡â”œÃ–Ã”Ã‡Ã—â”œÃ¿â”¬Â® C.
.\docs\ADMIN_MARKETPLACE_HANDOFF.md:2240:DELEGATED_SUPERVISORS_DENIED=True
.\docs\ADMIN_MARKETPLACE_HANDOFF.md:2250:# 39. â”œÃ¿â”¬Â«â”œÃ¿â”¬Âºâ”œÃ¿â”¬â–’â”œÃ¿â”¬Ã€â”œÃ¿â”¬Â® â”œÃ¿â”¬Âºâ”œÃ–Ã”Ã‡Ã—â”œÃ–Ã”Ã‡Âªâ”œÃ¿â”¬â”¤â”œÃ¿â”¬â–’â”œÃ–â•¦Ã¥â”œÃ¿â”¬â•£ â”œÃ¿â”¬Â¿â”œÃ¿â”¬â•£â”œÃ¿â”¬Â» Admin Marketplace
.\docs\ADMIN_MARKETPLACE_HANDOFF.md:2258:Phase B â”œÃ³Ã”Ã©Â¼Ã”Ã‡Ã˜ Admin Marketplace
.\docs\ADMIN_MARKETPLACE_HANDOFF.md:2357:Admin Marketplace end-to-end verification
.\docs\ADMIN_MARKETPLACE_HANDOFF.md:2441:Requires private admin API authorization matrix and step-up enforcement.
.\docs\ADMIN_MARKETPLACE_HANDOFF.md:2444:Requires private admin UI completion and backend denial tests for delegated supervisors.
.\docs\ADMIN_MARKETPLACE_HANDOFF.md:2456:Requires complete Admin Marketplace security, audit, reconciliation, operations and CI closure.
.\docs\architecture\identity-auth-data-model-r2.md:22:`auth_mfa_factors` stores the TOTP seed only as authenticated ciphertext plus a
.\docs\architecture\identity-auth-data-model-r2.md:28:`auth_mfa_recovery_codes` stores one-way hashes only and records single use.
.\docs\architecture\identity-auth-data-model-r2.md:29:`auth_mfa_challenges` stores a hash of the short-lived challenge handle, its
.\docs\commercial\GROUP2_COMMERCIAL_UI_FOUNDATION_INVENTORY.md:7:checkout, local Tunisia payment choice, and Admin Marketplace.
.\docs\commercial\GROUP2_COMMERCIAL_UI_FOUNDATION_INVENTORY.md:16:- Keep delegated supervisors denied from Admin Marketplace.
.\docs\commercial\GROUP2_COMMERCIAL_UI_FOUNDATION_INVENTORY.md:156:alembic\versions\20260727_0011_admin_marketplace_persistence.py
.\docs\commercial\GROUP2_COMMERCIAL_UI_FOUNDATION_INVENTORY.md:158:docs\ADMIN_MARKETPLACE_HANDOFF.md
.\docs\commercial\GROUP2_COMMERCIAL_UI_FOUNDATION_INVENTORY.md:177:processual_api\admin_marketplace\__init__.py
.\docs\commercial\GROUP2_COMMERCIAL_UI_FOUNDATION_INVENTORY.md:178:processual_api\admin_marketplace\audit_contracts.py
.\docs\commercial\GROUP2_COMMERCIAL_UI_FOUNDATION_INVENTORY.md:179:processual_api\admin_marketplace\authority.py
.\docs\commercial\GROUP2_COMMERCIAL_UI_FOUNDATION_INVENTORY.md:180:processual_api\admin_marketplace\contracts.py
.\docs\commercial\GROUP2_COMMERCIAL_UI_FOUNDATION_INVENTORY.md:181:processual_api\admin_marketplace\errors.py
.\docs\commercial\GROUP2_COMMERCIAL_UI_FOUNDATION_INVENTORY.md:182:processual_api\admin_marketplace\models.py
.\docs\commercial\GROUP2_COMMERCIAL_UI_FOUNDATION_INVENTORY.md:183:processual_api\admin_marketplace\persistence\__init__.py
.\docs\commercial\GROUP2_COMMERCIAL_UI_FOUNDATION_INVENTORY.md:184:processual_api\admin_marketplace\persistence\errors.py
.\docs\commercial\GROUP2_COMMERCIAL_UI_FOUNDATION_INVENTORY.md:185:processual_api\admin_marketplace\persistence\integrity.py
.\docs\commercial\GROUP2_COMMERCIAL_UI_FOUNDATION_INVENTORY.md:186:processual_api\admin_marketplace\persistence\protocols.py
.\docs\commercial\GROUP2_COMMERCIAL_UI_FOUNDATION_INVENTORY.md:187:processual_api\admin_marketplace\persistence\repositories.py
.\docs\commercial\GROUP2_COMMERCIAL_UI_FOUNDATION_INVENTORY.md:188:processual_api\admin_marketplace\persistence\unit_of_work.py
.\docs\commercial\GROUP2_COMMERCIAL_UI_FOUNDATION_INVENTORY.md:214:tests\test_admin_marketplace_audit_contracts_r1.py
.\docs\commercial\GROUP2_COMMERCIAL_UI_FOUNDATION_INVENTORY.md:215:tests\test_admin_marketplace_authority_r1.py
.\docs\commercial\GROUP2_COMMERCIAL_UI_FOUNDATION_INVENTORY.md:216:tests\test_admin_marketplace_channel_policy_r1.py
.\docs\commercial\GROUP2_COMMERCIAL_UI_FOUNDATION_INVENTORY.md:217:tests\test_admin_marketplace_commercial_policy_repositories_r3.py
.\docs\commercial\GROUP2_COMMERCIAL_UI_FOUNDATION_INVENTORY.md:218:tests\test_admin_marketplace_contracts_r1.py
.\docs\commercial\GROUP2_COMMERCIAL_UI_FOUNDATION_INVENTORY.md:219:tests\test_admin_marketplace_exports_r1.py
.\docs\commercial\GROUP2_COMMERCIAL_UI_FOUNDATION_INVENTORY.md:220:tests\test_admin_marketplace_integrity_translation_r3.py
.\docs\commercial\GROUP2_COMMERCIAL_UI_FOUNDATION_INVENTORY.md:221:tests\test_admin_marketplace_migration_r2.py
.\docs\commercial\GROUP2_COMMERCIAL_UI_FOUNDATION_INVENTORY.md:222:tests\test_admin_marketplace_models_r2.py
.\docs\commercial\GROUP2_COMMERCIAL_UI_FOUNDATION_INVENTORY.md:223:tests\test_admin_marketplace_payment_repositories_r3.py
.\docs\commercial\GROUP2_COMMERCIAL_UI_FOUNDATION_INVENTORY.md:224:tests\test_admin_marketplace_repositories_r3.py
.\docs\commercial\GROUP2_COMMERCIAL_UI_FOUNDATION_INVENTORY.md:225:tests\test_admin_marketplace_repository_contracts_r3.py
.\docs\commercial\GROUP2_COMMERCIAL_UI_FOUNDATION_INVENTORY.md:226:tests\test_admin_marketplace_transactional_repositories_r3.py
.\docs\commercial\GROUP2_COMMERCIAL_UI_FOUNDATION_INVENTORY.md:227:tests\test_admin_marketplace_unit_of_work_r3.py
.\docs\commercial\GROUP2_COMMERCIAL_UI_FOUNDATION_INVENTORY.md:269:.\alembic\versions\20260727_0011_admin_marketplace_persistence.py
.\docs\commercial\GROUP2_COMMERCIAL_UI_FOUNDATION_INVENTORY.md:271:.\processual_api\admin_marketplace\__init__.py
.\docs\commercial\GROUP2_COMMERCIAL_UI_FOUNDATION_INVENTORY.md:272:.\processual_api\admin_marketplace\audit_contracts.py
.\docs\commercial\GROUP2_COMMERCIAL_UI_FOUNDATION_INVENTORY.md:273:.\processual_api\admin_marketplace\authority.py
.\docs\commercial\GROUP2_COMMERCIAL_UI_FOUNDATION_INVENTORY.md:274:.\processual_api\admin_marketplace\contracts.py
.\docs\commercial\GROUP2_COMMERCIAL_UI_FOUNDATION_INVENTORY.md:275:.\processual_api\admin_marketplace\errors.py
.\docs\commercial\GROUP2_COMMERCIAL_UI_FOUNDATION_INVENTORY.md:276:.\processual_api\admin_marketplace\models.py
.\docs\commercial\GROUP2_COMMERCIAL_UI_FOUNDATION_INVENTORY.md:277:.\processual_api\admin_marketplace\persistence\__init__.py
.\docs\commercial\GROUP2_COMMERCIAL_UI_FOUNDATION_INVENTORY.md:278:.\processual_api\admin_marketplace\persistence\errors.py
.\docs\commercial\GROUP2_COMMERCIAL_UI_FOUNDATION_INVENTORY.md:279:.\processual_api\admin_marketplace\persistence\integrity.py
.\docs\commercial\GROUP2_COMMERCIAL_UI_FOUNDATION_INVENTORY.md:280:.\processual_api\admin_marketplace\persistence\protocols.py
.\docs\commercial\GROUP2_COMMERCIAL_UI_FOUNDATION_INVENTORY.md:281:.\processual_api\admin_marketplace\persistence\repositories.py
.\docs\commercial\GROUP2_COMMERCIAL_UI_FOUNDATION_INVENTORY.md:282:.\processual_api\admin_marketplace\persistence\unit_of_work.py
.\docs\commercial\GROUP2_COMMERCIAL_UI_FOUNDATION_INVENTORY.md:288:.\processual_api\auth\mfa_router.py
.\docs\commercial\GROUP2_COMMERCIAL_UI_FOUNDATION_INVENTORY.md:432:.\tests\test_admin_marketplace_audit_contracts_r1.py
.\docs\commercial\GROUP2_COMMERCIAL_UI_FOUNDATION_INVENTORY.md:433:.\tests\test_admin_marketplace_authority_r1.py
.\docs\commercial\GROUP2_COMMERCIAL_UI_FOUNDATION_INVENTORY.md:434:.\tests\test_admin_marketplace_channel_policy_r1.py
.\docs\commercial\GROUP2_COMMERCIAL_UI_FOUNDATION_INVENTORY.md:435:.\tests\test_admin_marketplace_commercial_policy_repositories_r3.py
.\docs\commercial\GROUP2_COMMERCIAL_UI_FOUNDATION_INVENTORY.md:436:.\tests\test_admin_marketplace_contracts_r1.py
.\docs\commercial\GROUP2_COMMERCIAL_UI_FOUNDATION_INVENTORY.md:437:.\tests\test_admin_marketplace_exports_r1.py
.\docs\commercial\GROUP2_COMMERCIAL_UI_FOUNDATION_INVENTORY.md:438:.\tests\test_admin_marketplace_integrity_translation_r3.py
.\docs\commercial\GROUP2_COMMERCIAL_UI_FOUNDATION_INVENTORY.md:439:.\tests\test_admin_marketplace_migration_r2.py
.\docs\commercial\GROUP2_COMMERCIAL_UI_FOUNDATION_INVENTORY.md:440:.\tests\test_admin_marketplace_models_r2.py
.\docs\commercial\GROUP2_COMMERCIAL_UI_FOUNDATION_INVENTORY.md:441:.\tests\test_admin_marketplace_payment_repositories_r3.py
.\docs\commercial\GROUP2_COMMERCIAL_UI_FOUNDATION_INVENTORY.md:442:.\tests\test_admin_marketplace_repositories_r3.py
.\docs\commercial\GROUP2_COMMERCIAL_UI_FOUNDATION_INVENTORY.md:443:.\tests\test_admin_marketplace_repository_contracts_r3.py
.\docs\commercial\GROUP2_COMMERCIAL_UI_FOUNDATION_INVENTORY.md:444:.\tests\test_admin_marketplace_transactional_repositories_r3.py
.\docs\commercial\GROUP2_COMMERCIAL_UI_FOUNDATION_INVENTORY.md:445:.\tests\test_admin_marketplace_unit_of_work_r3.py
.\docs\commercial\GROUP2_COMMERCIAL_UI_FOUNDATION_INVENTORY.md:465:.\tests\test_auth_mfa_http_r8.py
.\docs\commercial\GROUP2_COMMERCIAL_UI_FOUNDATION_INVENTORY.md:859:.\tests\test_auth_account_recovery_contracts_r9a.py:75:            role="platform_admin",
.\docs\commercial\GROUP2_COMMERCIAL_UI_FOUNDATION_INVENTORY.md:897:.\processual_api\auth\mfa_repository.py:70:    async def disable_pending_factors(self, user_id: uuid.UUID, *, disabled_at: datetime) -> None:
.\docs\commercial\GROUP2_COMMERCIAL_UI_FOUNDATION_INVENTORY.md:898:.\processual_api\auth\mfa_repository.py:74:            .values(status="disabled", disabled_at=disabled_at)
.\docs\commercial\GROUP2_COMMERCIAL_UI_FOUNDATION_INVENTORY.md:945:.\tests\test_auth_mfa_service_r8.py:52:    async def disable_pending_factors(self, user_id, *, disabled_at):
.\docs\commercial\GROUP2_COMMERCIAL_UI_FOUNDATION_INVENTORY.md:946:.\tests\test_auth_mfa_service_r8.py:54:            self.factor.status = "disabled"
.\docs\commercial\GROUP2_COMMERCIAL_UI_FOUNDATION_INVENTORY.md:947:.\tests\test_auth_mfa_service_r8.py:65:            disabled_at=None,
.\docs\commercial\GROUP2_COMMERCIAL_UI_FOUNDATION_INVENTORY.md:948:.\tests\test_auth_mfa_service_r8.py:227:    assert repository.factor.status == "disabled"
.\docs\commercial\GROUP2_COMMERCIAL_UI_FOUNDATION_INVENTORY.md:953:.\tests\test_auth_mfa_http_r8.py:121:    disabled = client.post("/auth/mfa/disable")
.\docs\commercial\GROUP2_COMMERCIAL_UI_FOUNDATION_INVENTORY.md:954:.\tests\test_auth_mfa_http_r8.py:130:    assert disabled.json() == {"status": "processed"}
.\docs\commercial\GROUP2_COMMERCIAL_UI_FOUNDATION_INVENTORY.md:1074:.\tests\test_auth_registration_http_r5b_r1.py:173:        json=_individual_payload(password=secret, role="platform_admin", plan_id="enterprise"),
.\processual_api\middleware\subscription.py:38:    "/auth/mfa/status",
.\processual_api\middleware\subscription.py:39:    "/auth/mfa/totp/enroll",
.\processual_api\middleware\subscription.py:40:    "/auth/mfa/totp/confirm",
.\processual_api\middleware\subscription.py:41:    "/auth/mfa/verify",
.\processual_api\middleware\subscription.py:42:    "/auth/mfa/recovery-codes/regenerate",
.\processual_api\middleware\subscription.py:43:    "/auth/mfa/disable",
.\processual_api\main.py:82:from .auth.mfa_router import router as mfa_router
.\processual_api\main.py:150:app.include_router(mfa_router)
.\processual_api\auth\token_material.py:53:            digest=self.digest(raw, purpose="mfa_recovery_code"),
.\processual_api\auth\session_service.py:73:        mfa_required: bool = False,
.\processual_api\auth\session_service.py:87:                scopes=["auth:mfa"] if mfa_required else ["evaluation"],
.\processual_api\auth\session_service.py:137:            mfa_required = await repository.requires_mfa(user.id)
.\processual_api\auth\session_service.py:152:                mfa_satisfied_at=None,
.\processual_api\auth\session_service.py:161:            mfa_required=mfa_required,
.\processual_api\auth\session_service.py:171:            mfa_required=mfa_required,
.\processual_api\auth\session_router.py:213:        mfa_required=True if issued.mfa_required else None,
.\processual_api\auth\session_repository.py:11:    AuthMfaFactor,
.\processual_api\auth\session_repository.py:59:    async def requires_mfa(self, user_id: uuid.UUID) -> bool:
.\processual_api\auth\session_repository.py:61:            select(AuthMfaFactor.id)
.\processual_api\auth\session_repository.py:62:            .where(AuthMfaFactor.user_id == user_id, AuthMfaFactor.status == "active")
.\processual_api\auth\session_repository.py:74:        active_platform_admin_authority_id = await self._session.scalar(
.\processual_api\auth\session_repository.py:78:                IdentityPlatformAuthority.authority == "platform_admin",
.\processual_api\auth\session_repository.py:86:            or active_platform_admin_authority_id is not None
.\processual_api\auth\session_repository.py:100:        mfa_satisfied_at: datetime | None = None,
.\processual_api\auth\session_repository.py:110:            mfa_satisfied_at=mfa_satisfied_at,
.\processual_api\auth\session_contracts.py:21:    mfa_required: bool | None = None
.\processual_api\auth\session_contracts.py:48:    mfa_required: bool = False
.\processual_api\auth\security.py:290:        AuthMfaFactor,
.\processual_api\auth\security.py:319:            active_mfa_factor_id = await db_session.scalar(
.\processual_api\auth\security.py:320:                select(AuthMfaFactor.id)
.\processual_api\auth\security.py:322:                    AuthMfaFactor.user_id == user_uuid,
.\processual_api\auth\security.py:323:                    AuthMfaFactor.status == "active",
.\processual_api\auth\security.py:336:            active_platform_admin_authority_id = await db_session.scalar(
.\processual_api\auth\security.py:340:                    IdentityPlatformAuthority.authority == "platform_admin",
.\processual_api\auth\security.py:364:    mfa_required = (
.\processual_api\auth\security.py:365:        active_mfa_factor_id is not None
.\processual_api\auth\security.py:367:        or active_platform_admin_authority_id is not None
.\processual_api\auth\security.py:369:    mfa_pending = mfa_required and auth_session.mfa_satisfied_at is None
.\processual_api\auth\security.py:370:    return str(user.id), authoritative_organization, mfa_pending
.\processual_api\auth\security.py:390:            subject, organization_id, mfa_pending = await _validate_identity_session(
.\processual_api\auth\security.py:404:                "scopes": ["auth:mfa"] if mfa_pending else ["evaluation"],
.\processual_api\auth\security.py:405:                "mfa_pending": mfa_pending,
.\processual_api\auth\security.py:406:                "mfa_satisfied_at": (
.\processual_api\auth\security.py:407:                    None if mfa_pending else payload.get("mfa_satisfied_at")
.\processual_api\auth\security.py:486:def require_recent_mfa(max_age_seconds: int = 300):
.\processual_api\auth\security.py:488:        raise ValueError("MFA step-up lifetime is outside its safe range.")
.\processual_api\auth\security.py:490:    async def _recent_mfa_dependency(current_user: dict = Depends(get_current_user)) -> dict:
.\processual_api\auth\security.py:520:            or auth_session.mfa_satisfied_at is None
.\processual_api\auth\security.py:521:            or auth_session.mfa_satisfied_at < now - timedelta(seconds=max_age_seconds)
.\processual_api\auth\security.py:525:                detail="Recent MFA verification required.",
.\processual_api\auth\security.py:529:    return _recent_mfa_dependency
.\processual_api\auth\security.py:531:def require_platform_admin_step_up(
.\processual_api\auth\security.py:535:        settings.auth_mfa_step_up_seconds
.\processual_api\auth\security.py:541:            "Platform-admin step-up lifetime is outside its safe range."
.\processual_api\auth\security.py:544:    async def _platform_admin_step_up_dependency(
.\processual_api\auth\security.py:580:                            == "platform_admin",
.\processual_api\auth\security.py:590:                detail="Platform administrator step-up required.",
.\processual_api\auth\security.py:610:            or auth_session.mfa_satisfied_at is None
.\processual_api\auth\security.py:611:            or auth_session.mfa_satisfied_at
.\processual_api\auth\security.py:616:                detail="Recent MFA verification required.",
.\processual_api\auth\security.py:621:    return _platform_admin_step_up_dependency
.\processual_api\auth\registration_contracts.py:21:    PLATFORM_ADMIN_BOOTSTRAP = "platform_admin_bootstrap"
.\processual_api\auth\registration_contracts.py:33:    PLATFORM_ADMIN = "platform_admin"
.\processual_api\auth\registration_contracts.py:127:    mfa_primary_method: str = "totp"
.\processual_api\auth\registration_contracts.py:134:    privileged_mfa_required: bool = True
.\processual_api\auth\registration_contracts.py:135:    mfa_secret_encrypted: bool = True
.\processual_api\auth\registration_contracts.py:136:    mfa_recovery_codes_hashed: bool = True
.\processual_api\auth\registration_contracts.py:137:    mfa_replay_protection_required: bool = True
.\processual_api\auth\registration_contracts.py:138:    platform_admin_public_registration: bool = False
.\processual_api\auth\registration_contracts.py:144:    raw_mfa_secret_persisted: bool = False
.\processual_api\auth\registration_contracts.py:162:        if self.mfa_primary_method != "totp":
.\processual_api\auth\registration_contracts.py:172:            "privileged_mfa_required": self.privileged_mfa_required,
.\processual_api\auth\registration_contracts.py:173:            "mfa_secret_encrypted": self.mfa_secret_encrypted,
.\processual_api\auth\registration_contracts.py:174:            "mfa_recovery_codes_hashed": self.mfa_recovery_codes_hashed,
.\processual_api\auth\registration_contracts.py:175:            "mfa_replay_protection_required": (self.mfa_replay_protection_required),
.\processual_api\auth\registration_contracts.py:182:            "platform_admin_public_registration": (self.platform_admin_public_registration),
.\processual_api\auth\registration_contracts.py:188:            "raw_mfa_secret_persisted": self.raw_mfa_secret_persisted,
.\processual_api\auth\registration_contracts.py:197:        if RegistrationMode.PLATFORM_ADMIN_BOOTSTRAP in (self.public_self_service_modes):
.\processual_api\auth\registration_contracts.py:199:        if MembershipRole.PLATFORM_ADMIN in self.invitable_roles:
.\processual_api\auth\recovery_email_verification_service.py:22:    async def platform_admin_user(
.\processual_api\auth\recovery_email_verification_service.py:125:        recent_step_up: bool,
.\processual_api\auth\recovery_email_verification_service.py:127:        if not recent_step_up:
.\processual_api\auth\recovery_email_verification_service.py:129:                "Recent MFA step-up is required."
.\processual_api\auth\recovery_email_verification_service.py:144:            actor = await repository.platform_admin_user(
.\processual_api\auth\recovery_email_verification_service.py:263:        recent_step_up: bool,
.\processual_api\auth\recovery_email_verification_service.py:265:        if not recent_step_up:
.\processual_api\auth\recovery_email_verification_service.py:267:                "Recent MFA step-up is required."
.\processual_api\auth\recovery_email_verification_service.py:273:            actor = await unit.repository.platform_admin_user(
.\processual_api\auth\recovery_email_verification_repository.py:23:    async def platform_admin_user(
.\processual_api\auth\recovery_email_verification_repository.py:40:                == "platform_admin",
.\processual_api\auth\recovery_email_router.py:39:    require_platform_admin_step_up,
.\processual_api\auth\recovery_email_router.py:69:platform_admin_step_up_dependency = (
.\processual_api\auth\recovery_email_router.py:70:    require_platform_admin_step_up()
.\processual_api\auth\recovery_email_router.py:170:        platform_admin_step_up_dependency
.\processual_api\auth\recovery_email_router.py:204:            recent_step_up=True,
.\processual_api\auth\recovery_email_router.py:243:        platform_admin_step_up_dependency
.\processual_api\auth\recovery_email_router.py:332:    "platform_admin_step_up_dependency",
.\processual_api\auth\rate_limit.py:140:MFA_VERIFICATION_RULES = (
.\processual_api\auth\rate_limit.py:293:    "MFA_VERIFICATION_RULES",
.\processual_api\auth\platform_supervisor_service.py:11:    async def active_platform_admin(self, *, user_id: uuid.UUID): ...
.\processual_api\auth\platform_supervisor_service.py:82:        recent_step_up: bool,
.\processual_api\auth\platform_supervisor_service.py:84:        if not recent_step_up:
.\processual_api\auth\platform_supervisor_service.py:86:                "Recent platform-administrator MFA step-up is required."
.\processual_api\auth\platform_supervisor_service.py:95:            if await repository.active_platform_admin(
.\processual_api\auth\platform_supervisor_service.py:108:                authority="platform_admin",
.\processual_api\auth\platform_supervisor_service.py:154:        recent_step_up: bool,
.\processual_api\auth\platform_supervisor_service.py:156:        if not recent_step_up:
.\processual_api\auth\platform_supervisor_service.py:158:                "Recent platform-administrator MFA step-up is required."
.\processual_api\auth\platform_supervisor_service.py:169:            if await repository.active_platform_admin(
.\processual_api\auth\platform_supervisor_repository.py:17:    async def active_platform_admin(self, *, user_id: uuid.UUID):
.\processual_api\auth\platform_supervisor_repository.py:23:                IdentityPlatformAuthority.authority == "platform_admin",
.\processual_api\auth\platform_admin_bootstrap_service.py:16:from processual_api.auth.platform_admin_bootstrap_repository import (
.\processual_api\auth\platform_admin_bootstrap_service.py:24:    async def platform_admin_authority_exists(
.\processual_api\auth\platform_admin_bootstrap_service.py:33:    def add_first_platform_admin(
.\processual_api\auth\platform_admin_bootstrap_service.py:80:    authority: str = "platform_admin"
.\processual_api\auth\platform_admin_bootstrap_service.py:81:    mfa_required: bool = True
.\processual_api\auth\platform_admin_bootstrap_service.py:188:                    .platform_admin_authority_exists()
.\processual_api\auth\platform_admin_bootstrap_service.py:204:                repository.add_first_platform_admin(
.\processual_api\auth\platform_admin_bootstrap_repository.py:16:PLATFORM_ADMIN_BOOTSTRAP_LOCK_ID = 781_204_601
.\processual_api\auth\platform_admin_bootstrap_repository.py:31:                    PLATFORM_ADMIN_BOOTSTRAP_LOCK_ID
.\processual_api\auth\platform_admin_bootstrap_repository.py:36:    async def platform_admin_authority_exists(self) -> bool:
.\processual_api\auth\platform_admin_bootstrap_repository.py:41:                == "platform_admin",
.\processual_api\auth\platform_admin_bootstrap_repository.py:64:    def add_first_platform_admin(
.\processual_api\auth\platform_admin_bootstrap_repository.py:88:            authority="platform_admin",
.\processual_api\auth\platform_admin_bootstrap_repository.py:91:            grant_reason="initial_platform_admin_bootstrap",
.\processual_api\auth\platform_admin_bootstrap_repository.py:154:    "PLATFORM_ADMIN_BOOTSTRAP_LOCK_ID",
.\processual_api\auth\platform_admin_bootstrap.py:9:from processual_api.auth.platform_admin_bootstrap_repository import (
.\processual_api\auth\platform_admin_bootstrap.py:12:from processual_api.auth.platform_admin_bootstrap_service import (
.\processual_api\auth\platform_admin_bootstrap.py:22:    "AUTH_PLATFORM_ADMIN_BOOTSTRAP_SECRET_SHA256"
.\processual_api\auth\platform_admin_bootstrap.py:128:        "PlatformAdminMfaRequired="
.\processual_api\auth\platform_admin_bootstrap.py:129:        f"{receipt.mfa_required}"
.\processual_api\auth\platform_admin_bootstrap.py:136:        "NextAction=login_and_complete_mfa"
.\processual_api\auth\models.py:86:    mfa_factors: Mapped[list[AuthMfaFactor]] = relationship(
.\processual_api\auth\models.py:194:            "authority IN ('platform_admin', 'platform_supervisor')",
.\processual_api\auth\models.py:217:        default="platform_admin",
.\processual_api\auth\models.py:322:    mfa_satisfied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
.\processual_api\auth\models.py:549:class AuthMfaFactor(Base):
.\processual_api\auth\models.py:550:    __tablename__ = "auth_mfa_factors"
.\processual_api\auth\models.py:554:        UniqueConstraint("user_id", "factor_type", "label", name="uq_auth_mfa_factor_user_type_label"),
.\processual_api\auth\models.py:555:        Index("ix_auth_mfa_factors_user_status", "user_id", "status"),
.\processual_api\auth\models.py:575:    user: Mapped[IdentityUser] = relationship(back_populates="mfa_factors")
.\processual_api\auth\models.py:576:    recovery_codes: Mapped[list[AuthMfaRecoveryCode]] = relationship(
.\processual_api\auth\models.py:582:class AuthMfaRecoveryCode(Base):
.\processual_api\auth\models.py:583:    __tablename__ = "auth_mfa_recovery_codes"
.\processual_api\auth\models.py:588:        ForeignKey("auth_mfa_factors.id", ondelete="CASCADE"),
.\processual_api\auth\models.py:595:    factor: Mapped[AuthMfaFactor] = relationship(back_populates="recovery_codes")
.\processual_api\auth\models.py:598:class AuthMfaChallenge(Base):
.\processual_api\auth\models.py:599:    __tablename__ = "auth_mfa_challenges"
.\processual_api\auth\models.py:602:        Index("ix_auth_mfa_challenges_user_expiry", "user_id", "expires_at"),
.\processual_api\auth\models.py:627:    AuthMfaFactor,
.\processual_api\auth\models.py:628:    AuthMfaRecoveryCode,
.\processual_api\auth\models.py:629:    AuthMfaChallenge,
.\processual_api\auth\mfa_service.py:8:from processual_api.auth.mfa_contracts import MfaEnrollment, MfaStatus
.\processual_api\auth\mfa_service.py:9:from processual_api.auth.mfa_crypto import EncryptedMfaSecret, MfaSecretCipher
.\processual_api\auth\mfa_service.py:19:class InvalidMfaCredentialError(RuntimeError):
.\processual_api\auth\mfa_service.py:20:    """The supplied MFA credential is absent, invalid, or was already used."""
.\processual_api\auth\mfa_service.py:23:class MfaConflictError(RuntimeError):
.\processual_api\auth\mfa_service.py:24:    """The requested MFA lifecycle transition is not allowed."""
.\processual_api\auth\mfa_service.py:27:class MfaStepUpRequiredError(RuntimeError):
.\processual_api\auth\mfa_service.py:28:    """The current session does not contain a sufficiently recent MFA proof."""
.\processual_api\auth\mfa_service.py:31:class MfaAuthorityUnavailableError(RuntimeError):
.\processual_api\auth\mfa_service.py:32:    """The authoritative MFA store or crypto authority is unavailable."""
.\processual_api\auth\mfa_service.py:35:class MfaService:
.\processual_api\auth\mfa_service.py:40:        cipher: MfaSecretCipher,
.\processual_api\auth\mfa_service.py:44:        step_up_ttl: timedelta = timedelta(minutes=5),
.\processual_api\auth\mfa_service.py:48:            raise ValueError("Invalid MFA enrollment policy.")
.\processual_api\auth\mfa_service.py:49:        if step_up_ttl < timedelta(minutes=1) or step_up_ttl > timedelta(minutes=30):
.\processual_api\auth\mfa_service.py:50:            raise ValueError("Invalid MFA step-up lifetime.")
.\processual_api\auth\mfa_service.py:56:        self._step_up_ttl = step_up_ttl
.\processual_api\auth\mfa_service.py:62:            raise ValueError("MFA clock must be timezone-aware.")
.\processual_api\auth\mfa_service.py:66:    def _encrypted_factor(factor) -> EncryptedMfaSecret:
.\processual_api\auth\mfa_service.py:67:        return EncryptedMfaSecret(
.\processual_api\auth\mfa_service.py:80:            raise MfaAuthorityUnavailableError("MFA authority is unavailable.") from exc
.\processual_api\auth\mfa_service.py:96:    async def enroll(self, *, user_id: uuid.UUID, label: str) -> MfaEnrollment:
.\processual_api\auth\mfa_service.py:102:                raise MfaAuthorityUnavailableError("MFA repository is unavailable.")
.\processual_api\auth\mfa_service.py:104:                raise MfaConflictError("An active MFA factor already exists.")
.\processual_api\auth\mfa_service.py:107:                raise MfaAuthorityUnavailableError("MFA identity authority is unavailable.")
.\processual_api\auth\mfa_service.py:124:        return MfaEnrollment(
.\processual_api\auth\mfa_service.py:142:            raise InvalidMfaCredentialError("MFA credential is invalid.")
.\processual_api\auth\mfa_service.py:152:            raise InvalidMfaCredentialError("MFA credential is invalid.")
.\processual_api\auth\mfa_service.py:153:        auth_session.mfa_satisfied_at = now
.\processual_api\auth\mfa_service.py:155:    def _assert_recent_step_up(self, auth_session, *, now: datetime) -> None:
.\processual_api\auth\mfa_service.py:160:            or auth_session.mfa_satisfied_at is None
.\processual_api\auth\mfa_service.py:161:            or auth_session.mfa_satisfied_at < now - self._step_up_ttl
.\processual_api\auth\mfa_service.py:163:            raise MfaStepUpRequiredError("Recent MFA verification is required.")
.\processual_api\auth\mfa_service.py:178:                raise MfaAuthorityUnavailableError("MFA repository is unavailable.")
.\processual_api\auth\mfa_service.py:181:                raise MfaConflictError("No pending MFA enrollment exists.")
.\processual_api\auth\mfa_service.py:208:                raise MfaAuthorityUnavailableError("MFA repository is unavailable.")
.\processual_api\auth\mfa_service.py:211:                raise InvalidMfaCredentialError("MFA credential is invalid.")
.\processual_api\auth\mfa_service.py:216:                digest = self._token_digester.digest(normalized, purpose="mfa_recovery_code")
.\processual_api\auth\mfa_service.py:219:                    raise InvalidMfaCredentialError("MFA credential is invalid.")
.\processual_api\auth\mfa_service.py:222:                raise InvalidMfaCredentialError("MFA credential is invalid.")
.\processual_api\auth\mfa_service.py:231:    async def require_recent_step_up(self, *, user_id: uuid.UUID, session_id: uuid.UUID) -> None:
.\processual_api\auth\mfa_service.py:237:                raise MfaAuthorityUnavailableError("MFA repository is unavailable.")
.\processual_api\auth\mfa_service.py:239:            self._assert_recent_step_up(auth_session, now=now)
.\processual_api\auth\mfa_service.py:253:                raise MfaAuthorityUnavailableError("MFA repository is unavailable.")
.\processual_api\auth\mfa_service.py:255:            self._assert_recent_step_up(auth_session, now=now)
.\processual_api\auth\mfa_service.py:258:                raise MfaConflictError("No active MFA factor exists.")
.\processual_api\auth\mfa_service.py:269:                raise MfaAuthorityUnavailableError("MFA repository is unavailable.")
.\processual_api\auth\mfa_service.py:271:            self._assert_recent_step_up(auth_session, now=now)
.\processual_api\auth\mfa_service.py:273:                raise MfaConflictError("MFA is required for this identity role.")
.\processual_api\auth\mfa_service.py:276:                raise MfaConflictError("No active MFA factor exists.")
.\processual_api\auth\mfa_service.py:284:                reason="mfa_disabled",
.\processual_api\auth\mfa_service.py:288:    async def status(self, *, user_id: uuid.UUID, session_id: uuid.UUID) -> MfaStatus:
.\processual_api\auth\mfa_service.py:294:                raise MfaAuthorityUnavailableError("MFA repository is unavailable.")
.\processual_api\auth\mfa_service.py:301:                and auth_session.mfa_satisfied_at is not None
.\processual_api\auth\mfa_service.py:302:                and auth_session.mfa_satisfied_at >= now - self._step_up_ttl
.\processual_api\auth\mfa_service.py:304:        return MfaStatus(enabled, pending, remaining, satisfied)
.\processual_api\auth\mfa_service.py:308:    "InvalidMfaCredentialError",
.\processual_api\auth\mfa_service.py:309:    "MfaAuthorityUnavailableError",
.\processual_api\auth\mfa_service.py:310:    "MfaConflictError",
.\processual_api\auth\mfa_service.py:311:    "MfaService",
.\processual_api\auth\mfa_service.py:312:    "MfaStepUpRequiredError",
.\processual_api\auth\mfa_runtime.py:9:from processual_api.auth.mfa_crypto import MfaSecretCipher
.\processual_api\auth\mfa_runtime.py:10:from processual_api.auth.mfa_repository import SqlAlchemyMfaUnitOfWork
.\processual_api\auth\mfa_runtime.py:11:from processual_api.auth.mfa_service import MfaService
.\processual_api\auth\mfa_runtime.py:19:class MfaRuntimeUnavailableError(RuntimeError):
.\processual_api\auth\mfa_runtime.py:20:    """A required MFA crypto, persistence, or rate-limit authority is unavailable."""
.\processual_api\auth\mfa_runtime.py:24:class MfaRuntime:
.\processual_api\auth\mfa_runtime.py:25:    service: MfaService
.\processual_api\auth\mfa_runtime.py:32:        raise MfaRuntimeUnavailableError("MFA key authority is unavailable.")
.\processual_api\auth\mfa_runtime.py:43:        raise MfaRuntimeUnavailableError("MFA key authority is invalid.") from exc
.\processual_api\auth\mfa_runtime.py:45:        raise MfaRuntimeUnavailableError("MFA key authority is invalid.")
.\processual_api\auth\mfa_runtime.py:51:        raise MfaRuntimeUnavailableError(f"{label} is unavailable.")
.\processual_api\auth\mfa_runtime.py:55:async def build_mfa_runtime(config: APISettings = settings) -> MfaRuntime:
.\processual_api\auth\mfa_runtime.py:58:        raise MfaRuntimeUnavailableError("MFA rate-limit authority is unavailable.")
.\processual_api\auth\mfa_runtime.py:61:        cipher = MfaSecretCipher(
.\processual_api\auth\mfa_runtime.py:62:            current_key_version=config.auth_mfa_current_key_version or "",
.\processual_api\auth\mfa_runtime.py:63:            keys=_keys(config.auth_mfa_key_ring_json),
.\processual_api\auth\mfa_runtime.py:76:        recovery_count = config.auth_mfa_recovery_code_count
.\processual_api\auth\mfa_runtime.py:77:        step_up_ttl = timedelta(seconds=config.auth_mfa_step_up_seconds)
.\processual_api\auth\mfa_runtime.py:79:            raise ValueError("Invalid MFA recovery-code policy.")
.\processual_api\auth\mfa_runtime.py:80:        if step_up_ttl < timedelta(minutes=1) or step_up_ttl > timedelta(minutes=30):
.\processual_api\auth\mfa_runtime.py:81:            raise ValueError("Invalid MFA step-up lifetime.")
.\processual_api\auth\mfa_runtime.py:82:    except MfaRuntimeUnavailableError:
.\processual_api\auth\mfa_runtime.py:85:        raise MfaRuntimeUnavailableError("MFA authority is unavailable.") from exc
.\processual_api\auth\mfa_runtime.py:87:    def unit_of_work_factory() -> SqlAlchemyMfaUnitOfWork:
.\processual_api\auth\mfa_runtime.py:88:        return SqlAlchemyMfaUnitOfWork(session_factory)
.\processual_api\auth\mfa_runtime.py:90:    return MfaRuntime(
.\processual_api\auth\mfa_runtime.py:91:        service=MfaService(
.\processual_api\auth\mfa_runtime.py:95:            issuer=config.auth_mfa_issuer,
.\processual_api\auth\mfa_runtime.py:97:            step_up_ttl=step_up_ttl,
.\processual_api\auth\mfa_runtime.py:104:__all__ = ["MfaRuntime", "MfaRuntimeUnavailableError", "build_mfa_runtime"]
.\processual_api\auth\mfa_router.py:11:from processual_api.auth.mfa_contracts import (
.\processual_api\auth\mfa_router.py:12:    MfaCodeRequestContract,
.\processual_api\auth\mfa_router.py:13:    MfaEnrollmentRequestContract,
.\processual_api\auth\mfa_router.py:14:    MfaEnrollmentResponseContract,
.\processual_api\auth\mfa_router.py:15:    MfaProcessedResponseContract,
.\processual_api\auth\mfa_router.py:16:    MfaRecoveryCodesResponseContract,
.\processual_api\auth\mfa_router.py:17:    MfaStatusResponseContract,
.\processual_api\auth\mfa_router.py:18:    MfaVerificationRequestContract,
.\processual_api\auth\mfa_router.py:20:from processual_api.auth.mfa_runtime import (
.\processual_api\auth\mfa_router.py:21:    MfaRuntime,
.\processual_api\auth\mfa_router.py:22:    MfaRuntimeUnavailableError,
.\processual_api\auth\mfa_router.py:23:    build_mfa_runtime,
.\processual_api\auth\mfa_router.py:25:from processual_api.auth.mfa_service import (
.\processual_api\auth\mfa_router.py:26:    InvalidMfaCredentialError,
.\processual_api\auth\mfa_router.py:27:    MfaAuthorityUnavailableError,
.\processual_api\auth\mfa_router.py:28:    MfaConflictError,
.\processual_api\auth\mfa_router.py:29:    MfaStepUpRequiredError,
.\processual_api\auth\mfa_router.py:32:    MFA_VERIFICATION_RULES,
.\processual_api\auth\mfa_router.py:39:GENERIC_INVALID = "Invalid MFA credential."
.\processual_api\auth\mfa_router.py:40:GENERIC_UNAVAILABLE = "MFA service temporarily unavailable."
.\processual_api\auth\mfa_router.py:43:class SensitiveMfaAPIRoute(APIRoute):
.\processual_api\auth\mfa_router.py:51:                return JSONResponse(status_code=422, content={"detail": "Invalid MFA request."})
.\processual_api\auth\mfa_router.py:57:    prefix="/auth/mfa",
.\processual_api\auth\mfa_router.py:58:    tags=["identity-mfa"],
.\processual_api\auth\mfa_router.py:59:    route_class=SensitiveMfaAPIRoute,
.\processual_api\auth\mfa_router.py:63:async def get_mfa_runtime() -> MfaRuntime:
.\processual_api\auth\mfa_router.py:65:        return await build_mfa_runtime()
.\processual_api\auth\mfa_router.py:66:    except MfaRuntimeUnavailableError as exc:
.\processual_api\auth\mfa_router.py:79:        "identity_mfa",
.\processual_api\auth\mfa_router.py:82:            "mfa_action": action,
.\processual_api\auth\mfa_router.py:83:            "mfa_result": result,
.\processual_api\auth\mfa_router.py:88:def _client_ip(request: Request, runtime: MfaRuntime) -> str:
.\processual_api\auth\mfa_router.py:99:    runtime: MfaRuntime,
.\processual_api\auth\mfa_router.py:105:            action="mfa_verify",
.\processual_api\auth\mfa_router.py:107:            rules=MFA_VERIFICATION_RULES,
.\processual_api\auth\mfa_router.py:114:            detail="Too many MFA requests.",
.\processual_api\auth\mfa_router.py:124:@router.get("/status", response_model=MfaStatusResponseContract)
.\processual_api\auth\mfa_router.py:125:async def mfa_status(
.\processual_api\auth\mfa_router.py:127:    runtime: MfaRuntime = Depends(get_mfa_runtime),
.\processual_api\auth\mfa_router.py:132:    except MfaAuthorityUnavailableError as exc:
.\processual_api\auth\mfa_router.py:134:    return MfaStatusResponseContract(
.\processual_api\auth\mfa_router.py:138:        step_up_satisfied=result.step_up_satisfied,
.\processual_api\auth\mfa_router.py:142:@router.post("/totp/enroll", response_model=MfaEnrollmentResponseContract)
.\processual_api\auth\mfa_router.py:144:    body: MfaEnrollmentRequestContract,
.\processual_api\auth\mfa_router.py:148:    runtime: MfaRuntime = Depends(get_mfa_runtime),
.\processual_api\auth\mfa_router.py:153:    except MfaConflictError as exc:
.\processual_api\auth\mfa_router.py:154:        raise HTTPException(status_code=409, detail="MFA enrollment is not available.") from exc
.\processual_api\auth\mfa_router.py:155:    except MfaAuthorityUnavailableError as exc:
.\processual_api\auth\mfa_router.py:159:    return MfaEnrollmentResponseContract(
.\processual_api\auth\mfa_router.py:165:@router.post("/totp/confirm", response_model=MfaRecoveryCodesResponseContract)
.\processual_api\auth\mfa_router.py:167:    body: MfaCodeRequestContract,
.\processual_api\auth\mfa_router.py:171:    runtime: MfaRuntime = Depends(get_mfa_runtime),
.\processual_api\auth\mfa_router.py:181:    except InvalidMfaCredentialError as exc:
.\processual_api\auth\mfa_router.py:184:    except MfaConflictError as exc:
.\processual_api\auth\mfa_router.py:185:        raise HTTPException(status_code=409, detail="MFA enrollment is not available.") from exc
.\processual_api\auth\mfa_router.py:186:    except MfaAuthorityUnavailableError as exc:
.\processual_api\auth\mfa_router.py:190:    return MfaRecoveryCodesResponseContract(recovery_codes=codes)
.\processual_api\auth\mfa_router.py:193:@router.post("/verify", response_model=MfaProcessedResponseContract)
.\processual_api\auth\mfa_router.py:194:async def verify_mfa(
.\processual_api\auth\mfa_router.py:195:    body: MfaVerificationRequestContract,
.\processual_api\auth\mfa_router.py:199:    runtime: MfaRuntime = Depends(get_mfa_runtime),
.\processual_api\auth\mfa_router.py:210:    except InvalidMfaCredentialError as exc:
.\processual_api\auth\mfa_router.py:213:    except MfaAuthorityUnavailableError as exc:
.\processual_api\auth\mfa_router.py:217:    return MfaProcessedResponseContract()
```

## Tunisia and checkout-channel patterns

```text
.\CONTRIBUTING.md:57:  billing/               Ã”Ã‡Ã¶ Lemon Squeezy integration
.\CHANGELOG.md:24:- Billing integration with Lemon Squeezy (checkout, portal, webhooks)
.\DEPLOYMENT_EXTERNAL.md:87:| `LEMONSQUEEZY_API_KEY`              | If billing enabled | Lemon Squeezy API key.                                                                |
.\DEPLOYMENT_EXTERNAL.md:88:| `LEMONSQUEEZY_STORE_ID`             | If billing enabled | Lemon Squeezy store ID.                                                               |
.\DEPLOYMENT_EXTERNAL.md:89:| `LEMONSQUEEZY_WEBHOOK_SECRET`       | If billing enabled | Webhook signing secret.                                                               |
.\DEPLOYMENT_EXTERNAL.md:90:| `LEMONSQUEEZY_CHECKOUT_SUCCESS_URL` | If billing enabled | Production checkout success URL.                                                      |
.\DEPLOYMENT_EXTERNAL.md:91:| `LEMONSQUEEZY_CHECKOUT_CANCEL_URL`  | If billing enabled | Production checkout cancel URL.                                                       |
.\README.md:148:LEMONSQUEEZY_API_KEY
.\README.md:149:LEMONSQUEEZY_STORE_ID
.\README.md:150:LEMONSQUEEZY_WEBHOOK_SECRET
.\README.md:178:| `LEMONSQUEEZY_API_KEY`              | If billing enabled | Lemon Squeezy API key.                                                                |
.\README.md:179:| `LEMONSQUEEZY_STORE_ID`             | If billing enabled | Lemon Squeezy store ID.                                                               |
.\README.md:180:| `LEMONSQUEEZY_WEBHOOK_SECRET`       | If billing enabled | Webhook signing secret.                                                               |
.\README.md:181:| `LEMONSQUEEZY_CHECKOUT_SUCCESS_URL` | If billing enabled | Production checkout success URL.                                                      |
.\README.md:182:| `LEMONSQUEEZY_CHECKOUT_CANCEL_URL`  | If billing enabled | Production checkout cancel URL.                                                       |
.\README.md:227:- **Billing Integration** Ã”Ã‡Ã¶ Lemon Squeezy checkout, customer portal, webhook handling
.\README.md:420:- Lemon Squeezy checkout is not considered production-ready until approved plan prices and variant IDs are mapped to the subscription catalog.
.\README.md:432:- Lemon Squeezy variant mapping must not be enabled until offer prices, intervals, and variant IDs are approved.
.\.env.production.example:95:# --- Billing: Lemon Squeezy --------------------------------------------------
.\.env.production.example:96:LEMONSQUEEZY_API_KEY=
.\.env.production.example:97:LEMONSQUEEZY_STORE_ID=
.\.env.production.example:98:LEMONSQUEEZY_WEBHOOK_SECRET=
.\.env.production.example:99:LEMONSQUEEZY_CHECKOUT_SUCCESS_URL=https://your-frontend.example.com/console
.\.env.production.example:100:LEMONSQUEEZY_CHECKOUT_CANCEL_URL=https://your-frontend.example.com/pricing
.\docs\api\index.md:19:| Billing | `/billing` | Lemon Squeezy checkout, portal, webhooks |
.\docs\ADMIN_MARKETPLACE_HANDOFF.md:165:Lemon Squeezy
.\docs\ADMIN_MARKETPLACE_HANDOFF.md:195:Lemon Squeezy API calls
.\docs\ADMIN_MARKETPLACE_HANDOFF.md:437:* â”œÃ¿â”¬Â¬â”œÃ¿â”¬Â«â”œÃ¿â”¬â–“â”œÃ–â”¼Ã¡â”œÃ–Ã”Ã‡Ã¡ â”œÃ¿â”¬Ãºâ”œÃ–Ã”Ã‡Ã­â”œÃ–Ã”Ã‡Ã—â”œÃ–â”¼Ã¡â”œÃ¿â”¬Â® Lemon Squeezy.
.\docs\ADMIN_MARKETPLACE_HANDOFF.md:1172:Lemon Squeezy integration
.\docs\ADMIN_MARKETPLACE_HANDOFF.md:1361:Lemon Squeezy SDK
.\docs\ADMIN_MARKETPLACE_HANDOFF.md:2055:No Lemon Squeezy API
.\docs\ADMIN_MARKETPLACE_HANDOFF.md:2135:Lemon Squeezy
.\docs\ADMIN_MARKETPLACE_HANDOFF.md:2182:## ADMIN-MARKET-R9 â”œÃ³Ã”Ã©Â¼Ã”Ã‡Ã˜ Lemon Squeezy integration
.\docs\ADMIN_MARKETPLACE_HANDOFF.md:2186:â”œÃ¿â”¬Ã‘â”œÃ¿â”¬Ã‚â”œÃ¿â”¬Âºâ”œÃ–â”¬Ã¼â”œÃ¿â”¬Â® â”œÃ¿â”¬Â¬â”œÃ–Ã£Ã†â”œÃ¿â”¬Âºâ”œÃ–Ã”Ã‡Âªâ”œÃ–Ã”Ã‡Ã— Lemon Squeezy â”œÃ¿â”¬Â»â”œÃ–â•¦Ã¥â”œÃ–Ã”Ã‡Ã¡ â”œÃ¿â”¬Â¬â”œÃ¿â”¬Â«â”œÃ¿â”¬â–“â”œÃ–â”¼Ã¡â”œÃ–Ã”Ã‡Ã¡ â”œÃ¿â”¬Ãºâ”œÃ¿â”¬â”‚â”œÃ¿â”¬â–’â”œÃ¿â”¬Âºâ”œÃ¿â”¬â–’ â”œÃ¿â”¬Ãºâ”œÃ–â•¦Ã¥ â”œÃ¿â”¬Â¿â”œÃ–â”¼Ã¡â”œÃ¿â”¬Âºâ”œÃ–Ã”Ã‡Ã¡â”œÃ¿â”¬Âºâ”œÃ¿â”¬Â¬ â”œÃ¿â”¬Â»â”œÃ–â”¬Ã¼â”œÃ¿â”¬â•£ â”œÃ¿â”¬Â«â”œÃ¿â”¬Âºâ”œÃ–Ã”Ã‡Âª â”œÃ–â•¦Ã¥â”œÃ¿â”¬Â»â”œÃ–â•¦Ã¥â”œÃ–Ã”Ã‡Ã¡ â”œÃ¿â”¬Âºâ”œÃ–Ã”Ã‡Ã—â”œÃ¿â”¬â”‚â”œÃ–Ã”Ã‡Âªâ”œÃ¿â”¬Âºâ”œÃ¿â”¬Â¡ â”œÃ–Ã”Ã‡Ã—â”œÃ–Ã”Ã‡Ã—â”œÃ¿â”¬Ãºâ”œÃ¿â”¬Â¡â”œÃ¿â”¬Â»â”œÃ¿â”¬Âºâ”œÃ¿â”¬Â½ â”œÃ¿â”¬Âºâ”œÃ–Ã”Ã‡Ã—â”œÃ¿â”¬Â«â”œÃ¿â”¬Âºâ”œÃ¿â”¬â–’â”œÃ¿â”¬Â¼â”œÃ–â”¼Ã¡â”œÃ¿â”¬Â® â”œÃ¿â”¬Â¿â”œÃ¿â”¬Â¬â”œÃ¿â”¬Â¼â”œÃ¿â”¬Âºâ”œÃ–â•¦Ã¥â”œÃ¿â”¬â–“ â”œÃ–Ã”Ã‡Ãœâ”œÃ–â•¦Ã¥â”œÃ¿â”¬Âºâ”œÃ¿â”¬â•£â”œÃ¿â”¬Â» â”œÃ¿â”¬Âºâ”œÃ–Ã”Ã‡Ã—â”œÃ¿â”¬â”‚â”œÃ–Ã”Ã‡Ã—â”œÃ¿â”¬Ã€â”œÃ¿â”¬Â® â”œÃ–â•¦Ã¥â”œÃ¿â”¬Âºâ”œÃ–Ã”Ã‡Ã—â”œÃ¿â”¬Â¡â”œÃ¿â”¬Âºâ”œÃ–Ã”Ã‡Ã—â”œÃ¿â”¬Â®.
.\docs\ADMIN_MARKETPLACE_HANDOFF.md:2220:Maestro Direct and Lemon Squeezy reconciliation
.\processual_api\billing\__init__.py:1:"""Billing & subscription management Ã”Ã‡Ã¶ Lemon Squeezy integration.
.\processual_api\billing\unit_cost_assumptions.py:53:        "tunisia_local_taxes": {
.\processual_api\billing\subscription_catalog.py:3:This module is intentionally public-safe. It does not expose Lemon Squeezy
.\processual_api\billing\router.py:1:"""Lemon Squeezy billing integration Ã”Ã‡Ã¶ webhooks, checkout, portal, licenses."""
.\processual_api\billing\router.py:30:    return os.environ.get("LEMONSQUEEZY_API_KEY", "")
.\processual_api\billing\router.py:34:    return os.environ.get("LEMONSQUEEZY_STORE_ID", "")
.\processual_api\billing\router.py:38:    return os.environ.get("LEMONSQUEEZY_WEBHOOK_SECRET", "")
.\processual_api\billing\router.py:42:    return os.environ.get("LEMONSQUEEZY_CHECKOUT_SUCCESS_URL", "https://yourdomain.com/console")
.\processual_api\billing\router.py:46:    return os.environ.get("LEMONSQUEEZY_CHECKOUT_CANCEL_URL", "https://yourdomain.com/pricing")
.\processual_api\billing\router.py:99:    """Create a Lemon Squeezy checkout session and return the URL."""
.\processual_api\billing\router.py:105:            detail="Lemon Squeezy not configured. Set LEMONSQUEEZY_API_KEY and STORE_ID.",
.\processual_api\billing\router.py:139:                "https://api.lemonsqueezy.com/v1/checkouts",
.\processual_api\billing\router.py:150:                    "error": f"Lemon Squeezy error: HTTP {res.status_code}",
.\processual_api\billing\router.py:179:    """Return the Lemon Squeezy Customer Portal URL for subscription management."""
.\processual_api\billing\router.py:182:        raise HTTPException(status_code=501, detail="Lemon Squeezy not configured")
.\processual_api\billing\router.py:199:                f"https://api.lemonsqueezy.com/v1/customers/{customer_id}",
.\processual_api\billing\router.py:206:                "portal_url": f"https://app.lemonsqueezy.com/customers/{customer_id}",
.\processual_api\billing\router.py:215:    """Handle Lemon Squeezy webhook events (order_created, subscription_*, license_key_*)."""
.\processual_api\billing\router.py:323:            "billing_provider": "lemonsqueezy",
.\processual_api\billing\router.py:333:        "billing_provider": "lemonsqueezy",
.\docs\commercial\GROUP2_COMMERCIAL_UI_FOUNDATION_INVENTORY.md:7:checkout, local Tunisia payment choice, and Admin Marketplace.
.\docs\commercial\GROUP2_COMMERCIAL_UI_FOUNDATION_INVENTORY.md:17:- Keep Tunisia local checkout optional and visible only to eligible Tunisian addresses at the start of the payment journey.
.\docs\commercial\GROUP2_COMMERCIAL_UI_FOUNDATION_INVENTORY.md:18:- Keep Lemon Squeezy available as the general route.
.\docs\commercial\GROUP2_COMMERCIAL_UI_FOUNDATION_INVENTORY.md:674:.\tests\test_admin_api_key_profiles_regression.py:146:        "LEMONSQUEEZY_SUCCESS_URL",
.\docs\commercial\GROUP2_COMMERCIAL_UI_FOUNDATION_INVENTORY.md:775:.\processual_api\billing\router.py:42:    return os.environ.get("LEMONSQUEEZY_CHECKOUT_SUCCESS_URL", "https://yourdomain.com/console")
.\docs\commercial\GROUP2_COMMERCIAL_UI_FOUNDATION_INVENTORY.md:1233:.\docs\commercial\GROUP2_COMMERCIAL_UI_FOUNDATION_INVENTORY.md:7:checkout, local Tunisia payment choice, and Admin Marketplace.
.\tests\test_admin_api_key_profiles_regression.py:19:    assert "It should not implement Lemon Squeezy API calls." in text
.\tests\test_admin_api_key_profiles_regression.py:136:def test_api_key_profiles_report_declares_lemonsqueezy_readiness():
.\tests\test_admin_api_key_profiles_regression.py:140:        "LEMONSQUEEZY_API_KEY",
.\tests\test_admin_api_key_profiles_regression.py:141:        "LEMONSQUEEZY_STORE_ID",
.\tests\test_admin_api_key_profiles_regression.py:142:        "LEMONSQUEEZY_WEBHOOK_SECRET",
.\tests\test_admin_api_key_profiles_regression.py:143:        "LEMONSQUEEZY_STARTER_VARIANT_ID",
.\tests\test_admin_api_key_profiles_regression.py:144:        "LEMONSQUEEZY_PRO_VARIANT_ID",
.\tests\test_admin_api_key_profiles_regression.py:145:        "LEMONSQUEEZY_BUSINESS_VARIANT_ID",
.\tests\test_admin_api_key_profiles_regression.py:146:        "LEMONSQUEEZY_SUCCESS_URL",
.\tests\test_admin_api_key_profiles_regression.py:147:        "LEMONSQUEEZY_CANCEL_URL",
.\tests\test_admin_api_key_profiles_regression.py:153:    assert "No real Lemon Squeezy secret may be committed to Git." in text
.\tests\test_admin_api_key_lifecycle_regression.py:32:def test_admin_api_key_ui_supports_tunisia_introductory_distribution_positioning():
.\tests\test_admin_api_key_external_usage_regression.py:48:        label="Tunisia pilot external access",
.\tests\test_admin_api_key_external_usage_regression.py:50:        issued_to="external-tunisia-pilot",
.\tests\test_admin_api_key_external_usage_regression.py:76:    assert created["issued_to"] == "external-tunisia-pilot"
.\tests\test_admin_api_key_external_usage_regression.py:107:    assert key["issued_to"] == "external-tunisia-pilot"
.\tests\test_admin_marketplace_channel_policy_r1.py:12:def test_tunisian_customer_may_choose_direct_or_lemon_squeezy() -> None:
.\tests\test_unit_cost_assumptions_route.py:41:    assert "tunisia_local_taxes" in components
.\tests\test_unit_cost_assumptions_route.py:47:    assert components["tunisia_local_taxes"]["accountant_review_required"] is True
.\tests\test_unit_cost_assumptions.py:15:def test_unit_cost_assumptions_include_infra_lemon_and_tunisia_tax_review():
.\tests\test_unit_cost_assumptions.py:23:    assert components["tunisia_local_taxes"]["accountant_review_required"] is True
.\tests\test_subscription_pricing_catalog.py:18:    "lemonsqueezy_api_key",
.\tests\test_subscription_pricing_catalog.py:19:    "lemonsqueezy_webhook_secret",
.\tests\test_billing_pricing_catalog_route.py:8:    "lemonsqueezy_api_key",
.\tests\test_billing_pricing_catalog_route.py:9:    "lemonsqueezy_webhook_secret",
.\tests\test_billing_pricing_catalog_route.py:17:    monkeypatch.delenv("LEMONSQUEEZY_API_KEY", raising=False)
.\tests\test_billing_pricing_catalog_route.py:18:    monkeypatch.delenv("LEMONSQUEEZY_STORE_ID", raising=False)
.\tests\test_billing_pricing_catalog_route.py:19:    monkeypatch.delenv("LEMONSQUEEZY_WEBHOOK_SECRET", raising=False)
.\tests\test_checkout_disabled_contract_09d_document.py:31:        "lemon squeezy wiring approved: `false`",
.\tests\test_checkout_disabled_contract_09d_document.py:155:        "lemon squeezy configuration",
.\tests\test_billing_subscription_regression.py:29:        "lemonsqueezy",
.\tests\test_billing_subscription_regression.py:85:    assert response["billing_provider"] == "lemonsqueezy"
.\tests\test_commercial_terms_review_09c_document.py:25:        "lemon squeezy wiring approved: `false`",
.\tests\test_commercial_terms_review_09c_document.py:30:        "lemon squeezy variant ids remain forbidden",
.\tests\test_commercial_terms_review_09c_document.py:128:        "lemon squeezy configuration",
.\tests\test_production_env_template_regression.py:94:        "LEMONSQUEEZY_API_KEY",
.\tests\test_production_env_template_regression.py:95:        "LEMONSQUEEZY_STORE_ID",
.\tests\test_production_env_template_regression.py:96:        "LEMONSQUEEZY_WEBHOOK_SECRET",
.\tests\test_production_env_template_regression.py:97:        "LEMONSQUEEZY_CHECKOUT_SUCCESS_URL",
.\tests\test_production_env_template_regression.py:98:        "LEMONSQUEEZY_CHECKOUT_CANCEL_URL",
.\tests\test_deployment_docs_alignment.py:30:        "LEMONSQUEEZY_API_KEY",
.\tests\test_deployment_docs_alignment.py:63:        "LEMONSQUEEZY_WEBHOOK_SECRET",
.\tests\test_deployment_docs_alignment.py:95:        "LEMONSQUEEZY_WEBHOOK_SECRET",
.\tests\test_pricing_subscriptions_surface_ui.py:38:    assert "lemonsqueezy" not in text
.\tests\test_pricing_subscriptions_surface_ui.py:49:    assert "lemonsqueezy_api_key" not in text
.\tests\test_pricing_review_09a_document.py:20:    assert "Lemon Squeezy wiring approved: `false`" in source
.\tests\test_pricing_review_09a_document.py:94:        "must not be used as lemon squeezy variants",
.\tests\test_pricing_offers_surface_ui.py:46:    assert "lemonsqueezy" not in text
.\tests\test_offer_pricebook_route.py:8:    "lemonsqueezy_api_key",
.\tests\test_offer_pricebook_route.py:9:    "lemonsqueezy_webhook_secret",
.\tests\test_offer_pricebook.py:15:    "lemonsqueezy_api_key",
.\tests\test_offer_pricebook.py:16:    "lemonsqueezy_webhook_secret",
.\tests\test_login_gateway_actions_ui.py:29:    assert "lemonsqueezy" not in text
.\docs\MASTER_REMAINING_EXECUTION_ROADMAP.md:20:3. Implement direct sales inside Tunisia independently from Lemon Squeezy.
.\docs\MASTER_REMAINING_EXECUTION_ROADMAP.md:21:4. Block Lemon Squeezy checkout for customers governed as Tunisian customers.
.\docs\MASTER_REMAINING_EXECUTION_ROADMAP.md:203:## ADMIN-MARKET-R3 Ã”Ã‡Ã¶ Tunisia sales-channel governance and customer choice
.\docs\MASTER_REMAINING_EXECUTION_ROADMAP.md:210:- Maestro direct sales must be available for supported Tunisian sales.
.\docs\MASTER_REMAINING_EXECUTION_ROADMAP.md:211:- Eligible Tunisian customers and institutions may also choose Lemon Squeezy
.\docs\MASTER_REMAINING_EXECUTION_ROADMAP.md:213:- Tunisian residency, organization country or billing country must not
.\docs\MASTER_REMAINING_EXECUTION_ROADMAP.md:214:  automatically prohibit Lemon Squeezy checkout.
.\docs\MASTER_REMAINING_EXECUTION_ROADMAP.md:233:Country=TN
.\docs\MASTER_REMAINING_EXECUTION_ROADMAP.md:235:LemonSqueezyCheckoutAllowed=True
.\docs\MASTER_REMAINING_EXECUTION_ROADMAP.md:239:Country=TN
.\docs\MASTER_REMAINING_EXECUTION_ROADMAP.md:241:LemonSqueezyCheckoutAllowed=False
.\docs\MASTER_REMAINING_EXECUTION_ROADMAP.md:246:EligibleCountryOutsideTunisia=True
.\docs\MASTER_REMAINING_EXECUTION_ROADMAP.md:248:LemonSqueezyCheckoutAllowed=True
.\docs\MASTER_REMAINING_EXECUTION_ROADMAP.md:255:- Support Tunisian dinar and approved international currencies.
.\docs\MASTER_REMAINING_EXECUTION_ROADMAP.md:261:## ADMIN-MARKET-R5 Ã”Ã‡Ã¶ Direct Tunisian order workflow
.\docs\MASTER_REMAINING_EXECUTION_ROADMAP.md:274:another later-approved Tunisian payment integration. No method is considered
.\docs\MASTER_REMAINING_EXECUTION_ROADMAP.md:300:## ADMIN-MARKET-R8 Ã”Ã‡Ã¶ Lemon Squeezy boundary
.\docs\MASTER_REMAINING_EXECUTION_ROADMAP.md:327:- Maestro Direct and Lemon Squeezy eligibility, selection and restriction
.\docs\MASTER_REMAINING_EXECUTION_ROADMAP.md:467:- Tunisia/direct price display.
.\docs\MASTER_REMAINING_EXECUTION_ROADMAP.md:468:- International Lemon Squeezy mapping.
.\docs\pricing\CHECKOUT_DISABLED_CONTRACT_09D.md:9:Lemon Squeezy wiring approved: `false`.
.\docs\pricing\CHECKOUT_DISABLED_CONTRACT_09D.md:33:- Lemon Squeezy wiring remains unapproved;
.\docs\pricing\CHECKOUT_DISABLED_CONTRACT_09D.md:167:- Lemon Squeezy configuration;
.\docs\pricing\COMMERCIAL_TERMS_REVIEW_09C.md:7:Lemon Squeezy wiring approved: `false`.
.\docs\pricing\COMMERCIAL_TERMS_REVIEW_09C.md:11:public pricing, checkout, Lemon Squeezy variants, tax treatment, Merchant of Record
.\docs\pricing\COMMERCIAL_TERMS_REVIEW_09C.md:24:- Lemon Squeezy variant IDs remain forbidden.
.\docs\pricing\COMMERCIAL_TERMS_REVIEW_09C.md:126:Lemon Squeezy or any other Merchant of Record must not be wired until this checklist
.\docs\pricing\COMMERCIAL_TERMS_REVIEW_09C.md:210:- Lemon Squeezy configuration;
.\docs\verification\ADMIN-MARKET-R1-domain-authority-contracts.md:20:Tunisian customers and institutions may be eligible for both Maestro Direct and
.\docs\verification\ADMIN-MARKET-R1-domain-authority-contracts.md:21:Lemon Squeezy. Tunisia alone is not a denial condition. Ineligibility requires a
.\docs\verification\ADMIN-MARKET-R1-domain-authority-contracts.md:34:TunisiaCustomerChannelChoicePreserved=True
.\docs\pricing\PRICING_REVIEW_09A_DRAFT.md:6:Lemon Squeezy wiring approved: `false`
.\docs\pricing\PRICING_REVIEW_09A_DRAFT.md:77:- Tunisia tax/accounting handling.
.\docs\pricing\PRICING_REVIEW_09A_DRAFT.md:117:public prices, currency, checkout, Lemon Squeezy wiring, tax treatment, or final
.\docs\pricing\PRICING_REVIEW_09A_DRAFT.md:122:Lemon Squeezy variants or public price-book amounts.
.\docs\pricing\PRICING_REVIEW_09A_DRAFT.md:133:- Lemon Squeezy variant IDs remain forbidden until approval.
.\docs\pricing\PRICING_REVIEW_09A_DRAFT.md:252:- Lemon Squeezy variant configuration;
.\docs\reports\API_KEYS_ADAPTERS_REGRESSION_REPORT.md:1018:TEST-13B adds focused regression coverage for billing and subscription behavior without relying on Lemon Squeezy network calls, real databases, Redis, or production secrets.
.\processual_api\static\js\admin_api_keys.js:87:    ['billing_service', 'Billing Service - Lemon Squeezy or billing sync'],
.\processual_api\static\js\admin_api_keys.js:749:        Tunisia introductory access positioning: use API keys as introductory access,
.\docs\reports\API_KEY_PROFILES_ADMIN_PROVISIONING.md:134:## Billing and Lemon Squeezy Readiness
.\docs\reports\API_KEY_PROFILES_ADMIN_PROVISIONING.md:136:Lemon Squeezy integration should become the billing authority for:
.\docs\reports\API_KEY_PROFILES_ADMIN_PROVISIONING.md:149:| `LEMONSQUEEZY_API_KEY` | Server-side Lemon Squeezy API token. |
.\docs\reports\API_KEY_PROFILES_ADMIN_PROVISIONING.md:150:| `LEMONSQUEEZY_STORE_ID` | Store identifier. |
.\docs\reports\API_KEY_PROFILES_ADMIN_PROVISIONING.md:151:| `LEMONSQUEEZY_WEBHOOK_SECRET` | Webhook signing secret. |
.\docs\reports\API_KEY_PROFILES_ADMIN_PROVISIONING.md:152:| `LEMONSQUEEZY_STARTER_VARIANT_ID` | Starter plan variant. |
.\docs\reports\API_KEY_PROFILES_ADMIN_PROVISIONING.md:153:| `LEMONSQUEEZY_PRO_VARIANT_ID` | Pro plan variant. |
.\docs\reports\API_KEY_PROFILES_ADMIN_PROVISIONING.md:154:| `LEMONSQUEEZY_BUSINESS_VARIANT_ID` | Business plan variant. |
.\docs\reports\API_KEY_PROFILES_ADMIN_PROVISIONING.md:155:| `LEMONSQUEEZY_SUCCESS_URL` | Checkout success redirect. |
.\docs\reports\API_KEY_PROFILES_ADMIN_PROVISIONING.md:156:| `LEMONSQUEEZY_CANCEL_URL` | Checkout cancellation redirect. |
.\docs\reports\API_KEY_PROFILES_ADMIN_PROVISIONING.md:158:No real Lemon Squeezy secret may be committed to Git.
.\docs\reports\API_KEY_PROFILES_ADMIN_PROVISIONING.md:246:It should not implement Lemon Squeezy API calls.
.\docs\reports\API_KEY_PROFILES_ADMIN_PROVISIONING.md:258:| BILLING-LEMON-01 | Add Lemon Squeezy configuration readiness. |
.\docs\reports\API_KEY_PROFILES_ADMIN_PROVISIONING.md:260:| BILLING-LEMON-03 | Add Lemon Squeezy webhook verification and subscription sync. |
.\docs\reports\PRODUCTION_SECURITY_READINESS.md:81:LEMONSQUEEZY_API_KEY
.\docs\reports\PRODUCTION_SECURITY_READINESS.md:82:LEMONSQUEEZY_STORE_ID
.\docs\reports\PRODUCTION_SECURITY_READINESS.md:83:LEMONSQUEEZY_WEBHOOK_SECRET
.\docs\reports\PRODUCTION_SECURITY_READINESS.md:372:If Lemon Squeezy billing is enabled, configure:
.\docs\reports\PRODUCTION_SECURITY_READINESS.md:375:LEMONSQUEEZY_API_KEY
.\docs\reports\PRODUCTION_SECURITY_READINESS.md:376:LEMONSQUEEZY_STORE_ID
.\docs\reports\PRODUCTION_SECURITY_READINESS.md:377:LEMONSQUEEZY_WEBHOOK_SECRET
.\docs\reports\PRODUCTION_SECURITY_READINESS.md:384:LEMONSQUEEZY_CHECKOUT_SUCCESS_URL
.\docs\reports\PRODUCTION_SECURITY_READINESS.md:385:LEMONSQUEEZY_CHECKOUT_CANCEL_URL
.\docs\reports\PRODUCTION_SECURITY_READINESS.md:596:- Lemon Squeezy billing keys.
.\docs\integrations\INTEGRATION_AUDIT_11A_R1.md:115:- Lemon Squeezy historical billing integration references.
```

## Selected pricing and enterprise policy

```text
docs\pricing\PRICING_REVIEW_09A_DRAFT.md:3:Status: `draft_review`
docs\pricing\PRICING_REVIEW_09A_DRAFT.md:114:Status: `draft_review`.
docs\pricing\MAESTRO_GROUP1_SELECTED_PRICING_PROPOSAL.md:6:Proposal status: draft_review
docs\pricing\MAESTRO_GROUP1_PRICING_REVIEW.md:19:Pricing status: draft_review
docs\pricing\MAESTRO_GROUP1_PRICING_REVIEW.md:123:- Prices remain `draft_review`.
docs\pricing\MAESTRO_ENTERPRISE_USAGE_REFERENCE.md:7:Pricing status: draft_review
docs\pricing\COMMERCIAL_TERMS_REVIEW_09C.md:3:Status: `draft_review`.
docs\pricing\CHECKOUT_DISABLED_CONTRACT_09D.md:3:Status: `draft_review`.
docs\integrations\TELECOM_CONNECTIVITY_16A.md:3:Status: `draft_review`.
docs\integrations\TELECOM_CONNECTIVITY_16A.md:151:- `enterprise_helpdesk_reference` uses the `enterprise_helpdesk` adapter contract and `enterprise_core_api_reference` credential profile.
docs\integrations\OPERATOR_READINESS_PACKAGE_12C.md:3:Status: draft_review
docs\integrations\OPERATOR_PILOT_HANDOFF_14A.md:3:Status: `draft_review`
docs\integrations\INTEGRATION_SCOPES_11B.md:3:Status: `draft_review`.
docs\integrations\INTEGRATION_READINESS_11E.md:5:`draft_review`
docs\integrations\INTEGRATION_ONBOARDING_13B.md:3:Status: `draft_review`
docs\integrations\INTEGRATION_ONBOARDING_13A.md:3:Status: `draft_review`
docs\integrations\INTEGRATION_KEY_PROFILES_11G.md:3:Status: `draft_review`
docs\integrations\INTEGRATION_KEY_PROFILES_11G.md:26:- enterprise_core_status_read
docs\integrations\INTEGRATION_KEY_PROFILES_11J.md:3:Status: draft_review
docs\integrations\INTEGRATION_CREDENTIALS_11D.md:5:`draft_review`
docs\integrations\INTEGRATION_KEY_PROFILES_11I.md:3:Status: draft_review
docs\integrations\INTEGRATION_ADAPTERS_11C.md:3:Status: `draft_review`.
docs\integrations\INTEGRATION_KEY_PROFILES_11H.md:3:Status: draft_review
docs\integrations\INTEGRATION_ADAPTERS_11A.md:3:Status: `draft_review`.
tests\test_admin_integration_readiness_case_management_12a.py:14:    case_id = "client_visible_12a:request_visible_12a:crm:enterprise_core_api_reference:visible"
tests\test_admin_integration_readiness_case_management_12a.py:25:                        "item_key": "enterprise_core_api_reference",
tests\test_admin_integration_readiness_case_management_12a.py:136:    assert detail_payload["input_statuses"][0]["item_key"] == "enterprise_core_api_reference"
tests\test_admin_integration_readiness_case_management_12a.py:143:            "item_key": "enterprise_core_api_reference",
tests\test_admin_integration_readiness_case_management_12a.py:187:            "item_key": "enterprise_core_api_reference",
tests\test_admin_integration_readiness_case_management_12a.py:238:            "item_key": "enterprise_core_api_reference",
tests\test_admin_marketplace_contracts_r1.py:76:        metadata={"source": "draft_review"},
tests\test_admin_integration_readiness_tracking_route_11p.py:22:        "credential_profile_id": "enterprise_core_api_reference",
tests\test_admin_integration_readiness_tracking_route_11p.py:23:        "readiness_check_id": "crm:enterprise_core_api_reference:readiness",
tests\test_admin_integration_readiness_supervisor_scope_audit_12b.py:14:    case_id = "client_visible_12b:request_visible_12b:crm:enterprise_core_api_reference:visible"
tests\test_admin_integration_readiness_supervisor_scope_audit_12b.py:25:                        "item_key": "enterprise_core_api_reference",
tests\test_admin_integration_readiness_supervisor_scope_audit_12b.py:142:            "item_key": "enterprise_core_api_reference",
tests\test_admin_integration_readiness_supervisor_scope_audit_12b.py:185:            "item_key": "enterprise_core_api_reference",
tests\test_admin_integration_readiness_supervisor_scope_audit_12b.py:232:            "item_key": "enterprise_core_api_reference",
tests\test_admin_integration_readiness_supervisor_scope_audit_12b.py:249:    assert event["item_key"] == "enterprise_core_api_reference"
processual_api\static\js\admin_operator_pilot_handoff_17c.js:69:    draft_review: "Draft review",
processual_api\static\js\admin_operator_pilot_handoff.js:6:    package_status: "draft_review",
processual_api\services\operator_readiness_package.py:7:PACKAGE_STATUS_12C = "draft_review"
processual_api\services\operator_readiness_package.py:101:            "status": "draft_review",
processual_api\services\operator_pilot_handoff_actions.py:12:ACTION_PLAN_STATUS: Final[str] = "draft_review"
processual_api\services\operator_pilot_handoff.py:6:PACKAGE_STATUS = "draft_review"
processual_api\services\integration_readiness_tracking_store.py:279:        "item_key": "enterprise_core_api_reference",
processual_api\billing\offer_pricebook.py:22:OFFER_PRICEBOOK_STATUS = "draft_review"
processual_api\billing\maestro_shadow_measurements.py:22:APPROVED_FOR_CHECKOUT = False
processual_api\billing\maestro_group1_selected_pricing.py:21:    APPROVED_FOR_CHECKOUT,
processual_api\billing\maestro_group1_selected_pricing.py:38:SELECTED_PROPOSAL_STATUS: Final = "draft_review"
processual_api\billing\maestro_group1_selected_pricing.py:46:SELECTED_MONTHLY_PRICES: Final[dict[str, Decimal]] = {
processual_api\billing\maestro_group1_selected_pricing.py:51:    "enterprise_pilot": Decimal("2790"),
processual_api\billing\maestro_group1_selected_pricing.py:52:    "enterprise_core": Decimal("7890"),
processual_api\billing\maestro_group1_selected_pricing.py:53:    "enterprise_scale": Decimal("14990"),
processual_api\billing\maestro_group1_selected_pricing.py:54:    "enterprise_strategic": Decimal("23900"),
processual_api\billing\maestro_group1_selected_pricing.py:58:    "enterprise_pilot": Decimal("0"),
processual_api\billing\maestro_group1_selected_pricing.py:59:    "enterprise_core": Decimal("6"),
processual_api\billing\maestro_group1_selected_pricing.py:60:    "enterprise_scale": Decimal("10"),
processual_api\billing\maestro_group1_selected_pricing.py:61:    "enterprise_strategic": Decimal("14"),
processual_api\billing\maestro_group1_selected_pricing.py:69:    "enterprise_pilot": Decimal("6.50"),
processual_api\billing\maestro_group1_selected_pricing.py:70:    "enterprise_core": Decimal("6.20"),
processual_api\billing\maestro_group1_selected_pricing.py:71:    "enterprise_scale": Decimal("5.95"),
processual_api\billing\maestro_group1_selected_pricing.py:72:    "enterprise_strategic": Decimal("5.75"),
processual_api\billing\maestro_group1_selected_pricing.py:116:        if self.pricing_status != "draft_review":
processual_api\billing\maestro_group1_selected_pricing.py:117:            raise PricingReviewValidationError("selected proposal must remain draft_review")
processual_api\billing\maestro_group1_selected_pricing.py:137:    if plan_id not in SELECTED_MONTHLY_PRICES:
processual_api\billing\maestro_group1_selected_pricing.py:150:    selected_monthly_price = SELECTED_MONTHLY_PRICES[plan_id]
processual_api\billing\maestro_group1_selected_pricing.py:170:    proposals = [calculate_selected_plan_proposal(plan_id).to_dict() for plan_id in SELECTED_MONTHLY_PRICES]
processual_api\billing\maestro_group1_selected_pricing.py:181:        "approved_for_checkout": APPROVED_FOR_CHECKOUT,
processual_api\billing\maestro_group1_pricing_review.py:29:PRICING_STATUS: Final = "draft_review"
processual_api\billing\maestro_group1_pricing_review.py:39:APPROVED_FOR_CHECKOUT: Final = False
processual_api\billing\maestro_group1_pricing_review.py:233:            raise PricingReviewValidationError("price_status must remain draft_review")
processual_api\billing\maestro_group1_pricing_review.py:343:    "enterprise_pilot": (
processual_api\billing\maestro_group1_pricing_review.py:347:    "enterprise_core": (
processual_api\billing\maestro_group1_pricing_review.py:351:    "enterprise_scale": (
processual_api\billing\maestro_group1_pricing_review.py:355:    "enterprise_strategic": (
processual_api\billing\maestro_group1_pricing_review.py:470:        "approved_for_checkout": APPROVED_FOR_CHECKOUT,
processual_api\billing\maestro_execution_family_evidence.py:29:APPROVED_FOR_CHECKOUT = False
processual_api\integrations\credential_profiles.py:23:    "draft_review",
processual_api\integrations\credential_profiles.py:172:        credential_profile_id="enterprise_core_api_reference",
processual_api\integrations\connector_registry.py:337:            "enterprise_core_api_reference",
processual_api\billing\maestro_execution_authority.py:20:APPROVED_FOR_CHECKOUT = False
processual_api\integrations\api_key_operational_profiles.py:178:        "profile_id": "enterprise_core_status_read",
processual_api\billing\maestro_commercial_execution_identity.py:21:APPROVED_FOR_CHECKOUT = False
processual_api\billing\maestro_calibration_contracts.py:12:APPROVED_FOR_CHECKOUT = False
processual_api\billing\maestro_agent_identity_carrier.py:30:APPROVED_FOR_CHECKOUT = False
processual_api\billing\maestro_agent_identity_bridge.py:29:APPROVED_FOR_CHECKOUT = False
tests\test_checkout_disabled_contract_09d_document.py:25:        "status: `draft_review`",
tests\test_commercial_terms_review_09c_document.py:21:        "status: `draft_review`",
tests\test_integration_api_key_operational_profiles_11g.py:23:        "enterprise_core_status_read",
tests\test_integration_adapter_contracts.py:159:        "status: `draft_review`",
tests\test_integration_credential_profiles.py:42:        "enterprise_core_api_reference",
tests\test_integration_credential_profiles.py:66:            "draft_review",
tests\test_integration_sector_profiles.py:152:        "status: `draft_review`",
tests\test_maestro_agent_identity_bridge_boundaries_m1_r4.py:50:    "APPROVED_FOR_CHECKOUT",
tests\test_integration_scope_catalog.py:169:        "status: `draft_review`",
tests\test_maestro_agent_identity_carrier_boundaries_m1_r3.py:50:    "APPROVED_FOR_CHECKOUT",
tests\test_maestro_agent_identity_bridge_m1_r4.py:8:    APPROVED_FOR_CHECKOUT,
tests\test_maestro_agent_identity_bridge_m1_r4.py:75:    assert APPROVED_FOR_CHECKOUT is False
tests\test_maestro_calibration_contracts_r1.py:7:    APPROVED_FOR_CHECKOUT,
tests\test_maestro_calibration_contracts_r1.py:43:    assert APPROVED_FOR_CHECKOUT is False
tests\test_integration_readiness_validated_write_guard_15b_r2.py:68:        "credential_profile_id": "enterprise_core_api_reference",
tests\test_integration_readiness_validated_write_guard_15b_r2.py:69:        "readiness_check_id": "crm:enterprise_core_api_reference:readiness",
tests\test_maestro_commercial_execution_identity_boundaries_m1_r2.py:44:    "APPROVED_FOR_CHECKOUT",
tests\test_maestro_agent_identity_carrier_m1_r3.py:8:    APPROVED_FOR_CHECKOUT,
tests\test_maestro_agent_identity_carrier_m1_r3.py:73:    assert APPROVED_FOR_CHECKOUT is False
tests\test_maestro_commercial_execution_identity_m1_r2.py:7:    APPROVED_FOR_CHECKOUT,
tests\test_maestro_commercial_execution_identity_m1_r2.py:62:    assert APPROVED_FOR_CHECKOUT is False
tests\test_integration_readiness_tracking_11n.py:20:        "readiness_check_id": "crm:enterprise_core_api_reference:readiness",
tests\test_integration_readiness_tracking_11n.py:22:        "credential_profile_id": "enterprise_core_api_reference",
tests\test_integration_readiness_tracking_11n.py:40:        "client_acme:request_123:crm:enterprise_core_api_reference:readiness"
tests\test_maestro_execution_authority_r2b.py:7:    APPROVED_FOR_CHECKOUT,
tests\test_maestro_execution_authority_r2b.py:38:    assert APPROVED_FOR_CHECKOUT is False
tests\test_integration_readiness_legacy_validated_write_guard_15b_r2b.py:69:        "credential_profile_id": "enterprise_core_api_reference",
tests\test_integration_readiness_legacy_validated_write_guard_15b_r2b.py:71:            "crm:enterprise_core_api_reference:readiness"
tests\test_maestro_execution_family_evidence_boundaries_m1.py:45:    "APPROVED_FOR_CHECKOUT",
tests\test_maestro_group1_pricing_review.py:10:    APPROVED_FOR_CHECKOUT,
tests\test_maestro_group1_pricing_review.py:41:    assert APPROVED_FOR_CHECKOUT is False
tests\test_maestro_group1_pricing_review.py:116:    assert review.price_status == "draft_review"
tests\test_maestro_group1_pricing_review.py:122:    assert payload["pricing_status"] == "draft_review"
tests\test_maestro_group1_pricing_review.py:171:    assert PLAN_REVIEW_CONFIG["enterprise_pilot"][0] == 500_000
tests\test_maestro_group1_pricing_review.py:172:    assert PLAN_REVIEW_CONFIG["enterprise_core"][0] == 1_500_000
tests\test_maestro_group1_pricing_review.py:173:    assert PLAN_REVIEW_CONFIG["enterprise_scale"][0] == 3_000_000
tests\test_maestro_group1_pricing_review.py:174:    assert PLAN_REVIEW_CONFIG["enterprise_strategic"][0] == 5_000_000
tests\test_maestro_group1_pricing_review.py:180:        "enterprise_pilot",
tests\test_maestro_group1_pricing_review.py:181:        "enterprise_core",
tests\test_maestro_group1_pricing_review.py:182:        "enterprise_scale",
tests\test_maestro_group1_pricing_review.py:183:        "enterprise_strategic",
tests\test_maestro_group1_selected_pricing.py:10:    SELECTED_MONTHLY_PRICES,
tests\test_maestro_group1_selected_pricing.py:18:    assert SELECTED_MONTHLY_PRICES == {
tests\test_maestro_group1_selected_pricing.py:23:        "enterprise_pilot": Decimal("2790"),
tests\test_maestro_group1_selected_pricing.py:24:        "enterprise_core": Decimal("7890"),
tests\test_maestro_group1_selected_pricing.py:25:        "enterprise_scale": Decimal("14990"),
tests\test_maestro_group1_selected_pricing.py:26:        "enterprise_strategic": Decimal("23900"),
tests\test_maestro_group1_selected_pricing.py:32:        "enterprise_pilot": Decimal("0"),
tests\test_maestro_group1_selected_pricing.py:33:        "enterprise_core": Decimal("6"),
tests\test_maestro_group1_selected_pricing.py:34:        "enterprise_scale": Decimal("10"),
tests\test_maestro_group1_selected_pricing.py:35:        "enterprise_strategic": Decimal("14"),
tests\test_maestro_group1_selected_pricing.py:41:    for plan_id in SELECTED_MONTHLY_PRICES:
tests\test_maestro_group1_selected_pricing.py:48:        "enterprise_pilot",
tests\test_maestro_group1_selected_pricing.py:49:        "enterprise_core",
tests\test_maestro_group1_selected_pricing.py:50:        "enterprise_scale",
tests\test_maestro_group1_selected_pricing.py:51:        "enterprise_strategic",
tests\test_maestro_group1_selected_pricing.py:61:    assert set(SELECTED_OVERAGE_PRICES_PER_1000_UNITS) == set(SELECTED_MONTHLY_PRICES)
tests\test_maestro_group1_selected_pricing.py:67:    assert payload["proposal_status"] == "draft_review"
tests\test_maestro_group1_pricing_review_boundaries.py:83:        "APPROVED_FOR_CHECKOUT: Final = False",
tests\test_maestro_shadow_measurements_r2.py:15:    APPROVED_FOR_CHECKOUT,
tests\test_maestro_shadow_measurements_r2.py:50:    assert APPROVED_FOR_CHECKOUT is False
tests\test_offer_pricebook.py:37:    assert payload["pricebook_status"] == OFFER_PRICEBOOK_STATUS == "draft_review"
tests\test_operator_pilot_handoff_actions_14d.py:23:    assert package["action_plan_status"] == "draft_review"
tests\test_offer_pricebook_route.py:23:    assert payload["pricebook_status"] == "draft_review"
tests\test_operator_readiness_package_12c.py:61:    assert payload["package_status"] == "draft_review"
tests\test_operator_readiness_package_12c.py:121:    assert "draft_review" in text
tests\test_pricing_review_09a_document.py:17:    assert "Status: `draft_review`" in source
tests\test_pricing_review_09a_document.py:90:        "status: `draft_review`",
tests\test_telecom_connector_runtime_contracts_16a.py:53:        "status: `draft_review`",
tests\test_telecom_connector_runtime_contracts_16a.py:454:            "enterprise_core_api_reference",
```

## Testing and build toolchain

```text
cgtlib\pyproject.toml
pyproject.toml
```
