import { useEffect, useMemo, useState } from "react";
import { BookOpen, CheckCircle2, Circle, Download, FileImage, GraduationCap, LockKeyhole, Send, Trophy } from "lucide-react";

type Lesson = {
  id: string; unit: number; level: "beginner" | "intermediate" | "advanced";
  title: string; outcome: string; concepts: string[]; practical_task: string; evidence: string[];
};
type Exercise = {
  id: string; lesson_id: string; level: string; kind: string; title: string; brief: string;
  required_evidence: string[]; assessment_mode: string; reference_asset_status: string;
};
type Progress = {
  completed_lesson_count: number; submission_count: number;
  completed_lessons: { lesson_id: string; completed_at: string }[];
  submissions: { id: string; exercise_id: string; assessment_status: string; created_at: string; image_filename?: string }[];
};

const emptyProgress: Progress = { completed_lesson_count: 0, submission_count: 0, completed_lessons: [], submissions: [] };

export default function GuidedLearningSchool({ apiBase }: { apiBase: string }) {
  const [learnerId] = useState(() => {
    const key = "yrgb-learning-learner-id";
    let value = localStorage.getItem(key);
    if (!value) { value = globalThis.crypto?.randomUUID?.() || "learner-" + Math.random().toString(36).slice(2); localStorage.setItem(key, value); }
    return value;
  });
  const [lessons, setLessons] = useState<Lesson[]>([]);
  const [exercises, setExercises] = useState<Exercise[]>([]);
  const [progress, setProgress] = useState<Progress>(emptyProgress);
  const [selectedLessonId, setSelectedLessonId] = useState("");
  const [selectedExerciseId, setSelectedExerciseId] = useState("");
  const [evidence, setEvidence] = useState("");
  const [submissionFile, setSubmissionFile] = useState<File | null>(null);
  const [profileId, setProfileId] = useState("");
  const [roi, setRoi] = useState({ x: "", y: "", width: "", height: "" });
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");

  const selectedLesson = lessons.find(item => item.id === selectedLessonId) || lessons[0];
  const lessonExercises = useMemo(() => exercises.filter(item => item.lesson_id === selectedLesson?.id), [exercises, selectedLesson?.id]);
  const selectedExercise = lessonExercises.find(item => item.id === selectedExerciseId) || lessonExercises[0];
  const completedIds = new Set(progress.completed_lessons.map(item => item.lesson_id));

  async function refreshProgress() {
    const response = await fetch(`${apiBase}/v1/learning/progress?learner_id=${encodeURIComponent(learnerId)}`);
    if (response.ok) setProgress(await response.json() as Progress);
  }

  useEffect(() => {
    let active = true;
    Promise.all([
      fetch(apiBase + "/v1/learning/curriculum").then(response => { if (!response.ok) throw new Error("Curriculum unavailable"); return response.json(); }),
      fetch(apiBase + "/v1/learning/exercises").then(response => { if (!response.ok) throw new Error("Exercises unavailable"); return response.json(); }),
      fetch(apiBase + "/v1/learning/progress?learner_id=" + encodeURIComponent(learnerId)).then(response => { if (!response.ok) throw new Error("Progress unavailable"); return response.json(); }),
    ]).then(([curriculum, exerciseData, progressData]) => {
      if (!active) return;
      setLessons(curriculum.lessons || []);
      setExercises(exerciseData.exercises || []);
      setProgress(progressData as Progress);
      setSelectedLessonId((curriculum.lessons || [])[0]?.id || "");
    }).catch(reason => { if (active) setError(reason instanceof Error ? reason.message : "Learning data unavailable"); });
    return () => { active = false; };
  }, [apiBase, learnerId]);

  useEffect(() => {
    setSelectedExerciseId("");
    setEvidence("");
    setSubmissionFile(null);
    setNotice("");
  }, [selectedLessonId]);

  async function markComplete() {
    if (!selectedLesson) return;
    setBusy(true); setError(""); setNotice("");
    try {
      const body = new FormData(); body.append("learner_id", learnerId);
      const response = await fetch(`${apiBase}/v1/learning/lessons/${encodeURIComponent(selectedLesson.id)}/complete`, { method: "POST", body });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "Could not update lesson progress");
      await refreshProgress(); setNotice("Lesson completion saved.");
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Progress save failed"); }
    finally { setBusy(false); }
  }

  async function submitExercise() {
    if (!selectedExercise) return;
    setBusy(true); setError(""); setNotice("");
    try {
      const body = new FormData();
      body.append("learner_id", learnerId);
      body.append("exercise_id", selectedExercise.id);
      body.append("evidence", evidence);
      if (submissionFile) body.append("file", submissionFile);
      if (profileId.trim()) body.append("profile_id", profileId.trim());
      if (Object.values(roi).every(value => value.trim() !== "")) {
        body.append("roi_x", roi.x); body.append("roi_y", roi.y);
        body.append("roi_width", roi.width); body.append("roi_height", roi.height);
      }
      const response = await fetch(apiBase + "/v1/learning/submissions", { method: "POST", body });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "Submission failed");
      setNotice(data.assessment?.note || "Exercise submission saved.");
      await refreshProgress();
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Submission failed"); }
    finally { setBusy(false); }
  }

  function downloadPracticeStill() {
    const anchor = document.createElement("a");
    anchor.href = apiBase + "/v1/learning/assets/neutral-practice-chart.png";
    anchor.download = "yrgb-neutral-practice-chart.png";
    document.body.appendChild(anchor); anchor.click(); anchor.remove();
  }

  return <div className="learning-school">
    <div className="learning-hero">
      <div><div className="eyebrow">COLORIST YRGB / LEARNING SCHOOL</div><h1>Guided Still-Image Exercises</h1><p>Learn the pipeline, practice with stills, submit evidence and track your progress.</p></div>
      <div className="learning-progress-card"><Trophy size={19} /><div><strong>{progress.completed_lesson_count} / {lessons.length}</strong><span>LESSONS COMPLETED</span></div><div className="learning-progress-track"><i style={{ width: `${lessons.length ? progress.completed_lesson_count / lessons.length * 100 : 0}%` }} /></div><small>{progress.submission_count} exercise submissions</small></div>
    </div>

    {error && <div className="learning-alert error">{error}</div>}
    {notice && <div className="learning-alert success">{notice}</div>}

    <div className="learning-layout">
      <aside className="learning-lesson-list">
        <div className="learning-section-title"><BookOpen size={16} /> CURRICULUM</div>
        {(["beginner", "intermediate", "advanced"] as const).map(level => <div className="learning-level" key={level}>
          <div className="learning-level-label">{level.toUpperCase()}</div>
          {lessons.filter(item => item.level === level).map(lesson => <button key={lesson.id} type="button" className={"learning-lesson-link" + (selectedLesson?.id === lesson.id ? " selected" : "")} onClick={() => setSelectedLessonId(lesson.id)}>
            {completedIds.has(lesson.id) ? <CheckCircle2 size={15} /> : <Circle size={15} />}<span>{lesson.title}</span>
          </button>)}
        </div>)}
      </aside>

      <section className="learning-lesson-content">
        {selectedLesson ? <>
          <div className="learning-lesson-heading"><span className="subtle-tag">UNIT {String(selectedLesson.unit + 1).padStart(2, "0")} · {selectedLesson.level.toUpperCase()}</span><h2>{selectedLesson.title}</h2><p>{selectedLesson.outcome}</p></div>
          <div className="learning-content-block"><h3>KEY CONCEPTS</h3><div className="learning-concepts">{selectedLesson.concepts.map(item => <span key={item}>{item}</span>)}</div></div>
          <div className="learning-content-block"><h3>GUIDED PRACTICE</h3><p>{selectedLesson.practical_task}</p><div className="learning-evidence-list">{selectedLesson.evidence.map(item => <span key={item}><CheckCircle2 size={13} /> {item}</span>)}</div>
            <button type="button" className="learning-secondary-button" onClick={downloadPracticeStill}><Download size={15} /> DOWNLOAD SYNTHETIC PRACTICE STILL</button>
            <small className="learning-disclaimer">Educational sample only. This generated chart is not a measured camera reference and cannot validate a camera transform.</small>
          </div>

          <div className="learning-content-block">
            <div className="learning-block-heading"><h3>EXERCISE SUBMISSION</h3><span>{lessonExercises.length} AVAILABLE</span></div>
            {lessonExercises.length ? <>
              <label className="learning-field">SELECT EXERCISE<select value={selectedExercise?.id || ""} onChange={event => setSelectedExerciseId(event.target.value)}>{lessonExercises.map(item => <option value={item.id} key={item.id}>{item.title}</option>)}</select></label>
              {selectedExercise && <>
                <div className="learning-exercise-brief"><strong>{selectedExercise.title}</strong><p>{selectedExercise.brief}</p><small>ASSESSMENT · {selectedExercise.assessment_mode.replaceAll("_", " ").toUpperCase()}</small></div>
                <label className="learning-field">YOUR EVIDENCE / REFLECTION<textarea value={evidence} onChange={event => setEvidence(event.target.value)} placeholder="Describe your process, observations, measurement evidence and decisions…" rows={4} /></label>
                {selectedExercise.kind !== "knowledge" && <label className="learning-field">YOUR GRADED STILL<input type="file" accept="image/*,.dng,.tif,.tiff,.exr,.dpx" onChange={event => setSubmissionFile(event.target.files?.[0] || null)} /></label>}
                {selectedExercise.assessment_mode === "correction_accuracy" && <details className="learning-advanced-fields"><summary>Native assessment evidence (optional)</summary>
                  <label className="learning-field">VALIDATED PROFILE ID<input value={profileId} onChange={event => setProfileId(event.target.value)} placeholder="Exact registry profile ID" /></label>
                  <div className="learning-roi-grid">{(["x", "y", "width", "height"] as const).map(key => <label className="learning-field" key={key}>ROI {key.toUpperCase()}<input type="number" min="0" value={roi[key]} onChange={event => setRoi(current => ({ ...current, [key]: event.target.value }))} /></label>)}</div>
                </details>}
                <button type="button" className="primary-button learning-submit" disabled={busy || evidence.trim().length < 10 || (selectedExercise.kind !== "knowledge" && !submissionFile)} onClick={() => void submitExercise()}><Send size={15} /> {busy ? "SAVING…" : "SUBMIT EXERCISE"}</button>
              </>}
            </> : <div className="learning-empty"><GraduationCap size={22} /><p>No interactive exercise is attached to this lesson yet. The lesson task and evidence checklist are ready for practice.</p></div>}
          </div>
          <button type="button" className="learning-complete-button" disabled={busy || completedIds.has(selectedLesson.id)} onClick={() => void markComplete()}>{completedIds.has(selectedLesson.id) ? <><CheckCircle2 size={16} /> LESSON COMPLETED</> : <><CheckCircle2 size={16} /> MARK LESSON COMPLETE</>}</button>
        </> : <div className="learning-empty">Loading learning curriculum…</div>}
      </section>
    </div>

    <section className="learning-history">
      <div className="learning-block-heading"><h3><FileImage size={15} /> SUBMISSION HISTORY</h3><span>{progress.submission_count} SAVED</span></div>
      {progress.submissions.length ? <div className="learning-history-list">{progress.submissions.map(item => <div className="learning-history-item" key={item.id}><div><strong>{item.exercise_id}</strong><small>{new Date(item.created_at).toLocaleString()}</small></div><span>{item.assessment_status.replaceAll("_", " ").toUpperCase()}</span></div>)}</div> : <p className="learning-history-empty">Your exercise submissions will appear here.</p>}
    </section>
    <div className="learning-assessment-note"><LockKeyhole size={15} /><span>Correction Accuracy is never guessed. It remains NOT SCORED until the exercise has a measured reference, a validated input transform and verified native measurement evidence. Creative Look Similarity remains a separate assessment.</span></div>
  </div>;
}
