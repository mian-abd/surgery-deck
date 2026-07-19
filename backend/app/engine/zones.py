"""Zone geometry: normalized polygons + point-in-zone lookup (shapely)."""
from __future__ import annotations

from dataclasses import dataclass

try:
    from shapely.geometry import Point, Polygon

    _HAS_SHAPELY = True
except Exception:  # shapely not installed yet
    _HAS_SHAPELY = False


@dataclass
class ZoneDef:
    name: str
    zone_type: str
    polygon: list[list[float]]  # normalized [[x,y], ...]


class ZoneSet:
    """Zones for a single camera. Coordinates are normalized to [0, 1]."""

    def __init__(self, zones: list[ZoneDef] | None = None) -> None:
        self._zones = zones or []
        self._shapes: list[tuple[ZoneDef, object]] = []
        self._rebuild()

    def _rebuild(self) -> None:
        self._shapes = []
        if not _HAS_SHAPELY:
            return
        for z in self._zones:
            if len(z.polygon) >= 3:
                self._shapes.append((z, Polygon(z.polygon)))

    def set(self, zones: list[ZoneDef]) -> None:
        self._zones = zones
        self._rebuild()

    @property
    def types(self) -> set[str]:
        return {z.zone_type for z in self._zones}

    def locate(self, nx: float, ny: float) -> ZoneDef | None:
        """Return the zone containing a normalized point, if any.

        Priority order keeps the most safety-relevant zone when polygons
        overlap (sterile field beats a broad nonsterile background).
        """
        if not _HAS_SHAPELY:
            return None
        pt = Point(nx, ny)
        hits = [z for (z, shape) in self._shapes if shape.contains(pt)]
        if not hits:
            return None
        priority = {"sterile": 0, "tray": 1, "sink": 2, "patient": 3, "entry": 4, "nonsterile": 5}
        hits.sort(key=lambda z: priority.get(z.zone_type, 9))
        return hits[0]
