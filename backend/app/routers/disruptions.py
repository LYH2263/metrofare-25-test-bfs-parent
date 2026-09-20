from fastapi import APIRouter, HTTPException

from app.repositories.disruptions import DisruptionError
from app.schemas.disruption import DisruptionRequest
from app.services.metro_service import MetroService

router = APIRouter(tags=["disruptions"])


@router.get("/disruptions")
def list_disruptions():
    with MetroService() as s:
        return {"items": s.disruptions()}


@router.post("/disruptions", status_code=201)
def create_disruption(body: DisruptionRequest):
    with MetroService() as s:
        try:
            return s.create_disruption(body.a, body.b, body.reason)
        except DisruptionError as e:
            raise HTTPException(status_code=400, detail=str(e))


@router.post("/disruptions/{disruption_id}/release")
def release_disruption(disruption_id: int):
    with MetroService() as s:
        row = s.release_disruption(disruption_id)
        if row is None:
            raise HTTPException(status_code=404, detail="中断记录不存在")
        return row
