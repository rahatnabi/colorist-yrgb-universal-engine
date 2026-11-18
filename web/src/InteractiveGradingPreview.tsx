import { useEffect, useRef, useState } from "react";
import { applyInteractiveLook, type InteractiveLookSettings } from "./grading";

export type InteractivePreviewAnalysis = {
  width: number; height: number; decoder: string; timestamp_seconds?: number; sample_domain: string;
  analysis: {
    channels: Record<string, { mean: number }>;
    histograms: Record<string, { counts: number[]; minimum: number; maximum: number; underflow: number; overflow: number }>;
    rgb_parade: Record<string, { counts: number[][]; width: number; height: number; minimum: number; maximum: number; underflow: number; overflow: number }>;
    waveform: { counts: number[][]; width: number; height: number; minimum: number; maximum: number; underflow: number; overflow: number };
    vectorscope_points: [number, number][]; scope_standard: "bt709"; scope_note: string; note: string;
  };
};

function formatMeasurement(value: number | null | undefined, digits = 4) {
  return typeof value === "number" && Number.isFinite(value) ? value.toFixed(digits) : "—";
}

type Props = {
  sourceUrl: string;
  filename: string;
  settings: InteractiveLookSettings;
  curveMidpoint: number;
  workingSpaceId: "scene-linear-rec709" | "acescg-linear";
  sourceFile: File | null;
  profileId: string;
  cameraModel: string;
  apiBase: string;
  onNativeMeasurements?: (analysis: {
    width: number; height: number; decoder: string; sample_domain: string;
    analysis: {
      histograms: Record<string, { counts: number[]; minimum: number; maximum: number; underflow: number; overflow: number }>;
      rgb_parade: Record<string, { counts: number[][]; width: number; height: number; minimum: number; maximum: number; underflow: number; overflow: number }>;
      waveform: { counts: number[][]; width: number; height: number; minimum: number; maximum: number; underflow: number; overflow: number } | null;
      vectorscope_points: [number, number][] | null;
      scope_note: string; note: string;
    };
  }) => void;
  onRender?: (result: InteractivePreviewAnalysis) => void;
  onReset?: () => void;
};

export default function InteractiveGradingPreview({ sourceUrl, filename, settings, curveMidpoint, workingSpaceId, sourceFile, profileId, cameraModel, apiBase, onNativeMeasurements, onRender, onReset }: Props) {
  const onRenderRef = useRef(onRender);
  onRenderRef.current = onRender;
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const sourceCanvasRef = useRef<HTMLCanvasElement | null>(null);
  const [status, setStatus] = useState("Waiting for a browser-decodable still image");
  const [dimensions, setDimensions] = useState<{ width: number; height: number } | null>(null);
  const [nativePreviewUrl, setNativePreviewUrl] = useState("");
  const [nativeStatus, setNativeStatus] = useState("Select a reference-validated camera profile to enable native rendering.");
  const [nativeBusy, setNativeBusy] = useState(false);
  const [masterFormat, setMasterFormat] = useState<"exr" | "tiff">("exr");
  const [masterBusy, setMasterBusy] = useState(false);
  const [masterStatus, setMasterStatus] = useState("Full-resolution export requires a reference-validated camera profile.");
  const [roi, setRoi] = useState({ x: 0, y: 0, width: 1, height: 1 });
  const [measurementBusy, setMeasurementBusy] = useState(false);
  const [measurementStatus, setMeasurementStatus] = useState("Choose a neutral reference region in the source still.");
  const [measurementResult, setMeasurementResult] = useState<{
    correction_accuracy: { status: string; score: number | null; exposure: { metrics: { measured: number | null; target: number | null; deviation: number | null; score: number | null }[] }; white_balance: { metrics: { name: string; measured: number | null; score: number | null }[] } };
    scopes: { analysis: { channels: Record<string, { minimum: number; maximum: number; mean: number }>; waveform: unknown; vectorscope_points: unknown[] | null } };
    frame: { width: number; height: number };
    scope_axis: string;
  } | null>(null);

  useEffect(() => () => {
    if (nativePreviewUrl) URL.revokeObjectURL(nativePreviewUrl);
  }, [nativePreviewUrl]);

  useEffect(() => {
    setNativePreviewUrl("");
    setMeasurementResult(null);
    setMeasurementStatus("Grade controls or source changed · run native measurements again.");
    setMasterStatus("Grade controls or source changed · export the full-resolution master again.");
    setNativeStatus(profileId
      ? "Grade controls changed · render again to refresh the native result."
      : "Select a reference-validated camera profile to enable native rendering.");
  }, [sourceUrl, profileId, cameraModel, settings, curveMidpoint]);

  useEffect(() => {
    if (!sourceUrl) {
      sourceCanvasRef.current = null;
      setDimensions(null);
      setStatus("Upload a still image to begin interactive grading.");
      return;
    }
    let active = true;
    sourceCanvasRef.current = null;
    setDimensions(null);
    setStatus("Decoding still image…");
    const visibleCanvas = canvasRef.current;
    if (visibleCanvas) { visibleCanvas.width = 1; visibleCanvas.height = 1; }
    const image = new Image();
    image.onload = () => {
      if (!active) return;
      const scale = Math.min(1, 2048 / image.naturalWidth, 2048 / image.naturalHeight);
      const width = Math.max(1, Math.round(image.naturalWidth * scale));
      const height = Math.max(1, Math.round(image.naturalHeight * scale));
      const source = document.createElement("canvas");
      source.width = width;
      source.height = height;
      const context = source.getContext("2d", { willReadFrequently: true });
      if (!context) {
        setStatus("Canvas 2D is unavailable in this browser.");
        return;
      }
      context.imageSmoothingEnabled = true;
      context.imageSmoothingQuality = "high";
      context.drawImage(image, 0, 0, width, height);
      sourceCanvasRef.current = source;
      setDimensions({ width, height });
      setStatus("Image decoded · interactive preview ready");
    };
    image.onerror = () => {
      if (active) {
        sourceCanvasRef.current = null;
        setDimensions(null);
        setStatus("This format cannot be previewed by the browser. DNG/RAW requires a supported RAW decoder.");
      }
    };
    image.src = sourceUrl;
    return () => { active = false; image.src = ""; };
  }, [sourceUrl]);

  useEffect(() => {
    const source = sourceCanvasRef.current;
    const canvas = canvasRef.current;
    if (!source || !canvas) return;
    canvas.width = source.width;
    canvas.height = source.height;
    const context = canvas.getContext("2d", { willReadFrequently: true });
    if (!context) return;
    context.drawImage(source, 0, 0);
    const pixels = context.getImageData(0, 0, canvas.width, canvas.height);
    const graded = applyInteractiveLook(pixels, { settings, curve_midpoint: curveMidpoint, working_space_id: workingSpaceId });
    context.putImageData(graded, 0, 0);

    const width = canvas.width;
    const height = canvas.height;
    const bins = 128;
    const scopeWidth = 128;
    const scopeHeight = 96;
    const channels = ["R", "G", "B"] as const;
    const histogramCounts = channels.map(() => new Array(bins).fill(0));
    const paradeCounts = channels.map(() => Array.from({ length: scopeWidth }, () => new Array(scopeHeight).fill(0)));
    const waveformCounts = Array.from({ length: scopeWidth }, () => new Array(scopeHeight).fill(0));
    const means = [0, 0, 0];
    const vectorscope: [number, number][] = [];
    const data = graded.data;
    let pixelCount = 0;
    for (let offset = 0; offset < data.length; offset += 4) {
      const r = data[offset] / 255;
      const g = data[offset + 1] / 255;
      const b = data[offset + 2] / 255;
      const values = [r, g, b];
      const x = Math.min(scopeWidth - 1, Math.floor((pixelCount % width) / width * scopeWidth));
      values.forEach((value, channel) => {
        means[channel] += value;
        histogramCounts[channel][Math.min(bins - 1, Math.floor(value * bins))] += 1;
        const y = scopeHeight - 1 - Math.min(scopeHeight - 1, Math.floor(value * scopeHeight));
        paradeCounts[channel][x][y] += 1;
      });
      const luma = 0.2126 * r + 0.7152 * g + 0.0722 * b;
      const waveY = scopeHeight - 1 - Math.min(scopeHeight - 1, Math.floor(luma * scopeHeight));
      waveformCounts[x][waveY] += 1;
      const cb = (b - luma) / 1.8556;
      const cr = (r - luma) / 1.5748;
      if (pixelCount % Math.max(1, Math.floor(width * height / 12000)) === 0) vectorscope.push([cb, cr]);
      pixelCount += 1;
    }
    const histograms = Object.fromEntries(channels.map((channel, index) => [channel, {
      counts: histogramCounts[index], minimum: 0, maximum: 1, underflow: 0, overflow: 0,
    }]));
    const rgbParade = Object.fromEntries(channels.map((channel, index) => [channel, {
      counts: paradeCounts[index], width: scopeWidth, height: scopeHeight,
      minimum: 0, maximum: 1, underflow: 0, overflow: 0,
    }]));
    onRenderRef.current?.({
      width, height, decoder: "Browser Canvas", sample_domain: "graded_browser_srgb_preview",
      analysis: {
        channels: Object.fromEntries(channels.map((channel, index) => [channel, { mean: means[index] / Math.max(1, pixelCount) }])),
        histograms, rgb_parade: rgbParade,
        waveform: { counts: waveformCounts, width: scopeWidth, height: scopeHeight, minimum: 0, maximum: 1, underflow: 0, overflow: 0 },
        vectorscope_points: vectorscope, scope_standard: "bt709",
        scope_note: "Live scopes are calculated from the graded, browser-decoded sRGB preview. They are not calibrated IRE/nits or camera-log scopes.",
        note: "Live graded preview scope statistics · browser sRGB display-referred sample domain.",
      },
    });
  }, [settings, curveMidpoint, workingSpaceId, dimensions]);


  async function renderNativePreview() {
    if (!sourceFile || !profileId) return;
    setNativeBusy(true);
    setNativeStatus("Processing the still through the validated native pipeline…");
    try {
      const body = new FormData();
      body.append("file", sourceFile);
      body.append("profile_id", profileId);
      if (cameraModel) body.append("camera_model", cameraModel);
      body.append("exposure_stops", String(settings.exposure_stops));
      body.append("contrast", String(settings.contrast));
      body.append("pivot", String(settings.pivot));
      body.append("saturation", String(settings.saturation));
      body.append("temperature_shift", String(settings.temperature_shift));
      body.append("tint_shift", String(settings.tint_shift));
      body.append("curve_midpoint", String(curveMidpoint));
      const response = await fetch(apiBase + "/v1/media/native-grade-preview", {
        method: "POST",
        body,
      });
      if (!response.ok) {
        const data = await response.json().catch(() => ({}));
        throw new Error(data.detail || "Native still render failed.");
      }
      const blob = await response.blob();
      const nextUrl = URL.createObjectURL(blob);
      setNativePreviewUrl(nextUrl);
      setNativeStatus("Native float32 grade rendered · display PNG preview only · not a delivery master.");
    } catch (error) {
      setNativeStatus(error instanceof Error ? error.message : "Native still render failed.");
    } finally {
      setNativeBusy(false);
    }
  }


  async function runNativeMeasurements() {
    if (!sourceFile || !profileId) return;
    if (roi.width < 1 || roi.height < 1 || roi.x < 0 || roi.y < 0) {
      setMeasurementStatus("ROI coordinates and dimensions must be positive.");
      return;
    }
    setMeasurementBusy(true);
    setMeasurementResult(null);
    setMeasurementStatus("Measuring scopes and correction accuracy from the native graded float32 image…");
    try {
      const body = new FormData();
      body.append("file", sourceFile);
      body.append("profile_id", profileId);
      if (cameraModel) body.append("camera_model", cameraModel);
      body.append("roi_x", String(roi.x));
      body.append("roi_y", String(roi.y));
      body.append("roi_width", String(roi.width));
      body.append("roi_height", String(roi.height));
      body.append("exposure_stops", String(settings.exposure_stops));
      body.append("contrast", String(settings.contrast));
      body.append("pivot", String(settings.pivot));
      body.append("saturation", String(settings.saturation));
      body.append("temperature_shift", String(settings.temperature_shift));
      body.append("tint_shift", String(settings.tint_shift));
      body.append("curve_midpoint", String(curveMidpoint));
      const response = await fetch(apiBase + "/v1/media/native-measurements", { method: "POST", body });
      const payload = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(payload.detail || "Native measurements failed.");
      setMeasurementResult(payload);
      onNativeMeasurements?.({
        width: payload.frame.width,
        height: payload.frame.height,
        decoder: "YRGB native float32 grading pipeline",
        sample_domain: payload.scopes.sample_domain,
        analysis: {
          histograms: payload.scopes.analysis.histograms,
          rgb_parade: payload.scopes.analysis.rgb_parade,
          waveform: payload.scopes.analysis.waveform,
          vectorscope_points: payload.scopes.analysis.vectorscope_points,
          scope_note: payload.scope_axis + " · native validated linear working-space measurements; not IRE or nits.",
          note: "All scopes are calculated from the same native graded float32 frame used for Correction Accuracy.",
        },
      });
      setMeasurementStatus("Measurements calculated from the same validated native graded float32 frame.");
    } catch (error) {
      setMeasurementStatus(error instanceof Error ? error.message : "Native measurements failed.");
    } finally {
      setMeasurementBusy(false);
    }
  }


  async function exportNativeMaster() {
    if (!sourceFile || !profileId) return;
    setMasterBusy(true);
    setMasterStatus("Processing the full-resolution still in the native float32 pipeline…");
    try {
      const body = new FormData();
      body.append("file", sourceFile);
      body.append("profile_id", profileId);
      body.append("export_format", masterFormat);
      if (cameraModel) body.append("camera_model", cameraModel);
      body.append("exposure_stops", String(settings.exposure_stops));
      body.append("contrast", String(settings.contrast));
      body.append("pivot", String(settings.pivot));
      body.append("saturation", String(settings.saturation));
      body.append("temperature_shift", String(settings.temperature_shift));
      body.append("tint_shift", String(settings.tint_shift));
      body.append("curve_midpoint", String(curveMidpoint));
      const response = await fetch(apiBase + "/v1/media/native-grade-export", { method: "POST", body });
      if (!response.ok) {
        const payload = await response.json().catch(() => ({}));
        throw new Error(payload.detail || "Native master export failed.");
      }
      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = filename.replace(/\\.[^.]+$/, "") + "_YRGB_master." + (masterFormat === "exr" ? "exr" : "tiff");
      anchor.click();
      URL.revokeObjectURL(url);
      const width = response.headers.get("X-YRGB-Frame-Width") || "?";
      const height = response.headers.get("X-YRGB-Frame-Height") || "?";
      const digest = response.headers.get("X-YRGB-Float-Samples-SHA256") || "not supplied";
      setMasterStatus("Full-resolution float32 " + masterFormat.toUpperCase() + " exported · " + width + " × " + height + " · unclamped · sample SHA-256 " + digest.slice(0, 16) + "…");
    } catch (error) {
      setMasterStatus(error instanceof Error ? error.message : "Native master export failed.");
    } finally {
      setMasterBusy(false);
    }
  }

  function exportPreview() {
    const canvas = canvasRef.current;
    if (!canvas) return;
    canvas.toBlob(blob => {
      if (!blob) { setStatus("PNG export failed."); return; }
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = filename.replace(/\.[^.]+$/, "") + "_YRGB_grade_preview.png";
      anchor.click();
      URL.revokeObjectURL(url);
      setStatus("Graded preview PNG exported at " + canvas.width + " × " + canvas.height + ".");
    }, "image/png");
  }

  return <section className="interactive-grading-preview" aria-label="Interactive still image grading preview">
    <div className="grading-preview-heading">
      <div><b>LIVE IMAGE PREVIEW</b><span>{dimensions ? dimensions.width + " × " + dimensions.height + " · PREVIEW" : "NO IMAGE"}</span></div>
      <div className="grading-preview-actions"><button type="button" className="preview-reset-button" onClick={() => onReset?.()}>RESET GRADE</button><button type="button" className="preview-export-button" disabled={!dimensions} onClick={exportPreview}>EXPORT GRADED PNG</button></div>
    </div>
    <div className="grading-preview-screen">
      {sourceUrl ? <canvas ref={canvasRef} aria-label="Interactive graded image preview" /> : <span>Upload a still image to see grading changes.</span>}
    </div>
    <div className="grading-preview-status">{status}</div>
    <div className="native-grading-action">
      <button type="button" className="preview-export-button" disabled={!sourceFile || !profileId || nativeBusy} onClick={renderNativePreview}>
        {nativeBusy ? "RENDERING NATIVE…" : "RENDER THROUGH NATIVE ENGINE"}
      </button>
      <span>{nativeStatus}</span>
    </div>


    <div className="native-master-export">
      <div className="native-measurements-heading"><b>FULL-RESOLUTION FLOAT MASTER</b><span>NO DISPLAY CLAMP</span></div>
      <p>Exports the native graded scene-linear frame at source resolution. This is not the browser preview PNG. Only reference-validated camera transforms are accepted.</p>
      <div className="native-master-controls">
        <label htmlFor="yrgb-master-format">FORMAT</label>
        <select id="yrgb-master-format" value={masterFormat} onChange={event => setMasterFormat(event.target.value as "exr" | "tiff")}>
          <option value="exr">OpenEXR · float32</option>
          <option value="tiff">TIFF · float32</option>
        </select>
        <button type="button" className="preview-export-button" disabled={!sourceFile || !profileId || masterBusy} onClick={exportNativeMaster}>
          {masterBusy ? "EXPORTING FULL-RESOLUTION MASTER…" : "EXPORT FLOAT MASTER"}
        </button>
      </div>
      <span className="native-measurement-status">{masterStatus}</span>
    </div>
    <div className="native-measurements-panel">
      <div className="native-measurements-heading"><b>NATIVE SCOPE & CORRECTION MEASUREMENTS</b><span>VALIDATED LINEAR FRAME</span></div>
      <p>Choose a neutral reference ROI in the original still. Coordinates are full-resolution source pixels, not the resized browser preview. Minimum sample area: 16 pixels; the initial 1 × 1 values are placeholders, not a selected gray reference.</p>
      <div className="native-roi-grid">
        {(["x", "y", "width", "height"] as const).map(key => <label key={key}>{key.toUpperCase()}<input type="number" min={key === "width" || key === "height" ? 1 : 0} step="1" value={roi[key]} onChange={event => setRoi(current => ({ ...current, [key]: Math.max(0, Math.floor(Number(event.target.value) || 0)) }))} /></label>)}
      </div>
      <button type="button" className="preview-export-button" disabled={!sourceFile || !profileId || measurementBusy || roi.width * roi.height < 16} onClick={runNativeMeasurements}>
        {measurementBusy ? "MEASURING NATIVE FRAME…" : "MEASURE NATIVE GRADE"}
      </button>
      <span className="native-measurement-status">{measurementStatus}</span>
      {measurementResult && <>
        <div className="native-measurement-score">
          <div><small>CORRECTION ACCURACY</small><b>{measurementResult.correction_accuracy.score === null ? "NOT SCORED" : measurementResult.correction_accuracy.score.toFixed(1) + "%"}</b></div>
          <div><small>EXPOSURE DEVIATION</small><b>{formatMeasurement(measurementResult.correction_accuracy.exposure.metrics[0]?.deviation, 3) + " stops"}</b></div>
        </div>
        <div className="native-measurement-wb">
          {measurementResult.correction_accuracy.white_balance.metrics.map(metric => <div key={metric.name}><small>{metric.name.toUpperCase()}</small><b>{formatMeasurement(metric.measured)}</b></div>)}
        </div>
        <div className="native-scope-summary">
          <b>NATIVE SCOPE SIGNAL</b>
          <span>{measurementResult.frame.width} × {measurementResult.frame.height} · {measurementResult.scope_axis}</span>
          <div>{Object.entries(measurementResult.scopes.analysis.channels).map(([channel, stats]) => <span key={channel}>{channel}: mean {stats.mean.toFixed(4)} · min {stats.minimum.toFixed(4)} · max {stats.maximum.toFixed(4)}</span>)}</div>
          <span>Waveform: {measurementResult.scopes.analysis.waveform ? "available" : "unavailable"} · Vectorscope samples: {measurementResult.scopes.analysis.vectorscope_points?.length ?? 0}</span>
        </div>
      </>}
    </div>
    {nativePreviewUrl && <div className="native-grading-result">
      <b>NATIVE PIPELINE OUTPUT · DISPLAY PREVIEW</b>
      <img src={nativePreviewUrl} alt="Native float32 graded still-image preview" />
    </div>}
    <p className="grading-preview-caveat">Preview pipeline: browser-decoded sRGB → selected linear working space → look operations → sRGB display. This is a responsive creative preview, not a camera Log transform, validated OCIO pipeline, calibrated monitor output, or full-resolution master export. Camera Log images need an explicitly validated input transform before accuracy scoring.</p>
  </section>;
}
