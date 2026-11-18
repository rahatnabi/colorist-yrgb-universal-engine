import pytest

from yrgb_engine.grading_pipeline import GradingPipelineError, process_validated_still
from yrgb_engine.look import LookSettings
from yrgb_engine.precision import ColorEncoding, PrecisionFrame


class _Registry:
    pass


def _frame(transfer="linear"):
    return PrecisionFrame.from_interleaved(
        width=1,
        height=1,
        channel_names=("R", "G", "B", "A"),
        values=(0.2, 0.4, 0.6, 0.75),
        source_path="fixture.exr",
        decoder="test",
        encoding=ColorEncoding(
            transfer=transfer, profile_id="camera.profile", validated=False
        ),
    )


def test_pipeline_uses_approved_linear_frame_and_keeps_preview_unvalidated(monkeypatch, tmp_path):
    import yrgb_engine.grading_pipeline as pipeline

    validated = _frame()
    validated.encoding = ColorEncoding(
        primaries="DWG", transfer="linear", profile_id="camera.profile",
        metadata_source="validated fixture", validated=True,
        working_space_id="linear-dwg", transform_id="camera-to-linear-dwg",
    )
    monkeypatch.setattr(
        pipeline, "prepare_frame_for_working_space",
        lambda frame, **kwargs: validated,
    )

    def fake_display_transform(frame, **kwargs):
        return PrecisionFrame.from_interleaved(
            width=frame.width, height=frame.height,
            channel_names=frame.channel_names, values=frame.samples,
            source_path=frame.source_path, decoder=frame.decoder,
            encoding=ColorEncoding(
                transfer="linear", profile_id="display-space",
                validated=False, working_space_id="display-space",
            ),
            sample_domain="test_display",
        )

    monkeypatch.setattr(pipeline, "transform_frame", fake_display_transform)
    result = process_validated_still(
        _frame(), LookSettings(exposure_stops=1), registry=_Registry(),
        config_path=tmp_path / "ocio.ocio", working_space_id="linear-dwg",
        display_space_id="display-space", display_transfer="srgb",
        display_primaries="srgb",
    )

    assert result.working_frame.encoding.validated is True
    assert result.graded_frame.pixel(0, 0) == pytest.approx((0.4, 0.8, 1.2, 0.75))
    assert result.display_preview_frame.encoding.validated is False
    assert result.display_preview_frame.encoding.transfer == "srgb"
    assert result.display_preview_frame.purpose == "display_preview_only"
    assert result.display_preview_frame.metadata["yrgb_mastering_export_allowed"] is False


def test_pipeline_rejects_non_linear_approved_output(monkeypatch, tmp_path):
    import yrgb_engine.grading_pipeline as pipeline

    encoded = _frame("slog3")
    encoded.encoding = ColorEncoding(
        transfer="slog3", profile_id="camera.profile", validated=True,
        working_space_id="linear-dwg",
    )
    monkeypatch.setattr(
        pipeline, "prepare_frame_for_working_space",
        lambda frame, **kwargs: encoded,
    )
    with pytest.raises(GradingPipelineError, match="scene-linear"):
        process_validated_still(
            _frame(), LookSettings(), registry=_Registry(),
            config_path=tmp_path / "ocio.ocio", working_space_id="linear-dwg",
            display_space_id="display-space", display_transfer="srgb",
            display_primaries="srgb",
        )


def test_pipeline_rejects_missing_display_contract():
    with pytest.raises(GradingPipelineError, match="required"):
        process_validated_still(
            _frame(), LookSettings(), registry=_Registry(), config_path="unused",
            working_space_id="linear-dwg", display_space_id="display-space",
            display_transfer="", display_primaries="srgb",
        )
