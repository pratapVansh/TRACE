from fastapi import APIRouter, Depends

from app.api.authorization import require_permission
from app.core.authorization import PERMISSIONS
from app.schemas.auth import UserMeResponse
from app.schemas.demo import DemoAdminResponse

router = APIRouter(prefix="/demo", tags=["demo"])


@router.get("/admin", response_model=DemoAdminResponse)
async def demo_admin_access(
    current_user: UserMeResponse = Depends(require_permission(PERMISSIONS.SYSTEM_SETTINGS)),
) -> DemoAdminResponse:
    return DemoAdminResponse()
