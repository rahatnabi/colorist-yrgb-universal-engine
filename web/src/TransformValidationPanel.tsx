import { useState } from "react";

type ValidationAudit = {
  passed: boolean;
  profile_id: string;
  transform_id: string;
  source_space: string;
  destination_space: string;
  reference_set_id: string;
  vector_count: number;
  max_absolute_error: number;
  tolerance: number;
  config_sha256: string;
  ocio_version: string;
  promotion_status: string;
  next_step: string;
};

export default function TransformValidationPanel({ apiBase }: { apiBase: string }) {
  const [manifest, setManifest] = useState<File | null>(null);
  const [tolerance, setTolerance] = useState("0.00001");
  const [busy, setBusy] = useState(false);
  const [audit, setAudit] = useState<ValidationAudit | null>(null);
  const [error, setError] = useState("");

  async function validate() {
    if (!manifest) return;
    setBusy(true);
    setAudit(null);
    setError("");
    try {
      const body = new FormData();
      body.append("manifest_file", manifest);
      const params = new URLSearchParams({ tolerance });
      const response = await fetch(apiBase + "/v1/transforms/validate-reference?" + params.toString(), {
        method: "POST",
        body,
      });
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.detail || "Reference validation failed.");
      setAudit(payload as ValidationAudit);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Reference validation failed.");
    } finally {
      setBusy(false);
    }
  }

  return <section className="transform-validation-panel">
    <div className="camera-metadata-heading"><b>CAMERA TRANSFORM VALIDATION</b><span>MEASURED REFERENCES ONLY</span></div>
    <p>Upload a traceable JSON manifest containing independently measured camera RGB reference vectors. The API compares the exact profile transform against the pinned server OCIO config.</p>
    <label className="camera-sidecar-picker">REFERENCE MANIFEST (.JSON)
      <input type="file" accept=".json,application/json" onChange={event => {
        setManifest(event.target.files?.[0] || null);
        setAudit(null);
        setError("");
      }} />
      <span>{manifest ? manifest.name : "Choose a measured reference manifest. Empty templates and synthetic vectors cannot approve a camera transform."}</span>
    </label>
    <div className="transform-validation-actions">
      <label>TOLERANCE
        <input type="number" min="0.0000001" max="0.01" step="0.000001" value={tolerance} onChange={event => setTolerance(event.target.value)} />
      </label>
      <button type="button" className="profile-select-button" disabled={!manifest || busy || !Number.isFinite(Number(tolerance)) || Number(tolerance) <= 0 || Number(tolerance) > 0.01} onClick={() => void validate()}>
        {busy ? "Validating…" : "Validate transform"}
      </button>
    </div>
    {error && <p className="transform-validation-error">{error}</p>}
    {audit && <div className="transform-validation-result">
      <div className="transform-validation-result-heading"><b>{audit.passed ? "REFERENCE VECTORS PASSED" : "REFERENCE VECTORS FAILED"}</b><span>{audit.promotion_status.replaceAll("_", " ").toUpperCase()}</span></div>
      <div className="camera-metadata-grid">
        <div><small>Profile</small><b>{audit.profile_id}</b></div>
        <div><small>Reference set</small><b>{audit.reference_set_id}</b></div>
        <div><small>Vectors</small><b>{audit.vector_count}</b></div>
        <div><small>Maximum RGB error</small><b>{audit.max_absolute_error.toExponential(3)}</b></div>
        <div><small>Tolerance</small><b>{audit.tolerance.toExponential(3)}</b></div>
        <div><small>OCIO version</small><b>{audit.ocio_version}</b></div>
      </div>
      <p>{audit.next_step}</p>
      <details><summary>Validation identity and config hash</summary><pre>{JSON.stringify({
        transform_id: audit.transform_id,
        source_space: audit.source_space,
        destination_space: audit.destination_space,
        config_sha256: audit.config_sha256,
      }, null, 2)}</pre></details>
    </div>}
  </section>;
}
