from fastapi import APIRouter, Depends

from api.dependencies import get_current_user
from core.system_mode import current_system_mode
from core.worker_metrics import metrics_snapshot
from schemas.auth import UserContext

router = APIRouter(prefix="/metrics", tags=["metrics"])


@router.get("/workers")
async def worker_metrics(_user: UserContext = Depends(get_current_user)) -> dict:
    metrics = metrics_snapshot()
    metrics["system_mode"] = current_system_mode()
    return metrics
