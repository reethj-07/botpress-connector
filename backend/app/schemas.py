from typing import Any

from pydantic import BaseModel, Field


class ResourceCreate(BaseModel):
    account_name: str = Field(min_length=1)
    resource_name: str = Field(min_length=1)
    webhook_id: str = Field(min_length=4, pattern=r"^[A-Za-z0-9_\-]+$")
    encryption_key: str | None = None
    user_id: str | None = None
    description: str | None = None


class ResourceOut(BaseModel):
    id: str
    account_name: str
    resource_name: str
    webhook_id: str
    encryption_key: None = None
    user_id: str | None = None
    description: str | None = None
    validation_status: str
    last_validated_at: str | None = None
    created_at: str
    updated_at: str


class PromptIn(BaseModel):
    vulnerability_id: str = Field(min_length=1)
    attack_id: str = Field(min_length=1)
    test_input: str = Field(min_length=1)


class ScanRequest(BaseModel):
    prompts: list[PromptIn] = Field(min_length=1)
    reset_conversation: bool = True


class ScanResultOut(BaseModel):
    vulnerability_id: str
    attack_id: str
    success: bool
    model_response: str | None
    execution_time_ms: int
    error: str | None
    metadata: dict[str, Any]

