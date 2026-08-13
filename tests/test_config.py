from pathlib import Path

from real_estate_monitor.config import Settings, parse_email_recipients


def test_parse_email_recipients_accepts_common_separators() -> None:
    value = "daniel@drumelia.com; Artur <artur@drumelia.com>,\n s.fluchaire@aionics.ai"

    assert parse_email_recipients(value) == [
        "daniel@drumelia.com",
        "artur@drumelia.com",
        "s.fluchaire@aionics.ai",
    ]


def test_settings_validates_multiple_web_users() -> None:
    settings = Settings(
        database_url="sqlite:///:memory:",
        report_dir=Path("reports"),
        log_level="INFO",
        scraper_headless=True,
        scraper_timeout_ms=30000,
        scraper_max_pages=0,
        scraper_retries=3,
        scraper_min_listing_ratio=0.85,
        scraper_max_removals_per_run=50,
        scraper_proxy_server=None,
        scraper_proxy_username=None,
        scraper_proxy_password=None,
        solvilla_proxy_server=None,
        solvilla_proxy_username=None,
        solvilla_proxy_password=None,
        telegram_enabled=False,
        telegram_bot_token=None,
        telegram_chat_id=None,
        whatsapp_enabled=False,
        whatsapp_access_token=None,
        whatsapp_phone_number_id=None,
        whatsapp_recipient=None,
        whatsapp_graph_api_version="v20.0",
        email_enabled=False,
        email_smtp_host=None,
        email_smtp_port=587,
        email_username=None,
        email_password=None,
        email_from=None,
        email_to=None,
        email_use_tls=True,
        scrape_schedule_time="09:00",
        scrape_schedule_timezone="Europe/Madrid",
        web_auth_enabled=True,
        web_username=None,
        web_password=None,
        web_users="one@drumelia.com:abc,two@drumelia.com:def",
        custom_report_max_concurrent_jobs=2,
    )

    assert settings.valid_web_credentials("one@drumelia.com", "abc")
    assert settings.valid_web_credentials("two@drumelia.com", "def")
    assert not settings.valid_web_credentials("two@drumelia.com", "abc")
