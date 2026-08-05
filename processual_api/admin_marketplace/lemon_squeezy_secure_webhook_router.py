from __future__ import annotations

import os

from fastapi import APIRouter, HTTPException, Request
from fastapi.routing import APIRoute

from processual_api.admin_marketplace.lemon_squeezy_ingestion_service import (
    ingest_lemon_squeezy_webhook_request_factory,
)
from processual_api.admin_marketplace.lemon_squeezy_webhooks import (
    LemonSquee