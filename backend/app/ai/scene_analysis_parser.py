import json
from dataclasses import dataclass
from typing import Any

from app.ai.errors import AIError

SCENE_ANALYSIS_RESPONSE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "description": {"type": "string"},
        "category": {"type": "string"},
        "keywords": {
            "type": "array",
            "items": {"type": "string"},
            "minItems": 1,
            "maxItems": 12,
        },
    },
    "required": ["description", "category", "keywords"],
    "additionalProperties": False,
}


@dataclass(frozen=True)
class ParsedSceneAnalysis:
    description: str
    category: str
    keywords: tuple[str, ...]


class SceneAnalysisParser:
    def parse(self, content: str) -> ParsedSceneAnalysis:
        try:
            data: Any = json.loads(content)
        except json.JSONDecodeError as error:
            raise AIError(
                "INVALID_AI_RESPONSE", "The AI response is not valid JSON."
            ) from error
        if not isinstance(data, dict) or set(data) != {
            "description",
            "category",
            "keywords",
        }:
            raise AIError(
                "INVALID_AI_RESPONSE", "The AI response has an invalid schema."
            )

        description = self._validateText(data["description"], "description", 2000)
        category = self._validateText(data["category"], "category", 100)
        keywords = self._validateKeywords(data["keywords"])
        return ParsedSceneAnalysis(description, category, keywords)

    def _validateText(self, value: Any, fieldName: str, maxLength: int) -> str:
        if not isinstance(value, str) or not value.strip():
            raise AIError(
                "INVALID_AI_RESPONSE", f"AI {fieldName} must be non-empty text."
            )
        normalizedValue = value.strip()
        if len(normalizedValue) > maxLength:
            raise AIError(
                "INVALID_AI_RESPONSE", f"AI {fieldName} exceeds its size limit."
            )
        return normalizedValue

    def _validateKeywords(self, value: Any) -> tuple[str, ...]:
        if not isinstance(value, list) or not 1 <= len(value) <= 12:
            raise AIError(
                "INVALID_AI_RESPONSE", "AI keywords must contain 1 to 12 items."
            )
        keywords: list[str] = []
        seenKeywords: set[str] = set()
        for item in value:
            keyword = self._validateText(item, "keyword", 100)
            normalizedKeyword = keyword.casefold()
            if normalizedKeyword not in seenKeywords:
                keywords.append(keyword)
                seenKeywords.add(normalizedKeyword)
        if not keywords:
            raise AIError("INVALID_AI_RESPONSE", "AI keywords cannot be empty.")
        return tuple(keywords)
