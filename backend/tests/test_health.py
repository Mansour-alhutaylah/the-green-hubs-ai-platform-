from httpx import AsyncClient


async def test_health(client: AsyncClient) -> None:
    response = await client.get("/api/v1/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"


async def test_health_db_reports_a_status(client: AsyncClient) -> None:
    """Should return 200 (reachable) or 503 (unreachable) -- never crash."""
    response = await client.get("/api/v1/health/db")
    assert response.status_code in (200, 503)
