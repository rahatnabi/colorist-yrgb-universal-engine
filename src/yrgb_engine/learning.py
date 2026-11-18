"""Still-image learning curriculum and exercise catalogue.

Exercise targets in this module are instructional examples, not measured camera
reference data. They must never be used to validate a camera input transform.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Literal


Level = Literal["beginner", "intermediate", "advanced"]
ExerciseKind = Literal["knowledge", "guided_correction", "independent_challenge"]


@dataclass(frozen=True, slots=True)
class Lesson:
    id: str
    unit: int
    level: Level
    title: str
    outcome: str
    concepts: tuple[str, ...]
    practical_task: str
    evidence: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class Exercise:
    id: str
    lesson_id: str
    level: Level
    kind: ExerciseKind
    title: str
    brief: str
    required_evidence: tuple[str, ...]
    assessment_mode: Literal["knowledge_only", "correction_accuracy", "creative_look_similarity"]
    reference_asset_status: Literal["not_attached", "instructional_sample", "measured_reference"]
    target: dict[str, float | str]


LESSONS: tuple[Lesson, ...] = (
    Lesson("B01-pipeline", 0, "beginner", "The still-image color pipeline",
           "Explain decode, input transform, working space and display/output transform.",
           ("scene-referred vs display-referred", "camera encoding vs file format", "DWG/Intermediate"),
           "Draw and annotate a source-to-Rec.709 still-image pipeline.",
           ("pipeline diagram", "source metadata notes")),
    Lesson("B02-media", 1, "beginner", "Read the still before grading",
           "Separate container, codec, bit depth, transfer function and gamut.",
           ("metadata limits", "RAW vs rendered still", "unknown values"),
           "Inspect one still and write down known, unknown and inferred properties separately.",
           ("media inspection report", "uncertainty notes")),
    Lesson("B03-exposure", 2, "beginner", "Exposure and neutral balance",
           "Use a declared neutral ROI and linear-light measurement without guessing gray-card identity.",
           ("18% reference convention", "exposure stops", "neutral ROI"),
           "Select a genuine neutral reference patch and explain why it is suitable.",
           ("ROI coordinates", "exposure measurement", "RGB balance")),
    Lesson("I01-scopes", 3, "intermediate", "Scopes as diagnostic evidence",
           "Interpret histogram, RGB parade, waveform and vectorscope in their declared sample domain.",
           ("sample-domain limits", "clipping vs headroom", "luma coefficients"),
           "Compare image judgement with scope evidence and record one limitation for each scope.",
           ("scope snapshot", "diagnostic notes")),
    Lesson("I02-match", 4, "intermediate", "Reference-based still matching",
           "Match exposure and neutral balance before subjective look decisions.",
           ("reference ROI", "tonal distribution", "measurement uncertainty"),
           "Match a candidate still to a designated reference using only declared targets.",
           ("Correction Accuracy report", "before/after stills")),
    Lesson("I03-look", 5, "intermediate", "Controlled look development",
           "Create a repeatable look while keeping technical correction separate.",
           ("contrast", "saturation", "tonal shaping", "creative intent"),
           "Build two distinct creative treatments from the same technically normalized still.",
           ("look settings", "Creative Look Similarity report")),
    Lesson("A01-difficult", 6, "advanced", "Mixed light and difficult color",
           "Diagnose competing illuminants and avoid universal assumptions about skin or neutral objects.",
           ("local illumination", "ROI selection", "selective correction"),
           "Document which regions can and cannot support a neutral-balance measurement.",
           ("region map", "measurement caveats")),
    Lesson("A02-transform", 7, "advanced", "Transform validation and uncertainty",
           "Distinguish a named transform from a reference-validated transform.",
           ("traceable reference vectors", "OCIO config pinning", "validation gates"),
           "Audit a proposed camera profile and list the evidence required before approval.",
           ("transform audit", "validation decision")),
    Lesson("A03-delivery", 8, "advanced", "Float master and delivery QC",
           "Verify a full-resolution still master and assess the decoded exported file.",
           ("float32 round-trip", "metadata integrity", "delivery QC"),
           "Export a validated master and review its round-trip and correction report.",
           ("master file", "round-trip report", "delivery QC report")),
)


EXERCISES: tuple[Exercise, ...] = (
    Exercise("EX-B03-01", "B03-exposure", "beginner", "knowledge",
             "Exposure reference basics",
             "Explain what an 18% gray reference means and why a neutral ROI must be explicitly selected.",
             ("written explanation",), "knowledge_only", "not_attached",
             {"gray_reference": 0.18, "target_exposure_stops": 0.0}),
    Exercise("EX-I02-01", "I02-match", "intermediate", "guided_correction",
             "Neutral patch correction",
             "Use a supplied, verified still and a clearly identified neutral patch. The exercise target is authored for teaching and is not camera-transform validation data.",
             ("source profile ID", "neutral ROI", "Correction Accuracy report"),
             "correction_accuracy", "instructional_sample",
             {"gray_reference": 0.18, "target_exposure_stops": 0.0}),
    Exercise("EX-I03-01", "I03-look", "intermediate", "independent_challenge",
             "Creative reference interpretation",
             "Create a deliberate look that communicates the supplied creative brief. Compare only against the designated creative reference.",
             ("creative brief", "graded still", "look settings"),
             "creative_look_similarity", "not_attached",
             {"reference_type": "creative_still"}),
)


def curriculum_payload() -> dict[str, object]:
    """Return the still-image learning path in API-safe form."""
    return {
        "product_scope": "still_image_grading_only",
        "levels": [
            {"id": "beginner", "title": "Beginner", "lesson_ids": [x.id for x in LESSONS if x.level == "beginner"]},
            {"id": "intermediate", "title": "Intermediate", "lesson_ids": [x.id for x in LESSONS if x.level == "intermediate"]},
            {"id": "advanced", "title": "Advanced", "lesson_ids": [x.id for x in LESSONS if x.level == "advanced"]},
        ],
        "lessons": [asdict(x) for x in LESSONS],
        "assessment_policy": {
            "correction_accuracy": "Objective, exercise-target technical correction measurement; only scored when validated source data and required ROIs are available.",
            "creative_look_similarity": "Perceptual comparison against a designated creative still reference; never merged with Correction Accuracy.",
            "unvalidated_data": "No numerical objective accuracy score is issued.",
        },
    }


def list_exercises(*, level: Level | None = None) -> list[dict[str, object]]:
    """List still-image exercises, optionally filtered by learning level."""
    return [asdict(x) for x in EXERCISES if level is None or x.level == level]


def get_lesson(lesson_id: str) -> dict[str, object] | None:
    """Return one lesson by stable ID."""
    lesson = next((item for item in LESSONS if item.id == lesson_id), None)
    return asdict(lesson) if lesson else None


def get_exercise(exercise_id: str) -> dict[str, object] | None:
    """Return one exercise by stable ID."""
    exercise = next((item for item in EXERCISES if item.id == exercise_id), None)
    return asdict(exercise) if exercise else None
