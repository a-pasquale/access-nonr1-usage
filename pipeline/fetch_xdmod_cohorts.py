#!/usr/bin/env python3
"""Step 4 - pull XDMoD cross-tabs for the R1 and non-R1-academic cohorts.

Runs AFTER classify.py, because the cohorts are defined by the classified
institution list (data/derived/cohorts.json). Filters XDMoD by pi_institution.

Writes to data/raw/:
  xdmod_xtabs.csv                       long table: group, dimension, metric, value, amount
  xdmod_quarterly_<group>_<dim>.csv     quarterly ACE timeseries by resource_type / board_type / jobsize
"""
import argparse, json
import pandas as pd
from config import RAW, DERIVED, XDMOD_URL, START, END, XTAB_DIMS, XTAB_METRICS
from fetch_xdmod import load_token


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", default=START)
    ap.add_argument("--end", default=END)
    a = ap.parse_args()
    # reuse the exact window of the institution pull when present
    w = RAW / "xdmod_window.txt"
    if w.exists() and a.end == END:
        a.start, a.end = w.read_text().split()
    load_token()
    from xdmod_data.warehouse import DataWarehouse

    cohorts = json.load(open(DERIVED / "cohorts.json"))
    dur = (a.start, a.end)
    frames = []
    with DataWarehouse(XDMOD_URL) as dw:
        for grp, insts in cohorts.items():
            for dim in XTAB_DIMS:
                for m in XTAB_METRICS:
                    print(grp, dim, m, flush=True)
                    try:
                        s = dw.get_data(duration=dur, realm="Jobs", metric=m, dimension=dim,
                                        dataset_type="aggregate", filters={"pi_institution": insts})
                    except Exception as e:  # noqa: BLE001
                        print("  FAILED", e)
                        continue
                    df = s.reset_index()
                    df.columns = ["value", "amount"]
                    df["group"], df["dimension"], df["metric"] = grp, dim, m
                    frames.append(df)
            for dim in ["resource_type", "board_type", "jobsize"]:
                print(grp, "quarterly", dim, flush=True)
                ts = dw.get_data(duration=dur, realm="Jobs", metric="total_ace", dimension=dim,
                                 dataset_type="timeseries", aggregation_unit="Quarter",
                                 filters={"pi_institution": insts})
                ts.to_csv(RAW / f"xdmod_quarterly_{grp}_{dim}.csv")
    pd.concat(frames).to_csv(RAW / "xdmod_xtabs.csv", index=False)
    print("wrote", RAW / "xdmod_xtabs.csv")


if __name__ == "__main__":
    main()
