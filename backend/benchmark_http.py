"""Measure cached hourly API responses at a fixed arrival rate."""

import argparse
import random
import time
from concurrent.futures import ThreadPoolExecutor

import httpx
import numpy as np


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://localhost:8000")
    parser.add_argument("--requests", type=int, default=1200)
    parser.add_argument("--rps", type=int, default=200)
    parser.add_argument("--workers", type=int, default=16)
    args = parser.parse_args()

    routes = [1, 5, 7, 11, 12, 17, 25, 26, 28, 50]
    days = ["2025-04-14", "2025-10-31", "2025-11-03", "2026-03-16", "2026-10-01"]
    rng = random.Random(42)
    queries = []
    for _ in range(args.requests):
        route, day, hour = rng.choice(routes), rng.choice(days), rng.randrange(23)
        queries.append({
            "from": f"{day}T{hour:02d}:00", "to": f"{day}T{hour + 1:02d}:00", "route": route,
        })

    with httpx.Client(base_url=args.url, timeout=10, trust_env=False,
                      limits=httpx.Limits(max_connections=args.workers)) as client:
        client.get("/health").raise_for_status()

        def request(params, due):
            response = client.get("/api/boardings", params=params)
            response.raise_for_status()
            return time.perf_counter() - due

        started = time.perf_counter()
        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            futures = []
            for i, params in enumerate(queries):
                due = started + i / args.rps
                delay = due - time.perf_counter()
                if delay > 0:
                    time.sleep(delay)
                futures.append(pool.submit(request, params, due))
            latencies = np.array([future.result() for future in futures]) * 1000
        elapsed = time.perf_counter() - started

    print(f"requests={args.requests} rps={args.requests / elapsed:.1f} "
          f"p50={np.median(latencies):.1f}ms p95={np.quantile(latencies, 0.95):.1f}ms "
          f"p99={np.quantile(latencies, 0.99):.1f}ms")


if __name__ == "__main__":
    main()
