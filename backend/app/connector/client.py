import base64
import hashlib
import hmac
import json
import time
import uuid
from typing import Any

import httpx

from app.connector.errors import ConnectorError, map_status_error, sanitize_error


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def sign_user_key(user_id: str, encryption_key: str) -> str:
    header = {"alg": "HS256", "typ": "JWT"}
    payload = {"id": user_id, "iat": int(time.time())}
    signing_input = ".".join(
        [
            _b64url(json.dumps(header, separators=(",", ":")).encode("utf-8")),
            _b64url(json.dumps(payload, separators=(",", ":")).encode("utf-8")),
        ]
    )
    signature = hmac.new(encryption_key.encode("utf-8"), signing_input.encode("ascii"), hashlib.sha256).digest()
    return f"{signing_input}.{_b64url(signature)}"


class BotpressClient:
    def __init__(
        self,
        webhook_id: str,
        *,
        base_url: str = "https://chat.botpress.cloud",
        encryption_key: str | None = None,
        user_id: str | None = None,
        timeout_sec: float = 20,
        http_client: httpx.Client | None = None,
    ) -> None:
        self.webhook_id = webhook_id.strip()
        self.base_url = base_url.rstrip("/")
        self.encryption_key = encryption_key
        self.user_id = user_id
        self.timeout_sec = timeout_sec
        self._client = http_client or httpx.Client(timeout=timeout_sec)

    @property
    def root_url(self) -> str:
        return f"{self.base_url}/{self.webhook_id}"

    def hello(self) -> dict[str, Any]:
        return self._request("GET", "/hello")

    def create_user(self) -> tuple[str, str]:
        if self.encryption_key and self.user_id:
            return self.user_id, sign_user_key(self.user_id, self.encryption_key)

        user_id = f"scanner_{uuid.uuid4().hex}"
        data = self._request("POST", "/users", json={"id": user_id, "name": "Security Scanner"})
        user = data.get("user") or {}
        try:
            return str(user.get("id") or user_id), str(data["key"])
        except KeyError as exc:
            raise ConnectorError("Botpress did not return a user key. Ensure the Webhook ID is valid.") from exc

    def create_conversation(self, user_key: str) -> str:
        data = self._request("POST", "/conversations", headers=self._auth(user_key), json={})
        return str(data["conversation"]["id"])

    def create_message(self, user_key: str, conversation_id: str, text: str) -> dict[str, Any]:
        payload = {"conversationId": conversation_id, "payload": {"type": "text", "text": text}}
        return self._request("POST", "/messages", headers=self._auth(user_key), json=payload)["message"]

    def list_messages(self, user_key: str, conversation_id: str) -> list[dict[str, Any]]:
        data = self._request("GET", f"/conversations/{conversation_id}/messages", headers=self._auth(user_key))
        return list(data.get("messages") or [])

    def _auth(self, user_key: str) -> dict[str, str]:
        return {"x-user-key": user_key}

    def _request(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        try:
            response = self._client.request(method, f"{self.root_url}{path}", **kwargs)
        except httpx.TimeoutException as exc:
            raise ConnectorError("Botpress request timed out.") from exc
        except httpx.HTTPError as exc:
            raise ConnectorError(sanitize_error(exc)) from exc

        if response.status_code >= 400:
            raise ConnectorError(map_status_error(response.status_code), response.status_code)

        if not response.content:
            return {}
        try:
            return response.json()
        except ValueError as exc:
            raise ConnectorError("Botpress returned an invalid JSON response.") from exc

