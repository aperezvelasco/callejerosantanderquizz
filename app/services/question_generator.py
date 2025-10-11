"""Question generation and evaluation services."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from random import Random
from typing import Iterable, List, Sequence

from .callejero import StreetDatasetLoader, StreetGraph


@dataclass
class Question:
    """A quiz question with evaluation helpers."""

    question_type: str
    prompt: str
    answer: List[str]
    answer_guide: str
    metadata: dict

    def evaluate(self, submission: Sequence[str]) -> bool:
        normalised_submission = [_normalise_text(item) for item in submission]
        normalised_answer = [_normalise_text(item) for item in self.answer]

        if self.question_type == "perpendicular":
            return set(normalised_submission) == set(normalised_answer)
        if self.question_type == "shortest_path":
            return normalised_submission == normalised_answer
        raise ValueError(f"Unknown question type: {self.question_type}")


class QuestionGenerator:
    """Generate deterministic daily questions based on street data."""

    def __init__(self, segments: Iterable = None) -> None:
        if segments is None:
            loader = StreetDatasetLoader()
            segments = loader.load()
        self.graph = StreetGraph(segments)

    def generate_for_date(self, target_date: date, amount: int) -> List[Question]:
        rng = Random(target_date.toordinal())
        questions: List[Question] = []
        attempts = 0
        candidate_streets = self.graph.candidate_streets()

        while len(questions) < amount and attempts < amount * 10:
            attempts += 1
            if not candidate_streets:
                break
            street = rng.choice(candidate_streets)
            if len(questions) % 2 == 0:
                question = self._build_perpendicular_question(street)
            else:
                other = rng.choice(candidate_streets)
                if other == street:
                    continue
                question = self._build_path_question(street, other)
            if question:
                questions.append(question)
        return questions

    def _build_perpendicular_question(self, street: str) -> Question | None:
        intersections = self.graph.intersecting_streets(street)
        if not intersections:
            return None
        prompt = f"¿Qué calles de la ciudad de Santander son perpendiculares a {street}?"
        metadata = {"street": street}
        return Question(
            question_type="perpendicular",
            prompt=prompt,
            answer=intersections,
            answer_guide="Responde con todas las calles perpendiculares separadas por comas.",
            metadata=metadata,
        )

    def _build_path_question(self, start: str, end: str) -> Question | None:
        path = self.graph.shortest_path(start, end)
        if not path or len(path) < 2:
            return None
        prompt = (
            "¿Qué calles tienes que pasar en el trayecto más corto para ir desde "
            f"{start} hasta {end}?"
        )
        metadata = {"start": start, "end": end}
        return Question(
            question_type="shortest_path",
            prompt=prompt,
            answer=path,
            answer_guide="Indica la secuencia completa de calles en orden, separadas por comas.",
            metadata=metadata,
        )


def _normalise_text(value: str) -> str:
    return value.strip().casefold()
