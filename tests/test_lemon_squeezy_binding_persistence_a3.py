from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from processual_api.admin_marketplace.lemon_squeezy_binding_persistence import (
    AdminMarketLemonSqueezyBinding,
    AdminMarketLemon