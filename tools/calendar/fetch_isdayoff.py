"""Save complete Russian isDayOff calendars as one CSV per year."""

import argparse
import csv
from datetime import date, timedelta
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import urlopen


def fetch(year: int) -> list[tuple[str, str]] | None:
    query = urlencode({"year": year, "cc": "ru", "pre": 1, "holiday": 1})
    try:
        with urlopen(f"https://isdayoff.ru/api/getdata?{query}", timeout=30) as response:
            codes = response.read().decode("ascii").strip()
    except HTTPError as error:
        if error.code == 404 and error.read().strip() == b"101":
            return None
        raise
    count = (date(year + 1, 1, 1) - date(year, 1, 1)).days
    if len(codes) != count or set(codes) - set("0128"):
        raise ValueError(f"Unexpected isDayOff response for {year}: {codes[:80]!r}")
    # Unsupported future years currently return HTTP 200 with one zero per day.
    if set(codes) == {"0"}:
        return None
    return [((date(year, 1, 1) + timedelta(days=i)).isoformat(), code)
            for i, code in enumerate(codes)]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("years", type=int, nargs="+")
    parser.add_argument("--output-dir", type=Path, action="append", required=True)
    args = parser.parse_args()
    for year in args.years:
        rows = fetch(year)
        if rows is None:
            print(f"{year}: unavailable (all working-day codes); using fallback")
            continue
        for directory in args.output_dir:
            directory.mkdir(parents=True, exist_ok=True)
            path = directory / f"{year}.csv"
            with path.open("w", newline="", encoding="utf-8") as target:
                writer = csv.writer(target)
                writer.writerow(("date", "day_type"))
                writer.writerows(rows)
            print(f"{year}: {len(rows)} days -> {path}")


if __name__ == "__main__":
    main()
