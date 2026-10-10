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
from config import RAW, DERIVED, ORDER, NONR1, AWARD_SINCE

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
    # Awards are rebuilt in classify.py; only projects with award_ok (all resources convertible, began on or after
    # AWARD_SINCE) carry a trustworthy amount, so every credit share below is computed on that subset.
    pa = proj[proj.award_ok]
    u = x.groupby("cohort").agg(ace=("total_ace", "sum"), n=("pi_institution", "count"),
                                pis=("active_pi_count", "sum"), users=("active_person_count", "sum")).reindex(TIERS).fillna(0)
    p = proj.groupby("cohort").agg(projects=("projectId", "count"), inst=("piInstitution", "nunique"),
                                   ).reindex(TIERS).fillna(0)
    p["credits"] = pa.groupby("cohort").award.sum().reindex(TIERS).fillna(0)
    tot_ace, tot_p, tot_c = x.total_ace.sum(), len(proj), p.credits.sum()
    D["shares"] = [dict(tier=t, usage=round(u.ace[t] / tot_ace * 100, 2), projects=round(p.projects[t] / tot_p * 100, 2),
                        credits=round(p.credits[t] / tot_c * 100, 2), inst_used=int(u.n[t]), inst_awarded=int(p.inst[t]),
                        pis=int(u.pis[t]), users=int(u.users[t]), ace=float(u.ace[t]), nproj=int(p.projects[t])) for t in TIERS]

    # ---- benchmark against research activity and reach within each Carnegie tier ----------
    # HERD (higher-ed R&D spending) is only published for designated institutions, so this covers R1, R2 and RCU and
    # normalizes every share to those three tiers. Reach counts distinct Carnegie institutions with any usage in the window.
    car = pd.read_excel(RAW / "carnegie_2025_rad.xlsx", sheet_name="Data")
    car["tier"] = car["2025 Research Activity Designation"].str.extract(r"^(Research 1|Research 2|Research Colleges)")[0].map(
        {"Research 1": "R1", "Research 2": "R2", "Research Colleges": "RCU"})
    BT = ["R1", "R2", "RCU"]
    herd = car.groupby("tier")["HERD FY21-23 AVG"].sum().reindex(BT)
    # Standalone health-science institutions carry large biomedical R&D budgets and little HPC demand, while integrated
    # R1s carry the same spending invisibly inside the parent, so the benchmark is also reported without them. They are
    # the 2021 Carnegie special-focus classes below; "Research Institution" in this file is entirely biomedical
    # (Icahn, Baylor College of Medicine, UCSF, OHSU, Rockefeller, ...).
    car["med"] = car["2021 Carnegie Classification"].isin([
        "Special Focus Four-Year: Medical Schools & Centers", "Special Focus Four-Year: Research Institution",
        "Special Focus Four-Year: Other Health Professions Schools"])
    med = set(car[car.med].INSTNM)
    reached = set(x.carnegie_instnm.dropna())
    xs = x.assign(med=x.carnegie_instnm.isin(med))
    ps = pa.assign(med=pa.carnegie_instnm.isin(med))

    def bench(keep_med):
        c = car if keep_med else car[~car.med]
        hh = c.groupby("tier")["HERD FY21-23 AVG"].sum().reindex(BT)
        aw = (ps if keep_med else ps[~ps.med]).groupby("cohort").award.sum().reindex(BT).fillna(0)
        us = (xs if keep_med else xs[~xs.med]).groupby("cohort").total_ace.sum().reindex(BT).fillna(0)
        return hh / hh.sum() * 100, aw / aw.sum() * 100, us / us.sum() * 100
    h_all, a_all, u_all = bench(True)
    h_xm, a_xm, u_xm = bench(False)
    rh = car.assign(r=car.INSTNM.isin(reached)).groupby("tier").apply(
        lambda d: d.loc[d.r, "HERD FY21-23 AVG"].sum() / d["HERD FY21-23 AVG"].sum() * 100, include_groups=False)
    D["benchmark"] = [dict(tier=t, n=int((car.tier == t).sum()), reached=int(car[(car.tier == t)].INSTNM.isin(reached).sum()),
                           reached_herd=round(rh[t], 1), herd=round(h_all[t], 1), credits=round(a_all[t], 1), usage=round(u_all[t], 1),
                           herd_xmed=round(h_xm[t], 1), credits_xmed=round(a_xm[t], 1), usage_xmed=round(u_xm[t], 1),
                           n_med=int((car.tier == t).sum() - (car[~car.med].tier == t).sum()),
                           n_xmed=int(((car.tier == t) & ~car.med).sum()),
                           reached_xmed=int(car[(car.tier == t) & ~car.med].INSTNM.isin(reached).sum())) for t in BT]
    un = car[car.tier.isin(["R2", "RCU"]) & ~car.INSTNM.isin(reached)].sort_values(["HERD FY21-23 AVG", "INSTNM"], ascending=[False, True], kind="stable")
    D["unreached"] = [dict(name=r.INSTNM, tier=r.tier, state=r.State, herd_m=round(r["HERD FY21-23 AVG"] / 1e6, 1), med=bool(r.med))
                      for _, r in un.iterrows()]
    un[["INSTNM", "tier", "State", "HERD FY21-23 AVG", "med"]].to_csv(DERIVED / "unreached_institutions.csv", index=False)

    # ---- monthly -> quarterly by cohort -------------------------------------------------
    ace = pd.read_csv(RAW / "xdmod_monthly_total_ace_by_pi_institution.csv", index_col=0, parse_dates=True)
    ace = ace.loc[:, ace.columns.map(lambda c: c in gmap)]
    groups = pd.Series(gmap).reindex(ace.columns)
    A = ace.T.groupby(groups).sum().T.reindex(columns=ORDER).fillna(0)
    A["nonR1"] = A[NONR1].sum(axis=1)
    last_full_q = (pd.Timestamp(end) if end else ace.index.max()).to_period("Q").start_time - pd.Timedelta(days=1)
    first_full_q = pd.Timestamp(start).to_period("Q").start_time
    if first_full_q < pd.Timestamp(start):
        first_full_q = (pd.Timestamp(start).to_period("Q") + 1).start_time
    q = A.resample("QE").sum()
    q = q[(q.index <= last_full_q) & (q.index >= first_full_q)]
    D["quarterly"] = [dict(q=qlabel(d), R2=round(r.R2 / 1e6, 2), RCU=round(r.RCU / 1e6, 2), Other=round(r["Other academic"] / 1e6, 2),
                           R1=round(r.R1 / 1e6, 1), share=round(r.nonR1 / r[ORDER].sum() * 100, 2)) for d, r in q.iterrows()]

    # ---- active institutions per quarter and 4-quarter retention -------------------------
    qa = (ace.resample("QE").sum() > 0)
    qa = qa[(qa.index <= last_full_q) & (qa.index >= first_full_q)]
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
    # ---- usage per awarded credit within allocation type ------------------------------------
    # Awards are the rebuilt amounts on award_ok projects. Maximize is excluded (reviewed allocations, not a fixed
    # credit size) and legacy Research has no credits. Usage covers the whole window while awards are recent current
    # projects only, so compare tiers within a type; the absolute ratio means little.
    ET = ["Explore", "Discover", "Accelerate"]
    pc = pa.assign(grp=pa.cohort.where(~pa.cohort.isin(NONR1), "nonR1"))
    cr = pc[pc.grp.isin(["R1", "nonR1"])].pivot_table(index="allocationType", columns="grp", values="award", aggfunc="sum").reindex(ET)
    ub = bt.reindex(ET)[["R1", "nonR1"]]
    conv = ub / cr
    c_r1, c_nr = ub.R1.sum() / cr.R1.sum(), ub.nonR1.sum() / cr.nonR1.sum()
    c_nr_r1mix = (cr.R1 / cr.R1.sum() * conv.nonR1).sum()
    c_r1_nrmix = (cr.nonR1 / cr.nonR1.sum() * conv.R1).sum()
    D["by_type"] = dict(
        rows=[dict(type=t, credit_share=round(cr.nonR1[t] / cr.loc[t].sum() * 100, 1), usage_share=round(ub.nonR1[t] / ub.loc[t].sum() * 100, 1),
                   credit_mix_r1=round(cr.R1[t] / cr.R1.sum() * 100, 1), credit_mix_nonr1=round(cr.nonR1[t] / cr.nonR1.sum() * 100, 1),
                   rel_conv=round(conv.nonR1[t] / conv.R1[t], 2)) for t in ET],
        credit_share=round(cr.nonR1.sum() / cr.sum().sum() * 100, 1), usage_share=round(ub.nonR1.sum() / ub.sum().sum() * 100, 1),
        rel_conv=round(c_nr / c_r1, 2), award_projects=int(len(pa)), all_projects=int(len(proj)),
        since_projects=int((proj.beginDate >= AWARD_SINCE).sum()),
        # the mix decomposition only means something when there is an overall gap to decompose
        mix_explained=(sorted([round((c_nr_r1mix - c_nr) / (c_r1 - c_nr) * 100), round((c_r1 - c_r1_nrmix) / (c_r1 - c_nr) * 100)])
                       if abs(c_nr / c_r1 - 1) >= 0.1 else None),
        r1_large=round((bt.R1.get("Maximize", 0) + bt.R1.get("Research", 0)) / bt.R1.sum() * 100, 1))
    # ---- new vs experienced PIs -------------------------------------------------------------
    # Experienced = any usage as PI in the pre-ACCESS lookback (fetch_xdmod_pis.py). A PI is keyed by XDMoD's
    # "name - institution" label, so a PI who changed institutions counts as new. "Continued" = any usage 12 or more
    # months after the PI's first ACCESS-window month, among PIs whose first month is at least 12 months before the end.
    if (RAW / "xdmod_pi_monthly.csv").exists():
        pm_ = pd.read_csv(RAW / "xdmod_pi_monthly.csv")
        prior = set(pd.read_csv(RAW / "xdmod_pi_prior.csv").pi)
        pb = pd.read_csv(RAW / "xdmod_pi_board.csv")
        pm_["grp"] = pm_.tier.where(pm_.tier == "R1", "nonR1")
        pm_["m"] = pd.PeriodIndex(pm_.month, freq="M").astype("int64")
        last = pm_.m.max()
        pis = pm_.groupby(["grp", "pi"]).agg(first=("m", "min"), lastm=("m", "max"), months=("m", "nunique"), ace=("ace", "sum")).reset_index()
        pis["new"] = ~pis.pi.isin(prior)
        later = pm_.merge(pis[["grp", "pi", "first"]], on=["grp", "pi"])
        key = lambda d: set(zip(d.grp, d.pi))
        c12 = key(later[later.m >= later["first"] + 12])
        c6 = key(later[(later.m >= later["first"] + 6) & (later.m <= later["first"] + 11)])
        pis["eligible"] = pis["first"] <= last - 12
        pis["continued"] = [k in c12 for k in zip(pis.grp, pis.pi)]
        pis["cont6"] = [k in c6 for k in zip(pis.grp, pis.pi)]
        # A PI labelled by their dominant type would be circular (PIs who stay tend to move up), so use
        # "ever used Explore" as the closest available proxy for starting on Explore.
        pis["explore"] = pis.pi.isin(set(pb[pb.board == "Explore"].pi))
        tier_of_pi = pm_.groupby(["grp", "pi"]).tier.agg(lambda t: t.value_counts().index[0])
        pis["tier"] = [tier_of_pi[(g, i)] for g, i in zip(pis.grp, pis.pi)]

        def cell(d):
            e = d[d.eligible]
            return dict(n=int(len(d)), ace_share=0.0, med_months=float(d.months.median()), med_ace=round(float(d.ace.median()) / 1e3, 1),
                        cont=round(e.continued.mean() * 100, 1) if len(e) else None, explore=round(d.explore.mean() * 100, 1))
        rows = []
        for g in ["R1", "nonR1"]:
            d = pis[pis.grp == g]
            for lab, sub in (("New", d[d.new]), ("Experienced", d[~d.new])):
                c = cell(sub)
                c.update(grp=g, kind=lab, ace_share=round(sub.ace.sum() / d.ace.sum() * 100, 1), pi_share=round(len(sub) / len(d) * 100, 1))
                rows.append(c)
        # continuation within new PIs: ever used Explore vs never
        ty = []
        for g in ["R1", "nonR1"]:
            for lab, sub in (("Explore", pis[(pis.grp == g) & pis.new & pis.explore & pis.eligible]),
                             ("Other types", pis[(pis.grp == g) & pis.new & ~pis.explore & pis.eligible])):
                ty.append(dict(grp=g, kind=lab, n=int(len(sub)), cont=round(sub.continued.mean() * 100, 1)))
        el6 = pis[pis["first"] <= last - 12]
        cont6 = {g: round(el6[(el6.grp == g) & el6.new].cont6.mean() * 100, 1) for g in ["R1", "nonR1"]}
        sub_tier = [dict(tier=t, n=int(len(d)), cont=round(d.continued.mean() * 100, 1))
                    for t in ["R1"] + NONR1 for d in [pis[(pis.tier == t) & pis.new & pis.eligible]]]
        # how much of the R1 / non-R1 continuation gap is the new-PI mix
        el = pis[pis.eligible]
        cr_ = el.groupby(["grp", "new"]).continued.mean()
        mix_r1 = el[el.grp == "R1"].new.value_counts(normalize=True)
        nr_at_r1mix = sum(mix_r1[k] * cr_[("nonR1", k)] for k in mix_r1.index)
        r1c, nrc = el[el.grp == "R1"].continued.mean(), el[el.grp == "nonR1"].continued.mean()
        D["pi_tenure"] = dict(rows=rows, by_type=ty, cont_r1=round(r1c * 100, 1), cont_nonr1=round(nrc * 100, 1),
                              cont_nonr1_r1mix=round(nr_at_r1mix * 100, 1), cont6_new=cont6, sub_tier=sub_tier,
                              pis_per_inst=[dict(tier=t, median=float(x[x.cohort == t].active_pi_count.median()),
                                                 one=round((x[x.cohort == t].active_pi_count <= 1).mean() * 100, 1)) for t in TIERS[:4]])

    rs = mix("resource", "total_ace")
    tot = rs.sum()
    gpu = rs[rs.index.str.contains(r"GPU|\bAI\b|DeltaAI|Neocortex|ACES|FASTER", regex=True)].sum()
    D["gpu_share"] = {g: round(gpu[g] / tot[g] * 100, 1) for g in ["R1", "nonR1"]}
    gw = xt[(xt.dimension == "gateway") & (xt.group == "nonR1") & xt.metric.isin(["total_ace", "job_count"])].pivot_table(
        index="value", columns="metric", values="amount", aggfunc="sum")
    gw = gw / gw.sum() * 100
    top = gw.sort_values("job_count", ascending=False).iloc[0]
    D["gateway_top"] = dict(name=top.name.split(";")[0], jobs=round(top.job_count, 1), ace=round(top.total_ace, 1))
    top = rs.sort_values("nonR1", ascending=False).head(10)
    D["resources"] = [dict(resource=i, R1=round(r.R1 / tot.R1 * 100, 1), nonR1=round(r.nonR1 / tot.nonR1 * 100, 1)) for i, r in top.iterrows()]

    # ---- funnel: awarded institutions that never ran a job --------------------------------
    D["never_used"] = [dict(tier=g, never=int(((pinst.cohort == g) & ~pinst.ever_used).sum()), total=int((pinst.cohort == g).sum()),
                            pct=round(((pinst.cohort == g) & ~pinst.ever_used).sum() / max((pinst.cohort == g).sum(), 1) * 100, 1),
                            projects=int(pinst[(pinst.cohort == g) & ~pinst.ever_used].projects.sum())) for g in TIERS]
    nu = pinst[~pinst.ever_used & pinst.cohort.isin(NONR1)].sort_values(["projects", "piInstitution"], ascending=[False, True], kind="stable")
    D["never_examples"] = [dict(name=r.piInstitution, tier=r.cohort, projects=int(r.projects)) for _, r in nu.head(8).iterrows()]

    # ---- MSIs and top non-R1 ---------------------------------------------------------------
    h = x[x.msi.notna() & (x.msi != "")].sort_values(["total_ace", "pi_institution"], ascending=[False, True], kind="stable")
    D["hbcu"] = [dict(name=r.pi_institution.split(" - ")[-1], msi=r.msi, tier=r.tier, ace=round(r.total_ace / 1e6, 2),
                      pis=int(r.active_pi_count), users=int(r.active_person_count)) for _, r in h.head(12).iterrows()]
    nonr1_ace = x[x.cohort.isin(NONR1)].total_ace.sum()
    # XDMoD can list one institution under several labels (e.g. two Prairie View A&M labels), so count by UNITID
    hu = h.groupby("UNITID").agg(msi=("msi", "first"), cohort=("cohort", "first"), pis=("active_pi_count", "sum"))
    D["hbcu_summary"] = dict(n=int((hu.msi == "HBCU").sum()), total=102, tcu=int((hu.msi == "TCU").sum()), tcu_total=35,
                             ace=round(h.total_ace.sum() / 1e6, 1), share_all=round(h.total_ace.sum() / tot_ace * 100, 2),
                             share_nonr1=round(h[h.cohort.isin(NONR1)].total_ace.sum() / nonr1_ace * 100, 1),
                             inst_share_nonr1=round(hu.cohort.isin(NONR1).sum() / x[x.cohort.isin(NONR1)].pipe(
                                 lambda d: d.UNITID.nunique() + d.UNITID.isna().sum()) * 100, 1),
                             single_pi=int(((hu.msi == "HBCU") & (hu.pis <= 1)).sum()))
    t = x[x.cohort.isin(NONR1)].sort_values(["total_ace", "pi_institution"], ascending=[False, True], kind="stable").head(12)
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
                     nonr1_credit_share=round(nonr1_p.credits.sum() / tot_c * 100, 1), award_projects=int(len(pa)), nonr1_projects=int(nonr1_p.projects.sum()),
                     retention_nonr1=round(float(np.mean(ret_nr)), 0), retention_r1=round(float(np.mean(ret_r1)), 0))

    json.dump(D, open(DERIVED / "report_data.json", "w"), indent=0)
    summary = "\n".join([f"window {start} .. {end}", f"total ACE (B) {D['meta']['total_ace']}",
                         f"R1 usage share {D['meta']['r1_share']}%", f"non-R1 academic usage share {D['meta']['nonr1_share']}%",
                         f"non-R1 academic project share {D['meta']['nonr1_proj_share']}%", f"non-R1 academic credit share {D['meta']['nonr1_credit_share']}%",
                         f"retention R1 {D['meta']['retention_r1']}% / non-R1 {D['meta']['retention_nonr1']}%",
                         *[f"{b['tier']}: reached {b['reached']}/{b['n']} ({b['reached_herd']}% of tier research spending), research spending {b['herd']}% / awarded credits {b['credits']}% / usage {b['usage']}% of R1+R2+RCU; without standalone medical schools {b['herd_xmed']}% / {b['credits_xmed']}% / {b['usage_xmed']}%" for b in D["benchmark"]],
                         *([f"PIs continuing 12+ months: R1 {D['pi_tenure']['cont_r1']}% / non-R1 {D['pi_tenure']['cont_nonr1']}%",
                            *[f"{r['grp']} {r['kind']} PIs: {r['pi_share']}% of PIs, {r['ace_share']}% of usage, continued {r['cont']}%" for r in D['pi_tenure']['rows']],
                            *[f"{r['grp']} new {r['kind']} PIs continued {r['cont']}% (n={r['n']})" for r in D['pi_tenure']['by_type']],
                            *[f"{r['tier']} median active PIs per institution {r['median']}, single-PI {r['one']}%" for r in D['pi_tenure']['pis_per_inst']]]
                           if "pi_tenure" in D else []),
                         f"Explore/Discover/Accelerate non-R1 credit share {D['by_type']['credit_share']}% / usage share {D['by_type']['usage_share']}%",
                         *[f"{r['type']} non-R1 usage per credit vs R1 {r['rel_conv']}x" for r in D["by_type"]["rows"]],
                         f"Explore/Discover/Accelerate non-R1 usage per credit vs R1 overall {D['by_type']['rel_conv']}x (awards from {D['by_type']['award_projects']} of {D['by_type']['all_projects']} current projects)",
                         f"Maximize + legacy Research share of R1 usage {D['by_type']['r1_large']}%",
                         *[f"never-used {r['tier']}: {r['never']}/{r['total']} ({r['pct']}%)" for r in D["never_used"]],
                         f"HBCU with usage {D['hbcu_summary']['n']}/102, TCU {D['hbcu_summary']['tcu']}/35"])
    (DERIVED / "summary.txt").write_text(summary + "\n")
    print(summary)


if __name__ == "__main__":
    main()
