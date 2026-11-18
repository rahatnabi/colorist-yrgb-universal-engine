# COLORIST YRGB — Still-Image Learning Architecture

Status: **curriculum catalogue and read-only learning API implemented; learner progress tracking and full lesson media remain future work.**

## Product scope

This curriculum teaches grading and assessment of **still images only**. It does not define video lessons, clip/frame analysis, temporal diagnostics, or video-grading workflows.

## Learning outcome

A learner should be able to inspect an unfamiliar still image, identify what is known and unknown about its encoding, select only a reference-validated input transform, evaluate exposure and neutral balance with declared measurements, interpret scopes in their actual sample domain, match a designated reference still, develop a repeatable creative look, and verify a float master.

## Learner pathway

| Level | Lesson | Observable outcome |
|---|---|---|
| Beginner | The still-image color pipeline | Draw a source-to-Rec.709 pipeline |
| Beginner | Read the still before grading | Separate container, codec, bit depth, transfer and gamut |
| Beginner | Exposure and neutral balance | Select a defensible neutral ROI and explain the 18% reference |
| Intermediate | Scopes as diagnostic evidence | Interpret histogram, RGB parade, waveform and vectorscope with domain caveats |
| Intermediate | Reference-based still matching | Match a candidate still to a designated reference |
| Intermediate | Controlled look development | Create repeatable looks without confusing creative intent with technical correction |
| Advanced | Mixed light and difficult color | Identify where neutral measurements are and are not defensible |
| Advanced | Transform validation and uncertainty | Audit evidence before a camera transform is approved |
| Advanced | Float master and delivery QC | Verify the exported still and review its delivery report |

## Standard lesson structure

Every lesson should include:
1. Why the concept matters in a real still-image grading task.
2. Core concept and terminology.
3. Pipeline location: decode, input transform, working space, display or output.
4. Demonstration using a clearly identified still and known source properties.
5. Guided exercise with one main learning objective.
6. Independent challenge using a different still.
7. Scope and measurement evidence, including limitations.
8. Common failure modes and uncertainty notes.
9. Submission: still, settings, measurements and short explanation.
10. Self-assessment and reflection.

## Exercise catalogue

The initial API catalogue contains:
- **EX-B03-01 — Exposure reference basics:** knowledge-only; no image score.
- **EX-I02-01 — Neutral patch correction:** guided technical correction; only eligible for objective Correction Accuracy when validated source data and a genuine neutral ROI are supplied.
- **EX-I03-01 — Creative reference interpretation:** creative challenge; assessed separately against a designated creative still reference.

The current exercise targets are instructional examples, not measured camera reference vectors and not approval evidence for any camera transform. The catalogue deliberately does not claim that downloadable practice assets are attached.

## Assessment policy

Two assessment tracks must remain independent:

### Correction Accuracy
Objective, exercise-target technical correction measurement. It may be scored only when the input transform is reference-validated, the working domain is validated linear RGB, required regions are explicitly selected, and the exercise target is defined. Missing evidence means **NOT SCORED**, not a guessed score.

### Creative Look Similarity
Perceptual comparison against a designated creative reference still. It describes resemblance to that reference, not objective technical correctness or a universally correct look.

These values must never be combined into one score. An attractive result is not evidence that a camera transform is technically valid.

## Technical-integrity gates

- Unknown or unverified camera transforms cannot be silently selected.
- A double input transform is a critical failure.
- Scope values must retain their declared sample-domain labels; browser-decoded sRGB samples must not be described as camera-log IRE or calibrated nits.
- Learner-selected ROIs are not automatically recognized as gray cards or neutral objects.
- No objective score is issued from unvalidated image data.
- Synthetic or instructional values cannot validate production camera transforms.

## API surface

- `GET /v1/learning/curriculum` — level structure and complete lesson catalogue.
- `GET /v1/learning/exercises` — exercise catalogue; optional `level=beginner|intermediate|advanced`.
- `GET /v1/learning/lessons/{lesson_id}` — one lesson.
- `GET /v1/learning/exercises/{exercise_id}` — one exercise.

These are read-only catalogue endpoints. They do not yet store learner submissions, progress, grades, or personal profiles.

## Next implementation milestones

1. Attach licensed, traceable still-image practice assets and record their actual metadata.
2. Add guided exercise UI with a selected still, task brief and submission evidence.
3. Connect eligible technical exercises to native Correction Accuracy.
4. Build a separate creative-reference comparison method and keep its score independent.
5. Add learner progress persistence and a transparent skill report.

## Guided exercise interface and learner records

The web workspace now includes a **Learning School** navigation view with:
- Nine lesson cards grouped by Beginner, Intermediate and Advanced.
- Lesson concepts, practical task and evidence checklist.
- A generated synthetic neutral practice chart download.
- Exercise selection, evidence notes and still-image file submission.
- Lesson completion and a learner progress/history panel.

The generated chart is an educational sample only. It is not a measured reference target and cannot validate camera transforms.

### Persistence and privacy boundary

The API stores learner progress and submission metadata in a local SQLite database under `YRGB_LEARNING_DATA_DIR`, defaulting to `~/.colorist-yrgb/learning`. Submitted still files are copied into that directory's `uploads` folder. This is local single-instance persistence, not cloud sync, multi-user authentication or a secure hosted classroom. Anyone with access to the machine and data directory may access those records. Configure a protected data directory and back it up as needed.

### Submission endpoints

- `GET /v1/learning/assets/neutral-practice-chart.png` — download synthetic practice still.
- `POST /v1/learning/lessons/{lesson_id}/complete` — record lesson completion for a learner ID.
- `GET /v1/learning/progress?learner_id=...` — retrieve that learner's lesson and submission history.
- `POST /v1/learning/submissions` — submit evidence and an optional/required still image depending on exercise type.

The submission endpoint enforces a 100 MiB upload limit, checks file type by declared MIME/extension, and stores files under generated IDs rather than user-provided paths. It does not yet run an automatic grading assessment.

### Assessment status

The current reference correction exercise is marked as an instructional sample, not a measured reference. Therefore submissions remain **NOT SCORED** even when a learner supplies a profile ID and ROI. The API does not award a score based only on learner-supplied identifiers. A future assessment runner must independently confirm the registry's reference-validation status, verify the neutral/reference region, decode and measure the submitted still through the native engine, and only then publish Correction Accuracy. Creative Look Similarity remains a separate perceptual review track.
