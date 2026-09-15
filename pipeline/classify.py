#!/usr/bin/env python3
"""Step 3 - tag every PI institution with a Carnegie 2025 tier and MSI flags.

Inputs (data/raw/): xdmod_by_pi_institution.csv, carnegie_2025_rad.xlsx,
                    ipeds_hd2023.zip, all_projects.json
Rules:  data/overrides.json  (every manual mapping, reviewable in one file)

Outputs (data/derived/):
  institutions.csv    one row per XDMoD PI institution: cohort, Carnegie tier, UNITID, HBCU/TCU, usage totals
  projects.csv        one row per current ACCESS project with the PI institution's cohort
  project_institutions.csv  per awarded institution: current projects, cohort, whether it has ever run a job
  cohorts.json        {"R1": [...xdmod labels], "nonR1": [...]} used to filter the XDMoD cross-tab pull
  classify_report.txt what matched how, and what fell through to keyword rules

Matching strategy, in order:
  1. manual override (overrides.json: xdmod_to_carnegie)
  2. exact match on a normalized name (lowercase, punctuation stripped, "the"/"at"/"campus" removed)
  3. R1-unit patterns (supercomputer centers, medical schools of R1s)
  4. foreign / unknown / extra-academic pattern lists
  5. keyword rule: looks like a university/college -> Other academic, else Non-academic
Nothing is fuzzy-matched automatically: fuzzy suggestions are written to the report for a human to
promote into overrides.json.
"""
import json, re, zipfile
import pandas as pd
from rapidfuzz import process, fuzz
from config import RAW, DERIVED, ROOT, NONR1

O = json.load(open(ROOT / "data" / "overrides.json"))
report = []


def norm(s):
    s = str(s).lower().replace("&", " and ")
    s = re.sub(r"\bthe\b", " ", s)
    s = re.sub(r"\bsaint\b", "st", s)
    s = re.sub(r"[,\-–/()\.]", " ", s)
    s = re.sub(r"\bat\b", " ", s)
    s = re.sub(r"\bin the city of new york\b|\bmain campus\b|\bcampus\b", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def tier_of(designation):
    return "R1" if designation.startswith("Research 1") else "R2" if designation.startswith("Research 2") else "RCU"


def load_carnegie():
    car = pd.read_excel(RAW / "carnegie_2025_rad.xlsx", sheet_name="Data")
    car["tier"] = car["2025 Research Activity Designation"].map(tier_of)
    car["n"] = car["INSTNM"].map(norm)
    return car


def load_ipeds():
    with zipfile.ZipFile(RAW / "ipeds_hd2023.zip") as z:
        name = [n for n in z.namelist() if n.lower().endswith(".csv")][0]
        raw = z.open(name).read()
    # the file is cp1252 with a UTF-8 BOM on the header; strip the BOM bytes before decoding
    if raw.startswith(b"\xef\xbb\xbf"):
        raw = raw[3:]
    import io
    hd = pd.read_csv(io.BytesIO(raw), encoding="latin-1", low_memory=False)
    hd.columns = [c.strip().upper() for c in hd.columns]
    hd["n"] = hd["INSTNM"].map(norm)
    return hd[["UNITID", "INSTNM", "STABBR", "HBCU", "TRIBAL", "C21BASIC", "CONTROL", "n"]]


def find_carnegie(car, name):
    hits = car[car["INSTNM"].str.lower() == name.lower()]
    if len(hits) != 1:
        hits = car[car["INSTNM"].str.lower().str.contains(re.escape(name.lower()))]
    return hits.iloc[0] if len(hits) == 1 else None


def classify_xdmod(xd, car):
    ovr = O["xdmod_to_carnegie"]
    r1u = O["r1_units"]["patterns"]
    acad = re.compile(O["academic_regex"])
    notacad = re.compile(O["not_academic_regex"])
    rows = []
    for _, r in xd.iterrows():
        label, full, n = r["pi_institution"], r["full"], r["n"]
        tier = match = how = None
        if label in ovr:
            h = find_carnegie(car, ovr[label])
            if h is not None:
                tier, match, how = h["tier"], h["INSTNM"], "override"
            else:
                tier, match, how = "Other academic", ovr[label], "override:not-in-carnegie-file"
        else:
            ex = car[car["n"] == n]
            if len(ex):
                tier, match, how = ex.iloc[0]["tier"], ex.iloc[0]["INSTNM"], "exact"
        if tier is None:
            if any(label.startswith(u) or u in label for u in r1u):
                tier, how = "R1", "r1-unit"
            elif any(u in label for u in O["foreign"]):
                tier, how = "Foreign", "foreign-list"
            elif any(label == u or label.startswith(u) for u in O["unknown"]):
                tier, how = "Unknown", "unknown-list"
            elif any(u in label for u in O["other_academic_extra"]["patterns"]):
                tier, how = "Other academic", "academic-list"
            elif acad.search(full.lower()) and not notacad.search(full.lower()):
                tier, how = "Other academic", "keyword"
            else:
                tier, how = "Non-academic", "keyword"
            # fuzzy suggestion for the human reviewer only
            b = process.extractOne(n, car["n"].tolist(), scorer=fuzz.token_sort_ratio)
            if b and b[1] >= 85:
                report.append(f"REVIEW  {label!r:70} -> {tier:15} (fuzzy {b[1]:.0f}: {car.iloc[b[2]]['INSTNM']!r})")
        rows.append((tier, match, how))
    xd[["tier", "carnegie_instnm", "match_method"]] = pd.DataFrame(rows, index=xd.index)
    xd["cohort"] = xd["tier"].map(lambda t: t if t in ("R1", "R2", "RCU", "Other academic", "Non-academic") else "Foreign/Unknown")
    return xd


def attach_ipeds(xd, car, hd):
    xd = xd.merge(car[["INSTNM", "UNITID"]].rename(columns={"INSTNM": "carnegie_instnm"}), on="carnegie_instnm", how="left")
    # institutions outside the Carnegie research file: exact normalized-name match into IPEDS
    m = xd["UNITID"].isna() & (xd["cohort"] == "Other academic")
    hits = 0
    for i, r in xd[m].iterrows():
        ex = hd[hd["n"] == r["n"]]
        if len(ex):
            xd.loc[i, "UNITID"] = ex.iloc[0]["UNITID"]
            hits += 1
    report.append(f"IPEDS name-match for non-Carnegie academic institutions: {hits} of {m.sum()}")
    xd = xd.merge(hd[["UNITID", "HBCU", "TRIBAL", "C21BASIC", "CONTROL", "STABBR"]], on="UNITID", how="left")
    xd["msi"] = xd.apply(lambda r: "HBCU" if r.HBCU == 1 else "TCU" if r.TRIBAL == 1 else "", axis=1)
    return xd


def classify_projects(xd, car):
    raw = json.load(open(RAW / "all_projects.json"))
    df = pd.json_normalize(raw)
    df["credits"] = [sum((res.get("allocation") or 0) for res in (p.get("resources") or []) if res.get("resourceName") == "ACCESS Credits") for p in raw]
    df = df.drop(columns=[c for c in ("resources", "publications", "abstract") if c in df.columns])
    xmap = dict(zip(xd["n"], xd["cohort"]))
    cmap = dict(zip(car["n"], car["tier"]))
    r1u = set(O["projects_r1_units"]["names"])
    nonacad = re.compile(O["projects_nonacademic_regex"])
    acad = re.compile(O["projects_academic_regex"])
    inst = df["piInstitution"].value_counts().rename_axis("piInstitution").reset_index(name="projects")
    inst["n"] = inst["piInstitution"].map(norm)

    def cls(name, n):
        if n in xmap:
            return xmap[n], "xdmod"          # institution has run jobs
        if n in cmap:
            return cmap[n], "carnegie"       # in Carnegie file, never ran a job
        if name in r1u:
            return "R1", "manual"
        b = process.extractOne(n, list(cmap), scorer=fuzz.token_sort_ratio)
        if b and b[1] >= 93:
            return cmap[b[0]], f"carnegie-fuzzy{b[1]:.0f}"
        if nonacad.search(n) and not acad.search(n):
            return "Non-academic", "keyword"
        if acad.search(n):
            return "Other academic", "keyword"
        return "Non-academic", "keyword-default"

    inst[["cohort", "match_method"]] = pd.DataFrame([cls(a, b) for a, b in zip(inst["piInstitution"], inst["n"])], index=inst.index)
    inst["ever_used"] = inst["match_method"] == "xdmod"
    df = df.merge(inst[["piInstitution", "cohort"]], on="piInstitution", how="left")
    return df, inst


def main():
    car = load_carnegie()
    hd = load_ipeds()
    xd = pd.read_csv(RAW / "xdmod_by_pi_institution.csv")
    xd["full"] = xd["pi_institution"].str.split(" - ", n=1).str[-1].str.strip()
    xd["n"] = xd["full"].map(norm)
    xd = classify_xdmod(xd, car)
    xd = attach_ipeds(xd, car, hd)

    matched = set(xd["carnegie_instnm"].dropna())
    un = car[(car.tier == "R1") & ~car["INSTNM"].isin(matched)]
    report.insert(0, f"R1 institutions in Carnegie file with no XDMoD match: {len(un)} -> {un['INSTNM'].tolist()}")
    report.insert(0, xd["match_method"].value_counts().to_string())
    report.insert(0, f"XDMoD PI institutions: {len(xd)}; total ACE {xd.total_ace.sum():,.2f}")

    cols = ["pi_institution", "cohort", "tier", "carnegie_instnm", "match_method", "UNITID", "msi", "C21BASIC", "STABBR",
            "total_ace", "total_cpu_hours", "total_node_hours", "job_count", "active_pi_count", "active_allocation_count", "active_person_count"]
    xd[cols].sort_values("total_ace", ascending=False).to_csv(DERIVED / "institutions.csv", index=False)

    projects, inst = classify_projects(xd, car)
    projects.to_csv(DERIVED / "projects.csv", index=False)
    inst.drop(columns=["n"]).to_csv(DERIVED / "project_institutions.csv", index=False)
    report.append(f"Current projects: {len(projects)}; awarded institutions: {len(inst)}; never-used institutions: {(~inst.ever_used).sum()}")

    cohorts = {"nonR1": xd[xd.cohort.isin(NONR1)]["pi_institution"].tolist(),
               "R1": xd[xd.cohort == "R1"]["pi_institution"].tolist()}
    json.dump(cohorts, open(DERIVED / "cohorts.json", "w"), indent=0)
    (DERIVED / "classify_report.txt").write_text("\n".join(report) + "\n")
    print("\n".join(report[:3]))
    print(xd.groupby("cohort").agg(n=("pi_institution", "count"), ace=("total_ace", "sum")).assign(share=lambda d: (d.ace / d.ace.sum() * 100).round(2)))


if __name__ == "__main__":
    main()
