#!/usr/bin/env python3
"""Step 6 - render the report page from data/derived/report_data.json.

  docs/index.html       full standalone HTML document for GitHub Pages
  docs/report_data.json a copy of the data the page embeds, for anyone who wants to check the numbers
  data/derived/artifact.html  the same page without the document skeleton (for publishing as a Claude artifact)

The page is static: all data is embedded at build time, no runtime fetches.
Only Google Fonts is loaded externally, with system-font fallbacks.
"""
import argparse, datetime as dt, json, shutil
from config import DERIVED, DOCS, SITE

DEFAULT_REPO = "https://github.com/apasquale/access-nonr1-usage"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo-url", default=DEFAULT_REPO, help="link shown in the masthead")
    a = ap.parse_args()
    data = json.load(open(DERIVED / "report_data.json"))
    head = (SITE / "head.html").read_text()
    body = (SITE / "body.html").read_text().replace("__REPO_URL__", a.repo_url)
    scripts = (SITE / "scripts.html").read_text()
    scripts = scripts.replace("__DATA__", json.dumps(data, separators=(",", ":")))
    scripts = scripts.replace("__BUILT__", json.dumps(dt.date.today().isoformat()))
    inner = head + body + scripts
    (DERIVED / "artifact.html").write_text(inner)
    full = ('<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
            '<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">\n'
            '<meta name="description" content="How non-R1 institutions use ACCESS-CI compute versus R1s: share, trend, retention, the award-to-usage funnel and MSI participation. Reproducible from public data plus an XDMoD API token.">\n'
            + head + '</head>\n<body>\n' + body + scripts + '\n</body>\n</html>\n')
    DOCS.mkdir(exist_ok=True)
    (DOCS / "index.html").write_text(full)
    (DOCS / ".nojekyll").write_text("")
    shutil.copy(DERIVED / "report_data.json", DOCS / "report_data.json")
    for f in ("institutions.csv", "projects.csv", "project_institutions.csv", "summary.txt"):
        shutil.copy(DERIVED / f, DOCS / f)
    print("wrote", DOCS / "index.html", f"{(DOCS / 'index.html').stat().st_size:,} bytes")


if __name__ == "__main__":
    main()
