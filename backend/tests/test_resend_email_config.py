from src.config import Settings


def test_resend_is_sufficient_for_otp_delivery_when_pepper_is_strong():
    settings = Settings(
        _env_file=None,
        resend_api_key="re_test_key",
        resend_from_email="PesaGuard <no-reply@example.com>",
        auth_otp_pepper="p" * 32,
    )
    assert settings.auth_email_delivery_configured is True


def test_resend_without_from_address_does_not_enable_otp_delivery():
    settings = Settings(
        _env_file=None,
        resend_api_key="re_test_key",
        resend_from_email="",
        auth_otp_pepper="p" * 32,
    )
    assert settings.auth_email_delivery_configured is False


def test_weak_otp_pepper_disables_email_auth_even_with_resend():
    settings = Settings(
        _env_file=None,
        resend_api_key="re_test_key",
        resend_from_email="PesaGuard <no-reply@example.com>",
        auth_otp_pepper="too-short",
    )
    assert settings.auth_email_delivery_configured is False


def test_smtp_remains_an_explicit_fallback():
    settings = Settings(
        _env_file=None,
        smtp_host="smtp.example.com",
        smtp_from_email="no-reply@example.com",
        auth_otp_pepper="p" * 32,
    )
    assert settings.auth_email_delivery_configured is True
