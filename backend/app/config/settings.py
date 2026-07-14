import os
import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class AppSettings:
    appName: str
    environment: str
    logLevel: str
    appDataDirectory: Path
    promptConfigPath: Path
    ollamaBaseUrl: str
    ollamaModel: str
    openaiApiKey: str | None
    openaiBaseUrl: str
    openaiModel: str
    aiRequestTimeoutSeconds: float
    aiMaxAttempts: int
    aiRetryInitialDelaySeconds: float
    aiRetryMaxDelaySeconds: float
    localMediaLibraryPaths: tuple[Path, ...]
    localMediaMaxScannedFiles: int
    mediaCacheMaxFileSizeBytes: int
    mediaDownloadTimeoutSeconds: float
    mediaCacheMaxTotalSizeBytes: int
    mediaCacheMaxAgeDays: int
    ffmpegPath: str | None
    mediaFingerprintTimeoutSeconds: float
    mediaDedupThresholdsPath: Path
    pexelsApiKey: str | None
    pexelsBaseUrl: str
    dvidsApiKey: str | None
    dvidsBaseUrl: str
    dvidsVideoQuality: str
    dvidsVideoMaxFileSizeBytes: int
    dvidsMaxAttempts: int
    dvidsRetryInitialDelaySeconds: float
    dvidsRetryMaxDelaySeconds: float
    dvidsRetryJitterRatio: float
    dvidsSearchCacheTtlSeconds: int
    dvidsAssetCacheTtlSeconds: int
    dvidsNegativeCacheTtlSeconds: int
    pixabayApiKey: str | None
    pixabayBaseUrl: str
    pixabayMaxAttempts: int
    pixabayRetryInitialDelaySeconds: float
    pixabayRetryMaxDelaySeconds: float
    pixabayRetryJitterRatio: float
    pixabaySearchCacheTtlSeconds: int
    wikimediaCommonsBaseUrl: str
    wikimediaUserAgent: str | None
    wikimediaMaxAttempts: int
    wikimediaRetryInitialDelaySeconds: float
    wikimediaRetryMaxDelaySeconds: float
    wikimediaRetryJitterRatio: float
    wikimediaSearchCacheTtlSeconds: int


def getDefaultAppDataDirectory() -> Path:
    localAppData = os.getenv("LOCALAPPDATA")
    if localAppData:
        return Path(localAppData) / "AI Video Pipeline Studio"

    dataHome = os.getenv("XDG_DATA_HOME")
    if dataHome:
        return Path(dataHome) / "ai-video-pipeline-studio"

    return Path.home() / ".local" / "share" / "ai-video-pipeline-studio"


def getDefaultPromptConfigPath() -> Path:
    bundleDirectory = getattr(sys, "_MEIPASS", None)
    if bundleDirectory:
        return Path(str(bundleDirectory)) / "configs" / "prompts.json"
    return Path(__file__).resolve().parents[3] / "configs" / "prompts.json"


def getDefaultMediaDedupThresholdsPath() -> Path:
    return getDefaultPromptConfigPath().with_name("media_dedup_thresholds.json")


def getSettings() -> AppSettings:
    aiRequestTimeoutSeconds = float(os.getenv("AI_REQUEST_TIMEOUT_SECONDS", "120"))
    if aiRequestTimeoutSeconds <= 0:
        raise ValueError("AI_REQUEST_TIMEOUT_SECONDS must be positive.")
    aiMaxAttempts = int(os.getenv("AI_MAX_ATTEMPTS", "3"))
    aiRetryInitialDelaySeconds = float(os.getenv("AI_RETRY_INITIAL_DELAY_SECONDS", "1"))
    aiRetryMaxDelaySeconds = float(os.getenv("AI_RETRY_MAX_DELAY_SECONDS", "8"))
    if aiMaxAttempts < 1:
        raise ValueError("AI_MAX_ATTEMPTS must be positive.")
    if (
        aiRetryInitialDelaySeconds < 0
        or aiRetryMaxDelaySeconds < aiRetryInitialDelaySeconds
    ):
        raise ValueError("AI retry delays are invalid.")
    openaiApiKey = os.getenv("OPENAI_API_KEY")
    mediaLibraryValue = os.getenv("LOCAL_MEDIA_LIBRARY_PATHS", "")
    localMediaLibraryPaths = tuple(
        Path(value.strip())
        for value in mediaLibraryValue.split(os.pathsep)
        if value.strip()
    )
    localMediaMaxScannedFiles = int(os.getenv("LOCAL_MEDIA_MAX_SCANNED_FILES", "50000"))
    if localMediaMaxScannedFiles < 1:
        raise ValueError("LOCAL_MEDIA_MAX_SCANNED_FILES must be positive.")
    mediaCacheMaxFileSizeBytes = int(
        os.getenv("MEDIA_CACHE_MAX_FILE_SIZE_BYTES", str(2 * 1024 * 1024 * 1024))
    )
    mediaDownloadTimeoutSeconds = float(
        os.getenv("MEDIA_DOWNLOAD_TIMEOUT_SECONDS", "300")
    )
    if mediaCacheMaxFileSizeBytes < 1 or mediaDownloadTimeoutSeconds <= 0:
        raise ValueError("Media cache settings must be positive.")
    mediaCacheMaxTotalSizeBytes = int(
        os.getenv("MEDIA_CACHE_MAX_TOTAL_SIZE_BYTES", str(10 * 1024 * 1024 * 1024))
    )
    mediaCacheMaxAgeDays = int(os.getenv("MEDIA_CACHE_MAX_AGE_DAYS", "30"))
    if mediaCacheMaxTotalSizeBytes < 0 or mediaCacheMaxAgeDays < 0:
        raise ValueError("Media cache cleanup settings cannot be negative.")
    ffmpegPath = os.getenv("FFMPEG_PATH")
    mediaFingerprintTimeoutSeconds = float(
        os.getenv("MEDIA_FINGERPRINT_TIMEOUT_SECONDS", "120")
    )
    if mediaFingerprintTimeoutSeconds <= 0:
        raise ValueError("MEDIA_FINGERPRINT_TIMEOUT_SECONDS must be positive.")
    pexelsApiKey = os.getenv("PEXELS_API_KEY")
    dvidsApiKey = os.getenv("DVIDS_API_KEY")
    dvidsVideoQuality = os.getenv("DVIDS_VIDEO_QUALITY", "highest").strip().lower()
    dvidsVideoMaxFileSizeBytes = int(os.getenv("DVIDS_VIDEO_MAX_FILE_SIZE_BYTES", "0"))
    if dvidsVideoQuality not in {"highest", "1080p", "720p"}:
        raise ValueError("DVIDS_VIDEO_QUALITY must be highest, 1080p, or 720p.")
    if dvidsVideoMaxFileSizeBytes < 0:
        raise ValueError("DVIDS_VIDEO_MAX_FILE_SIZE_BYTES cannot be negative.")
    dvidsMaxAttempts = int(os.getenv("DVIDS_MAX_ATTEMPTS", "3"))
    dvidsRetryInitialDelaySeconds = float(
        os.getenv("DVIDS_RETRY_INITIAL_DELAY_SECONDS", "1")
    )
    dvidsRetryMaxDelaySeconds = float(os.getenv("DVIDS_RETRY_MAX_DELAY_SECONDS", "60"))
    dvidsRetryJitterRatio = float(os.getenv("DVIDS_RETRY_JITTER_RATIO", "0.25"))
    dvidsSearchCacheTtlSeconds = int(
        os.getenv("DVIDS_SEARCH_CACHE_TTL_SECONDS", "86400")
    )
    dvidsAssetCacheTtlSeconds = int(os.getenv("DVIDS_ASSET_CACHE_TTL_SECONDS", "3600"))
    dvidsNegativeCacheTtlSeconds = int(
        os.getenv("DVIDS_NEGATIVE_CACHE_TTL_SECONDS", "300")
    )
    if (
        dvidsMaxAttempts < 1
        or dvidsRetryInitialDelaySeconds < 0
        or dvidsRetryMaxDelaySeconds < dvidsRetryInitialDelaySeconds
        or dvidsRetryJitterRatio < 0
        or dvidsRetryJitterRatio > 1
        or dvidsSearchCacheTtlSeconds < 1
        or dvidsAssetCacheTtlSeconds < 1
        or dvidsAssetCacheTtlSeconds > dvidsSearchCacheTtlSeconds
        or dvidsNegativeCacheTtlSeconds < 1
        or dvidsNegativeCacheTtlSeconds > dvidsAssetCacheTtlSeconds
    ):
        raise ValueError("DVIDS retry and cache settings are invalid.")
    pixabayApiKey = os.getenv("PIXABAY_API_KEY")
    pixabayMaxAttempts = int(os.getenv("PIXABAY_MAX_ATTEMPTS", "3"))
    pixabayRetryInitialDelaySeconds = float(
        os.getenv("PIXABAY_RETRY_INITIAL_DELAY_SECONDS", "1")
    )
    pixabayRetryMaxDelaySeconds = float(
        os.getenv("PIXABAY_RETRY_MAX_DELAY_SECONDS", "60")
    )
    pixabayRetryJitterRatio = float(os.getenv("PIXABAY_RETRY_JITTER_RATIO", "0.25"))
    pixabaySearchCacheTtlSeconds = int(
        os.getenv("PIXABAY_SEARCH_CACHE_TTL_SECONDS", "86400")
    )
    if (
        pixabayMaxAttempts < 1
        or pixabayRetryInitialDelaySeconds < 0
        or pixabayRetryMaxDelaySeconds < pixabayRetryInitialDelaySeconds
        or pixabayRetryJitterRatio < 0
        or pixabayRetryJitterRatio > 1
        or pixabaySearchCacheTtlSeconds < 1
    ):
        raise ValueError("Pixabay retry and cache settings are invalid.")
    wikimediaMaxAttempts = int(os.getenv("WIKIMEDIA_MAX_ATTEMPTS", "3"))
    wikimediaRetryInitialDelaySeconds = float(
        os.getenv("WIKIMEDIA_RETRY_INITIAL_DELAY_SECONDS", "1")
    )
    wikimediaRetryMaxDelaySeconds = float(
        os.getenv("WIKIMEDIA_RETRY_MAX_DELAY_SECONDS", "60")
    )
    wikimediaRetryJitterRatio = float(os.getenv("WIKIMEDIA_RETRY_JITTER_RATIO", "0.25"))
    wikimediaSearchCacheTtlSeconds = int(
        os.getenv("WIKIMEDIA_SEARCH_CACHE_TTL_SECONDS", "86400")
    )
    if (
        wikimediaMaxAttempts < 1
        or wikimediaRetryInitialDelaySeconds < 0
        or wikimediaRetryMaxDelaySeconds < wikimediaRetryInitialDelaySeconds
        or wikimediaRetryJitterRatio < 0
        or wikimediaRetryJitterRatio > 1
        or wikimediaSearchCacheTtlSeconds < 1
    ):
        raise ValueError("Wikimedia retry and cache settings are invalid.")
    return AppSettings(
        appName=os.getenv("APP_NAME", "AI Video Pipeline Studio"),
        environment=os.getenv("APP_ENV", "development"),
        logLevel=os.getenv("APP_LOG_LEVEL", "INFO"),
        appDataDirectory=Path(
            os.getenv("APP_DATA_DIR", str(getDefaultAppDataDirectory()))
        ),
        promptConfigPath=Path(
            os.getenv("PROMPT_CONFIG_PATH", str(getDefaultPromptConfigPath()))
        ),
        ollamaBaseUrl=os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434"),
        ollamaModel=os.getenv("OLLAMA_MODEL", "llama3.2"),
        openaiApiKey=openaiApiKey.strip() if openaiApiKey else None,
        openaiBaseUrl=os.getenv("OPENAI_BASE_URL", "https://api.openai.com"),
        openaiModel=os.getenv("OPENAI_MODEL", "gpt-5-mini"),
        aiRequestTimeoutSeconds=aiRequestTimeoutSeconds,
        aiMaxAttempts=aiMaxAttempts,
        aiRetryInitialDelaySeconds=aiRetryInitialDelaySeconds,
        aiRetryMaxDelaySeconds=aiRetryMaxDelaySeconds,
        localMediaLibraryPaths=localMediaLibraryPaths,
        localMediaMaxScannedFiles=localMediaMaxScannedFiles,
        mediaCacheMaxFileSizeBytes=mediaCacheMaxFileSizeBytes,
        mediaDownloadTimeoutSeconds=mediaDownloadTimeoutSeconds,
        mediaCacheMaxTotalSizeBytes=mediaCacheMaxTotalSizeBytes,
        mediaCacheMaxAgeDays=mediaCacheMaxAgeDays,
        ffmpegPath=ffmpegPath.strip() if ffmpegPath else None,
        mediaFingerprintTimeoutSeconds=mediaFingerprintTimeoutSeconds,
        mediaDedupThresholdsPath=Path(
            value
            if (value := os.getenv("MEDIA_DEDUP_THRESHOLDS_PATH"))
            else getDefaultMediaDedupThresholdsPath()
        ),
        pexelsApiKey=pexelsApiKey.strip() if pexelsApiKey else None,
        pexelsBaseUrl=os.getenv("PEXELS_BASE_URL", "https://api.pexels.com"),
        dvidsApiKey=dvidsApiKey.strip() if dvidsApiKey else None,
        dvidsBaseUrl=os.getenv("DVIDS_BASE_URL", "https://api.dvidshub.net"),
        dvidsVideoQuality=dvidsVideoQuality,
        dvidsVideoMaxFileSizeBytes=dvidsVideoMaxFileSizeBytes,
        dvidsMaxAttempts=dvidsMaxAttempts,
        dvidsRetryInitialDelaySeconds=dvidsRetryInitialDelaySeconds,
        dvidsRetryMaxDelaySeconds=dvidsRetryMaxDelaySeconds,
        dvidsRetryJitterRatio=dvidsRetryJitterRatio,
        dvidsSearchCacheTtlSeconds=dvidsSearchCacheTtlSeconds,
        dvidsAssetCacheTtlSeconds=dvidsAssetCacheTtlSeconds,
        dvidsNegativeCacheTtlSeconds=dvidsNegativeCacheTtlSeconds,
        pixabayApiKey=pixabayApiKey.strip() if pixabayApiKey else None,
        pixabayBaseUrl=os.getenv("PIXABAY_BASE_URL", "https://pixabay.com"),
        pixabayMaxAttempts=pixabayMaxAttempts,
        pixabayRetryInitialDelaySeconds=pixabayRetryInitialDelaySeconds,
        pixabayRetryMaxDelaySeconds=pixabayRetryMaxDelaySeconds,
        pixabayRetryJitterRatio=pixabayRetryJitterRatio,
        pixabaySearchCacheTtlSeconds=pixabaySearchCacheTtlSeconds,
        wikimediaCommonsBaseUrl=os.getenv(
            "WIKIMEDIA_COMMONS_BASE_URL", "https://commons.wikimedia.org"
        ),
        wikimediaUserAgent=(
            value.strip() if (value := os.getenv("WIKIMEDIA_USER_AGENT")) else None
        ),
        wikimediaMaxAttempts=wikimediaMaxAttempts,
        wikimediaRetryInitialDelaySeconds=wikimediaRetryInitialDelaySeconds,
        wikimediaRetryMaxDelaySeconds=wikimediaRetryMaxDelaySeconds,
        wikimediaRetryJitterRatio=wikimediaRetryJitterRatio,
        wikimediaSearchCacheTtlSeconds=wikimediaSearchCacheTtlSeconds,
    )
