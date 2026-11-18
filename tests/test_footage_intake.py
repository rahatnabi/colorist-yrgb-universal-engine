import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from footage_intake import build_report, parse_xml_sidecar, sha256_file


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


def test_build_report_never_modifies_source_files(tmp_path):
    source = tmp_path / "sidecar.xml"
    original = b"<Root><Gamma>S-Log3</Gamma></Root>"
    source.write_bytes(original)
    report = build_report([source], run_probe=False)
    assert report["source_files_modified"] is False
    assert report["files"][0]["sha256"] == hashlib.sha256(original).hexdigest()
    assert source.read_bytes() == original
    assert report["files"][0]["sidecar"]["values"]["Gamma"] == ["S-Log3"]


def test_missing_file_is_explicit(tmp_path):
    report = build_report([tmp_path / "missing.mp4"], run_probe=False)
    assert report["files"][0]["status"] == "not_found"
