import copy
import json

import pytest

from processual_api.services.client_plan_source import (
    ClientRequestPlanApplyError,
    apply_verified_client_request_plan,
    supported_verified_plan,
)

FORBIDDEN_MARKERS = (
    'provider_secret',
    'encrypted_key',
    'raw_key',
    'token',
    'password',
    'api_key',
)


def _entry(**overrides):
    data = {
        'request_id': 'creq_plan_source_123',
        'client_id': 'client-plan',
        'request_type': 'billing_usage_review',
        'requested_plan': 'business',
        'status': 'approved',
        'created_at': '2026-07-06T10:00:00+00:00',
        'source': 'client_settings',
        'message': 'Please apply our verified plan safely.',
    }
    data.update(overrides)
    return data


def test_supported_verified_plan_uses_pricing_catalog():
    assert supported_verified_plan('Business') == ('business', 100000)
    assert supported_verified_plan('enterprise integration') == (
        'enterprise_integration',
        500000,
    )
    assert supported_verified_plan('imaginary') == ('', 0)


def test_apply_verified_client_request_plan_sets_source_fields():
    entry = _entry()

    result = apply_verified_client_request_plan(
        entry,
        actor='owner-admin',
        now='2026-07-06T18:00:00+00:00',
    )

    assert result == {
        'status': 'plan_applied',
        'changed': True,
        'plan': {
            'plan_id': 'business',
            'source': 'client_requests',
            'monthly_unit_allowance': 100000,
        },
    }
    assert entry['approved_plan'] == 'business'
    assert entry['plan_source'] == 'client_requests'
    assert entry['plan_applied'] is True
    assert entry['plan_applied_at'] == '2026-07-06T18:00:00+00:00'
    assert entry['plan_applied_by'] == 'owner-admin'
    assert entry['updated_at'] == '2026-07-06T18:00:00+00:00'
    assert entry['status_history'][-1]['event'] == 'plan_applied'
    assert entry['status_history'][-1]['plan_id'] == 'business'
    assert entry['status_history'][-1]['source'] == 'admin_clients_panel'

    serialized = json.dumps({'result': result, 'entry': entry}, sort_keys=True).lower()
    for marker in FORBIDDEN_MARKERS:
        assert marker not in serialized


def test_completed_request_can_apply_verified_plan():
    entry = _entry(status='completed', requested_plan='starter')

    result = apply_verified_client_request_plan(
        entry,
        actor='owner-admin',
        now='2026-07-06T18:00:00+00:00',
    )

    assert result['status'] == 'plan_applied'
    assert result['plan']['plan_id'] == 'starter'
    assert result['plan']['monthly_unit_allowance'] == 10000
    assert entry['approved_plan'] == 'starter'


def test_apply_verified_client_request_plan_is_idempotent():
    entry = _entry()

    first = apply_verified_client_request_plan(
        entry,
        actor='owner-admin',
        now='2026-07-06T18:00:00+00:00',
    )
    second = apply_verified_client_request_plan(
        entry,
        actor='owner-admin',
        now='2026-07-06T18:01:00+00:00',
    )

    assert first['status'] == 'plan_applied'
    assert second['status'] == 'already_applied'
    assert second['changed'] is False
    assert [
        item for item in entry['status_history'] if item.get('event') == 'plan_applied'
    ] == [entry['status_history'][0]]
    assert entry['plan_applied_at'] == '2026-07-06T18:00:00+00:00'


def test_apply_verified_client_request_plan_rejects_pending_request():
    entry = _entry(status='reviewed')
    before = copy.deepcopy(entry)

    with pytest.raises(ClientRequestPlanApplyError) as exc:
        apply_verified_client_request_plan(
            entry,
            actor='owner-admin',
            now='2026-07-06T18:00:00+00:00',
        )

    assert exc.value.reason == 'request_not_approved'
    assert entry == before


def test_apply_verified_client_request_plan_rejects_unknown_plan():
    entry = _entry(requested_plan='imaginary')
    before = copy.deepcopy(entry)

    with pytest.raises(ClientRequestPlanApplyError) as exc:
        apply_verified_client_request_plan(
            entry,
            actor='owner-admin',
            now='2026-07-06T18:00:00+00:00',
        )

    assert exc.value.reason == 'unsupported_plan'
    assert entry == before

