"""Integration tests for the FastAPI app."""

import pytest
from httpx import AsyncClient, ASGITransport
from sw_reviewer.app import app


@pytest.mark.asyncio
async def test_health_check():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_start_review_returns_202():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/reviews", json={
            "repo_url": "https://github.com/test/myrepo",
            "project_type": "web",
            "demo_url": "https://myapp.vercel.app",
            "requester": "testuser",
        })
    assert response.status_code == 202
    data = response.json()
    assert "review_id" in data
    assert data["status"] == "queued"


@pytest.mark.asyncio
async def test_get_status_not_found():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/reviews/nonexistent/status")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_cancel_not_found():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.delete("/reviews/nonexistent")
    assert response.status_code == 404
