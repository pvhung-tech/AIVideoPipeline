import re
from string import Formatter

from app.ai.errors import AIError
from app.ai.prompt_models import PromptTemplate, RenderedPrompt
from app.repositories.prompt_repository import PromptRepository

PROMPT_ID_PATTERN = re.compile(r"^[a-z][a-z0-9_]*$")


class PromptManager:
    def __init__(self, repository: PromptRepository) -> None:
        templates = repository.loadTemplates()
        self.templates = self._indexTemplates(templates)

    def listTemplates(self) -> tuple[PromptTemplate, ...]:
        return tuple(self.templates[promptId] for promptId in sorted(self.templates))

    def getTemplate(self, promptId: str) -> PromptTemplate:
        normalizedId = promptId.strip().lower()
        template = self.templates.get(normalizedId)
        if template is None:
            raise AIError(
                "PROMPT_NOT_FOUND", f"Prompt template '{normalizedId}' was not found."
            )
        return template

    def render(self, promptId: str, variables: dict[str, str]) -> RenderedPrompt:
        template = self.getTemplate(promptId)
        requiredVariables = set(template.requiredVariables)
        providedVariables = set(variables)
        missingVariables = sorted(requiredVariables - providedVariables)
        unknownVariables = sorted(providedVariables - requiredVariables)
        if missingVariables or unknownVariables:
            details = self._formatVariableError(missingVariables, unknownVariables)
            raise AIError("INVALID_PROMPT_VARIABLES", details)

        systemPrompt = template.systemTemplate.format_map(variables)
        userPrompt = template.userTemplate.format_map(variables)
        return RenderedPrompt.create(template, systemPrompt, userPrompt)

    def _indexTemplates(
        self, templates: tuple[PromptTemplate, ...]
    ) -> dict[str, PromptTemplate]:
        if not templates:
            raise AIError("EMPTY_PROMPT_CONFIG", "At least one prompt is required.")
        indexedTemplates: dict[str, PromptTemplate] = {}
        for template in templates:
            self._validateTemplate(template)
            if template.id in indexedTemplates:
                raise AIError(
                    "DUPLICATE_PROMPT_ID",
                    f"Prompt template '{template.id}' is duplicated.",
                )
            indexedTemplates[template.id] = template
        return indexedTemplates

    def _validateTemplate(self, template: PromptTemplate) -> None:
        if not PROMPT_ID_PATTERN.fullmatch(template.id):
            raise AIError("INVALID_PROMPT_TEMPLATE", "Prompt ID is invalid.")
        if template.version < 1:
            raise AIError("INVALID_PROMPT_TEMPLATE", "Prompt version must be positive.")
        if not template.systemTemplate.strip() or not template.userTemplate.strip():
            raise AIError("INVALID_PROMPT_TEMPLATE", "Prompt text cannot be empty.")

        placeholders = self._extractPlaceholders(template)
        requiredVariables = set(template.requiredVariables)
        if len(requiredVariables) != len(template.requiredVariables):
            raise AIError("INVALID_PROMPT_TEMPLATE", "Prompt variables must be unique.")
        if placeholders != requiredVariables:
            raise AIError(
                "INVALID_PROMPT_TEMPLATE",
                "Prompt placeholders must match required variables.",
            )

    def _extractPlaceholders(self, template: PromptTemplate) -> set[str]:
        placeholders: set[str] = set()
        formatter = Formatter()
        for promptText in (template.systemTemplate, template.userTemplate):
            for _literal, fieldName, formatSpec, conversion in formatter.parse(
                promptText
            ):
                if fieldName is None:
                    continue
                if not fieldName.isidentifier() or formatSpec or conversion:
                    raise AIError(
                        "INVALID_PROMPT_TEMPLATE",
                        "Prompt placeholders must be simple variable names.",
                    )
                placeholders.add(fieldName)
        return placeholders

    def _formatVariableError(
        self, missingVariables: list[str], unknownVariables: list[str]
    ) -> str:
        details: list[str] = []
        if missingVariables:
            details.append(f"Missing variables: {', '.join(missingVariables)}.")
        if unknownVariables:
            details.append(f"Unknown variables: {', '.join(unknownVariables)}.")
        return " ".join(details)
