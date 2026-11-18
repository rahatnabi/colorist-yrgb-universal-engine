import pytest

from yrgb_engine.precision import PrecisionFrame
from yrgb_engine.shot_comparison import align_and_compare


def _frame(rgb, name):
    return PrecisionFrame.from_interleaved(
        width=rgb.shape[1], height=rgb.shape[0],
        channel_names=("R", "G", "B"), values=rgb.astype("float32").reshape(-1),
        source_path=name, decoder="test", sample_domain="synthetic_linear_values",
    )


def test_feature_alignment_registers_translated_and_rotated_still():
    cv2 = pytest.importorskip("cv2")
    np = pytest.importorskip("numpy")
    rng = np.random.default_rng(42)
    base = rng.random((420, 560, 3), dtype=np.float32)
    # Add stable high-contrast features so ORB has repeatable keypoints.
    for index in range(35):
        x = int(rng.integers(25, 535))
        y = int(rng.integers(25, 395))
        cv2.circle(base, (x, y), int(rng.integers(4, 15)),
                   tuple(float(v) for v in rng.random(3)), -1)
    matrix = cv2.getRotationMatrix2D((280, 210), 2.5, 0.98)
    matrix[0, 2] += 9
    matrix[1, 2] -= 6
    candidate = cv2.warpAffine(base, matrix, (560, 420), flags=cv2.INTER_LINEAR)

    result = align_and_compare(_frame(base, "reference"), _frame(candidate, "candidate"))

    assert result["alignment"]["inliers"] >= 8
    assert result["alignment"]["inlier_ratio"] >= 0.15
    assert result["alignment"]["overlap_ratio"] > 0.5
    assert result["comparison"]["sample_domain_match"] is True
    assert result["alignment_preview_data_url"].startswith("data:image/jpeg;base64,")
    assert result["comparison"]["measurement_domain"] == "aligned_decoded_rgb_sample_values"
