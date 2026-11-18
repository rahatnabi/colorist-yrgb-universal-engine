import { useEffect, useRef, useState } from "react";
import { applyInteractiveLook, type InteractiveLookSettings } from "./grading";

type Props = {
  sourceUrl: string;
  filename: string;
  settings: InteractiveLookSettings;
  curveMidpoint: number;
};

export default function InteractiveGradingPreview({ sourceUrl, filename, settings, curveMidpoint }: Props) {
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
    const graded = applyInteractiveLook(pixels, { settings, curve_midpoint: curveMidpoint });
    context.putImageData(graded, 0, 0);
  }, [settings, curveMidpoint, dimensions]);

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
      <button type="button" className="preview-export-button" disabled={!dimensions} onClick={exportPreview}>EXPORT GRADED PNG</button>
    </div>
    <div className="grading-preview-screen">
      {sourceUrl ? <canvas ref={canvasRef} aria-label="Interactive graded image preview" /> : <span>Upload a still image to see grading changes.</span>}
    </div>
    <div className="grading-preview-status">{status}</div>
    <p className="grading-preview-caveat">Preview pipeline: browser-decoded sRGB → linear-sRGB look operations → sRGB display. This is a responsive creative preview, not a camera Log transform, validated OCIO pipeline, calibrated monitor output, or full-resolution master export. Camera Log images need an explicitly validated input transform before accuracy scoring.</p>
  </section>;
}
