import socket
import threading
import time
from contextlib import contextmanager
from typing import Iterator

import uvicorn
from fastapi import FastAPI, Header, HTTPException


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def create_mock_botpress_app(*, delayed_attempts: int = 0, rate_limit_messages: bool = False) -> FastAPI:
    app = FastAPI()
    state = {"conversations": {}, "polls": {}}

    @app.get("/{webhook_id}/hello")
    def hello(webhook_id: str):
        if webhook_id == "missing":
            raise HTTPException(status_code=404, detail="missing")
        return {"hello": "world"}

    @app.post("/{webhook_id}/users", status_code=201)
    def create_user(webhook_id: str, payload: dict):
        user_id = payload.get("id") or "user_mock"
        return {"user": {"id": user_id}, "key": f"key_{user_id}"}

    @app.post("/{webhook_id}/conversations", status_code=201)
    def create_conversation(webhook_id: str, x_user_key: str = Header()):
        conversation_id = f"conv_{len(state['conversations']) + 1}"
        state["conversations"][conversation_id] = []
        state["polls"][conversation_id] = 0
        return {"conversation": {"id": conversation_id}}

    @app.post("/{webhook_id}/messages", status_code=201)
    def create_message(webhook_id: str, payload: dict, x_user_key: str = Header()):
        if rate_limit_messages:
            raise HTTPException(status_code=429, detail="rate limited")
        conversation_id = payload["conversationId"]
        user_id = x_user_key.replace("key_", "")
        message = {
            "id": f"msg_{len(state['conversations'][conversation_id]) + 1}",
            "createdAt": "2026-01-01T00:00:00Z",
            "userId": user_id,
            "conversationId": conversation_id,
            "payload": payload["payload"],
        }
        state["conversations"][conversation_id].append(message)
        return {"message": message}

    @app.get("/{webhook_id}/conversations/{conversation_id}/messages")
    def list_messages(webhook_id: str, conversation_id: str, x_user_key: str = Header()):
        state["polls"][conversation_id] += 1
        messages = list(state["conversations"][conversation_id])
        if state["polls"][conversation_id] > delayed_attempts:
            messages.append(
                {
                    "id": "bot_msg_1",
                    "createdAt": "2026-01-01T00:00:01Z",
                    "userId": "bot_mock",
                    "conversationId": conversation_id,
                    "payload": {"type": "text", "text": "Mock bot response"},
                }
            )
        return {"messages": messages, "meta": {}}

    return app


@contextmanager
def run_mock_botpress(app: FastAPI) -> Iterator[str]:
    port = free_port()
    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    deadline = time.time() + 5
    while not server.started and time.time() < deadline:
        time.sleep(0.01)
    try:
        yield f"http://127.0.0.1:{port}"
    finally:
        server.should_exit = True
        thread.join(timeout=5)

