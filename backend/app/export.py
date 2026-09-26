import csv
from io import StringIO


COLUMNS = ("route", "start", "end", "boardings", "source", "forecast_version", "historical_end")


def csv_chunks(points):
    buffer = StringIO(newline="")
    writer = csv.writer(buffer, delimiter=";", lineterminator="\n")
    writer.writerow(COLUMNS)
    yield buffer.getvalue()
    buffer.seek(0)
    buffer.truncate(0)

    for index, point in enumerate(points, start=1):
        writer.writerow([point[column] if point[column] is not None else "" for column in COLUMNS])
        if index % 1000 == 0:
            yield buffer.getvalue()
            buffer.seek(0)
            buffer.truncate(0)

    if buffer.tell():
        yield buffer.getvalue()
