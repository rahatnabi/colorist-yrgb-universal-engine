import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_media_analysis_schema_separates_measurement_domains_and_evidence_states():
    schema = json.loads(
        (ROOT / "data/footage_library/media_analysis_report.schema.json").read_text()
    )
    assert schema["$schema"].endswith("/2020-12/schema")
    assert set(schema["required"]) >= {
        "evidence",
        "color_metadata",
        "measurement_domains",
        "timecode",
        "reference_validation",
    }
    statuses = schema["$defs"]["status"]["enum"]
    assert {"verified", "reported", "estimated", "conflict", "unresolved", "unavailable"} <= set(statuses)
    domains = schema["properties"]["measurement_domains"]["properties"]
    assert set(domains) == {
        "original_yuv_code_values",
        "nonlinear_rgb_code_values",
        "linear_light_rgb",
    }
    assert schema["properties"]["reference_validation"]["properties"]["status"]["enum"] == [
        "not_validated",
        "decoder_validated",
        "metadata_confirmed",
        "reference_validated",
    ]


def test_media_analysis_contract_documents_non_equivalent_validation_states():
    doc = (ROOT / "docs/media-analysis-report-contract.md").read_text()
    for phrase in (
        "Legal-range excursions",
        "Hard code saturation",
        "Linear-light RGB",
        "Timecode",
        "reference_validated",
    ):
        assert phrase in doc


def test_pending_media_analysis_template_is_explicitly_unvalidated():
    template = json.loads(
        (ROOT / "data/footage_library/media_analysis_report.template.json").read_text()
    )
    assert template["report_state"] == "not_validated"
    assert template["color_metadata"]["resolution_status"] == "unresolved"
    assert all(
        domain["status"] == "unavailable"
        for domain in template["measurement_domains"].values()
    )
    assert template["reference_validation"]["status"] == "not_validated"
