from yrgb_engine.capabilities import capabilities_as_dict, detect_capabilities

def test_capability_report_has_expected_tools():
    names = {item.name for item in detect_capabilities()}
    assert {"ffmpeg", "ffprobe", "PIL", "rawpy", "OpenImageIO", "PyOpenColorIO"} <= names

def test_capability_report_is_json_friendly():
    report = capabilities_as_dict()
    assert all(isinstance(item["available"], bool) for item in report)
    assert all("limitation" in item for item in report)
