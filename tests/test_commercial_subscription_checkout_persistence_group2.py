from processual_api.billing.commercial_subscription_checkout_models import (
    CommercialSubscriptionActivationDecisionRow,
    CommercialSubscriptionCheckoutOrderRow,
    CommercialSubscriptionPaymentEvidenceRow,
)
from processual_api.billing.commercial_subscription_checkout_unit_of_work import (
    COMMERCIAL_SUBSCRIPTION_CHECKOUT_RUNTIME_WIRING_ENABLED,
    COMMERCIAL_SUBSCRIPTION_CHECKOUT_SQLALCHEMY_UOW_ENABLED,
)


def test_checkout_persistence_tables_are_distinct() -> None:
    assert CommercialSubscriptionCheckoutOrderRow.__tablename__ == ("commercial_subscription_checkout_orders")
    assert CommercialSubscriptionPaymentEvidenceRow.__tablename__ == ("commercial_subscription_payment_evidence")
    assert CommercialSubscriptionActivationDecisionRow.__tablename__ == ("commercial_subscription_activation_decisions")


def test_checkout_persistence_remains_fail_closed() -> None:
    assert COMMERCIAL_SUBSCRIPTION_CHECKOUT_SQLALCHEMY_UOW_ENABLED is False
    assert COMMERCIAL_SUBSCRIPTION_CHECKOUT_RUNTIME_WIRING_ENABLED is False


def test_activation_table_requires_platform_admin() -> None:
    names = {item.name for item in CommercialSubscriptionActivationDecisionRow.__table__.constraints if item.name}
    assert "ck_commercial_subscription_activation_decisions_platform_admin_exact" in names
