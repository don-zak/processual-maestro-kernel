#!/usr/bin/env bash
set -euo pipefail

python -m pytest -q \
  tests/test_admin_marketplace_original_offers_catalog.py \
  tests/test_admin_marketplace_original_offers_ui.py

python -m pytest -q \
  tests/test_admin_marketplace_authority_r1.py \
  tests/test_admin_marketplace_channel_policy_r1.py

python -m ruff check \
  processual_api/admin_marketplace/catalog_router.py \
  tests/test_admin_marketplace_original_offers_catalog.py \
  tests/test_admin_marketplace_original_offers_ui.py

python -m pytest -q
