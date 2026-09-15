#!/usr/bin/env python3
"""Step 2 - pull ACCESS XDMoD Jobs-realm usage by PI institution.

Requires an XDMoD API token (xdmod.access-ci.org -> My Profile -> API Token)
in the environment as XDMOD_API_TOKEN, or in a .env file at the repo root,
or in ~/xdmod-api.key.

Writes to data/raw/:
  xdmod_by_pi_institution.csv                   aggregate totals per PI institution
  xdmod_by_pi_institution_type.csv              aggregate totals per PI institution type
  xdmod_monthly_<metric>_by_pi_institution.csv  monthly timeseries per PI institution

Pass --end YYYY-MM-DD to pin the window end (default: yesterday) so that a
re-run can reproduce a dated snapshot exactly.
"""
import argparse, os, pathlib
import pandas as pd
from config import RAW, XDMOD_URL, START, END, METRICS, MONTHLY_METRICS


def load_token():
    if os.environ.get("XDMOD_API_TOKEN"):
        return
    try:
        from dotenv import load_dotenv
        load_dotenv(pathlib.Path(__file__).resolve().parents[1] / ".env")
    except ImportError:
        pass
    if not os.environ.get("XDMOD_API_TOKEN"):
        key = pathlib.Path("~/xdmod-api.key").expanduser()
        if key.exists():
            os.environ["XDMOD_API_TOKEN"] = key.read_text().strip()
    if not os.environ.get("XDMOD_API_TOKEN"):
        raise SystemExit("XDMOD_API_TOKEN not set (env, .env, or ~/xdmod-api.key)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", default=START)
    ap.add_argument("--end", default=END)
    a = ap.parse_args()
    load_token()
    from xdmod_data.warehouse import DataWarehouse

    dur = (a.start, a.end)
    print(f"window {a.start} .. {a.end}")
    frames = {}
    with DataWarehouse(XDMOD_URL) as dw:
        for m in METRICS:
            print("aggregate", m, flush=True)
            frames[m] = dw.get_data(duration=dur, realm="Jobs", metric=m,
                                    dimension="pi_institution", dataset_type="aggregate")
        types = dw.get_data(duration=dur, realm="Jobs", metric="total_ace",
                            dimension="pi_institution_type", dataset_type="aggregate")
        types.to_csv(RAW / "xdmod_by_pi_institution_type.csv")
        for m in MONTHLY_METRICS:
            print("monthly", m, flush=True)
            ts = dw.get_data(duration=dur, realm="Jobs", metric=m, dimension="pi_institution",
                             dataset_type="timeseries", aggregation_unit="Month")
            ts.to_csv(RAW / f"xdmod_monthly_{m}_by_pi_institution.csv")
    df = pd.DataFrame(frames)
    df.index.name = "pi_institution"
    df.to_csv(RAW / "xdmod_by_pi_institution.csv")
    (RAW / "xdmod_window.txt").write_text(f"{a.start}\n{a.end}\n")
    print("wrote", RAW / "xdmod_by_pi_institution.csv", df.shape,
          f"total ACE {df.total_ace.sum():,.2f}")


if __name__ == "__main__":
    main()
