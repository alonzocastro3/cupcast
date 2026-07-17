from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from app.dependencies import CacheDep, PaginationDep, SessionDep
from app.repositories.team import TeamRepository
from app.schemas import Page
from app.schemas.team import TeamRead
from app.services.team import TeamService

router = APIRouter(prefix="/api/v1/teams", tags=["teams"])


def _service(session: SessionDep, cache: CacheDep) -> TeamService:
    return TeamService(TeamRepository(session), cache)


ServiceDep = Annotated[TeamService, Depends(_service)]


@router.get("", response_model=Page[TeamRead])
async def list_teams(pagination: PaginationDep, service: ServiceDep) -> dict:
    teams, total = await service.list_teams(pagination.limit, pagination.offset)
    return {
        "items": teams,
        "total": total,
        "limit": pagination.limit,
        "offset": pagination.offset,
    }


@router.get("/{team_id}", response_model=TeamRead)
async def get_team(team_id: int, service: ServiceDep) -> TeamRead:
    team = await service.get_team(team_id)
    if team is None:
        raise HTTPException(status_code=404, detail=f"Team {team_id} not found")
    return team  # type: ignore[return-value]
