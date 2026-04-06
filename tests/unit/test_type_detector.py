from services.ingest.type_detector import detect_media_type


def test_detect_media_type_image():
    assert detect_media_type("image/png", "a.png") == "image"


def test_detect_media_type_audio():
    assert detect_media_type("audio/mpeg", "a.mp3") == "audio"


def test_detect_media_type_video():
    assert detect_media_type("video/mp4", "a.mp4") == "video"


def test_detect_media_type_text_default():
    assert detect_media_type("application/pdf", "a.pdf") == "text"
