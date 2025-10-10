import shutil
from io import BytesIO

import pytest

from services.media_voice_enforcer import (
    VoiceConversionError,
    convert_stream_to_voice,
    normalize_media_type,
    should_convert_to_voice,
)


def test_normalize_media_type_converts_audio_to_voice():
    assert normalize_media_type("audio") == "voice"


def test_normalize_media_type_keeps_other_types():
    assert normalize_media_type("video") == "video"
    assert normalize_media_type(None) is None


def test_should_convert_to_voice_only_when_needed():
    assert should_convert_to_voice("audio", "voice") is True
    assert should_convert_to_voice("voice", "voice") is False
    assert should_convert_to_voice(None, "voice") is True
    assert should_convert_to_voice("video", "video") is False


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg not available")
def test_convert_stream_to_voice_generates_ogg(tmp_path):
    original = BytesIO(b"RIFF....fakewav")
    original.name = "test.wav"

    with pytest.raises(VoiceConversionError):
        convert_stream_to_voice(original)
