import asyncio
import copy

from processual_api.routers import settings as settings_router


def _api_key_record(**overrides) -> dict:
    record = {
        "id": "key_1",
        "status": "enabled",
        "revoked_at": None,
        "plan_id": "starter",
        "quota_policy": {
            "id": "starter",
            "name": "Starter",
            "source": "plan_store",
            "quotas": {"evaluation": 100},
        },
        "quota_scope": "evaluation",
        "quota_limit": 100,
        "quota_used": 35,
        "quota_reset_at": None,
        "quota_rejected_count": 2,
    }
    record.update(overrides)
    return record


def _patch_memory_store(monkeypatch, initial_raw: dict):
    saved = {}
    raw = copy.deepcopy(initial_raw)

    def fake_load_raw(user_id: str):
        saved["loaded_user_id"] = user_id
        return copy.deepcopy(raw)

    def fake_save_raw(user_id: str, data: dict):
        saved["saved_user_id"] = user_id
        saved["raw"] = copy.deepcopy(data)

    monkeypatch.setattr(settings_router, "_load_raw", fake_load_raw)
    monkeypatch.setattr(settings_router, "_save_raw", fake_save_raw)

    return saved


def _patch_plan_helpers(monkeypatch):
    plan_limits = {
        "starter": 100,
        "pro": 500,
        "enterprise": 5000,
    }

    def fake_resolve_plan_id(value):
        return str(value or "starter").lower()

    def fake_get_plan_policy(plan_id):
        limit = plan_limits[plan_id]
        return {
            "id": plan_id,
            "name": plan_id.title(),
            "source": "plan_store",
            "quotas": {"evaluation": limit},
        }

    def fake_quota_limit_for_plan(plan_id, quota_scope):
        assert quota_scope == "evaluation"
        return plan_limits[plan_id]

    monkeypatch.setattr(settings_router, "resolve_plan_id", fake_resolve_plan_id)
    monkeypatch.setattr(settings_router, "get_plan_policy", fake_get_plan_policy)
    monkeypatch.setattr(settings_router, "quota_limit_for_plan", fake_quota_limit_for_plan)


def test_update_api_key_plan_rebinds_quota_and_clears_manual_override(monkeypatch):
    _patch_plan_helpers(monkeypatch)
    saved = _patch_memory_store(
        monkeypatch,
        {
            "api_keys": [
                _api_key_record(
                    quota_limit_override=42,
                    quota_policy={"id": "manual_override", "source": "manual"},
                    quota_limit=42,
                )
            ]
        },
    )

    response = asyncio.run(
        settings_router.update_api_key_plan(
            "key_1",
            settings_router.ApiKeyPlanUpdate(plan_id="pro"),
            current_user={"sub": "owner_user"},
        )
    )

    stored = saved["raw"]["api_keys"][0]

    assert saved["saved_user_id"] == "owner_user"
    assert response["status"] == "updated"
    assert response["change"] == "plan"
    assert response["id"] == "key_1"
    assert response["plan_id"] == "pro"
    assert response["quota_scope"] == "evaluation"
    assert response["quota_limit"] == 500
    assert response["quota_used"] == 35
    assert response["quota_remaining"] == 465
    assert response["quota_policy_source"] == "plan_store"
    assert response["quota_limit_override"] is None
    assert response["quota_rejected_count"] == 2

    assert stored["plan_id"] == "pro"
    assert stored["quota_limit"] == 500
    assert stored["quota_policy"]["id"] == "pro"
    assert stored["quota_policy"]["source"] == "plan_store"
    assert "quota_limit_override" not in stored


def test_update_api_key_quota_sets_manual_override(monkeypatch):
    _patch_plan_helpers(monkeypatch)
    saved = _patch_memory_store(
        monkeypatch,
        {
            "subscription": {"plan_id": "starter"},
            "api_keys": [_api_key_record(quota_limit=100, quota_used=35)],
        },
    )

    response = asyncio.run(
        settings_router.update_api_key_quota(
            "key_1",
            settings_router.ApiKeyQuotaUpdate(quota_limit_override=50),
            current_user={"sub": "owner_user"},
        )
    )

    stored = saved["raw"]["api_keys"][0]

    assert response["status"] == "updated"
    assert response["change"] == "quota_override_set"
    assert response["quota_limit"] == 50
    assert response["quota_used"] == 35
    assert response["quota_remaining"] == 15
    assert response["quota_policy_source"] == "manual"
    assert response["quota_limit_override"] == 50

    assert stored["quota_limit"] == 50
    assert stored["quota_limit_override"] == 50
    assert stored["quota_policy"]["id"] == "manual_override"
    assert stored["quota_policy"]["source"] == "manual"
    assert stored["quota_policy"]["quotas"]["evaluation"] == 50


def test_update_api_key_quota_clears_manual_override_back_to_plan(monkeypatch):
    _patch_plan_helpers(monkeypatch)
    saved = _patch_memory_store(
        monkeypatch,
        {
            "subscription": {"plan_id": "pro"},
            "api_keys": [
                _api_key_record(
                    plan_id="pro",
                    quota_limit=50,
                    quota_limit_override=50,
                    quota_policy={
                        "id": "manual_override",
                        "name": "Manual Quota Override",
                        "source": "manual",
                        "quotas": {"evaluation": 50},
                    },
                )
            ],
        },
    )

    response = asyncio.run(
        settings_router.update_api_key_quota(
            "key_1",
            settings_router.ApiKeyQuotaUpdate(quota_limit_override=None),
            current_user={"sub": "owner_user"},
        )
    )

    stored = saved["raw"]["api_keys"][0]

    assert response["status"] == "updated"
    assert response["change"] == "quota_override_cleared"
    assert response["plan_id"] == "pro"
    assert response["quota_limit"] == 500
    assert response["quota_used"] == 35
    assert response["quota_remaining"] == 465
    assert response["quota_policy_source"] == "plan_store"
    assert response["quota_limit_override"] is None

    assert stored["plan_id"] == "pro"
    assert stored["quota_limit"] == 500
    assert stored["quota_policy"]["id"] == "pro"
    assert stored["quota_policy"]["source"] == "plan_store"
    assert "quota_limit_override" not in stored


def test_api_key_quota_summary_handles_unlimited_quota():
    summary = settings_router._api_key_quota_summary(
        _api_key_record(
            quota_limit=-1,
            quota_used=999,
            quota_policy={"id": "enterprise", "source": "plan_store"},
        )
    )

    assert summary["quota_limit"] == -1
    assert summary["quota_used"] == 999
    assert summary["quota_remaining"] is None
    assert summary["quota_policy_source"] == "plan_store"