"""Reference lists of codes for building profile forms."""

from fastapi import APIRouter

from app.schemas.taxonomy import TaxonomyResponse

router = APIRouter(prefix="/taxonomy", tags=["taxonomy"])


@router.get("", response_model=TaxonomyResponse)
async def get_taxonomy() -> TaxonomyResponse:
    """Return the versioned code lists; public, since they hold no personal data.

    :return: Sports, capability categories, equipment rules, districts and ranges, as codes.
    """
    return TaxonomyResponse.current()
