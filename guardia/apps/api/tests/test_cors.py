"""The Flutter app calls the API cross-origin with a Bearer token, never a cookie.

Regression coverage for the bug where a missing CORS policy made the browser's
preflight OPTIONS request fail with 405, so the real POST /auth/token was never sent.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.testclient import TestClient

from app.core.config import Settings


def _settings(**overrides: object) -> Settings:
    base: dict[str, object] = dict(
        db_host="db",
        db_name="guardia",
        db_user="guardia",
        db_password="x",
        jwt_secret="x" * 32,
    )
    base.update(overrides)
    return Settings(**base)


def _app_with_cors(settings: Settings) -> FastAPI:
    app = FastAPI()
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.post("/api/v1/auth/token")
    def token() -> dict[str, str]:
        return {}

    return app


def test_cors_origins_defaults_to_wildcard() -> None:
    assert _settings().cors_origin_list == ["*"]


def test_cors_origins_parses_comma_separated_list() -> None:
    settings = _settings(cors_origins="https://a.example, https://b.example")
    assert settings.cors_origin_list == ["https://a.example", "https://b.example"]


def test_preflight_for_auth_token_succeeds() -> None:
    with TestClient(_app_with_cors(_settings())) as client:
        response = client.options(
            "/api/v1/auth/token",
            headers={
                "Origin": "http://localhost:55353",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "content-type,authorization",
            },
        )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "*"


def test_preflight_rejects_origin_outside_configured_allowlist() -> None:
    settings = _settings(cors_origins="https://app.example.org")
    with TestClient(_app_with_cors(settings)) as client:
        response = client.options(
            "/api/v1/auth/token",
            headers={
                "Origin": "https://attacker.example",
                "Access-Control-Request-Method": "POST",
            },
        )
    assert "access-control-allow-origin" not in response.headers
