"""Shared auth helper for API integration tests."""

from __future__ import annotations

import os

import httpx

API_BASE = os.environ.get("API_BASE", "http://localhost:8000")
ADMIN_USER = os.environ.get("API_BOOTSTRAP_ADMIN_USERNAME", "admin")
ADMIN_PASS = os.environ.get("API_BOOTSTRAP_ADMIN_PASSWORD", "change_me_admin")


def login(
    client: httpx.Client,
    *,
    username: str = ADMIN_USER,
    password: str = ADMIN_PASS,
    base_url: str | None = None,
) -> str:
    path = "/api/v1/auth/login"
    existing = str(client.base_url or "").rstrip("/")
    root = (base_url or existing or API_BASE).rstrip("/")
    url = f"{root}{path}"
    resp = client.post(
        url,
        json={"username": username, "password": password},
    )
    assert resp.status_code == 200, resp.text
    token = resp.json()["access_token"]
    client.headers["Authorization"] = f"Bearer {token}"
    return token


def auth_client(base_url: str = API_BASE) -> httpx.Client:
    client = httpx.Client(base_url=base_url, timeout=30.0)
    login(client)
    return client
