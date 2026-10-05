"""
DRISHTI-AI risk engine.

Combines three signal sources into one explainable 0-100 risk score per project:
  1. Rule-based checks   -> cost anomaly, expenditure/progress mismatch, delay
  2. Unsupervised ML     -> Isolation Forest over numeric features (catches
                             anomalies rules don't explicitly cover)
  3. NLP text similarity -> flags likely duplicate/split works in the same district

Each project also gets a list of human-readable "reasons" so the score is
explainable, not a black box -- this is what powers the "Why is this project
risky?" panel in Project Details.
"""
import numpy as np
import pandas as pd
from datetime import datetime
from sklearn.ensemble import IsolationForest
from rapidfuzz import fuzz

TODAY = datetime(2026, 9, 9)


def compute_derived_fields(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["Start_Date"] = pd.to_datetime(df["Start_Date"])
    df["Expected_Completion"] = pd.to_datetime(df["Expected_Completion"])
    df["Expenditure_Pct"] = (df["Expenditure"] / df["Sanctioned_Amount"] * 100).round(1)
    df["Days_Overdue"] = (TODAY - df["Expected_Completion"]).dt.days.clip(lower=0)
    df.loc[df["Status"] == "Completed", "Days_Overdue"] = 0
    return df


def rule_based_flags(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    reasons = [[] for _ in range(len(df))]
    rule_score = np.zeros(len(df))

    # 1. Cost anomaly: sanctioned amount vs standard cost norm for this work type
    #    (a fixed schedule-of-rates baseline per work type, not a peer-median --
    #    peer medians get skewed by how each MP's entitlement happens to be split
    #    across projects, which isn't a real anomaly signal)
    cost_ratio = df["Sanctioned_Amount"] / df["Standard_Cost_Norm"]
    for i, ratio in enumerate(cost_ratio):
        if ratio > 1.45:
            pts = min(45, (ratio - 1.45) * 60)
            rule_score[i] += pts
            reasons[i].append(f"Cost anomaly \u2014 cost is {ratio:.1f}x higher than the standard cost norm for this work type")

    # 2. Expenditure vs progress mismatch
    mismatch = df["Expenditure_Pct"] - df["Physical_Progress_Pct"]
    for i, m in enumerate(mismatch):
        if m > 15:
            pts = min(45, (m - 15) * 1.1)
            rule_score[i] += pts
            reasons[i].append(
                f"Expenditure vs progress mismatch \u2014 {df['Expenditure_Pct'].iloc[i]:.0f}% money spent "
                f"but only {df['Physical_Progress_Pct'].iloc[i]:.0f}% progress"
            )

    # 3. Delay
    for i, d in enumerate(df["Days_Overdue"]):
        if d > 0:
            pts = min(35, 8 + d / 12)
            rule_score[i] += pts
            months = round(d / 30)
            reasons[i].append(f"Delay \u2014 project is {months} month(s) beyond expected completion")

    df["rule_score"] = rule_score
    df["reasons"] = reasons
    return df


def duplicate_detection(df: pd.DataFrame, threshold: int = 90) -> pd.DataFrame:
    """Flags likely duplicate/split works: same district, near-identical work
    name, AND similar cost AND overlapping start date. Name similarity alone
    isn't enough here -- a constituency legitimately gets several projects of
    the same work TYPE (e.g. two separate road works), so we also require the
    cost and timing to line up before calling it a suspected duplicate."""
    df = df.copy()
    df["Start_Date_dt"] = pd.to_datetime(df["Start_Date"])
    dup_flag = [False] * len(df)
    dup_score = np.zeros(len(df))

    for district, group in df.groupby("District"):
        idxs = group.index.tolist()
        names = group["Work_Name"].tolist()
        costs = group["Sanctioned_Amount"].tolist()
        dates = group["Start_Date_dt"].tolist()
        for a in range(len(idxs)):
            for b in range(a + 1, len(idxs)):
                name_score = fuzz.token_sort_ratio(names[a], names[b])
                cost_ratio = min(costs[a], costs[b]) / max(costs[a], costs[b]) if max(costs[a], costs[b]) > 0 else 0
                date_gap = abs((dates[a] - dates[b]).days)
                if name_score >= threshold and cost_ratio >= 0.75 and date_gap <= 45:
                    dup_flag[df.index.get_loc(idxs[a])] = True
                    dup_flag[df.index.get_loc(idxs[b])] = True
                    dup_score[df.index.get_loc(idxs[a])] = max(dup_score[df.index.get_loc(idxs[a])], 20)
                    dup_score[df.index.get_loc(idxs[b])] = max(dup_score[df.index.get_loc(idxs[b])], 20)

    df["duplicate_flag"] = dup_flag
    df["duplicate_score"] = dup_score
    df = df.drop(columns=["Start_Date_dt"])
    for i in df.index:
        if df.loc[i, "duplicate_flag"]:
            df.loc[i, "reasons"].append("Similar project detected \u2014 similar work found in same district")
    return df


def agency_pattern_flags(df: pd.DataFrame, risk_col: str = "interim_score") -> pd.DataFrame:
    df = df.copy()
    agency_avg = df.groupby("Implementing_Agency")[risk_col].transform("mean")
    for i in df.index:
        if agency_avg.loc[i] > 45:
            df.loc[i, "reasons"].append(
                f"Agency pattern \u2014 {df.loc[i, 'Implementing_Agency']} flagged on other high-risk projects"
            )
            df.loc[i, "rule_score"] = min(100, df.loc[i, "rule_score"] + 8)
    return df


def isolation_forest_score(df: pd.DataFrame) -> np.ndarray:
    features = df[["Sanctioned_Amount", "Expenditure_Pct", "Physical_Progress_Pct", "Days_Overdue"]].copy()
    features = (features - features.mean()) / (features.std() + 1e-9)
    model = IsolationForest(n_estimators=200, contamination=0.15, random_state=42)
    model.fit(features)
    raw = -model.score_samples(features)  # higher = more anomalous
    # scale to 0-100
    scaled = (raw - raw.min()) / (raw.max() - raw.min() + 1e-9) * 100
    return scaled


def risk_level(score: float) -> str:
    if score >= 38:
        return "Critical"
    if score >= 31:
        return "High"
    if score >= 13:
        return "Medium"
    return "Low"


def run_pipeline(df: pd.DataFrame) -> pd.DataFrame:
    df = compute_derived_fields(df)
    df = rule_based_flags(df)
    df["interim_score"] = df["rule_score"].clip(0, 100)
    df = agency_pattern_flags(df, risk_col="interim_score")
    df = duplicate_detection(df)

    ml_score = isolation_forest_score(df)
    df["ml_score"] = ml_score

    # Blend: rule-based checks carry the most weight (explainable), duplicate
    # detection adds a smaller boost, ML anomaly score catches what rules miss
    combined = 0.68 * df["rule_score"] + 0.12 * df["duplicate_score"] + 0.20 * df["ml_score"]
    df["Risk_Score"] = combined.clip(0, 100).round(0).astype(int)
    df["Risk_Level"] = df["Risk_Score"].apply(risk_level)
    df["Reasons"] = df["reasons"].apply(lambda r: r if r else ["No significant risk indicators detected"])

    # explicit flags for dashboard KPI cards
    df["Cost_Anomaly_Flag"] = df["reasons"].apply(lambda r: any("Cost anomaly" in x for x in r))
    df["Duplicate_Flag"] = df["duplicate_flag"]

    df = df.drop(columns=["rule_score", "reasons", "interim_score", "ml_score", "duplicate_score"])
    return df


if __name__ == "__main__":
    raw = pd.read_csv("data/mplads_projects.csv")
    scored = run_pipeline(raw)
    scored.to_csv("data/mplads_projects_scored.csv", index=False)
    print(scored["Risk_Level"].value_counts(normalize=True).round(3) * 100)
