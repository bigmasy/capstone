from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models
from app.config import settings
from app.db import Base, engine, get_db
from app.matching import find_matches
from app.privacy import distance_band, fuzz_location
from app.schemas import MatchItem, ProfileCreate, ProfilePrivate, ProfilePublic

Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Partner matching API for adaptive sport",
    version="0.1.0",
    openapi_url="/api/v1/openapi.json",
    docs_url="/docs",
)


@app.exception_handler(RequestValidationError)
def validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """Return a 422 response without the input data.

    The default response includes an input field with the whole request body,
    including the exact coordinates. Only the error type, location and message
    are kept here.
    """
    detail = [
        {"type": err["type"], "loc": list(err["loc"]), "msg": err["msg"]} for err in exc.errors()
    ]
    return JSONResponse(status_code=422, content={"detail": detail})


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/v1/profiles", response_model=ProfilePrivate, response_model_by_alias=True, status_code=201)
def create_profile(payload: ProfileCreate, db: Session = Depends(get_db)) -> models.Profile:
    lat, lon = fuzz_location(payload.location.latitude, payload.location.longitude)
    profile = models.Profile(
        display_name=payload.display_name,
        district=payload.district,
        area_lat=lat,
        area_lon=lon,
        intensity=payload.intensity,
        is_visible=payload.is_visible,
        sports=[models.ProfileSport(sport=s.sport, level=s.level) for s in payload.sports],
        capabilities=[
            models.FunctionalCapability(category=c.category, level=c.level, equipment=c.equipment)
            for c in payload.capabilities
        ],
    )
    db.add(profile)
    db.commit()
    db.refresh(profile)
    return profile


@app.get("/api/v1/profiles/{profile_id}", response_model=ProfilePublic, response_model_by_alias=True)
def get_profile(profile_id: str, db: Session = Depends(get_db)) -> models.Profile:
    profile = db.get(models.Profile, profile_id)
    if profile is None:
        raise HTTPException(status_code=404, detail="Profile not found")
    return profile


@app.get(
    "/api/v1/profiles/{profile_id}/matches",
    response_model=list[MatchItem],
    response_model_by_alias=True,
)
def get_matches(
    profile_id: str,
    limit: int = Query(default=20, ge=1, le=settings.max_matches),
    db: Session = Depends(get_db),
) -> list[MatchItem]:
    me = db.get(models.Profile, profile_id)
    if me is None:
        raise HTTPException(status_code=404, detail="Profile not found")
    candidates = list(db.scalars(select(models.Profile).where(models.Profile.is_visible.is_(True))))
    matches = find_matches(me, candidates, limit)
    return [
        MatchItem(
            profile=ProfilePublic.model_validate(m.profile),
            score=m.score,
            distance=distance_band(m.distance_km),
        )
        for m in matches
    ]
