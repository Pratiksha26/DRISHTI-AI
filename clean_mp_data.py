"""
STEP 1 — DATA CLEANING
Cleans the real "Allocated Limit for Hon'ble MPs" dataset (source: official
MPLADS/eSAKSHI allocation export, provided as data/raw/Allocated_Limit_for_Honble_MPs.xlsx).

This is REAL government data: 542 valid rows covering 36 states/UTs, giving each
sitting MP's name, constituency, state, and total MPLADS fund entitlement.

Raw issues found and fixed (run this file to see the report):
  1. Two header rows (a title row, then the real header) -> skiprows=1
  2. A "Grand Total" footer row (NaN in every column except the amount) -> dropped
  3. Inconsistent name casing (ALL CAPS mixed with Title Case) -> standardized to Title Case
  4. Constituency names carry embedded reservation tags, e.g. "NANDURBAR(ST)",
     "PALAMU(SC)" -> tag extracted into its own Reservation column (GEN/SC/ST)
  5. Some constituency names carry a state-disambiguation suffix, e.g.
     "AURANGABAD_BR" (Bihar) vs "AURANGABAD" (Maharashtra) -> suffix stripped for
     display, but State + Constituency kept together as a unique join key
  6. Allocated amount is a float with paise in some rows -> rounded to nearest rupee
  7. Whitespace/double-space cleanup on all text columns
  8. Duplicate-key check on (State, Constituency) -> none found, but the guard stays
     in for future runs
"""
import pandas as pd
import re
import os

RAW_XLSX = os.path.join(os.path.dirname(__file__), "data", "raw", "Allocated_Limit_for_Honble_MPs.xlsx")
OUT_CSV = os.path.join(os.path.dirname(__file__), "data", "mp_allocations_clean.csv")


def _read_raw():
    """openpyxl chokes on this workbook's stylesheet (a known style-parsing bug
    with certain Excel exports), so convert via LibreOffice headless first if a
    direct read fails, falling back to a plain read otherwise."""
    try:
        return pd.read_excel(RAW_XLSX, skiprows=1, engine="openpyxl")
    except Exception:
        import subprocess
        import tempfile
        tmp_csv = os.path.join(tempfile.gettempdir(), "mp_alloc_raw.csv")
        subprocess.run([
            "soffice", "--headless", "--convert-to", "csv",
            "--outdir", tempfile.gettempdir(), RAW_XLSX,
        ], check=True, capture_output=True)
        converted = os.path.join(
            tempfile.gettempdir(),
            os.path.splitext(os.path.basename(RAW_XLSX))[0] + ".csv",
        )
        return pd.read_csv(converted, skiprows=1)


def clean():
    df = _read_raw()
    before = len(df)

    df = df.dropna(subset=[df.columns[1], df.columns[2], df.columns[3]])
    df.columns = ["Sr_No", "State", "MP_Name", "Constituency_Raw", "Allocated_Amount"]

    for col in ["State", "MP_Name", "Constituency_Raw"]:
        df[col] = df[col].astype(str).str.strip().str.replace(r"\s+", " ", regex=True)

    df["MP_Name"] = df["MP_Name"].str.title()
    df["State"] = df["State"].str.title()

    def split_reservation(name):
        m = re.match(r"^(.*?)\s*\(([A-Z]{2,3})\)\s*$", name)
        if m:
            return m.group(1).strip(), m.group(2)
        return name.strip(), "GEN"

    parts = df["Constituency_Raw"].apply(split_reservation)
    df["Constituency"] = parts.apply(lambda t: t[0]).str.title()
    df["Reservation"] = parts.apply(lambda t: t[1])
    df["Constituency"] = df["Constituency"].str.replace(r"_[A-Z]{2}$", "", regex=True)
    df["Constituency_Key"] = df["State"] + " | " + df["Constituency"]

    df["Allocated_Amount"] = pd.to_numeric(df["Allocated_Amount"], errors="coerce").round(0)
    df = df.dropna(subset=["Allocated_Amount"])
    dupes = df["Constituency_Key"].duplicated().sum()
    df = df.drop_duplicates(subset=["Constituency_Key"], keep="first")

    df = df[["State", "MP_Name", "Constituency", "Reservation", "Constituency_Key", "Allocated_Amount"]]
    df = df.reset_index(drop=True)

    print(f"Rows before cleaning : {before}")
    print(f"Rows after cleaning  : {len(df)}  (removed footer/null rows, {dupes} duplicate keys)")
    print(f"States covered       : {df['State'].nunique()}")
    print(f"Reservation tags     : {df['Reservation'].value_counts().to_dict()}")
    print(f"Allocated amount (₹) : min={df['Allocated_Amount'].min():,.0f}  "
          f"median={df['Allocated_Amount'].median():,.0f}  max={df['Allocated_Amount'].max():,.0f}")

    df.to_csv(OUT_CSV, index=False)
    print(f"Saved -> {OUT_CSV}")
    return df


if __name__ == "__main__":
    clean()
