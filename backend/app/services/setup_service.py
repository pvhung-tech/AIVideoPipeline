from dataclasses import dataclass
from typing import Any

import httpx

from app.config.settings import AppSettings


@dataclass(frozen=True)
class SetupCheck:
    id: str
    label: str
    status: str
    configured: bool
    message: str
    hint: str
    envVar: str | None = None
    valuePreview: str | None = None

    def toDictionary(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "label": self.label,
            "status": self.status,
            "configured": self.configured,
            "message": self.message,
            "hint": self.hint,
            "envVar": self.envVar,
            "valuePreview": self.valuePreview,
        }


@dataclass(frozen=True)
class SetupStatus:
    providers: tuple[SetupCheck, ...]
    apiKeys: tuple[SetupCheck, ...]
    tools: tuple[SetupCheck, ...]

    def toDictionary(self) -> dict[str, Any]:
        return {
            "providers": [item.toDictionary() for item in self.providers],
            "apiKeys": [item.toDictionary() for item in self.apiKeys],
            "tools": [item.toDictionary() for item in self.tools],
        }


class SetupService:
    def __init__(
        self,
        settings: AppSettings,
        ollamaTimeoutSeconds: float = 2.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.settings = settings
        self.ollamaTimeoutSeconds = ollamaTimeoutSeconds
        self.transport = transport

    async def getStatus(self) -> SetupStatus:
        ollamaStatus = await self._checkOllama()
        openaiStatus = self._configuredProvider(
            providerId="openai",
            label="OpenAI",
            configured=self.settings.openaiApiKey is not None,
            model=self.settings.openaiModel,
            envVar="OPENAI_API_KEY",
        )
        geminiStatus = SetupCheck(
            id="gemini",
            label="Gemini",
            status="unsupported",
            configured=False,
            message="Gemini provider is not wired into this build yet.",
            hint=(
                "Use Ollama or OpenAI for Phase 7, or add the Gemini adapter "
                "before enabling this provider."
            ),
            envVar="GEMINI_API_KEY",
        )
        return SetupStatus(
            providers=(ollamaStatus, openaiStatus, geminiStatus),
            apiKeys=self._apiKeyChecks(),
            tools=self._toolChecks(),
        )

    async def _checkOllama(self) -> SetupCheck:
        baseUrl = self.settings.ollamaBaseUrl.rstrip("/")
        try:
            async with httpx.AsyncClient(
                base_url=baseUrl,
                timeout=self.ollamaTimeoutSeconds,
                transport=self.transport,
            ) as client:
                response = await client.get("/api/tags")
                response.raise_for_status()
                data: Any = response.json()
        except (httpx.HTTPError, ValueError):
            return SetupCheck(
                id="ollama",
                label="Ollama",
                status="unavailable",
                configured=True,
                message="Ollama is configured but not reachable.",
                hint=(
                    "Start Ollama, then run `ollama pull {model}` if the "
                    "model is missing."
                ),
                envVar="OLLAMA_BASE_URL",
                valuePreview=baseUrl,
            )
        models = self._ollamaModelNames(data)
        if self.settings.ollamaModel not in models:
            return SetupCheck(
                id="ollama",
                label="Ollama",
                status="missing_model",
                configured=True,
                message=(
                    f"Ollama is running, but {self.settings.ollamaModel} "
                    "is not installed."
                ),
                hint=(
                    f"Run `ollama pull {self.settings.ollamaModel}` and "
                    "refresh setup."
                ),
                envVar="OLLAMA_MODEL",
                valuePreview=self.settings.ollamaModel,
            )
        return SetupCheck(
            id="ollama",
            label="Ollama",
            status="ready",
            configured=True,
            message=f"Ollama is ready with {self.settings.ollamaModel}.",
            hint="You can use Ollama for local scene analysis.",
            envVar="OLLAMA_MODEL",
            valuePreview=self.settings.ollamaModel,
        )

    def _configuredProvider(
        self,
        providerId: str,
        label: str,
        configured: bool,
        model: str,
        envVar: str,
    ) -> SetupCheck:
        if configured:
            return SetupCheck(
                id=providerId,
                label=label,
                status="configured",
                configured=True,
                message=f"{label} key is configured. Model: {model}.",
                hint=(
                    f"{label} live requests can run when the machine has "
                    "network access."
                ),
                envVar=envVar,
                valuePreview=model,
            )
        return SetupCheck(
            id=providerId,
            label=label,
            status="missing_key",
            configured=False,
            message=f"{label} key is not configured.",
            hint=(
                f"Set {envVar} in the environment, restart the desktop app, "
                "then refresh setup."
            ),
            envVar=envVar,
            valuePreview=model,
        )

    def _apiKeyChecks(self) -> tuple[SetupCheck, ...]:
        return (
            self._keyCheck(
                "openai",
                "OpenAI API key",
                self.settings.openaiApiKey,
                "OPENAI_API_KEY",
            ),
            self._keyCheck(
                "pexels",
                "Pexels API key",
                self.settings.pexelsApiKey,
                "PEXELS_API_KEY",
            ),
            self._keyCheck(
                "pixabay",
                "Pixabay API key",
                self.settings.pixabayApiKey,
                "PIXABAY_API_KEY",
            ),
            self._keyCheck(
                "dvids",
                "DVIDS API key",
                self.settings.dvidsApiKey,
                "DVIDS_API_KEY",
            ),
        )

    def _keyCheck(
        self, checkId: str, label: str, value: str | None, envVar: str
    ) -> SetupCheck:
        configured = value is not None
        return SetupCheck(
            id=checkId,
            label=label,
            status="configured" if configured else "missing_key",
            configured=configured,
            message=f"{label} is {'configured' if configured else 'not configured'}.",
            hint=(
                "The value is loaded from the process environment and is "
                "never returned by this API."
                if configured
                else f"Set {envVar}, restart the app, then refresh setup."
            ),
            envVar=envVar,
        )

    def _toolChecks(self) -> tuple[SetupCheck, ...]:
        ffmpegConfigured = self.settings.ffmpegPath is not None
        return (
            SetupCheck(
                id="ffmpeg",
                label="FFmpeg / FFprobe",
                status="configured" if ffmpegConfigured else "path",
                configured=ffmpegConfigured,
                message=(
                    "Custom FFmpeg path is configured."
                    if ffmpegConfigured
                    else "FFmpeg will be resolved from PATH."
                ),
                hint=(
                    "Render preflight performs the final FFmpeg and FFprobe "
                    "availability check."
                ),
                envVar="FFMPEG_PATH",
                valuePreview=self.settings.ffmpegPath,
            ),
            SetupCheck(
                id="wikimedia-user-agent",
                label="Wikimedia User-Agent",
                status="configured" if self.settings.wikimediaUserAgent else "missing",
                configured=self.settings.wikimediaUserAgent is not None,
                message=(
                    "Wikimedia User-Agent is configured."
                    if self.settings.wikimediaUserAgent
                    else "Wikimedia User-Agent is missing."
                ),
                hint=(
                    "Set WIKIMEDIA_USER_AGENT with an app name and contact "
                    "email before live Wikimedia searches."
                ),
                envVar="WIKIMEDIA_USER_AGENT",
            ),
        )

    def _ollamaModelNames(self, data: Any) -> set[str]:
        if not isinstance(data, dict) or not isinstance(data.get("models"), list):
            return set()
        names: set[str] = set()
        for item in data["models"]:
            if isinstance(item, dict) and isinstance(item.get("name"), str):
                names.add(item["name"])
                names.add(item["name"].split(":", 1)[0])
        return names
