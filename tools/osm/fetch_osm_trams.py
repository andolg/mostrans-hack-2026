#!/usr/bin/env python3
"""Download Moscow tram route relations and all referenced OSM primitives."""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path


DEFAULT_ENDPOINT = "https://overpass-api.de/api/interpreter"
DEFAULT_BBOX = "55.48,37.29,55.98,37.96"


def build_query(bbox: str, route_refs: list[str]) -> str:
    ref_filter = ""
    if route_refs:
        escaped = "|".join(re.escape(ref) for ref in route_refs)
        ref_filter = f'[ref~"^({escaped})$"]'
    return f"""[out:json][timeout:180];
relation[type=route][route=tram]{ref_filter}({bbox});
out body;
>;
out body qt;
"""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--bbox", default=DEFAULT_BBOX, help="south,west,north,east")
    parser.add_argument("--route-refs", nargs="+", default=[], metavar="REF", help="Route numbers or refs separated by spaces")
    parser.add_argument("--route-ref", action="append", default=[], help="Single route ref (can be repeated)")
    parser.add_argument("--endpoint", default=DEFAULT_ENDPOINT)
    args = parser.parse_args()

    started = time.monotonic()

    def progress(message: str) -> None:
        print(f"[{time.monotonic() - started:.1f}s] {message}", flush=True)

    refs = args.route_refs + args.route_ref
    query = build_query(args.bbox, refs)
    request = urllib.request.Request(
        args.endpoint,
        data=urllib.parse.urlencode({"data": query}).encode("utf-8"),
        headers={"User-Agent": "mostrans-hack-2026/0.1 (offline data preparation)"},
        method="POST",
    )
    progress(f"Requesting {', '.join(refs) if refs else 'all tram routes'} from {args.endpoint}; waiting for Overpass...")
    try:
        with urllib.request.urlopen(request, timeout=240) as response:
            progress("Response received; downloading JSON...")
            data = bytearray()
            next_report = 256 * 1024
            while chunk := response.read(64 * 1024):
                data.extend(chunk)
                if len(data) >= next_report:
                    progress(f"Downloaded {len(data) // 1024} KiB")
                    next_report += 256 * 1024
            progress(f"Parsing {len(data) // 1024} KiB of JSON...")
            payload = json.loads(data)
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as error:
        print(f"OSM download failed: {error}", file=sys.stderr)
        return 1

    args.output.parent.mkdir(parents=True, exist_ok=True)
    progress(f"Writing {args.output}...")
    args.output.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    relations = sum(1 for item in payload.get("elements", []) if item.get("type") == "relation")
    progress(f"Saved {len(payload.get('elements', []))} OSM elements ({relations} relations) to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
