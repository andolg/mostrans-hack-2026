"""Measure resident-model prediction latency without HTTP or cache hits."""

import argparse
import json
import os
import random
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
import pandas as pd
import psutil

from predict_saved import SavedPredictor


def benchmark(models_dir: Path, requests: int, rps: int, workers: int) -> dict:
    process = psutil.Process()
    rss_before = process.memory_info().rss
    started = time.perf_counter()
    predictor = SavedPredictor(models_dir)
    load_ms = 1000 * (time.perf_counter() - started)

    dates = pd.date_range("2025-11-01", "2025-12-31").strftime("%Y-%m-%d")
    grid = pd.MultiIndex.from_product(
        [predictor.routes, dates, range(24)],
        names=["route", "date", "hour"],
    ).to_frame(index=False)
    one_day = grid.loc[(grid.route == 1) & (grid.date == "2025-11-03")]
    predictor.predict_one(1, "2025-11-03", 8)
    predictor.predict_frame(one_day)
    predictor.predict_frame(grid)

    batch_ms = {}
    batches = [
        ("route_day_24", one_day),
        ("all_routes_day_240", grid.loc[grid.date == "2025-11-03"]),
        ("route_month_720", grid.loc[(grid.route == 1) & (grid.date < "2025-12-01")]),
        ("all_routes_month_7200", grid.loc[grid.date < "2025-12-01"]),
        ("two_months_14640", grid),
    ]
    for name, frame in batches:
        times = []
        for _ in range(3):
            before = time.perf_counter()
            predictor.predict_frame(frame)
            times.append(1000 * (time.perf_counter() - before))
        batch_ms[name] = round(float(np.median(times)), 3)

    rng = random.Random(42)
    routes = [route for route in predictor.routes if route != 5]
    queries = [(rng.choice(routes), rng.choice(dates), rng.randrange(24))
               for _ in range(requests)]
    rss = [process.memory_info().rss]
    stopped = threading.Event()

    def sample_memory():
        while not stopped.wait(0.05):
            rss.append(process.memory_info().rss)

    def run_one(query, due):
        begun = time.perf_counter()
        predictor.predict_one(*query)
        finished = time.perf_counter()
        return 1000 * (finished - due), 1000 * (finished - begun), finished

    monitor = threading.Thread(target=sample_memory, daemon=True)
    monitor.start()
    wall_start = time.perf_counter()
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = []
        for i, query in enumerate(queries):
            due = wall_start + i / rps
            delay = due - time.perf_counter()
            if delay > 0:
                time.sleep(delay)
            futures.append(executor.submit(run_one, query, due))
        results = [future.result() for future in futures]
    wall_end = max(result[2] for result in results)
    stopped.set()
    monitor.join()
    elapsed = wall_end - wall_start
    response = np.array([result[0] for result in results])
    service = np.array([result[1] for result in results])
    before_precompute = time.perf_counter()
    precomputed = predictor.precompute()
    precompute_ms = 1000 * (time.perf_counter() - before_precompute)
    return {
        "requested_rps": rps, "workers": workers, "requests": requests,
        "machine_logical_cpus": os.cpu_count(),
        "process_affinity_cpus": len(process.cpu_affinity()),
        "achieved_rps": round(requests / elapsed, 1),
        "response_p50_ms": round(float(np.quantile(response, 0.50)), 3),
        "response_p95_ms": round(float(np.quantile(response, 0.95)), 3),
        "response_p99_ms": round(float(np.quantile(response, 0.99)), 3),
        "service_p95_ms": round(float(np.quantile(service, 0.95)), 3),
        "rss_before_load_mb": round(rss_before / 2**20, 1),
        "rss_loaded_mb": round(rss[0] / 2**20, 1),
        "rss_peak_mb": round(max(rss) / 2**20, 1),
        "model_load_ms": round(load_ms, 1),
        "precompute_rows": len(precomputed),
        "precompute_ms": round(precompute_ms, 1),
        "rss_after_precompute_mb": round(process.memory_info().rss / 2**20, 1),
        "batch_median_ms": batch_ms,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--models-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--requests", type=int, default=1000)
    parser.add_argument("--rps", type=int, default=200)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--cpu-limit", type=int,
                        help="Pin the benchmark process to this many logical CPUs")
    args = parser.parse_args()
    if args.cpu_limit:
        process = psutil.Process()
        process.cpu_affinity(process.cpu_affinity()[:args.cpu_limit])
    result = benchmark(args.models_dir, args.requests, args.rps, args.workers)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2))
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
