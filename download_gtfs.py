"""Download GO Transit's latest static GTFS schedule into data/.

The schedule only covers about six weeks and GO republishes it often, so it is
downloaded again before each load instead of being kept by hand.

Usage:  python download_gtfs.py
"""

import io
import os
import zipfile
from urllib.request import urlopen

GTFS_URL = "https://assets.metrolinx.com/raw/upload/Documents/Metrolinx/Open%20Data/GO-GTFS.zip"
NEEDED_FILES = [
    "stops.txt",
    "routes.txt",
    "trips.txt",
    "stop_times.txt",
    "calendar_dates.txt",
    "shapes.txt",
]


def download_zip(url):
    """Download the GTFS zip file and return it as an open ZipFile."""
    with urlopen(url, timeout=120) as response:
        return zipfile.ZipFile(io.BytesIO(response.read()))


def extract_needed_files(gtfs_zip, folder):
    """Save only the GTFS files the loaders use into the given folder."""
    os.makedirs(folder, exist_ok=True)
    for file_name in NEEDED_FILES:
        with gtfs_zip.open(file_name) as source:
            with open(os.path.join(folder, file_name), "wb") as target:
                target.write(source.read())
        print("Saved", file_name)


if __name__ == "__main__":
    extract_needed_files(download_zip(GTFS_URL), "data")
