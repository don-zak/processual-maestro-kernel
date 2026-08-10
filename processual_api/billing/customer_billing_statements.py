from __future__ import annotations

import hashlib
import io
import json
import re
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterable

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

from processual_api.billing.maestro_units import (
    MAESTRO_UNIT_CONTRACT_VERSION,
    MAESTRO_UNIT_METRIC,
    normalize_maestro_metric_code,
)
from processual_api.billing.usage_pricing import PRICING_VERSION, monthly_unit_allowance
from processual_api.services.client_usage_summary import resolve_client_plan

BILLING_STATEMENT_SCHEMA_VERSION = "2026-08-customer-billing-statement-v1"
_SAFE_REF = re.compile(r"[^A-Za-z0-9_.-]+")

_LINE_ITEM_LABELS = {
    "analysis_evaluation": "Analysis",
    "governance_evaluation": "Governance",
    "batch_governance_evaluation": "Batch Governance",
    "report_generation": "Generated Reports",
    "metered_api_request": "Other Metered API Usage",
    "unattributed_authoritative_usage": "Unattributed Authoritative Usage",
}


class BillingStatementIntegrityError(ValueError):
    pass


def _as_int(value: Any, default: int = 0) -> int:
    try:
        return int(value if value is not None else default)
    except (TypeError, ValueError):
        return default


def _canonical_json(payload: dict[str, Any]) -> bytes:
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def statement_sha256(payload: dict[str, Any]) -> str:
    unsigned = {key: value for key, value in payload.items() if key != "statement_sha256"}
    return hashlib.sha256(_canonical_json(unsigned)).hexdigest()


def _period_bounds(period: str) -> tuple[str, str]:
    try:
        year_text, month_text = period.split("-", 1)
        year = int(year_text)
        month = int(month_text)
        if month < 1 or month > 12:
            raise ValueError
    except (ValueError, AttributeError):
        raise ValueError("billing period must use YYYY-MM") from None

    start = f"{year:04d}-{month:02d}-01T00:00:00+00:00"
    if month == 12:
        end = f"{year + 1:04d}-01-01T00:00:00+00:00"
    else:
        end = f"{year:04d}-{month + 1:02d}-01T00:00:00+00:00"
    return start, end


def _record_period(record: dict[str, Any]) -> str:
    explicit = str(record.get("quota_period") or "").strip()
    if explicit:
        return explicit[:7]
    return str(record.get("created_at") or "")[:7]


def _is_billable(record: dict[str, Any]) -> bool:
    status_code = _as_int(record.get("status_code"), 0)
    return 200 <= status_code < 400 and not bool(record.get("quota_rejected", False))


def _client_record(record: dict[str, Any], client_id: str) -> bool:
    return str(record.get("client_id") or "").strip() == client_id


def _statement_ref(client_id: str, period: str, digest: str) -> str:
    safe_client = _SAFE_REF.sub("-", client_id).strip("-.") or "client"
    return f"MUS-{period}-{safe_client[:24]}-{digest[:12]}"


def read_usage_records(data_dir: Path) -> list[dict[str, Any]]:
    path = data_dir / "usage_logs.jsonl"
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        return []

    records: list[dict[str, Any]] = []
    for line in lines:
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            records.append(payload)
    return records


def read_client_settings(data_dir: Path, user_id: str) -> dict[str, Any]:
    path = data_dir / f"settings_{user_id}.json"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _line_items(records: Iterable[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, int]]:
    grouped: dict[str, dict[str, int]] = defaultdict(lambda: {"requests": 0, "units": 0})
    rejected_requests = 0
    rejected_attempted_units = 0

    for record in records:
        units = max(_as_int(record.get("units_charged"), 0), 0)
        if _is_billable(record):
            endpoint_class = str(record.get("endpoint_class") or "metered_api_request")
            grouped[endpoint_class]["requests"] += 1
            grouped[endpoint_class]["units"] += units
        elif bool(record.get("quota_rejected", False)) or _as_int(record.get("status_code"), 0) == 429:
            rejected_requests += 1
            rejected_attempted_units += units

    items = [
        {
            "code": code,
            "label": _LINE_ITEM_LABELS.get(code, code.replace("_", " ").title()),
            "request_count": values["requests"],
            "maestro_units": values["units"],
        }
        for code, values in sorted(grouped.items())
        if values["units"] > 0
    ]
    return items, {
        "rejected_requests": rejected_requests,
        "rejected_attempted_units": rejected_attempted_units,
    }


def build_billing_statement(
    *,
    client_id: str,
    user_id: str,
    period: str,
    usage_records: Iterable[dict[str, Any]],
    raw_settings: dict[str, Any] | None = None,
    quota_cycle: dict[str, Any] | None = None,
    issued_at: str | None = None,
) -> dict[str, Any]:
    period_start, period_end = _period_bounds(period)
    matching = [
        record
        for record in usage_records
        if _client_record(record, client_id) and _record_period(record) == period
    ]

    items, rejected = _line_items(matching)
    attributed_units = sum(item["maestro_units"] for item in items)

    settings_payload = raw_settings if isinstance(raw_settings, dict) else {}
    resolved_plan, plan_source = resolve_client_plan(settings_payload)
    cycle = quota_cycle if isinstance(quota_cycle, dict) else {}
    plan_id = str(cycle.get("plan_code") or resolved_plan or "unknown")
    if not plan_id:
        plan_id = "unknown"

    metric = normalize_maestro_metric_code(cycle.get("metric_code") or MAESTRO_UNIT_METRIC)
    if metric and metric != MAESTRO_UNIT_METRIC:
        raise BillingStatementIntegrityError("quota cycle does not use Maestro Units")

    base_limit = max(
        _as_int(cycle.get("base_limit_units"), monthly_unit_allowance(plan_id)),
        0,
    )
    rollover_units = max(_as_int(cycle.get("rollover_units"), 0), 0)
    top_up_units = max(_as_int(cycle.get("top_up_units"), 0), 0)
    available_units = base_limit + rollover_units + top_up_units

    if cycle:
        authoritative_used = max(_as_int(cycle.get("used_units"), 0), 0)
        if attributed_units > authoritative_used:
            raise BillingStatementIntegrityError(
                "billable ledger units exceed authoritative quota-cycle usage"
            )
    else:
        authoritative_used = attributed_units

    unattributed = authoritative_used - attributed_units
    if unattributed > 0:
        items.append(
            {
                "code": "unattributed_authoritative_usage",
                "label": _LINE_ITEM_LABELS["unattributed_authoritative_usage"],
                "request_count": 0,
                "maestro_units": unattributed,
            }
        )

    item_total = sum(item["maestro_units"] for item in items)
    if item_total != authoritative_used:
        raise BillingStatementIntegrityError("billing line items do not reconcile to quota usage")

    closing_units = max(available_units - authoritative_used, 0)
    issued_timestamp = issued_at or datetime.now(UTC).isoformat()
    cycle_start = str(cycle.get("period_start") or period_start)
    cycle_end = str(cycle.get("period_end") or period_end)

    statement: dict[str, Any] = {
        "schema_version": BILLING_STATEMENT_SCHEMA_VERSION,
        "statement_ref": "",
        "statement_sha256": "",
        "issued_at": issued_timestamp,
        "client_id": client_id,
        "user_id": user_id,
        "billing_period": {
            "period": period,
            "period_start": cycle_start,
            "period_end": cycle_end,
        },
        "commercial_contract": {
            "metric": MAESTRO_UNIT_METRIC,
            "maestro_unit_contract_version": MAESTRO_UNIT_CONTRACT_VERSION,
            "pricing_version": PRICING_VERSION,
            "plan_catalog_version": str(cycle.get("plan_catalog_version") or ""),
        },
        "plan": {
            "plan_id": plan_id,
            "source": "quota_cycle" if cycle else plan_source,
            "base_allowance_units": base_limit,
        },
        "balance": {
            "base_allowance_units": base_limit,
            "rollover_units": rollover_units,
            "top_up_units": top_up_units,
            "available_units": available_units,
            "consumed_units": authoritative_used,
            "remaining_units": closing_units,
        },
        "usage_line_items": items,
        "non_billable_activity": rejected,
        "reconciliation": {
            "authoritative_used_units": authoritative_used,
            "line_item_units": item_total,
            "reconciled": item_total == authoritative_used,
            "unattributed_units": unattributed,
        },
    }

    provisional_digest = statement_sha256(statement)
    statement["statement_ref"] = _statement_ref(client_id, period, provisional_digest)
    statement["statement_sha256"] = statement_sha256(statement)
    return statement


def _statement_dir(data_dir: Path) -> Path:
    path = data_dir / "billing_statements"
    path.mkdir(parents=True, exist_ok=True)
    return path


def persist_statement(data_dir: Path, statement: dict[str, Any]) -> dict[str, Any]:
    expected = statement_sha256(statement)
    if statement.get("statement_sha256") != expected:
        raise BillingStatementIntegrityError("statement SHA-256 does not match canonical payload")

    ref = str(statement.get("statement_ref") or "")
    if not ref or _SAFE_REF.sub("", ref) != ref:
        raise BillingStatementIntegrityError("invalid statement reference")

    path = _statement_dir(data_dir) / f"{ref}.json"
    canonical = json.dumps(statement, sort_keys=True, indent=2, ensure_ascii=False) + "\n"
    if path.exists():
        existing = json.loads(path.read_text(encoding="utf-8"))
        if existing != statement:
            raise BillingStatementIntegrityError("immutable statement reference already exists")
        return existing

    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(canonical, encoding="utf-8")
    tmp.replace(path)
    return statement


def load_statement(data_dir: Path, statement_ref: str) -> dict[str, Any]:
    safe_ref = str(statement_ref or "").strip()
    if not safe_ref or _SAFE_REF.sub("", safe_ref) != safe_ref:
        raise FileNotFoundError(statement_ref)
    path = _statement_dir(data_dir) / f"{safe_ref}.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise BillingStatementIntegrityError("invalid statement snapshot")
    if payload.get("statement_sha256") != statement_sha256(payload):
        raise BillingStatementIntegrityError("stored statement SHA-256 verification failed")
    return payload


def list_statements(data_dir: Path, *, client_id: str | None = None) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for path in sorted(_statement_dir(data_dir).glob("MUS-*.json"), reverse=True):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(payload, dict):
            continue
        if client_id and str(payload.get("client_id") or "") != client_id:
            continue
        try:
            if payload.get("statement_sha256") != statement_sha256(payload):
                continue
        except Exception:
            continue
        results.append(payload)
    return results


def render_statement_pdf(statement: dict[str, Any]) -> bytes:
    if statement.get("statement_sha256") != statement_sha256(statement):
        raise BillingStatementIntegrityError("cannot render a statement with invalid SHA-256")

    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    x = 48
    y = height - 54

    def line(text: str, *, gap: int = 16, bold: bool = False) -> None:
        nonlocal y
        if y < 60:
            pdf.showPage()
            y = height - 54
        pdf.setFont("Helvetica-Bold" if bold else "Helvetica", 10 if not bold else 11)
        pdf.drawString(x, y, text[:115])
        y -= gap

    line("Maestro Usage Statement", gap=22, bold=True)
    line(f"Statement: {statement['statement_ref']}")
    line(f"SHA-256: {statement['statement_sha256']}", gap=22)
    line(f"Client: {statement['client_id']}")
    line(f"Period: {statement['billing_period']['period']}")
    line(f"Plan: {statement['plan']['plan_id']}", gap=22)

    balance = statement["balance"]
    line("Balance", bold=True)
    line(f"Base allowance: {balance['base_allowance_units']:,} Maestro Units")
    line(f"Rollover: {balance['rollover_units']:,} Maestro Units")
    line(f"Top-ups: {balance['top_up_units']:,} Maestro Units")
    line(f"Available: {balance['available_units']:,} Maestro Units")
    line(f"Consumed: {balance['consumed_units']:,} Maestro Units")
    line(f"Remaining: {balance['remaining_units']:,} Maestro Units", gap=22)

    line("Usage", bold=True)
    for item in statement["usage_line_items"]:
        line(
            f"{item['label']}: {item['request_count']:,} requests | "
            f"{item['maestro_units']:,} Maestro Units"
        )

    non_billable = statement["non_billable_activity"]
    y -= 8
    line("Rejected / non-billable activity", bold=True)
    line(f"Rejected requests: {non_billable['rejected_requests']:,}")
    line(f"Attempted units not deducted: {non_billable['rejected_attempted_units']:,}", gap=22)

    line("Integrity", bold=True)
    line(f"Reconciled: {statement['reconciliation']['reconciled']}")
    line(f"Maestro Unit contract: {statement['commercial_contract']['maestro_unit_contract_version']}")
    line(f"Pricing version: {statement['commercial_contract']['pricing_version']}")

    pdf.save()
    return buffer.getvalue()


__all__ = [
    "BILLING_STATEMENT_SCHEMA_VERSION",
    "BillingStatementIntegrityError",
    "build_billing_statement",
    "list_statements",
    "load_statement",
    "persist_statement",
    "read_client_settings",
    "read_usage_records",
    "render_statement_pdf",
    "statement_sha256",
]
