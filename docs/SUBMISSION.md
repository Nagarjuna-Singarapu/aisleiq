# AisleIQ: AI-Powered Retail Video Intelligence

## Title

AisleIQ: AI-Powered Retail Video Intelligence

## Description

AisleIQ is a production-ready retail analytics system that turns CCTV footage into structured, actionable store intelligence. The solution processes multi-camera store videos, detects and tracks shoppers, generates events such as entries, exits, zone movement, dwell time updates, and queue/crowd signals, and exposes the results through both a REST API and an interactive dashboard.

The backend is built with FastAPI and SQLite, with documented endpoints for video processing, events, analytics, alerts, and health checks. The computer vision pipeline supports YOLO-based detection with a fallback detector, track persistence across frames, zone occupancy analytics, and anomaly detection for crowding, queue build-up, and suspicious loitering. The Streamlit dashboard provides a live operational view with video upload, processing controls, KPI cards, occupancy trends, zone analytics, dwell time summary, recent event tables, active alerts, and processing job history.

GitHub repository: https://github.com/Nagarjuna-Singarapu/aisleiq

## Snapshots

All submission snapshots are stored in `docs/submission-snapshots/`.

- `01-dashboard-overview.png` - Dashboard overview with KPIs, occupancy chart, zone analytics, and processing controls.
- `02-dashboard-events-alerts-jobs.png` - Recent events, active alerts, and processing jobs sections.
- `03-api-docs-overview.png` - Swagger API documentation overview.
- `04-api-docs-alerts-schemas.png` - Additional Swagger API documentation and schemas.
- `05-api-jobs-response.png` - Jobs API response with completed processing records.
- `06-api-health-response.png` - Health check API response.

## Presentation

The pitch deck is stored in `docs/presentation/AisleIQ-Pitch-Deck.pptx`.
