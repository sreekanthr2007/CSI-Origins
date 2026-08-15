"""API route handlers for Cross-Bank Mule Detection services."""
from fastapi import APIRouter
from typing import Dict, Any, List
from backend.app.data_generator.synthetic_banks import get_registered_banks

router = APIRouter()


@router.get("/banks", response_model=List[Dict[str, Any]])
def list_banks() -> List[Dict[str, Any]]:
    """Return participating banks."""
    return get_registered_banks()


@router.get("/status")
def get_system_status() -> Dict[str, Any]:
    """Return current network status and module state."""
    return {
        "status": "OPERATIONAL",
        "flow_a_active": True,
        "flow_b_ready": True,
        "registered_banks_count": len(get_registered_banks())
    }
