"""Download hourly Moscow weather history from the Open-Meteo archive API."""

import argparse
import json
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen

import pandas as pd

URL = "https://archive-api.open-meteo.com/v1/archive"
VARIABLES = [
    "temperature_2m", "apparent_temperature", "precipitation", "rain", "snowfall",
    "snow_depth", "weather_code", "cloud_cover", "wind_speed_10m", "wind_gusts_10m",
]


def fetch_year(start: str, end: str, latitude: float, longitude: float) -> pd.DataFrame:
    query = urlencode({
        "latitude": latitude, "longitude": longitude, "start_date": start, "end_date": end,
        "hourly": ",".join(VARIABLES), "timezone": "Europe/Moscow",
    })
    with urlopen(f"{URL}?{query}", timeout=120) as response:
        hourly = json.load(response)["hourly"]
    frame = pd.DataFrame(hourly)
    time = pd.to_datetime(frame.pop("time"))
    frame.insert(0, "hour", time.dt.hour)
    frame.insert(0, "date", time.dt.strftime("%Y-%m-%d"))
    return frame


def fetch(start: str, end: str, latitude: float, longitude: float) -> pd.DataFrame:
    parts = []
    for year in range(int(start[:4]), int(end[:4]) + 1):
        parts.append(fetch_year(max(start, f"{year}-01-01"), min(end, f"{year}-12-31"),
                                latitude, longitude))
    return pd.concat(parts, ignore_index=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start", required=True, help="YYYY-MM-DD, inclusive")
    parser.add_argument("--end", required=True, help="YYYY-MM-DD, inclusive")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--latitude", type=float, default=55.7558)
    parser.add_argument("--longitude", type=float, default=37.6173)
    args = parser.parse_args()
    weather = fetch(args.start, args.end, args.latitude, args.longitude)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    weather.to_csv(args.output, sep=";", index=False)
    print(f"{len(weather)} rows, {weather.isna().sum().sum()} missing values -> {args.output}")
