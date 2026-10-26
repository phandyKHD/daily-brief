#!/usr/bin/env python3
"""One-off: turn world-atlas countries-50m TopoJSON into viewer/geo/countries.json.

Usage: python3 scripts/geo_build.py <countries-50m.json>
Output: {"<country name>": [[[lon, lat], ...], ...]} (outer rings and holes, simplified).
Source data: Natural Earth via world-atlas@2.0.2 (public domain).
"""
import json
import sys


def decode(topo):
    sx, sy = topo["transform"]["scale"]
    tx, ty = topo["transform"]["translate"]
    arcs = []
    for arc in topo["arcs"]:
        x = y = 0
        pts = []
        for dx, dy in arc:
            x += dx
            y += dy
            pts.append((x * sx + tx, y * sy + ty))
        arcs.append(pts)
    return arcs


def ring(arcs, idxs):
    out = []
    for i in idxs:
        pts = arcs[i] if i >= 0 else list(reversed(arcs[~i]))
        out.extend(pts if not out else pts[1:])
    return out


def simplify(pts, tol=0.04):
    if len(pts) < 8:
        return pts
    keep = [pts[0]]
    for p in pts[1:-1]:
        q = keep[-1]
        if abs(p[0] - q[0]) > tol or abs(p[1] - q[1]) > tol:
            keep.append(p)
    keep.append(pts[-1])
    return keep


def main():
    topo = json.load(open(sys.argv[1]))
    arcs = decode(topo)
    out = {}
    for g in topo["objects"]["countries"]["geometries"]:
        name = g.get("properties", {}).get("name")
        if not name or g["type"] not in ("Polygon", "MultiPolygon"):
            continue
        polys = [g["arcs"]] if g["type"] == "Polygon" else g["arcs"]
        rings = []
        for poly in polys:
            for r in poly:
                pts = simplify(ring(arcs, r))
                if len(pts) >= 4:
                    rings.append([[round(x, 2), round(y, 2)] for x, y in pts])
        out[name] = rings
    json.dump(out, open("viewer/geo/countries.json", "w"), separators=(",", ":"))
    print(len(out), "countries")


if __name__ == "__main__":
    main()
