#!/usr/bin/env python3
"""Step 4c - pull monthly usage per allocation (charge number) for recent projects.

Lets the analysis compute utilization per awarded allocation: each current project's usage since it began,
divided by its rebuilt award. Only the window from AWARD_SINCE is pulled, because only projects begun since
then carry a trustworthy award (see classify.py). Requests are split by quarter; longer requests by
allocation time out at the XDMoD gateway.

Writes data/raw/xdmod_allocation_monthly.csv: allocation (charge number), month, ace.
"""
import argparse
import pandas as pd
from config import RAW, XDMOD_URL, END, AWARD_SINCE
from fetch_xdmod import load_token, get_data


def quarters(start, end):
    cuts = [d for d in pd.date_range(start, end, freq="QS") if d > pd.Timestamp(start)]
    los = [pd.Timestamp(start)] + cuts
    his = [c - pd.Timedelta(days=1) for c in cuts] + [pd.Timestamp(end)]
    return [(lo.date().isoformat(), hi.date().isoformat()) for lo, hi in zip(los, his)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", default=AWARD_SINCE)
    ap.add_argument("--end", default=END)
    a = ap.parse_args()
    w = RAW / "xdmod_window.txt"
    if w.exists() and a.end == END:
        a.end = w.read_text().split()[1]
    load_token()
    from xdmod_data.warehouse import DataWarehouse

    parts = []
    with DataWarehouse(XDMOD_URL) as dw:
        for lo, hi in quarters(a.start, a.end):
            print("allocation monthly", lo, hi, flush=True)
            ts = get_data(dw, duration=(lo, hi), realm="Jobs", metric="total_ace", dimension="allocation",
                             dataset_type="timeseries", aggregation_unit="Month")
            wide = ts.T.reset_index()
            st = wide.melt(id_vars=wide.columns[0], var_name="month", value_name="ace")
            st.columns = ["label", "month", "ace"]
            parts.append(st)
    m = pd.concat(parts)
    m = m[m.ace.astype(float) > 0]
    out = pd.DataFrame({"allocation": m.label.astype(str).str.split(" - ", n=1).str[0].str.strip(),
                        "month": pd.to_datetime(m.month).dt.strftime("%Y-%m"), "ace": m.ace.astype(float)})
    out = out.groupby(["allocation", "month"], as_index=False).ace.sum().sort_values(["allocation", "month"])
    out.to_csv(RAW / "xdmod_allocation_monthly.csv", index=False)
    print("wrote", RAW / "xdmod_allocation_monthly.csv", len(out), "rows,", out.allocation.nunique(), "allocations")


if __name__ == "__main__":
    main()
