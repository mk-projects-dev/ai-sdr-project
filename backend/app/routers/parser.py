from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status

from app.auth import get_current_admin
from app.models import Admin
from app.parser_runtime import mark_finished, mark_started, snapshot
from app.schemas_parser import ParserRunRequest, ParserRunResponse, ParserStatusResponse
from app.services.scraper_service import run_maps_parser_job

router = APIRouter(tags=["parser"])


async def _run_maps_parser_guarded(location: str, keyword: str, limit: int) -> None:
    created = 0
    try:
        created = await run_maps_parser_job(location, keyword, limit)
    finally:
        mark_finished(created)


@router.get("/parser/status", response_model=ParserStatusResponse)
async def parser_status(_: Admin = Depends(get_current_admin)) -> ParserStatusResponse:
    busy, finished_at, created = snapshot()
    return ParserStatusResponse(
        busy=busy,
        last_finished_at=finished_at,
        last_created_count=created,
    )


@router.post("/parser/run", response_model=ParserRunResponse)
async def start_parser(
    body: ParserRunRequest,
    background_tasks: BackgroundTasks,
    _: Admin = Depends(get_current_admin),
) -> ParserRunResponse:
    if snapshot()[0]:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Parser already running",
        )
    started_at = mark_started()
    background_tasks.add_task(
        _run_maps_parser_guarded,
        body.location.strip(),
        body.keyword.strip(),
        body.limit,
    )
    return ParserRunResponse(started_at=started_at)
