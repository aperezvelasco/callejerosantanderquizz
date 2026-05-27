#!/usr/bin/env python
"""CLI tool for street guide analysis and quiz generation using GeoJSON street data."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path
from typing import List, Optional

from app.services.callejero import StreetGraph
from app.services.question_generator import QuestionGenerator


def handle_build(streets_path: str, save_path: str) -> None:
    """Build the connectivity graph from GeoJSON and save it to a JSON file.

    Parameters
    ----------
    streets_path : str
        Path to the GeoJSON streets file.
    save_path : str
        Path to save the JSON adjacency list.
    """
    if not Path(streets_path).exists():
        print(f"Error: GeoJSON file not found: {streets_path}", file=sys.stderr)
        sys.exit(1)

    print(f"Loading streets from {streets_path}...")
    graph = StreetGraph(data=streets_path)

    # Convert the graph to a serializable adjacency list
    adjacency = {}
    for node in graph.graph.nodes:
        canonical_name = graph.canonical_names[node]
        neighbors = [
            graph.canonical_names[neighbor]
            for neighbor in graph.graph.neighbors(node)
        ]
        adjacency[canonical_name] = sorted(neighbors)

    out_path = Path(save_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(adjacency, f, ensure_ascii=False, indent=2)

    print(f"Successfully built graph with {graph.graph.number_of_nodes()} nodes and {graph.graph.number_of_edges()} edges.")
    print(f"Saved adjacency list to {out_path}")


def handle_path(streets_path: str, src: str, dst: str) -> None:
    """Find and print the shortest path (minimum street changes) between two streets.

    Parameters
    ----------
    streets_path : str
        Path to the GeoJSON streets file.
    src : str
        The starting street name.
    dst : str
        The target street name.
    """
    if not Path(streets_path).exists():
        print(f"Error: GeoJSON file not found: {streets_path}", file=sys.stderr)
        sys.exit(1)

    graph = StreetGraph(data=streets_path)
    path = graph.shortest_path(src, dst)

    if path:
        print(" -> ".join(path))
    else:
        print(f"No path found between '{src}' and '{dst}'.", file=sys.stderr)
        sys.exit(1)


def handle_intersects(streets_path: str, street: str) -> None:
    """List all streets that intersect the given street.

    Parameters
    ----------
    streets_path : str
        Path to the GeoJSON streets file.
    street : str
        The name of the target street.
    """
    if not Path(streets_path).exists():
        print(f"Error: GeoJSON file not found: {streets_path}", file=sys.stderr)
        sys.exit(1)

    graph = StreetGraph(data=streets_path)
    intersections = graph.intersecting_streets(street)

    if intersections:
        for name in intersections:
            print(name)
    else:
        print(f"No intersections found for '{street}'.")


def handle_quiz(streets_path: str, n: int, out_path: str, types_str: str) -> None:
    """Generate random quiz questions and export them to a JSON file.

    Parameters
    ----------
    streets_path : str
        Path to the GeoJSON streets file.
    n : int
        Number of questions to generate.
    out_path : str
        Path to the output JSON file.
    types_str : str
        Comma-separated list of question types to generate.
    """
    if not Path(streets_path).exists():
        print(f"Error: GeoJSON file not found: {streets_path}", file=sys.stderr)
        sys.exit(1)

    # Initialize graph and generator
    graph = StreetGraph(data=streets_path)
    generator = QuestionGenerator(segments=graph.gdf)

    print(f"Generating {n} questions of types [{types_str}]...")
    today = date.today()
    questions = generator.generate_for_date(today, n)

    # Filter generated questions by type if needed
    allowed_types = [t.strip().upper() for t in types_str.split(",") if t.strip()]
    
    payload = []
    for index, q in enumerate(questions, start=1):
        q_type_upper = q.question_type.upper()
        # Handle backward compatibility question type names mapping
        mapped_type = q_type_upper
        if q_type_upper == "SHORTEST_PATH":
            mapped_type = "PATH"
        elif q_type_upper == "PERPENDICULAR":
            mapped_type = "INTERSECTS"

        # Check if the type is requested
        if mapped_type in allowed_types or q.question_type in allowed_types:
            payload.append({
                "id": index,
                "question_type": q.question_type,
                "prompt": q.prompt,
                "choices": q.choices,
                "answer": q.answer,
                "answer_guide": q.answer_guide,
                "metadata": q.metadata
            })

    # If the list is empty, write all generated questions
    if not payload:
        for index, q in enumerate(questions, start=1):
            payload.append({
                "id": index,
                "question_type": q.question_type,
                "prompt": q.prompt,
                "choices": q.choices,
                "answer": q.answer,
                "answer_guide": q.answer_guide,
                "metadata": q.metadata
            })

    output_file = Path(out_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(payload[:n], f, ensure_ascii=False, indent=2)

    print(f"Saved {len(payload[:n])} questions to {output_file}")


def main() -> None:
    """Entry point for CLI subcommand parsing and routing."""
    parser = argparse.ArgumentParser(
        description="CLI tool to build connectivity graphs and generate quizzes from streets GeoJSON."
    )
    subparsers = parser.add_subparsers(dest="command", required=True, help="Subcommand to run.")

    # 1. build subcommand
    parser_build = subparsers.add_parser("build", help="Build connectivity graph and save to JSON.")
    parser_build.add_argument("--streets", type=str, required=True, help="Path to streets GeoJSON.")
    parser_build.add_argument("--save", type=str, required=True, help="Path to save JSON adjacency.")

    # 2. path subcommand
    parser_path = subparsers.add_parser("path", help="Find shortest path between two streets.")
    parser_path.add_argument("--streets", type=str, required=True, help="Path to streets GeoJSON.")
    parser_path.add_argument("--src", type=str, required=True, help="Source street name.")
    parser_path.add_argument("--dst", type=str, required=True, help="Destination street name.")

    # 3. intersects subcommand
    parser_intersects = subparsers.add_parser("intersects", help="List intersecting streets.")
    parser_intersects.add_argument("--streets", type=str, required=True, help="Path to streets GeoJSON.")
    parser_intersects.add_argument("--street", type=str, required=True, help="Target street name.")

    # 4. quiz subcommand
    parser_quiz = subparsers.add_parser("quiz", help="Generate random quiz questions.")
    parser_quiz.add_argument("--streets", type=str, required=True, help="Path to streets GeoJSON.")
    parser_quiz.add_argument("-n", type=int, default=10, help="Number of questions to generate.")
    parser_quiz.add_argument("--out", type=str, required=True, help="Path to save JSON quiz.")
    parser_quiz.add_argument(
        "--types",
        type=str,
        default="path,intersects,count,open_intersections",
        help="Comma-separated question types (path, intersects, count, open_intersections)."
    )

    args = parser.parse_args()

    if args.command == "build":
        handle_build(args.streets, args.save)
    elif args.command == "path":
        handle_path(args.streets, args.src, args.dst)
    elif args.command == "intersects":
        handle_intersects(args.streets, args.street)
    elif args.command == "quiz":
        handle_quiz(args.streets, args.n, args.out, args.types)


if __name__ == "__main__":
    main()
