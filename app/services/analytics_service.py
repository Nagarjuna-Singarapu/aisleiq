"""
Analytics service — computes all store metrics from DB events and tracks.
"""
from __future__ import annotations

import json
import statistics
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from sqlalchemy import func, and_
from sqlalchemy.orm import Session

from app.config import settings
from app.models.db_models import StoreEvent, Track, Alert, ProcessingJob
from app.models.schemas import (
    AnalyticsSummary,
    DwellTimeSummary,
    EventType,
    OccupancyPoint,
    ZoneOccupancy,
)
from app.utils.logger import get_logger

log = get_logger(__name__)


class AnalyticsService:
    # ------------------------------------------------------------------ #
    # Footfall & occupancy
    # ------------------------------------------------------------------ #

    def get_footfall(self, db: Session, camera_id: Optional[str] = None) -> int:
        q = db.query(func.count(StoreEvent.id)).filter(
            StoreEvent.event_type == EventType.PERSON_ENTERED.value
        )
        if camera_id:
            q = q.filter(StoreEvent.camera_id == camera_id)
        return q.scalar() or 0

    def get_current_occupancy(self, db: Session, camera_id: Optional[str] = None) -> int:
        """
        occupancy = entered - exited (floor at 0).
        Uses only the most recent job per camera.
        """
        def _count(event_type: str) -> int:
            q = db.query(func.count(StoreEvent.id)).filter(
                StoreEvent.event_type == event_type
            )
            if camera_id:
                q = q.filter(StoreEvent.camera_id == camera_id)
            return q.scalar() or 0

        entered = _count(EventType.PERSON_ENTERED.value)
        exited = _count(EventType.PERSON_EXITED.value)
        return max(0, entered - exited)

    def get_occupancy_timeline(
        self,
        db: Session,
        camera_id: Optional[str] = None,
        from_dt: Optional[datetime] = None,
        to_dt: Optional[datetime] = None,
    ) -> List[OccupancyPoint]:
        """Return occupancy count per minute bucket."""
        q = db.query(StoreEvent).filter(
            StoreEvent.event_type.in_([
                EventType.PERSON_ENTERED.value,
                EventType.PERSON_EXITED.value,
            ])
        )
        if camera_id:
            q = q.filter(StoreEvent.camera_id == camera_id)
        if from_dt:
            q = q.filter(StoreEvent.timestamp >= from_dt)
        if to_dt:
            q = q.filter(StoreEvent.timestamp <= to_dt)

        events = q.order_by(StoreEvent.timestamp).all()
        if not events:
            return []

        # Build minute-bucket time series
        bucket_map: dict[datetime, int] = {}
        running = 0
        for ev in events:
            bucket = ev.timestamp.replace(second=0, microsecond=0)
            if ev.event_type == EventType.PERSON_ENTERED.value:
                running += 1
            else:
                running = max(0, running - 1)
            bucket_map[bucket] = running

        return [
            OccupancyPoint(timestamp=ts, occupancy=occ, camera_id=camera_id or "all")
            for ts, occ in sorted(bucket_map.items())
        ]

    # ------------------------------------------------------------------ #
    # Dwell time
    # ------------------------------------------------------------------ #

    def get_dwell_summary(self, db: Session, camera_id: Optional[str] = None) -> DwellTimeSummary:
        q = db.query(Track.dwell_seconds)
        if camera_id:
            q = q.filter(Track.camera_id == camera_id)
        dwells = [r[0] for r in q.all() if r[0] > 0]

        if not dwells:
            return DwellTimeSummary(
                avg_dwell_seconds=0,
                min_dwell_seconds=0,
                max_dwell_seconds=0,
                p50_dwell_seconds=0,
                p95_dwell_seconds=0,
                total_tracks=0,
            )

        sorted_d = sorted(dwells)
        n = len(sorted_d)
        return DwellTimeSummary(
            avg_dwell_seconds=round(statistics.mean(dwells), 1),
            min_dwell_seconds=round(min(dwells), 1),
            max_dwell_seconds=round(max(dwells), 1),
            p50_dwell_seconds=round(sorted_d[n // 2], 1),
            p95_dwell_seconds=round(sorted_d[int(n * 0.95)], 1),
            total_tracks=n,
        )

    # ------------------------------------------------------------------ #
    # Zone analytics
    # ------------------------------------------------------------------ #

    def get_zone_occupancy(self, db: Session, camera_id: Optional[str] = None) -> List[ZoneOccupancy]:
        """Compute current + total entries per zone from zone-change events."""
        q = db.query(StoreEvent).filter(
            StoreEvent.event_type == EventType.ZONE_OCCUPANCY_CHANGED.value,
            StoreEvent.zone.isnot(None),
        )
        if camera_id:
            q = q.filter(StoreEvent.camera_id == camera_id)

        events = q.order_by(StoreEvent.timestamp).all()

        zone_entries: dict[str, int] = {}
        # track -> current zone
        track_zone: dict[int, str | None] = {}

        for ev in events:
            payload = json.loads(ev.payload or "{}")
            to_zone = payload.get("to_zone")
            from_zone = payload.get("from_zone")
            tid = ev.track_id

            if to_zone:
                zone_entries[to_zone] = zone_entries.get(to_zone, 0) + 1
            track_zone[tid] = to_zone

        # current counts = tracks whose last zone is this zone
        current_counts: dict[str, int] = {}
        for zone in track_zone.values():
            if zone:
                current_counts[zone] = current_counts.get(zone, 0) + 1

        all_zones = set(list(zone_entries.keys()) + list(current_counts.keys()))
        return [
            ZoneOccupancy(
                zone=z,
                current_count=current_counts.get(z, 0),
                total_entries=zone_entries.get(z, 0),
            )
            for z in sorted(all_zones)
        ]

    # ------------------------------------------------------------------ #
    # Peak crowd
    # ------------------------------------------------------------------ #

    def get_peak(self, db: Session, camera_id: Optional[str] = None) -> tuple[int, Optional[datetime]]:
        timeline = self.get_occupancy_timeline(db, camera_id)
        if not timeline:
            return 0, None
        peak = max(timeline, key=lambda p: p.occupancy)
        return peak.occupancy, peak.timestamp

    # ------------------------------------------------------------------ #
    # Summary
    # ------------------------------------------------------------------ #

    def get_summary(self, db: Session, camera_id: Optional[str] = None) -> AnalyticsSummary:
        footfall = self.get_footfall(db, camera_id)
        occupancy = self.get_current_occupancy(db, camera_id)
        dwell = self.get_dwell_summary(db, camera_id)
        zone_occ = self.get_zone_occupancy(db, camera_id)
        peak_occ, peak_time = self.get_peak(db, camera_id)
        total_alerts = db.query(func.count(Alert.id)).scalar() or 0

        return AnalyticsSummary(
            camera_id=camera_id or "all",
            total_footfall=footfall,
            current_occupancy=occupancy,
            dwell_time=dwell,
            zone_occupancy=zone_occ,
            peak_occupancy=peak_occ,
            peak_time=peak_time,
            total_alerts=total_alerts,
            generated_at=datetime.now(tz=timezone.utc),
        )
