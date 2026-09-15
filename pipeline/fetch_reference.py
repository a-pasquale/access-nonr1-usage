#!/usr/bin/env python3
"""Step 1 - fetch the public reference datasets.

  data/raw/carnegie_2025_rad.xlsx   Carnegie 2025 Research Activity Designations
  data/raw/ipeds_hd2023.zip         IPEDS institutional characteristics (HBCU / tribal flags)
  data/raw/all_projects.json        every current ACCESS project (paged public feed)

No credentials needed. Re-running overwrites the snapshot; pass --keep to skip
files that already exist.
"""
import argparse, json, sys, time, urllib.request
from config import RAW, CARNEGIE_URL, IPEDS_URL, ALLOCATIONS_FEED

UA = {"User-Agent": "access-nonr1-usage/1.0 (reproducibility pipeline)"}


def download(url, dest):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=120) as r, open(dest, "wb") as f:
        f.write(r.read())
    print(f"  {dest.name}: {dest.stat().st_size:,} bytes")


def get_json(url):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)


def fetch_projects(dest):
    """The feed is paged, 20 projects per page, 1-indexed `page` parameter."""
    first = get_json(ALLOCATIONS_FEED)
    pages = first["pages"]
    print(f"  projects feed: {pages} pages")
    projects = {p["projectId"]: p for p in first["projects"]}
    for i in range(2, pages + 1):
        for attempt in range(3):
            try:
                d = get_json(f"{ALLOCATIONS_FEED}?page={i}")
                break
            except Exception as e:  # noqa: BLE001
                print(f"  retry page {i}: {e}", file=sys.stderr)
                time.sleep(2)
        else:
            raise SystemExit(f"page {i} failed three times")
        for p in d["projects"]:
            p.pop("abstract", None)      # keep the snapshot small; not used
            p.pop("publications", None)
            projects[p["projectId"]] = p
        if i % 50 == 0:
            print(f"  page {i}/{pages} ({len(projects)} projects)")
    json.dump(list(projects.values()), open(dest, "w"))
    print(f"  {dest.name}: {len(projects)} projects")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--keep", action="store_true", help="skip files that already exist")
    a = ap.parse_args()
    jobs = [
        (RAW / "carnegie_2025_rad.xlsx", lambda d: download(CARNEGIE_URL, d)),
        (RAW / "ipeds_hd2023.zip", lambda d: download(IPEDS_URL, d)),
        (RAW / "all_projects.json", fetch_projects),
    ]
    for dest, fn in jobs:
        if a.keep and dest.exists():
            print(f"  keep {dest.name}")
            continue
        print(f"fetching {dest.name}")
        fn(dest)


if __name__ == "__main__":
    main()
