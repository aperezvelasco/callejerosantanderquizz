from datetime import date
from pathlib import Path

from app.services.callejero import StreetDatasetLoader, StreetGraph
from app.services.question_generator import QuestionGenerator


def load_sample_segments():
    loader = StreetDatasetLoader(cache_path=Path("tests/data") / "sample_callejero_tramos.json")
    return loader.load()


def test_dataset_loader_reads_sample():
    segments = load_sample_segments()
    assert segments, "expected sample dataset to load segments"
    names = {segment.street for segment in segments}
    assert "Calle Castilla" in names


def test_graph_shortest_path():
    segments = load_sample_segments()
    graph = StreetGraph(segments)
    path = graph.shortest_path("Calle Ruiz Zorrilla", "Calle Argentina")
    assert path[0] == "Calle Ruiz Zorrilla"
    assert path[-1] == "Calle Argentina"
    assert "Calle Castilla" in path
    assert len(path) == 4


def test_generate_questions_from_sample():
    segments = load_sample_segments()
    generator = QuestionGenerator(segments)
    questions = generator.generate_for_date(date(2024, 1, 1), 3)
    assert len(questions) == 3
    assert any(q.question_type == "perpendicular" for q in questions)
    assert any(q.question_type == "shortest_path" for q in questions)
    for question in questions:
        assert len(question.options) == 4
        assert 0 <= question.correct_option_index < len(question.options)
        # Ensure evaluation works with letter submissions
        letter = chr(ord("a") + question.correct_option_index)
        assert question.evaluate([letter]) is True
