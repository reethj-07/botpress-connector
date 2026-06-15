import time
from typing import Any

from app.connector.client import BotpressClient
from app.connector.errors import BotpressTimeoutError, ConnectorError, sanitize_error


DEFAULT_REPLY_TIMEOUT_SEC = 60
DEFAULT_POLL_INTERVAL_SEC = 2


def redact_webhook_id(webhook_id: str) -> str:
    if len(webhook_id) <= 8:
        return "***"
    return f"{webhook_id[:4]}...{webhook_id[-4:]}"


def extract_text_from_payload(payload: dict[str, Any]) -> str | None:
    payload_type = payload.get("type")
    if payload_type in {"text", "markdown"}:
        text = payload.get("text") or payload.get("markdown")
        return str(text) if text else None
    if payload_type == "choice":
        text = payload.get("text")
        options = payload.get("options") or []
        option_text = ", ".join(str(item.get("label") or item.get("value")) for item in options if isinstance(item, dict))
        return " ".join(part for part in [text, option_text] if part)
    if payload_type == "carousel":
        cards = payload.get("items") or payload.get("cards") or []
        fragments: list[str] = []
        for card in cards:
            if isinstance(card, dict):
                fragments.extend(str(card.get(key)) for key in ("title", "subtitle") if card.get(key))
        return "\n".join(fragments) if fragments else None
    return None


class BotpressScanner:
    def __init__(self, target_config: dict[str, Any], http_client: BotpressClient | None = None) -> None:
        self.target_config = target_config
        self.webhook_id = str(target_config["webhook_id"]).strip()
        self.reply_timeout_sec = float(target_config.get("reply_timeout_sec") or DEFAULT_REPLY_TIMEOUT_SEC)
        self.poll_interval_sec = float(target_config.get("poll_interval_sec") or DEFAULT_POLL_INTERVAL_SEC)
        self.client = http_client or BotpressClient(
            self.webhook_id,
            base_url=str(target_config.get("base_url") or "https://chat.botpress.cloud"),
            encryption_key=target_config.get("encryption_key"),
            user_id=target_config.get("user_id"),
        )
        self.user_id: str | None = None
        self.user_key: str | None = None
        self.conversation_id: str | None = None

    def validate_target(self) -> bool:
        try:
            self.client.hello()
            self._ensure_conversation()
            result = self.execute_test("validation", "ping", "ping")
            return bool(result["success"])
        except ConnectorError:
            return False

    def execute_test(self, vulnerability_id: str, attack_id: str, test_input: str) -> dict[str, Any]:
        started = time.monotonic()
        message_id: str | None = None
        try:
            self._ensure_conversation()
            assert self.user_key and self.conversation_id and self.user_id
            message = self.client.create_message(self.user_key, self.conversation_id, test_input)
            message_id = str(message.get("id")) if message.get("id") else None
            response = self._wait_for_bot_reply(message_id)
            return self._result(
                True,
                vulnerability_id,
                attack_id,
                response["text"],
                started,
                None,
                message_id,
            )
        except BotpressTimeoutError as exc:
            return self._result(False, vulnerability_id, attack_id, None, started, sanitize_error(exc.message), message_id)
        except ConnectorError as exc:
            return self._result(False, vulnerability_id, attack_id, None, started, sanitize_error(exc.message), message_id)
        except Exception as exc:
            return self._result(False, vulnerability_id, attack_id, None, started, sanitize_error(exc), message_id)

    def reset_conversation(self) -> None:
        self.conversation_id = None
        self._ensure_conversation()

    def get_platform_metadata(self) -> dict[str, Any]:
        return {
            "platform": "botpress",
            "webhook_id": redact_webhook_id(self.webhook_id),
            "resource_name": self.target_config.get("resource_name"),
            "delivery_mode": "poll",
        }

    def _ensure_conversation(self) -> None:
        if not self.user_key:
            self.user_id, self.user_key = self.client.create_user()
        if not self.conversation_id:
            self.conversation_id = self.client.create_conversation(self.user_key)

    def _wait_for_bot_reply(self, sent_message_id: str | None) -> dict[str, str]:
        assert self.user_key and self.conversation_id and self.user_id
        deadline = time.monotonic() + self.reply_timeout_sec
        seen_sent_message = sent_message_id is None

        while time.monotonic() < deadline:
            messages = sorted(self.client.list_messages(self.user_key, self.conversation_id), key=lambda item: item.get("createdAt", ""))
            for message in messages:
                if sent_message_id and message.get("id") == sent_message_id:
                    seen_sent_message = True
                    continue
                if not seen_sent_message:
                    continue
                if message.get("userId") == self.user_id:
                    continue
                text = extract_text_from_payload(message.get("payload") or {})
                if text:
                    return {"text": text, "message_id": str(message.get("id") or "")}
            time.sleep(self.poll_interval_sec)

        raise BotpressTimeoutError("Timed out waiting for a Botpress reply.")

    def _result(
        self,
        success: bool,
        vulnerability_id: str,
        attack_id: str,
        model_response: str | None,
        started: float,
        error: str | None,
        message_id: str | None,
    ) -> dict[str, Any]:
        return {
            "vulnerability_id": vulnerability_id,
            "attack_id": attack_id,
            "success": success,
            "model_response": model_response,
            "execution_time_ms": int((time.monotonic() - started) * 1000),
            "error": error,
            "metadata": {
                "platform": "botpress",
                "conversation_id": self.conversation_id,
                "webhook_id": redact_webhook_id(self.webhook_id),
                "message_id": message_id,
                "delivery_mode": "poll",
            },
        }

