"""Locator maps for articles: project points and nearby country outlines into SVG paths.

A map visual in an edition:
  {"type": "map", "title": "...", "note": "...", "source": "...",
   "points": [{"label": "Berezniki", "lat": 59.41, "lon": 56.82,
               "detail": "Avisma titanium plant hit by drones", "kind": "strike"}],
   "highlight": ["Ukraine"],          # optional: countries to shade
   "bbox": [lon_min, lat_min, lon_max, lat_max]}   # optional: force the frame

kind is one of strike | target (accent), base | origin (blue), place (neutral).
`basemap(vis)` returns the drawing data the viewer and the PDF both use.
"""
import json
import math
import os

import common

W = 600.0
_GEO = None


def _countries():
    global _GEO
    if _GEO is None:
        with open(common.code("viewer", "geo", "countries.json"), encoding="utf-8") as f:
            _GEO = json.load(f)
    return _GEO


def _country_box(name):
    rings = _countries().get(name) or []
    pts = [p for r in rings for p in r if -170 < p[0] < 190]
    if not pts:
        return None
    # Use the largest ring only (mainland), so far-flung islands don't stretch the frame.
    main = max(rings, key=len)
    return min(p[0] for p in main), min(p[1] for p in main), max(p[0] for p in main), max(p[1] for p in main)


def frame(vis):
    if vis.get("bbox"):
        return tuple(vis["bbox"])
    lons = [p["lon"] for p in vis["points"]]
    lats = [p["lat"] for p in vis["points"]]
    # Highlighted countries are always shown whole, so the reader can orient themselves.
    for name in vis.get("highlight") or []:
        box = _country_box(name)
        if box:
            lons += [box[0], box[2]]
            lats += [box[1], box[3]]
    lo0, lo1, la0, la1 = min(lons), max(lons), min(lats), max(lats)
    span_lo = max(lo1 - lo0, 10.0) * 1.15
    span_la = max(la1 - la0, 6.0) * 1.2
    clo, cla = (lo0 + lo1) / 2, (la0 + la1) / 2
    # Keep the frame from getting too wide and flat (unreadable on a phone): at least 0.6 tall per 1 wide.
    k = math.cos(math.radians(cla))
    if span_la < 0.6 * span_lo * k:
        span_la = 0.6 * span_lo * k
    if span_la > 1.1 * span_lo * k:
        span_lo = span_la / (1.1 * k)
    return (clo - span_lo / 2, cla - span_la / 2, clo + span_lo / 2, cla + span_la / 2)


def basemap(vis):
    lo0, la0, lo1, la1 = frame(vis)
    k = math.cos(math.radians((la0 + la1) / 2))  # equirectangular, true scale at the middle latitude
    sx = W / ((lo1 - lo0) * k)
    h = round((la1 - la0) * sx, 1)

    def xy(lon, lat):
        return round((lon - lo0) * k * sx, 1), round((la1 - lat) * sx, 1)

    def clip(poly):
        # Sutherland-Hodgman against the frame, so outlines never spill outside the map.
        for edge in ("l", "r", "t", "b"):
            if not poly:
                return poly
            inside = {"l": lambda p: p[0] >= 0, "r": lambda p: p[0] <= W,
                      "t": lambda p: p[1] >= 0, "b": lambda p: p[1] <= h}[edge]

            def cross(p, q, edge=edge):
                if edge in ("l", "r"):
                    x = 0 if edge == "l" else W
                    t = (x - p[0]) / (q[0] - p[0])
                    return (x, round(p[1] + t * (q[1] - p[1]), 1))
                y = 0 if edge == "t" else h
                t = (y - p[1]) / (q[1] - p[1])
                return (round(p[0] + t * (q[0] - p[0]), 1), y)
            out = []
            for i, cur in enumerate(poly):
                prev = poly[i - 1]
                if inside(cur):
                    if not inside(prev):
                        out.append(cross(prev, cur))
                    out.append(cur)
                elif inside(prev):
                    out.append(cross(prev, cur))
            poly = out
        return poly

    hl = set(vis.get("highlight") or [])
    paths = []
    for name, rings in _countries().items():
        parts = []
        for r in rings:
            rlo = [p[0] for p in r]
            rla = [p[1] for p in r]
            if max(rlo) < lo0 or min(rlo) > lo1 or max(rla) < la0 or min(rla) > la1:
                continue
            pts = clip([xy(lon, lat) for lon, lat in r])
            if len(pts) >= 3:
                parts.append("M" + "L".join(f"{x},{y}" for x, y in pts) + "Z")
        if parts:
            paths.append({"name": name, "d": "".join(parts), "hl": name in hl})
    pts = []
    for i, p in enumerate(vis["points"], 1):
        x, y = xy(p["lon"], p["lat"])
        pts.append({"n": i, "x": x, "y": y, "label": p["label"], "detail": p.get("detail", ""), "kind": p.get("kind", "place")})
    return {"w": W, "h": h, "paths": paths, "points": pts}


def attach(edition):
    """Add precomputed `_map` drawing data to every map visual in an edition (in place)."""
    for a in edition.get("articles", []):
        v = a.get("visual")
        if v and v.get("type") == "map" and v.get("points"):
            v["_map"] = basemap(v)
    return edition
