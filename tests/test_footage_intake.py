import hashlib
import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from footage_intake import build_report, inspect_file, parse_xml_sidecar, sha256_file  # noqa: E402


def test_sha256_file_reads_in_chunks(tmp_path):
    source = tmp_path / "clip.bin"
    source.write_bytes(b"camera-original-bytes")
    assert sha256_file(source) == hashlib.sha256(b"camera-original-bytes").hexdigest()


def test_xml_sidecar_extracts_values(tmp_path):
    source = tmp_path / "camera.xml"
    source.write_text('<Root><CameraModel>ILME-FX3</CameraModel><Setting name="Gamma">S-Log3</Setting></Root>', encoding="utf-8")
    result = parse_xml_sidecar(source)
    assert result["status"] == "parsed"
    assert result["values"]["CameraModel"] == ["ILME-FX3"]
    assert result["values"]["Setting@name"] == ["Gamma"]
    assert result["values"]["Setting"] == ["S-Log3"]


def test_invalid_xml_is_reported_not_raised(tmp_path):
    source = tmp_path / "broken.xml"
    source.write_text("<root>", encoding="utf-8")
    assert parse_xml_sidecar(source)["status"] == "parse_error"


def test_oversized_xml_is_rejected_before_parsing(tmp_path):
    source = tmp_path / "large.xml"
    source.write_text("<root>123456</root>", encoding="utf-8")
    result = parse_xml_sidecar(source, max_bytes=4)
    assert result["status"] == "rejected_size_limit"
    assert result["size_bytes"] == source.stat().st_size
    assert result["max_bytes"] == 4
    assert result["values"] == {}


def test_build_report_never_modifies_source_files(tmp_path):
    source = tmp_path / "sidecar.xml"
    original = b"<Root><Gamma>S-Log3</Gamma></Root>"
    source.write_bytes(original)
    report = build_report([source], run_probe=False)
    assert report["source_files_modified"] is False
    assert report["files"][0]["sha256"] == hashlib.sha256(original).hexdigest()
    assert source.read_bytes() == original
    assert report["files"][0]["sidecar"]["values"]["Gamma"] == ["S-Log3"]


def test_skip_probe_does_not_add_probe_result(tmp_path):
    source = tmp_path / "clip.mp4"
    source.write_bytes(b"placeholder-original")
    report = build_report([source], run_probe=False)
    assert report["files"][0]["status"] == "bytes_acquired"
    assert "probe" not in report["files"][0]
    assert "probe_error" not in report["files"][0]


def test_unexpected_probe_error_is_reported_and_checksum_retained(tmp_path, monkeypatch):
    source = tmp_path / "clip.mp4"
    source.write_bytes(b"placeholder-original")
    fake_module = types.ModuleType("yrgb_engine.probe")
    def broken_probe(_path):
        raise RuntimeError("decoder wrapper failed")
    fake_module.probe_media = broken_probe
    monkeypatch.setitem(sys.modules, "yrgb_engine.probe", fake_module)
    result = inspect_file(source, run_probe=True)
    assert result["status"] == "probe_error"
    assert result["probe_error"] == "RuntimeError: decoder wrapper failed"
    assert result["sha256"] == hashlib.sha256(source.read_bytes()).hexdigest()


def test_report_summary_counts_missing(tmp_path):
    present = tmp_path / "clip.mp4"
    present.write_bytes(b"original")
    report = build_report([present, tmp_path / "missing.mp4"], run_probe=False)
    assert report["summary"]["file_count"] == 2
    assert report["summary"]["bytes_acquired_count"] == 1
    assert report["files"][1]["status"] == "not_found"


def test_sony_m01_sidecar_reconciles_against_video_stream(tmp_path, monkeypatch):
    xml = tmp_path / "C1382M01.XML"
    xml.write_text("<Root><CaptureGammaEquation>S-Log3</CaptureGammaEquation><CaptureColorPrimaries>S-Gamut3.Cine</CaptureColorPrimaries><CodingEquations>Rec.709</CodingEquations></Root>", encoding="utf-8")
    video = tmp_path / "C1382.MP4"
    video.write_bytes(b"mock-video")
    fake_module = types.ModuleType("yrgb_engine.probe")
    class FakeResult:
        status = "probed"
        def to_dict(self):
            return {"status": "probed", "metadata": {"capture_metadata": {"color_transfer": "bt709", "color_primaries": "bt709", "color_matrix": "bt709"}, "stream_summary": [{"codec_type": "video", "color_transfer": "bt709", "color_primaries": "bt709", "color_space": "bt709"}]}}
    fake_module.probe_media = lambda _path: FakeResult()
    monkeypatch.setitem(sys.modules, "yrgb_engine.probe", fake_module)
    report = build_report([video, xml], run_probe=True)
    reconciliation = report["files"][0]["sidecar_reconciliation"]
    assert reconciliation["sidecar_filename"] == "C1382M01.XML"
    assert reconciliation["status"] == "conflict"
    assert reconciliation["comparison"]["comparisons"]["camera_transfer"]["status"] == "conflict"
    assert reconciliation["comparison"]["comparisons"]["camera_primaries"]["status"] == "conflict"
    assert reconciliation["comparison"]["comparisons"]["coding_equations"]["status"] == "reported"
    assert report["summary"]["metadata_conflict_count"] == 1


def test_multiple_matching_sidecars_remain_unresolved(tmp_path, monkeypatch):
    video = tmp_path / "C1382.MP4"
    video.write_bytes(b"mock-video")
    for suffix in ("M01", "M02"):
        (tmp_path / f"C1382{suffix}.XML").write_text("<Root><CaptureGammaEquation>S-Log3</CaptureGammaEquation></Root>", encoding="utf-8")
    fake_module = types.ModuleType("yrgb_engine.probe")
    class FakeResult:
        status = "probed"
        def to_dict(self):
            return {"status": "probed", "metadata": {"stream_summary": []}}
    fake_module.probe_media = lambda _path: FakeResult()
    monkeypatch.setitem(sys.modules, "yrgb_engine.probe", fake_module)
    report = build_report([video, *sorted(tmp_path.glob("*.XML"))], run_probe=True)
    result = report["files"][0]["sidecar_reconciliation"]
    assert result["status"] == "unresolved"
    assert len(result["candidate_sidecars"]) == 2
