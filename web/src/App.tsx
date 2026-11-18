import { useEffect, useMemo, useState } from "react";
import { Activity, Aperture, AudioWaveform, CheckCircle2, CircleHelp, Clapperboard, FileImage, Film, Gauge, LoaderCircle, MonitorPlay, ScanSearch, Settings2, UploadCloud } from "lucide-react";

const API_BASE = import.meta.env.VITE_YRGB_API_URL || "http://localhost:8000";

type Probe = { detected_type?: string; status?: string; signature?: string; warnings?: string[]; metadata?: Record<string, unknown> };
type ProbeResponse = { filename: string; size_bytes: number; probe: Probe };
type Profile = { id: string; manufacturer: string; encoding: string; gamut?: string; status: string; usable_for_transform?: boolean; camera_models?: string[] };
type ScopeHistogram = { counts: number[]; minimum: number; maximum: number; underflow: number; overflow: number };
type ScopeRaster = { counts: number[][]; width: number; height: number; minimum: number; maximum: number; underflow: number; overflow: number };
type AnalysisResponse = { width: number; height: number; decoder: string; timestamp_seconds?: number; sample_domain: string; analysis: { histograms: Record<string, ScopeHistogram>; rgb_parade: Record<string, ScopeRaster>; note: string } };
type VideoSampleFrame = { timestamp_seconds: number; frame_index: number; histogram_distance: number | null; channel_mean_delta: number[] | null; mean_luminance_delta: number | null; shot_change_candidate: boolean; channels: Record<string, { mean: number }> };
type VideoSampleReport = { frame_count: number; start_seconds: number; interval_seconds: number; shot_change_threshold: number | null; frames: VideoSampleFrame[]; note: string };

function formatBytes(bytes: number) {
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
}

function ScopePanel({ title, subtitle, icon, histograms, parades }: { title: string; subtitle: string; icon: React.ReactNode; histograms?: Record<string, ScopeHistogram>; parades?: Record<string, ScopeRaster> }) {
  const channels = ["R", "G", "B"] as const;
  const hasParade = !!parades && channels.every(channel => !!parades[channel]);
  const hasHistogram = !!histograms && channels.every(channel => !!histograms[channel]);
  const hasSignal = hasHistogram || hasParade;
  return <section className="scope-panel">
    <div className="panel-head"><div className="panel-title">{icon}<span>{title}</span></div><span className="scope-state">{hasSignal ? "SAMPLE DATA" : "NO SIGNAL"}</span></div>
    <div className={"scope-screen" + (hasParade ? " rgb-parade-screen" : "")}><div className="scope-grid"><span /><span /><span /><span /><span /><span /><span /><span /><span /></div>
      {hasHistogram ? <svg className="rgb-histogram" viewBox="0 0 128 100" preserveAspectRatio="none" role="img" aria-label="RGB channel histogram">
        {channels.map(channel => {
          const counts = histograms[channel].counts;
          const peak = Math.max(1, ...counts);
          const points = counts.map((count, index) => (index / Math.max(1, counts.length - 1) * 128) + "," + (96 - count / peak * 88)).join(" ");
          return <polyline key={channel} className={"histogram-" + channel.toLowerCase()} points={points} />;
        })}
      </svg>
      : hasParade ? <div className="rgb-parade-bands">{channels.map(channel => {
        const raster = parades[channel];
        return <div className={"parade-band parade-" + channel.toLowerCase()} key={channel}>
          <span className="parade-channel-label">{channel}</span>
          <svg viewBox={"0 0 " + raster.width + " " + raster.height} preserveAspectRatio="none" role="img" aria-label={channel + " channel parade"}>
            {raster.counts.flatMap((column, x) => column.map((count, y) => count > 0 ? <rect key={x + "-" + y} x={x} y={y} width="1" height="1" opacity={Math.min(1, 0.18 + count / 8)} /> : null))}
          </svg>
        </div>;
      })}</div>
      : <div className="scope-empty"><Activity size={19} /><span>Waiting for decoded frame</span></div>}
    </div>
    <div className="scope-foot">{subtitle}{hasHistogram ? " · R/G/B · 128 bins · under/over R " + histograms.R.underflow + "/" + histograms.R.overflow + " · G " + histograms.G.underflow + "/" + histograms.G.overflow + " · B " + histograms.B.underflow + "/" + histograms.B.overflow : hasParade ? " · R/G/B channels · source range under/over: " + channels.map(channel => parades[channel].underflow + "/" + parades[channel].overflow).join(" · ") : ""}</div>
  </section>;
}

export default function App() {
  const [apiOnline, setApiOnline] = useState(false);
  const [file, setFile] = useState<File | null>(null);
  const [previewUrl, setPreviewUrl] = useState("");
  const [probe, setProbe] = useState<ProbeResponse | null>(null);
  const [analysis, setAnalysis] = useState<AnalysisResponse | null>(null);
  const [analysisNote, setAnalysisNote] = useState("");
  const [frameTimestamp, setFrameTimestamp] = useState("0");
  const [sampleInterval, setSampleInterval] = useState("1");
  const [sampleCount, setSampleCount] = useState("8");
  const [sampleReport, setSampleReport] = useState<VideoSampleReport | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [manufacturer, setManufacturer] = useState("Sony");
  const [encoding, setEncoding] = useState("S-Log3");
  const [gamut, setGamut] = useState("");
  const [profiles, setProfiles] = useState<Profile[]>([]);
  const [profileNote, setProfileNote] = useState("");
  const [lutFile, setLutFile] = useState<File | null>(null);
  const [lutSize, setLutSize] = useState("35");
  const [lutNote, setLutNote] = useState("");
  const [lutBusy, setLutBusy] = useState(false);

  useEffect(() => {
    let active = true;
    fetch(`${API_BASE}/health`).then(r => r.ok).then(ok => { if (active) setApiOnline(ok); }).catch(() => { if (active) setApiOnline(false); });
    return () => { active = false; };
  }, []);

  useEffect(() => {
    if (!file) { setPreviewUrl(""); return; }
    const url = URL.createObjectURL(file);
    setPreviewUrl(url);
    return () => URL.revokeObjectURL(url);
  }, [file]);

  const isVideo = useMemo(() => !!file && (file.type.startsWith("video/") || /\.(mov|mxf|mp4|mkv|avi)$/i.test(file.name)), [file]);
  const isImage = useMemo(() => !!file && (file.type.startsWith("image/") || /\.(dng|tif|tiff|exr|dpx|png|jpe?g)$/i.test(file.name)), [file]);

  async function inspectMedia(selected: File) {
    setFile(selected); setProbe(null); setAnalysis(null); setSampleReport(null); setAnalysisNote(""); setFrameTimestamp("0"); setError(""); setBusy(true);
    try {
      const body = new FormData(); body.append("file", selected);
      const response = await fetch(`${API_BASE}/v1/media/probe`, { method: "POST", body });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "Media inspection failed");
      setProbe(data as ProbeResponse);
      const lowerName = selected.name.toLowerCase();
      const imageLike = selected.type.startsWith("image/") || [".dng", ".tif", ".tiff", ".exr", ".dpx", ".png", ".jpg", ".jpeg"].some(ext => lowerName.endsWith(ext));
      if (imageLike) {
        setAnalysisNote("Decoding high-precision still image for sample-domain scopes…");
        const analysisBody = new FormData(); analysisBody.append("file", selected);
        const analysisResponse = await fetch(API_BASE + "/v1/media/analyze", { method: "POST", body: analysisBody });
        const analysisData = await analysisResponse.json();
        if (!analysisResponse.ok) setAnalysisNote(analysisData.detail || "Precision decoder unavailable. Install the OpenImageIO extra.");
        else { setAnalysis(analysisData as AnalysisResponse); setAnalysisNote("Decoded by engine. Values are source sample-domain measurements; no input transform or IRE scale is assumed."); }
      } else if (selected.type.startsWith("video/") || /\.(mov|mxf|mp4|mkv|avi)$/i.test(selected.name)) {
        setAnalysisNote("Decoding video frame at 0.0 seconds…");
        const frameBody = new FormData(); frameBody.append("file", selected);
        const frameResponse = await fetch(API_BASE + "/v1/media/video-frame?timestamp_seconds=0", { method: "POST", body: frameBody });
        const frameData = await frameResponse.json();
        if (!frameResponse.ok) setAnalysisNote(frameData.detail || "Video frame decoder unavailable. Install FFmpeg and NumPy.");
        else { setAnalysis(frameData as AnalysisResponse); setAnalysisNote("Frame decoded at 0.0s by FFmpeg. Source sample-domain measurements only; no camera transform or IRE scale is assumed."); }
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not reach the media API");
    } finally { setBusy(false); }
  }

  async function findProfiles(event: React.FormEvent) {
    event.preventDefault(); setProfileNote("Searching profile registry…"); setProfiles([]);
    const params = new URLSearchParams({ manufacturer, encoding });
    if (gamut.trim()) params.set("gamut", gamut.trim());
    try {
      const response = await fetch(`${API_BASE}/v1/profiles/candidates?${params}`);
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "Profile lookup failed");
      setProfiles(data.candidates || []);
      setProfileNote(data.note || "Candidates found. No transform was selected.");
    } catch (err) { setProfileNote(err instanceof Error ? err.message : "Profile lookup unavailable"); }
  }

  return <main className="app-shell">
    <header className="topbar">
      <div className="brand"><div className="brand-mark"><Aperture size={20} /></div><div><div className="brand-name">COLORIST <b>YRGB</b></div><div className="brand-sub">UNIVERSAL COLOR ENGINE</div></div></div>
      <div className="topbar-center"><span className="workspace-dot" /> MEDIA INTELLIGENCE WORKSPACE <span className="version">EARLY ACCESS · 0.1</span></div>
      <div className="topbar-right"><span className={apiOnline ? "api-status online" : "api-status"}><i />{apiOnline ? "ENGINE CONNECTED" : "ENGINE OFFLINE"}</span><button className="icon-button" title="Settings"><Settings2 size={17} /></button></div>
    </header>

    <div className="workspace">
      <aside className="sidebar">
        <div className="side-label">WORKSPACE</div>
        <div className="nav-item active"><MonitorPlay size={17} /> Media Analysis</div>
        <div className="nav-item disabled"><Clapperboard size={17} /> Color Grading <small>SOON</small></div>
        <div className="nav-item disabled"><Gauge size={17} /> Shot Matching <small>SOON</small></div>
        <div className="side-divider" />
        <div className="side-label">TOOLS</div>
        <div className="nav-item"><ScanSearch size={17} /> Camera Profiles</div>
        <div className="nav-item"><AudioWaveform size={17} /> Scopes</div>
        <div className="side-note"><CircleHelp size={15} /><span>Analysis only. No unverified camera transform is applied.</span></div>
        <div className="sidebar-bottom"><span className="engine-indicator" /> ENGINE BUILD 0.1.0</div>
      </aside>

      <section className="main-content">
        <div className="page-heading"><div><div className="eyebrow">COLOR WORKFLOW / 01</div><h1>Media Intelligence</h1><p>Inspect image and video sources before entering the grading pipeline.</p></div><div className="pipeline-pill"><span>INPUT</span><b>→</b><span className="current">ANALYSIS</span><b>→</b><span>GRADE</span><b>→</b><span>OUTPUT</span></div></div>

        <div className="content-grid">
          <section className="card media-card">
            <div className="card-heading"><div><span className="section-kicker">SOURCE</span><h2>Media Input</h2></div><span className="subtle-tag">IMAGE + VIDEO</span></div>
            <label className="drop-zone" htmlFor="media-file">
              <input id="media-file" type="file" accept="image/*,video/*,.dng,.exr,.dpx,.mxf,.mkv,.mov,.cube" onChange={e => { const selected = e.target.files?.[0]; if (selected) void inspectMedia(selected); }} />
              <div className="upload-icon"><UploadCloud size={23} /></div><strong>Drop media here or <em>browse files</em></strong><span>Still images · Video clips · Image sequences (sequence support pending)</span><span className="upload-limit">MAX UPLOAD 512 MB · SERVER TEMP FILE REMOVED AFTER PROBE</span>
            </label>
            {error && <div className="error-message">{error}</div>}
            {file && <div className="media-result">
              <div className="media-preview">{previewUrl && isVideo ? <video src={previewUrl} controls /> : previewUrl && isImage ? <img src={previewUrl} alt="Local media preview" /> : <div className="unsupported-preview"><FileImage size={26} /><span>Browser preview unavailable</span></div>}</div>
              <div className="media-meta"><div className="file-title">{isVideo ? <Film size={15} /> : <FileImage size={15} />}<b>{file.name}</b></div><span>{formatBytes(file.size)} · {file.type || "Unknown MIME type"}</span>
                {busy ? <span className="processing"><LoaderCircle size={14} /> Inspecting media metadata…</span> : probe ? <span className="success-line"><CheckCircle2 size={14} /> Probe complete · {probe.probe.status || "unknown"}</span> : null}
              </div>
              {probe && <div className="probe-details"><div><small>DETECTED TYPE</small><b>{probe.probe.detected_type || "Unknown"}</b></div><div><small>FILE SIGNATURE</small><b>{probe.probe.signature || "Unknown"}</b></div><div><small>PROBE STATUS</small><b>{probe.probe.status || "Unknown"}</b></div></div>}
              {probe?.probe.warnings?.length ? <div className="warning-line">{probe.probe.warnings.join(" · ")}</div> : null}
              {isVideo && <div className="video-frame-control">
                <label>FRAME TIME (SECONDS)<input type="number" min="0" max="86400" step="0.1" value={frameTimestamp} onChange={e => setFrameTimestamp(e.target.value)} /></label>
                <button type="button" disabled={busy || !apiOnline || !Number.isFinite(Number(frameTimestamp)) || Number(frameTimestamp) < 0} onClick={async () => {
                  if (!file) return;
                  setBusy(true); setAnalysis(null); setAnalysisNote("Decoding frame at " + frameTimestamp + " seconds…");
                  try {
                    const frameBody = new FormData(); frameBody.append("file", file);
                    const frameResponse = await fetch(API_BASE + "/v1/media/video-frame?timestamp_seconds=" + encodeURIComponent(frameTimestamp), { method: "POST", body: frameBody });
                    const frameData = await frameResponse.json();
                    if (!frameResponse.ok) throw new Error(frameData.detail || "Video frame analysis failed");
                    setAnalysis(frameData as AnalysisResponse);
                    setAnalysisNote("Frame decoded at " + frameTimestamp + "s. Source sample-domain values; no camera transform or IRE scale is assumed.");
                  } catch (err) { setAnalysisNote(err instanceof Error ? err.message : "Video frame analysis failed"); }
                  finally { setBusy(false); }
                }}>Analyze frame</button>
              </div>}
              {isVideo && <div className="video-sample-control">
                <div className="sample-control-heading"><b>Temporal Sample Analysis</b><span>BOUNDED FRAME SCAN</span></div>
                <div className="sample-control-fields">
                  <label>INTERVAL (SEC)<input type="number" min="0.1" max="60" step="0.1" value={sampleInterval} onChange={e => setSampleInterval(e.target.value)} /></label>
                  <label>FRAME COUNT (1–24)<input type="number" min="1" max="24" step="1" value={sampleCount} onChange={e => setSampleCount(e.target.value)} /></label>
                  <button type="button" disabled={busy || !apiOnline || !Number.isFinite(Number(sampleInterval)) || Number(sampleInterval) <= 0 || !Number.isInteger(Number(sampleCount)) || Number(sampleCount) < 1 || Number(sampleCount) > 24} onClick={async () => {
                    if (!file) return;
                    setBusy(true); setSampleReport(null); setAnalysisNote("Sampling video frames and comparing adjacent histograms…");
                    try {
                      const body = new FormData(); body.append("file", file);
                      const params = new URLSearchParams({ start_seconds: frameTimestamp, interval_seconds: sampleInterval, frame_count: sampleCount, shot_change_threshold: "0.35" });
                      const response = await fetch(API_BASE + "/v1/media/video-sample?" + params.toString(), { method: "POST", body });
                      const data = await response.json();
                      if (!response.ok) throw new Error(data.detail || "Video sample analysis failed");
                      setSampleReport(data as VideoSampleReport);
                      setAnalysisNote("Temporal sample complete. Shot flags are histogram-change candidates, not confirmed scene cuts.");
                    } catch (err) { setAnalysisNote(err instanceof Error ? err.message : "Video sample analysis failed"); }
                    finally { setBusy(false); }
                  }}>Analyze sequence</button>
                </div>
                {sampleReport && <div className="sample-report">
                  <div className="sample-report-summary"><b>{sampleReport.frame_count} frames analyzed</b><span>{sampleReport.frames.filter(frame => frame.shot_change_candidate).length} change candidates</span></div>
                  <div className="sample-frame-list">{sampleReport.frames.map(frame => <div className="sample-frame-row" key={frame.frame_index}>
                    <span>#{String(frame.frame_index + 1).padStart(2, "0")} · {frame.timestamp_seconds.toFixed(2)}s</span>
                    <span>Δ histogram {frame.histogram_distance === null ? "—" : frame.histogram_distance.toFixed(3)}</span>
                    {frame.shot_change_candidate ? <b className="candidate-flag">CHANGE CANDIDATE</b> : <small>—</small>}
                  </div>)}</div>
                  <p>{sampleReport.note}</p>
                </div>}
              </div>}
            </div>}
            <div className="format-row"><span>SUPPORTED BY DECODER DEPENDENCIES</span><b>JPEG</b><b>PNG</b><b>TIFF</b><b>EXR</b><b>RAW*</b><b>PRORES*</b><small>* Optional decoder / codec support</small></div>
          </section>

          <section className="card profile-card">
            <div className="card-heading"><div><span className="section-kicker">INPUT TRANSFORM RESEARCH</span><h2>Camera Profile</h2></div><ScanSearch size={18} className="muted-icon" /></div>
            <form onSubmit={findProfiles} className="profile-form">
              <label>MANUFACTURER<input value={manufacturer} onChange={e => setManufacturer(e.target.value)} placeholder="e.g. Sony" required /></label>
              <label>LOG / GAMMA ENCODING<input value={encoding} onChange={e => setEncoding(e.target.value)} placeholder="e.g. S-Log3" /></label>
              <label>COLOR GAMUT <span className="optional">OPTIONAL FILTER</span><input value={gamut} onChange={e => setGamut(e.target.value)} placeholder="e.g. S-Gamut3.Cine" /></label>
              <button className="primary-button" type="submit" disabled={!apiOnline}><ScanSearch size={15} /> Find exact candidates</button>
            </form>
            {profileNote && <p className="profile-note">{profileNote}</p>}
            {profiles.map(profile => <div className="profile-result" key={profile.id}><div><b>{profile.encoding} · {profile.gamut || "Gamut unspecified"}</b><small>{profile.manufacturer} / {profile.id}</small></div><span className={profile.usable_for_transform ? "verified" : "unverified"}>{profile.status}</span></div>)}
            <div className="profile-warning">Profile discovery does not apply a transform. Verify camera model, gamut and transfer function before processing.</div>
          </section>
        </div>

        <div className="section-header"><div><span className="section-kicker">SIGNAL MONITORING</span><h2>Scopes & Diagnostics</h2></div><span className="subtle-tag">{analysis ? "ENGINE DECODED · SAMPLE DOMAIN" : "AWAITING DECODED FRAME"}</span></div>
        {analysisNote && <div className="analysis-note">{analysisNote}</div>}
        <div className="scope-grid-layout">
          <ScopePanel title="Waveform" subtitle="Luma / RGB · explicit coefficients required" icon={<Activity size={15} />} />
          <ScopePanel title="RGB Parade" subtitle="Separate R / G / B channel density · decoded source values" icon={<AudioWaveform size={15} />} parades={analysis?.analysis.rgb_parade} />
          <ScopePanel title="RGB Histogram" subtitle="Overlaid R / G / B distributions · source code-value range 0–1" icon={<Gauge size={15} />} histograms={analysis?.analysis.histograms} />
          <ScopePanel title="Vectorscope" subtitle="Cb / Cr · explicit matrix required" icon={<Aperture size={15} />} />
        </div>
        <section className="card lut-export-card">
          <div className="card-heading"><div><span className="section-kicker">LOOK DELIVERY</span><h2>3D LUT Export</h2></div><span className="subtle-tag">.CUBE · 3D GRID</span></div>
          <p className="lut-export-description">Import a developed .cube look and resample it for delivery. The engine preserves the source LUT domain and evaluates its transform at the selected grid density.</p>
          <div className="lut-export-controls">
            <label className="lut-file-picker">SOURCE LOOK (.CUBE)<input type="file" accept=".cube,text/plain" onChange={e => { setLutFile(e.target.files?.[0] || null); setLutNote(""); }} /><span>{lutFile ? lutFile.name : "Choose a .cube look…"}</span></label>
            <label>EXPORT GRID<select value={lutSize} onChange={e => setLutSize(e.target.value)}><option value="17">17 Point</option><option value="33">33 Point</option><option value="35">35 Point</option><option value="65">65 Point</option></select></label>
            <button type="button" className="primary-button" disabled={!apiOnline || !lutFile || lutBusy} onClick={async () => {
              if (!lutFile) return;
              setLutBusy(true); setLutNote("Generating " + lutSize + "-point 3D LUT…");
              try {
                const body = new FormData(); body.append("file", lutFile);
                const response = await fetch(API_BASE + "/v1/lut/export?size=" + lutSize + "&title=" + encodeURIComponent(lutFile.name.replace(/\.cube$/i, "")), { method: "POST", body });
                if (!response.ok) { const data = await response.json(); throw new Error(data.detail || "LUT export failed"); }
                const blob = await response.blob();
                const url = URL.createObjectURL(blob);
                const anchor = document.createElement("a"); anchor.href = url; anchor.download = lutFile.name.replace(/\.cube$/i, "") + "_" + lutSize + "pt.cube"; anchor.click(); URL.revokeObjectURL(url);
                setLutNote("Export generated. Confirm the LUT input/output color-space contract before using it in another application.");
              } catch (err) { setLutNote(err instanceof Error ? err.message : "LUT export failed"); }
              finally { setLutBusy(false); }
            }}>{lutBusy ? "Generating…" : "Export .cube LUT"}</button>
          </div>
          {lutNote && <div className="lut-export-note">{lutNote}</div>}
          <div className="lut-grid-info"><span>35 POINT <b>42,875</b> RGB entries</span><span>65 POINT <b>274,625</b> RGB entries</span></div>
        </section>
        <div className="bottom-disclaimer"><span>ENGINE NOTE</span> Browser preview is not a color-managed reference display. Histogram and parade show decoded source sample values only. No camera transform, IRE scale, luminance interpretation or calibrated vectorscope is inferred.</div>
      </section>
    </div>
  </main>;
}