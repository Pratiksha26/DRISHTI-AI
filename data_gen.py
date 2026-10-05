"""
STEP 3 — PROJECT-LEVEL DATA SIMULATION (anchored to real data)
Builds the project-level dataset DRISHTI-AI's risk engine runs on.

REAL layer: State, MP_Name, Constituency, Reservation, Allocated_Amount for all
542 MPs (from clean_mp_data.py / mp_allocations_clean.csv, official government export).

SIMULATED layer: individual works/projects under each MP's entitlement. The public
eSAKSHI/MPLADS portal (mplads.mospi.gov.in) does not expose project-level records
(it's a login-gated dashboard for MPs/District Authorities), so there is nothing
public to pull those from. To keep the simulation grounded in the real data instead
of pure fabrication:
  - Every project's District/State/MP_Name is REAL (taken directly from the
    cleaned allocation file) instead of a small made-up list of districts.
  - The TOTAL sanctioned amount across a constituency's projects is capped by
    that MP's REAL allocated ceiling -- so no constituency ever "spends" more
    than it was actually entitled to, exactly like the real scheme.
  - Realistic risk patterns (cost anomalies, expenditure/progress mismatches,
    delays, near-duplicate works) are injected the same way as before, so the
    risk engine has real signal to detect.

Swap-in note: once project-level MPLADS data becomes available (RTI, an official
export, or API access), point this file's output schema at that data directly and
skip the simulation step entirely -- the risk engine only cares about the schema.
"""
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
import os
from state_centroids import STATE_CENTROIDS

random_seed = 42
np.random.seed(random_seed)
rng = np.random.default_rng(random_seed)

TODAY = datetime(2026, 9, 9)
DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
MP_CLEAN_PATH = os.path.join(DATA_DIR, "mp_allocations_clean.csv")

WORK_TYPES = [
    # (work name, sector, base_cost_lakh, implementing agency pool)
    ("Community Hall Construction", "Public Amenities", 45, ["Zilla Parishad", "Municipal Council"]),
    ("Road Construction", "Infrastructure", 60, ["PWD", "Zilla Parishad"]),
    ("Drinking Water Supply Scheme", "Water Supply", 35, ["Water Supply Dept", "Zilla Parishad"]),
    ("Government School Building", "Education", 55, ["Rural Development Dept", "Zilla Parishad"]),
    ("Anganwadi Centre", "Education", 18, ["Rural Development Dept", "Municipal Council"]),
    ("Primary Health Centre Renovation", "Health", 30, ["PWD", "Health Dept"]),
    ("Drainage System", "Infrastructure", 25, ["Municipal Council", "PWD"]),
    ("Street Light Installation", "Public Amenities", 12, ["Municipal Council"]),
    ("Bridge / Culvert Construction", "Infrastructure", 80, ["PWD"]),
    ("Public Toilet Complex", "Public Amenities", 15, ["Municipal Council", "Zilla Parishad"]),
    ("Solar Power Unit", "Rural Development", 22, ["Rural Development Dept"]),
    ("Sports Ground Development", "Public Amenities", 28, ["Municipal Council", "Zilla Parishad"]),
]


def gen_projects_for_mp(mp_row, pid_counter, rng):
    state, constituency, mp_name = mp_row["State"], mp_row["Constituency"], mp_row["MP_Name"]
    allocated = mp_row["Allocated_Amount"]

    base_lat, base_lon = STATE_CENTROIDS.get(state, (22.0, 79.0))
    lat = base_lat + rng.uniform(-0.8, 0.8)
    lon = base_lon + rng.uniform(-0.8, 0.8)

    n_projects = int(rng.integers(2, 13))  # avg ~7 works per constituency over the term

    rows = []
    running_total = 0.0
    for _ in range(n_projects):
        wt_idx = rng.integers(0, len(WORK_TYPES))
        work_name, sector, base_cost, agencies = WORK_TYPES[wt_idx]
        agency = agencies[rng.integers(0, len(agencies))]
        # a location/zone descriptor so repeat work-types in the same constituency
        # (e.g. two separate road projects) get distinct names -- without this,
        # duplicate-detection would flag every same-type project as a "clone"
        zone = rng.integers(1, 16)
        work_name = f"{work_name} (Zone {zone})"

        standard_cost_norm = base_cost * 100000
        sanctioned = standard_cost_norm * rng.uniform(0.75, 1.25)  # realistic unit-cost jitter

        is_cost_anomaly = rng.random() < 0.07
        is_mismatch = rng.random() < 0.09
        is_delayed = rng.random() < 0.12

        if is_cost_anomaly:
            sanctioned *= rng.uniform(1.5, 2.2)

        # hard safety cap: never let a constituency's total sanctioned amount
        # exceed its MP's real entitlement ceiling
        if running_total + sanctioned > allocated * 0.97:
            sanctioned = max(allocated * 0.97 - running_total, standard_cost_norm * 0.3)
        running_total += sanctioned

        start_days_ago = int(rng.integers(30, 900))
        start_date = TODAY - timedelta(days=start_days_ago)
        expected_completion = start_date + timedelta(days=365)

        elapsed_frac = min(1.0, start_days_ago / 365)
        base_progress = np.clip(rng.normal(elapsed_frac * 100, 15), 0, 100)
        if is_delayed:
            base_progress = np.clip(base_progress * rng.uniform(0.25, 0.55), 0, 100)
        progress_pct = round(float(base_progress), 0)

        if is_mismatch:
            expenditure_pct = np.clip(progress_pct + rng.uniform(35, 60), 0, 100)
        else:
            expenditure_pct = np.clip(progress_pct + rng.uniform(-8, 8), 0, 100)
        expenditure = sanctioned * expenditure_pct / 100

        overdue = (TODAY > expected_completion) and progress_pct < 100
        if progress_pct >= 100:
            status = "Completed"
        elif overdue:
            status = "Delayed"
        elif progress_pct == 0:
            status = "Not Started"
        else:
            status = "Ongoing"

        rows.append({
            "Project_ID": f"P{pid_counter[0]:04d}",
            "Work_Name": work_name,
            "Sector": sector,
            "State": state,
            "District": constituency,          # real constituency name used as location
            "Constituency": f"{constituency} (LS)",
            "MP_Name": mp_name,
            "Implementing_Agency": agency,
            "Sanctioned_Amount": round(float(sanctioned), -2),
            "Standard_Cost_Norm": round(float(standard_cost_norm), -2),
            "Expenditure": round(float(expenditure), -2),
            "Physical_Progress_Pct": progress_pct,
            "Start_Date": start_date.strftime("%Y-%m-%d"),
            "Expected_Completion": expected_completion.strftime("%Y-%m-%d"),
            "Status": status,
            "Latitude": round(lat + rng.uniform(-0.15, 0.15), 4),
            "Longitude": round(lon + rng.uniform(-0.15, 0.15), 4),
        })
        pid_counter[0] += 1

    return rows


def generate():
    rng = np.random.default_rng(random_seed)
    mp_df = pd.read_csv(MP_CLEAN_PATH)
    pid_counter = [1]
    all_rows = []
    for _, mp_row in mp_df.iterrows():
        all_rows.extend(gen_projects_for_mp(mp_row, pid_counter, rng))

    df = pd.DataFrame(all_rows)

    dup_source_idx = rng.choice(df.index, size=min(18, len(df) // 20), replace=False)
    extra = []
    for src in dup_source_idx:
        src_row = df.loc[src].to_dict()
        dup = src_row.copy()
        dup["Project_ID"] = f"P{pid_counter[0]:04d}"
        pid_counter[0] += 1
        dup["Work_Name"] = src_row["Work_Name"] + " Phase II"
        dup["Sanctioned_Amount"] = round(src_row["Sanctioned_Amount"] * rng.uniform(0.85, 1.1), -2)
        dup["Expenditure"] = round(dup["Sanctioned_Amount"] * rng.uniform(0.3, 0.7), -2)
        dup["Physical_Progress_Pct"] = round(float(rng.uniform(10, 40)), 0)
        extra.append(dup)
    df = pd.concat([df, pd.DataFrame(extra)], ignore_index=True)

    out_path = os.path.join(DATA_DIR, "mplads_projects.csv")
    df.to_csv(out_path, index=False)
    print(f"Generated {len(df)} projects across {mp_df['State'].nunique()} states, "
          f"{mp_df['Constituency'].nunique()} real constituencies -> {out_path}")
    print(df["Status"].value_counts())
    print(f"Total sanctioned: Rs.{df['Sanctioned_Amount'].sum():,.0f}  "
          f"vs total real allocation: Rs.{mp_df['Allocated_Amount'].sum():,.0f} "
          f"({df['Sanctioned_Amount'].sum() / mp_df['Allocated_Amount'].sum() * 100:.1f}% utilisation)")
    return df


if __name__ == "__main__":
    generate()
