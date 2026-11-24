"""Download raw Overture Maps building footprints for a bounding box.

Uses the official `overturemaps` CLI with a pinned release, stores the
GeoJSON unmodified and writes a provenance file next to it.

Usage:
    python tools/overture_importer/fetch_overture.py --bbox=W,S,E,N RELEASE OUTPUT_GEOJSON
"""

from __future__ import annotations

import argparse
import collections
import datetime as dt
import hashlib
import json
import subprocess
import sys
from pathlib import Path

CLI = Path(sys.executable).with_name("overturemaps")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("release", help="Overture release, e.g. 2026-11-18.0")
    parser.add_argument("--bbox", required=True, help="west,south,east,north in WGS 84 degrees")
    parser.add_argument("output", type=Path)
    args = parser.parse_args()

    if args.output.exists():
        print(f"refusing to overwrite existing source data: {args.output}", file=sys.stderr)
        return 1
    args.output.parent.mkdir(parents=True, exist_ok=True)
    command = [str(CLI), "download", f"--bbox={args.bbox}", "-f", "geojson", "-t", "building",
               "-r", args.release, "-o", str(args.output)]
    subprocess.run(command, check=True)
    args.output.with_name(args.output.name + ".state").unlink(missing_ok=True)  # CLI cache, not data

    raw = args.output.read_bytes()
    features = json.loads(raw)["features"]
    datasets = collections.Counter(
        source.get("dataset") for f in features for source in f["properties"].get("sources") or []
    )
    licenses = sorted({source.get("license") for f in features for source in f["properties"].get("sources") or []})
    provenance = {
        "source": "overture_maps",
        "theme": "buildings",
        "type": "building",
        "release": args.release,
        "bbox_wsen": [float(v) for v in args.bbox.split(",")],
        "licenses": licenses,
        "attribution": "© OpenStreetMap contributors, Overture Maps Foundation; "
                       "includes Google Open Buildings and Microsoft ML Building Footprints",
        "datasets": dict(datasets),
        "feature_count": len(features),
        "downloaded_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "file": args.output.name,
    }
    provenance_path = args.output.with_name(args.output.name.removesuffix(".geojson") + ".provenance.json")
    provenance_path.write_text(json.dumps(provenance, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"saved {args.output} ({len(features)} features) and {provenance_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
