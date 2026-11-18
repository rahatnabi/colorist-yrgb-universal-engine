"""Feature-based alignment and reference-relative RGB diagnostics for still images.

This module performs geometric registration only. It does not normalize color spaces,
decode transfer functions, or interpret RGB differences as exposure or perceptual color.
"""
from __future__ import annotations

from typing import Any
import base64

from .precision import PrecisionFrame


class ShotAlignmentError(ValueError):
    """Raised when reliable feature-based image alignment cannot be estimated."""


def _rgb_array(frame: PrecisionFrame):
    try:
        import numpy as np
    except ImportError as exc:
        raise ShotAlignmentError("NumPy is required for reference comparison.") from exc

    names = [name.upper() for name in frame.channel_names]
    if not all(name in names for name in ("R", "G", "B")):
        raise ShotAlignmentError("Both images must contain named R, G and B channels.")
    indices = [names.index(name) for name in ("R", "G", "B")]
    samples = np.asarray(frame.samples, dtype=np.float32).reshape(
        frame.height, frame.width, frame.channel_count
    )
    return samples[:, :, indices]


def _feature_gray(rgb, cv2, np):
    # Robust per-image scaling is only for feature detection, never for color metrics.
    luminance_like = (rgb[:, :, 0] + rgb[:, :, 1] + rgb[:, :, 2]) / 3.0
    low, high = np.percentile(luminance_like, [1.0, 99.0])
    if not np.isfinite(low) or not np.isfinite(high) or high <= low:
        raise ShotAlignmentError("Image has insufficient tonal variation for feature alignment.")
    scaled = np.clip((luminance_like - low) / (high - low), 0.0, 1.0)
    return (scaled * 255.0).astype(np.uint8)


def align_and_compare(
    reference: PrecisionFrame,
    candidate: PrecisionFrame,
    *,
    max_dimension: int = 1280,
    max_features: int = 6000,
) -> dict[str, Any]:
    """Align candidate to reference and compare RGB samples over their overlap."""
    try:
        import cv2
        import numpy as np
    except ImportError as exc:
        raise ShotAlignmentError(
            "OpenCV and NumPy are required. Install the optional 'vision' dependencies."
        ) from exc

    if not 320 <= max_dimension <= 2048:
        raise ShotAlignmentError("max_dimension must be between 320 and 2048.")
    ref_rgb = _rgb_array(reference)
    cand_rgb = _rgb_array(candidate)

    def resize(rgb):
        h, w = rgb.shape[:2]
        scale = min(1.0, max_dimension / max(h, w))
        if scale < 1.0:
            rgb = cv2.resize(
                rgb, (max(1, round(w * scale)), max(1, round(h * scale))),
                interpolation=cv2.INTER_AREA,
            )
        return rgb

    ref = resize(ref_rgb)
    cand = resize(cand_rgb)
    ref_gray = _feature_gray(ref, cv2, np)
    cand_gray = _feature_gray(cand, cv2, np)

    detector = cv2.ORB_create(nfeatures=max_features, scaleFactor=1.2, nlevels=8)
    key_ref, desc_ref = detector.detectAndCompute(ref_gray, None)
    key_cand, desc_cand = detector.detectAndCompute(cand_gray, None)
    if desc_ref is None or desc_cand is None or len(key_ref) < 8 or len(key_cand) < 8:
        raise ShotAlignmentError(
            "Not enough distinctive features. Try images with more shared detail and texture."
        )

    matcher = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=False)
    pairs = matcher.knnMatch(desc_cand, desc_ref, k=2)
    good = [m for pair in pairs if len(pair) == 2
            for m, n in [pair] if m.distance < 0.75 * n.distance]
    if len(good) < 8:
        raise ShotAlignmentError(
            f"Only {len(good)} reliable feature matches found; at least 8 are required."
        )

    source_points = np.float32([key_cand[m.queryIdx].pt for m in good]).reshape(-1, 1, 2)
    target_points = np.float32([key_ref[m.trainIdx].pt for m in good]).reshape(-1, 1, 2)
    homography, inlier_mask = cv2.findHomography(
        source_points, target_points, cv2.RANSAC, 4.0,
        maxIters=3000, confidence=0.995,
    )
    if homography is None or inlier_mask is None:
        raise ShotAlignmentError("Feature matches could not produce a stable alignment.")
    inliers = int(inlier_mask.ravel().sum())
    inlier_ratio = inliers / len(good)
    if inliers < 8 or inlier_ratio < 0.15:
        raise ShotAlignmentError(
            "Alignment confidence is too low. Use images with more shared, stationary detail."
        )

    out_h, out_w = ref.shape[:2]
    warped = cv2.warpPerspective(cand, homography, (out_w, out_h), flags=cv2.INTER_LINEAR)
    source_mask = np.full(cand_gray.shape, 255, dtype=np.uint8)
    warped_mask = cv2.warpPerspective(source_mask, homography, (out_w, out_h),
                                      flags=cv2.INTER_NEAREST)
    overlap = warped_mask > 0
    overlap_pixels = int(overlap.sum())
    total_pixels = out_w * out_h
    overlap_ratio = overlap_pixels / total_pixels
    if overlap_pixels < 256 or overlap_ratio < 0.05:
        raise ShotAlignmentError("Aligned images have too little overlapping area to compare.")

    ref_overlap = ref[overlap].astype(np.float64)
    cand_overlap = warped[overlap].astype(np.float64)
    delta = cand_overlap - ref_overlap
    channel_metrics = {}
    for index, channel in enumerate(("R", "G", "B")):
        channel_delta = delta[:, index]
        channel_metrics[channel] = {
            "reference_mean": float(ref_overlap[:, index].mean()),
            "candidate_aligned_mean": float(cand_overlap[:, index].mean()),
            "mean_delta_candidate_minus_reference": float(channel_delta.mean()),
            "mean_absolute_difference": float(np.abs(channel_delta).mean()),
            "root_mean_square_difference": float(np.sqrt(np.mean(channel_delta ** 2))),
        }

    # A diagnostic overlay uses one shared percentile scale; it is not color managed.
    combined_values = np.concatenate((ref_overlap.reshape(-1), cand_overlap.reshape(-1)))
    preview_low, preview_high = np.percentile(combined_values, [1.0, 99.0])
    if not np.isfinite(preview_low) or not np.isfinite(preview_high) or preview_high <= preview_low:
        preview_low, preview_high = float(combined_values.min()), float(combined_values.max() + 1.0)
    ref_preview = np.clip((ref - preview_low) / (preview_high - preview_low), 0.0, 1.0)
    cand_preview = np.clip((warped - preview_low) / (preview_high - preview_low), 0.0, 1.0)
    overlay = ref_preview.copy()
    overlay[overlap] = 0.5 * ref_preview[overlap] + 0.5 * cand_preview[overlap]
    encoded_ok, encoded_preview = cv2.imencode(
        ".jpg", cv2.cvtColor((overlay * 255.0).astype(np.uint8), cv2.COLOR_RGB2BGR),
        [cv2.IMWRITE_JPEG_QUALITY, 78],
    )
    preview_data_url = (
        "data:image/jpeg;base64," + base64.b64encode(encoded_preview.tobytes()).decode("ascii")
        if encoded_ok else None
    )

    same_sample_domain = reference.sample_domain == candidate.sample_domain
    return {
        "alignment_preview_data_url": preview_data_url,
        "alignment_preview_note": (
            "50/50 reference and aligned-candidate overlay with a shared 1st-99th percentile sample scale. "
            "Diagnostic only; not a color-managed display transform."
        ),
        "alignment": {
            "method": "ORB feature matching + RANSAC homography",
            "reference_size": {"width": reference.width, "height": reference.height},
            "candidate_size": {"width": candidate.width, "height": candidate.height},
            "analysis_size": {"width": out_w, "height": out_h},
            "homography_candidate_to_reference": homography.tolist(),
            "good_matches": len(good),
            "inliers": inliers,
            "inlier_ratio": float(inlier_ratio),
            "overlap_pixels": overlap_pixels,
            "overlap_ratio": float(overlap_ratio),
        },
        "comparison": {
            "measurement_domain": "aligned_decoded_rgb_sample_values",
            "reference_sample_domain": reference.sample_domain,
            "candidate_sample_domain": candidate.sample_domain,
            "sample_domain_match": same_sample_domain,
            "channel_metrics": channel_metrics,
            "comparability": (
                "same_sample_domain_but_colorimetry_unverified"
                if same_sample_domain else "different_sample_domains_not_directly_comparable"
            ),
            "note": (
                "Geometric alignment uses feature detection and does not alter source files. "
                "RGB metrics compare decoded samples over the overlap only. Matching sample-domain "
                "labels do not prove matching primaries, transfer functions, white balance or ICC profiles. "
                "These metrics are not exposure stops, calibrated luminance, or perceptual Delta E."
            ),
        },
    }
