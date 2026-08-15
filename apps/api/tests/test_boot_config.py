"""Boot configuration tests (GM-12 D1.2 / D1.4).

Exercises the fail-closed datastore-secret validation and the API_ENV-gated
docs/OpenAPI exposure without booting a live stack. The lifespan's admin
check (GM-9) is deliberately NOT exercised here — TestClient without entering
lifespan never runs boot validation, matching the pattern in
test_admin_auth.py.
"""

from __future__ import annotations

import pytest

from app.config import validate_boot_secrets
from app.main import create_app


class TestValidateBootSecrets:
    def test_development_env_skips_validation(self) -> None:
        # Development is the escape hatch: default dev creds are fine locally.
        assert (
            validate_boot_secrets(
                api_env="development",
                postgres_password="change_me_in_production",
                minio_secret_key="change_me_in_production",
                redis_password="",
            )
            is None
        )

    def test_non_dev_with_default_postgres_password_refuses(self) -> None:
        with pytest.raises(RuntimeError, match="POSTGRES_PASSWORD"):
            validate_boot_secrets(
                api_env="production",
                postgres_password="change_me_in_production",
                minio_secret_key="a-strong-secret",
                redis_password="a-strong-secret",
            )

    def test_non_dev_with_empty_minio_secret_refuses(self) -> None:
        with pytest.raises(RuntimeError, match="MINIO_SECRET_KEY"):
            validate_boot_secrets(
                api_env="ci",
                postgres_password="a-strong-secret",
                minio_secret_key="",
                redis_password="a-strong-secret",
            )

    def test_non_dev_with_empty_redis_password_refuses(self) -> None:
        with pytest.raises(RuntimeError, match="REDIS_PASSWORD"):
            validate_boot_secrets(
                api_env="production",
                postgres_password="a-strong-secret",
                minio_secret_key="a-strong-secret",
                redis_password="",
            )

    def test_non_dev_reports_all_offenders(self) -> None:
        with pytest.raises(RuntimeError) as excinfo:
            validate_boot_secrets(
                api_env="production",
                postgres_password="change_me_in_production",
                minio_secret_key="",
                redis_password="",
            )
        msg = str(excinfo.value)
        assert "POSTGRES_PASSWORD" in msg
        assert "MINIO_SECRET_KEY" in msg
        assert "REDIS_PASSWORD" in msg

    def test_non_dev_with_all_strong_secrets_passes(self) -> None:
        assert (
            validate_boot_secrets(
                api_env="production",
                postgres_password="strong-pg-pass",
                minio_secret_key="strong-minio-pass",
                redis_password="strong-redis-pass",
            )
            is None
        )


class TestCreateAppDocsGating:
    def test_production_app_disables_docs(self) -> None:
        app = create_app(api_env="production")
        assert app.docs_url is None
        assert app.openapi_url is None
        assert app.redoc_url is None

    def test_ci_app_disables_docs(self) -> None:
        app = create_app(api_env="ci")
        assert app.docs_url is None
        assert app.openapi_url is None

    def test_development_app_enables_docs(self) -> None:
        app = create_app(api_env="development")
        assert app.docs_url == "/docs"
        assert app.openapi_url == "/openapi.json"

    def test_default_env_is_development(self) -> None:
        # Without API_ENV set, docs stay enabled (local dev ergonomics).
        app = create_app()
        assert app.docs_url == "/docs"
