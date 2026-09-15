#!/usr/bin/env python3
"""Step 5 - compute every figure on the page from the derived tables.

Inputs:  data/derived/institutions.csv, projects.csv, project_institutions.csv
         data/raw/xdmod_monthly_*.csv, xdmod_xtabs.csv
Output:  data/derived/report_data.json   (the only thing the page reads)
         data/derived/summary.txt        (the headline numbers, for diffing between runs)
"""
import json
import numpy as np
import pandas as pd
from config import RAW, DERIVED, ORDER, NONR1

TIERS = ["R1", "R2", "RCU", "Other academic", "Non-academic"]


def qlabel(d):
    return f"{d.year}Q{(d.month - 1) // 3 + 1}"


def main():
    D = {}
    x = pd.read_csv(DERIVED / "institutions.csv")
    proj = pd.read_csv(DERIVED / "projects.csv")
    pinst = pd.read_csv(DERIVED / "project_institutions.csv")
    start, end = (RAW / "xdmod_window.txt").read_text().split() if (RAW / "xdmod_window.txt").exists() else ("2022-09-01", "")
    gmap = dict(zip(x.pi_institution, x.cohort))

    # ---- shares: usage vs current projects vs awarded credits -----------------------------
    u = x.groupby("cohort").agg(ace=("total_ace", "sum"), n=("pi_institution", "count"),
                                pis=("active_pi_count", "sum"), users=("active_person_count", "sum")).reindex(TIERS).fillna(0)
    p = proj.groupby("cohort").agg(projects=("projectId", "count"), inst=("piInstitution", "nunique"),
                                   credits=("credits", "sum")).reindex(TIERS).fillna(0)
    tot_ace, tot_p, tot_c = x.total_ace.sum(), len(proj), proj.credits.sum()
    D["shares"] = [dict(tier=t, usage=round(u.ace[t] / tot_ace * 100, 2), projects=round(p.projects[t] / tot_p * 100, 2),
                        credits=round(p.credits[t] / tot_c * 100, 2), inst_used=int(u.n[t]), inst_awarded=int(p.inst[t]),
                        pis=int(u.pis[t]), users=int(u.users[t]), ace=float(u.ace[t]), nproj=int(p.projects[t])) for t in TIERS]

    # ---- monthly -> quarterly by cohort -------------------------------------------------
    ace = pd.read_csv(RAW / "xdmod_monthly_total_ace_by_pi_institution.csv", index_col=0, parse_dates=True)
    ace = ace.loc[:, ace.columns.map(lambda c: c in gmap)]
    groups = pd.Series(gmap).reindex(ace.columns)
    A = ace.T.groupby(groups).sum().T.reindex(columns=ORDER).fillna(0)
    A["nonR1"] = A[NONR1].sum(axis=1)
    last_full_q = (pd.Timestamp(end) if end else ace.index.max()).to_period("Q").start_time - pd.Timedelta(days=1)
    q = A.resample("QE").sum()
    q = q[q.index <= last_full_q]
    D["quarterly"] = [dict(q=qlabel(d), R2=round(r.R2 / 1e6, 2), RCU=round(r.RCU / 1e6, 2), Other=round(r["Other academic"] / 1e6, 2),
                           R1=round(r.R1 / 1e6, 1), share=round(r.nonR1 / r[ORDER].sum() * 100, 2)) for d, r in q.iterrows()]

    # ---- active institutions per quarter and 4-quarter retention -------------------------
    qa = (ace.resample("QE").sum() > 0)
    qa = qa[qa.index <= last_full_q]
    act = qa.T.groupby(groups).sum().T
    D["active_inst"] = [dict(q=qlabel(d), R1=int(r.get("R1", 0)), nonR1=int(sum(r.get(k, 0) for k in NONR1))) for d, r in act.iterrows()]

    def ret(cohorts):
        cols = [c for c in qa.columns if gmap[c] in cohorts]
        s = qa[cols]
        return [round((s.iloc[i] & s.iloc[i + 4]).sum() / s.iloc[i].sum() * 100, 1) for i in range(len(s) - 4)]
    D["retention"] = dict(quarters=[qlabel(d) for d in qa.index[:-4]], R1=ret(["R1"]), nonR1=ret(NONR1))

    # ---- persistence: months with any usage -------------------------------------------
    months = (ace > 0).sum()
    ma = pd.DataFrame({"months": months, "cohort": groups})
    D["persistence"] = [dict(tier=g, median=float(ma[ma.cohort == g].months.median()),
                             le3=round((ma[ma.cohort == g].months <= 3).mean() * 100, 1),
                             ge24=round((ma[ma.cohort == g].months >= 24).mean() * 100, 1)) for g in TIERS]
    D["months_possible"] = int(len(ace))

    # ---- program years (Sep-Aug) ----------------------------------------------------------
    fy = A.copy()
    fy["PY"] = [(d.year if d.month >= 9 else d.year - 1) for d in fy.index]
    full = fy.groupby("PY").size()
    f = fy.groupby("PY")[ORDER + ["nonR1"]].sum()
    f = f[full.reindex(f.index) == 12]
    D["py"] = [dict(py=f"PY{int(i)}", R1=round(r.R1 / 1e6), nonR1=round(r.nonR1 / 1e6, 1), share=round(r.nonR1 / r[ORDER].sum() * 100, 2)) for i, r in f.iterrows()]

    # ---- seasonality over complete calendar years ---------------------------------------
    yrs = [y for y, n in A.groupby(A.index.year).size().items() if n == 12]
    mm = A[A.index.year.isin(yrs)].copy()
    mm["mo"] = mm.index.month
    seas = mm.groupby("mo")[["R1", "nonR1"]].sum()
    seas = seas / seas.sum() * 100
    D["seasonality"] = dict(years=[int(y) for y in yrs], R1=[round(v, 2) for v in seas.R1], nonR1=[round(v, 2) for v in seas.nonR1])

    # ---- cross-tabs -----------------------------------------------------------------------
    xt = pd.read_csv(RAW / "xdmod_xtabs.csv")

    def mix(dim, metric):
        return xt[(xt.dimension == dim) & (xt.metric == metric)].pivot_table(index="value", columns="group", values="amount", aggfunc="sum").fillna(0)
    bt = mix("board_type", "total_ace")
    keys = [k for k in ["Explore", "Discover", "Accelerate", "Maximize", "Research"] if k in bt.index]
    bt = bt.loc[keys]
    D["board_usage"] = {g: {k: round(v / bt[g].sum() * 100, 1) for k, v in bt[g].items()} for g in ["R1", "nonR1"]}
    pm = pd.crosstab(proj.cohort, proj.allocationType)
    bk = [k for k in ["Explore", "Discover", "Accelerate", "Maximize"] if k in pm.columns]
    pm = pm[bk]
    nr = pm.reindex(NONR1).fillna(0).sum()
    r1 = pm.loc["R1"]
    D["board_projects"] = {"R1": {k: round(v / r1.sum() * 100, 1) for k, v in r1.items()}, "nonR1": {k: round(v / nr.sum() * 100, 1) for k, v in nr.items()},
                           "R1_n": {k: int(v) for k, v in r1.items()}, "nonR1_n": {k: int(v) for k, v in nr.items()}}
    rs = mix("resource", "total_ace")
    tot = rs.sum()
    top = rs.sort_values("nonR1", ascending=False).head(10)
    D["resources"] = [dict(resource=i, R1=round(r.R1 / tot.R1 * 100, 1), nonR1=round(r.nonR1 / tot.nonR1 * 100, 1)) for i, r in top.iterrows()]

    # ---- funnel: awarded institutions that never ran a job --------------------------------
    D["never_used"] = [dict(tier=g, never=int(((pinst.cohort == g) & ~pinst.ever_used).sum()), total=int((pinst.cohort == g).sum()),
                            pct=round(((pinst.cohort == g) & ~pinst.ever_used).sum() / max((pinst.cohort == g).sum(), 1) * 100, 1),
                            projects=int(pinst[(pinst.cohort == g) & ~pinst.ever_used].projects.sum())) for g in TIERS]
    nu = pinst[~pinst.ever_used & pinst.cohort.isin(NONR1)].sort_values("projects", ascending=False)
    D["never_examples"] = [dict(name=r.piInstitution, tier=r.cohort, projects=int(r.projects)) for _, r in nu.head(8).iterrows()]

    # ---- MSIs and top non-R1 ---------------------------------------------------------------
    h = x[x.msi.notna() & (x.msi != "")].sort_values("total_ace", ascending=False)
    D["hbcu"] = [dict(name=r.pi_institution.split(" - ")[-1], msi=r.msi, tier=r.tier, ace=round(r.total_ace / 1e6, 2),
                      pis=int(r.active_pi_count), users=int(r.active_person_count)) for _, r in h.head(12).iterrows()]
    nonr1_ace = x[x.cohort.isin(NONR1)].total_ace.sum()
    D["hbcu_summary"] = dict(n=int((h.msi == "HBCU").sum()), total=102, tcu=int((h.msi == "TCU").sum()), tcu_total=35,
                             ace=round(h.total_ace.sum() / 1e6, 1), share_all=round(h.total_ace.sum() / tot_ace * 100, 2),
                             share_nonr1=round(h.total_ace.sum() / nonr1_ace * 100, 1))
    t = x[x.cohort.isin(NONR1)].sort_values("total_ace", ascending=False).head(12)
    D["top_nonr1"] = [dict(name=r.pi_institution.split(" - ")[-1], tier=r.tier, ace=round(r.total_ace / 1e6, 1), pis=int(r.active_pi_count),
                           users=int(r.active_person_count), months=int(months.get(r.pi_institution, 0))) for _, r in t.iterrows()]

    # ---- headline ---------------------------------------------------------------------------
    nonr1_u = u.loc[NONR1]
    nonr1_p = p.loc[NONR1]
    ret_nr = D["retention"]["nonR1"]
    ret_r1 = D["retention"]["R1"]
    D["meta"] = dict(start=start, end=end, total_ace=round(tot_ace / 1e9, 2), total_projects=int(tot_p), inst_used=int(len(x)),
                     inst_awarded=int(len(pinst)), nonr1_inst=int(nonr1_u.n.sum()), nonr1_share=round(nonr1_u.ace.sum() / tot_ace * 100, 1),
                     r1_share=round(u.ace.R1 / tot_ace * 100, 1), nonr1_proj_share=round(nonr1_p.projects.sum() / tot_p * 100, 1),
                     nonr1_credit_share=round(nonr1_p.credits.sum() / tot_c * 100, 1), nonr1_projects=int(nonr1_p.projects.sum()),
                     retention_nonr1=round(float(np.mean(ret_nr)), 0), retention_r1=round(float(np.mean(ret_r1)), 0))

    json.dump(D, open(DERIVED / "report_data.json", "w"), indent=0)
    summary = "\n".join([f"window {start} .. {end}", f"total ACE (B) {D['meta']['total_ace']}",
                         f"R1 usage share {D['meta']['r1_share']}%", f"non-R1 academic usage share {D['meta']['nonr1_share']}%",
                         f"non-R1 academic project share {D['meta']['nonr1_proj_share']}%", f"non-R1 academic credit share {D['meta']['nonr1_credit_share']}%",
                         f"retention R1 {D['meta']['retention_r1']}% / non-R1 {D['meta']['retention_nonr1']}%",
                         *[f"never-used {r['tier']}: {r['never']}/{r['total']} ({r['pct']}%)" for r in D["never_used"]],
                         f"HBCU with usage {D['hbcu_summary']['n']}/102, TCU {D['hbcu_summary']['tcu']}/35"])
    (DERIVED / "summary.txt").write_text(summary + "\n")
    print(summary)


if __name__ == "__main__":
    main()
