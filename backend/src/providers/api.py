"""Read-only provider readiness endpoint.

No external provider is called here. Live BRS/KRA/Peleza integrations must be added
only after approved endpoint contracts, credentials, permissions and data terms exist.
"""
import os
from datetime import datetime, timezone

from fastapi import APIRouter, Depends

from ..security import require_api_key

router = APIRouter(prefix="/api/v1/providers", tags=["registry providers"], dependencies=[Depends(require_api_key)])

_PROVIDER_ENV = {
    "brs": ("BRS_API_BASE_URL", "BRS_API_TOKEN"),
    "kra": ("KRA_API_BASE_URL", "KRA_API_TOKEN"),
    "peleza": ("PELEZA_API_BASE_URL", "PELEZA_API_TOKEN"),
}


@router.get("/status")
def provider_status():
    items = []
    for name, env_names in _PROVIDER_ENV.items():
        credentials_present = all(bool(os.getenv(key, "").strip()) for key in env_names)
        items.append({
            "provider": name,
            "status": "not_connected",
            "connected": False,
            "configuration_present": credentials_present,
            "required_configuration": list(env_names),
            "capability": "adapter_contract_only",
            "message": "No live adapter is enabled. This endpoint does not call the provider or verify an organization.",
        })
    return {
        "items": items,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "warning": "Credentials alone do not establish provider connectivity or authorization. Confirm contracts and data-processing terms before implementing a live adapter.",
    }
