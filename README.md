# Callejero Santander Quizz

Backend API for the "Callejero Santander Quizz" mobile application. The service downloads the Santander street segment dataset and generates three daily questions for registered users. Players earn one point for every correct answer and can consult the global leaderboard with the total questions answered, accumulated points and success ratio.

## Features

- User registration and login endpoints.
- Deterministic generation of three daily questions using the official Callejero dataset.
- Two kinds of questions inspired by the municipal exam:
  - Streets that intersect a particular street (perpendicular questions).
  - Shortest path between two streets expressed as the sequence of connecting streets.
- Recording of answers, automatic validation and scoring.
- Leaderboard summarising the performance of every registered player.

## Project structure

```
app/
├── core/            # Configuration
├── routers/         # FastAPI routers (users, quiz, leaderboard)
├── services/        # Dataset loader and question generator
├── database.py      # SQLAlchemy engine and helpers
├── main.py          # FastAPI entry point
└── models.py        # SQLAlchemy models
```

A small sample dataset is provided in `data/sample_callejero_tramos.json` to run the application offline or during testing. When the API can reach the official endpoint, the dataset is downloaded and cached to `data/callejero_segments.json`.

## Installation

Create a Python 3.11 virtual environment and install the dependencies listed in `pyproject.toml`.

```
python -m venv .venv
source .venv/bin/activate
pip install -e .[test]
```

## Running the API

Initialize the database and start the FastAPI server with Uvicorn:

```
uvicorn app.main:app --reload
```

The following endpoints are available:

- `POST /users/register` — create a user account.
- `POST /users/login` — validate user credentials.
- `GET /quiz/daily` — retrieve or generate the three daily questions.
- `POST /quiz/{question_id}/answer?username=...` — submit an answer (provide a JSON array with the sequence of street names in the `answer` field).
- `GET /quiz/leaderboard` — list the global classification with total answers, points and accuracy.

## Running tests

```
pytest
```

## Notes

- The dataset endpoint sometimes requires a user agent header. If downloading fails the API automatically falls back to the sample dataset bundled with the repository.
- Question generation is deterministic per day, meaning all users receive the same three questions for a given date.
