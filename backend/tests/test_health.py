from fastapi.testclient import TestClient

from app.main import createApp


def testHealthEndpointReturnsStandardResponse() -> None:
    client = TestClient(createApp())

    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {
        "success": True,
        "data": {
            "appName": "AI Video Pipeline Studio",
            "environment": "development",
            "status": "ok",
        },
        "message": "Backend is healthy.",
        "error": None,
    }
