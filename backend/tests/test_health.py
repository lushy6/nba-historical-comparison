import asyncio

import httpx

from app.main import app


def test_health_reports_when_the_optional_dataset_is_missing() -> None:
    async def request_health() -> httpx.Response:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.get("/api/health")

    response = asyncio.run(request_health())

    assert response.status_code == 200
    assert response.json() == {
        "status": "dataset_missing",
        "database_path": "nba.sqlite",
        "tables": [],
        "message": "Place nba.sqlite in the project root to enable comparisons.",
    }
