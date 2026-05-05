from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends

from app.auth import get_current_admin
from app.models import Admin
from app.schemas_parser import ParserRunRequest, ParserRunResponse
from app.services.scraper_service import run_maps_parser_job

router = APIRouter(tags=["parser"])


@router.post("/parser/run", response_model=ParserRunResponse)
async def start_parser(
    body: ParserRunRequest,
    background_tasks: BackgroundTasks,
    _: Admin = Depends(get_current_admin),
) -> ParserRunResponse:
    background_tasks.add_task(
        run_maps_parser_job,
        body.location.strip(),
        body.keyword.strip(),
        body.limit,
    )
    return ParserRunResponse()
