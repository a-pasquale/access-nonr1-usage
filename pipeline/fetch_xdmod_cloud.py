#!/usr/bin/env python3
"""Step 2b - pull Jetstream2 usage from XDMoD's Cloud realm.

The Jobs realm covers batch HPC only. Jetstream2 (cloud) usage is reported separately, in core-hours, by resource.
Core-hours are converted to ACCESS Credits in analyze.py with the per-resource SU rates in overrides.json
(cloud_su_per_core_hour). Requests are per resource, and the allocation pull is split by quarter to stay under the
gateway timeout.

Writes to data/raw/:
  xdmod_cloud_by_pi_institution.csv   pi_institution, resource, core_hours   (whole window)
  xdmod_cloud_allocation_monthly.csv  allocation, resource, month, core_hours (from AWARD_SINCE)
"""
import argparse, json
import pandas as pd
from config import RAW, ROOT, XDMOD_URL, START, END, AWARD_SINCE
from fetch_xdmod import load_token, get_data
from fetch_xdmod_allocations import quarters

RESOURCES = [k for k in json.load(open(ROOT / "data" / "overrides.json"))["cloud_su_per_core_hour"] if not k.startswith("_")]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", default=START)
    ap.add_argument("--end", default=END)
    a = ap.parse_args()
    w = RAW / "xdmod_window.txt"
    if w.exists() and a.end == END:
        a.start, a.end = w.read_text().split()
    load_token()
    from xdmod_data.warehouse import DataWarehouse

    inst, alloc = [], []
    with DataWarehouse(XDMOD_URL) as dw:
        for r in RESOURCES:
            print("cloud by institution", r, flush=True)
            s = get_data(dw, duration=(a.start, a.end), realm="Cloud", metric="cloud_core_time", dimension="pi_institution",
                         dataset_type="aggregate", filters={"resource": [r]})
            inst.append(pd.DataFrame({"pi_institution": s.index.astype(str), "resource": r, "core_hours": s.values.astype(float)}))
            for lo, hi in quarters(AWARD_SINCE, a.end):
                print("cloud by allocation", r, lo, hi, flush=True)
                ts = get_data(dw, duration=(lo, hi), realm="Cloud", metric="cloud_core_time", dimension="allocation",
                              dataset_type="timeseries", aggregation_unit="Month", filters={"resource": [r]})
                wide = ts.T.reset_index()
                st = wide.melt(id_vars=wide.columns[0], var_name="month", value_name="core_hours")
                st.columns = ["label", "month", "core_hours"]
                st = st[st.core_hours.astype(float) > 0]
                alloc.append(pd.DataFrame({"allocation": st.label.astype(str).str.split(" - ", n=1).str[0].str.strip(), "resource": r,
                                           "month": pd.to_datetime(st.month).dt.strftime("%Y-%m"), "core_hours": st.core_hours.astype(float)}))
    i = pd.concat(inst)
    i = i[i.core_hours > 0].sort_values(["pi_institution", "resource"])
    i.to_csv(RAW / "xdmod_cloud_by_pi_institution.csv", index=False)
    al = pd.concat(alloc).groupby(["allocation", "resource", "month"], as_index=False).core_hours.sum().sort_values(["allocation", "resource", "month"])
    al.to_csv(RAW / "xdmod_cloud_allocation_monthly.csv", index=False)
    print("wrote cloud files:", len(i), "institution rows,", al.allocation.nunique(), "allocations")


if __name__ == "__main__":
    main()
