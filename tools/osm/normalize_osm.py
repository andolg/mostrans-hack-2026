#!/usr/bin/env python3
"""Normalize an Overpass JSON response into route and stop GeoJSON files."""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def feature_collection(features: list[dict[str, Any]]) -> dict[str, Any]:
    return {"type": "FeatureCollection", "features": features}


def line_feature(relation: dict[str, Any], way: dict[str, Any], sequence: int, nodes: dict[int, dict[str, Any]]) -> dict[str, Any] | None:
    coordinates = [
        [nodes[node_id]["lon"], nodes[node_id]["lat"]]
        for node_id in way.get("nodes", [])
        if node_id in nodes and "lon" in nodes[node_id]
    ]
    if len(coordinates) < 2:
        return None
    tags = relation.get("tags", {})
    relation_id = int(relation["id"])
    route_id = f"osm-rel:{relation_id}"
    route_ref = tags.get("ref") or tags.get("name") or str(relation_id)
    route_name = tags.get("name") or f"Трамвай {route_ref}"
    way_nodes = way.get("nodes", [])
    return {
        "type": "Feature",
        "geometry": {"type": "LineString", "coordinates": coordinates},
        "properties": {
            "segmentId": f"{route_id}:way:{way['id']}:{sequence}",
            "routeId": route_id,
            "routeName": route_name,
            "routeRef": route_ref,
            "relationId": relation_id,
            "fromStopId": f"osm:{way_nodes[0]}" if way_nodes else "",
            "toStopId": f"osm:{way_nodes[-1]}" if way_nodes else "",
            "sequence": sequence,
            "osmWayId": int(way["id"]),
        },
    }


def stop_coordinate(element_type: str, ref: int, nodes: dict[int, dict[str, Any]], ways: dict[int, dict[str, Any]]) -> list[float] | None:
    if element_type == "node" and ref in nodes:
        node = nodes[ref]
        if "lon" in node and "lat" in node:
            return [node["lon"], node["lat"]]
    if element_type == "way" and ref in ways:
        coordinates = [
            [nodes[node_id]["lon"], nodes[node_id]["lat"]]
            for node_id in ways[ref].get("nodes", [])
            if node_id in nodes and "lon" in nodes[node_id]
        ]
        if coordinates:
            return [sum(x for x, _ in coordinates) / len(coordinates), sum(y for _, y in coordinates) / len(coordinates)]
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    payload = json.loads(args.input.read_text(encoding="utf-8"))
    elements = payload.get("elements", [])
    nodes = {int(item["id"]): item for item in elements if item.get("type") == "node"}
    ways = {int(item["id"]): item for item in elements if item.get("type") == "way"}
    relations = [item for item in elements if item.get("type") == "relation" and item.get("tags", {}).get("route") == "tram"]

    route_features: list[dict[str, Any]] = []
    stop_routes: dict[tuple[str, int], set[str]] = defaultdict(set)
    stop_names: dict[tuple[str, int], str] = {}

    for relation in relations:
        route_id = f"osm-rel:{relation['id']}"
        sequence = 0
        for member in relation.get("members", []):
            member_type = member.get("type", "")
            ref = int(member.get("ref", 0))
            role = member.get("role", "").lower()
            if member_type == "way" and ref in ways and role not in {"platform", "stop", "stop_entry_only", "stop_exit_only"}:
                feature = line_feature(relation, ways[ref], sequence, nodes)
                if feature:
                    route_features.append(feature)
                    sequence += 1
            member_tags = (nodes.get(ref) if member_type == "node" else ways.get(ref, {})).get("tags", {})
            is_stop = (
                "stop" in role
                or "platform" in role
                or member_tags.get("railway") in {"tram_stop", "platform"}
                or member_tags.get("public_transport") in {"stop_position", "platform"}
            )
            if is_stop:
                key = (member_type, ref)
                stop_routes[key].add(route_id)
                stop_names[key] = member_tags.get("name") or member_tags.get("official_name") or "Без названия"

    # Retain tagged tram stops even when a relation omits explicit platform membership.
    for node_id, node in nodes.items():
        tags = node.get("tags", {})
        if tags.get("railway") == "tram_stop" or (tags.get("public_transport") in {"stop_position", "platform"} and tags.get("tram") == "yes"):
            key = ("node", node_id)
            stop_names.setdefault(key, tags.get("name") or "Без названия")

    stop_features: list[dict[str, Any]] = []
    for (element_type, ref), name in stop_names.items():
        coordinate = stop_coordinate(element_type, ref, nodes, ways)
        if not coordinate:
            continue
        stop_id = f"osm:{ref}" if element_type == "node" else f"osm:way:{ref}"
        stop_features.append({
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": coordinate},
            "properties": {
                "stopId": stop_id,
                "name": name,
                "osmId": ref,
                "routeIds": sorted(stop_routes.get((element_type, ref), set())),
            },
        })

    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "tram_routes.geojson").write_text(json.dumps(feature_collection(route_features), ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    (args.output / "tram_stops.geojson").write_text(json.dumps(feature_collection(stop_features), ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    metadata = {
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "source": "OpenStreetMap contributors via Overpass API",
        "license": "ODbL 1.0",
        "routeCount": len(relations),
        "segmentCount": len(route_features),
        "stopCount": len(stop_features),
        "relationIds": [int(relation["id"]) for relation in relations],
    }
    (args.output / "metadata.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {len(relations)} routes, {len(route_features)} segments, {len(stop_features)} stops to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

