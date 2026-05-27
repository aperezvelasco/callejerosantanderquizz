"""Utilities for loading, querying, and verifying the Santander street network."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, Iterator, List, Optional, Set

import geopandas as gpd
import networkx as nx
import shapely
from pyproj import Transformer
from shapely.geometry import Point
from shapely.ops import nearest_points, transform


@dataclass(frozen=True)
class StreetSegment:
    """Representation of a street segment between two intersections.

    Parameters
    ----------
    street : str
        The name of the main street.
    from_street : str, optional
        The name of the street intersecting at the start.
    to_street : str, optional
        The name of the street intersecting at the end.
    """

    street: str
    from_street: Optional[str]
    to_street: Optional[str]

    def intersections(self) -> Set[str]:
        """Return the set of intersecting streets for the segment.

        Returns
        -------
        Set[str]
            A set containing the non-null intersecting street names.
        """
        return {name for name in (self.from_street, self.to_street) if name}


def normalize_street_name(name: str) -> str:
    """Normalize a street name for comparison and grouping.

    This removes common Spanish street prefixes, normalizes accents,
    removes special characters, and converts to lowercase.

    Parameters
    ----------
    name : str
        The raw street name to normalize.

    Returns
    -------
    str
        The normalized street name.
    """
    if not isinstance(name, str):
        return ""
    # Lowercase and strip
    n = name.lower().strip()

    # Standardize abbreviations and prefixes
    # Use regex to strip prefixes at the start of the string
    prefixes = [
        r"^calle\s+",
        r"^c/\s*",
        r"^c\.\s*",
        r"^avenida\s+",
        r"^avda\.\s*",
        r"^avda\s+",
        r"^plaza\s+",
        r"^pl\.\s*",
        r"^paseo\s+",
        r"^pº\s*",
        r"^travesía\s+",
        r"^trav\.\s*",
        r"^grupo\s+",
        r"^gp\.\s*",
        r"^barrio\s+",
        r"^bo\.\s*",
        r"^vía\s+",
        r"^via\s+",
        r"^cuesta\s+",
        r"^subida\s+",
        r"^pasaje\s+",
        r"^ronda\s+",
        r"^carretera\s+",
        r"^crta\.\s*",
        r"^callejón\s+",
        r"^autovía\s+",
        r"^autovia\s+",
        r"^camino\s+",
    ]
    for pattern in prefixes:
        n = re.sub(pattern, "", n)

    # Strip common Spanish prepositions and articles at the start (e.g. "de la", "del", "de")
    n = re.sub(
        r"^(de\s+la\s+|de\s+los\s+|de\s+las\s+|de\s+|del\s+|la\s+|el\s+|los\s+|las\s+)",
        "",
        n,
    )

    # Replace Spanish accents
    trans = str.maketrans("áéíóúüâêîôûàèìòùäëïöü", "aeiouuaeiouaeiouaeiou")
    n = n.translate(trans)

    # Keep only alphanumeric characters, spaces, hyphens, and ñ
    n = re.sub(r"[^a-z0-9\s\-_ñ]", "", n)

    # Normalize spaces
    n = re.sub(r"\s+", " ", n).strip()
    return n


class StreetDatasetLoader:
    """Load and parse street segments or GeoJSON geometries.

    Parameters
    ----------
    dataset_url : str, optional
        Unused URL parameter (retained for backward compatibility).
    cache_path : Path, optional
        The path to the GeoJSON or JSON street cache file.
    """

    def __init__(
        self, dataset_url: Optional[str] = None, cache_path: Optional[Path] = None
    ) -> None:
        self.cache_path = cache_path or Path("streets_santander_muni.geojson")
        self.sample_path = Path("data") / "sample_callejero_tramos.json"

    def load(self, *, force_refresh: bool = False) -> Any:
        """Return the loaded street dataset.

        Returns a GeoDataFrame if loading a GeoJSON file, or a list of
        StreetSegment objects if loading the old segment JSON format.

        Parameters
        ----------
        force_refresh : bool, default False
            Unused refresh parameter (retained for backward compatibility).

        Returns
        -------
        Any
            gpd.GeoDataFrame or List[StreetSegment] containing street data.
        """
        # If cache path is GeoJSON and exists, load it
        if self.cache_path.suffix == ".geojson":
            if self.cache_path.exists():
                return gpd.read_file(self.cache_path)
            # If not exists, fall back to segment JSON sample
            if self.sample_path.exists():
                return self._load_from_json(self.sample_path)
            raise FileNotFoundError("No street dataset available")

        # Otherwise, load old segment JSON format
        if self.cache_path.exists():
            return self._load_from_json(self.cache_path)
        return self._load_from_json(self.sample_path)

    def _load_from_json(self, path: Path) -> List[StreetSegment]:
        """Load and parse segments stored in a local JSON file.

        Parameters
        ----------
        path : Path
            The path to the JSON file.

        Returns
        -------
        List[StreetSegment]
            List of parsed StreetSegment objects.
        """
        if not path.exists():
            raise FileNotFoundError(f"Dataset file not found: {path}")

        raw_data = json.loads(path.read_text(encoding="utf-8"))
        records: List[Dict[str, Any]] = []

        if isinstance(raw_data, list):
            records = raw_data
        elif isinstance(raw_data, dict):
            # Recursively find records in dictionary payload
            records = list(self._walk_records(raw_data))

        segments: List[StreetSegment] = []
        for item in records:
            street = (
                item.get("calle")
                or item.get("nombre")
                or item.get("via")
                or item.get("street")
            )
            from_street = (
                item.get("desde") or item.get("inicio") or item.get("from_street")
            )
            to_street = item.get("hasta") or item.get("fin") or item.get("to_street")

            if street:
                segments.append(
                    StreetSegment(
                        street=street.strip(),
                        from_street=from_street.strip() if from_street else None,
                        to_street=to_street.strip() if to_street else None,
                    )
                )
        return segments

    def _walk_records(self, payload: Any) -> Iterator[Dict[str, Any]]:
        """Recursively yield dictionaries from nested payloads.

        Parameters
        ----------
        payload : Any
            The payload to traverse.

        Yields
        ------
        Dict[str, Any]
            Dictionaries found inside the payload.
        """
        if isinstance(payload, dict):
            if any(key in payload for key in ("calle", "nombre", "via", "street")):
                yield payload
            for value in payload.values():
                yield from self._walk_records(value)
        elif isinstance(payload, list):
            for item in payload:
                yield from self._walk_records(item)


class StreetGraph:
    """Graph representation of street connectivity and spatial indices.

    Supports building connectivity from raw segments or a GeoJSON file,
    finding paths, and checking map click guesses.

    Parameters
    ----------
    data : Any, optional
        An iterable of StreetSegment objects or a GeoDataFrame to load.
    """

    def __init__(self, data: Optional[Any] = None) -> None:
        self.graph: nx.Graph = nx.Graph()
        self.canonical_names: Dict[str, str] = {}
        self.geometries: Dict[str, shapely.geometry.base.BaseGeometry] = {}
        self.gdf: Optional[gpd.GeoDataFrame] = None
        self.tree: Optional[shapely.STRtree] = None

        if data is not None:
            if isinstance(data, gpd.GeoDataFrame):
                self.load_from_gdf(data)
            elif isinstance(data, (str, Path)):
                self.load_from_geojson(Path(data))
            else:
                # Assume iterable of StreetSegment
                self._build_from_segments(data)

    def _build_from_segments(self, segments: Iterable[StreetSegment]) -> None:
        """Build the connectivity graph from street segments.

        Parameters
        ----------
        segments : Iterable[StreetSegment]
            The segments containing street names and intersections.
        """
        for segment in segments:
            street = segment.street
            norm_street = normalize_street_name(street)
            if not norm_street:
                continue

            self.canonical_names[norm_street] = street
            self.graph.add_node(norm_street)

            for neighbor in segment.intersections():
                norm_neighbor = normalize_street_name(neighbor)
                if not norm_neighbor or norm_neighbor == norm_street:
                    continue

                self.canonical_names[norm_neighbor] = neighbor
                self.graph.add_node(norm_neighbor)
                self.graph.add_edge(norm_street, norm_neighbor)

    def load_from_gdf(self, gdf: gpd.GeoDataFrame) -> None:
        """Load and build the connectivity graph from a GeoDataFrame.

        Parameters
        ----------
        gdf : gpd.GeoDataFrame
            The GeoDataFrame containing columns name, normalized_name, geometry.
        """
        self.gdf = gdf
        self.graph.clear()
        self.canonical_names.clear()
        self.geometries.clear()

        # Add all streets as nodes
        for _, row in self.gdf.iterrows():
            name = row["name"]
            norm_name = row["normalized_name"]
            geom = row["geometry"]
            self.canonical_names[norm_name] = name
            self.geometries[norm_name] = geom
            self.graph.add_node(norm_name)

        # Build spatial index
        geoms = self.gdf.geometry.values
        self.tree = shapely.STRtree(geoms)

        # Query all intersecting bounding boxes and verify exact intersection
        left_idx, right_idx = self.tree.query(geoms, predicate="intersects")

        for idx_a, idx_b in zip(left_idx, right_idx):
            if idx_a >= idx_b:
                continue

            norm_a = self.gdf.iloc[idx_a]["normalized_name"]
            norm_b = self.gdf.iloc[idx_b]["normalized_name"]

            if norm_a != norm_b:
                self.graph.add_edge(norm_a, norm_b)

    def load_from_geojson(self, geojson_path: Path) -> None:
        """Load and build the connectivity graph from a GeoJSON file.

        Parameters
        ----------
        geojson_path : Path
            The path to the GeoJSON file.
        """
        gdf = gpd.read_file(geojson_path)
        self.load_from_gdf(gdf)

    def shortest_path(self, start: str, goal: str) -> Optional[List[str]]:
        """Compute the shortest path (minimum street changes) between two streets.

        Parameters
        ----------
        start : str
            The name of the starting street.
        goal : str
            The name of the target street.

        Returns
        -------
        List[str], optional
            The sequence of canonical street names in the path, or None if no path exists.
        """
        norm_start = normalize_street_name(start)
        norm_goal = normalize_street_name(goal)

        if norm_start not in self.graph or norm_goal not in self.graph:
            return None

        try:
            path = nx.shortest_path(self.graph, source=norm_start, target=norm_goal)
            return [self.canonical_names[node] for node in path]
        except nx.NetworkXNoPath:
            return None

    def intersecting_streets(self, street: str) -> List[str]:
        """Return streets that intersect the provided street.

        Parameters
        ----------
        street : str
            The name of the query street.

        Returns
        -------
        List[str]
            Sorted list of canonical intersecting street names.
        """
        norm_street = normalize_street_name(street)
        if norm_street not in self.graph:
            return []
        return sorted(
            self.canonical_names[n] for n in self.graph.neighbors(norm_street)
        )

    def candidate_streets(self) -> List[str]:
        """Return streets that have at least one intersection.

        Returns
        -------
        List[str]
            Sorted list of canonical street names.
        """
        return sorted(
            self.canonical_names[node]
            for node, degree in self.graph.degree()
            if degree > 0
        )

    def guess_street(
        self, street_name: str, lat: float, lng: float, threshold_meters: float = 15.0
    ) -> Dict[str, Any]:
        """Evaluate a map click guess against the target street.

        Calculates distance in meters using EPSG:25830 projection, finds the
        closest point on the street line, and builds a GeoJSON geometry response.

        Parameters
        ----------
        street_name : str
            The name of the target street to guess.
        lat : float
            The latitude of the user's click guess.
        lng : float
            The longitude of the user's click guess.
        threshold_meters : float, default 15.0
            The maximum distance in meters to consider the guess correct.

        Returns
        -------
        Dict[str, Any]
            Dictionary containing distance, correctness, closest point, and geometry.
        """
        norm_name = normalize_street_name(street_name)
        if norm_name not in self.geometries:
            raise ValueError(f"Street '{street_name}' not found in dataset")

        geom = self.geometries[norm_name]
        guess_point = Point(lng, lat)

        # Project to UTM 30N (EPSG:25830) for metric distance calculations
        to_utm = Transformer.from_crs("EPSG:4326", "EPSG:25830", always_xy=True)
        to_wgs84 = Transformer.from_crs("EPSG:25830", "EPSG:4326", always_xy=True)

        projected_geom = transform(to_utm.transform, geom)
        projected_guess = transform(to_utm.transform, guess_point)

        # Distance calculation
        distance = projected_geom.distance(projected_guess)

        # Get closest point on street line
        nearest_geom_pt, _ = nearest_points(projected_geom, projected_guess)
        closest_lng, closest_lat = to_wgs84.transform(
            nearest_geom_pt.x, nearest_geom_pt.y
        )

        # Serialize shapely geometry
        geojson_geom = shapely.geometry.mapping(geom)

        return {
            "street_name": self.canonical_names[norm_name],
            "distance_meters": round(distance, 2),
            "is_correct": distance <= threshold_meters,
            "closest_point": {"lat": closest_lat, "lng": closest_lng},
            "street_geometry": geojson_geom,
        }


_global_graph: Optional[StreetGraph] = None


def get_street_graph() -> StreetGraph:
    """Get or initialize the global cached StreetGraph instance.

    Returns
    -------
    StreetGraph
        The cached graph instance.
    """
    global _global_graph
    if _global_graph is None:
        geojson_path = Path("streets_santander_muni.geojson")
        if geojson_path.exists():
            _global_graph = StreetGraph(data=geojson_path)
        else:
            loader = StreetDatasetLoader()
            segments = loader.load()
            _global_graph = StreetGraph(segments)
    return _global_graph
