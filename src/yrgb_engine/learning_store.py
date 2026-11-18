"""Local persistence for still-image learning submissions and progress."""
from __future__ import annotations

import json
import os
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _root() -> Path:
    root = Path(os.getenv("YRGB_LEARNING_DATA_DIR", Path.home() / ".colorist-yrgb" / "learning"))
    root.mkdir(parents=True, exist_ok=True)
    (root / "uploads").mkdir(exist_ok=True)
    return root


def _connect() -> sqlite3.Connection:
    connection = sqlite3.connect(_root() / "learning.sqlite3")
    connection.row_factory = sqlite3.Row
    connection.execute(
        """CREATE TABLE IF NOT EXISTS submissions (
            id TEXT PRIMARY KEY,
            learner_id TEXT NOT NULL,
            exercise_id TEXT NOT NULL,
            evidence TEXT NOT NULL,
            image_path TEXT,
            image_filename TEXT,
            assessment_status TEXT NOT NULL,
            correction_accuracy_score REAL,
            created_at TEXT NOT NULL
        )"""
    )
    connection.execute(
        """CREATE TABLE IF NOT EXISTS lesson_progress (
            learner_id TEXT NOT NULL,
            lesson_id TEXT NOT NULL,
            completed_at TEXT NOT NULL,
            PRIMARY KEY (learner_id, lesson_id)
        )"""
    )
    return connection


def save_submission(
    *,
    learner_id: str,
    exercise_id: str,
    evidence: dict[str, Any],
    image_bytes: bytes | None,
    image_filename: str | None,
    assessment_status: str,
) -> dict[str, Any]:
    submission_id = uuid.uuid4().hex
    image_path: str | None = None
    safe_filename: str | None = None
    root = _root()
    if image_bytes is not None:
        suffix = Path(image_filename or "practice.png").suffix.lower()
        if suffix not in {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".exr", ".dng", ".dpx", ".webp"}:
            suffix = ".img"
        destination = root / "uploads" / f"{submission_id}{suffix}"
        destination.write_bytes(image_bytes)
        image_path = str(destination)
        safe_filename = Path(image_filename or "still-image").name[:180]
    created_at = datetime.now(timezone.utc).isoformat()
    with _database() as connection:
        connection.execute(
            """INSERT INTO submissions
            (id, learner_id, exercise_id, evidence, image_path, image_filename,
             assessment_status, correction_accuracy_score, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, NULL, ?)""",
            (submission_id, learner_id, exercise_id, json.dumps(evidence), image_path,
             safe_filename, assessment_status, created_at),
        )
    return {
        "id": submission_id,
        "exercise_id": exercise_id,
        "assessment_status": assessment_status,
        "correction_accuracy_score": None,
        "created_at": created_at,
        "image_attached": image_path is not None,
    }


def complete_lesson(*, learner_id: str, lesson_id: str) -> dict[str, str]:
    completed_at = datetime.now(timezone.utc).isoformat()
    with _connect() as connection:
        connection.execute(
            """INSERT INTO lesson_progress (learner_id, lesson_id, completed_at)
            VALUES (?, ?, ?)
            ON CONFLICT(learner_id, lesson_id) DO UPDATE SET completed_at=excluded.completed_at""",
            (learner_id, lesson_id, completed_at),
        )
    return {"lesson_id": lesson_id, "completed_at": completed_at}


def get_progress(learner_id: str) -> dict[str, Any]:
    with _connect() as connection:
        lessons = connection.execute(
            "SELECT lesson_id, completed_at FROM lesson_progress WHERE learner_id=? ORDER BY completed_at",
            (learner_id,),
        ).fetchall()
        submissions = connection.execute(
            """SELECT id, exercise_id, assessment_status, correction_accuracy_score,
            created_at, image_filename FROM submissions WHERE learner_id=? ORDER BY created_at DESC""",
            (learner_id,),
        ).fetchall()
    return {
        "learner_id": learner_id,
        "completed_lessons": [dict(row) for row in lessons],
        "submissions": [dict(row) for row in submissions],
        "completed_lesson_count": len(lessons),
        "submission_count": len(submissions),
    }
