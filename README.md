# Beyond the R1s — ACCESS-CI usage by institution tier

A reproducible analysis of how non-R1 institutions use ACCESS-CI computing compared with R1s,
stage by stage: awards against research spending, reach, how fully awards are used (by PI
experience and allocation type), scale and campus depth, plus trend, computing profile and
HBCU / tribal college participation. The output is a single static page (`docs/index.html`) whose every
number is computed by the scripts in `pipeline/` from the data in `data/raw/`.

**Live page:** https://a-pasquale.github.io/access-nonr1-usage/ (once Pages is enabled — see below)

## What the numbers say (snapshot 2022-09-01 → 2026-09-14)

Usage is batch HPC (XDMoD Jobs realm) plus Jetstream2 cloud (Cloud realm), in ACCESS Credits.

| | Share of current projects | Share of awarded credits* | Share of usage |
|---|---:|---:|---:|
| R1 | 83.9% | 86.5% | 91.9% |
| R2 | 5.3% | 5.2% | 2.9% |
| RCU | 3.5% | 2.2% | 1.2% |
| Other academic | 3.5% | 1.9% | 0.6% |
| Non-academic | 3.9% | 4.3% | 3.1% |

\* Rebuilt awards on projects begun 2025 or later (5,116 of 7,157 current projects); see Method.

Among research institutions, research spending explains about half of the R1/non-R1 difference. Most of the rest
is Maximize-scale computing, where non-R1 institutions are far below their research share. Reach and campus depth
are the other clear gaps.

- **Awards against research spending** (HERD, R1+R2+RCU, standalone health-science institutions excluded): R2s and
  RCUs hold 9.1% of current projects, 6.8% of research spending and 4.0% of usage; spending accounts for about 45% of
  the drop from project share to usage share. On Explore/Discover/Accelerate projects begun since 2025 they hold 7.1%
  of awards, close to their research share. On Maximize they hold 4.7% of current projects (10 of 215), and non-R1
  academic PIs run 1.7% of Maximize batch HPC usage. Award amounts for older multi-year Maximize projects cannot be
  compared fairly (they accumulate several years of resource lines), so the Maximize comparison uses counts and usage.
- **Reach**: 186 of 187 R1s have used ACCESS since 2022, against 107 of 139 R2s and 105 of 216 RCUs (90% and 64% of
  those tiers' research spending). Outside medical schools, 27 R2s and 92 RCUs have no usage.
- **Use of awards** (projects begun in the last 12 months, batch HPC plus cloud over credits available for them): the
  median non-R1 project is at 0.18× against 0.38× for R1 (gap 95% interval 0.07–0.29). The components are less
  certain: 19% vs 15% have no usage yet (difference interval −1 to 8 points), and among started projects 0.39× vs
  0.56× (interval −0.03 to 0.29). Standardizing to R1's mix of PI experience and allocation type explains about a
  third of the median gap; the rest is uncertain. Counting batch HPC alone the medians would be 0.01× and 0.24×;
  among projects with no Jetstream2 award they are 0.07× and 0.34×.
- **Scale**: Maximize and legacy Research carry 72% of R1 batch HPC usage. Within Explore/Discover/Accelerate,
  non-R1 PIs run 9.6% of R1 + non-R1 batch HPC usage (9.1% since 2025), in line with their 9.6% of those awards.
- **Depth**: 63% of R1 PIs and 64% of non-R1 academic PIs are still computing a year after their first ACCESS-era
  job, but institution retention is 93% against 75%. The median R1 has 11 active batch HPC PIs, the median RCU 2, and
  80% of active non-designated colleges have one.
- **Cloud**: Jetstream2 is 11% of all usage, 26% of RCU usage and 32% of non-designated colleges' usage, against 9%
  of R1 usage.

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
make all             # fetch_reference → fetch_xdmod → fetch_xdmod_cloud → classify → fetch_xdmod_cohorts → fetch_xdmod_pis → fetch_xdmod_allocations → analyze → build_site
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
| 2b | `pipeline/fetch_xdmod_cloud.py` | XDMoD Cloud realm, `cloud_core_time` by PI institution and (monthly, from `AWARD_SINCE`) by allocation, per Jetstream2 resource | `data/raw/xdmod_cloud_by_pi_institution.csv`, `xdmod_cloud_allocation_monthly.csv` |
| 3 | `pipeline/classify.py` | raw + `data/overrides.json` | `data/derived/institutions.csv`, `projects.csv`, `project_institutions.csv`, `cohorts.json`, `classify_report.txt` |
| 4 | `pipeline/fetch_xdmod_cohorts.py` | XDMoD, filtered to each cohort's institution list | `data/raw/xdmod_xtabs.csv`, `xdmod_quarterly_*.csv` |
| 4b | `pipeline/fetch_xdmod_pis.py` | XDMoD `pi` dimension: pre-ACCESS lookback (unfiltered), then monthly and by allocation type per tier | `data/raw/xdmod_pi_prior.csv`, `xdmod_pi_monthly.csv`, `xdmod_pi_board.csv` |
| 4c | `pipeline/fetch_xdmod_allocations.py` | XDMoD `allocation` dimension, monthly, from `AWARD_SINCE`, split by quarter (pulled 2026-10-10) | `data/raw/xdmod_allocation_monthly.csv` |
| 5 | `pipeline/analyze.py` | derived + raw monthly/xtabs, Carnegie xlsx, `xdmod_pi_*.csv`, `xdmod_allocation_monthly.csv`, `xdmod_cloud_allocation_monthly.csv` | `data/derived/report_data.json`, `summary.txt`, `unreached_institutions.csv` |
| 6 | `pipeline/build_site.py` | `report_data.json` + `site/*.html` | `docs/index.html` (+ copies of the derived CSVs) |

`make rebuild` runs steps 3, 5 and 6 only.

## Method

**Usage** is batch HPC plus cloud, grouped by PI institution (the institution of the project's PI, not of the
individual user). Batch HPC is ACCESS Credit Equivalents (ACEs) charged in the XDMoD Jobs realm; ACEs normalize across
CPU, GPU and node-allocated resources (1 ACE = 1 CPU-hour on SDSC Expanse). Cloud is Jetstream2 core-hours from the
XDMoD Cloud realm, converted to SUs at Jetstream2's documented rates (1 SU per vCPU-hour for CPU, 2 for large-memory
and for the g3 GPU flavors, the only GPU flavors XDMoD shows) and to credits at one credit per SU, the Allocations
catalog rate (`overrides.json` → `cloud_su_per_core_hour`). Institutions with only cloud usage are classified like
any other. This pipeline pulls monthly series, resource and allocation-type cross-tabs and PI-level data from the Jobs realm only,
so trends, retention, those breakdowns and PI-level figures are batch HPC only.

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
by hand against the XDMoD list; one R1 (The University of Tennessee Health Science Center) has no ACCESS usage under any name; UMass Boston has
Jetstream2 usage only. On the Allocations-feed side,
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
the awarded institution has no XDMoD job or cloud record at all in the window. The R1 never-used count is
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

**Utilization per allocation.** Each current project begun in the 12 months before the window end, with at least 3
months elapsed, is joined to its own XDMoD usage by charge number (`requestNumber` = XDMoD `allocation`). Earlier starts
are excluded because the feed lists only current projects: 12-month projects from early 2025 have expired, so those
still listed are extended survivors. Utilization is batch HPC plus cloud usage since the project began divided by the
credits it could have used (credits exchanged into Jobs-realm resources, `overrides.json` → `jobs_realm_resources`,
or into Jetstream2, `cloud_resources`, capped at the award, plus credits not yet exchanged), prorated over a fixed
12-month term. A batch-HPC-only version is reported as a sensitivity check. Exchanged credits alone would
be close to circular, since PIs exchange on demand. Projects that put every credit into unmeasured resources are counted separately. A PI is *experienced* if their "last, first" name (suffixes dropped) had any usage as PI in XDMoD before the
project began: pre-ACCESS from `xdmod_pi_prior.csv`, ACCESS-era from `xdmod_pi_monthly.csv`. Medians lead; non-R1 is
standardized to R1's mix of experience × type (Explore vs. Discover/Accelerate, weighted by R1 project counts) as a
weighted mean of within-cell medians, with 95% intervals from 2,000 bootstrap resamples. Maximize is excluded because
it is a reviewed allocation, not a fixed credit size.

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
- The PI-level files were pulled on 2026-10-10 for the same pinned window. Their tier totals differ from the
  2026-09-14 institution pull by +1.5% to +3.5% by tier (about +2% overall), because XDMoD keeps ingesting late job records for past months. The PI analysis
  computes its shares and rates within the PI files alone, so the two pulls are never mixed in one figure.
- The XDMoD system label "CUNY - City University of New York" is mapped to the CUNY Graduate Center (R1), though it
  likely mixes campuses (about 4.5M ACEs). It is left as is and flagged here.
- Usage covers batch HPC and Jetstream2. Credits exchanged for storage, OSG, TAMU Launch, CloudBank and similar
  resources produce no measured usage. Trends, retention and PI-level figures cover batch HPC only, and non-R1
  institutions lean on cloud more, so those figures understate non-R1 activity.
- The cohort cross-tabs (`xdmod_xtabs.csv`, `xdmod_quarterly_*`) predate the override fixes; the PI-level files were
  re-pulled with the corrected cohorts on 2026-10-10.
- The Allocations feed only shows *current* projects. Projects that close early or expire leave it, which is why the
  per-allocation utilization test is limited to projects begun in the last 12 months, and why tier-level award shares
  compare current awards with usage over the whole window.

## Hosting on GitHub Pages

The built page lives in `docs/`. In the repository settings → Pages, set **Source: Deploy from a
branch**, **Branch: main, folder: /docs**. Every push that changes `docs/index.html` redeploys.
`docs/.nojekyll` is present so nothing gets processed.

## Sources

- XDMoD for ACCESS: https://xdmod.access-ci.org (Jobs and Cloud realms; API via the `xdmod-data` Python package)
- Jetstream2 SU rates: https://docs.jetstream-cloud.org/general/instance-flavors/
- ACCESS Allocations current projects: https://allocations.access-ci.org/current-projects.json
- Carnegie Classification 2025 Research Activity Designations: https://carnegieclassifications.acenet.edu/ (public data file, v1.1, Feb 2025)
- IPEDS Institutional Characteristics HD2023: https://nces.ed.gov/ipeds/datacenter/
