from app.pipeline.scene_parser import SceneParser
from app.pipeline.script_models import ScriptFormat, SubtitleCue


def testSceneParserSplitsTxtByParagraphs() -> None:
    scenes = SceneParser().parse(
        ScriptFormat.TXT,
        "First paragraph.\n\nSecond line one.\nSecond line two.\n",
        (),
    )

    assert [scene.id for scene in scenes] == ["scene-0001", "scene-0002"]
    assert scenes[1].text == "Second line one.\nSecond line two."
    assert scenes[0].startMilliseconds is None


def testSceneParserMapsSrtCuesWithTiming() -> None:
    cues = (
        SubtitleCue(1, 500, 1500, "First"),
        SubtitleCue(2, 1600, 3000, "Second"),
    )

    scenes = SceneParser().parse(ScriptFormat.SRT, "ignored", cues)

    assert len(scenes) == 2
    assert scenes[1].sourceCueIndexes == (2,)
    assert scenes[1].startMilliseconds == 1600
    assert scenes[1].endMilliseconds == 3000
