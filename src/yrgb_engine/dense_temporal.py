"""Dense fixed-ROI temporal metrics with strict evidence gates.

The module accepts per-frame ROI means, not full decoded frames. It only
computes exposure-stop metrics when the caller proves that samples are
reference-validated scene-linear RGB from a stable ROI.
"""
from __future__ import annotations

from math import isfinite, log2
from statistics import median
from typing import Any


class DenseTemporalError(ValueError):
    """Raised when dense temporal samples are malformed."""



def _spectral_peak(values: list[float], sample_rate: float) -> dict[str, float] | None:
    """Return a conservative detrended Hann-window spectral peak summary."""
    import numpy as np
    signal = np.asarray(values, dtype=np.float64)
    if signal.size < 32 or not np.all(np.isfinite(signal)) or float(np.mean(np.abs(signal))) <= 1e-12:
        return None
    time = np.arange(signal.size, dtype=np.float64)
    slope, intercept = np.polyfit(time, signal, 1)
    residual = signal - (slope * time + intercept)
    residual -= float(np.mean(residual))
    window = np.hanning(signal.size)
    spectrum = np.abs(np.fft.rfft(residual * window))
    frequencies = np.fft.rfftfreq(signal.size, d=1.0 / sample_rate)
    upper = min(30.0, sample_rate / 2.0)
    eligible = (frequencies >= 1.0) & (frequencies <= upper)
    if int(np.count_nonzero(eligible)) < 3:
        return None
    indices = np.flatnonzero(eligible)
    peak_index = int(indices[int(np.argmax(spectrum[eligible]))])
    peak = float(spectrum[peak_index])
    floor = float(np.median(spectrum[eligible]))
    amplitude = 2.0 * peak / max(float(np.sum(window)), 1e-12)
    baseline = max(float(np.mean(np.abs(signal))), 1e-9)
    return {
        "frequency_hz": float(frequencies[peak_index]),
        "peak_to_median_spectral_floor": peak / max(floor, 1e-12),
        "relative_modulation_amplitude": amplitude / baseline,
    }


def _luminance(rgb: dict[str, float], coefficients: tuple[float, float, float]) -> float:
    return sum(rgb[key] * coefficient for key, coefficient in zip(("R", "G", "B"), coefficients, strict=True))


def analyze_dense_roi_samples(
    samples: list[dict[str, Any]],
    *,
    expected_interval_seconds: float,
    minimum_samples: int = 24,
    luminance_coefficients: tuple[float, float, float] = (0.2126, 0.7152, 0.0722),
) -> dict[str, Any]:
    """Analyze a fixed ROI; scene-linear exposure metrics require validated evidence."""
    if isinstance(expected_interval_seconds, bool) or not isinstance(expected_interval_seconds, (int, float)) or not isfinite(expected_interval_seconds) or expected_interval_seconds <= 0:
        raise DenseTemporalError("expected_interval_seconds must be finite and positive.")
    if isinstance(minimum_samples, bool) or not isinstance(minimum_samples, int) or minimum_samples < 3:
        raise DenseTemporalError("minimum_samples must be an integer of at least 3.")
    if len(luminance_coefficients) != 3 or any(not isfinite(v) or v < 0 for v in luminance_coefficients) or abs(sum(luminance_coefficients) - 1.0) > 1e-6:
        raise DenseTemporalError("Luminance coefficients must be three non-negative values summing to 1.")

    normalized = []
    previous_time = None
    previous_frame = None
    roi_id = None
    domain = None
    transform_validated = True
    for index, sample in enumerate(samples):
        timestamp = sample.get("timestamp_seconds")
        frame_index = sample.get("frame_index")
        current_roi = sample.get("roi_id")
        current_domain = sample.get("measurement_domain")
        channels = sample.get("roi_mean")
        validated = sample.get("reference_validated_transform") is True
        if isinstance(timestamp, bool) or not isinstance(timestamp, (int, float)) or not isfinite(timestamp) or timestamp < 0:
            raise DenseTemporalError(f"Sample {index} has an invalid timestamp.")
        if isinstance(frame_index, bool) or not isinstance(frame_index, int) or frame_index < 0:
            raise DenseTemporalError(f"Sample {index} has an invalid frame index.")
        if previous_time is not None and (timestamp <= previous_time or frame_index <= previous_frame):
            raise DenseTemporalError("Timestamps and frame indices must be strictly increasing.")
        if not isinstance(current_roi, str) or not current_roi:
            raise DenseTemporalError(f"Sample {index} is missing roi_id.")
        if roi_id is None:
            roi_id, domain = current_roi, current_domain
        elif current_roi != roi_id:
            raise DenseTemporalError("ROI identity changed during the temporal sample sequence.")
        if current_domain != domain:
            raise DenseTemporalError("Measurement domain changed during the temporal sample sequence.")
        if not isinstance(channels, dict):
            raise DenseTemporalError(f"Sample {index} is missing roi_mean.")
        rgb = []
        for channel in ("R", "G", "B"):
            value = channels.get(channel)
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not isfinite(value):
                raise DenseTemporalError(f"Sample {index} has invalid {channel} mean.")
            rgb.append(float(value))
        tile_means = sample.get("tile_means")
        if tile_means is not None:
            if not isinstance(tile_means, list) or len(tile_means) != 4:
                raise DenseTemporalError(f"Sample {index} tile_means must contain exactly four tile RGB means.")
            for tile in tile_means:
                if not isinstance(tile, dict) or any(
                    isinstance(tile.get(channel), bool)
                    or not isinstance(tile.get(channel), (int, float))
                    or not isfinite(tile[channel])
                    for channel in ("R", "G", "B")
                ):
                    raise DenseTemporalError(f"Sample {index} contains invalid tile RGB means.")
        normalized.append((float(timestamp), frame_index, tuple(rgb), tile_means))
        previous_time, previous_frame = float(timestamp), frame_index
        transform_validated = transform_validated and validated

    if not normalized:
        return {
            "status": "unavailable",
            "sample_count": 0,
            "flicker_assessment": {"status": "unavailable", "reason": "No samples supplied."},
            "exposure_drift_assessment": {"status": "unavailable", "reason": "No samples supplied."},
        }

    intervals = [normalized[i][0] - normalized[i - 1][0] for i in range(1, len(normalized))]
    median_interval = median(intervals) if intervals else None
    interval_tolerance = expected_interval_seconds * 0.05
    dense_sampling = (
        len(normalized) >= minimum_samples
        and median_interval is not None
        and abs(median_interval - expected_interval_seconds) <= interval_tolerance
        and all(abs(value - expected_interval_seconds) <= interval_tolerance for value in intervals)
    )
    stable_roi = True  # ROI identity was enforced above.
    linear_evidence = domain == "linear_light_rgb" and transform_validated
    luminance = [
        sum(channel * coefficient for channel, coefficient in zip(rgb, luminance_coefficients, strict=True))
        for _, _, rgb, _ in normalized
    ]
    positive = all(value > 0 for value in luminance)
    first_last_stops = log2(luminance[-1] / luminance[0]) if len(luminance) > 1 and positive else None

    flicker = {
        "status": "inconclusive",
        "reason": "ROI mean periodicity is a candidate only; spatial coherence cannot rule out camera motion or moving content.",
    }
    scene_boundaries = []
    for index in range(1, len(normalized)):
        before = normalized[index - 1][2]
        after = normalized[index][2]
        scale = max(sum(abs(v) for v in before) / 3.0, 0.05)
        distance = sum(abs(after[c] - before[c]) for c in range(3)) / (3.0 * scale)
        if distance >= 0.25:
            scene_boundaries.append({
                "sample_index": index,
                "timestamp_seconds": normalized[index][0],
                "relative_rgb_mean_step": distance,
                "status": "boundary_candidate",
            })

    frequency_analysis = {"status": "unavailable", "reason": "Requires at least 32 dense, regular samples."}
    spatial_coherence = {"status": "unavailable", "reason": "Four-tile ROI measurements were not supplied."}
    if dense_sampling and len(normalized) >= 32:
        sample_rate = 1.0 / median_interval
        signal = [
            _luminance({"R": rgb[0], "G": rgb[1], "B": rgb[2]}, luminance_coefficients)
            for _, _, rgb, _ in normalized
        ]
        peak = _spectral_peak(signal, sample_rate)
        if peak is None:
            frequency_analysis = {"status": "inconclusive", "reason": "No stable non-zero spectral signal in the supported frequency band."}
        else:
            candidate = peak["peak_to_median_spectral_floor"] >= 6.0 and peak["relative_modulation_amplitude"] >= 0.002
            frequency_analysis = {
                "status": "periodic_variation_candidate" if candidate else "no_strong_periodic_peak",
                **peak,
                "supported_band_hz": [1.0, min(30.0, sample_rate / 2.0)],
                "interpretation": "Decoder-sample-domain periodic candidate; not a confirmed lighting flicker diagnosis.",
            }
            if all(item[3] is not None for item in normalized):
                tile_peaks = []
                for tile_index in range(4):
                    tile_signal = [
                        _luminance(item[3][tile_index], luminance_coefficients)
                        for item in normalized
                    ]
                    tile_peaks.append(_spectral_peak(tile_signal, sample_rate))
                coherent = [
                    item for item in tile_peaks if item is not None
                    and abs(item["frequency_hz"] - peak["frequency_hz"]) <= max(0.5, sample_rate / len(normalized))
                    and item["peak_to_median_spectral_floor"] >= 4.0
                ]
                spatial_coherence = {
                    "status": "reported",
                    "coherent_tile_count": len(coherent),
                    "tile_count": 4,
                    "coherence_fraction": len(coherent) / 4.0,
                    "interpretation": "Spatial coherence supports an illumination-change hypothesis but does not compensate for motion or prove flicker.",
                }
            flicker = {
                "status": "candidate" if candidate else "inconclusive",
                "reason": "A periodic ROI mean signal was found; spatial coherence and current diagnostics cannot confirm a lighting source.",
                "frequency_analysis": frequency_analysis,
                "spatial_coherence": spatial_coherence,
            }
    if not dense_sampling:
        flicker = {
            "status": "unavailable",
            "reason": "Insufficient sample count or irregular frame intervals for dense temporal analysis.",
        }

    exposure = {
        "status": "unavailable",
        "reason": "Requires reference-validated scene-linear RGB, a fixed ROI, and positive luminance samples.",
    }
    if linear_evidence and stable_roi and positive and len(normalized) >= minimum_samples:
        exposure = {
            "status": "reported",
            "first_to_last_delta_stops": first_last_stops,
            "sample_count": len(normalized),
            "interpretation": "ROI luminance change in scene-linear measurement domain; not proof of camera auto-exposure behavior.",
        }
    elif domain == "linear_light_rgb" and not transform_validated:
        exposure["reason"] = "Linear-light label is insufficient: reference_validated_transform must be true for every sample."

    return {
        "status": "reported",
        "measurement_domain": domain,
        "roi_id": roi_id,
        "sample_count": len(normalized),
        "median_interval_seconds": median_interval,
        "dense_sampling": dense_sampling,
        "luminance_coefficients": list(luminance_coefficients),
        "flicker_assessment": flicker,
        "frequency_analysis": frequency_analysis,
        "spatial_coherence": spatial_coherence,
        "scene_boundary_candidates": scene_boundaries,
        "exposure_drift_assessment": exposure,
        "limitations": [
            "ROI means cannot distinguish illumination changes from moving content inside the ROI.",
            "Frequency peaks are candidates only; no optical-flow motion compensation or lighting-source identification is performed.",
            "Scene boundaries are RGB mean-step candidates, not confirmed cuts.",
            "Exposure drift is reported only as first-to-last scene-linear ROI luminance delta in stops.",
        ],
    }
