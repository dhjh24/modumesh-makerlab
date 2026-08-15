"""Admin/plugin control-plane endpoints require a valid admin API key.

Regression tests for the fail-closed admin auth: with no key configured the
endpoints must return 403 (not open), and a wrong key must also be rejected.
These tests hit the auth dependency only — they never touch the database
because ``require_admin`` rejects the request before the endpoint body runs.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

ADMIN_SIGN_URL = "/api/v1/admin/plugins/test-plugin/sign"
ADMIN_LIST_URL = "/api/v1/admin/plugins"
ADMIN_QUOTA_URL = "/api/v1/admin/plugins/test-plugin/quota"
PLUGIN_RESYNC_URL = "/api/v1/plugins/resync"
PLUGIN_ENABLE_URL = "/api/v1/plugins/test-plugin/versions/1.0.0/enable"
PLUGIN_DISABLE_URL = "/api/v1/plugins/test-plugin/versions/1.0.0/disable"


@pytest.mark.parametrize(
    "method, url",
    [
        ("POST", ADMIN_SIGN_URL),
        ("GET", ADMIN_LIST_URL),
        ("POST", ADMIN_QUOTA_URL),
        ("POST", PLUGIN_RESYNC_URL),
        ("POST", PLUGIN_ENABLE_URL),
        ("POST", PLUGIN_DISABLE_URL),
    ],
)
def test_control_plane_requires_admin_key(method: str, url: str) -> None:
    """No Authorization header → 403 (fail-closed, even with key unset)."""
    response = client.request(method, url)
    assert response.status_code == 403, f"{method} {url} should be 403"
    assert response.json()["detail"] == "Admin access required"


@pytest.mark.parametrize(
    "method, url",
    [
        ("POST", ADMIN_SIGN_URL),
        ("GET", ADMIN_LIST_URL),
        ("POST", ADMIN_QUOTA_URL),
        ("POST", PLUGIN_RESYNC_URL),
        ("POST", PLUGIN_ENABLE_URL),
        ("POST", PLUGIN_DISABLE_URL),
    ],
)
def test_control_plane_rejects_wrong_key(method: str, url: str) -> None:
    """A mismatched bearer key → 403."""
    response = client.request(method, url, headers={"Authorization": "Bearer wrong-key"})
    assert response.status_code == 403, f"{method} {url} should be 403"
