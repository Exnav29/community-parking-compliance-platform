# SPDX-License-Identifier: Apache-2.0
"""Geo helpers: accuracy tiers, geofence checks, privacy-safe aggregation (PRD 7, 11, 30.3)."""
from __future__ import annotations

import math
from collections import Counter

Point = tuple[float, float]  # (lat, lon)


def accuracy_tier(accuracy_m: float | None, high: float = 25, approx: float = 75) -> str:
    """Illustrative, configurable UX thresholds - NOT a guarantee of vehicle position."""
    if accuracy_m is None or accuracy_m < 0:
        return "unknown"
    if accuracy_m <= high:
        return "high"
    if accuracy_m <= approx:
        return "approximate"
    return "low - confirm location"


def valid_coordinate(lat: float, lon: float) -> bool:
    return -90 <= lat <= 90 and -180 <= lon <= 180 and not (lat == 0 and lon == 0)


def point_in_polygon(pt: Point, polygon: list[Point]) -> bool:
    """Ray casting; polygon is a list of (lat, lon) vertices (closed or open)."""
    lat, lon = pt
    inside = False
    n = len(polygon)
    for i in range(n):
        y1, x1 = polygon[i]
        y2, x2 = polygon[(i + 1) % n]
        if (x1 > lon) != (x2 > lon):
            y_cross = (y2 - y1) * (lon - x1) / (x2 - x1) + y1
            if lat < y_cross:
                inside = not inside
    return inside


def haversine_m(a: Point, b: Point) -> float:
    r = 6371000.0
    p1, p2 = math.radians(a[0]), math.radians(b[0])
    dphi, dl = p2 - p1, math.radians(b[1] - a[1])
    h = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(h))


def geofence_status(pt: Point, boundary: list[Point], far_m: float = 2000) -> str:
    """'inside' | 'outside' | 'far'. Callers must require an override reason unless 'inside'.
    Coordinates are never silently snapped to the property."""
    if point_in_polygon(pt, boundary):
        return "inside"
    nearest = min(haversine_m(pt, v) for v in boundary)
    return "far" if nearest > far_m else "outside"


def blur_point(pt: Point, grid_m: float = 100) -> Point:
    """Snap to a coarse grid centre for resident-facing views."""
    dlat = grid_m / 111_320.0
    dlon = grid_m / (111_320.0 * max(math.cos(math.radians(pt[0])), 0.01))
    return (round(math.floor(pt[0] / dlat) * dlat + dlat / 2, 6), round(math.floor(pt[1] / dlon) * dlon + dlon / 2, 6))


def zone_counts_with_threshold(zone_ids: list[str], k: int = 5) -> dict[str, int | None]:
    """Counts per zone; cells below k are suppressed (None) so a single household cannot be singled out."""
    counts = Counter(zone_ids)
    return {z: (c if c >= k else None) for z, c in counts.items()}
