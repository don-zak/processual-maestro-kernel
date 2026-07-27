from unittest.mock import AsyncMock

import inspect

from processual_api.admin_marketplace.persistence.repositories import (
    SqlAlchemyChannelEligibilityRepository,
)


def test_channel_eligibility_repository_has_customer_lookup():
    session = AsyncMock()

    repository = SqlAlchemyChannelEligibilityRepository(session)

    assert hasattr(repository, "get_by_customer_ref")

    method = repository.get_by_customer_ref

    assert inspect.iscoroutinefunction(method)
