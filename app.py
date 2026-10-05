import ast
import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
import os

from data_loader import load_scored_data, load_investigations, save_investigation

TODAY = datetime(2026, 9, 9)

NAVY = "#1B2A4A"
BLUE = "#0077B6"
SAFFRON = "#FF9933"
GREEN = "#138808"
RED = "#C0392B"
AMBER = "#E67E22"

RISK_COLORS = {"Low": GREEN, "Medium": SAFFRON, "High": AMBER, "Critical": RED}

# Rough bounding box for mainland India + islands, used to sanity-check lat/lon
# before plotting on the map. Anything outside this is almost certainly bad
# data (e.g. an unset lat/lon defaulting to 0.0, which plots near Gabon/Africa).
INDIA_LAT_RANGE = (6.0, 38.0)
INDIA_LON_RANGE = (68.0, 98.0)

st.set_page_config(page_title="DRISHTI-AI | MPLADS Risk Intelligence", page_icon="👁️", layout="wide")

# ---------------------------------------------------------------- styling ---
st.markdown(f"""
<style>
    .block-container {{ padding-top: 1.5rem; padding-bottom: 2rem; }}

    section[data-testid="stSidebar"] {{ background-color: {NAVY}; }}
    section[data-testid="stSidebar"] * {{ color: #FFFFFF !important; }}
    section[data-testid="stSidebar"] .stRadio > label {{ color: white; }}
    div[role="radiogroup"] > label {{
        background: rgba(255,255,255,0.04); border-radius: 8px; padding: 8px 10px; margin-bottom: 4px;
        transition: background 0.15s ease;
    }}
    div[role="radiogroup"] > label:hover {{ background: rgba(255,255,255,0.12); }}

    /* ---- KPI cards ---- */
    .kpi-card {{
        border-radius: 14px; padding: 18px 18px; display: flex; align-items: center; gap: 14px;
        background: #FFFFFF;
        border: 1px solid #EEF0F4;
        box-shadow: 0 1px 3px rgba(16,24,40,0.06), 0 1px 2px rgba(16,24,40,0.04);
        transition: transform 0.15s ease, box-shadow 0.15s ease;
    }}
    .kpi-card:hover {{
        transform: translateY(-2px);
        box-shadow: 0 6px 16px rgba(16,24,40,0.10);
    }}
    .kpi-icon {{
        width: 44px; height: 44px; border-radius: 11px; display: flex; align-items: center;
        justify-content: center; font-size: 20px; flex-shrink: 0;
    }}
    .kpi-label {{ font-size: 12.5px; font-weight: 600; opacity: 0.65; margin-bottom: 3px; letter-spacing: 0.2px; }}
    .kpi-value {{ font-size: 26px; font-weight: 800; line-height: 1.1; color: {NAVY}; }}

    /* ---- Hero banner ---- */
    .hero-banner {{
        position: relative; border-radius: 16px; overflow: hidden; margin-bottom: 1.4rem;
        box-shadow: 0 4px 18px rgba(16,24,40,0.14);
    }}
    .hero-banner::after {{
        content: ""; position: absolute; inset: 0;
        background: linear-gradient(90deg, rgba(15,23,50,0.88) 0%, rgba(15,23,50,0.55) 45%, rgba(15,23,50,0.15) 75%);
    }}
    .hero-text {{
        position: absolute; top: 0; left: 0; height: 100%; z-index: 2; display: flex;
        flex-direction: column; justify-content: center; padding: 0 2.5rem; max-width: 60%;
    }}
    .hero-eyebrow {{
        color: {SAFFRON}; font-size: 12.5px; font-weight: 700; letter-spacing: 1.5px;
        text-transform: uppercase; margin-bottom: 8px;
    }}
    .hero-title {{
        color: white; font-size: 30px; font-weight: 800; line-height: 1.25;
        text-shadow: 0 2px 8px rgba(0,0,0,0.25);
    }}
    .hero-subtitle {{
        color: #CADCFC; font-size: 14.5px; margin-top: 8px; font-weight: 400;
    }}

    .risk-badge {{
        display: inline-block; padding: 3px 12px; border-radius: 6px; color: white;
        font-weight: 600; font-size: 12.5px;
    }}
    .reason-card {{
        background: #FBE3E1; border-left: 4px solid {RED}; border-radius: 6px;
        padding: 10px 14px; margin-bottom: 8px; font-size: 14px;
    }}

    h2, h3 {{ color: {NAVY}; }}
</style>
""", unsafe_allow_html=True)


# ---------------------------------------------------------------- cached data loaders ---
# BUG/IMPROVEMENT: previously load_scored_data()/load_investigations() were called
# directly, which means Streamlit re-loaded and re-scored the full dataset on
# every single widget interaction (every rerun). Wrapping them in @st.cache_data
# means the expensive load only happens once per session (until the underlying
# data changes), which matters a lot on a 3700+ row dataset.
@st.cache_data
def get_scored_data():
    return load_scored_data()


@st.cache_data(ttl=5)  # short TTL so newly-submitted investigations still show up
def get_investigations():
    return load_investigations()


def parse_reasons(value):
    """Safely parse the Reasons column.

    BUG FIX: the original code used eval(row["Reasons"]) to turn the stored
    string back into a list. eval() will execute arbitrary Python code, which
    is unsafe even if you currently trust the data source. ast.literal_eval
    only parses Python literals (lists, strings, numbers, etc.) and will raise
    instead of running anything unexpected.
    """
    if isinstance(value, str):
        try:
            return ast.literal_eval(value)
        except (ValueError, SyntaxError):
            return [value]
    return value


df = get_scored_data()

# ---------------------------------------------------------------- sidebar ---
st.sidebar.markdown(
    f"<div style='display:flex;align-items:center;gap:10px;margin-bottom:1.2rem;'>"
    f"<span style='font-size:28px;'>👁️</span>"
    f"<span style='font-size:20px;font-weight:800;'>DRISHTI-AI</span></div>",
    unsafe_allow_html=True,
)

PAGES = ["🏠 Dashboard", "📁 All Projects", "🔍 Risk Analysis", "🗺️ Map View",
         "📌 Project Details", "🕵️ Investigation", "📊 Reports", "ℹ️ About"]
page_choice = st.sidebar.radio("Navigate", PAGES, label_visibility="collapsed")
page = page_choice.split(" ", 1)[1]  # strip emoji for routing logic below

st.sidebar.markdown("---")
st.sidebar.caption("District Officer")
st.sidebar.caption("MPLADS Risk Intelligence Platform")


def risk_badge(level):
    return f"<span class='risk-badge' style='background:{RISK_COLORS[level]}'>{level}</span>"


def money(x):
    return f"₹{x:,.0f}"


def recommended_action(reasons):
    mapping = [
        ("Expenditure vs progress mismatch", "Conduct field verification and verify expenditure/progress documentation."),
        ("Cost anomaly", "Verify cost estimates against the standard schedule of rates for this work type."),
        ("Delay", "Request an updated project timeline and cause-of-delay report from the implementing agency."),
        ("Similar project detected", "Cross-check with the implementing agency to confirm this is not a duplicate or split work."),
        ("Agency pattern", "Flag the implementing agency for a broader portfolio audit."),
    ]
    for key, action in mapping:
        if any(key in r for r in reasons):
            return action
    return "Continue routine monitoring; no urgent action required."


# =================================================================== DASHBOARD
if page == "Dashboard":
    import base64
    banner_path = os.path.join(os.path.dirname(__file__), "assets", "hero_banner.png")
    with open(banner_path, "rb") as f:
        banner_b64 = base64.b64encode(f.read()).decode()
    st.markdown(
        f"<div class='hero-banner'>"
        f"<img src='data:image/png;base64,{banner_b64}' style='width:100%;display:block;height:280px;object-fit:cover;'/>"
        f"<div class='hero-text'>"
        f"<div class='hero-eyebrow'>MPLADS · SIH26102</div>"
        f"<div class='hero-title'>MPLADS Risk Intelligence Dashboard</div>"
        f"<div class='hero-subtitle'>From Data to Development with Transparency</div>"
        f"</div></div>",
        unsafe_allow_html=True,
    )

    total = len(df)
    high_risk = (df["Risk_Level"] == "High").sum()
    critical = (df["Risk_Level"] == "Critical").sum()
    delayed = (df["Status"] == "Delayed").sum()
    cost_anomalies = df["Cost_Anomaly_Flag"].sum()
    duplicates = df["Duplicate_Flag"].sum()

    kpis = [
        ("📁", "Total Projects", total, "#EAF0FF", NAVY),
        ("⚠️", "High Risk", high_risk, "#FFF1E0", "#B5570C"),
        ("❗", "Critical Risk", critical, "#FDE7E5", RED),
        ("⏱️", "Delayed Projects", delayed, "#E7F0FE", "#1D4ED8"),
        ("🧾", "Cost Anomalies", cost_anomalies, "#F1EAFD", "#6D28D9"),
        ("🔗", "Potential Duplicates", duplicates, "#E5F7EA", "#15803D"),
    ]
    cols = st.columns(6)
    for c, (icon, label, val, icon_bg, text_color) in zip(cols, kpis):
        c.markdown(
            f"<div class='kpi-card'>"
            f"<div class='kpi-icon' style='background:{icon_bg};'>{icon}</div>"
            f"<div><div class='kpi-label'>{label}</div>"
            f"<div class='kpi-value'>{val}</div></div></div>",
            unsafe_allow_html=True,
        )

    st.write("")
    st.caption(f"📍 Spanning **{df['State'].nunique()} states/UTs** and **{df['District'].nunique()} real Lok Sabha constituencies** "
               f"— entitlement data sourced from the official MPLADS allocation list.")
    c1, c2 = st.columns([1, 1.4])
    with c1:
        st.subheader("Risk Distribution")
        counts = df["Risk_Level"].value_counts().reindex(["Low", "Medium", "High", "Critical"]).fillna(0)
        fig = go.Figure(go.Pie(
            labels=counts.index, values=counts.values, hole=0.62,
            marker_colors=[RISK_COLORS[l] for l in counts.index], sort=False,
        ))
        fig.update_layout(
            showlegend=True, height=320, margin=dict(t=10, b=10, l=10, r=10),
            annotations=[dict(text=f"{total}<br>Projects", x=0.5, y=0.5, font_size=16, showarrow=False)],
        )
        st.plotly_chart(fig, use_container_width=True)

    with c2:
        st.subheader("Projects by State (Top 5)")
        state_counts = df["State"].value_counts().head(5).sort_values()
        fig = go.Figure(go.Bar(
            x=state_counts.values, y=state_counts.index, orientation="h",
            marker_color=BLUE, text=state_counts.values, textposition="outside",
        ))
        fig.update_layout(height=320, margin=dict(t=10, b=10, l=10, r=30), xaxis_title=None, yaxis_title=None)
        st.plotly_chart(fig, use_container_width=True)

    st.info(
        "ℹ️ **Data note:** Constituency, MP name, state and fund-entitlement figures are "
        "REAL, sourced from the official MPLADS allocation list for the 18th Lok Sabha "
        "(542 constituencies, 36 states/UTs). The public eSAKSHI portal doesn't expose "
        "project-level records, so individual works below each MP's real entitlement "
        "ceiling are simulated for this prototype. Risk scores indicate potential "
        "irregularities flagged for review and do **not** constitute proof of fraud."
    )

# =================================================================== ALL PROJECTS
elif page == "All Projects":
    st.title("All MPLADS Projects")
    st.caption("Search, filter and explore project details")

    f1, f2, f3, f4 = st.columns(4)
    state_f = f1.selectbox("State", ["All"] + sorted(df["State"].unique().tolist()))
    dist_options = df[df["State"] == state_f]["District"].unique() if state_f != "All" else df["District"].unique()
    dist_f = f2.selectbox("District", ["All"] + sorted(dist_options.tolist()))
    sector_f = f3.selectbox("Sector", ["All"] + sorted(df["Sector"].unique().tolist()))
    risk_f = f4.selectbox("Risk Level", ["All", "Low", "Medium", "High", "Critical"])

    search = st.text_input("🔍 Search by Project ID, Work Name, District...")

    fdf = df.copy()
    if state_f != "All":
        fdf = fdf[fdf["State"] == state_f]
    if dist_f != "All":
        fdf = fdf[fdf["District"] == dist_f]
    if sector_f != "All":
        fdf = fdf[fdf["Sector"] == sector_f]
    if risk_f != "All":
        fdf = fdf[fdf["Risk_Level"] == risk_f]
    if search:
        s = search.lower()
        fdf = fdf[
            fdf["Project_ID"].str.lower().str.contains(s)
            | fdf["Work_Name"].str.lower().str.contains(s)
            | fdf["District"].str.lower().str.contains(s)
        ]

    fdf = fdf.sort_values("Risk_Score", ascending=False)
    st.caption(f"Showing {len(fdf)} of {len(df)} projects")

    show = fdf[["Project_ID", "Work_Name", "District", "MP_Name", "Sanctioned_Amount",
                "Physical_Progress_Pct", "Risk_Score", "Risk_Level", "Status"]].rename(columns={
        "Project_ID": "Project ID", "Work_Name": "Work Name", "Sanctioned_Amount": "Sanctioned Amount",
        "MP_Name": "MP", "Physical_Progress_Pct": "Progress %", "Risk_Score": "Risk Score",
        "Risk_Level": "Risk Level", "Status": "Status",
    })

    def style_risk(v):
        return f"background-color:{RISK_COLORS.get(v, '#eee')}22; color:{RISK_COLORS.get(v,'#333')}; font-weight:600;"

    styled = show.style.map(style_risk, subset=["Risk Level"]).format({"Sanctioned Amount": "₹{:,.0f}", "Progress %": "{:.0f}%"})
    st.dataframe(styled, use_container_width=True, height=520, hide_index=True)

# =================================================================== RISK ANALYSIS
elif page == "Risk Analysis":
    st.title("Risk Analysis")
    st.caption("Portfolio-wide risk patterns detected by the model")

    c1, c2 = st.columns(2)
    with c1:
        st.subheader("Risk score distribution")
        fig = px.histogram(df, x="Risk_Score", nbins=25, color_discrete_sequence=[BLUE])
        fig.update_layout(height=320, margin=dict(t=10, b=10, l=10, r=10), bargap=0.05)
        st.plotly_chart(fig, use_container_width=True)
    with c2:
        st.subheader("Average risk score by sector")
        sec = df.groupby("Sector")["Risk_Score"].mean().sort_values()
        fig = go.Figure(go.Bar(x=sec.values, y=sec.index, orientation="h", marker_color=SAFFRON))
        fig.update_layout(height=320, margin=dict(t=10, b=10, l=10, r=30))
        st.plotly_chart(fig, use_container_width=True)

    st.subheader("Implementing agencies by average risk")
    agency = df.groupby("Implementing_Agency")["Risk_Score"].agg(["mean", "count"]).sort_values("mean", ascending=False)
    agency.columns = ["Avg Risk Score", "Project Count"]

    # BUG FIX: .background_gradient(cmap="Reds") requires matplotlib to be
    # installed, and it was NOT in requirements.txt, which is exactly why this
    # page crashed with "ImportError: matplotlib required...". Rather than
    # forcing an extra heavyweight dependency just for one table, we switch to
    # Styler.bar(), which renders the same kind of "size = value" visual cue
    # using plain CSS and needs no external plotting library.
    st.dataframe(
        agency.style
        .format({"Avg Risk Score": "{:.1f}"})
        .bar(subset=["Avg Risk Score"], color=RED, vmin=0, vmax=100),
        use_container_width=True,
    )
    # NOTE: if you'd rather keep the original heatmap look and don't mind the
    # extra dependency, the alternative fix is simply to add "matplotlib" to
    # requirements.txt and keep .background_gradient(subset=["Avg Risk Score"], cmap="Reds").

    st.subheader("Top 15 riskiest projects")
    top = df.sort_values("Risk_Score", ascending=False).head(15)[
        ["Project_ID", "Work_Name", "District", "Risk_Score", "Risk_Level"]
    ]
    st.dataframe(top, use_container_width=True, hide_index=True)

# =================================================================== MAP VIEW
elif page == "Map View":
    st.title("Risk Map of MPLADS Projects")
    st.caption("Geographical distribution of project risk")

    c1, c2 = st.columns([1, 3])
    state_list = sorted(df["State"].unique().tolist())
    default_state = "Maharashtra" if "Maharashtra" in state_list else state_list[0]
    state_f = c1.selectbox("State", state_list, index=state_list.index(default_state))
    mdf = df[df["State"] == state_f].copy()

    # BUG FIX: the map was rendering centered near Gabon/São Tomé (lat/lon ~ 0,0)
    # instead of Karnataka. That happens when some rows have missing/placeholder
    # coordinates (e.g. NaN silently coerced to 0.0, or a failed lookup in
    # state_centroids.py falling back to (0, 0)). 0°N, 0°E is in the Gulf of
    # Guinea off the coast of Africa, which is exactly what Image 5 showed.
    #
    # This filters out any row whose lat/lon falls outside India's bounding box
    # before plotting, so a handful of bad rows can no longer drag the map's
    # auto-center off to Africa. The real fix long-term is to correct the
    # source of those bad coordinates in state_centroids.py / data_gen.py —
    # search there for any lat/lon defaulting to 0, NaN, or an unmapped state
    # key falling through to a default value.
    valid_mask = (
        mdf["Latitude"].between(*INDIA_LAT_RANGE)
        & mdf["Longitude"].between(*INDIA_LON_RANGE)
    )
    bad_rows = (~valid_mask).sum()
    mdf = mdf[valid_mask]

    if bad_rows:
        st.warning(
            f"⚠️ {bad_rows} project(s) in {state_f} had invalid latitude/longitude "
            "(outside India's bounding box) and were excluded from the map. "
            "This usually means a lookup in state_centroids.py or data_gen.py is "
            "falling back to (0, 0) for those rows — worth checking the source data."
        )

    if mdf.empty:
        st.error(f"No projects with valid coordinates found for {state_f}.")
    else:
        fig = px.scatter_map(
            mdf, lat="Latitude", lon="Longitude", color="Risk_Level",
            color_discrete_map=RISK_COLORS, hover_name="Project_ID",
            hover_data={"Work_Name": True, "District": True, "Risk_Score": True, "Latitude": False, "Longitude": False},
            zoom=6, height=560,
            center={"lat": mdf["Latitude"].median(), "lon": mdf["Longitude"].median()},
            category_orders={"Risk_Level": ["Low", "Medium", "High", "Critical"]},
        )
        fig.update_traces(marker=dict(size=12))
        fig.update_layout(map_style="carto-positron", margin=dict(t=0, b=0, l=0, r=0))
        st.plotly_chart(fig, use_container_width=True)

        top_critical = mdf[mdf["Risk_Level"] == "Critical"].sort_values("Risk_Score", ascending=False)
        if len(top_critical):
            r = top_critical.iloc[0]
            st.warning(f"⚠️ **{r['Project_ID']}** — {r['Work_Name']} in {r['District']} — Risk Score **{r['Risk_Score']}/100** (Critical)")

    st.subheader(f"{state_f}: district summary")
    dist_summary = df[df["State"] == state_f].groupby("District").agg(
        Total_Projects=("Project_ID", "count"),
        High_Risk=("Risk_Level", lambda s: (s == "High").sum()),
        Critical=("Risk_Level", lambda s: (s == "Critical").sum()),
    )
    st.dataframe(dist_summary, use_container_width=True)

# =================================================================== PROJECT DETAILS
elif page == "Project Details":
    st.title("Project Details")

    pid = st.selectbox("Select Project ID", df.sort_values("Risk_Score", ascending=False)["Project_ID"].tolist())
    row = df[df["Project_ID"] == pid].iloc[0]

    top = st.columns([2, 1])
    with top[0]:
        st.subheader(f"{row['Work_Name']}")
        st.caption(f"{row['District']}, {row['State']}  •  {row['Constituency']}")
    with top[1]:
        st.markdown(
            f"<div style='text-align:right;'>"
            f"<span style='font-size:13px;color:#5B6478;'>Risk Score</span><br>"
            f"<span style='font-size:26px;font-weight:800;color:{RISK_COLORS[row['Risk_Level']]};'>{row['Risk_Score']} / 100</span> "
            f"{risk_badge(row['Risk_Level'])}</div>",
            unsafe_allow_html=True,
        )

    st.write("")
    c1, c2 = st.columns([1, 1.4])
    with c1:
        st.markdown("##### Project Info")
        info = {
            "Project ID": row["Project_ID"], "Work Type": row["Work_Name"], "Sector": row["Sector"],
            "District / Constituency": row["District"], "Member of Parliament": row["MP_Name"],
            "Implementing Agency": row["Implementing_Agency"],
            "Sanctioned Amount": money(row["Sanctioned_Amount"]), "Expenditure": money(row["Expenditure"]),
            "Expenditure %": f"{row['Expenditure_Pct']:.0f}%", "Physical Progress": f"{row['Physical_Progress_Pct']:.0f}%",
            "Start Date": row["Start_Date"].strftime("%d-%b-%Y") if hasattr(row["Start_Date"], "strftime") else row["Start_Date"],
            "Expected Completion": row["Expected_Completion"].strftime("%d-%b-%Y") if hasattr(row["Expected_Completion"], "strftime") else row["Expected_Completion"],
            "Current Status": row["Status"],
        }
        for k, v in info.items():
            st.markdown(f"<div style='display:flex;justify-content:space-between;font-size:14px;padding:3px 0;'>"
                        f"<span style='color:#5B6478;'>{k}</span><span style='font-weight:600;'>{v}</span></div>",
                        unsafe_allow_html=True)

    with c2:
        st.markdown("##### Why is this project flagged as risky?")
        reasons = parse_reasons(row["Reasons"])
        for r in reasons:
            st.markdown(f"<div class='reason-card'>⚠️ {r}</div>", unsafe_allow_html=True)
        st.markdown(
            f"<div style='background:#FBE3E1;border-radius:6px;padding:10px 14px;margin-top:10px;'>"
            f"<b style='color:{RED};'>Recommended Action:</b> {recommended_action(reasons)}</div>",
            unsafe_allow_html=True,
        )
        if st.button("🚩 Send to Investigation"):
            st.session_state["prefill_pid"] = pid
            st.info("Go to the **Investigation** page from the sidebar — the Project ID is pre-filled.")

# =================================================================== INVESTIGATION
elif page == "Investigation":
    st.title("Initiate Investigation")
    st.caption("Send a flagged project for further review")

    prefill = st.session_state.get("prefill_pid", df.sort_values("Risk_Score", ascending=False)["Project_ID"].iloc[0])
    ids = df["Project_ID"].tolist()
    pid = st.selectbox("Project ID", ids, index=ids.index(prefill) if prefill in ids else 0)
    row = df[df["Project_ID"] == pid].iloc[0]

    c1, c2 = st.columns(2)
    with c1:
        st.markdown(f"**Priority Level:**  {risk_badge(row['Risk_Level'])}", unsafe_allow_html=True)
        officer = st.selectbox("Assigned To", ["District Officer - A. Sharma", "District Officer - R. Patil",
                                                 "Vigilance Cell - N. Verma", "Field Auditor - S. Iyer"])
        remarks = st.text_area("Remarks (optional)", placeholder="Enter remarks...")
        submit = st.button("✅ Start Investigation", type="primary")

    with c2:
        st.markdown("###### Project snapshot")
        st.write(f"**{row['Work_Name']}** — {row['District']}")
        st.write(f"Risk Score: **{row['Risk_Score']}/100** ({row['Risk_Level']})")
        reasons = parse_reasons(row["Reasons"])
        st.caption(recommended_action(reasons))

    if submit:
        rec = {
            "Project_ID": pid, "Priority": row["Risk_Level"], "Assigned_To": officer,
            "Remarks": remarks, "Created_On": TODAY.strftime("%Y-%m-%d"), "Status": "Pending Review",
        }
        save_investigation(rec)
        # IMPROVEMENT: clear the prefill + the cached investigations so the log
        # below reflects the new record immediately and a stale project ID
        # doesn't keep resurfacing on the next visit to this page.
        st.session_state.pop("prefill_pid", None)
        get_investigations.clear()
        st.success("✅ Investigation Created!")
        st.json(rec)

    st.markdown("---")
    st.subheader("Investigation log")
    inv = get_investigations()
    st.dataframe(inv, use_container_width=True, hide_index=True)

# =================================================================== REPORTS
elif page == "Reports":
    st.title("Reports & Analytics")
    st.caption("Insights for better governance")

    csv = df.drop(columns=["Reasons"]).to_csv(index=False).encode("utf-8")
    st.download_button("⬇ Download Full Report (CSV)", csv, "drishti_ai_report.csv", "text/csv")

    tabs = st.tabs(["Overview", "Cost Analysis", "Delay Analysis", "Sector Analysis", "Agency Analysis"])

    with tabs[0]:
        c1, c2 = st.columns(2)
        with c1:
            st.subheader("Projects by Sector")
            sec = df["Sector"].value_counts().sort_values()
            fig = go.Figure(go.Bar(x=sec.values, y=sec.index, orientation="h", marker_color=BLUE))
            fig.update_layout(height=320, margin=dict(t=10, b=10, l=10, r=30))
            st.plotly_chart(fig, use_container_width=True)
        with c2:
            st.subheader("Project Status")
            st_counts = df["Status"].value_counts()
            fig = go.Figure(go.Pie(labels=st_counts.index, values=st_counts.values, hole=0.55))
            fig.update_layout(height=320, margin=dict(t=10, b=10, l=10, r=10))
            st.plotly_chart(fig, use_container_width=True)

    with tabs[1]:
        st.subheader("Sanctioned amount vs risk score")
        fig = px.scatter(df, x="Sanctioned_Amount", y="Risk_Score", color="Risk_Level",
                          color_discrete_map=RISK_COLORS, hover_data=["Project_ID", "Work_Name"])
        fig.update_layout(height=440)
        st.plotly_chart(fig, use_container_width=True)

    with tabs[2]:
        st.subheader("Days overdue distribution")
        overdue = df[df["Days_Overdue"] > 0]
        fig = px.histogram(overdue, x="Days_Overdue", nbins=20, color_discrete_sequence=[AMBER])
        fig.update_layout(height=440)
        st.plotly_chart(fig, use_container_width=True)

    with tabs[3]:
        st.subheader("Average progress vs expenditure % by sector")
        sec_avg = df.groupby("Sector")[["Physical_Progress_Pct", "Expenditure_Pct"]].mean()
        fig = go.Figure()
        fig.add_bar(name="Progress %", x=sec_avg.index, y=sec_avg["Physical_Progress_Pct"], marker_color=GREEN)
        fig.add_bar(name="Expenditure %", x=sec_avg.index, y=sec_avg["Expenditure_Pct"], marker_color=RED)
        fig.update_layout(barmode="group", height=440)
        st.plotly_chart(fig, use_container_width=True)

    with tabs[4]:
        st.subheader("Top implementing agencies by risk-weighted project count")
        agency = df.groupby("Implementing_Agency").agg(
            Projects=("Project_ID", "count"), Avg_Risk=("Risk_Score", "mean")
        ).sort_values("Avg_Risk", ascending=False)
        st.dataframe(agency.style.format({"Avg_Risk": "{:.1f}"}), use_container_width=True)

# =================================================================== ABOUT
elif page == "About":
    st.title("About DRISHTI-AI")
    st.markdown("""
**DRISHTI-AI** is an AI-powered risk intelligence and monitoring layer for the MPLADS
scheme, built for **Smart India Hackathon — Problem Statement SIH26102**
(Ministry of Statistics and Programme Implementation, MoSPI).

##### Data pipeline
1. **Real data ingestion** — official MPLADS allocation list for the 18th Lok Sabha:
   542 MPs, 36 states/UTs, real constituency names and fund entitlements.
2. **Cleaning** (`clean_mp_data.py`) — dropped header/footer noise, standardized
   name casing, split reservation tags (SC/ST/GEN) out of constituency names,
   resolved state-disambiguation suffixes, de-duplicated on (state, constituency).
3. **EDA** (`eda_mp_data.py`) — entitlement distribution, outlier detection,
   reservation-category split, coverage checks across states.
4. **Project-level simulation** (`data_gen.py`) — since the public eSAKSHI portal
   exposes no project-level records, realistic works are generated under each
   MP's *real* entitlement ceiling (never exceeding it), with risk patterns
   (cost anomalies, expenditure/progress mismatches, delays, duplicates) injected
   for the model to detect.
5. **Risk engine** (`risk_engine.py`) — rule-based checks + Isolation Forest
   anomaly detection + NLP text-similarity duplicate detection, blended into an
   explainable 0–100 score.
6. **Dashboard & investigation workflow** (`app.py`) — officers filter, drill
   down, and log investigations directly from the tool.

##### Data honesty
The **entitlement layer (MP, constituency, state, allocated amount) is 100% real**
government data. The **project-level layer** (individual works, expenditure,
progress %) is simulated, bounded by each MP's real ceiling, because the public
portal doesn't expose that layer. Swapping in real project-level data (once
available) is a one-file change — the risk engine works on the schema, not the source.

##### Tech stack
Python • Pandas • scikit-learn (Isolation Forest) • RapidFuzz (text similarity) •
Streamlit • Plotly

##### Team
Team Name: ____________________
Team Members: 1. _______  2. _______  3. _______  4. _______  5. _______  6. _______
""")
    st.info("Technically feasible. Practically implementable. Scalable. Impactful.")