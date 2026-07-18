from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.authorization import require_permission
from app.api.deps import get_graph_store_optional
from app.core.authorization import PERMISSIONS
from app.core.dependencies import get_db
from app.graph.base import GraphStore
from app.schemas.dashboard import DashboardResponse
from app.services.dashboard_service import DashboardService

router = APIRouter(tags=["dashboard"])


@router.get(
    "/dashboard",
    response_model=DashboardResponse,
)
async def get_dashboard(
    request: Request,
    session: AsyncSession = Depends(get_db),
    graph_store: GraphStore | None = Depends(get_graph_store_optional),
    _=Depends(require_permission(PERMISSIONS.DASHBOARD)),
) -> DashboardResponse:
    service = DashboardService(session=session, graph_store=graph_store)
    data = await service.get_dashboard()
    data.qdrant_connected = getattr(request.app.state, "qdrant_connected", False)
    data.db_connected = getattr(request.app.state, "db_connected", False)
    return data
