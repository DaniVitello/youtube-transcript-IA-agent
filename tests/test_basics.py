from utils.files import sanitize_filename
from utils.url import extract_video_id


def test_extract_video_id():
    assert extract_video_id("https://www.youtube.com/watch?v=dQw4w9WgXcQ") == "dQw4w9WgXcQ"
    assert extract_video_id("https://youtu.be/dQw4w9WgXcQ") == "dQw4w9WgXcQ"
    assert extract_video_id("https://www.youtube.com/shorts/dQw4w9WgXcQ") == "dQw4w9WgXcQ"
    assert extract_video_id("dQw4w9WgXcQ") == "dQw4w9WgXcQ"
    assert extract_video_id("no-es-url") is None


def test_sanitize():
    assert sanitize_filename("Cómo funciona Whisper: guía 2026?") == "Como_funciona_Whisper_guia_2026"
    assert sanitize_filename("") == "video"
