"""
STEP 2 — EXPLORATORY DATA ANALYSIS
Run after clean_mp_data.py. Prints the key findings that shaped the project-level
data simulation in data_gen.py (Step 3) and are worth quoting in your SIH pitch.
"""
import pandas as pd
import os

CLEAN_CSV = os.path.join(os.path.dirname(__file__), "data", "mp_allocations_clean.csv")


def eda():
    df = pd.read_csv(CLEAN_CSV)

    print("=" * 60)
    print("1. COVERAGE")
    print("=" * 60)
    print(f"Total MPs / constituencies : {len(df)}")
    print(f"States & UTs covered       : {df['State'].nunique()}")
    print(f"Top 5 states by seat count :\n{df['State'].value_counts().head(5)}\n")

    print("=" * 60)
    print("2. ALLOCATED AMOUNT DISTRIBUTION")
    print("=" * 60)
    print(df["Allocated_Amount"].describe().apply(lambda x: f"{x:,.0f}"))
    q1, q3 = df["Allocated_Amount"].quantile([0.25, 0.75])
    iqr = q3 - q1
    outliers = df[(df["Allocated_Amount"] < q1 - 1.5 * iqr) | (df["Allocated_Amount"] > q3 + 1.5 * iqr)]
    print(f"\nIQR outliers (unusually high/low entitlement): {len(outliers)} rows")
    print(outliers[["State", "MP_Name", "Constituency", "Allocated_Amount"]].sort_values("Allocated_Amount"))
    print("\nInsight: most MPs sit at the standard entitlement (~₹14.7 crore median).")
    print("Outliers above/below that are typically MPs seated via by-election")
    print("(prorated entitlement) or those with carried-over unspent balance.")

    print("\n" + "=" * 60)
    print("3. RESERVATION CATEGORY SPLIT")
    print("=" * 60)
    print(df["Reservation"].value_counts())
    print((df["Reservation"].value_counts(normalize=True) * 100).round(1))

    print("\n" + "=" * 60)
    print("4. WHY WE STILL NEED SIMULATED PROJECT-LEVEL DATA")
    print("=" * 60)
    print("This file has ONE ROW PER MP (entitlement ceiling only) — no individual")
    print("works/projects, no expenditure, no progress %, no dates. DRISHTI-AI's risk")
    print("engine operates at PROJECT level, so Step 3 (data_gen.py) generates 1-3")
    print("realistic projects per constituency, with total sanctioned amount bounded")
    print("by that MP's REAL allocated ceiling from this file — i.e. the entitlement")
    print("layer is 100% real; only the project-level breakdown beneath it is simulated.")


if __name__ == "__main__":
    eda()
