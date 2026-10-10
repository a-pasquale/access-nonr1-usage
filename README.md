# Beyond the R1s — ACCESS-CI usage by institution tier

A reproducible analysis of how non-R1 institutions use ACCESS-CI compute compared with R1s:
share of usage vs. share of awards, trend since ACCESS began (Sept 2022), four-quarter
retention, the award-to-first-job funnel, resource and allocation-tier mix, and HBCU / tribal
college participation. The output is a single static page (`docs/index.html`) whose every
number is computed by the scripts in `pipeline/` from the data in `data/raw/`.

**Live page:** https://a-pasquale.github.io/access-nonr1-usage/ (once Pages is enabled — see below)

## What the numbers say (snapshot 2022-09-01 → 2026-09-14)

| | Share of current projects | Share of awarded credits* | Share of ACEs consumed |
|---|---:|---:|---:|
| R1 | 83.9% | 86.5% | 93.2% |
| R2 | 5.3% | 5.2% | 2.9% |
| RCU | 3.5% | 2.2% | 1.0% |
| Other academic | 3.5% | 1.9% | 0.5% |
| Non-academic | 3.9% | 4.3% | 2.4% |

\* Rebuilt awards on projects begun 2025 or later (5,116 of 7,157 current projects); see Method.

Awards track research spending (HERD) once standalone health-science institutions are set aside: R1 92.5% of awards
for 93.2% of R1+R2+RCU spending, R2 5.2% for 4.8%, RCU 2.3% for 2.0%. Usage does not: R1s run 96%. Counting the
health-science schools, R2s look short (5.5% of awards for 7.9% of spending). Reach: 185 of 187 R1s have run a job on
ACCESS since 2022, against 102 of 139 R2s and 99 of 216 RCUs (84% and 62% of those tiers' research spending).

Within Explore, Discover and Accelerate, non-R1 academic PIs hold 9.6% of awards and run 9.6% of the usage. Per
awarded credit, non-R1 Explore projects use 0.71× what R1 ones do, Discover 1.12× and Accelerate 1.16×. Maximize and
legacy Research carry 72% of R1 usage.

At the PI level, 63% of R1 PIs and 64% of non-R1 academic PIs are still computing a year after their first ACCESS-era
job. New non-R1 PIs drop off sooner (66% active at 6–11 months against 73%), and new PIs at RCUs (51%) and
non-designated colleges (48%) continue less than at R1s (58%). New PIs who ever used Explore continue 52–54% of the
time at both. Four-quarter institution retention (R1 93%, non-R1 75%) is consistent with depth: the median R1 has 11
active PIs, the median RCU 2, and 80% of active non-designated colleges have one.

`data/derived/summary.txt` holds the current headline numbers; `make verify` recomputes and diffs them.

## Reproduce it

Two levels of reproduction, depending on how skeptical you are.

### 1. Recompute everything from the committed raw snapshot (no credentials, ~10 s)

```bash
git clone https://github.com/a-pasquale/access-nonr1-usage
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
make all             # fetch_reference → fetch_xdmod → classify → fetch_xdmod_cohorts → fetch_xdmod_pis → analyze → build_site
```

The XDMoD pulls are ~150 queries against the Jobs realm and take 30–40 minutes. To reproduce a
*dated* snapshot exactly rather than pulling through yesterday, pin the window:

```bash
python3 pipeline/fetch_xdmod.py --end 2026-09-14
```

XDMoD keeps ingesting late job records, so a pinned re-pull matches the committed raw CSVs closely but not to
the last digit; see Known limitations. The Allocations feed is a
live view of *current* projects and will differ by however many projects started or expired
since the snapshot; the Carnegie and IPEDS files are static releases.

## Pipeline

| Step | Script | Reads | Writes |
|---|---|---|---|
| 1 | `pipeline/fetch_reference.py` | Carnegie 2025 RAD xlsx, IPEDS HD2023 zip, ACCESS current-projects feed (358 pages), Allocations resource catalog | `data/raw/carnegie_2025_rad.xlsx`, `ipeds_hd2023.zip`, `all_projects.json`, `allocations_resources.json` |
| 2 | `pipeline/fetch_xdmod.py` | XDMoD Jobs realm, dimension `pi_institution` | `data/raw/xdmod_by_pi_institution.csv`, `xdmod_by_pi_institution_type.csv`, `xdmod_monthly_*.csv`, `xdmod_window.txt` |
| 3 | `pipeline/classify.py` | raw + `data/overrides.json` | `data/derived/institutions.csv`, `projects.csv`, `project_institutions.csv`, `cohorts.json`, `classify_report.txt` |
| 4 | `pipeline/fetch_xdmod_cohorts.py` | XDMoD, filtered to each cohort's institution list | `data/raw/xdmod_xtabs.csv`, `xdmod_quarterly_*.csv` |
| 4b | `pipeline/fetch_xdmod_pis.py` | XDMoD `pi` dimension: pre-ACCESS lookback (unfiltered), then monthly and by allocation type per tier | `data/raw/xdmod_pi_prior.csv`, `xdmod_pi_monthly.csv`, `xdmod_pi_board.csv` |
| 5 | `pipeline/analyze.py` | derived + raw monthly/xtabs, Carnegie xlsx, `xdmod_pi_*.csv` | `data/derived/report_data.json`, `summary.txt`, `unreached_institutions.csv` |
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
XDMoD labels are never fuzzy-matched automatically; the classifier writes fuzzy *suggestions* to
`classify_report.txt` for a human to promote into `overrides.json`. Every Carnegie R1 was checked
by hand against the XDMoD list; two R1s (The University of Tennessee Health Science Center, UMass Boston) have no ACCESS
usage under any name. On the Allocations-feed side,
project institutions with no exact match are fuzzy-matched to the Carnegie file at a score of 93 or above; this
applied to two institutions (Philadelphia College of Osteopathic Medicine, UT Permian Basin), marked `carnegie-fuzzy`
in `project_institutions.csv`.

**Awarded projects** are the current projects in the public Allocations feed. The feed's *ACCESS Credits* line is the
balance left after the PI exchanges credits for resource units, not the award, so `classify.py` rebuilds each award by
converting every exchanged resource back to credits with the `conversionFactor` values in the Allocations resource
catalog (`allocations_resources.json`; credits per unit = resource factor ÷ the ACCESS Credits factor). Old resource
names in the feed are mapped to current ones in `overrides.json` → `resource_aliases`. The catalog carries only today's
factors, which reproduce standard award sizes (200k/400k, 750k/1.5M, 1.5M/3M) for 96%/91%/84% of Explore/Discover/
Accelerate projects begun in 2026 but under 40% of those begun in 2023, because rates changed over time. Credit
comparisons therefore use only projects begun on or after `AWARD_SINCE` (2025-01-01) whose resources all have a
factor; projects on retired systems, CloudBank, MATCHPlus and a few new resources are excluded and listed in
`classify_report.txt`. "Never used" means
the awarded institution has no XDMoD job record at all in the window. The R1 never-used count is
mostly name variants between the two systems and should be read as noise.

**MSI flags** are IPEDS HD2023 `HBCU` and `TRIBAL` via UNITID. IPEDS has no HSI flag
(HSI status is enrollment-derived); adding it needs the EF2023A enrollment file.

**Research-spending benchmark.** Each tier's share of awards and usage is compared with its share of academic
R&D spending (HERD FY21–23 average, from the Carnegie 2025 file). This measures proportionality to research money,
not equity. It is also reported without standalone health-science institutions (the 2021 Carnegie special-focus
medical-school, research-institution and health-professions classes), whose large biomedical budgets carry little HPC
demand and which integrated R1s carry invisibly. Unreached R2s and RCUs are listed in `unreached_institutions.csv`. HERD exists only for designated institutions, so
the benchmark covers R1, R2 and RCU and normalizes every share to those three tiers. *Reach* is the number of distinct
Carnegie institutions in a tier with any XDMoD usage in the window.

**Allocation type.** Usage per awarded credit is compared between tiers within Explore, Discover and Accelerate,
using rebuilt awards. Maximize is excluded because it is a reviewed allocation, not a fixed credit size. Usage covers
the whole window while credits are current projects only, so only the within-type comparison between tiers is
meaningful, not the ratio itself.

**New vs. experienced PIs.** A PI is *experienced* if XDMoD has any usage under their name as PI from 2017-01-01 up to
the start of ACCESS (XSEDE era), otherwise *new*. A PI *continued* if they have usage 12 or more months after their
first month in the ACCESS window; only PIs whose first month is at least 12 months before the window end are counted.
A six-to-eleven-month version is reported for new PIs too. Allocation type for a PI is "ever used Explore" vs. never:
XDMoD does not record which allocation came first, and labelling by the type with the most usage would be circular
(PIs who stay tend to move up).
PIs are keyed by XDMoD's "name - institution" label, so a PI who moved institutions counts as new. PI labels are
replaced with a 12-character SHA-1 prefix before the raw files are written, so the repo carries no per-person names.

**Retention** counts an institution as active in a quarter if any job was charged, and asks whether
it was also active four quarters later. Partial quarters and partial program years are excluded
from the trend charts; program years run September–August.

## Known limitations

- Institution names are the join key everywhere; XDMoD, the Allocations feed, Carnegie and IPEDS
  each spell them differently. The overrides file is the audit trail for every judgment call.
- Usage is attributed to the PI's institution. A non-R1 collaborator on an R1 PI's project counts
  as R1 usage (and vice versa). XDMoD's `institution` dimension (user institution) would give the
  other view.
- XDMoD renames institutions over time ("University of Illinois at Urbana-Champaign" is now "University of Illinois
  Urbana-Champaign"). `fetch_xdmod_pis.py` maps the snapshot's labels to the current ones by normalized name and
  prints any it cannot match.
- The PI-level files were pulled on 2026-10-09 for the same pinned window. Their tier totals differ from the
  2026-09-14 institution pull by −1% to +9% by tier (about +2% overall), because XDMoD keeps ingesting late job records for past months. The PI analysis
  computes its shares and rates within the PI files alone, so the two pulls are never mixed in one figure.
- The XDMoD system label "CUNY - City University of New York" is mapped to the CUNY Graduate Center (R1), though it
  likely mixes campuses (about 4.5M ACEs). It is left as is and flagged here.
- The cohort cross-tabs (`xdmod_xtabs.csv`, `xdmod_quarterly_*`) and the PI-level files were pulled before the
  2026-10 override fixes (LSU Health New Orleans and Wake Forest School of Medicine moved from R1 to R2; six RCUs
  newly matched). Those raw files still group them the old way, a few million ACEs out of 13.8B. A fresh `make all`
  re-pulls with the corrected cohorts and will differ slightly from the committed snapshot.
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
