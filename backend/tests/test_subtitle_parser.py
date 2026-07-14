import pytest

from app.pipeline.script_errors import ScriptError
from app.pipeline.subtitle_parser import SubtitleParser


def testSubtitleParserParsesMultilineCues() -> None:
    content = """1
00:00:01,250 --> 00:00:03,500
First line
Second line

2
00:00:04,000 --> 00:00:05,125 position:50%
Next cue
"""

    cues = SubtitleParser().parse(content)

    assert len(cues) == 2
    assert cues[0].startMilliseconds == 1250
    assert cues[0].endMilliseconds == 3500
    assert cues[0].text == "First line\nSecond line"
    assert cues[1].text == "Next cue"


@pytest.mark.parametrize(
    ("content", "errorCode"),
    [
        ("", "EMPTY_SCRIPT"),
        ("2\n00:00:00,000 --> 00:00:01,000\nText", "INVALID_SRT_INDEX"),
        ("1\ninvalid\nText", "INVALID_SRT_TIMESTAMP"),
        (
            "1\n00:00:02,000 --> 00:00:01,000\nText",
            "INVALID_SRT_DURATION",
        ),
        (
            "1\n00:00:02,000 --> 00:00:03,000\nFirst\n\n"
            "2\n00:00:01,000 --> 00:00:02,000\nSecond",
            "INVALID_SRT_ORDER",
        ),
    ],
)
def testSubtitleParserRejectsInvalidContent(content: str, errorCode: str) -> None:
    with pytest.raises(ScriptError) as error:
        SubtitleParser().parse(content)

    assert error.value.code == errorCode
