from pathlib import Path

import pytest

from app.ai.errors import AIError
from app.ai.prompt_manager import PromptManager
from app.ai.prompt_models import PromptTemplate
from app.repositories.file_prompt_repository import FilePromptRepository


class FakePromptRepository:
    def __init__(self, templates: tuple[PromptTemplate, ...]) -> None:
        self.templates = templates

    def loadTemplates(self) -> tuple[PromptTemplate, ...]:
        return self.templates


def createTemplate() -> PromptTemplate:
    return PromptTemplate(
        id="scene_analysis",
        version=1,
        systemTemplate="Analyze in {language}.",
        userTemplate="Scene: {sceneText}",
        requiredVariables=("language", "sceneText"),
    )


def testPromptManagerRendersVersionedMessages() -> None:
    manager = PromptManager(FakePromptRepository((createTemplate(),)))

    prompt = manager.render(
        "SCENE_ANALYSIS",
        {"language": "Vietnamese", "sceneText": "A city at sunrise."},
    )

    assert prompt.templateId == "scene_analysis"
    assert prompt.templateVersion == 1
    assert prompt.messages[0].content == "Analyze in Vietnamese."
    assert prompt.messages[1].content == "Scene: A city at sunrise."


@pytest.mark.parametrize(
    ("variables", "expectedMessage"),
    [
        ({"language": "English"}, "Missing variables: sceneText."),
        (
            {"language": "English", "sceneText": "Text", "extra": "value"},
            "Unknown variables: extra.",
        ),
    ],
)
def testPromptManagerRejectsInvalidVariables(
    variables: dict[str, str], expectedMessage: str
) -> None:
    manager = PromptManager(FakePromptRepository((createTemplate(),)))

    with pytest.raises(AIError) as error:
        manager.render("scene_analysis", variables)

    assert error.value.code == "INVALID_PROMPT_VARIABLES"
    assert error.value.message == expectedMessage


def testPromptManagerRejectsUnsafePlaceholder() -> None:
    template = PromptTemplate(
        id="unsafe_prompt",
        version=1,
        systemTemplate="System",
        userTemplate="{scene.text}",
        requiredVariables=("scene.text",),
    )

    with pytest.raises(AIError) as error:
        PromptManager(FakePromptRepository((template,)))

    assert error.value.code == "INVALID_PROMPT_TEMPLATE"


def testDefaultPromptConfigurationLoads() -> None:
    configPath = Path(__file__).resolve().parents[2] / "configs" / "prompts.json"

    templates = FilePromptRepository(configPath).loadTemplates()
    manager = PromptManager(FakePromptRepository(templates))

    assert manager.listTemplates()[0].id == "scene_analysis"
