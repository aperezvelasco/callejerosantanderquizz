"""Utilities for loading and querying the Santander street dataset."""
from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, Iterable, Iterator, List, Optional, Sequence, Set
from urllib.error import URLError
from urllib.request import Request, urlopen

try:  # pragma: no cover - optional dependency during testing
    from ..core.config import get_settings
except Exception:  # pylint: disable=broad-except
    get_settings = None  # type: ignore[assignment]


@dataclass(frozen=True)
class StreetSegment:
    """Representation of a street segment between two intersections."""

    street: str
    from_street: Optional[str]
    to_street: Optional[str]

    def intersections(self) -> Set[str]:
        """Return the set of intersecting streets for the segment."""

        return {name for name in (self.from_street, self.to_street) if name}


class StreetDatasetLoader:
    """Load and cache street segments from the Santander open data portal."""

    def __init__(self, dataset_url: Optional[str] = None, cache_path: Optional[Path] = None) -> None:
        default_url = "https://datos.santander.es/api/rest/datasets/callejero_tramos.json"
        if get_settings is not None:
            settings = get_settings()
            default_url = settings.callejero_dataset_url
        self.dataset_url = dataset_url or default_url
        self.local_dataset_path = Path("data") / "callejero_santander.json"
        self.cache_path = cache_path or Path("data") / "callejero_segments.json"
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)

    def load(self, *, force_refresh: bool = False) -> List[StreetSegment]:
        """Return the list of street segments, using cache or downloading."""

        if self.local_dataset_path.exists() and not force_refresh:
            return self._load_from_file(self.local_dataset_path)

        if self.cache_path.exists() and not force_refresh:
            return self._load_from_file(self.cache_path)

        try:
            segments = self._download_segments()
        except Exception as exc:
            if self.local_dataset_path.exists():
                segments = self._load_from_file(self.local_dataset_path)
            elif self.cache_path.exists():
                segments = self._load_from_file(self.cache_path)
            else:
                raise RuntimeError(
                    "Unable to load street dataset. Provide data/callejero_santander.json"
                ) from exc
        else:
            self._write_cache(segments)

        return segments

    def _download_segments(self) -> List[StreetSegment]:
        """Download the dataset from the remote API."""

        request = Request(self.dataset_url, headers={"User-Agent": "callejero-quizz-bot"})
        try:
            with urlopen(request, timeout=30) as response:  # nosec B310
                charset = response.headers.get_content_charset() or "utf-8"
                raw = response.read().decode(charset)
        except URLError as exc:
            raise ConnectionError("Unable to download street dataset") from exc

        payload = json.loads(raw)

        segments = list(self._parse_segments(payload))
        if not segments:
            raise ValueError("Dataset did not contain any street segments")
        return segments

    def _load_from_file(self, path: Path) -> List[StreetSegment]:
        """Load segments stored in a local JSON file."""

        if not path.exists():
            raise FileNotFoundError(f"Dataset file not found: {path}")
        data = json.loads(path.read_text(encoding="utf-8"))
        return list(self._parse_segments(data))

    def _write_cache(self, segments: Sequence[StreetSegment]) -> None:
        """Persist segments into the cache path."""

        serialisable = [asdict(segment) for segment in segments]
        self.cache_path.write_text(json.dumps(serialisable, ensure_ascii=False, indent=2), encoding="utf-8")

    def _parse_segments(self, data: object) -> Iterator[StreetSegment]:
        """Yield :class:`StreetSegment` objects from raw dataset payloads."""

        if isinstance(data, list):
            for item in data:
                yield from self._parse_segments(item)
            return

        if isinstance(data, dict):
            traversed = False
            for key in ("resources", "data", "items", "dataset"):
                value = data.get(key)
                if isinstance(value, (list, dict)):
                    traversed = True
                    yield from self._parse_segments(value)
            if traversed:
                return

            record = data
            street = self._find_value(record, {"calle", "nombre", "via", "nombre_via", "nom_calle"})
            from_street = self._find_value(record, {"desde", "inicio", "desde_calle", "ini"})
            to_street = self._find_value(record, {"hasta", "fin", "hasta_calle", "fin2", "final"})

            if street:
                yield StreetSegment(street=_clean_name(street), from_street=_clean_name(from_street), to_street=_clean_name(to_street))
            return

    def _find_value(self, record: Dict[str, object], candidate_keys: Set[str]) -> Optional[str]:
        """Search for the first matching key in the record."""

        for key, value in _walk_items(record):
            if key.lower() in candidate_keys and isinstance(value, str):
                return value
        return None


class StreetGraph:
    """Graph abstraction for street intersections."""

    def __init__(self, segments: Iterable[StreetSegment]):
        self.segments: List[StreetSegment] = list(segments)
        self.adjacency: Dict[str, Set[str]] = {}
        self._build_graph()

    def _build_graph(self) -> None:
        for segment in self.segments:
            street = segment.street
            self.adjacency.setdefault(street, set())
            for neighbour in segment.intersections():
                cleaned = neighbour
                if not cleaned or cleaned.lower() == street.lower():
                    continue
                self.adjacency.setdefault(cleaned, set()).add(street)
                self.adjacency[street].add(cleaned)

    def intersecting_streets(self, street: str) -> List[str]:
        """Return streets that intersect the provided street."""

        return sorted(self.adjacency.get(street, []))

    def shortest_path(self, start: str, goal: str) -> Optional[List[str]]:
        """Compute the shortest path between two streets using BFS."""

        if start not in self.adjacency or goal not in self.adjacency:
            return None
        if start == goal:
            return [start]

        queue: List[List[str]] = [[start]]
        visited: Set[str] = {start}

        while queue:
            path = queue.pop(0)
            node = path[-1]
            for neighbour in sorted(self.adjacency.get(node, [])):
                if neighbour in visited:
                    continue
                new_path = path + [neighbour]
                if neighbour == goal:
                    return new_path
                visited.add(neighbour)
                queue.append(new_path)
        return None

    def candidate_streets(self) -> List[str]:
        """Return streets that have at least one intersection."""

        return sorted(street for street, neighbours in self.adjacency.items() if neighbours)


def _walk_items(payload: object) -> Iterator[tuple[str, object]]:
    """Yield key/value pairs recursively from nested payloads."""

    if isinstance(payload, dict):
        for key, value in payload.items():
            yield key, value
            yield from _walk_items(value)
    elif isinstance(payload, list):
        for item in payload:
            yield from _walk_items(item)


def _clean_name(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned or None
