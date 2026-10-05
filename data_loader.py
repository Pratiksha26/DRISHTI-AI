import pandas as pd
import streamlit as st
import os
from risk_engine import run_pipeline

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
RAW_PATH = os.path.join(DATA_DIR, "mplads_projects.csv")
INVESTIGATIONS_PATH = os.path.join(DATA_DIR, "investigations.csv")


@st.cache_data(show_spinner="Scoring projects with DRISHTI-AI risk engine...")
def load_scored_data():
    raw = pd.read_csv(RAW_PATH)
    scored = run_pipeline(raw)
    return scored


def load_investigations():
    if os.path.exists(INVESTIGATIONS_PATH):
        return pd.read_csv(INVESTIGATIONS_PATH)
    return pd.DataFrame(columns=[
        "Project_ID", "Priority", "Assigned_To", "Remarks", "Created_On", "Status"
    ])


def save_investigation(row: dict):
    df = load_investigations()
    df = pd.concat([df, pd.DataFrame([row])], ignore_index=True)
    df.to_csv(INVESTIGATIONS_PATH, index=False)
    return df
