"""Every route declares its response and either requires authentication or is listed as public."""

from fastapi import FastAPI, status
from fastapi.routing import APIRoute

from tests.conftest import make_settings

PUBLIC_ROUTES = {
    ("GET", "/health"),
    ("GET", "/ready"),
    ("GET", "/api/v1/taxonomy"),
    # Links to public articles, shown to every visitor of the landing page
    ("GET", "/api/v1/news"),
    ("POST", "/api/v1/auth/register"),
    ("POST", "/api/v1/auth/login"),
    # Opened from a mailbox, possibly on another device, so it takes no bearer token
    ("POST", "/api/v1/auth/verify-email"),
    # The person forgot the password, so there is no session; both answer without telling
    # whether the address exists
    ("POST", "/api/v1/auth/forgot-password"),
    ("POST", "/api/v1/auth/reset-password"),
}


def api_routes(app: FastAPI) -> list[APIRoute]:
    return [route for route in app.routes if isinstance(route, APIRoute)]


def test_every_route_declares_a_response_model_or_an_empty_204(app: FastAPI):
    for route in api_routes(app):
        if route.status_code == status.HTTP_204_NO_CONTENT:
            assert route.response_model is None, route.path
        else:
            assert route.response_model is not None, route.path


def test_every_route_requires_a_bearer_token_or_is_explicitly_public(app: FastAPI):
    operations = app.openapi()["paths"]
    seen_public = set()

    for route in api_routes(app):
        for method in route.methods:
            operation = operations[route.path][method.lower()]
            if (method, route.path) in PUBLIC_ROUTES:
                seen_public.add((method, route.path))
                assert "security" not in operation, (method, route.path)
            else:
                assert operation.get("security"), f"{method} {route.path} is not protected"

    assert seen_public == PUBLIC_ROUTES, "PUBLIC_ROUTES lists a route that does not exist"


def test_every_route_has_tags(app: FastAPI):
    for route in api_routes(app):
        assert route.tags, route.path


def test_documentation_and_schema_are_off_in_production():
    from app.main import create_app

    prod = create_app(
        make_settings(
            ENV="prod",
            JWT_SECRET="p" * 40,
            DB_URL="postgresql+asyncpg://u:p@db/app",
            MAIL_BACKEND="log",
        )
    )

    assert prod.docs_url is None
    assert prod.redoc_url is None
    assert prod.openapi_url is None
