from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from app.dependencies import PaginationDep, SessionDep
from app.enums import MatchStatus
from app.repositories.match import MatchRepository
from app.repositories.prediction import PredictionRepository
from app.schemas import Page
from app.schemas.match import MatchRead
from app.schemas.prediction import ModelPrediction, PredictionSummary
from app.services.match import MatchService
from app.services.model_prediction import ModelPredictionService
from app.services.prediction import PredictionService

router = APIRouter(prefix="/api/v1/matches", tags=["matches"])


def _match_service(session: SessionDep) -> MatchService:
    return MatchService(MatchRepository(session))


def _prediction_service(session: SessionDep) -> PredictionService:
    return PredictionService(MatchRepository(session), PredictionRepository(session))


def _model_prediction_service(session: SessionDep) -> ModelPredictionService:
    return ModelPredictionService(MatchRepository(session))


MatchServiceDep = Annotated[MatchService, Depends(_match_service)]
PredictionServiceDep = Annotated[PredictionService, Depends(_prediction_service)]
ModelPredictionServiceDep = Annotated[ModelPredictionService, Depends(_model_prediction_service)]


@router.get("", response_model=Page[MatchRead])
async def list_matches(
    pagination: PaginationDep,
    service: MatchServiceDep,
    status: MatchStatus | None = Query(None, description="Filter by match status"),
    stage: str | None = Query(None, description="Filter by stage (e.g. group_a, final)"),
    team_id: int | None = Query(None, description="Filter matches involving a team"),
) -> dict:
    matches, total = await service.list_matches(
        pagination.limit, pagination.offset, status, stage, team_id
    )
    return {
        "items": matches,
        "total": total,
        "limit": pagination.limit,
        "offset": pagination.offset,
    }


@router.get("/{match_id}", response_model=MatchRead)
async def get_match(match_id: int, service: MatchServiceDep) -> MatchRead:
    match = await service.get_match(match_id)
    if match is None:
        raise HTTPException(status_code=404, detail=f"Match {match_id} not found")
    return match  # type: ignore[return-value]


@router.get("/{match_id}/prediction-summary", response_model=PredictionSummary)
async def get_prediction_summary(
    match_id: int,
    service: PredictionServiceDep,
) -> PredictionSummary:
    summary = await service.get_summary(match_id)
    if summary is None:
        raise HTTPException(status_code=404, detail=f"Match {match_id} not found")
    return summary


@router.get("/{match_id}/model-prediction", response_model=ModelPrediction)
async def get_model_prediction(
    match_id: int,
    service: ModelPredictionServiceDep,
) -> ModelPrediction:
    prediction = await service.get_model_prediction(match_id)
    if prediction is None:
        raise HTTPException(status_code=404, detail=f"Match {match_id} not found")
    return prediction
