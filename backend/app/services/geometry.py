"""GeoJSON geometry helpers (centroid, geodesic area, bounding box)."""
from __future__ import annotations

from pyproj import Geod
from shapely.geometry import shape
from shapely.geometry.base import BaseGeometry

_GEOD = Geod(ellps="WGS84")


def extract_geometry(geojson: dict) -> dict:
    """Accept a Feature, FeatureCollection (first feature) or bare geometry."""
    if not isinstance(geojson, dict):
        raise ValueError("geojson must be an object")
    gtype = geojson.get("type")
    if gtype == "FeatureCollection":
        feats = geojson.get("features") or []
        if not feats:
            raise ValueError("FeatureCollection has no features")
        return extract_geometry(feats[0])
    if gtype == "Feature":
        geom = geojson.get("geometry")
        if not geom:
            raise ValueError("Feature has no geometry")
        return geom
    if gtype in {"Polygon", "MultiPolygon", "Point", "LineString"}:
        return geojson
    raise ValueError(f"unsupported geojson type: {gtype!r}")


def polygon_stats(geojson: dict) -> dict:
    """Return centroid, geodesic area (hectares) and bbox for a GeoJSON input."""
    geom: BaseGeometry = shape(extract_geometry(geojson))
    if geom.is_empty:
        raise ValueError("geometry is empty")

    centroid = geom.centroid
    minx, miny, maxx, maxy = geom.bounds

    area_ha = 0.0
    if geom.geom_type in {"Polygon", "MultiPolygon"}:
        area_m2, _perimeter = _GEOD.geometry_area_perimeter(geom)
        area_ha = abs(area_m2) / 10_000.0

    return {
        "centroid_lat": float(centroid.y),
        "centroid_lon": float(centroid.x),
        "area_hectares": round(area_ha, 4),
        "bbox": [float(minx), float(miny), float(maxx), float(maxy)],
        "geometry": extract_geometry(geojson),
    }


def padded_bbox(bbox: list[float], pad_ratio: float = 0.15, min_pad_deg: float = 0.002) -> list[float]:
    """Grow a bbox slightly so thumbnails have visual context around the plot."""
    minx, miny, maxx, maxy = bbox
    dx = max((maxx - minx) * pad_ratio, min_pad_deg)
    dy = max((maxy - miny) * pad_ratio, min_pad_deg)
    return [minx - dx, miny - dy, maxx + dx, maxy + dy]
