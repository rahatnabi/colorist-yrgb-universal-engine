import pytest

from yrgb_engine.linear_export import LinearExportError, save_linear_float_exr
from yrgb_engine.look import LookDevelopmentError, LookSettings, apply_look_to_declared_linear_frame
from yrgb_engine.precision import ColorEncoding, PrecisionFrame


def _frame(transfer="unknown"):
    return PrecisionFrame.from_interleaved(
        width=1, height=1, channel_names=("R", "G", "B", "A"),
        values=(0.2, 0.4, 0.6, 0.75), source_path="fixture.exr", decoder="test",
        encoding=ColorEncoding(transfer=transfer),
    )


def test_declared_linear_look_keeps_frame_unvalidated_and_preserves_alpha():
    result = apply_look_to_declared_linear_frame(
        _frame(), LookSettings(exposure_stops=1),
        input_space_id="acescg-linear", linear_input_confirmed=True,
    )
    assert result.pixel(0, 0) == pytest.approx((0.4, 0.8, 1.2, 0.75))
    assert result.encoding.validated is False
    assert result.encoding.working_space_id == "acescg-linear"


def test_declared_linear_look_requires_operator_confirmation():
    with pytest.raises(LookDevelopmentError, match="confirmation"):
        apply_look_to_declared_linear_frame(
            _frame(), LookSettings(), input_space_id="linear", linear_input_confirmed=False
        )


def test_declared_linear_look_rejects_known_nonlinear_source():
    with pytest.raises(LookDevelopmentError, match="non-linear"):
        apply_look_to_declared_linear_frame(
            _frame("sRGB"), LookSettings(), input_space_id="linear", linear_input_confirmed=True
        )


def test_exr_export_requires_openimageio(monkeypatch, tmp_path):
    import builtins

    original_import = builtins.__import__

    def blocked(name, *args, **kwargs):
        if name in {"numpy", "OpenImageIO"}:
            raise ImportError("missing")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", blocked)
    with pytest.raises(LinearExportError, match="OpenImageIO"):
        save_linear_float_exr(_frame(), tmp_path / "out.exr")
