from fastapi.testclient import TestClient

from app.config.dependencies import getSetupService
from app.main import createApp


class FakeSetupService:
    async def getStatus(self) -> object:
        return self

    def toDictionary(self) -> dict[str, object]:
        return {
            "providers": [
                {
                    "id": "ollama",
                    "label": "Ollama",
                    "status": "ready",
                    "configured": True,
                    "message": "Ollama is ready.",
                    "hint": "Use local analysis.",
                    "envVar": "OLLAMA_MODEL",
                    "valuePreview": "llama3.2",
                }
            ],
            "apiKeys": [
                {
                    "id": "openai",
                    "label": "OpenAI API key",
                    "status": "configured",
                    "configured": True,
                    "message": "OpenAI API key is configured.",
                    "hint": "The value is never returned.",
                    "envVar": "OPENAI_API_KEY",
                    "valuePreview": None,
                }
            ],
            "tools": [],
        }


def testSetupStatusEndpointReturnsProviderReadiness() -> None:
    app = createApp()
    app.dependency_overrides[getSetupService] = FakeSetupService
    client = TestClient(app)

    response = client.get("/api/setup/status")

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["data"]["providers"][0]["id"] == "ollama"
    assert payload["data"]["providers"][0]["status"] == "ready"
    assert payload["data"]["apiKeys"][0]["envVar"] == "OPENAI_API_KEY"
