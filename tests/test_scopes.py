import json

import pytest

from yrgb_engine.precision import ColorEncoding, PrecisionFrame
from yrgb_engine.scopes import (
    ScopeConfig,
    ScopeEngineError,
    build_scope_snapshot,
)


def make_frame(values, *, width=2, encoding=None):
    return PrecisionFrame.from_interleaved(
        width=width,
        height=1,
        channel_names=("R", "G", "B"),
        values=values,
        source_path="synthetic",
        decoder="test",
        encoding=encoding or ColorEncoding(transfer="unknown"),
        sample_domain="decoder_float_output",
    )


def test_scope_snapshot_contains_all_base_scopes_and_safe_axis_label():
    frame = make_frame([0.1, 0.2, 0.3, 0.8, 0.7, 0.6])
    result = build_scope_snapshot(
        frame,
        ScopeConfig(
            value_range=(0.0, 1.0),
            histogram_bins=16,
            raster_width=32,
            raster_height=16,
            waveform_coefficients=(0.2126, 0.7152, 0.0722),
            vectorscope_coefficients=(0.2126, 0.7152, 0.0722),
        ),
        frame_index=12,
        timestamp_seconds=0.5,
    )
    assert set(result.analysis.histograms) == {"R", "G", "B"}
    assert set(result.analysis.rgb_parade) == {"R", "G", "B"}
    assert result.analysis.waveform is not None
    assert result.analysis.vectorscope_points is not None
    assert result.value_axis_label == "Source sample value"
    assert result.scale_kind == "sample-domain"
    assert result.frame_index == 12
    assert result.timestamp_seconds == pytest.approx(0.5)


def test_payload_is_json_compatible_and_preserves_encoding_metadata():
    encoding = ColorEncoding(
        primaries="camera-gamut",
        transfer="camera-log",
        matrix="unknown",
        range="full",
        working_space_id="DWG/Intermediate",
        transform_id="camera-log-to-dwg-v1",
    )
    result = build_scope_snapshot(make_frame([0.1, 0.2, 0.3], width=1, encoding=encoding))
    payload = result.to_payload()
    json.dumps(payload)
    assert payload["working_space_id"] == "DWG/Intermediate"
    assert payload["transfer"] == "camera-log"
    assert isinstance(payload["analysis"]["histograms"]["R"]["counts"], list)


def test_scope_snapshot_does_not_assume_ire_or_apply_a_transform():
    frame = make_frame([-0.2, 0.5, 1.4], width=1)
    result = build_scope_snapshot(frame, ScopeConfig(value_range=(0.0, 1.0)))
    assert result.value_axis_label != "IRE"
    assert result.analysis.histograms["R"].underflow == 1
    assert result.analysis.histograms["B"].overflow == 1
    assert frame.encoding.validated is False


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"frame_index": -1}, "frame_index"),
        ({"timestamp_seconds": -0.1}, "timestamp_seconds"),
        ({"timestamp_seconds": float("inf")}, "timestamp_seconds"),
    ],
)
def test_invalid_frame_timing_is_rejected(kwargs, message):
    frame = make_frame([0.1, 0.2, 0.3], width=1)
    with pytest.raises(ScopeEngineError, match=message):
        build_scope_snapshot(frame, **kwargs)


def test_invalid_scope_config_is_reported_as_scope_engine_error():
    frame = make_frame([0.1, 0.2, 0.3], width=1)
    with pytest.raises(ScopeEngineError, match="value_range"):
        build_scope_snapshot(frame, ScopeConfig(value_range=(1.0, 0.0)))
