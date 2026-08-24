"""Download today's Home Office register of licensed sponsors.

The CSV lives on GOV.UK at a URL that changes every business day (it embeds the
date and a content hash), so we can't hard-code it. Instead we fetch the
publication page and pull the current CSV asset URL out of its HTML.

Usage:
    python scripts/download_register.py
"""

import re
import sys
from pathlib import Path

import requests

PUBLICATION_URL = (
    "https://www.gov.uk/government/publications/"
    "register-of-licensed-sponsors-workers"
)
# GOV.UK serves attachments from this asset host.
CSV_URL_PATTERN = re.compile(
    r"https://assets\.publishing\.service\.gov\.uk/media/[^\"'\s]+\.csv"
)
OUTPUT_PATH = Path(__file__).resolve().parent.parent / "data" / "sponsors.csv"


def find_csv_url() -> str:
    """Scrape the publication page for the current CSV attachment URL."""
    resp = requests.get(PUBLICATION_URL, timeout=30)
    resp.raise_for_status()
    matches = CSV_URL_PATTERN.findall(resp.text)
    if not matches:
        raise RuntimeError(
            "Could not find a CSV link on the publication page — "
            "GOV.UK may have changed its markup."
        )
    # If several are present, the Worker register is the one we want.
    for url in matches:
        if "Worker" in url:
            return url
    return matches[0]


def download(url: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    resp = requests.get(url, timeout=120)
    resp.raise_for_status()
    dest.write_bytes(resp.content)


def main() -> int:
    try:
        url = find_csv_url()
        print(f"Found register: {url}")
        download(url, OUTPUT_PATH)
        size_mb = OUTPUT_PATH.stat().st_size / 1_000_000
        print(f"Saved {size_mb:.1f} MB -> {OUTPUT_PATH}")
        return 0
    except Exception as exc:  # noqa: BLE001 — top-level script, report and exit
        print(f"Download failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
