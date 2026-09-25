"""Aggregate raw validation events into a complete route/date/hour panel."""

import argparse
from pathlib import Path

import pandas as pd


def prepare(inputs: list[Path], output: Path, start: str, end: str,
            routes: list[int], chunksize: int = 500_000) -> pd.DataFrame:
    counts = None
    valid_routes = set(routes)
    for path in inputs:
        for chunk in pd.read_csv(
            path, sep=";", usecols=["tran_date_time", "validation_result", "ngpt_route"],
            dtype=str, chunksize=chunksize,
        ):
            chunk = chunk.loc[chunk["validation_result"].eq("1")].copy()
            chunk["date"] = chunk["tran_date_time"].str[:10]
            chunk = chunk.loc[chunk["date"].between(start, end)]
            chunk["route"] = pd.to_numeric(
                chunk["ngpt_route"].str.extract(r"^(\d+)\s+трамвай", expand=False),
                errors="coerce",
            )
            chunk = chunk.loc[chunk["route"].isin(valid_routes)].copy()
            chunk["hour"] = pd.to_numeric(chunk["tran_date_time"].str[11:13], errors="coerce")
            chunk = chunk.loc[chunk["hour"].between(0, 23)]
            part = chunk.groupby(["route", "date", "hour"]).size()
            counts = part if counts is None else counts.add(part, fill_value=0)

    index = pd.MultiIndex.from_product(
        [routes, pd.date_range(start, end).strftime("%Y-%m-%d"), range(24)],
        names=["route", "date", "hour"],
    )
    if counts is None:
        counts = pd.Series(dtype="int64")
    panel = counts.reindex(index, fill_value=0).fillna(0).astype("int64")
    result = panel.rename("boardings").reset_index()
    output.parent.mkdir(parents=True, exist_ok=True)
    result.to_csv(output, sep=";", index=False)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, action="append", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--start", required=True, help="Inclusive YYYY-MM-DD")
    parser.add_argument("--end", required=True, help="Inclusive YYYY-MM-DD")
    parser.add_argument("--routes", nargs="+", type=int,
                        default=[1, 5, 7, 11, 12, 17, 25, 26, 28, 50])
    parser.add_argument("--chunksize", type=int, default=500_000)
    args = parser.parse_args()
    panel = prepare(args.input, args.output, args.start, args.end,
                    args.routes, args.chunksize)
    print(f"{len(panel):,} hours, {panel.boardings.sum():,} boardings -> {args.output}")


if __name__ == "__main__":
    main()
