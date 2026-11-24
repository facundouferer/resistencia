"""Download raw OpenStreetMap data through the Overpass API.

The response is stored byte-for-byte, never modified, next to a provenance
file recording source, query, endpoint, timestamps and license.

Usage:
    python tools/osm_importer/fetch_osm.py QUERY_FILE OUTPUT_JSON

QUERY_FILE is an Overpass QL file requesting `[out:json]`.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import sys
import time
from pathlib import Path

import requests

ENDPOINTS = (
    "https://overpass-api.de/api/interpreter",
    "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
)
USER_AGENT = "resistencia-3d-pipeline/0.1"
LICENSE = "Open Database License (ODbL) 1.0"
ATTRIBUTION = "© OpenStreetMap contributors"


def fetch(query: str, attempts: int = 5, initial_wait: float = 30.0) -> tuple[bytes, str]:
    """Return (raw response bytes, endpoint) using exponential backoff."""
    wait = initial_wait
    last_error = "no attempt made"
    for attempt in range(1, attempts + 1):
        for endpoint in ENDPOINTS:
            try:
                response = requests.post(
                    endpoint, data={"data": query}, headers={"User-Agent": USER_AGENT}, timeout=180
                )
            except requests.RequestException as exc:
                last_error = f"{endpoint}: {exc}"
                print(f"attempt {attempt}: {last_error}", file=sys.stderr)
                continue
            if response.status_code == 200:
                json.loads(response.content)  # fail loudly on a non-JSON body
                return response.content, endpoint
            last_error = f"{endpoint}: HTTP {response.status_code}"
            print(f"attempt {attempt}: {last_error}", file=sys.stderr)
        if attempt < attempts:
            time.sleep(wait)
            wait *= 2
    raise RuntimeError(f"Overpass download failed after {attempts} attempts ({last_error})")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("query_file", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()

    query = args.query_file.read_text(encoding="utf-8")
    if args.output.exists():
        print(f"refusing to overwrite existing source data: {args.output}", file=sys.stderr)
        return 1

    raw, endpoint = fetch(query)
    data = json.loads(raw)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(raw)
    provenance = {
        "source": "openstreetmap",
        "license": LICENSE,
        "attribution": ATTRIBUTION,
        "endpoint": endpoint,
        "query": query,
        "downloaded_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "osm_base_timestamp": data.get("osm3s", {}).get("timestamp_osm_base"),
        "element_count": len(data.get("elements", [])),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "file": args.output.name,
    }
    provenance_path = args.output.with_suffix(".provenance.json")
    provenance_path.write_text(json.dumps(provenance, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"saved {args.output} ({provenance['element_count']} elements) and {provenance_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
