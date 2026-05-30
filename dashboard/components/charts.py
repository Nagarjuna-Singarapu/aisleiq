"""
Reusable chart helpers for the Streamlit dashboard.
"""
from __future__ import annotations

from typing import List

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go


def occupancy_line_chart(occupancy_data: List[dict]) -> go.Figure:
    if not occupancy_data:
        fig = go.Figure()
        fig.update_layout(title="Occupancy Timeline (no data yet)")
        return fig
    df = pd.DataFrame(occupancy_data)
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    fig = px.line(
        df,
        x="timestamp",
        y="occupancy",
        color="camera_id",
        title="Occupancy Over Time",
        labels={"occupancy": "People in Store", "timestamp": "Time"},
    )
    fig.update_layout(height=300)
    return fig


def zone_bar_chart(zone_data: List[dict]) -> go.Figure:
    if not zone_data:
        fig = go.Figure()
        fig.update_layout(title="Zone Occupancy (no data yet)")
        return fig
    df = pd.DataFrame(zone_data)
    fig = px.bar(
        df,
        x="zone",
        y=["current_count", "total_entries"],
        barmode="group",
        title="Zone Occupancy & Total Entries",
        labels={"value": "Count", "zone": "Store Zone"},
    )
    fig.update_layout(height=300)
    return fig


def dwell_histogram(dwell_data: dict) -> go.Figure:
    if not dwell_data or dwell_data.get("total_tracks", 0) == 0:
        fig = go.Figure()
        fig.update_layout(title="Dwell Time Distribution (no data yet)")
        return fig
    labels = ["Avg", "P50", "P95", "Max"]
    values = [
        dwell_data.get("avg_dwell_seconds", 0),
        dwell_data.get("p50_dwell_seconds", 0),
        dwell_data.get("p95_dwell_seconds", 0),
        dwell_data.get("max_dwell_seconds", 0),
    ]
    fig = go.Figure(go.Bar(x=labels, y=values, marker_color=["#636EFA", "#EF553B", "#00CC96", "#AB63FA"]))
    fig.update_layout(title="Dwell Time Summary (seconds)", height=280)
    return fig


def events_table(events: List[dict]) -> pd.DataFrame:
    if not events:
        return pd.DataFrame(columns=["timestamp", "event_type", "track_id", "zone", "camera_id"])
    df = pd.DataFrame(events)[["timestamp", "event_type", "track_id", "zone", "camera_id"]]
    df["timestamp"] = pd.to_datetime(df["timestamp"]).dt.strftime("%H:%M:%S")
    return df
