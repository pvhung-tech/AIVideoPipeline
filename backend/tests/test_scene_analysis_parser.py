import pytest

from app.ai.errors import AIError
from app.ai.scene_analysis_parser import SceneAnalysisParser


def testSceneAnalysisParserNormalizesAndDeduplicatesKeywords() -> None:
    parsed = SceneAnalysisParser().parse(
        '{"description":" City skyline ","category":" location ",'
        '"keywords":["city skyline","City Skyline","sunrise"]}'
    )

    assert parsed.description == "City skyline"
    assert parsed.category == "location"
    assert parsed.keywords == ("city skyline", "sunrise")


@pytest.mark.parametrize(
    "content",
    [
        "not json",
        '{"description":"Text","category":"location","keywords":[]}',
        '{"description":"Text","category":"location","keywords":["x"],"extra":1}',
    ],
)
def testSceneAnalysisParserRejectsInvalidResponses(content: str) -> None:
    with pytest.raises(AIError) as error:
        SceneAnalysisParser().parse(content)

    assert error.value.code == "INVALID_AI_RESPONSE"
