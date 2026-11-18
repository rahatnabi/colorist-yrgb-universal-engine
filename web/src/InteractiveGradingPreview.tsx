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

type Props = {
  sourceUrl: string;
  filename: string;
  settings: InteractiveLookSettings;
  curveMidpoint: number;
  workingSpaceId: "scene-linear-rec709" | "acescg-linear";
  onRender?: (result: InteractivePreviewAnalysis) => void;
  onReset?: () => void;
};

export default function InteractiveGradingPreview({ sourceUrl, filename, settings, curveMidpoint, workingSpaceId, onRender, onReset }: Props) {
  const onRenderRef = useRef(onRender);
  onRenderRef.current = onRender;
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const sourceCanvasRef = useRef<HTMLCanvasElement | null>(null);
  const [status, setStatus] = useState("Waiting for a browser-decodable still image");
  const [dimensions, setDimensions] = useState<{ width: number; height: number } | null>(null);

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
    <p className="grading-preview-caveat">Preview pipeline: browser-decoded sRGB → selected linear working space → look operations → sRGB display. This is a responsive creative preview, not a camera Log transform, validated OCIO pipeline, calibrated monitor output, or full-resolution master export. Camera Log images need an explicitly validated input transform before accuracy scoring.</p>
  </section>;
}
