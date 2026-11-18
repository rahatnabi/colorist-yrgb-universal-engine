# COLORIST YRGB — Learning Architecture (Milestone 1)

Status: **curriculum architecture complete; delivery/content production is a later implementation activity.**

## Learning outcome

A learner should be able to inspect unfamiliar still/video media, identify its technical properties, choose a defensible input transform, evaluate exposure and color with scopes, match shots, create a restrained look, and deliver a technically valid master. The curriculum teaches measurement before aesthetics and makes uncertainty visible.

## Instructional design

- **Workflow-first:** every concept is taught in the order it appears in a real grading session.
- **Evidence-first:** learners must identify source encoding, gamut, bit depth, and metadata before applying a transform.
- **One variable at a time:** exercises isolate exposure, white balance, contrast, saturation, and look design.
- **Scope-supported, not scope-only:** waveform, RGB parade, histogram, vectorscope, and image judgement are used together.
- **Camera-agnostic:** examples cover multiple manufacturers, but no profile is treated as universal.
- **Practice-led:** every lesson ends with an observable task and a saved result.
- **Honest validation:** an attractive image is not proof of a correct transform; an unverified profile must remain labelled unverified.

## Learner pathway

| Unit | Focus | Required practical outcome |
|---|---|---|
| 0 | Orientation, color pipeline, project setup | Create a documented project and identify its working/output spaces |
| 1 | Media literacy: containers, codecs, bit depth, chroma, metadata | Produce a media inspection report |
| 2 | Log, gamut, RAW, scene/display reference | Distinguish transfer function, gamut, container, and codec |
| 3 | Input transforms and color management | Build a traceable camera-to-working-space pipeline |
| 4 | Exposure and white balance | Correct exposure and neutral balance using declared references |
| 5 | Scopes and diagnostics | Read waveform, RGB parade, histogram, and vectorscope without confusing code values with scene-linear values |
| 6 | Shot matching | Match a selected reference shot and explain the measurement choices |
| 7 | Creative look development | Build a repeatable look with controlled contrast, saturation, hue, and texture |
| 8 | Skin, mixed lighting, and difficult scenes | Diagnose mixed illuminants and evaluate skin regions without assuming one universal skin color |
| 9 | Stills, video, sequences, and LUTs | Process representative image/video assets and validate LUT input/output assumptions |
| 10 | Output, QC, and delivery | Export a master and complete a delivery/QC checklist |
| 11 | Capstone | Grade a short scene from ingest to final delivery and submit an audit trail |

## Lesson template

Every lesson uses the same structure:
1. **Why it matters** — the production problem being solved.
2. **Core concept** — a short explanation with terminology.
3. **Pipeline location** — where the operation belongs (decode, input transform, working space, display, output).
4. **Demonstration** — a reproducible example with known source settings.
5. **Guided exercise** — a constrained task with one main learning objective.
6. **Independent challenge** — a less familiar shot or image.
7. **Scope evidence** — which scopes/measurements support the decision.
8. **Common failure modes** — wrong gamut, double transform, clipping, legal/full range confusion, wrong bit-depth assumptions, etc.
9. **Submission** — project, still, settings, and short explanation.
10. **Self-assessment** — rubric plus reflection.

## Exercise and assessment system

Each unit has three exercise levels:
- **Foundation:** identify, label, and explain.
- **Applied:** perform a controlled correction on supplied media.
- **Transfer:** solve a new shot with incomplete or mixed metadata and document uncertainty.

### Assessment rubric (100 points)

| Criterion | Points | Evidence |
|---|---:|---|
| Media/profile identification | 15 | Correctly distinguishes codec, transfer, gamut, and camera model |
| Color-management integrity | 20 | Explicit, non-duplicated input/working/output transforms |
| Exposure and balance | 15 | Measured decisions with correct signal-domain assumptions |
| Scope interpretation | 15 | Correct use and limitations of scopes |
| Shot continuity | 10 | Consistent reference relationship across shots |
| Creative intent | 10 | Controlled, repeatable look decisions |
| Output/QC | 10 | Correct format, tags, levels, and delivery checks |
| Documentation | 5 | Reproducible notes and evidence |

**Critical-failure gates:** an incorrect or guessed camera transform, an undisclosed double transform, or a false claim of color accuracy prevents a passing technical-integrity score regardless of aesthetic quality.

## Suggested 30-day starter sequence

- Days 1–3: pipeline vocabulary, media inspection, and metadata report.
- Days 4–6: transfer functions, gamuts, and input transforms.
- Days 7–9: exposure and white balance.
- Days 10–12: waveform, parade, histogram, and vectorscope.
- Days 13–15: shot matching.
- Days 16–19: contrast, saturation, curves, and look design.
- Days 20–22: mixed lighting and skin-region diagnostics.
- Days 23–25: still/video/LUT handling.
- Days 26–28: output transforms and QC.
- Days 29–30: capstone grade and review.

## Completion criteria for Milestone 1

- [x] Learning outcomes and workflow sequence defined.
- [x] Unit-level curriculum and practical outcomes defined.
- [x] Standard lesson template defined.
- [x] Exercise progression and assessment rubric defined.
- [x] Technical-integrity failure gates defined.
- [x] Starter 30-day sequence defined.

This milestone completes the **learning architecture specification**. It does not claim that all lessons, video tutorials, downloadable exercises, or grading assessments have already been produced or deployed.
