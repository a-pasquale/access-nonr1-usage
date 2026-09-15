"""Shared configuration for the ACCESS non-R1 usage pipeline."""
from pathlib import Path
import datetime as dt

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
DERIVED = ROOT / "data" / "derived"
SITE = ROOT / "site"
DOCS = ROOT / "docs"

XDMOD_URL = "https://xdmod.access-ci.org"
ALLOCATIONS_FEED = "https://allocations.access-ci.org/current-projects.json"
CARNEGIE_URL = "https://carnegieclassifications.acenet.edu/wp-content/uploads/2025/02/2025-RAD-Public-Data-File.xlsx"
IPEDS_URL = "https://nces.ed.gov/ipeds/datacenter/data/HD2023.zip"

# Analysis window: ACCESS program start through yesterday (XDMoD lags ~1 day).
START = "2022-09-01"
END = (dt.date.today() - dt.timedelta(days=1)).isoformat()

# Cohorts. "Non-R1 academic" is the union of R2, RCU and Other academic.
ORDER = ["R1", "R2", "RCU", "Other academic", "Non-academic", "Foreign/Unknown"]
NONR1 = ["R2", "RCU", "Other academic"]

METRICS = ["total_ace", "total_cpu_hours", "total_node_hours", "job_count",
           "active_pi_count", "active_allocation_count", "active_person_count"]
MONTHLY_METRICS = ["total_ace", "job_count", "active_person_count", "active_pi_count"]
XTAB_DIMS = ["resource", "resource_type", "board_type", "grant_type", "nsfdirectorate",
             "parentscience", "jobsize", "jobwalltime", "jobwaittime", "gateway", "queue",
             "pi_institution_state"]
XTAB_METRICS = ["total_ace", "job_count", "active_pi_count", "active_person_count", "active_allocation_count"]

for p in (RAW, DERIVED, DOCS):
    p.mkdir(parents=True, exist_ok=True)
