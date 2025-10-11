"""Question generation and evaluation services."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from random import Random
from string import ascii_lowercase
from typing import Iterable, List, Sequence

from .callejero import StreetDatasetLoader, StreetGraph


@dataclass
class Question:
    """A quiz question with evaluation helpers."""

    question_type: str
    prompt: str
    answer: List[str]
    options: List[str]
    correct_option_index: int
    answer_guide: str
    metadata: dict

    def evaluate(self, submission: Sequence[str]) -> bool:
        if not submission:
            return False

        first = _normalise_text(submission[0])
        if self.options:
            # Accept either option text or its alphabetical label (a, b, c...)
            for index, option in enumerate(self.options):
                label = ascii_lowercase[index]
                normalised_option = _normalise_text(option)
                if first in {label, f"{label}.", f"{label})"}:
                    return index == self.correct_option_index
                if first == normalised_option:
                    return index == self.correct_option_index

        # Fallback to legacy evaluation for completeness.
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
        self._candidate_streets = self.graph.candidate_streets()

    def generate_for_date(self, target_date: date, amount: int) -> List[Question]:
        rng = Random(target_date.toordinal())
        questions: List[Question] = []
        attempts = 0

        while len(questions) < amount and attempts < amount * 10:
            attempts += 1
            if not self._candidate_streets:
                break
            street = rng.choice(self._candidate_streets)
            if len(questions) % 2 == 0:
                question = self._build_perpendicular_question(street, rng)
            else:
                other = rng.choice(self._candidate_streets)
                if other == street:
                    continue
                question = self._build_path_question(street, other, rng)
            if question:
                questions.append(question)
        return questions

    def _build_perpendicular_question(self, street: str, rng: Random) -> Question | None:
        intersections = self.graph.intersecting_streets(street)
        if not intersections:
            return None

        distractor_pool = [
            candidate
            for candidate in self._candidate_streets
            if candidate not in intersections and candidate != street
        ]
        if len(distractor_pool) < 3:
            return None

        correct_option = rng.choice(intersections)
        distractors = rng.sample(distractor_pool, k=3)
        options = [correct_option, *distractors]
        rng.shuffle(options)
        prompt = f"¿Cuál de las siguientes calles es perpendicular a {street}?"
        metadata = {"street": street}

        return Question(
            question_type="perpendicular",
            prompt=prompt,
            answer=[correct_option],
            options=options,
            correct_option_index=options.index(correct_option),
            answer_guide="Selecciona la opción correcta (a, b, c o d).",
            metadata=metadata,
        )

    def _build_path_question(self, start: str, end: str, rng: Random) -> Question | None:
        path = self.graph.shortest_path(start, end)
        if not path or len(path) < 2:
            return None

        prompt = (
            "¿Cuál de las siguientes rutas corresponde al trayecto más corto para ir desde "
            f"{start} hasta {end}?"
        )
        correct_option = _format_path(path)
        distractors = self._generate_path_distractors(path, rng)
        if len(distractors) < 3:
            return None

        options = [correct_option, *distractors[:3]]
        rng.shuffle(options)
        metadata = {"start": start, "end": end, "path": path}

        return Question(
            question_type="shortest_path",
            prompt=prompt,
            answer=[correct_option],
            options=options,
            correct_option_index=options.index(correct_option),
            answer_guide="Selecciona la opción correcta (a, b, c o d).",
            metadata=metadata,
        )

    def _generate_path_distractors(self, path: List[str], rng: Random) -> List[str]:
        """Create alternative path descriptions to serve as distractors."""

        distractors: List[str] = []
        used = {_format_path(path)}
        candidates = [street for street in self._candidate_streets if street not in path]

        # Reverse path as a distractor when it differs from the correct option.
        reversed_path = list(reversed(path))
        reversed_option = _format_path(reversed_path)
        if reversed_option not in used and reversed_option != _format_path(path):
            distractors.append(reversed_option)
            used.add(reversed_option)

        # Omit the last street when possible.
        if len(path) > 2:
            shortened_option = _format_path(path[:-1])
            if shortened_option not in used:
                distractors.append(shortened_option)
                used.add(shortened_option)

        # Replace an intermediate street with a random alternative.
        if len(path) > 2 and candidates:
            replace_index = rng.randrange(1, len(path) - 1)
            replacement = rng.choice(candidates)
            mutated = path.copy()
            mutated[replace_index] = replacement
            mutated_option = _format_path(mutated)
            if mutated_option not in used:
                distractors.append(mutated_option)
                used.add(mutated_option)

        # Add an extra street at the end when enough candidates remain.
        if candidates:
            extension = path + [rng.choice(candidates)]
            extended_option = _format_path(extension)
            if extended_option not in used:
                distractors.append(extended_option)
                used.add(extended_option)

        # Alter the final street to a different candidate when possible.
        if candidates:
            alternative_end = path[:-1] + [rng.choice(candidates)]
            alternative_option = _format_path(alternative_end)
            if alternative_option not in used:
                distractors.append(alternative_option)
                used.add(alternative_option)

        # Insert an additional street between start and end.
        if candidates:
            inserted = path[:1] + [rng.choice(candidates)] + path[1:]
            inserted_option = _format_path(inserted)
            if inserted_option not in used:
                distractors.append(inserted_option)
                used.add(inserted_option)

        return distractors


def _normalise_text(value: str) -> str:
    return value.strip().casefold()


def _format_path(path: Sequence[str]) -> str:
    return " → ".join(path)
