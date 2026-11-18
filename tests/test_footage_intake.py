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


def test_xml_sidecar_extracts_values_without_guessing_vendor_meaning(tmp_path):
    source = tmp_path / "camera.xml"
    source.write_text(
        '<Root><CameraModel>ILME-FX3</CameraModel>'
        '<Setting name="Gamma">S-Log3</Setting></Root>',
        encoding="utf-8",
    )
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
    assert "RuntimeError: decoder wrapper failed" == result["probe_error"]
    assert result["sha256"] == hashlib.sha256(source.read_bytes()).hexdigest()


def test_report_summary_counts_missing_and_probe_errors(tmp_path):
    present = tmp_path / "clip.mp4"
    present.write_bytes(b"original")
    missing = tmp_path / "missing.mp4"
    report = build_report([present, missing], run_probe=False)
    assert report["summary"]["file_count"] == 2
    assert report["summary"]["bytes_acquired_count"] == 1
    assert report["files"][1]["status"] == "not_found"


def test_missing_file_is_explicit(tmp_path):
    report = build_report([tmp_path / "missing.mp4"], run_probe=False)
    assert report["files"][0]["status"] == "not_found"
