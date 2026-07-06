from __future__ import annotations

from typing import Any

from processual_api.billing.usage_pricing import monthly_unit_allowance, normalize_plan_id

VERIFIED_CLIENT_REQUEST_PLAN_SOURCE = 'client_requests'
PLAN_APPLIED_EVENT = 'plan_applied'
ELIGIBLE_PLAN_REQUEST_STATUSES = frozenset({'approved', 'completed'})


class ClientRequestPlanApplyError(ValueError):
    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


def _text(value: Any) -> str:
    return str(value or '').strip()


def supported_verified_plan(plan_value: Any) -> tuple[str, int]:
    plan_id = normalize_plan_id(_text(plan_value))
    allowance = monthly_unit_allowance(plan_id)
    if not plan_id or allowance <= 0:
        return '', 0
    return plan_id, allowance


def request_plan_candidate(entry: dict[str, Any]) -> str:
    for key in ('approved_plan', 'requested_plan', 'plan_id', 'plan'):
        value = _text(entry.get(key))
        if value:
            return value
    return ''


def _append_plan_applied_history(
    entry: dict[str, Any],
    *,
    plan_id: str,
    actor: str,
    now: str,
    note: str,
) -> None:
    history = entry.get('status_history')
    if not isinstance(history, list):
        history = []

    event: dict[str, Any] = {
        'status': _text(entry.get('status')) or 'approved',
        'event': PLAN_APPLIED_EVENT,
        'plan_id': plan_id,
        'plan_source': VERIFIED_CLIENT_REQUEST_PLAN_SOURCE,
        'at': now,
        'actor': actor,
        'source': 'admin_clients_panel',
    }
    if note:
        event['note'] = note

    history.append(event)
    entry['status_history'] = history


def apply_verified_client_request_plan(
    entry: dict[str, Any],
    *,
    actor: str,
    now: str,
    note: str | None = None,
) -> dict[str, Any]:
    if not isinstance(entry, dict):
        raise ClientRequestPlanApplyError('invalid_request')

    request_status = _text(entry.get('status')).lower()
    if request_status not in ELIGIBLE_PLAN_REQUEST_STATUSES:
        raise ClientRequestPlanApplyError('request_not_approved')

    plan_id, allowance = supported_verified_plan(request_plan_candidate(entry))
    if not plan_id or allowance <= 0:
        raise ClientRequestPlanApplyError('unsupported_plan')

    actor_text = _text(actor) or 'admin'
    now_text = _text(now)
    note_text = _text(note) or 'Verified plan source applied from approved client request.'

    already_applied = (
        entry.get('plan_applied') is True
        and normalize_plan_id(entry.get('approved_plan')) == plan_id
        and _text(entry.get('plan_source')) == VERIFIED_CLIENT_REQUEST_PLAN_SOURCE
    )

    if not already_applied:
        entry['approved_plan'] = plan_id
        entry['plan_source'] = VERIFIED_CLIENT_REQUEST_PLAN_SOURCE
        entry['plan_applied'] = True
        entry['plan_applied_at'] = now_text
        entry['plan_applied_by'] = actor_text
        entry['updated_at'] = now_text
        _append_plan_applied_history(
            entry,
            plan_id=plan_id,
            actor=actor_text,
            now=now_text,
            note=note_text,
        )

    return {
        'status': 'already_applied' if already_applied else 'plan_applied',
        'changed': not already_applied,
        'plan': {
            'plan_id': plan_id,
            'source': VERIFIED_CLIENT_REQUEST_PLAN_SOURCE,
            'monthly_unit_allowance': allowance,
        },
    }

