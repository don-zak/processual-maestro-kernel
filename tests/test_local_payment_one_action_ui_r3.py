from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXUPS = ROOT / "processual_api" / "static" / "js" / "admin_runtime_fixups.js"


def test_admin_local_payment_normal_path_is_one_activation_action() -> None:
    script = FIXUPS.read_text(encoding="utf-8")

    assert "function alignLocalPaymentActivationUi()" in script
    assert "Activate payment route" in script
    assert "validates, activates, and publishes it as the default customer payment route" in script
    assert "makes it the default route" in script
    assert "Retries resume safely with the same idempotency key" in script


def test_admin_local_payment_activation_copy_replaces_legacy_multi_step_copy() -> None:
    script = FIXUPS.read_text(encoding="utf-8")

    assert "Create and validate destination?" in script
    assert "Activate payment route?" in script
    assert "Payment destination created and validated. Activate it separately when ready." in script
    assert "Payment route is active, default, and ready for eligible Tunisian customers." in script
    assert "MutationObserver" in script
