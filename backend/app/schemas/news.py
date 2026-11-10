"""Response models of the news route."""

from datetime import datetime

from pydantic import BaseModel

from app.domain.news import Category, NewsColumn


class NewsItemOut(BaseModel):
    """One item of the digest: what the page needs to link to the original article."""

    title: str
    url: str
    source: str
    published_at: datetime


class NewsColumnOut(BaseModel):
    """The newest items of one category."""

    id: Category
    items: list[NewsItemOut]


class NewsResponse(BaseModel):
    """The digest for the landing page, one column per category."""

    columns: list[NewsColumnOut]

    @classmethod
    def from_columns(cls, columns: list[NewsColumn]) -> "NewsResponse":
        """Build the response from the service result.

        :param columns: Columns read by the service.
        :return: The response model.
        """
        return cls(
            columns=[
                NewsColumnOut(
                    id=column.id,
                    items=[
                        NewsItemOut(
                            title=entry.title,
                            url=entry.url,
                            source=source,
                            published_at=entry.published_at,
                        )
                        for entry, source in column.items
                    ],
                )
                for column in columns
            ]
        )
