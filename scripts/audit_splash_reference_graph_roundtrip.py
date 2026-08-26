#!/usr/bin/env python3
"""Audit that the canonical graph round-trips exactly to canonical pixels.

Every graph edge is expected to preserve its source pixel walk exactly. This
auditor reconstructs all tree/shared/unowned graph pixels from edge paths plus
explicit isolated nodes and compares the union to the canonical pixel manifest
without smoothing, interpolation, or line drawing. Any missing or extra pixel is
a hard promotion failure.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def parse_args() -> argparse.Namespace:
    p=argparse.ArgumentParser()
    p.add_argument("canonical_manifest",type=Path)
    p.add_argument("canonical_graph",type=Path)
    p.add_argument("--out",type=Path,required=True)
    return p.parse_args()


def pixel_set(records):
    out=set()
    for item in records:
        for x,y in item.get("pixels",[]): out.add((int(x),int(y)))
    return out


def graph_pixels(graph):
    out=set()
    for group in ("route_trees","shared_geometry","preserved_unowned_geometry"):
        for item in graph.get(group,[]):
            for edge in item.get("edges",[]):
                for x,y in edge.get("path",[]): out.add((int(x),int(y)))
            for x,y in item.get("isolated_nodes",[]):
                out.add((int(x),int(y)))
    return out


def canonical_pixels(manifest):
    out=pixel_set(manifest.get("route_trees",[]))
    out|=pixel_set(manifest.get("shared_geometry",[]))
    out|=pixel_set(manifest.get("preserved_unowned_geometry",[]))
    return out


def main():
    args=parse_args(); args.out.mkdir(parents=True,exist_ok=True)
    manifest=json.loads(args.canonical_manifest.read_text(encoding="utf-8"))
    graph=json.loads(args.canonical_graph.read_text(encoding="utf-8"))
    expected=canonical_pixels(manifest); actual=graph_pixels(graph)
    missing=sorted(expected-actual,key=lambda p:(p[1],p[0]))
    extra=sorted(actual-expected,key=lambda p:(p[1],p[0]))
    result={
        "meta":{
            "stage":"CANONICAL_GRAPH_RASTER_ROUNDTRIP_AUDIT",
            "expected_pixel_count":len(expected),
            "rasterized_graph_pixel_count":len(actual),
            "missing_pixel_count":len(missing),
            "extra_pixel_count":len(extra),
            "roundtrip_exact":not missing and not extra,
            "canonical_promoted":False,
            "splash_reconstruction_allowed":False,
            "next_gate":"reference overlay audit" if not missing and not extra else "repair graph compression",
        },
        "missing_pixels":[list(p) for p in missing],
        "extra_pixels":[list(p) for p in extra],
    }
    (args.out/"canonical_graph_roundtrip_audit.json").write_text(json.dumps(result,indent=2),encoding="utf-8")
    print(json.dumps(result["meta"],indent=2))
    if missing or extra:
        raise SystemExit("Canonical graph roundtrip mismatch")

if __name__=="__main__": main()
