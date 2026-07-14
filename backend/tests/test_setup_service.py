from pathlib import Path

import httpx
import pytest

from app.config.settings import AppSettings
from app.services.setup_service import SetupService


def makeSettings() -> AppSettings:
    return AppSettings(
        appName="AI Video Pipeline Studio",
        environment="test",
        logLevel="INFO",
        appDataDirectory=Path("data"),
        promptConfigPath=Path("prompts.json"),
        ollamaBaseUrl="http://ollama.test",
        ollamaModel="llama3.2",
        openaiApiKey="secret",
        openaiBaseUrl="https://api.openai.com",
        openaiModel="gpt-5-mini",
        aiRequestTimeoutSeconds=120,
        aiMaxAttempts=3,
        aiRetryInitialDelaySeconds=1,
        aiRetryMaxDelaySeconds=8,
        localMediaLibraryPaths=(),
        localMediaMaxScannedFiles=50000,
        mediaCacheMaxFileSizeBytes=1024,
        mediaDownloadTimeoutSeconds=30,
        mediaCacheMaxTotalSizeBytes=1024,
        mediaCacheMaxAgeDays=30,
        ffmpegPath=None,
        mediaFingerprintTimeoutSeconds=120,
        mediaDedupThresholdsPath=Path("thresholds.json"),
        pexelsApiKey=None,
        pexelsBaseUrl="https://api.pexels.com",
        dvidsApiKey=None,
        dvidsBaseUrl="https://api.dvidshub.net",
        dvidsVideoQuality="highest",
        dvidsVideoMaxFileSizeBytes=0,
        dvidsMaxAttempts=3,
        dvidsRetryInitialDelaySeconds=1,
        dvidsRetryMaxDelaySeconds=60,
        dvidsRetryJitterRatio=0.25,
        dvidsSearchCacheTtlSeconds=86400,
        dvidsAssetCacheTtlSeconds=3600,
        dvidsNegativeCacheTtlSeconds=300,
        pixabayApiKey=None,
        pixabayBaseUrl="https://pixabay.com",
        pixabayMaxAttempts=3,
        pixabayRetryInitialDelaySeconds=1,
        pixabayRetryMaxDelaySeconds=60,
        pixabayRetryJitterRatio=0.25,
        pixabaySearchCacheTtlSeconds=86400,
        wikimediaCommonsBaseUrl="https://commons.wikimedia.org",
        wikimediaUserAgent=None,
        wikimediaMaxAttempts=3,
        wikimediaRetryInitialDelaySeconds=1,
        wikimediaRetryMaxDelaySeconds=60,
        wikimediaRetryJitterRatio=0.25,
        wikimediaSearchCacheTtlSeconds=86400,
    )


@pytest.mark.anyio
async def testSetupServiceReportsOllamaReadyWithoutReturningSecrets() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/tags"
        return httpx.Response(200, json={"models": [{"name": "llama3.2:latest"}]})

    service = SetupService(makeSettings(), transport=httpx.MockTransport(handler))

    status = await service.getStatus()
    data = status.toDictionary()

    assert data["providers"][0]["status"] == "ready"
    assert data["providers"][1]["status"] == "configured"
    assert data["apiKeys"][0]["configured"] is True
    assert "secret" not in str(data)
