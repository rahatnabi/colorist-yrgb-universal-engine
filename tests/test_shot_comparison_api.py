from fastapi.testclient import TestClient

from yrgb_engine.api import create_app
from yrgb_engine.precision import PrecisionFrame
from yrgb_engine.registry import ProfileRegistry


def test_align_compare_endpoint_registers_candidate_to_reference(monkeypatch):
    decoded_names = []

    def fake_decode(path):
        decoded_names.append(str(path))
        return PrecisionFrame.from_interleaved(
            width=16, height=16, channel_names=("R", "G", "B"),
            values=[0.25, 0.5, 0.75] * (16 * 16),
            source_path=str(path), decoder="test-decoder",
            sample_domain="test_encoded_rgb",
        )

    def fake_align(reference, candidate):
        assert reference.width == candidate.width == 16
        return {
            "alignment": {
                "method": "test-registration",
                "inliers": 24,
                "inlier_ratio": 0.8,
                "overlap_ratio": 0.95,
                "homography_candidate_to_reference": [
                    [1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]
                ],
            },
            "comparison": {
                "measurement_domain": "aligned_decoded_rgb_sample_values",
                "comparability": "same_sample_domain_but_colorimetry_unverified",
                "sample_domain_match": True,
                "channel_metrics": {
                    channel: {
                        "reference_mean": 0.5,
                        "candidate_aligned_mean": 0.51,
                        "mean_delta_candidate_minus_reference": 0.01,
                        "mean_absolute_difference": 0.02,
                        "root_mean_square_difference": 0.03,
                    } for channel in ("R", "G", "B")
                },
                "note": "test-only measurement note",
            },
        }

    monkeypatch.setattr("yrgb_engine.oiio_decoder.decode_oiio_float", fake_decode)
    monkeypatch.setattr("yrgb_engine.shot_comparison.align_and_compare", fake_align)
    client = TestClient(create_app(registry=ProfileRegistry([])))
    response = client.post(
        "/v1/media/align-compare",
        files={
            "reference": ("reference.tif", b"reference bytes", "image/tiff"),
            "candidate": ("candidate.tif", b"candidate bytes", "image/tiff"),
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["reference_filename"] == "reference.tif"
    assert payload["candidate_filename"] == "candidate.tif"
    assert payload["alignment"]["method"] == "test-registration"
    assert payload["comparison"]["measurement_domain"] == "aligned_decoded_rgb_sample_values"
    assert payload["comparison"]["channel_metrics"]["R"]["mean_delta_candidate_minus_reference"] == 0.01
    assert len(decoded_names) == 2


def test_align_compare_endpoint_rejects_empty_upload():
    client = TestClient(create_app(registry=ProfileRegistry([])))
    response = client.post(
        "/v1/media/align-compare",
        files={
            "reference": ("reference.tif", b"", "image/tiff"),
            "candidate": ("candidate.tif", b"candidate", "image/tiff"),
        },
    )
    assert response.status_code == 400
