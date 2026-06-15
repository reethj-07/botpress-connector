from app.connector.scanner import BotpressScanner

from tests.mock_botpress import create_mock_botpress_app, run_mock_botpress


def test_scanner_against_mock_botpress_happy_path():
    app = create_mock_botpress_app(delayed_attempts=1)
    with run_mock_botpress(app) as base_url:
        scanner = BotpressScanner(
            {
                "webhook_id": "mock_webhook",
                "base_url": base_url,
                "reply_timeout_sec": 2,
                "poll_interval_sec": 0.01,
            }
        )
        result = scanner.execute_test("prompt_injection", "direct_extraction", "hello")

    assert result["success"] is True
    assert result["model_response"] == "Mock bot response"


def test_scanner_against_mock_botpress_rate_limit_case():
    app = create_mock_botpress_app(rate_limit_messages=True)
    with run_mock_botpress(app) as base_url:
        scanner = BotpressScanner(
            {
                "webhook_id": "mock_webhook",
                "base_url": base_url,
                "reply_timeout_sec": 1,
                "poll_interval_sec": 0.01,
            }
        )
        result = scanner.execute_test("prompt_injection", "direct_extraction", "hello")

    assert result["success"] is False
    assert "rate limit" in result["error"].lower()

