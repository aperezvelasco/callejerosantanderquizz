"""Question generation and evaluation services for the street quiz."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from random import Random
from typing import Any, Dict, Iterable, List, Optional, Sequence

import networkx as nx

from .callejero import StreetGraph, normalize_street_name


@dataclass
class Question:
    """A quiz question with evaluation helpers.

    Parameters
    ----------
    question_type : str
        The type of the question (e.g. 'PATH', 'INTERSECTS', 'COUNT', 'OPEN_INTERSECTIONS').
    prompt : str
        The question prompt displayed to the user.
    answer : List[str]
        The correct answer(s).
    answer_guide : str
        Instructions on how to answer.
    metadata : Dict[str, Any]
        Additional context for the question.
    choices : List[str]
        Multiple choice options, if applicable.
    """

    question_type: str
    prompt: str
    answer: List[str]
    answer_guide: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    choices: List[str] = field(default_factory=list)

    def evaluate(self, submission: Sequence[str]) -> bool:
        """Evaluate if the user submission is correct.

        Parameters
        ----------
        submission : Sequence[str]
            The user's submitted answer(s).

        Returns
        -------
        bool
            True if the submission is correct, False otherwise.
        """
        if not submission:
            return False

        norm_submission = [normalize_street_name(s) for s in submission]
        norm_answer = [normalize_street_name(a) for a in self.answer]

        if self.question_type in (
            "perpendicular",
            "open_intersections",
            "OPEN_INTERSECTIONS",
        ):
            # Set comparison: order doesn't matter
            return set(norm_submission) == set(norm_answer)

        if self.question_type in ("shortest_path", "path", "PATH"):
            # Sequence comparison: order matters
            return norm_submission == norm_answer

        if self.question_type in ("intersects", "INTERSECTS"):
            # Multiple choice match
            return any(s in norm_answer for s in norm_submission)

        if self.question_type in ("count", "COUNT"):
            # Exact match of the count (represented as string)
            return norm_submission == norm_answer

        raise ValueError(f"Unknown question type: {self.question_type}")


class QuestionGenerator:
    """Generate deterministic daily questions based on street data."""

    def __init__(self, segments: Optional[Iterable[Any]] = None) -> None:
        if segments is None:
            from .callejero import get_street_graph

            self.graph = get_street_graph()
        else:
            self.graph = StreetGraph(segments)

    def generate_for_date(self, target_date: date, amount: int) -> List[Question]:
        """Generate a deterministic set of questions for a specific date.

        Parameters
        ----------
        target_date : date
            The date to seed the random number generator.
        amount : int
            The number of questions to generate.

        Returns
        -------
        List[Question]
            List of generated Question objects.
        """
        rng = Random(target_date.toordinal())
        questions: List[Question] = []
        attempts = 0
        candidate_streets = self.graph.candidate_streets()

        if not candidate_streets:
            return []

        # We will cycle through question types to get a good mix
        types = ["PATH", "INTERSECTS", "COUNT"]

        while len(questions) < amount and attempts < amount * 15:
            attempts += 1
            q_type = types[len(questions) % len(types)]
            street = rng.choice(candidate_streets)

            question: Optional[Question] = None
            if q_type == "PATH":
                # Find a target street that is between 2 and 4 steps away
                target = self._find_distant_street(
                    street, rng, min_steps=2, max_steps=4
                )
                if target:
                    question = self._build_path_question(street, target, rng)
            elif q_type == "INTERSECTS":
                question = self._build_intersects_question(street, rng)
            elif q_type == "COUNT":
                question = self._build_count_question(street, rng)

            if question:
                questions.append(question)

        # Fallback using multiple choice questions
        if len(questions) < amount:
            while len(questions) < amount and attempts < amount * 30:
                attempts += 1
                street = rng.choice(candidate_streets)
                if len(questions) % 3 == 0:
                    other = rng.choice(candidate_streets)
                    if other != street:
                        question = self._build_path_question(street, other, rng)
                elif len(questions) % 3 == 1:
                    question = self._build_intersects_question(street, rng)
                else:
                    question = self._build_count_question(street, rng)
                if question:
                    questions.append(question)

        return questions[:amount]

    def _find_distant_street(
        self, start: str, rng: Random, min_steps: int = 2, max_steps: int = 4
    ) -> Optional[str]:
        """Find a street that is between min_steps and max_steps away from start.

        Parameters
        ----------
        start : str
            The starting street name.
        rng : Random
            The random number generator.
        min_steps : int, default 2
            Minimum number of intersection changes.
        max_steps : int, default 4
            Maximum number of intersection changes.

        Returns
        -------
        str, optional
            The name of the target street, or None if none found.
        """
        norm_start = normalize_street_name(start)
        if norm_start not in self.graph.graph:
            return None

        # BFS to find distances
        lengths = nx.single_source_shortest_path_length(self.graph.graph, norm_start)
        candidates = [
            self.graph.canonical_names[node]
            for node, dist in lengths.items()
            if min_steps <= dist <= max_steps
        ]

        if not candidates:
            return None
        return rng.choice(candidates)

    def _build_path_question(
        self, start: str, end: str, rng: Random
    ) -> Optional[Question]:
        """Build a PATH question with multiple-choice choices and correct answer.

        Parameters
        ----------
        start : str
            Start street name.
        end : str
            End street name.
        rng : Random
            Random number generator.

        Returns
        -------
        Question, optional
            The generated Question, or None.
        """
        path = self.graph.shortest_path(start, end)
        if not path or len(path) < 2:
            return None

        prompt = (
            "¿Cuál es la ruta más corta (menos cambios de calle) para ir desde "
            f"'{start}' hasta '{end}'?"
        )
        correct_str = " -> ".join(path)

        # Generate distractors
        choices = [correct_str]

        # Distractor 1: Reversed path
        reversed_path = list(reversed(path))
        rev_str = " -> ".join(reversed_path)
        if rev_str not in choices:
            choices.append(rev_str)

        # Distractor 2: Path with a detour or wrong street
        # Let's replace one middle street with a random street
        if len(path) > 2:
            all_streets = self.graph.candidate_streets()
            for _ in range(3):
                detour = list(path)
                detour[rng.randint(1, len(path) - 2)] = rng.choice(all_streets)
                detour_str = " -> ".join(detour)
                if detour_str not in choices:
                    choices.append(detour_str)
                    break

        # Distractor 3: Detour/random path
        for _ in range(5):
            if len(choices) >= 4:
                break
            # Find a path between different random nodes
            s_rand = rng.choice(self.graph.candidate_streets())
            e_rand = rng.choice(self.graph.candidate_streets())
            p_rand = self.graph.shortest_path(s_rand, e_rand)
            if p_rand and len(p_rand) == len(path):
                p_rand_str = " -> ".join(p_rand)
                if p_rand_str not in choices:
                    choices.append(p_rand_str)

        # Pad to 4 choices if needed
        all_streets = self.graph.candidate_streets()
        while len(choices) < 4:
            dummy = (
                [start]
                + [rng.choice(all_streets) for _ in range(len(path) - 2)]
                + [end]
            )
            dummy_str = " -> ".join(dummy)
            if dummy_str not in choices:
                choices.append(dummy_str)

        rng.shuffle(choices)

        return Question(
            question_type="PATH",
            prompt=prompt,
            answer=path,
            answer_guide="Selecciona la secuencia correcta de calles.",
            metadata={"start": start, "end": end},
            choices=choices,
        )

    def _build_intersects_question(
        self, street: str, rng: Random
    ) -> Optional[Question]:
        """Build an INTERSECTS multiple choice question.

        Parameters
        ----------
        street : str
            Target street name.
        rng : Random
            Random number generator.

        Returns
        -------
        Question, optional
            The generated Question, or None.
        """
        intersections = self.graph.intersecting_streets(street)
        if not intersections:
            return None

        prompt = f"¿Cuál de las siguientes calles intersecta con '{street}'?"
        correct_choice = rng.choice(intersections)

        # Generate distractors (streets that do NOT intersect)
        distractors: List[str] = []
        all_candidates = self.graph.candidate_streets()
        norm_intersections = {normalize_street_name(i) for i in intersections}
        norm_street = normalize_street_name(street)

        attempts = 0
        while len(distractors) < 3 and attempts < 100:
            attempts += 1
            candidate = rng.choice(all_candidates)
            norm_cand = normalize_street_name(candidate)
            if (
                norm_cand not in norm_intersections
                and norm_cand != norm_street
                and candidate not in distractors
            ):
                distractors.append(candidate)

        choices = [correct_choice] + distractors
        rng.shuffle(choices)

        return Question(
            question_type="INTERSECTS",
            prompt=prompt,
            answer=[correct_choice],
            answer_guide="Selecciona la calle que intersecta.",
            metadata={"street": street},
            choices=choices,
        )

    def _build_count_question(self, street: str, rng: Random) -> Optional[Question]:
        """Build a COUNT intersections multiple choice question.

        Parameters
        ----------
        street : str
            Target street name.
        rng : Random
            Random number generator.

        Returns
        -------
        Question, optional
            The generated Question, or None.
        """
        intersections = self.graph.intersecting_streets(street)
        count = len(intersections)
        if count == 0:
            return None

        prompt = f"¿Cuántas calles intersectan con '{street}'?"

        # Generate choices
        choices = [str(count)]
        offsets = [-2, -1, 1, 2, 3]
        rng.shuffle(offsets)

        for offset in offsets:
            val = count + offset
            if val > 0 and str(val) not in choices:
                choices.append(str(val))
            if len(choices) >= 4:
                break

        rng.shuffle(choices)

        return Question(
            question_type="COUNT",
            prompt=prompt,
            answer=[str(count)],
            answer_guide="Selecciona el número correcto de intersecciones.",
            metadata={"street": street, "count": count},
            choices=choices,
        )

    def _build_open_intersections_question(self, street: str) -> Optional[Question]:
        """Build an OPEN_INTERSECTIONS question.

        Parameters
        ----------
        street : str
            Target street name.

        Returns
        -------
        Question, optional
            The generated Question, or None.
        """
        intersections = self.graph.intersecting_streets(street)
        if not intersections:
            return None

        prompt = f"Indica todas las calles que intersectan con '{street}':"

        return Question(
            question_type="OPEN_INTERSECTIONS",
            prompt=prompt,
            answer=intersections,
            answer_guide="Escribe los nombres de las calles separados por comas.",
            metadata={"street": street},
            choices=[],
        )

    def _build_perpendicular_question(self, street: str) -> Optional[Question]:
        """Backward-compatibility helper for perpendicular questions."""
        intersections = self.graph.intersecting_streets(street)
        if not intersections:
            return None
        return Question(
            question_type="perpendicular",
            prompt=f"¿Qué calles de la ciudad de Santander son perpendiculares a {street}?",
            answer=intersections,
            answer_guide="Responde con todas las calles perpendiculares separadas por comas.",
            metadata={"street": street},
        )

    def _build_path_question_street_names(
        self, start: str, end: str
    ) -> Optional[Question]:
        """Backward-compatibility helper for shortest_path questions."""
        path = self.graph.shortest_path(start, end)
        if not path or len(path) < 2:
            return None
        return Question(
            question_type="shortest_path",
            prompt=(
                "¿Qué calles tienes que pasar en el trayecto más corto para ir desde "
                f"{start} hasta {end}?"
            ),
            answer=path,
            answer_guide="Indica la secuencia completa de calles en orden, separadas por comas.",
            metadata={"start": start, "end": end},
        )
