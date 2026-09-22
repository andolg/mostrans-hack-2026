#!/usr/bin/env python3
"""Generate deterministic, structured synthetic tram demand forecasts."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


MOSCOW_TZ = timezone(timedelta(hours=3))
HORIZONS = ("day", "month", "year")


def stable_rng(seed: int, identifier: str) -> random.Random:
    digest = hashlib.sha256(f"{seed}:{identifier}".encode()).digest()
    return random.Random(int.from_bytes(digest[:8], "big"))


def timestamps(start: datetime, horizon: str) -> list[datetime]:
    if horizon == "day":
        return [start + timedelta(minutes=15 * index) for index in range(96)]
    if horizon == "month":
        return [start + timedelta(hours=index) for index in range(24 * 30)]
    return [start + timedelta(days=index) for index in range(365)]


def gaussian(value: float, center: float, width: float) -> float:
    return math.exp(-((value - center) ** 2) / (2 * width**2))


def route_params(seed: int, route_id: str) -> dict[str, float]:
    rng = stable_rng(seed, route_id)
    return {
        "base": rng.uniform(35, 70),
        "morning_amp": rng.uniform(90, 190),
        "evening_amp": rng.uniform(85, 175),
        "morning_time": rng.uniform(7.25, 9.25),
        "evening_time": rng.uniform(16.5, 19.5),
        "morning_width": rng.uniform(0.6, 1.3),
        "evening_width": rng.uniform(0.8, 1.6),
        "capacity": rng.uniform(175, 245),
        "weekend_sat": rng.uniform(0.70, 0.85),
        "weekend_sun": rng.uniform(0.60, 0.80),
        "season_amp": rng.uniform(0.05, 0.14),
        "season_phase": rng.uniform(0, 45),
        "trend": rng.uniform(0.01, 0.065),
        "shape": rng.uniform(0.75, 1.45),
    }


def make_route_points(seed: int, route_id: str, horizon: str, start: datetime) -> list[dict[str, Any]]:
    params = route_params(seed, route_id)
    rng = stable_rng(seed, f"{route_id}:{horizon}")
    uncertainty = {"day": rng.uniform(0.08, 0.14), "month": rng.uniform(0.14, 0.21), "year": rng.uniform(0.22, 0.34)}[horizon]
    result = []
    for stamp in timestamps(start, horizon):
        hour = stamp.hour + stamp.minute / 60
        demand = params["base"]
        if horizon != "year":
            demand += params["morning_amp"] * gaussian(hour, params["morning_time"], params["morning_width"])
            demand += params["evening_amp"] * gaussian(hour, params["evening_time"], params["evening_width"])
        else:
            demand += 0.42 * (params["morning_amp"] + params["evening_amp"])
        weekday = stamp.weekday()
        if weekday == 4:
            demand *= rng.uniform(0.96, 1.04)
        elif weekday == 5:
            demand *= params["weekend_sat"]
        elif weekday == 6:
            demand *= params["weekend_sun"]
        day_of_year = stamp.timetuple().tm_yday
        demand *= 1 + params["season_amp"] * math.cos(2 * math.pi * (day_of_year - params["season_phase"]) / 365)
        demand *= 1 + params["trend"] * max(0, (stamp - start).days) / 365
        noise = {"day": 0.035, "month": 0.045, "year": 0.025}[horizon]
        demand *= 1 + rng.gauss(0, noise)
        demand = max(0, demand)
        load = min(1.4, demand / params["capacity"])
        result.append({
            "timestamp": stamp.isoformat(),
            "predictedBoardings": round(demand),
            "predictedLoad": round(load, 4),
            "p10": round(max(0, load * (1 - uncertainty)), 4),
            "p50": round(load, 4),
            "p90": round(min(1.5, load * (1 + uncertainty)), 4),
            "loadP10": round(max(0, load * (1 - uncertainty)), 4),
            "loadP90": round(min(1.5, load * (1 + uncertainty)), 4),
            "boardingsP10": round(demand * (1 - uncertainty)),
            "boardingsP90": round(demand * (1 + uncertainty)),
        })
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--osm-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--start-date", default="2026-09-23")
    args = parser.parse_args()
    start = datetime.fromisoformat(args.start_date).replace(tzinfo=MOSCOW_TZ)

    routes_geo = json.loads((args.osm_dir / "tram_routes.geojson").read_text(encoding="utf-8"))
    stops_geo = json.loads((args.osm_dir / "tram_stops.geojson").read_text(encoding="utf-8"))
    route_segments: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for feature in routes_geo["features"]:
        route_segments[feature["properties"]["routeId"]].append(feature["properties"])

    route_forecasts: dict[str, dict[str, list[dict[str, Any]]]] = {}
    segment_profiles: dict[str, dict[str, Any]] = {}
    for route_id, segments in route_segments.items():
        route_forecasts[route_id] = {horizon: make_route_points(args.seed, route_id, horizon, start) for horizon in HORIZONS}
        params = route_params(args.seed, route_id)
        sorted_segments = sorted(segments, key=lambda item: item["sequence"])
        denominator = max(1, len(sorted_segments) - 1)
        for index, segment in enumerate(sorted_segments):
            position = index / denominator
            factor = 0.4 + 0.9 * math.sin(math.pi * position) ** params["shape"]
            factor *= 1 + stable_rng(args.seed, segment["segmentId"]).uniform(-0.045, 0.045)
            segment_profiles[segment["segmentId"]] = {"routeId": route_id, "factor": round(factor, 4)}

    stop_profiles: dict[str, dict[str, Any]] = {}
    route_ids = list(route_forecasts)
    for feature in stops_geo["features"]:
        properties = feature["properties"]
        stop_id = properties["stopId"]
        served = [route_id for route_id in properties.get("routeIds", []) if route_id in route_forecasts] or route_ids[:1]
        rng = stable_rng(args.seed, stop_id)
        importance = rng.uniform(0.38, 0.83) * (1 + 0.23 * max(0, len(served) - 1))
        if len(served) >= 3:
            importance *= 1.45
        stop_profiles[stop_id] = {"routeIds": served, "factor": round(importance, 4)}

    metadata = {
        "generatedAt": start.isoformat(),
        "seed": args.seed,
        "model": "synthetic-gaussian-v1",
        "horizonDescriptions": {"day": "15 минут / 24 часа", "month": "1 час / 30 дней", "year": "1 день / 365 дней"},
    }
    args.output.mkdir(parents=True, exist_ok=True)
    compact = {"ensure_ascii": False, "separators": (",", ":")}
    (args.output / "route_forecasts.json").write_text(json.dumps({"metadata": metadata, "routes": route_forecasts, "segmentProfiles": segment_profiles}, **compact), encoding="utf-8")
    (args.output / "stop_forecasts.json").write_text(json.dumps({"metadata": metadata, "stopProfiles": stop_profiles}, **compact), encoding="utf-8")
    (args.output / "metadata.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Generated forecasts for {len(route_forecasts)} routes, {len(segment_profiles)} segments and {len(stop_profiles)} stops")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
