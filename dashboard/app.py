"""
AisleIQ — AI-Powered Retail Video Intelligence Dashboard
Run with: streamlit run dashboard/app.py
"""
from __future__ import annotations

import os
import sys
import time
from typing import Optional

# Ensure project root is on sys.path when Streamlit runs this as a script
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

import requests
import streamlit as st

from dashboard.components.charts import (
    dwell_histogram,
    events_table,
    occupancy_line_chart,
    zone_bar_chart,
)

# ── Config ────────────────────────────────────────────────────────────── #
API_BASE = os.getenv("API_BASE_URL", "http://localhost:8000")
REFRESH_INTERVAL = 10  # seconds

st.set_page_config(
    page_title="AisleIQ",
    page_icon="🛒",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ── Helpers ───────────────────────────────────────────────────────────── #
_api_errors: list[str] = []


def _get(path: str, params: dict | None = None) -> dict | list | None:
    try:
        r = requests.get(f"{API_BASE}{path}", params=params, timeout=5)
        r.raise_for_status()
        return r.json()
    except requests.exceptions.ConnectionError:
        return None  # API offline — shown once via health check banner
    except Exception as exc:
        _api_errors.append(f"{path}: {exc}")
        return None


def _post(path: str, body: dict) -> dict | None:
    try:
        r = requests.post(f"{API_BASE}{path}", json=body, timeout=10)
        r.raise_for_status()
        return r.json()
    except requests.exceptions.ConnectionError:
        st.error("API is offline. Start it with: `make run-api`")
        return None
    except Exception as exc:
        st.error(f"Request failed: {exc}")
        return None


# ── Sidebar ───────────────────────────────────────────────────────────── #
st.sidebar.title("🛒 AisleIQ")
st.sidebar.markdown("**AI-Powered Retail Video Intelligence**")

camera_filter = st.sidebar.text_input("Filter by Camera ID", value="")
auto_refresh = st.sidebar.checkbox("Auto-refresh (10s)", value=True)

st.sidebar.divider()
st.sidebar.subheader("📤 Upload Video")
uploaded_file = st.sidebar.file_uploader(
    "Upload an MP4/AVI/MOV file",
    type=["mp4", "avi", "mov", "mkv"],
    help="File is saved to data/videos/ on the server",
)
if uploaded_file is not None:
    save_path = os.path.join(_PROJECT_ROOT, "data", "videos", uploaded_file.name)
    if os.path.exists(save_path):
        st.sidebar.warning(f"`{uploaded_file.name}` already exists — will reuse it.")
    else:
        with open(save_path, "wb") as f:
            f.write(uploaded_file.getbuffer())
        st.sidebar.success(f"✅ Saved `{uploaded_file.name}` to data/videos/")

st.sidebar.divider()
st.sidebar.subheader("▶ Process Video")
available: list = _get("/process-video/available-videos") or []
if available:
    selected_video = st.sidebar.selectbox("Select video file", available)
    default_cam = os.path.splitext(selected_video)[0].replace(" ", "")
    cam_id_input = st.sidebar.text_input("Camera ID", value=default_cam)
    frame_skip = st.sidebar.slider("Frame skip (1=every frame, 10=fast)", 1, 10, 3)
    if st.sidebar.button("▶ Start Processing", type="primary"):
        result = _post(
            "/process-video",
            {"camera_id": cam_id_input, "video_filename": selected_video, "frame_skip": frame_skip},
        )
        if result:
            st.sidebar.success(f"Job {result['job_id']} queued — status: {result['status']}")
            st.rerun()
        else:
            st.sidebar.error("Job submission failed — check API logs.")
else:
    st.sidebar.warning("No videos found. Upload one above or start the API first:\n`make run-api`")

st.sidebar.divider()
if st.sidebar.button("🔄 Refresh Now"):
    st.rerun()

# ── Main ─────────────────────────────────────────────────────────────── #
st.title("📹 AisleIQ — Retail Video Intelligence")

cam_param = camera_filter or None

# Health check banner
health = _get("/health")
_api_online = health and health.get("status") == "ok"
if _api_online:
    st.success(f"✅ API online | DB: {health.get('database')} | v{health.get('version')}")
else:
    st.error(
        "❌ API is offline. Open a **second terminal** and run:\n"
        "```\nmake run-api\n```"
    )
    st.info("The dashboard will reconnect automatically once the API starts.")
    if auto_refresh:
        time.sleep(REFRESH_INTERVAL)
        st.rerun()
    st.stop()

# ── KPI Row ──────────────────────────────────────────────────────────── #
summary = _get("/analytics/summary", {"camera_id": cam_param} if cam_param else None)
summary = summary or {}

col1, col2, col3, col4 = st.columns(4)
col1.metric("👥 Current Occupancy", summary.get("current_occupancy", "—"))
col2.metric("🚶 Total Footfall", summary.get("total_footfall", "—"))
col3.metric("⏱ Avg Dwell (s)", summary.get("dwell_time", {}).get("avg_dwell_seconds", "—"))
col4.metric("🚨 Total Alerts", summary.get("total_alerts", "—"))

peak_occ = summary.get("peak_occupancy", 0)
peak_time = summary.get("peak_time", "N/A")
st.caption(f"Peak occupancy: **{peak_occ}** at {peak_time}")

st.divider()

# ── Charts Row ───────────────────────────────────────────────────────── #
left, right = st.columns(2)

with left:
    occ_data = _get("/analytics/occupancy", {"camera_id": cam_param} if cam_param else None) or []
    st.plotly_chart(occupancy_line_chart(occ_data), width="stretch")

with right:
    zone_data = _get("/analytics/zones", {"camera_id": cam_param} if cam_param else None) or []
    st.plotly_chart(zone_bar_chart(zone_data), width="stretch")

dwell_data = _get("/analytics/dwell-time", {"camera_id": cam_param} if cam_param else None) or {}
st.plotly_chart(dwell_histogram(dwell_data), width="stretch")

st.divider()

# ── Events Table ─────────────────────────────────────────────────────── #
st.subheader("📋 Recent Events")
events_params: dict = {"limit": 50}
if cam_param:
    events_params["camera_id"] = cam_param
events_data = _get("/events", events_params) or []
df = events_table(events_data)
st.dataframe(df, width="stretch")

# ── Alerts ───────────────────────────────────────────────────────────── #
st.subheader("🚨 Active Alerts")
alerts_params: dict = {"acknowledged": False, "limit": 20}
if cam_param:
    alerts_params["camera_id"] = cam_param
alerts_data = _get("/alerts", alerts_params) or []

if alerts_data:
    for alert in alerts_data:
        colour = "red" if alert["severity"] == "high" else "orange"
        with st.container():
            c1, c2, c3 = st.columns([3, 1, 1])
            c1.markdown(f":{colour}[**{alert['alert_type'].upper()}**] {alert['message']}")
            c2.write(alert["timestamp"][:19])
            if c3.button("Acknowledge", key=alert["alert_id"]):
                requests.patch(f"{API_BASE}/alerts/{alert['alert_id']}/acknowledge", timeout=5)
                st.rerun()
else:
    st.success("No active alerts")

# ── Processing Jobs ──────────────────────────────────────────────────── #
with st.expander("🔧 Processing Jobs", expanded=True):
    jobs = _get("/process-video/jobs") or []
    if jobs:
        import pandas as pd
        jobs_df = pd.DataFrame(jobs)[["job_id", "camera_id", "status", "processed_frames", "total_frames", "fps", "created_at"]]
        st.dataframe(jobs_df, width="stretch")
    else:
        st.info("No jobs yet")

# ── Auto-refresh ─────────────────────────────────────────────────────── #
if auto_refresh:
    time.sleep(REFRESH_INTERVAL)
    st.rerun()
