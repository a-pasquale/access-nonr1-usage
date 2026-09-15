# Beyond the R1s — ACCESS-CI usage by institution tier

A reproducible analysis of how non-R1 institutions use ACCESS-CI compute compared with R1s:
share of usage vs. share of awards, trend since ACCESS began (Sept 2022), four-quarter
retention, the award-to-first-job funnel, resource and allocation-tier mix, and HBCU / tribal
college participation. The output is a single static page (`docs/index.html`) whose every
number is computed by the scripts in `pipeline/` from the data in `data/raw/`.

**Live page:** https://apasquale.github.io/access-nonr1-usage/ (once Pages is enabled — see below)

## What the numbers say (snapshot 2022-09-01 → 2026-09-14)

| | Share of current projects | Share of awarded credits | Share of ACEs consumed |
|---|---:|---:|---:|
| R1 | 83.9% | 84.5% | 93.2% |
| R2 | 5.3% | 5.3% | 2.9% |
| RCU | 3.3% | 3.4% | 0.9% |
| Other academic | 3.7% | 2.8% | 0.5% |
| Non-academic | 3.9% | 4.1% | 2.4% |

Four-quarter institution retention: R1 ≈ 93%, non-R1 academic ≈ 75%. Of institutions holding a
current award, the share that has never run a job: R1 3%, R2 6%, RCU 20%, other academic 41%.
`data/derived/summary.txt` holds the current headline numbers; `make verify` recomputes and diffs them.

## Reproduce it

Two levels of reproduction, depending on how skeptical you are.

### 1. Recompute everything from the committed raw snapshot (no credentials, ~10 s)

```bash
git clone https://github.com/apasquale/access-nonr1-usage
cd access-nonr1-usage
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
make verify          # classify → analyze → build page, then diff summary.txt against the committed one
make serve           # open http://localhost:8000
```

This re-derives every figure on the page from `data/raw/` and confirms the committed
`summary.txt` is what the code actually produces. Review `data/overrides.json` (the only
hand-authored input) and `data/derived/classify_report.txt` (what matched how, and the
fuzzy suggestions that were *not* applied automatically).

### 2. Re-pull the source data yourself (needs an XDMoD API token, ~30 min)

1. Get a token: sign in at https://xdmod.access-ci.org → My Profile → API Token.
2. Put it in the environment, a `.env` file at the repo root (`XDMOD_API_TOKEN=...`), or `~/xdmod-api.key`.
3. Run:

```bash
make all             # fetch_reference → fetch_xdmod → classify → fetch_xdmod_cohorts → analyze → build_site
```

The XDMoD pulls are ~130 queries against the Jobs realm and take 20–30 minutes. To reproduce a
*dated* snapshot exactly rather than pulling through yesterday, pin the window:

```bash
python3 pipeline/fetch_xdmod.py --end 2026-09-14
```

XDMoD data is append-only, so a pinned re-pull should match the committed raw CSVs to the last
digit (ACEs are floats; expect identical values, not just close ones). The Allocations feed is a
live view of *current* projects and will differ by however many projects started or expired
since the snapshot; the Carnegie and IPEDS files are static releases.

## Pipeline

| Step | Script | Reads | Writes |
|---|---|---|---|
| 1 | `pipeline/fetch_reference.py` | Carnegie 2025 RAD xlsx, IPEDS HD2023 zip, ACCESS current-projects feed (358 pages) | `data/raw/carnegie_2025_rad.xlsx`, `ipeds_hd2023.zip`, `all_projects.json` |
| 2 | `pipeline/fetch_xdmod.py` | XDMoD Jobs realm, dimension `pi_institution` | `data/raw/xdmod_by_pi_institution.csv`, `xdmod_monthly_*.csv` |
| 3 | `pipeline/classify.py` | raw + `data/overrides.json` | `data/derived/institutions.csv`, `projects.csv`, `project_institutions.csv`, `cohorts.json`, `classify_report.txt` |
| 4 | `pipeline/fetch_xdmod_cohorts.py` | XDMoD, filtered to each cohort's institution list | `data/raw/xdmod_xtabs.csv`, `xdmod_quarterly_*.csv` |
| 5 | `pipeline/analyze.py` | derived + raw monthly/xtabs | `data/derived/report_data.json`, `summary.txt` |
| 6 | `pipeline/build_site.py` | `report_data.json` + `site/*.html` | `docs/index.html` (+ copies of the derived CSVs) |

`make rebuild` runs steps 3, 5 and 6 only.

## Method

**Usage** is ACCESS Credit Equivalents (ACEs) charged, from the XDMoD Jobs realm grouped by PI
institution — the institution of the project's PI, not of the individual user. ACEs normalize
across CPU, GPU and node-allocated resources (1 ACE = 1 CPU-hour on SDSC Expanse).

**Tiers** are the Carnegie 2025 Research Activity Designations: Research 1, Research 2, and
Research Colleges & Universities (RCU). Institutions not in that file are "Other academic" if they
look like a college or university, otherwise "Non-academic" (national labs, industry, hospitals,
government, nonprofits). Organizational units of R1s — supercomputer centers, medical schools,
observatories — are folded into R1. "Non-R1 academic" = R2 + RCU + Other academic; non-academic
PIs are reported but excluded from that cohort.

**Matching** is exact on a normalized name (lowercased, punctuation and "the/at/campus" removed),
with hand-written overrides in `data/overrides.json` for campus-system naming
("University of Michigan" → Ann Arbor, "TAMU" → College Station, SUNY campuses, etc.).
Nothing is fuzzy-matched automatically; the classifier writes fuzzy *suggestions* to
`classify_report.txt` for a human to promote into `overrides.json`. Every Carnegie R1 was checked
by hand against the XDMoD list; two R1s (UT Health Science Center, UMass Boston) have no ACCESS
usage under any name.

**Awarded projects** are the current projects in the public Allocations feed. "Never used" means
the awarded institution has no XDMoD job record at all in the window. The R1 never-used count is
mostly name variants between the two systems and should be read as noise.

**MSI flags** are IPEDS HD2023 `HBCU` and `TRIBAL` via UNITID. IPEDS has no HSI flag
(HSI status is enrollment-derived); adding it needs the EF2023A enrollment file.

**Retention** counts an institution as active in a quarter if any job was charged, and asks whether
it was also active four quarters later. Partial quarters and partial program years are excluded
from the trend charts; program years run September–August.

## Known limitations

- Institution names are the join key everywhere; XDMoD, the Allocations feed, Carnegie and IPEDS
  each spell them differently. The overrides file is the audit trail for every judgment call.
- Usage is attributed to the PI's institution. A non-R1 collaborator on an R1 PI's project counts
  as R1 usage (and vice versa). XDMoD's `institution` dimension (user institution) would give the
  other view.
- The Allocations feed only shows *current* projects, so the funnel compares current awards with
  all-time usage. A project-level join (allocation charge number ↔ XDMoD `allocation` dimension)
  would be tighter and is the natural next step.

## Hosting on GitHub Pages

The built page lives in `docs/`. In the repository settings → Pages, set **Source: Deploy from a
branch**, **Branch: main, folder: /docs**. Every push that changes `docs/index.html` redeploys.
`docs/.nojekyll` is present so nothing gets processed.

## Sources

- XDMoD for ACCESS: https://xdmod.access-ci.org (Jobs realm; API via the `xdmod-data` Python package)
- ACCESS Allocations current projects: https://allocations.access-ci.org/current-projects.json
- Carnegie Classification 2025 Research Activity Designations: https://carnegieclassifications.acenet.edu/ (public data file, v1.1, Feb 2025)
- IPEDS Institutional Characteristics HD2023: https://nces.ed.gov/ipeds/datacenter/
