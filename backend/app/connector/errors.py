import re
from dataclasses import dataclass


SECRET_PATTERNS = [
    re.compile(r"Bearer\s+[A-Za-z0-9._\-]+", re.IGNORECASE),
    re.compile(r"x-user-key[:=]\s*[A-Za-z0-9._\-]+", re.IGNORECASE),
]


@dataclass
class ConnectorError(Exception):
    message: str
    status_code: int | None = None


class BotpressTimeoutError(ConnectorError):
    pass


def sanitize_error(value: object) -> str:
    text = str(value) if value else "Botpress request failed."
    for pattern in SECRET_PATTERNS:
        text = pattern.sub("[redacted]", text)
    if len(text) > 500:
        text = text[:497] + "..."
    return text


def map_status_error(status_code: int) -> str:
    if status_code in {401, 403}:
        return "Botpress rejected the credentials or user key."
    if status_code == 404:
        return "Botpress webhook or conversation was not found."
    if status_code == 429:
        return "Botpress rate limit reached. Wait and retry."
    if 500 <= status_code:
        return "Botpress service returned an upstream error."
    return f"Botpress request failed with HTTP {status_code}."

