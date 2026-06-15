from fastapi import APIRouter, Depends, HTTPException

from app.config import Settings, get_settings
from app.connector.scanner import BotpressScanner, redact_webhook_id
from app.schemas import ResourceCreate, ScanRequest
from app.storage import Store

router = APIRouter()


def get_store(settings: Settings = Depends(get_settings)) -> Store:
    return Store(settings.database_url)


def public_resource(resource: dict) -> dict:
    data = dict(resource)
    data["webhook_id"] = redact_webhook_id(str(data["webhook_id"]))
    data["encryption_key"] = None
    return data


def scanner_for(resource: dict, settings: Settings) -> BotpressScanner:
    return BotpressScanner(
        {
            "webhook_id": resource["webhook_id"],
            "resource_name": resource["resource_name"],
            "encryption_key": resource.get("encryption_key"),
            "user_id": resource.get("user_id"),
            "base_url": settings.botpress_chat_base_url,
        }
    )


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/ready")
def ready(store: Store = Depends(get_store)) -> dict[str, str]:
    store.init()
    return {"status": "ready"}


@router.post("/api/v1/resources", status_code=201)
def create_resource(payload: ResourceCreate, store: Store = Depends(get_store)) -> dict:
    resource = store.create_resource(payload.model_dump())
    return public_resource(resource)


@router.get("/api/v1/resources")
def list_resources(store: Store = Depends(get_store)) -> dict[str, list[dict]]:
    return {"resources": [public_resource(resource) for resource in store.list_resources()]}


@router.get("/api/v1/resources/{resource_id}")
def get_resource(resource_id: str, store: Store = Depends(get_store)) -> dict:
    try:
        return public_resource(store.get_resource(resource_id))
    except KeyError:
        raise HTTPException(status_code=404, detail="Resource not found")


@router.post("/api/v1/resources/{resource_id}/validate")
def validate_resource(resource_id: str, store: Store = Depends(get_store), settings: Settings = Depends(get_settings)) -> dict:
    try:
        resource = store.get_resource(resource_id, include_secrets=True)
    except KeyError:
        raise HTTPException(status_code=404, detail="Resource not found")
    valid = scanner_for(resource, settings).validate_target()
    updated = store.update_validation(resource_id, "validated" if valid else "failed")
    return {"valid": valid, "resource": public_resource(updated)}


@router.post("/api/v1/resources/{resource_id}/scan")
def scan_resource(
    resource_id: str,
    payload: ScanRequest,
    store: Store = Depends(get_store),
    settings: Settings = Depends(get_settings),
) -> dict:
    try:
        resource = store.get_resource(resource_id, include_secrets=True)
    except KeyError:
        raise HTTPException(status_code=404, detail="Resource not found")

    scanner = scanner_for(resource, settings)
    results = []
    for index, prompt in enumerate(payload.prompts):
        if payload.reset_conversation and index == 0:
            scanner.reset_conversation()
        result = scanner.execute_test(prompt.vulnerability_id, prompt.attack_id, prompt.test_input)
        results.append(result)
    run = store.create_scan_run(resource_id, [prompt.model_dump() for prompt in payload.prompts], results)
    return {"resource_id": resource_id, "scan_run_id": run["id"], "results": results}


@router.get("/api/v1/resources/{resource_id}/scans")
def list_scans(resource_id: str, store: Store = Depends(get_store)) -> dict[str, list[dict]]:
    try:
        store.get_resource(resource_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Resource not found")
    return {"scans": store.list_scans(resource_id)}

