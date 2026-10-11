#!/usr/bin/env python3
"""Step 4b - pull PI-level usage per tier, to separate new PIs from experienced ones.

Runs AFTER classify.py (needs data/derived/institutions.csv for the tier institution lists).
A PI is "experienced" if they had any usage as PI in the lookback window before ACCESS
(XSEDE era, default 2017-01-01 .. 2022-08-31), otherwise "new".

PI names are replaced with a short hash before anything is written, so the committed raw
files carry no per-person names.

Writes to data/raw/:
  xdmod_pi_prior.csv     pi, pi_name, ace       usage before ACCESS (lookback window); pi_name hashes 'last, first'
                                                 so the Allocations feed's PI names can be matched
  xdmod_pi_monthly.csv   tier, pi, pi_name, month, ace   monthly usage in the ACCESS window
  xdmod_pi_board.csv     tier, pi, board, ace   ACCESS-window usage by allocation type
"""
import argparse, hashlib
import pandas as pd
from config import RAW, DERIVED, XDMOD_URL, START, END, NONR1
from fetch_xdmod import load_token, get_data
from classify import norm

TIERS = ["R1"] + NONR1
SUFFIXES = {"jr", "sr", "ii", "iii", "iv"}
BOARDS = ["Explore", "Discover", "Accelerate", "Maximize"]


def h(name):
    return hashlib.sha1(str(name).encode()).hexdigest()[:12]


def name_key(label):
    """'Last, First Middle - Inst' -> 'last, first': matches the Allocations feed's PI name, which has no institution."""
    name = str(label).split(" - ", 1)[0]
    # drop generational suffixes wherever they sit ("Smith, Jr., John" / "Smith, John Jr.")
    parts = [t.strip() for t in name.split(",") if t.strip().rstrip(".").lower() not in SUFFIXES]
    last = parts[0] if parts else ""
    first = [w for w in " ".join(parts[1:]).split() if w.rstrip(".,").lower() not in SUFFIXES]
    return f"{last.lower()}, {(first or [''])[0].lower()}"


def years(start, end):
    """Split [start, end] into calendar-year pieces (inclusive dates)."""
    cuts = [d for d in pd.date_range(start, end, freq="YS") if d > pd.Timestamp(start)]
    los = [pd.Timestamp(start)] + cuts
    his = [c - pd.Timedelta(days=1) for c in cuts] + [pd.Timestamp(end)]
    return [(lo.date().isoformat(), hi.date().isoformat()) for lo, hi in zip(los, his)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--lookback", default="2017-01-01")
    ap.add_argument("--start", default=START)
    ap.add_argument("--end", default=END)
    ap.add_argument("--skip-prior", action="store_true", help="keep the existing xdmod_pi_prior.csv")
    a = ap.parse_args()
    w = RAW / "xdmod_window.txt"
    if w.exists() and a.end == END:
        a.start, a.end = w.read_text().split()
    prior_end = (pd.Timestamp(a.start) - pd.Timedelta(days=1)).date().isoformat()
    load_token()
    from xdmod_data.warehouse import DataWarehouse

    x = pd.read_csv(DERIVED / "institutions.csv")
    prior, monthly, board = [], [], []
    with DataWarehouse(XDMOD_URL) as dw:
        # Pre-ACCESS usage is pulled unfiltered (a PI's experience does not depend on tier), one request per
        # year because a single multi-year request by PI times out at the XDMoD gateway.
        for lo, hi in ([] if a.skip_prior else years(a.lookback, prior_end)):
            print("prior", lo, hi, flush=True)
            s = get_data(dw, duration=(lo, hi), realm="Jobs", metric="total_ace", dimension="pi", dataset_type="aggregate")
            prior.append(pd.DataFrame({"pi": [h(i) for i in s.index], "pi_name": [h(name_key(i)) for i in s.index],
                                       "ace": s.values.astype(float)}))
        if prior:
            pd.concat(prior).groupby(["pi", "pi_name"], as_index=False).ace.sum().to_csv(RAW / "xdmod_pi_prior.csv", index=False)
        # XDMoD renames institutions over time ("University of Illinois at Urbana-Champaign" became
        # "... Illinois Urbana-Champaign"), so map the snapshot's labels to the current ones by normalized name.
        cur = dw.get_filter_values("Jobs", "pi_institution").label.tolist()
        key = lambda lab: norm(str(lab).split(" - ", 1)[-1])
        cmap = {key(c): c for c in cur}
        x["current"] = x.pi_institution.map(lambda l: l if l in set(cur) else cmap.get(key(l)))
        miss = x[x.cohort.isin(TIERS) & x.current.isna()]
        if len(miss):
            print(f"{len(miss)} institutions not found under any current XDMoD label:", miss.pi_institution.tolist(), flush=True)
        for t in TIERS:
            insts = x[(x.cohort == t) & x.current.notna()].current.unique().tolist()
            f = {"pi_institution": insts}
            parts = []
            for lo, hi in years(a.start, a.end):
                print(t, "monthly", lo, hi, flush=True)
                ts = get_data(dw, duration=(lo, hi), realm="Jobs", metric="total_ace", dimension="pi",
                                 dataset_type="timeseries", aggregation_unit="Month", filters=f)
                # stack each piece on its own: XDMoD can return two PIs under the same label, which breaks a wide concat
                wide = ts.T.reset_index()
                st = wide.melt(id_vars=wide.columns[0], var_name="month", value_name="ace")
                st.columns = ["pi", "month", "ace"]
                parts.append(st)
            m = pd.concat(parts)
            m = m[m.ace.astype(float) > 0]
            monthly.append(pd.DataFrame({"tier": t, "pi": m.pi.map(h), "pi_name": m.pi.map(lambda l: h(name_key(l))),
                                         "month": pd.to_datetime(m.month).dt.strftime("%Y-%m"), "ace": m.ace.astype(float)}))
            for b in BOARDS:
                print(t, "board", b, flush=True)
                s = get_data(dw, duration=(a.start, a.end), realm="Jobs", metric="total_ace", dimension="pi",
                                dataset_type="aggregate", filters={**f, "board_type": [b]})
                board.append(pd.DataFrame({"tier": t, "pi": [h(i) for i in s.index], "board": b, "ace": s.values.astype(float)}))
    pd.concat(monthly).to_csv(RAW / "xdmod_pi_monthly.csv", index=False)
    pd.concat(board).to_csv(RAW / "xdmod_pi_board.csv", index=False)
    print("wrote", RAW / "xdmod_pi_*.csv")


if __name__ == "__main__":
    main()
