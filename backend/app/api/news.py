"""The adaptive-sport digest for the landing page; public, like the page itself."""

from typing import Annotated

from fastapi import APIRouter, Query

from app.api.deps import NewsServiceDep
from app.schemas.news import NewsResponse

router = APIRouter(prefix="/news", tags=["news"])


@router.get("", response_model=NewsResponse)
async def get_news(
    service: NewsServiceDep,
    limit: Annotated[int, Query(ge=1, le=20, description="Items per column")] = 6,
) -> NewsResponse:
    """Return the newest collected items of each category.

    No sign-in is needed: the items are links to public articles of public sources, and the
    landing page shows them to every visitor. They are collected once a day by a separate
    worker, never while a visitor waits.

    :param service: News service.
    :param limit: Maximum number of items per category.
    :return: One column per category.
    """
    return NewsResponse.from_columns(await service.digest(limit))
