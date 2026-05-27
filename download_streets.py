#!/usr/bin/env python
"""Download and process street data from OpenStreetMap for a municipal area."""

from __future__ import annotations

import argparse
import re
import sys
from collections import Counter
from pathlib import Path
import geopandas as gpd
import osmnx as ox


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


def choose_canonical_name(names: list[str]) -> str:
    """Choose the best canonical name from a list of street name variants.

    Prefers names that are complete and well-formatted based on frequency.

    Parameters
    ----------
    names : list of str
        List of original street name variants.

    Returns
    -------
    str
        The chosen canonical street name.
    """
    valid_names = [n.strip() for n in names if n and n.strip()]
    if not valid_names:
        return ""
    # Heuristic: Sort to have deterministic choice.
    # Count frequencies
    counter = Counter(valid_names)
    most_common = counter.most_common()
    # Sort by frequency (descending) and length (descending)
    most_common.sort(key=lambda x: (-x[1], -len(x[0])))
    return most_common[0][0]


def main() -> None:
    """Parse command line arguments and execute the street extraction workflow."""
    parser = argparse.ArgumentParser(
        description="Download and process streets from OSM inside a municipal boundary."
    )
    parser.add_argument(
        "--place",
        type=str,
        default="Santander, Cantabria, Spain",
        help="The place name to fetch administrative boundary for.",
    )
    parser.add_argument(
        "--out",
        type=str,
        default="streets_santander_muni.geojson",
        help="Path to output GeoJSON file.",
    )
    parser.add_argument(
        "--footways",
        action="store_true",
        help="If set, include footways, paths, and cycleways.",
    )
    args = parser.parse_args()

    # Configure OSMnx settings for fast single-query and caching
    ox.settings.max_query_area_size = 2500000000
    ox.settings.use_cache = True

    print(f"Fetching administrative boundary for '{args.place}'...")
    try:
        # Use OSMnx 2.x features_from_place
        boundary_gdf = ox.features.features_from_place(
            args.place, tags={"boundary": "administrative", "admin_level": "8"}
        )
    except Exception as e:
        print(f"Error fetching boundary: {e}", file=sys.stderr)
        sys.exit(1)

    # Get the relation representing the municipality named "Santander"
    boundary_relation = boundary_gdf[
        (boundary_gdf.index.get_level_values("element") == "relation")
        & (boundary_gdf["name"] == "Santander")
    ]
    if boundary_relation.empty:
        boundary_relation = boundary_gdf[boundary_gdf["name"] == "Santander"]
    if boundary_relation.empty:
        boundary_relation = boundary_gdf[
            boundary_gdf.index.get_level_values("element") == "relation"
        ]
    if boundary_relation.empty:
        boundary_relation = boundary_gdf[
            boundary_gdf.geom_type.isin(["Polygon", "MultiPolygon"])
        ]

    if boundary_relation.empty:
        print("Error: No administrative boundary polygon found.", file=sys.stderr)
        sys.exit(1)

    if hasattr(boundary_relation, "union_all"):
        boundary_geom = boundary_relation.union_all()
    else:
        boundary_geom = boundary_relation.unary_union
    print("Successfully retrieved municipal boundary.")

    # Save boundary polygon for the frontend
    try:
        boundary_path = Path("data") / "santander_boundary.geojson"
        boundary_path.parent.mkdir(parents=True, exist_ok=True)
        gpd.GeoDataFrame(geometry=[boundary_geom], crs="epsg:4326").to_file(
            boundary_path, driver="GeoJSON"
        )
        print(f"Saved municipal boundary to {boundary_path}")
    except Exception as e:
        print(f"Warning: Could not save boundary GeoJSON: {e}", file=sys.stderr)

    print("Fetching street features inside the boundary...")
    try:
        # Fetch highway features inside the boundary geometry
        streets_gdf = ox.features.features_from_polygon(
            boundary_geom, tags={"highway": True}
        )
    except Exception as e:
        print(f"Error fetching street features: {e}", file=sys.stderr)
        sys.exit(1)

    print(f"Retrieved {len(streets_gdf)} total features. Processing...")

    # Ensure we have name column
    if "name" not in streets_gdf.columns:
        print(
            "Error: The downloaded features do not contain a 'name' column.",
            file=sys.stderr,
        )
        sys.exit(1)

    # Filter out features without name
    streets_gdf = streets_gdf[streets_gdf["name"].notna() & (streets_gdf["name"] != "")]

    # Define valid highway types
    valid_highways = [
        "motorway",
        "trunk",
        "primary",
        "secondary",
        "tertiary",
        "residential",
        "living_street",
        "service",
        "pedestrian",
        "motorway_link",
        "trunk_link",
        "primary_link",
        "secondary_link",
        "tertiary_link",
    ]
    if args.footways:
        valid_highways.extend(["footway", "path", "cycleway"])

    # Ensure highway column exists and filter
    if "highway" in streets_gdf.columns:
        streets_gdf = streets_gdf[streets_gdf["highway"].isin(valid_highways)]
    else:
        print(
            "Warning: 'highway' column not found, skipping highway filter.",
            file=sys.stderr,
        )

    if streets_gdf.empty:
        print("No streets found matching criteria.", file=sys.stderr)
        sys.exit(0)

    print("Clipping street geometries to the municipal boundary...")
    clipped_gdf = gpd.clip(streets_gdf, boundary_geom)

    # Filter out empty geometries post-clip
    clipped_gdf = clipped_gdf[~clipped_gdf.geometry.is_empty]

    if clipped_gdf.empty:
        print("No street geometries remained after boundary clipping.", file=sys.stderr)
        sys.exit(0)

    # Normalize street names and choose canonical names
    print("Normalizing street names and dissolving geometries...")
    clipped_gdf["normalized_name"] = clipped_gdf["name"].apply(normalize_street_name)

    # Filter out empty normalized names
    clipped_gdf = clipped_gdf[clipped_gdf["normalized_name"] != ""]

    canonical_map = {}
    for norm, group in clipped_gdf.groupby("normalized_name"):
        canonical_map[norm] = choose_canonical_name(group["name"].tolist())

    clipped_gdf["canonical_name"] = clipped_gdf["normalized_name"].map(canonical_map)

    # Dissolve by normalized name
    dissolved_gdf = clipped_gdf.dissolve(
        by="normalized_name", aggfunc={"canonical_name": "first"}
    )
    dissolved_gdf = dissolved_gdf.reset_index()
    dissolved_gdf = dissolved_gdf.rename(columns={"canonical_name": "name"})

    # Filter to only keep line geometries
    dissolved_gdf = dissolved_gdf[
        dissolved_gdf.geometry.type.isin(["LineString", "MultiLineString"])
    ]

    # Project to EPSG:25830 (UTM Zone 30N) for metric length calculation
    print("Calculating street lengths in meters...")
    projected_gdf = dissolved_gdf.to_crs(epsg=25830)
    dissolved_gdf["length"] = projected_gdf.geometry.length

    # Exclude very short remnants (length < 1 meter)
    dissolved_gdf = dissolved_gdf[dissolved_gdf["length"] > 1.0]

    # Sort alphabetically by canonical name
    dissolved_gdf = dissolved_gdf.sort_values(by="name")

    # Select final columns to save
    final_gdf = dissolved_gdf[["name", "normalized_name", "length", "geometry"]]

    # Save to GeoJSON
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    final_gdf.to_file(out_path, driver="GeoJSON")
    print(f"Exported {len(final_gdf)} streets to {out_path}")


if __name__ == "__main__":
    main()
